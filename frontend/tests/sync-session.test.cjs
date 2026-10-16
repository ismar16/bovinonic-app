const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const ts = require('typescript');

function store(value) {
  return { value, set(next) { this.value = next; } };
}

function table(key = 'id') {
  const rows = new Map();
  let sequence = 0;
  const copy = (value) => structuredClone(value);
  const api = {
    async put(row) { rows.set(row[key], copy(row)); },
    async add(row) { const id = ++sequence; rows.set(id, copy({ ...row, id })); return id; },
    async get(id) { const row = rows.get(id); return row && copy(row); },
    async toArray() { return [...rows.values()].map(copy); },
    async count() { return rows.size; },
    async clear() { rows.clear(); },
    async delete(id) { rows.delete(id); },
    async bulkDelete(ids) { ids.forEach((id) => rows.delete(id)); },
    async bulkPut(values) { for (const row of values) await api.put(row); },
    orderBy() { return api; },
    filter(predicate) {
      return { async count() { return [...rows.values()].filter(predicate).length; } };
    }
  };
  return api;
}

function load(name, dependencies) {
  const source = readFileSync(join(__dirname, '../src/lib', `${name}.ts`), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
  }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', code)(module, module.exports, (id) => {
    if (!(id in dependencies)) throw new Error(`Unexpected import: ${id}`);
    return dependencies[id];
  });
  return module.exports;
}

function setup() {
  const stores = {
    currentFarm: store({ id: 'farm-a', name: 'A', role: 'admin' }),
    online: store(true), syncing: store(false), sessionChanging: store(false),
    sessionNotice: store(null), pendingCount: store(0), lastSyncResult: store(null),
    syncError: store(null), syncWarnings: store([]), sessionUser: store({ id: 1 }),
    availableFarms: store([])
  };
  const db = {};
  const names = ['owners', 'brands', 'paddocks', 'animals', 'weighings', 'milkings',
    'reproductive_events', 'health_events', 'outbox', 'sync_meta'];
  for (const name of names) db[name] = table(name === 'sync_meta' ? 'key' : 'id');
  db.tables = names.map((name) => db[name]);
  db.table = (name) => db[name];
  db.transaction = async (...args) => args.at(-1)();
  const api = {
    ApiError: class extends Error {},
    pull: async () => ({ sync_cursor: '2026-10-16T00:00:00Z' }),
    pushBatch: async () => ({}), logout: async () => {}
  };
  const dependencies = {
    '$app/environment': { browser: true },
    'svelte/store': { get: (s) => s.value },
    './api': api, './db': { db }, './stores': stores,
    '$app/navigation': { goto: async () => {} }
  };
  const sync = load('sync', dependencies);
  return { stores, db, api, sync, dependencies };
}

test('an edit queued during upload survives acknowledgement and download', async () => {
  const { sync, db, api } = setup();
  await sync.enqueue('animals', { id: 'cow', name: 'Original' });
  api.pushBatch = async () => {
    await sync.enqueue('animals', { id: 'cow', name: 'Edited while uploading' });
    return { animals: [{ id: 'cow', status: 'updated' }] };
  };
  api.pull = async () => ({ animals: [{ id: 'cow', name: 'Old server copy' }],
    sync_cursor: '2026-10-16T00:00:00Z' });
  await sync.syncNow();
  assert.equal(await db.outbox.count(), 1);
  assert.equal((await db.outbox.toArray())[0].payload.name, 'Edited while uploading');
  assert.equal((await db.animals.get('cow')).name, 'Edited while uploading');
});

test('multiple offline edits to the same record upload only its latest version', async () => {
  const { sync, db, api } = setup();
  await sync.enqueue('animals', { id: 'cow', name: 'First' });
  await sync.enqueue('animals', { id: 'cow', name: 'Latest' });
  api.pushBatch = async (_farm, collections) => {
    assert.deepEqual(collections.animals, [{ id: 'cow', name: 'Latest' }]);
    return { animals: [{ id: 'cow', status: 'created' }] };
  };
  await sync.syncNow();
  assert.equal(await db.outbox.count(), 0);
});

test('new sync ignores the old device cursor and saves the server cursor', async () => {
  const { sync, db, api } = setup();
  await db.sync_meta.put({ key: 'last_pull_at', value: '2099-01-01T00:00:00Z' });
  const cursors = [];
  api.pull = async (_farm, since) => {
    cursors.push(since);
    return { sync_cursor: '2026-10-16T00:00:00Z' };
  };
  await sync.syncNow();
  await sync.syncNow();
  assert.deepEqual(cursors, [undefined, '2026-10-16T00:00:00Z']);
});

test('failed download leaves the previous cursor intact', async () => {
  const { sync, db, api } = setup();
  await db.sync_meta.put({ key: 'last_pull_server_at_v1', value: 'previous' });
  api.pull = async () => { throw new TypeError('offline'); };
  await sync.syncNow();
  assert.equal((await db.sync_meta.get('last_pull_server_at_v1')).value, 'previous');
});

test('pending merged milking is retained for the next upload', async () => {
  const { sync, db, api } = setup();
  await sync.enqueue('milkings', { id: 'local', liters: '5' });
  api.pushBatch = async () => {
    await sync.enqueue('milkings', { id: 'local', liters: '8' });
    return { milkings: [{ id: 'local', status: 'updated', merged_into: 'server' }] };
  };
  await sync.syncNow();
  assert.equal((await db.milkings.get('local')).liters, '8');
  assert.equal(await db.outbox.count(), 1);
});

test('logout and switching farms preserve pending data', async () => {
  const { db, stores, dependencies } = setup();
  const session = load('session', { ...dependencies, './sync': { syncNow: async () => {} } });
  await db.outbox.add({ record_id: 'cow' });
  await db.animals.put({ id: 'cow' });
  assert.equal(await session.logoutAndWipe(), false);
  assert.equal(await session.switchFarm({ id: 'farm-b', name: 'B', role: 'admin' }), false);
  assert.equal(stores.currentFarm.value.id, 'farm-a');
  assert.equal(await db.outbox.count(), 1);
  assert.ok(await db.animals.get('cow'));
  assert.match(stores.sessionNotice.value, /pendientes/);
});

test('an active sync blocks session changes', async () => {
  const { stores, dependencies, db } = setup();
  const session = load('session', { ...dependencies, './sync': { syncNow: async () => {} } });
  await db.animals.put({ id: 'cow' });
  stores.syncing.set(true);
  assert.equal(await session.logoutAndWipe(), false);
  assert.ok(await db.animals.get('cow'));
});

test('session changes clear only a fully synced database and release the lock', async () => {
  const { stores, dependencies, db } = setup();
  let syncs = 0;
  const session = load('session', { ...dependencies, './sync': { syncNow: async () => { syncs++; } } });
  await db.animals.put({ id: 'cow' });
  assert.equal(await session.switchFarm({ id: 'farm-b', name: 'B', role: 'admin' }), true);
  assert.equal(stores.currentFarm.value.id, 'farm-b');
  assert.equal(await db.animals.count(), 0);
  assert.equal(stores.sessionChanging.value, false);
  assert.equal(syncs, 1);
});

test('forms cannot enqueue while a session change is clearing local data', async () => {
  const { sync, stores, db } = setup();
  stores.sessionChanging.set(true);
  await assert.rejects(sync.enqueue('animals', { id: 'cow' }), /cambio de sesión/);
  assert.equal(await db.outbox.count(), 0);
});

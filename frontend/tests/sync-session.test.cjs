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
  const names = ['owners', 'brands', 'paddocks', 'lots', 'animals', 'weighings', 'milkings',
    'reproductive_events', 'health_events', 'outbox', 'sync_meta'];
  for (const name of names) db[name] = table(name === 'sync_meta' ? 'key' : 'id');
  db.tables = names.map((name) => db[name]);
  db.table = (name) => db[name];
  db.transaction = async (...args) => args.at(-1)();
  const api = {
    ApiError: class extends Error {},
    syncState: async () => ({ data_version: 0, farm_name: 'A' }),
    pull: async () => ({ sync_cursor: '2026-10-16T00:00:00Z' }),
    pushBatch: async () => ({}), logout: async () => {}
  };
  const dependencies = {
    '$app/environment': { browser: true },
    'svelte/store': { get: (s) => s.value },
    './api': api, './db': { db }, './stores': stores, './forms': load('forms', {}),
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
    assert.deepEqual(collections.animals, [{ id: 'cow', name: 'Latest', farm: 'farm-a' }]);
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
  await db.sync_meta.put({ key: 'last_pull_server_at_v2', value: 'previous' });
  api.pull = async () => { throw new TypeError('offline'); };
  await sync.syncNow();
  assert.equal((await db.sync_meta.get('last_pull_server_at_v2')).value, 'previous');
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

test('new offline animals retain their farm and appear in farm-scoped queries', async () => {
  const { sync, db } = setup();
  await sync.enqueue('animals', { id: 'new-calf', tag: 'NI-100' });
  assert.equal((await db.animals.get('new-calf')).farm, 'farm-a');
  assert.equal((await db.outbox.toArray())[0].payload.farm, 'farm-a');
});

test('saving without an assigned farm cannot orphan data', async () => {
  const { sync, db, stores } = setup();
  stores.currentFarm.set(null);
  await assert.rejects(sync.enqueue('animals', { id: 'calf' }), /finca/);
  assert.equal(await db.animals.count(), 0);
});

test('business dates remain on the Nicaragua day after midnight UTC', () => {
  const { farmDate, addDateDays } = load('dates', {});
  assert.equal(farmDate(new Date('2026-10-16T02:30:00Z')), '2026-10-15');
  assert.equal(farmDate(new Date('2026-10-16T06:01:00Z')), '2026-10-16');
  assert.equal(addDateDays('2026-12-31', 1), '2027-01-01');
  assert.equal(addDateDays('2024-02-28', 1), '2024-02-29');
});

test('operators cannot queue animal edits that the API would reject', async () => {
  const { sync, db, stores } = setup();
  stores.currentFarm.set({ id: 'farm-a', role: 'operator' });
  await assert.rejects(sync.enqueue('animals', { id: 'cow' }), /rol/);
  assert.equal(await db.outbox.count(), 0);
  await sync.enqueue('weighings', { id: 'weight', animal: 'cow', weight_kg: '200' });
  assert.equal(await db.outbox.count(), 1);
});
const verifiedUser = { id: 1, username: 'boss', farms: [{ farm: 'farm-a', farm_name: 'A', role: 'admin' }] };
test('lot and bulk writes retain their farm and upload lot before dependent animals', async () => {
  const { sync, db, api } = setup();
  await sync.enqueueMany([{ collection: 'lots', payload: { id: 'lot', name: 'Reemplazo' } }, ...Array.from({ length: 25 }, (_, i) => ({ collection: 'animals', payload: { id: `cow-${i}`, lot: 'lot' } }))]);
  let calls = 0;
  api.pushBatch = async (_farm, collections) => {
    calls++;
    if (calls === 1) assert.equal(collections.lots[0].id, 'lot');
    for (const a of collections.animals) assert.equal(a.farm, 'farm-a');
    return Object.fromEntries(Object.entries(collections).map(([name, rows]) => [name, rows.map(row => ({ id: row.id, status: 'created' }))]));
  };
  await sync.syncNow();
  assert.equal(calls, 2); assert.equal(await db.outbox.count(), 0); assert.equal(await db.animals.count(), 25);
});
test('insufficient role rejects the entire local operation before writing', async () => {
  const { sync, db, stores } = setup(); stores.currentFarm.set({ id: 'farm-a', role: 'operator' });
  await assert.rejects(sync.enqueueMany([{ collection: 'weighings', payload: { id: 'w' } }, { collection: 'lots', payload: { id: 'lot' } }]), /rol/);
  assert.equal(await db.outbox.count(), 0); assert.equal(await db.weighings.count(), 0);
});
test('recent verified session reopens offline without extending validity', async () => {
  const { db, api, stores, dependencies } = setup(); const session = load('session', { ...dependencies, './sync': { syncNow: async () => {} } });
  api.me = async () => verifiedUser; await session.restoreSession();
  const snapshot = (await db.sync_meta.get('offline_session_v1')).value;
  stores.sessionUser.set(null); stores.currentFarm.set(null); api.me = async () => { throw new TypeError('offline'); };
  await session.restoreSession(); assert.equal(stores.currentFarm.value.id, 'farm-a'); assert.equal((await db.sync_meta.get('offline_session_v1')).value, snapshot);
});
test('expired offline verification and server rejection cannot reopen cached access', async () => {
  const { db, api, dependencies } = setup(); const session = load('session', { ...dependencies, './sync': { syncNow: async () => {} } });
  await db.sync_meta.put({ key: 'offline_session_v1', value: JSON.stringify({ user: verifiedUser, farmId: 'farm-a', verifiedAt: Date.now() - 15 * 86400000 }) });
  api.me = async () => { throw new TypeError('offline'); }; await assert.rejects(session.restoreSession(), /internet/);
  api.me = async () => { throw new api.ApiError('401'); }; await assert.rejects(session.restoreSession(), /401/);
});
test('switching accounts preserves the original user pending work', async () => {
  const { db, dependencies, stores } = setup(); const session = load('session', { ...dependencies, './sync': { syncNow: async () => {} } });
  await session.acceptUser(verifiedUser); await db.outbox.add({ record_id: 'cow' });
  await assert.rejects(session.acceptUser({ ...verifiedUser, id: 2 }), /pendientes/); assert.equal(stores.sessionUser.value.id, 1); assert.equal(await db.outbox.count(), 1);
});
test('forms reject impossible dates and invalid numeric quantities', () => {
  const { validDate, decimalValue } = load('forms', {}); assert.equal(validDate('2026-02-30'), false); assert.equal(validDate('2024-02-29'), true); assert.equal(decimalValue('12,50'), 12.5);
  assert.equal(decimalValue('0', true), 0); for (const v of ['-1', 'NaN', 'Infinity', '2.123', '', '1e3', '0']) assert.throws(() => decimalValue(v));
});
function reportDeps(weighings = [], events = []) {
  const dates = load('dates', {}); const animals = [{ id: 'cow', farm: 'farm-a', status: 'active', sex: 'H', category: 'cow_lactating' }];
  const db = { animals: { where: () => ({ equals: () => ({ toArray: async () => animals }) }) }, weighings: { toArray: async () => weighings }, reproductive_events: { toArray: async () => events } };
  return { './dates': dates, '$lib/dates': dates, './db': { db }, '$app/environment': { browser: true } };
}
test('weight alerts require distinct dates and use the latest updated reading per date', async () => {
  let report = load('reports', reportDeps([{ animal: 'cow', date: '2026-10-01', weight_kg: '100' }, { animal: 'cow', date: '2026-10-01', weight_kg: '90' }]));
  assert.deepEqual(await report.gmdAlerts('farm-a'), []);
  report = load('reports', reportDeps([{ animal: 'cow', date: '2026-09-01', weight_kg: '100' }, { animal: 'cow', date: '2026-10-01', weight_kg: '110', updated_at: '2026-10-01T00:00:00Z' }, { animal: 'cow', date: '2026-10-01', weight_kg: '90', updated_at: '2026-10-01T02:00:00Z' }]));
  const rows = await report.gmdAlerts('farm-a'); assert.equal(rows[0].lastWeight, 90); assert.equal(rows[0].days, 30);
});
test('calving, abortion and empty diagnoses cancel an old calving forecast', async () => {
  const { farmDate, addDateDays } = load('dates', {}); const today = farmDate();
  const service = { animal: 'cow', type: 'service', date: addDateDays(today, -270), estimated_calving_date: addDateDays(today, 13) };
  for (const type of ['calving', 'abortion', 'palpation']) {
    const report = load('alerts', reportDeps([], [service, { animal: 'cow', date: today, type, palpation_result: 'empty' }]));
    assert.equal((await report.computeReproAlerts('farm-a')).calvingSoon.length, 0);
  }
});


test('a temporary API failure does not permanently lock out manual or automatic retries', async () => {
  const { sync, api, stores } = setup();
  stores.online.set(false);
  let retried = false;
  api.pull = async () => { retried = true; stores.online.set(true); return { sync_cursor: 'recovered' }; };
  await sync.syncNow();
  assert.equal(retried, true);
  assert.equal(stores.online.value, true);
});


test('server reset clears stale records and pending uploads before any push', async () => {
  const { sync, db, api, stores } = setup();
  await sync.enqueue('animals', { id: 'old-test' });
  await db.sync_meta.put({ key: 'last_pull_server_at_v2', value: 'old-cursor' });
  api.syncState = async () => ({ data_version: 1, farm_name: 'Finca La Bendición' });
  let pushed = false;
  api.pushBatch = async () => { pushed = true; return {}; };
  api.pull = async (_farm, since) => { assert.equal(since, undefined); return { animals: [{ id: 'real-cow', farm: 'farm-a' }], sync_cursor: 'new-cursor' }; };
  await sync.syncNow();
  assert.equal(pushed, false);
  assert.equal(await db.outbox.count(), 0);
  assert.equal(await db.animals.get('old-test'), undefined);
  assert.ok(await db.animals.get('real-cow'));
  assert.equal(stores.currentFarm.value.name, 'Finca La Bendición');
  assert.equal((await db.sync_meta.get('farm_data_version:farm-a')).value, '1');
});

test('current-version offline records survive sync and include their version on upload', async () => {
  const { sync, db, api } = setup();
  await db.sync_meta.put({ key: 'farm_data_version:farm-a', value: '1' });
  await sync.enqueue('animals', { id: 'real-cow' });
  api.syncState = async () => ({ data_version: 1, farm_name: 'Real farm' });
  api.pushBatch = async (_farm, data, version) => { assert.equal(version, 1); assert.equal(data.animals[0].id, 'real-cow'); return { animals: [{ id: 'real-cow', status: 'created' }] }; };
  await sync.syncNow();
  assert.equal(await db.outbox.count(), 0);
  assert.ok(await db.animals.get('real-cow'));
});

test('an unreachable reset check preserves local data and does not upload', async () => {
  const { sync, db, api } = setup();
  await sync.enqueue('animals', { id: 'pending' });
  api.syncState = async () => { throw new TypeError('offline'); };
  api.pushBatch = async () => { assert.fail('must not upload without checking reset version'); };
  await sync.syncNow();
  assert.equal(await db.outbox.count(), 1);
  assert.ok(await db.animals.get('pending'));
});

test('a server version rollback cannot erase current real records', async () => {
  const { sync, db, api } = setup();
  await db.sync_meta.put({ key: 'farm_data_version:farm-a', value: '1' });
  await sync.enqueue('animals', { id: 'real-cow' });
  api.syncState = async () => ({ data_version: 0, farm_name: 'Old server' });
  api.pushBatch = async () => { assert.fail('must not upload to an old database version'); };
  await sync.syncNow();
  assert.ok(await db.animals.get('real-cow'));
  assert.equal(await db.outbox.count(), 1);
});

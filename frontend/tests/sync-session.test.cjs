const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const ts = require('typescript');

function store(value) {
  const subscribers = new Set();
  return { value, set(next) { this.value = next; for (const subscriber of subscribers) subscriber(next); },
    subscribe(fn) { subscribers.add(fn); fn(this.value); return () => subscribers.delete(fn); } };
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

function load(name, dependencies, globals = {}) {
  const source = readFileSync(join(__dirname, '../src/lib', `${name}.ts`), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
  }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', ...Object.keys(globals), code)(module, module.exports, (id) => {
    if (!(id in dependencies)) throw new Error(`Unexpected import: ${id}`);
    return dependencies[id];
  }, ...Object.values(globals));
  return module.exports;
}

function setup(globals = {}) {
  const stores = {
    currentFarm: store({ id: 'farm-a', name: 'A', role: 'admin' }),
    online: store(true), syncing: store(false), sessionChanging: store(false),
    sessionNotice: store(null), pendingCount: store(0), lastSyncResult: store(null),
    syncError: store(null), syncWarnings: store([]), sessionUser: store({ id: 1 }),
    availableFarms: store([])
  };
  const db = {};
  const names = ['owners', 'brands', 'paddocks', 'lots', 'animals', 'agreements', 'sales', 'sale_payments', 'sale_expenses', 'weighings', 'milkings', 'daily_milk',
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
  const sync = load('sync', dependencies, globals);
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
  await db.sync_meta.put({ key: 'last_pull_server_at_v7', value: 'previous' });
  api.pull = async () => { throw new TypeError('offline'); };
  await sync.syncNow();
  assert.equal((await db.sync_meta.get('last_pull_server_at_v7')).value, 'previous');
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
  await db.sync_meta.put({ key: 'last_pull_server_at_v7', value: 'old-cursor' });
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

function autoSyncSetup() {
  let now = 0, sequence = 0;
  const timers = new Map(), intervals = new Map();
  function events() {
    const listeners = new Map();
    return { addEventListener(type, fn) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); },
      removeEventListener(type, fn) { listeners.get(type)?.delete(fn); },
      emit(type) { for (const fn of listeners.get(type) ?? []) fn(); },
      count() { return [...listeners.values()].reduce((sum, group) => sum + group.size, 0); } };
  }
  const window = events(), document = { ...events(), visibilityState: 'visible' };
  const context = setup({ window, document,
    setTimeout(fn, delay) { const id = ++sequence; timers.set(id, { fn, at: now + delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval(fn) { const id = ++sequence; intervals.set(id, fn); return id; },
    clearInterval(id) { intervals.delete(id); } });
  return { ...context, window, document, timers, intervals,
    async tick(ms) {
      const end = now + ms;
      for (;;) {
        const next = [...timers.entries()].filter(([, timer]) => timer.at <= end).sort((a,b) => a[1].at - b[1].at)[0];
        if (!next) break;
        now = next[1].at; timers.delete(next[0]); next[1].fn();
        await new Promise(setImmediate);
      }
      now = end; await new Promise(setImmediate);
    } };
}

test('saving several records quickly automatically uploads their latest values together', async () => {
  const ctx = autoSyncSetup(); const stop = ctx.sync.startAutoSync(); let requests = 0;
  try {
    ctx.api.pushBatch = async (_farm, data) => { requests++; assert.equal(data.animals[0].name, 'Latest'); assert.equal(data.animals.length, 2); return { animals: data.animals.map(row => ({ id: row.id, status: 'created' })) }; };
    await ctx.sync.enqueue('animals', { id: 'cow', name: 'First' });
    await ctx.tick(1000);
    await ctx.sync.enqueueMany([{ collection: 'animals', payload: { id: 'cow', name: 'Latest' } }, { collection: 'animals', payload: { id: 'calf' } }]);
    await ctx.tick(1499); assert.equal(requests, 0);
    await ctx.tick(1); assert.equal(requests, 1); assert.equal(await ctx.db.outbox.count(), 0);
  } finally { stop(); }
});

test('a save during a slow upload is automatically sent after that upload finishes', async () => {
  const ctx = autoSyncSetup(); const stop = ctx.sync.startAutoSync(); let release, requests = 0;
  try {
    const gate = new Promise(resolve => release = resolve);
    ctx.api.pushBatch = async (_farm, data) => { requests++; if (requests === 1) await gate; return { animals: data.animals.map(row => ({ id: row.id, status: 'updated' })) }; };
    await ctx.sync.enqueue('animals', { id: 'cow', name: 'First' });
    await ctx.tick(1500); assert.equal(requests, 1); assert.equal(ctx.stores.syncing.value, true);
    await ctx.sync.enqueue('animals', { id: 'cow', name: 'Edited during upload' });
    await ctx.tick(1500); assert.equal(requests, 1);
    release(); await new Promise(setImmediate); await ctx.tick(0);
    assert.equal(requests, 2); assert.equal(await ctx.db.outbox.count(), 0);
    assert.equal((await ctx.db.animals.get('cow')).name, 'Edited during upload');
  } finally { release?.(); stop(); }
});

test('failed automatic sync preserves pending work and reconnect immediately retries it', async () => {
  const ctx = autoSyncSetup(); const stop = ctx.sync.startAutoSync(); let requests = 0;
  try {
    ctx.api.syncState = async () => { requests++; throw new TypeError('offline'); };
    await ctx.sync.enqueue('animals', { id: 'cow' }); await ctx.tick(1500);
    assert.equal(requests, 1); assert.equal(await ctx.db.outbox.count(), 1);
    await ctx.tick(10000); assert.equal(requests, 1);
    ctx.api.syncState = async () => ({ data_version: 0, farm_name: 'A' });
    ctx.api.pushBatch = async () => ({ animals: [{ id: 'cow', status: 'created' }] });
    ctx.window.emit('online'); await ctx.tick(0);
    assert.equal(await ctx.db.outbox.count(), 0);
  } finally { stop(); }
});

test('returning to the app and the periodic timer both refresh the server data', async () => {
  const ctx = autoSyncSetup(); const stop = ctx.sync.startAutoSync(); let pulls = 0;
  try {
    ctx.api.pull = async () => { pulls++; return {}; };
    ctx.document.visibilityState = 'hidden'; ctx.document.emit('visibilitychange'); await ctx.tick(0); assert.equal(pulls, 0);
    ctx.document.visibilityState = 'visible'; ctx.document.emit('visibilitychange'); await ctx.tick(0); assert.equal(pulls, 1);
    for (const interval of ctx.intervals.values()) interval(); await ctx.tick(0); assert.equal(pulls, 2);
  } finally { stop(); }
});

test('automatic sync waits for session changes and cleanup cancels scheduled work', async () => {
  const ctx = autoSyncSetup(); const stop = ctx.sync.startAutoSync(); let uploads = 0;
  ctx.api.pushBatch = async () => { uploads++; return { animals: [{ id: 'cow', status: 'created' }] }; };
  await ctx.sync.enqueue('animals', { id: 'cow' }); ctx.stores.sessionChanging.set(true);
  await ctx.tick(1500); assert.equal(uploads, 0);
  ctx.stores.sessionChanging.set(false); await ctx.tick(0); assert.equal(uploads, 1);
  await ctx.sync.enqueue('animals', { id: 'another' }); stop();
  await ctx.tick(2000); assert.equal(uploads, 1);
  assert.equal(ctx.timers.size, 0); assert.equal(ctx.intervals.size, 0);
  assert.equal(ctx.window.count(), 0); assert.equal(ctx.document.count(), 0);
});

const agreementHelpers = () => load('agreements', { './forms': load('forms', {}), './dates': load('dates', {}) });

test('client and server use the same settlement vectors, including rounding, losses and all modalities', () => {
  const { agreementSettlement } = agreementHelpers();
  const vectors = JSON.parse(readFileSync(join(__dirname, '../../backend/apps/livestock/settlement_vectors.json'), 'utf8').replace(/^\uFEFF/, ''));
  for (const vector of vectors) {
    const result = agreementSettlement(vector);
    for (const [key, value] of Object.entries(vector.expected)) assert.equal(result[key], value, `${vector.name}:${key}`);
    if (vector.kind !== 'pasture') {
      const cents = value => BigInt(value.replace('.', ''));
      assert.equal(cents(result.owner_total) + cents(result.partner_total), cents(result.sale_value));
    }
  }
});

function draftAgreement() {
  return { id: 'agreement', farm: 'farm-a', title: 'A medias', owner_name: 'Owner', partner_name: 'Partner', external_farm: 'Other farm', kind: 'weight_gain', currency: 'NIO', owner_share: '50', start_date: '2026-09-01', end_date: '2026-09-30', status: 'active', notes: '',
    animals: [{ animal: 'cow', tag: 'NI-1', name: '', initial_weight: '180', final_weight: '280', price_per_kg: '100', final_date: '2026-09-30' }],
    expenses: [{ id: 'expense', date: '2026-09-15', concept: 'Medicines', amount: '1000', paid_by: 'owner', animal: null }] };
}

test('settlement validation normalizes comma decimals and does not modify the draft', () => {
  const { validateAgreement } = agreementHelpers(); const draft = draftAgreement(); draft.animals[0].initial_weight = '180,00';
  const settled = validateAgreement(draft, true);
  assert.equal(settled.status, 'settled'); assert.equal(settled.animals[0].initial_weight, '180.00');
  assert.equal(settled.settlement.owner_total, '23500.00'); assert.equal(draft.status, 'active');
});

test('closing validates dates, required sale data, out-of-agreement expenses and explicit losses', () => {
  const { validateAgreement } = agreementHelpers();
  let draft = draftAgreement(); draft.animals[0].final_date = null; assert.throws(() => validateAgreement(draft, true), /fecha final/);
  draft = draftAgreement(); draft.expenses[0].animal = 'other-cow'; assert.throws(() => validateAgreement(draft), /gastos/);
  draft = draftAgreement(); draft.expenses[0].date = '2026-08-30'; assert.throws(() => validateAgreement(draft), /fecha/);
  draft = draftAgreement(); draft.animals[0].final_weight = '170'; assert.throws(() => validateAgreement(draft, true), /negativo/);
  draft.accept_loss = true; assert.equal(validateAgreement(draft,true).settlement.net_gain, '-2000.00');
});

test('agreement writes require administrator and survive ordinary sync', async () => {
  const { sync, stores, db, api } = setup(); stores.currentFarm.set({ id: 'farm-a', role: 'technician' });
  await assert.rejects(sync.enqueue('agreements', draftAgreement()), /rol/); assert.equal(await db.outbox.count(), 0);
  stores.currentFarm.set({ id: 'farm-a', role: 'admin' });
  await sync.enqueue('agreements', draftAgreement());
  api.pushBatch = async (_farm, data) => { assert.equal(data.agreements[0].farm, 'farm-a'); return { agreements: [{ id: 'agreement', status: 'created' }] }; };
  api.pull = async () => ({ agreements: [{ ...draftAgreement(), title: 'Server validated' }] });
  await sync.syncNow(); assert.equal(await db.outbox.count(), 0); assert.equal((await db.agreements.get('agreement')).title, 'Server validated');
});

const saleHelpers = () => load('sales', { './agreements': agreementHelpers(), './forms': load('forms', {}), './dates': load('dates', {}) });
function draftSale() {
  return { id:'sale', farm:'farm-a', buyer:' Buyer ', buyer_phone:'', currency:'NIO', date:'2026-10-01', notes:'', lines:[{ animal:'cow', tag:'NI-1', weight_kg:'280', price_per_kg:'100', agreement:null, agreement_version:null, expenses:[] }] };
}

test('sale preview normalizes decimals and agrees with the server settlement including partial cents', () => {
  const {validateSale,allocatedExpenses}=saleHelpers(); const agreement=draftAgreement(); agreement.updated_at='2026-10-01T00:00:00Z';
  agreement.animals.push({...agreement.animals[0],animal:'cow-2',tag:'NI-2'}); agreement.expenses[0].amount='1000.01';
  const draft=draftSale(); draft.lines[0].weight_kg='280,00'; const result=validateSale(draft,[agreement]);
  assert.equal(result.total,'28000.00'); assert.equal(result.lines[0].settlement.expenses,'500.01');
  assert.equal(result.lines[0].settlement.owner_total,'23250.01'); assert.equal(result.lines[0].settlement.partner_total,'4749.99');
  assert.equal(allocatedExpenses(agreement,'cow-2')[0].amount,'500.00'); assert.equal(draft.lines[0].weight_kg,'280,00');
  assert.equal(result.lines[0].agreement_version,agreement.updated_at);
});

test('sales reject missing weights, duplicates, wrong currency and unconfirmed losses', () => {
  const {validateSale}=saleHelpers(); let draft=draftSale(); draft.lines[0].weight_kg=''; assert.throws(()=>validateSale(draft,[]));
  draft=draftSale(); draft.lines.push({...draft.lines[0]}); assert.throws(()=>validateSale(draft,[]),/repetir/);
  const agreement=draftAgreement(); agreement.updated_at='2026-10-01T00:00:00Z'; draft=draftSale(); draft.currency='USD'; assert.throws(()=>validateSale(draft,[agreement]),/moneda/);
  draft=draftSale(); draft.lines[0].weight_kg='170'; assert.throws(()=>validateSale(draft,[agreement]),/pérdidas/);
  draft.accept_loss=true; assert.equal(validateSale(draft,[agreement]).lines[0].settlement.net_gain,'-2000.00');
  draft.accept_loss='true'; assert.throws(()=>validateSale(draft,[agreement]),/pérdidas/);
});

test('sale costs belong to one animal and do not mutate original agreement expenses', () => {
  const {validateSale}=saleHelpers(); const agreement=draftAgreement(); agreement.updated_at='2026-10-01T00:00:00Z';
  const draft=draftSale(); draft.lines[0].expenses=[{concept:'Transport',amount:'500',paid_by:'partner'}];
  const result=validateSale(draft,[agreement]); assert.equal(result.lines[0].settlement.expenses,'1500.00');
  assert.equal(result.lines[0].settlement.partner_total,'4750.00'); assert.equal(agreement.expenses.length,1);
  assert.throws(()=>validateSale(draft,[]),/pagador/);
});

test('sale and payment financial records require admin and sync without losing receipt', async () => {
  const {sync,db,stores,api}=setup(); stores.currentFarm.set({id:'farm-a',role:'technician'});
  await assert.rejects(sync.enqueue('sales',draftSale()),/rol/); await assert.rejects(sync.enqueue('sale_payments',{id:'payment'}),/rol/);
  stores.currentFarm.set({id:'farm-a',role:'admin'}); await sync.enqueue('sales',draftSale());
  api.pushBatch=async(_farm,data)=>{assert.equal(data.sales[0].farm,'farm-a');return {sales:[{id:'sale',status:'created'}]};};
  api.pull=async()=>({sales:[{...draftSale(),total:'28000.00'}],animals:[{id:'cow',status:'sold'}]});
  await sync.syncNow();assert.equal(await db.outbox.count(),0);assert.equal((await db.sales.get('sale')).total,'28000.00');assert.equal((await db.animals.get('cow')).status,'sold');
});

test('correcting a financial pending replaces earlier queue entries instead of accepting an older chunk', async () => {
  const {sync,db,stores}=setup();await sync.enqueue('sales',draftSale());
  for(let i=0;i<25;i++)await sync.enqueue('weighings',{id:`w-${i}`});
  await sync.enqueue('sales',{...draftSale(),buyer:'Corrected'});
  assert.equal((await db.outbox.toArray()).filter((r)=>r.collection==='sales').length,1);
  stores.syncing.set(true);await assert.rejects(sync.enqueue('sales',{...draftSale(),buyer:'Inflight'}),/termine/);
  assert.equal((await db.sales.get('sale')).buyer,'Corrected');
});

test('a lost financial response is reconciled from the server before editing and never erases another pending', async () => {
  const {sync,db,api}=setup();await sync.enqueue('sales',draftSale());await sync.enqueue('animals',{id:'other'});
  api.financialReceipt=async()=>({record:{...draftSale(),total:'28000.00',buyer:'Authoritative'}});
  assert.equal(await sync.reviewFinancialPending('sales','sale'),true);
  assert.equal((await db.sales.get('sale')).buyer,'Authoritative');assert.equal(await db.outbox.count(),1);
  assert.equal((await db.outbox.toArray())[0].record_id,'other');
  await sync.enqueue('sale_payments',{id:'payment'});api.financialReceipt=async()=>({record:null});
  assert.equal(await sync.reviewFinancialPending('sale_payments','payment'),false);assert.equal(await db.outbox.count(),2);
});

function confirmedSale() {
  const agreement=draftAgreement();agreement.updated_at='2026-10-01T00:00:00Z';
  const sale=saleHelpers().validateSale(draftSale(),[agreement]);
  Object.assign(sale.lines[0],{kind:'weight_gain',initial_weight:'180',owner_share:'50'});
  return sale;
}
function lateExpense(overrides={}) {
  return {id:'late',farm:'farm-a',sale:'sale',animal:'cow',date:'2026-09-15',concept:'Medicine forgotten',amount:'1000',paid_by:'owner',...overrides};
}

test('later sale expense recalculates from snapshots and merging the server receipt never deducts twice',()=>{
  const {saleWithExpenses,validateSaleExpense}=saleHelpers();const sale=confirmedSale();
  const added=validateSaleExpense(lateExpense(),sale,[]);const adjusted=saleWithExpenses(sale,[added]);
  assert.equal(adjusted.lines[0].settlement.net_gain,'8000.00');assert.equal(adjusted.lines[0].settlement.expenses,'2000.00');
  assert.equal(adjusted.lines[0].settlement.owner_total,'24000.00');assert.equal(adjusted.lines[0].settlement.partner_total,'4000.00');
  const again=saleWithExpenses(adjusted,[added]);assert.deepEqual(again,adjusted);
  assert.equal(sale.lines[0].settlement.net_gain,'9000.00');assert.equal(sale.total,adjusted.total);
});

test('later sale expenses validate animals, dates, payer, exact decimals and loss acknowledgement',()=>{
  const {validateSaleExpense}=saleHelpers();const sale=confirmedSale();
  for(const bad of [{animal:'other'},{date:'2099-01-01'},{amount:'NaN'},{amount:'0'},{amount:'1.001'},{concept:' '}])assert.throws(()=>validateSaleExpense(lateExpense(bad),sale,[]));
  assert.throws(()=>validateSaleExpense(lateExpense({amount:'11000'}),sale,[]),/pérdidas/);
  const result=validateSaleExpense(lateExpense({amount:'11000',accept_loss:true}),sale,[]);assert.equal(result.amount,'11000.00');
  assert.throws(()=>validateSaleExpense(lateExpense({amount:'11000',accept_loss:'true'}),sale,[]),/pérdidas/);
});

test('later expenses preserve both payers and derive net income for own animals',()=>{
  const {saleWithExpenses}=saleHelpers();let sale=confirmedSale();
  let result=saleWithExpenses(sale,[lateExpense(),lateExpense({id:'second',paid_by:'partner',amount:'500'})]);
  assert.equal(result.lines[0].settlement.expenses,'2500.00');assert.equal(result.lines[0].settlement.partner_total,'4250.00');
  sale=saleHelpers().validateSale(draftSale(),[]);result=saleWithExpenses(sale,[lateExpense()]);
  assert.equal(result.lines[0].net_after_expenses,'27000.00');assert.equal(result.lines[0].settlement,null);
});

test('later expense sync enforces admin, survives failure and pulls adjusted sale and agreement',async()=>{
  const {sync,db,stores,api}=setup();stores.currentFarm.set({id:'farm-a',role:'operator'});
  await assert.rejects(sync.enqueue('sale_expenses',lateExpense()),/rol/);stores.currentFarm.set({id:'farm-a',role:'admin'});
  await sync.enqueue('sale_expenses',lateExpense());api.pushBatch=async()=>{throw new TypeError('network');};
  await sync.syncNow();assert.equal(await db.outbox.count(),1);
  api.pushBatch=async()=>({sale_expenses:[{id:'late',status:'created'}]});
  api.pull=async()=>({sale_expenses:[lateExpense()],sales:[saleHelpers().saleWithExpenses(confirmedSale(),[lateExpense()])],agreements:[{...draftAgreement(),settlement:{expenses:'2000.00'}}]});
  await sync.syncNow();assert.equal(await db.outbox.count(),0);assert.equal((await db.sales.get('sale')).lines[0].settlement.expenses,'2000.00');
  assert.equal((await db.agreements.get('agreement')).settlement.expenses,'2000.00');
});

test('farm daily milk replaces individual totals for the same day, including zero, without fake shifts',()=>{
  const {milkDayTotals}=load('reports',{'./db':{db:{}},'./dates':load('dates',{})});
  const rows=milkDayTotals([{id:'m1',animal:'cow',date:'2026-10-01',shift:'AM',liters:'10.10'},{id:'m2',animal:'cow',date:'2026-10-01',shift:'PM',liters:'5.20'},{id:'m3',animal:'cow',date:'2026-10-02',shift:'AM',liters:'12'}],
    [{id:'daily',farm:'farm-a',date:'2026-10-01',liters:'100.25',notes:''}]);
  assert.equal(rows.find(r=>r.date==='2026-10-01').total,100.25);assert.equal(rows.find(r=>r.date==='2026-10-01').am,null);
  assert.equal(rows.find(r=>r.date==='2026-10-01').hasIndividual,true);assert.equal(rows.find(r=>r.date==='2026-10-02').total,12);
  const zero=milkDayTotals([{animal:'cow',date:'2026-10-01',shift:'AM',liters:'10'}],[{id:'zero',date:'2026-10-01',liters:'0'}]);
  assert.equal(zero[0].total,0);assert.equal(zero[0].source,'daily');
});

test('daily milk report chooses one pending total while another device canonical id is being merged',()=>{
  const {milkDayTotals}=load('reports',{'./db':{db:{}},'./dates':load('dates',{})});
  const rows=milkDayTotals([],[{id:'server',date:'2026-10-01',liters:'100',updated_at:'2026-10-16T10:00:00Z'},{id:'pending',date:'2026-10-01',liters:'125.50',updated_at:'2026-10-15T10:00:00Z'}],new Set(['pending']));
  assert.equal(rows.length,1);assert.equal(rows[0].total,125.5);
});

test('daily milk individual fallback adds exact cents',()=>{
  const {milkDayTotals}=load('reports',{'./db':{db:{}},'./dates':load('dates',{})});
  const rows=milkDayTotals([{date:'2026-10-01',shift:'AM',liters:'0.10'},{date:'2026-10-01',shift:'AM',liters:'0.20'}],[]);
  assert.equal(rows[0].total,0.3);assert.equal(rows[0].am,0.3);
});

test('operator daily milk persists offline and server id merge keeps a newer pending correction',async()=>{
  const {sync,db,stores,api}=setup();stores.currentFarm.set({id:'farm-a',role:'operator'});
  await sync.enqueue('daily_milk',{id:'local',date:'2026-10-01',liters:'100.00',notes:''});
  api.pushBatch=async(_farm,data)=>{assert.equal(data.daily_milk[0].farm,'farm-a');await sync.enqueue('daily_milk',{id:'local',date:'2026-10-01',liters:'125.00',notes:'Correction'});return {daily_milk:[{id:'local',status:'updated',merged_into:'canonical'}]};};
  await sync.syncNow();assert.equal(await db.outbox.count(),1);assert.equal((await db.daily_milk.get('local')).liters,'125.00');
});

test('sale reference shows the confirmed farm sequence and hides internal UUIDs until confirmed',()=>{
  const {saleReference}=saleHelpers();
  assert.equal(saleReference({number:1}),'V-000001');assert.equal(saleReference({number:1234567}),'V-1234567');
  assert.equal(saleReference({id:'8b82896c-968f-4fbf-9529-889ebab3e20b'}),'Pendiente de numeración');
  assert.equal(saleReference({number:null}),'Pendiente de numeración');
});

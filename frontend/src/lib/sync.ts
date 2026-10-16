import { browser } from '$app/environment';
import { get } from 'svelte/store';

import { errorMessage } from './forms';
import { ApiError, pull, pushBatch, syncState, financialReceipt } from './api';
import { db, type OutboxRecord } from './db';
import { availableFarms, currentFarm, lastSyncResult, online, pendingCount, sessionChanging, sessionNotice, syncError, syncing, syncWarnings } from './stores';

const PULL_TABLES = [
	'owners',
	'brands',
	'paddocks',
	'lots',
	'animals',
	'agreements',
	'weighings',
	'milkings',
	'reproductive_events',
	'health_events',
	'sales',
	'sale_payments'
] as const;

// Ignore old cursors derived from the device clock; refresh once after upgrading.
const LAST_PULL_KEY = 'last_pull_server_at_v4';
const CHUNK_SIZE = 20;
const SAVE_SYNC_DELAY_MS = 1500;
const savedListeners = new Set<() => void>();

export async function refreshPendingCount(): Promise<void> {
	if (!browser) return;
	pendingCount.set(await db.outbox.count());
}

/** Resolve a lost response before correcting a pending immutable financial record. */
export async function reviewFinancialPending(collection: 'sales' | 'sale_payments', id: string): Promise<boolean> {
	const farm = get(currentFarm);
	if (!farm || farm.role !== 'admin') throw new Error('Esta acción requiere un administrador.');
	if (get(syncing) || get(sessionChanging)) throw new Error('Esperá a que termine la sincronización y volvé a revisar.');
	sessionChanging.set(true);
	try {
		const response = await financialReceipt(farm.id, collection, id);
		if (!response.record) return false;
		await db.transaction('rw', [db.outbox, db[collection]], async () => {
			const pending = (await db.outbox.toArray()).filter((r) => r.collection === collection && r.record_id === id);
			await db[collection].put(response.record as never);
			await db.outbox.bulkDelete(pending.map((r) => r.id!));
		});
		await refreshPendingCount();
		return true;
	} finally { sessionChanging.set(false); }
}

export interface PendingWrite {
    collection: OutboxRecord['collection'];
    payload: Record<string, unknown> & { id: string };
}

export async function enqueue(collection: PendingWrite['collection'], payload: PendingWrite['payload']): Promise<void> {
    await enqueueMany([{ collection, payload }]);
}

/** Save a whole local operation or nothing: lots and bulk entry cannot be half-saved. */
export async function enqueueMany(records: PendingWrite[]): Promise<void> {
    const farm = get(currentFarm);
    if (!farm) throw new Error('Seleccioná una finca antes de guardar.');
    if (get(sessionChanging)) throw new Error('Esperá a que termine el cambio de sesión.');
    const rank: Record<string, number> = { operator: 1, technician: 2, admin: 3 };
    const normalized = records.map(({ collection, payload }) => {
        const minimum = ['owners','brands','paddocks','agreements','sales','sale_payments'].includes(collection) ? 3
            : ['animals','lots','reproductive_events','health_events'].includes(collection) ? 2 : 1;
        if ((rank[farm.role] ?? 0) < minimum) throw new Error('Tu rol no permite guardar este tipo de registro.');
        const catalog = ['animals','lots','owners','brands','paddocks','agreements','sales','sale_payments'].includes(collection);
        return { collection, payload: catalog ? { ...payload, farm: farm.id } : payload };
    });
    const tables = [db.outbox, ...new Set(normalized.map((record) => db[record.collection]))];
    await db.transaction('rw', tables, async () => {
        if (get(sessionChanging) || get(currentFarm)?.id !== farm.id || (get(currentFarm)?.dataVersion ?? 0) !== (farm.dataVersion ?? 0)) throw new Error('La finca cambió. Revisá el formulario antes de guardar.');
        for (const { collection, payload } of normalized) {
            if (collection === 'sales' || collection === 'sale_payments') {
                const previous = (await db.outbox.toArray()).filter((r) => r.collection === collection && r.record_id === payload.id);
                if (previous.length && get(syncing)) throw new Error('Esperá a que termine el envío antes de corregir el registro financiero.');
                await db.outbox.bulkDelete(previous.map((r) => r.id!));
            }
            await db[collection].put(payload as never);
            await db.outbox.add({ collection, record_id: payload.id, payload, created_at: new Date().toISOString() });
        }
    });
    await refreshPendingCount();
    if (records.length) for (const listener of savedListeners) listener();
}

export async function syncNow(): Promise<{ pushed: number; warnings: string[] }> {
	const farm = get(currentFarm);
	// The last API failure is not a permanent offline lock: allow retries.
	if (!farm || get(syncing) || get(sessionChanging)) {
		return { pushed: 0, warnings: [] };
	}
	syncing.set(true);
	const warnings: string[] = [];
	let pushed = 0;

	try {
		// Check before uploading: clearing only the server would resurrect offline test records.
		const state = await syncState(farm.id);
		if (!Number.isSafeInteger(state.data_version) || state.data_version < 0) throw new Error('Marcador de finca inválido.');
		const versionKey = `farm_data_version:${farm.id}`;
		const previousVersion = await db.sync_meta.get(versionKey);
		const localVersion = Number(previousVersion?.value ?? 0);
		if (!Number.isSafeInteger(localVersion) || localVersion < 0 || state.data_version < localVersion) throw new Error('La versión de los datos cambió de forma inesperada. Contactá al administrador.');
		const reset = state.data_version > localVersion;
		await db.transaction('rw', [db.outbox, db.sync_meta, ...PULL_TABLES.map((t) => db[t])], async () => {
			if (reset) {
				for (const table of PULL_TABLES) await db[table].clear();
				await db.outbox.clear();
				await db.sync_meta.delete(LAST_PULL_KEY);
			}
			await db.sync_meta.put({ key: versionKey, value: String(state.data_version) });
			const cached = await db.sync_meta.get('offline_session_v1');
			if (cached) {
				const snapshot = JSON.parse(cached.value);
				for (const entry of snapshot.user.farms) if (entry.farm === farm.id) entry.farm_name = state.farm_name;
				await db.sync_meta.put({ key: cached.key, value: JSON.stringify(snapshot) });
			}
		});
		currentFarm.set({ ...farm, name: state.farm_name, dataVersion: state.data_version });
		availableFarms.set(get(availableFarms).map((entry) => entry.id === farm.id ? { ...entry, name: state.farm_name } : entry));
		if (reset) sessionNotice.set('La finca se reinició. Se eliminaron de este dispositivo los registros anteriores y sus pendientes. Ya podés ingresar los datos reales.');
		const pending = await db.outbox.orderBy('id').toArray();
		for (let start = 0; start < pending.length; start += CHUNK_SIZE) {
			const chunk = pending.slice(start, start + CHUNK_SIZE);
			const collections: Record<string, Record<string, unknown>[]> = {};
			const latest = new Map(chunk.map((entry) => [`${entry.collection}:${entry.record_id}`, entry]));
			for (const entry of latest.values()) {
				(collections[entry.collection] ??= []).push(entry.payload);
			}
			const results = await pushBatch(farm.id, collections, state.data_version);
			const confirmedIds = new Set<string>();
			const mergedIds: { collection: string; id: string }[] = [];
			for (const [collection, entries] of Object.entries(results)) {
				for (const entry of entries) {
					confirmedIds.add(entry.id);
					if (entry.merged_into) {
						mergedIds.push({ collection, id: entry.id });
					}
					if (entry.conflict) {
						warnings.push(
							`El registro ${entry.id} fue modificado en otro dispositivo; se aplicó tu versión.`
						);
					}
					if (entry.historical_warning) {
						warnings.push(
							`El animal del registro ${entry.id} figura como vendido/muerto. Se guardó como histórico.`
						);
					}
				}
			}
			await db.transaction('rw', [db.outbox, ...PULL_TABLES.map((t) => db[t])], async () => {
				// Only acknowledge the outbox entries actually sent in this request.
				const acknowledged = chunk.filter((entry) => confirmedIds.has(entry.record_id));
				await db.outbox.bulkDelete(acknowledged.map((entry) => entry.id!));
				for (const merged of mergedIds) {
					const stillPending = await db.outbox.filter((entry) =>
						entry.collection === merged.collection && entry.record_id === merged.id
					).count();
					if (!stillPending) await db.table(merged.collection).delete(merged.id);
				}
			});
			pushed += confirmedIds.size;
			await refreshPendingCount();
		}

		const lastPull = await db.sync_meta.get(LAST_PULL_KEY);
		const data = await pull(farm.id, lastPull?.value);
		await db.transaction('rw', [db.outbox, db.sync_meta, ...PULL_TABLES.map((t) => db[t])], async () => {
			const pending = await db.outbox.toArray();
			for (const table of PULL_TABLES) {
				const pendingIds = new Set(pending.filter((entry) => entry.collection === table)
					.map((entry) => entry.record_id));
				const rows = (data[table] ?? []) as { id: string }[];
				await db.table(table).bulkPut(rows.filter((row) => !pendingIds.has(row.id)));
			}
			if (data.sync_cursor) {
				await db.sync_meta.put({ key: LAST_PULL_KEY, value: data.sync_cursor });
			}
		});

		lastSyncResult.set(new Date().toISOString());
		syncError.set(null);
		syncWarnings.set(warnings);
	} catch (error) {
		if (error instanceof ApiError) {
			syncError.set(errorMessage(error, `Error del servidor (${error.statusCode})`));
		} else if (error instanceof TypeError) {
			syncError.set(null);
		} else {
			syncError.set('Error inesperado al sincronizar.');
		}
	} finally {
		syncing.set(false);
		await refreshPendingCount();
	}
	return { pushed, warnings };
}

export function startAutoSync(): () => void {
	if (!browser) return () => undefined;
	let timer: ReturnType<typeof setTimeout> | null = null;
	let requested = false;
	function flush() {
		timer = null;
		// A save during an upload waits for that upload, then sends the new edit.
		if (get(syncing) || get(sessionChanging)) return;
		requested = false;
		void syncNow();
	}
	function request(delay: number) {
		requested = true;
		if (timer !== null) clearTimeout(timer);
		timer = setTimeout(flush, delay);
	}
	const onSaved = () => request(SAVE_SYNC_DELAY_MS);
	const onOnline = () => request(0);
	const onVisible = () => {
		if (document.visibilityState === 'visible') request(0);
	};
	const onIdle = () => {
		if (requested && timer === null && !get(syncing) && !get(sessionChanging)) request(0);
	};
	savedListeners.add(onSaved);
	const unsubscribeSync = syncing.subscribe(onIdle);
	const unsubscribeSession = sessionChanging.subscribe(onIdle);
	window.addEventListener('online', onOnline);
	document.addEventListener('visibilitychange', onVisible);
	const interval = setInterval(onOnline, 60_000);
	if (get(pendingCount) > 0) request(0);
	return () => {
		savedListeners.delete(onSaved);
		unsubscribeSync();
		unsubscribeSession();
		window.removeEventListener('online', onOnline);
		document.removeEventListener('visibilitychange', onVisible);
		if (timer !== null) clearTimeout(timer);
		clearInterval(interval);
	};
}

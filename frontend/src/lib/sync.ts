import { browser } from '$app/environment';
import { get } from 'svelte/store';

import { ApiError, pull, pushBatch } from './api';
import { db, type OutboxRecord } from './db';
import { currentFarm, lastSyncResult, online, pendingCount, sessionChanging, syncError, syncing, syncWarnings } from './stores';

const PULL_TABLES = [
	'owners',
	'brands',
	'paddocks',
	'animals',
	'weighings',
	'milkings',
	'reproductive_events',
	'health_events'
] as const;

// Ignore old cursors derived from the device clock; refresh once after upgrading.
const LAST_PULL_KEY = 'last_pull_server_at_v1';
const CHUNK_SIZE = 20;

export async function refreshPendingCount(): Promise<void> {
	if (!browser) return;
	pendingCount.set(await db.outbox.count());
}

export async function enqueue(
	collection: OutboxRecord['collection'],
	payload: Record<string, unknown> & { id: string }
): Promise<void> {
	const farm = get(currentFarm);
	if (!farm) throw new Error('Seleccioná una finca antes de guardar.');
	const roles: Record<string, number> = { operator: 1, technician: 2, admin: 3 };
	const minimum = ['owners', 'brands', 'paddocks'].includes(collection) ? 3
		: ['animals', 'reproductive_events', 'health_events'].includes(collection) ? 2 : 1;
	if ((roles[farm.role] ?? 0) < minimum) throw new Error('Tu rol no permite guardar este tipo de registro.');
	const localPayload = ['animals', 'owners', 'brands', 'paddocks'].includes(collection)
		? { ...payload, farm: farm.id } : payload;
	await db.transaction('rw', db.outbox, db[collection], async () => {
		if (get(sessionChanging)) throw new Error('Esperá a que termine el cambio de sesión.');
		await db[collection].put(localPayload as never);
		await db.outbox.add({
			collection,
			record_id: payload.id,
			payload: localPayload,
			created_at: new Date().toISOString()
		});
	});
	await refreshPendingCount();
}

export async function syncNow(): Promise<{ pushed: number; warnings: string[] }> {
	const farm = get(currentFarm);
	if (!farm || !get(online) || get(syncing) || get(sessionChanging)) {
		return { pushed: 0, warnings: [] };
	}
	syncing.set(true);
	const warnings: string[] = [];
	let pushed = 0;

	try {
		const pending = await db.outbox.orderBy('id').toArray();
		for (let start = 0; start < pending.length; start += CHUNK_SIZE) {
			const chunk = pending.slice(start, start + CHUNK_SIZE);
			const collections: Record<string, Record<string, unknown>[]> = {};
			const latest = new Map(chunk.map((entry) => [`${entry.collection}:${entry.record_id}`, entry]));
			for (const entry of latest.values()) {
				(collections[entry.collection] ??= []).push(entry.payload);
			}
			const results = await pushBatch(farm.id, collections);
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
			const detail =
				error.body && typeof error.body === 'object' && 'detail' in error.body
					? String((error.body as { detail: unknown }).detail)
					: `Error del servidor (${error.statusCode})`;
			syncError.set(detail);
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
	const handler = () => {
		void syncNow();
	};
	window.addEventListener('online', handler);
	const interval = setInterval(handler, 60_000);
	return () => {
		window.removeEventListener('online', handler);
		clearInterval(interval);
	};
}

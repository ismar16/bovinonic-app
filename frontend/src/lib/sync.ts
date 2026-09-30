import { browser } from '$app/environment';
import { get } from 'svelte/store';

import { ApiError, pull, pushBatch } from './api';
import { db, type OutboxRecord } from './db';
import { currentFarm, lastSyncResult, online, pendingCount, syncError, syncing } from './stores';

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

const LAST_PULL_KEY = 'last_pull_at';

export async function refreshPendingCount(): Promise<void> {
	if (!browser) return;
	pendingCount.set(await db.outbox.count());
}

export async function enqueue(
	collection: OutboxRecord['collection'],
	payload: Record<string, unknown> & { id: string }
): Promise<void> {
	await db.transaction('rw', db.outbox, db[collection], async () => {
		await db[collection].put(payload as never);
		await db.outbox.add({
			collection,
			record_id: payload.id,
			payload,
			created_at: new Date().toISOString()
		});
	});
	await refreshPendingCount();
}

export async function syncNow(): Promise<{ pushed: number; warnings: string[] }> {
	const farm = get(currentFarm);
	if (!farm || !get(online) || get(syncing)) {
		return { pushed: 0, warnings: [] };
	}
	syncing.set(true);
	const warnings: string[] = [];
	let pushed = 0;

	try {
		const pending = await db.outbox.orderBy('id').toArray();
		if (pending.length > 0) {
			const collections: Record<string, Record<string, unknown>[]> = {};
			for (const entry of pending) {
				(collections[entry.collection] ??= []).push(entry.payload);
			}
			const results = await pushBatch(farm.id, collections);
			const confirmedIds = new Set<string>();
			for (const [collection, entries] of Object.entries(results)) {
				for (const entry of entries) {
					confirmedIds.add(entry.id);
					if (entry.historical_warning) {
						warnings.push(
							`El animal del registro ${entry.id} figura como vendido/muerto. Se guardó como histórico.`
						);
					}
				}
			}
			await db.outbox
				.filter((entry) => confirmedIds.has(entry.record_id))
				.delete();
			pushed = confirmedIds.size;
		}

		const lastPull = await db.sync_meta.get(LAST_PULL_KEY);
		const data = await pull(farm.id, lastPull?.value);
		await db.transaction('rw', PULL_TABLES.map((t) => db[t]), async () => {
			for (const table of PULL_TABLES) {
				const rows = (data[table] ?? []) as { id: string }[];
				await db.table(table).bulkPut(rows);
			}
		});
		await db.sync_meta.put({ key: LAST_PULL_KEY, value: new Date().toISOString() });

		lastSyncResult.set(new Date().toISOString());
		syncError.set(null);
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

import { goto } from '$app/navigation';
import { get } from 'svelte/store';

import { logout } from './api';
import { db } from './db';
import { syncNow } from './sync';
import { availableFarms, currentFarm, lastSyncResult, pendingCount, sessionChanging, sessionNotice, sessionUser, syncError, syncing, syncWarnings } from './stores';

export interface FarmOption {
	id: string;
	name: string;
	role: string;
}

async function changeSession(action: () => Promise<void>): Promise<boolean> {
	if (get(sessionChanging)) return false;
	if (get(syncing)) {
		sessionNotice.set('Esperá a que termine la sincronización antes de cambiar de finca o cerrar sesión.');
		return false;
	}
	sessionChanging.set(true);
	try {
		// Serialize the pending check and cleanup with writes from forms.
		const cleared = await db.transaction('rw', db.tables, async () => {
			const count = await db.outbox.count();
			pendingCount.set(count);
			if (count > 0) return false;
			for (const table of db.tables) await table.clear();
			return true;
		});
		if (!cleared) {
			sessionNotice.set('Tenés registros pendientes. Sincronizalos antes de cambiar de finca o cerrar sesión para conservarlos.');
			return false;
		}
		sessionNotice.set(null);
		syncError.set(null);
		syncWarnings.set([]);
		lastSyncResult.set(null);
		await action();
		return true;
	} finally {
		sessionChanging.set(false);
	}
}

export async function logoutAndWipe(): Promise<boolean> {
	return changeSession(async () => {
		try {
			await logout();
		} catch {
			// Allow local logout when the server is unreachable, after safeguarding pending data.
		}
		currentFarm.set(null);
		sessionUser.set(null);
		availableFarms.set([]);
		await goto('/login');
	});
}

export async function switchFarm(farm: FarmOption): Promise<boolean> {
	const current = get(currentFarm);
	if (current?.id === farm.id) return true;
	const changed = await changeSession(async () => {
		currentFarm.set({ id: farm.id, name: farm.name, role: farm.role });
		await goto('/');
	});
	if (changed) await syncNow();
	return changed;
}

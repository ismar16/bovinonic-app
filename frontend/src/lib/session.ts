import { goto } from '$app/navigation';
import { get } from 'svelte/store';

import { logout, me, type User } from './api';
import { db } from './db';
import { syncNow } from './sync';
import { availableFarms, currentFarm, lastSyncResult, pendingCount, sessionChanging, sessionNotice, sessionUser, syncError, syncing, syncWarnings } from './stores';

export interface FarmOption {
	id: string;
	name: string;
	role: string;
}

const SESSION_KEY = 'offline_session_v1';
interface CachedSession { user: User; farmId: string | null; verifiedAt: number; }

function applyUser(user: User, preferred?: string | null): void {
	const farms = user.farms.map((farm) => ({ id: farm.farm, name: farm.farm_name, role: farm.role }));
	sessionUser.set({ id: user.id, username: user.username });
	availableFarms.set(farms);
	currentFarm.set(farms.find((farm) => farm.id === preferred) ?? farms[0] ?? null);
}

async function cachedSession(): Promise<CachedSession | null> {
	const row = await db.sync_meta.get(SESSION_KEY);
	try {
		const cached = row ? JSON.parse(row.value) as CachedSession : null;
		return cached && typeof cached.verifiedAt === 'number' && Array.isArray(cached.user?.farms) ? cached : null;
	} catch { return null; }
}

export async function acceptUser(user: User): Promise<void> {
	const cached = await cachedSession();
	if (cached && cached.user.id !== user.id) {
		if (await db.outbox.count()) throw new Error(`Hay registros pendientes de ${cached.user.username}. Ingresá con esa cuenta y sincronizalos antes de cambiar de usuario.`);
		await db.transaction('rw', db.tables, async () => { for (const table of db.tables) await table.clear(); });
	}
	const remembered = cached?.user.id === user.id ? cached.farmId : null;
	if (remembered && !user.farms.some((farm) => farm.farm === remembered) && await db.outbox.count()) throw new Error('Hay registros pendientes de una finca a la que esta cuenta ya no tiene acceso. Contactá al administrador para recuperar el acceso.');
	applyUser(user, remembered);
	await db.sync_meta.put({ key: SESSION_KEY, value: JSON.stringify({ user, farmId: get(currentFarm)?.id ?? null, verifiedAt: Date.now() } satisfies CachedSession) });
}

/** Revalidate online; only network failures can reopen a recently verified offline session. */
export async function restoreSession(): Promise<void> {
	try { await acceptUser(await me()); }
	catch (cause) {
		if (!(cause instanceof TypeError)) throw cause;
		const cached = await cachedSession();
		if (!cached || Date.now() - cached.verifiedAt > 14 * 86_400_000) throw new Error('Conectate a internet e iniciá sesión para habilitar los datos de esta finca en el dispositivo.');
		applyUser(cached.user, cached.farmId);
	}
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
	const cached = await cachedSession();
	const changed = await changeSession(async () => {
		currentFarm.set({ id: farm.id, name: farm.name, role: farm.role });
		if (cached) await db.sync_meta.put({ key: SESSION_KEY, value: JSON.stringify({ ...cached, farmId: farm.id }) });
		await goto('/');
	});
	if (changed) await syncNow();
	return changed;
}

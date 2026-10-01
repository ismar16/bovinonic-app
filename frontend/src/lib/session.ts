import { goto } from '$app/navigation';
import { get } from 'svelte/store';

import { logout } from './api';
import { db } from './db';
import { currentFarm, pendingCount, sessionUser } from './stores';

export interface FarmOption {
	id: string;
	name: string;
	role: string;
}

export async function logoutAndWipe(): Promise<void> {
	try {
		await logout();
	} catch {
		// offline logout: wipe local data anyway
	}
	await db.delete();
	currentFarm.set(null);
	sessionUser.set(null);
	pendingCount.set(0);
	await goto('/login');
}

export async function switchFarm(farm: FarmOption): Promise<void> {
	const current = get(currentFarm);
	if (current?.id === farm.id) return;
	await db.delete();
	currentFarm.set({ id: farm.id, name: farm.name, role: farm.role });
	pendingCount.set(0);
	await goto('/');
}

import { browser } from '$app/environment';
import { writable } from 'svelte/store';

export const online = writable(browser ? navigator.onLine : true);
export const pendingCount = writable(0);
export const syncing = writable(false);
export const lastSyncResult = writable<string | null>(null);
export const syncError = writable<string | null>(null);
export const syncWarnings = writable<string[]>([]);
export const alertCount = writable(0);
export const currentFarm = writable<{ id: string; name: string; role: string } | null>(null);
export const sessionUser = writable<{ id: number; username: string } | null>(null);
export const availableFarms = writable<{ id: string; name: string; role: string }[]>([]);

if (browser) {
	window.addEventListener('online', () => online.set(true));
	window.addEventListener('offline', () => online.set(false));
}

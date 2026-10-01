import { browser } from '$app/environment';

import { online } from './stores';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

export class ApiError extends Error {
	constructor(
		public statusCode: number,
		message: string,
		public body: unknown = null
	) {
		super(message);
	}
}

async function safeFetch(input: string, init?: RequestInit): Promise<Response> {
	try {
		const response = await fetch(input, init);
		online.set(true);
		return response;
	} catch (error) {
		if (error instanceof TypeError) {
			online.set(false);
		}
		throw error;
	}
}

async function request(path: string, options: RequestInit = {}, retry = true): Promise<Response> {
	const response = await safeFetch(`${BASE_URL}${path}`, {
		credentials: 'include',
		headers: { 'Content-Type': 'application/json', ...options.headers },
		...options
	});

	if (response.status === 401 && retry && browser) {
		const refreshed = await safeFetch(`${BASE_URL}/api/auth/refresh`, {
			method: 'POST',
			credentials: 'include'
		});
		if (refreshed.ok) {
			return request(path, options, false);
		}
	}

	if (!response.ok) {
		let body: unknown = null;
		try {
			body = await response.json();
		} catch {
			// non-JSON body
		}
		throw new ApiError(response.status, `API ${response.status}`, body);
	}
	return response;
}

export interface User {
	id: number;
	username: string;
	farms: { id: string; farm: string; farm_name: string; role: string }[];
}

export async function login(username: string, password: string): Promise<void> {
	await request('/api/auth/login', {
		method: 'POST',
		body: JSON.stringify({ username, password })
	});
}

export async function logout(): Promise<void> {
	await request('/api/auth/logout', { method: 'POST' });
}

export async function me(): Promise<User> {
	const response = await request('/api/auth/me');
	return response.json();
}

export async function pull(farmId: string, since?: string): Promise<Record<string, unknown[]>> {
	const params = new URLSearchParams({ farm: farmId });
	if (since) params.set('since', since);
	const response = await request(`/api/sync/pull?${params.toString()}`);
	return response.json();
}

export interface BatchResultEntry {
	id: string;
	status: 'created' | 'updated';
	historical_warning?: boolean;
	merged_into?: string;
	conflict?: boolean;
}

export interface FarmUser {
	id: string;
	username: string;
	role: string;
	is_active: boolean;
}

export async function listFarmUsers(farmId: string): Promise<FarmUser[]> {
	const params = new URLSearchParams({ farm: farmId });
	const response = await request(`/api/manage/users?${params.toString()}`);
	return response.json();
}

export async function createFarmUser(
	farmId: string,
	username: string,
	password: string,
	role: string
): Promise<void> {
	const response = await request('/api/manage/users', {
		method: 'POST',
		body: JSON.stringify({ farm: farmId, username, password, role })
	});
	await response.json();
}

export async function pushBatch(
	farmId: string,
	collections: Record<string, Record<string, unknown>[]>
): Promise<Record<string, BatchResultEntry[]>> {
	const response = await request('/api/sync/batch', {
		method: 'POST',
		body: JSON.stringify({ farm: farmId, ...collections })
	});
	const data = await response.json();
	return data.results;
}

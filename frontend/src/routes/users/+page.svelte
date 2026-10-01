<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { ApiError, createFarmUser, listFarmUsers, type FarmUser } from '$lib/api';
	import { currentFarm, online } from '$lib/stores';

	const ROLES = [
		{ value: 'operator', label: 'Operador de corral' },
		{ value: 'technician', label: 'Técnico/Veterinario' },
		{ value: 'admin', label: 'Administrador' }
	] as const;

	let users = $state<FarmUser[]>([]);
	let username = $state('');
	let password = $state('');
	let role = $state<(typeof ROLES)[number]['value']>('operator');
	let error = $state('');
	let success = $state('');
	let loading = $state(false);

	async function load() {
		const farm = $currentFarm;
		if (!farm) return;
		users = await listFarmUsers(farm.id);
	}

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm || farm.role !== 'admin') {
			await goto('/settings');
			return;
		}
		try {
			await load();
		} catch {
			error = 'Sin conexión: la gestión de usuarios requiere internet.';
		}
	});

	async function save() {
		const farm = $currentFarm;
		if (!farm) return;
		error = '';
		success = '';
		loading = true;
		try {
			await createFarmUser(farm.id, username.trim(), password, role);
			success = `Usuario ${username.trim()} creado con rol ${role}.`;
			username = '';
			password = '';
			await load();
		} catch (e) {
			if (e instanceof ApiError && e.body && typeof e.body === 'object' && 'detail' in e.body) {
				error = String((e.body as { detail: unknown }).detail);
			} else {
				error = 'Error al crear el usuario (verificá la conexión).';
			}
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>Usuarios · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Usuarios de la finca</h1>

	{#if !$online}
		<p class="rounded-md border-2 border-yellow-600 bg-yellow-50 p-3 font-bold text-yellow-800">
			Modo campo: la gestión de usuarios requiere conexión.
		</p>
	{/if}

	<section class="rounded-md border-2 border-black p-4">
		<h2 class="mb-2 text-xl font-extrabold">Con acceso ({users.length})</h2>
		<ul class="flex flex-col gap-1">
			{#each users as u (u.id)}
				<li class="flex justify-between">
					<span class="font-bold">{u.username}</span>
					<span class="text-sm uppercase">{u.role}</span>
				</li>
			{:else}
				<li class="text-neutral-600">Sin datos (requiere conexión).</li>
			{/each}
		</ul>
	</section>

	<section class="rounded-md border-2 border-black p-4">
		<h2 class="mb-2 text-xl font-extrabold">Crear usuario</h2>
		<div class="flex flex-col gap-3">
			<input
				bind:value={username}
				placeholder="Usuario"
				autocomplete="off"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
			<input
				bind:value={password}
				type="password"
				placeholder="Contraseña (mín. 8)"
				autocomplete="new-password"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
			<select
				bind:value={role}
				class="h-14 rounded-md border-2 border-black bg-white px-4 text-xl"
			>
				{#each ROLES as r}
					<option value={r.value}>{r.label}</option>
				{/each}
			</select>
			{#if error}
				<p class="rounded-md border-2 border-red-700 bg-red-50 p-3 font-bold text-red-700">{error}</p>
			{/if}
			{#if success}
				<p class="rounded-md border-2 border-green-700 bg-green-50 p-3 font-bold text-green-700">{success}</p>
			{/if}
			<button
				type="button"
				onclick={save}
				disabled={loading || !$online || !username.trim() || !password}
				class="h-14 rounded-md bg-green-700 text-xl font-extrabold text-white disabled:opacity-50"
			>
				{loading ? 'Creando…' : 'Crear usuario'}
			</button>
		</div>
	</section>

	<button
		type="button"
		onclick={() => goto('/settings')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

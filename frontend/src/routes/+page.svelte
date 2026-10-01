<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { me } from '$lib/api';
	import { computeReproAlerts, computeWithdrawalCount } from '$lib/alerts';
	import { db, type Animal } from '$lib/db';
	import { switchFarm } from '$lib/session';
	import { availableFarms, currentFarm, online, sessionUser } from '$lib/stores';
	import { syncNow } from '$lib/sync';

	let query = $state('');
	let animals = $state<Animal[]>([]);
	let ready = $state(false);
	let calvingSoonCount = $state(0);
	let dryingOffCount = $state(0);
	let daysOpenCount = $state(0);
	let withdrawalsCount = $state(0);

	onMount(async () => {
		if (!getFarm()) {
			try {
				const user = await me();
				sessionUser.set({ id: user.id, username: user.username });
				availableFarms.set(
					user.farms.map((f) => ({ id: f.farm, name: f.farm_name, role: f.role }))
				);
				if (user.farms.length === 0) {
					ready = true;
					return;
				}
				const first = user.farms[0];
				currentFarm.set({ id: first.farm, name: first.farm_name, role: first.role });
			} catch {
				await goto('/login');
				return;
			}
		}
		await loadAnimals();
		if ($online) void syncNow().then(loadAnimals);
		ready = true;
	});

	function getFarm(): { id: string; name: string; role: string } | null {
		let value: { id: string; name: string; role: string } | null = null;
		currentFarm.subscribe((v) => (value = v))();
		return value;
	}

	async function loadAnimals() {
		const farm = getFarm();
		if (!farm) return;
		animals = await db.animals.where('farm').equals(farm.id).toArray();
		const alerts = await computeReproAlerts(farm.id);
		calvingSoonCount = alerts.calvingSoon.length;
		dryingOffCount = alerts.dryingOffSoon.length;
		daysOpenCount = alerts.daysOpen.length;
		withdrawalsCount = await computeWithdrawalCount(farm.id);
	}

	let filtered = $derived(
		query.trim() === ''
			? animals
			: animals.filter(
					(a) =>
						a.tag.toLowerCase().includes(query.trim().toLowerCase()) ||
						a.name.toLowerCase().includes(query.trim().toLowerCase())
				)
	);
</script>

<svelte:head><title>Hato · Gestión Ganadera</title></svelte:head>

{#if ready}
	<div class="pt-4">
		{#if $currentFarm}
			<h1 class="mb-1 text-2xl font-extrabold">{$currentFarm.name}</h1>
			<p class="mb-4 text-sm font-bold text-neutral-700">Rol: {$currentFarm.role}</p>

			{#if $availableFarms.length > 1}
				<select
					class="mb-4 h-14 w-full rounded-md border-2 border-black bg-white px-4 text-xl font-bold"
					value={$currentFarm.id}
					onchange={(e) => {
						const selected = $availableFarms.find((f) => f.id === e.currentTarget.value);
						if (selected) void switchFarm(selected);
					}}
				>
					{#each $availableFarms as farm (farm.id)}
						<option value={farm.id}>{farm.name}</option>
					{/each}
				</select>
			{/if}

			<div class="mb-4 grid grid-cols-4 gap-2 text-center">
				<a href="/" class="rounded-md border-2 border-black p-2">
					<p class="text-2xl font-extrabold">{animals.filter((a) => a.status === 'active').length}</p>
					<p class="text-xs font-bold">Activos</p>
				</a>
				<a href="/alerts" class="rounded-md border-2 border-black p-2">
					<p class="text-2xl font-extrabold">{calvingSoonCount}</p>
					<p class="text-xs font-bold">Por parir</p>
				</a>
				<a href="/alerts" class="rounded-md border-2 border-yellow-600 p-2">
					<p class="text-2xl font-extrabold">{dryingOffCount + daysOpenCount}</p>
					<p class="text-xs font-bold">Alertas</p>
				</a>
				<a href="/health/withdrawals" class="rounded-md border-2 border-red-700 p-2">
					<p class="text-2xl font-extrabold text-red-700">{withdrawalsCount}</p>
					<p class="text-xs font-bold text-red-700">Retiros</p>
				</a>
			</div>

			<nav class="mb-4 grid grid-cols-1 gap-2">
				<a
					href="/animals/new"
					class="flex h-14 items-center justify-center rounded-md border-2 border-black bg-black text-xl font-extrabold text-white"
					>Nuevo animal</a
				>
				<a
					href="/weighing"
					class="flex h-14 items-center justify-center rounded-md bg-green-700 text-xl font-extrabold text-white"
					>Pesaje rápido</a
				>
				<a
					href="/milking"
					class="flex h-14 items-center justify-center rounded-md bg-green-700 text-xl font-extrabold text-white"
					>Control lechero</a
				>
				<a
					href="/reproduction"
					class="flex h-14 items-center justify-center rounded-md bg-green-700 text-xl font-extrabold text-white"
					>Evento reproductivo</a
				>
				<a
					href="/health"
					class="flex h-14 items-center justify-center rounded-md bg-green-700 text-xl font-extrabold text-white"
					>Evento sanitario</a
				>
				<a
					href="/health/withdrawals"
					class="flex h-14 items-center justify-center rounded-md border-2 border-red-700 text-xl font-extrabold text-red-700"
					>Retiros activos</a
				>
				<a
					href="/reports"
					class="flex h-14 items-center justify-center rounded-md border-2 border-black text-xl font-extrabold"
					>Reportes</a
				>
				{#if $currentFarm.role === 'admin'}
					<a
						href="/catalogs"
						class="flex h-14 items-center justify-center rounded-md border-2 border-black text-xl font-extrabold"
						>Catálogos</a
					>
					<a
						href="/users"
						class="flex h-14 items-center justify-center rounded-md border-2 border-black text-xl font-extrabold"
						>Usuarios</a
					>
				{/if}
			</nav>

			<input
				bind:value={query}
				placeholder="Buscar arete o nombre…"
				class="mb-4 h-14 w-full rounded-md border-2 border-black px-4 text-xl"
			/>

			<ul class="flex flex-col gap-2">
				{#each filtered as animal (animal.id)}
					<li>
						<a
							href="/animals/{animal.id}"
							class="flex items-center justify-between rounded-md border-2 border-black p-4"
						>
							<div>
								<p class="text-xl font-extrabold">{animal.tag}</p>
								<p class="text-sm">{animal.name || 'Sin nombre'}</p>
							</div>
							<span
								class="rounded-md border-2 px-2 py-1 text-xs font-extrabold uppercase {animal.status ===
								'active'
									? 'border-green-700 text-green-700'
									: 'border-red-700 text-red-700'}"
							>
								{animal.status}
							</span>
						</a>
					</li>
				{:else}
					<li class="rounded-md border-2 border-dashed border-neutral-400 p-6 text-center">
						Sin animales. Sincronizá con conexión para descargar el hato.
					</li>
				{/each}
			</ul>
		{:else}
			<p class="pt-8 text-center">Sin finca asignada. Contactá al administrador.</p>
		{/if}
	</div>
{/if}

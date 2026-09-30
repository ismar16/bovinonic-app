<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { me } from '$lib/api';
	import { db, type Animal } from '$lib/db';
	import { currentFarm, online, sessionUser } from '$lib/stores';
	import { syncNow } from '$lib/sync';

	let query = $state('');
	let animals = $state<Animal[]>([]);
	let ready = $state(false);

	onMount(async () => {
		if (!getFarm()) {
			try {
				const user = await me();
				sessionUser.set({ id: user.id, username: user.username });
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

			<nav class="mb-4 grid grid-cols-1 gap-2">
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

<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { db, type Animal } from '$lib/db';
	import { currentFarm } from '$lib/stores';

	const STATUS_LABELS: Record<string, string> = {
		active: 'Activo',
		sold: 'Vendido',
		dead: 'Muerto',
		culled: 'Descarte'
	};

	let query = $state('');
	let animals = $state<Animal[]>([]);
	let ready = $state(false);

	onMount(async () => {
		if (!$currentFarm) {
			await goto('/');
			return;
		}
		animals = await db.animals.where('farm').equals($currentFarm.id).toArray();
		ready = true;
	});

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
							{STATUS_LABELS[animal.status] ?? animal.status}
						</span>
					</a>
				</li>
			{:else}
				<li class="rounded-md border-2 border-dashed border-neutral-400 p-6 text-center">
					Sin animales. Sincronizá con conexión para descargar el hato.
				</li>
			{/each}
		</ul>
	</div>
{/if}

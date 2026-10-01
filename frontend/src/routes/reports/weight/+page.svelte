<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { gmdAlerts, type GmdAlertRow } from '$lib/reports';
	import { currentFarm } from '$lib/stores';

	let rows = $state<GmdAlertRow[]>([]);

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm) {
			await goto('/');
			return;
		}
		rows = await gmdAlerts(farm.id);
	});
</script>

<svelte:head><title>Alertas de peso · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Alertas de peso (GMD)</h1>
	<p class="text-sm font-bold text-neutral-700">
		Animales activos con ganancia media diaria ≤ 0.10 kg entre sus dos últimos pesajes.
	</p>

	<ul class="flex flex-col gap-2">
		{#each rows as row (row.animal.id)}
			<li class="rounded-md border-2 {row.gmd < 0 ? 'border-red-700 bg-red-50' : 'border-yellow-600 bg-yellow-50'} p-4">
				<div class="flex items-center justify-between">
					<a href="/animals/{row.animal.id}" class="text-xl font-extrabold underline">{row.animal.tag}</a>
					<span class="font-extrabold {row.gmd < 0 ? 'text-red-700' : 'text-yellow-800'}">
						{row.gmd} kg/día
					</span>
				</div>
				<p class="text-sm">
					{row.animal.name || 'Sin nombre'} · {row.prevWeight} kg → {row.lastWeight} kg en {row.days} días (al {row.lastDate})
				</p>
			</li>
		{:else}
			<li class="rounded-md border-2 border-dashed border-green-700 p-6 text-center font-bold text-green-700">
				Sin animales estancados o perdiendo peso.
			</li>
		{/each}
	</ul>

	<button
		type="button"
		onclick={() => goto('/reports')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

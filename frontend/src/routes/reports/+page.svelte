<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { exportAnimalsCsv, exportMilkingsCsv, exportWeighingsCsv } from '$lib/reports';
	import { currentFarm } from '$lib/stores';

	let exporting = $state('');

	onMount(() => {
		if (!$currentFarm) void goto('/');
	});

	async function run(key: string, fn: (farmId: string) => Promise<void>) {
		const farm = $currentFarm;
		if (!farm) return;
		exporting = key;
		try {
			await fn(farm.id);
		} finally {
			exporting = '';
		}
	}
</script>

<svelte:head><title>Reportes · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Reportes</h1>

	<a
		href="/reports/milk"
		class="flex h-14 items-center justify-center rounded-md bg-green-700 text-xl font-extrabold text-white"
		>Producción lechera</a
	>
	<a
		href="/reports/weight"
		class="flex h-14 items-center justify-center rounded-md bg-green-700 text-xl font-extrabold text-white"
		>Alertas de peso (GMD)</a
	>

	<h2 class="mt-4 text-xl font-extrabold">Exportar CSV</h2>
	<button
		type="button"
		onclick={() => run('animals', exportAnimalsCsv)}
		disabled={exporting !== ''}
		class="h-14 w-full rounded-md border-2 border-black text-xl font-extrabold disabled:opacity-50"
	>
		{exporting === 'animals' ? 'Generando…' : 'Animales'}
	</button>
	<button
		type="button"
		onclick={() => run('weighings', exportWeighingsCsv)}
		disabled={exporting !== ''}
		class="h-14 w-full rounded-md border-2 border-black text-xl font-extrabold disabled:opacity-50"
	>
		{exporting === 'weighings' ? 'Generando…' : 'Pesajes'}
	</button>
	<button
		type="button"
		onclick={() => run('milkings', exportMilkingsCsv)}
		disabled={exporting !== ''}
		class="h-14 w-full rounded-md border-2 border-black text-xl font-extrabold disabled:opacity-50"
	>
		{exporting === 'milkings' ? 'Generando…' : 'Ordeños'}
	</button>

	<button
		type="button"
		onclick={() => goto('/')}
		class="mt-4 h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

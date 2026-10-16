<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	import { errorMessage } from '$lib/forms';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { exportAnimalsCsv, exportMilkingsCsv, exportWeighingsCsv } from '$lib/reports';
	import { currentFarm } from '$lib/stores';

	let error = $state('');
	let exporting = $state('');

	onMount(() => {
		if (!$currentFarm) void goto('/settings');
	});

	async function run(key: string, fn: (farmId: string) => Promise<void>) {
		const farm = $currentFarm;
		if (!farm || exporting) return;
		exporting = key;
		try {
			await fn(farm.id);
		} catch (cause) { error = errorMessage(cause); } finally {
			exporting = '';
		}
	}
</script>

<svelte:head><title>Reportes · Gestión Ganadera</title></svelte:head>

<div class="workspace-page space-y-6">
	<PageHeader title="Reportes" description="Consultá resultados y exportá los registros de tu finca." backHref="/settings" /><Notice tone="error" message={error} />

	<a
		href="/reports/milk"
		class="panel flex min-h-24 items-center p-6 font-serif text-xl transition-colors hover:bg-[#edf2e7]"
		>Producción lechera</a
	>
	<a
		href="/reports/weight"
		class="panel flex min-h-24 items-center p-6 font-serif text-xl transition-colors hover:bg-[#edf2e7]"
		>Alertas de peso (GMD)</a
	>

	<h2 class="mt-4 text-lg font-semibold">Exportar CSV</h2>
	<button
		type="button"
		onclick={() => run('animals', exportAnimalsCsv)}
		disabled={exporting !== ''}
		class="quiet-button w-full sm:w-auto"
	>
		{exporting === 'animals' ? 'Generando…' : 'Animales'}
	</button>
	<button
		type="button"
		onclick={() => run('weighings', exportWeighingsCsv)}
		disabled={exporting !== ''}
		class="quiet-button w-full sm:w-auto"
	>
		{exporting === 'weighings' ? 'Generando…' : 'Pesajes'}
	</button>
	<button
		type="button"
		onclick={() => run('milkings', exportMilkingsCsv)}
		disabled={exporting !== ''}
		class="quiet-button w-full sm:w-auto"
	>
		{exporting === 'milkings' ? 'Generando…' : 'Ordeños'}
	</button>

	<button
		type="button"
		onclick={() => goto('/settings')}
		class="quiet-button"
	>
		Volver
	</button>
</div>

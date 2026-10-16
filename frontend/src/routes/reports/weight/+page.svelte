<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	import { errorMessage } from '$lib/forms';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { gmdAlerts, type GmdAlertRow } from '$lib/reports';
	import { currentFarm } from '$lib/stores';

	let error = $state(''); let loading = $state(true);
	let rows = $state<GmdAlertRow[]>([]);

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm) {
			await goto('/');
			return;
		}
		try { rows = await gmdAlerts(farm.id); } catch (cause) { error = errorMessage(cause); } finally { loading = false; }
	});
</script>

<svelte:head><title>Alertas de peso · Gestión Ganadera</title></svelte:head>

<div class="workspace-page space-y-6">
	<PageHeader title="Seguimiento de peso" description="Comparación de los últimos pesajes en fechas distintas." backHref="/reports" /><Notice tone="error" message={error} />
	<p class="text-sm font-bold text-neutral-700">
		Animales activos con ganancia media diaria ≤ 0.10 kg entre sus dos últimos pesajes.
	</p>

	<ul class="flex flex-col gap-2">
		{#each rows as row (row.animal.id)}
			<li class="rounded-md border {row.gmd < 0 ? 'border-red-700 bg-red-50' : 'border-yellow-600 bg-yellow-50'} p-4">
				<div class="flex items-center justify-between">
					<a href="/animals/{row.animal.id}" class="text-lg font-semibold underline">{row.animal.tag}</a>
					<span class="font-semibold {row.gmd < 0 ? 'text-red-700' : 'text-yellow-800'}">
						{row.gmd} kg/día
					</span>
				</div>
				<p class="text-sm">
					{row.animal.name || 'Sin nombre'} · {row.prevWeight} kg → {row.lastWeight} kg en {row.days} días (al {row.lastDate})
				</p>
			</li>
		{:else}
			<li class="empty-state">
				{loading ? 'Cargando pesajes…' : 'No hay alertas calculables. Se necesitan al menos dos pesajes en fechas distintas por animal.'}
			</li>
		{/each}
	</ul>

	<button
		type="button"
		onclick={() => goto('/reports')}
		class="quiet-button"
	>
		Volver
	</button>
</div>

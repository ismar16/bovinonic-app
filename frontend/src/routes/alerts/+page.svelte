<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	import { errorMessage } from '$lib/forms';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { computeReproAlerts, type ReproAlerts } from '$lib/alerts';
	import { currentFarm } from '$lib/stores';

	let error = $state('');
	let alerts = $state<ReproAlerts | null>(null);

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm) {
			await goto('/');
			return;
		}
		try { alerts = await computeReproAlerts(farm.id); } catch (cause) { error = errorMessage(cause); }
	});
</script>

<svelte:head><title>Alertas reproductivas · Gestión Ganadera</title></svelte:head>

<div class="workspace-page space-y-6">
	<PageHeader title="Alertas reproductivas" description="Fechas orientativas según los eventos registrados." backHref="/" /><Notice tone="error" message={error} />

	{#if alerts}
		<section>
			<h2 class="mb-2 text-lg font-semibold">
				Próximas a parir (≤ 30 días)
				<span class="ml-2 rounded-md bg-[#31583c] px-2 py-0.5 text-sm text-white">{alerts.calvingSoon.length}</span>
			</h2>
			<ul class="flex flex-col gap-2">
				{#each alerts.calvingSoon as row (row.animal.id)}
					<li class="panel p-5">
						<div class="flex items-center justify-between">
							<a href="/animals/{row.animal.id}" class="text-lg font-semibold underline">{row.animal.tag}</a>
							<span class="font-semibold">{row.daysLeft} días</span>
						</div>
						<p class="text-sm">{row.animal.name || 'Sin nombre'} · parto estimado: {row.date}</p>
					</li>
				{:else}
					<li class="empty-state">
						Ninguna vaca por parir en los próximos 30 días.
					</li>
				{/each}
			</ul>
		</section>

		<section>
			<h2 class="mb-2 text-lg font-semibold">
				Secado sugerido esta semana
				<span class="ml-2 rounded-md bg-[#31583c] px-2 py-0.5 text-sm text-white">{alerts.dryingOffSoon.length}</span>
			</h2>
			<ul class="flex flex-col gap-2">
				{#each alerts.dryingOffSoon as row (row.animal.id)}
					<li class="notice warning">
						<div class="flex items-center justify-between">
							<a href="/animals/{row.animal.id}" class="text-lg font-semibold underline">{row.animal.tag}</a>
							<span class="font-semibold">{row.daysLeft} días</span>
						</div>
						<p class="text-sm">{row.animal.name || 'Sin nombre'} · secado sugerido: {row.date}</p>
					</li>
				{:else}
					<li class="empty-state">
						Ningún secado sugerido esta semana.
					</li>
				{/each}
			</ul>
		</section>

		<section>
			<h2 class="mb-2 text-lg font-semibold">
				Días abiertos (&gt; 90 sin preñez confirmada)
				<span class="ml-2 rounded-md bg-red-700 px-2 py-0.5 text-sm text-white">{alerts.daysOpen.length}</span>
			</h2>
			<ul class="flex flex-col gap-2">
				{#each alerts.daysOpen as row (row.animal.id)}
					<li class="notice error">
						<div class="flex items-center justify-between">
							<a href="/animals/{row.animal.id}" class="text-lg font-semibold underline">{row.animal.tag}</a>
							<span class="font-semibold text-red-700">{row.daysLeft} días abiertos</span>
						</div>
						<p class="text-sm">{row.animal.name || 'Sin nombre'} · {row.detail}</p>
					</li>
				{:else}
					<li class="empty-state">
						Ninguna vaca con días abiertos excesivos.
					</li>
				{/each}
			</ul>
		</section>
	{:else if !error}<p class="empty-state">Cargando alertas…</p>{/if}

	<button
		type="button"
		onclick={() => goto('/')}
		class="quiet-button"
	>
		Volver
	</button>
</div>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { computeReproAlerts, type ReproAlerts } from '$lib/alerts';
	import { currentFarm } from '$lib/stores';

	let alerts = $state<ReproAlerts | null>(null);

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm) {
			await goto('/');
			return;
		}
		alerts = await computeReproAlerts(farm.id);
	});
</script>

<svelte:head><title>Alertas reproductivas · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-6 pt-4">
	<h1 class="text-2xl font-extrabold">Alertas reproductivas</h1>

	{#if alerts}
		<section>
			<h2 class="mb-2 text-xl font-extrabold">
				Próximas a parir (≤ 30 días)
				<span class="ml-2 rounded-md bg-black px-2 py-0.5 text-sm text-white">{alerts.calvingSoon.length}</span>
			</h2>
			<ul class="flex flex-col gap-2">
				{#each alerts.calvingSoon as row (row.animal.id)}
					<li class="rounded-md border-2 border-black p-4">
						<div class="flex items-center justify-between">
							<a href="/animals/{row.animal.id}" class="text-xl font-extrabold underline">{row.animal.tag}</a>
							<span class="font-extrabold">{row.daysLeft} días</span>
						</div>
						<p class="text-sm">{row.animal.name || 'Sin nombre'} · parto estimado: {row.date}</p>
					</li>
				{:else}
					<li class="rounded-md border-2 border-dashed border-neutral-400 p-4 text-center">
						Ninguna vaca por parir en los próximos 30 días.
					</li>
				{/each}
			</ul>
		</section>

		<section>
			<h2 class="mb-2 text-xl font-extrabold">
				Secado sugerido esta semana
				<span class="ml-2 rounded-md bg-black px-2 py-0.5 text-sm text-white">{alerts.dryingOffSoon.length}</span>
			</h2>
			<ul class="flex flex-col gap-2">
				{#each alerts.dryingOffSoon as row (row.animal.id)}
					<li class="rounded-md border-2 border-yellow-600 bg-yellow-50 p-4">
						<div class="flex items-center justify-between">
							<a href="/animals/{row.animal.id}" class="text-xl font-extrabold underline">{row.animal.tag}</a>
							<span class="font-extrabold">{row.daysLeft} días</span>
						</div>
						<p class="text-sm">{row.animal.name || 'Sin nombre'} · secado sugerido: {row.date}</p>
					</li>
				{:else}
					<li class="rounded-md border-2 border-dashed border-neutral-400 p-4 text-center">
						Ningún secado sugerido esta semana.
					</li>
				{/each}
			</ul>
		</section>

		<section>
			<h2 class="mb-2 text-xl font-extrabold">
				Días abiertos (&gt; 90 sin preñez confirmada)
				<span class="ml-2 rounded-md bg-red-700 px-2 py-0.5 text-sm text-white">{alerts.daysOpen.length}</span>
			</h2>
			<ul class="flex flex-col gap-2">
				{#each alerts.daysOpen as row (row.animal.id)}
					<li class="rounded-md border-2 border-red-700 bg-red-50 p-4">
						<div class="flex items-center justify-between">
							<a href="/animals/{row.animal.id}" class="text-xl font-extrabold underline">{row.animal.tag}</a>
							<span class="font-extrabold text-red-700">{row.daysLeft} días abiertos</span>
						</div>
						<p class="text-sm">{row.animal.name || 'Sin nombre'} · {row.detail}</p>
					</li>
				{:else}
					<li class="rounded-md border-2 border-dashed border-neutral-400 p-4 text-center">
						Ninguna vaca con días abiertos excesivos.
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<button
		type="button"
		onclick={() => goto('/')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

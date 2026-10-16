<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	import { errorMessage } from '$lib/forms';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { daysAgo, milkByCow, milkByDay, type MilkCowRow, type MilkDayRow } from '$lib/reports';
	import { currentFarm } from '$lib/stores';

	let error = $state('');
	let range = $state(7);
	let byDay = $state<MilkDayRow[]>([]);
	let byCow = $state<MilkCowRow[]>([]);

	async function load() {
		const farm = $currentFarm;
		if (!farm) return;
		const from = daysAgo(range - 1);
		const to = daysAgo(0);
		try { byDay = await milkByDay(farm.id, from, to);
		byCow = await milkByCow(farm.id, from, to); } catch (cause) { error = errorMessage(cause); }
	}

	onMount(async () => {
		if (!$currentFarm) {
			await goto('/');
			return;
		}
		await load();
	});

	let totalPeriod = $derived(
		Math.round(byDay.reduce((sum, row) => sum + row.total, 0) * 100) / 100
	);
</script>

<svelte:head><title>Producción lechera · Gestión Ganadera</title></svelte:head>

<div class="workspace-page space-y-6">
	<PageHeader title="Producción lechera" description="Totales por fecha y animal, calculados con los registros de este dispositivo." backHref="/reports" /><Notice tone="error" message={error} />

	<div class="grid grid-cols-3 gap-2">
		{#each [7, 14, 30] as days}
			<button
				type="button"
				onclick={() => {
					range = days;
					void load();
				}}
				class="quiet-button choice-button" aria-pressed={range === days}
			>
				{days} días
			</button>
		{/each}
	</div>

	<p class="panel p-6 text-center font-serif text-3xl">
		Total del período: {totalPeriod} L
	</p>

	<section>
		<h2 class="mb-2 text-lg font-semibold">Por día</h2>
		<ul class="flex flex-col gap-1">
			{#each byDay as row (row.date)}
				<li class="panel flex flex-wrap items-center justify-between gap-3 p-4">
					<span class="font-bold">{row.date}</span>
					<span>AM {row.am} · PM {row.pm}</span>
					<span class="font-semibold">{row.total} L</span>
				</li>
			{:else}
				<li class="empty-state">
					Sin ordeños en el período.
				</li>
			{/each}
		</ul>
	</section>

	<section>
		<h2 class="mb-2 text-lg font-semibold">Por vaca</h2>
		<ul class="flex flex-col gap-1">
			{#each byCow as row (row.animal.id)}
				<li class="panel flex flex-wrap items-center justify-between gap-3 p-4">
					<a href="/animals/{row.animal.id}" class="font-semibold underline">{row.animal.tag}</a>
					<span class="text-sm">{row.days} día{row.days === 1 ? '' : 's'} · prom {row.avgPerDay} L/día</span>
					<span class="font-semibold">{row.total} L</span>
				</li>
			{:else}
				<li class="empty-state">
					Sin datos por vaca.
				</li>
			{/each}
		</ul>
	</section>

	<button
		type="button"
		onclick={() => goto('/reports')}
		class="quiet-button"
	>
		Volver
	</button>
</div>

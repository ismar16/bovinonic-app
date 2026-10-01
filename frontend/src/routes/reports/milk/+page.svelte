<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { daysAgo, milkByCow, milkByDay, type MilkCowRow, type MilkDayRow } from '$lib/reports';
	import { currentFarm } from '$lib/stores';

	let range = $state(7);
	let byDay = $state<MilkDayRow[]>([]);
	let byCow = $state<MilkCowRow[]>([]);

	async function load() {
		const farm = $currentFarm;
		if (!farm) return;
		const from = daysAgo(range - 1);
		const to = daysAgo(0);
		byDay = await milkByDay(farm.id, from, to);
		byCow = await milkByCow(farm.id, from, to);
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

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Producción lechera</h1>

	<div class="grid grid-cols-3 gap-2">
		{#each [7, 14, 30] as days}
			<button
				type="button"
				onclick={() => {
					range = days;
					void load();
				}}
				class="h-14 rounded-md border-2 border-black font-extrabold {range === days
					? 'bg-black text-white'
					: 'bg-white'}"
			>
				{days} días
			</button>
		{/each}
	</div>

	<p class="rounded-md border-2 border-black p-3 text-center text-xl font-extrabold">
		Total del período: {totalPeriod} L
	</p>

	<section>
		<h2 class="mb-2 text-xl font-extrabold">Por día</h2>
		<ul class="flex flex-col gap-1">
			{#each byDay as row (row.date)}
				<li class="flex justify-between rounded-md border-2 border-black p-3">
					<span class="font-bold">{row.date}</span>
					<span>AM {row.am} · PM {row.pm}</span>
					<span class="font-extrabold">{row.total} L</span>
				</li>
			{:else}
				<li class="rounded-md border-2 border-dashed border-neutral-400 p-4 text-center">
					Sin ordeños en el período.
				</li>
			{/each}
		</ul>
	</section>

	<section>
		<h2 class="mb-2 text-xl font-extrabold">Por vaca</h2>
		<ul class="flex flex-col gap-1">
			{#each byCow as row (row.animal.id)}
				<li class="flex items-center justify-between rounded-md border-2 border-black p-3">
					<a href="/animals/{row.animal.id}" class="font-extrabold underline">{row.animal.tag}</a>
					<span class="text-sm">{row.days} día{row.days === 1 ? '' : 's'} · prom {row.avgPerDay} L/día</span>
					<span class="font-extrabold">{row.total} L</span>
				</li>
			{:else}
				<li class="rounded-md border-2 border-dashed border-neutral-400 p-4 text-center">
					Sin datos por vaca.
				</li>
			{/each}
		</ul>
	</section>

	<button
		type="button"
		onclick={() => goto('/reports')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { db } from '$lib/db';
	import { currentFarm } from '$lib/stores';

	interface WithdrawalRow {
		animalId: string;
		tag: string;
		name: string;
		product: string;
		type: string;
		endDate: string;
		daysLeft: number;
	}

	const TYPE_LABELS: Record<string, string> = {
		vaccine: 'Vacuna',
		deworming: 'Desparasitación',
		antibiotic: 'Antibiótico',
		vitamin: 'Vitamina'
	};

	let rows = $state<WithdrawalRow[]>([]);

	function addDays(isoDate: string, days: number): string {
		const d = new Date(`${isoDate}T00:00:00`);
		d.setDate(d.getDate() + days);
		return d.toISOString().slice(0, 10);
	}

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm) {
			await goto('/');
			return;
		}
		const today = new Date().toISOString().slice(0, 10);
		const animals = await db.animals.where('farm').equals(farm.id).toArray();
		const animalMap = new Map(animals.map((a) => [a.id, a]));
		const events = await db.health_events.toArray();

		const result: WithdrawalRow[] = [];
		for (const e of events) {
			const animal = animalMap.get(e.animal);
			if (!animal) continue;
			const end = e.withdrawal_end_date ?? addDays(e.date, e.withdrawal_days ?? 0);
			if (end < today) continue;
			const daysLeft = Math.ceil(
				(new Date(`${end}T00:00:00`).getTime() - new Date(`${today}T00:00:00`).getTime()) /
					86_400_000
			);
			result.push({
				animalId: animal.id,
				tag: animal.tag,
				name: animal.name,
				product: e.product,
				type: TYPE_LABELS[e.type] ?? e.type,
				endDate: end,
				daysLeft
			});
		}
		rows = result.sort((a, b) => a.daysLeft - b.daysLeft);
	});
</script>

<svelte:head><title>Retiros activos · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Retiros activos</h1>
	<p class="text-sm font-bold text-neutral-700">
		Animales con leche/carne NO apta para consumo o venta.
	</p>

	<ul class="flex flex-col gap-2">
		{#each rows as row (row.animalId + row.endDate)}
			<li class="rounded-md border-2 border-red-700 bg-red-50 p-4">
				<div class="flex items-center justify-between">
					<a href="/animals/{row.animalId}" class="text-xl font-extrabold underline">
						{row.tag}
					</a>
					<span class="rounded-md bg-red-700 px-2 py-1 text-xs font-extrabold text-white">
						{row.daysLeft} día{row.daysLeft === 1 ? '' : 's'} restante{row.daysLeft === 1 ? '' : 's'}
					</span>
				</div>
				<p class="mt-1 text-sm">{row.name || 'Sin nombre'}</p>
				<p class="text-sm font-bold">{row.type}: {row.product}</p>
				<p class="text-sm">Retiro hasta: <span class="font-extrabold">{row.endDate}</span></p>
			</li>
		{:else}
			<li class="rounded-md border-2 border-dashed border-green-700 p-6 text-center font-bold text-green-700">
				Sin retiros activos. Toda la producción está apta.
			</li>
		{/each}
	</ul>

	<button
		type="button"
		onclick={() => goto('/health')}
		class="h-14 w-full rounded-md bg-green-700 text-xl font-extrabold text-white"
	>
		Registrar evento sanitario
	</button>

	<button
		type="button"
		onclick={() => goto('/')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

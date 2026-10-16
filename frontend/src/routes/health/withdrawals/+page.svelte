<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	import { errorMessage } from '$lib/forms';
	import { farmDate, addDateDays } from '$lib/dates';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { db } from '$lib/db';
	import { currentFarm } from '$lib/stores';

	interface WithdrawalRow {
		eventId: string;
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

	let error = $state(''); let loading = $state(true);
	let rows = $state<WithdrawalRow[]>([]);

	function addDays(isoDate: string, days: number): string {
		return addDateDays(isoDate, days);
	}

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm) {
			await goto('/');
			return;
		}
		try { const today = farmDate();
		const animals = await db.animals.where('farm').equals(farm.id).toArray();
		const animalMap = new Map(animals.map((a) => [a.id, a]));
		const events = await db.health_events.toArray();

		const result: WithdrawalRow[] = [];
		for (const e of events) {
			const animal = animalMap.get(e.animal);
			if (!animal || animal.status !== 'active' || e.date > today) continue;
			if (!e.withdrawal_days) continue;
			const end = e.withdrawal_end_date ?? addDays(e.date, e.withdrawal_days ?? 0);
			if (end < today) continue;
			const daysLeft = Math.ceil(
				(new Date(`${end}T00:00:00`).getTime() - new Date(`${today}T00:00:00`).getTime()) /
					86_400_000
			);
			result.push({
				eventId: e.id, animalId: animal.id,
				tag: animal.tag,
				name: animal.name,
				product: e.product,
				type: TYPE_LABELS[e.type] ?? e.type,
				endDate: end,
				daysLeft
			});
		}
		rows = result.sort((a, b) => a.daysLeft - b.daysLeft); } catch (cause) { error = errorMessage(cause); } finally { loading = false; }
	});
</script>

<svelte:head><title>Retiros activos · Gestión Ganadera</title></svelte:head>

<div class="workspace-page space-y-6">
	<PageHeader title="Retiros activos" description="Revisá los tratamientos y plazos registrados antes de disponer de la producción." backHref="/operations" /><Notice tone="error" message={error} />
	<p class="text-sm font-bold text-neutral-700">
		Animales con leche/carne NO apta para consumo o venta.
	</p>

	<ul class="flex flex-col gap-2">
		{#each rows as row (row.eventId)}
			<li class="notice error">
				<div class="flex items-center justify-between">
					<a href="/animals/{row.animalId}" class="text-lg font-semibold underline">
						{row.tag}
					</a>
					<span class="rounded-md bg-red-700 px-2 py-1 text-xs font-semibold text-white">
						{row.daysLeft} día{row.daysLeft === 1 ? '' : 's'} restante{row.daysLeft === 1 ? '' : 's'}
					</span>
				</div>
				<p class="mt-1 text-sm">{row.name || 'Sin nombre'}</p>
				<p class="text-sm font-bold">{row.type}: {row.product}</p>
				<p class="text-sm">Retiro hasta: <span class="font-semibold">{row.endDate}</span></p>
			</li>
		{:else}
			<li class="empty-state">
				{loading ? 'Cargando retiros…' : 'No hay retiros vigentes en los registros de animales activos de este dispositivo.'}
			</li>
		{/each}
	</ul>

	<button
		type="button"
		onclick={() => goto('/health')}
		class="action-button"
	>
		Registrar evento sanitario
	</button>

	<button
		type="button"
		onclick={() => goto('/')}
		class="quiet-button"
	>
		Volver
	</button>
</div>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	import { db, type Animal, type HealthEvent, type Milking, type ReproductiveEvent, type Weighing } from '$lib/db';

	let animal = $state<Animal | null>(null);
	let mother = $state<Animal | null>(null);
	let father = $state<Animal | null>(null);
	let offspring = $state<Animal[]>([]);
	let weighings = $state<Weighing[]>([]);
	let milkings = $state<Milking[]>([]);
	let reproEvents = $state<ReproductiveEvent[]>([]);
	let healthEvents = $state<HealthEvent[]>([]);
	let activeWithdrawal = $state<string | null>(null);
	let notFound = $state(false);

	function addDays(isoDate: string, days: number): string {
		const d = new Date(`${isoDate}T00:00:00`);
		d.setDate(d.getDate() + days);
		return d.toISOString().slice(0, 10);
	}

	onMount(async () => {
		const id = page.params.id;
		if (!id) {
			notFound = true;
			return;
		}
		const found = await db.animals.get(id);
		if (!found) {
			notFound = true;
			return;
		}
		animal = found;
		if (found.mother) mother = (await db.animals.get(found.mother)) ?? null;
		if (found.father) father = (await db.animals.get(found.father)) ?? null;
		const asMother = await db.animals.where('farm').equals(found.farm).filter((a) => a.mother === found.id).toArray();
		const asFather = await db.animals.where('farm').equals(found.farm).filter((a) => a.father === found.id).toArray();
		offspring = [...asMother, ...asFather];
		weighings = (await db.weighings.where('animal').equals(found.id).sortBy('date')).reverse().slice(0, 10);
		const rawMilkings = (await db.milkings.where('animal').equals(found.id).sortBy('date')).reverse();
		const seenShifts = new Set<string>();
		milkings = rawMilkings
			.filter((m) => {
				const key = `${m.date}|${m.shift}`;
				if (seenShifts.has(key)) return false;
				seenShifts.add(key);
				return true;
			})
			.slice(0, 10);
		reproEvents = (await db.reproductive_events.where('animal').equals(found.id).sortBy('date')).reverse().slice(0, 10);
		healthEvents = (await db.health_events.where('animal').equals(found.id).sortBy('date')).reverse().slice(0, 10);
		const today = new Date().toISOString().slice(0, 10);
		const active = healthEvents
			.map((e) => e.withdrawal_end_date ?? addDays(e.date, e.withdrawal_days ?? 0))
			.filter((end) => end >= today)
			.sort()
			.reverse();
		activeWithdrawal = active[0] ?? null;
	});

	const TYPE_LABELS: Record<string, string> = {
		heat: 'Celo', service: 'Servicio', palpation: 'Palpación',
		calving: 'Parto', drying_off: 'Secado', abortion: 'Aborto',
		vaccine: 'Vacuna', deworming: 'Desparasitación',
		antibiotic: 'Antibiótico', vitamin: 'Vitamina'
	};
</script>

<svelte:head><title>Ficha {animal?.tag ?? ''} · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	{#if notFound}
		<p class="rounded-md border-2 border-red-700 bg-red-50 p-4 font-bold text-red-700">
			Animal no encontrado en este dispositivo.
		</p>
	{:else if animal}
		<div class="rounded-md border-2 border-black p-4">
			<p class="text-3xl font-extrabold">{animal.tag}</p>
			<p class="text-lg">{animal.name || 'Sin nombre'}</p>
			<p class="mt-1 text-sm font-bold uppercase">
				{animal.sex} · {animal.category} ·
				<span class={animal.status === 'active' ? 'text-green-700' : 'text-red-700'}>
					{animal.status}
				</span>
			</p>
			{#if animal.birth_date}
				<p class="text-sm">Nacimiento: {animal.birth_date}</p>
			{/if}
			{#if animal.status !== 'active' && animal.status_changed_at}
				<p class="mt-1 text-sm font-bold text-red-700">
					{animal.status} el {animal.status_changed_at}{animal.status_reason
						? ` — ${animal.status_reason}`
						: ''}
				</p>
			{/if}
		</div>

		<div class="grid grid-cols-2 gap-2">
			<a
				href="/animals/{animal.id}/edit"
				class="flex h-14 items-center justify-center rounded-md border-2 border-black font-extrabold"
				>Editar datos</a
			>
			<a
				href="/animals/{animal.id}/status"
				class="flex h-14 items-center justify-center rounded-md bg-red-700 font-extrabold text-white"
				>Cambio de estado</a
			>
		</div>

		{#if activeWithdrawal}
			<p class="rounded-md border-2 border-red-700 bg-red-50 p-3 font-bold text-red-700">
				Retiro vigente hasta {activeWithdrawal} — leche/carne no apta.
			</p>
		{/if}

		<section class="rounded-md border-2 border-black p-4">
			<h2 class="mb-2 text-xl font-extrabold">Genealogía</h2>
			<p><span class="font-bold">Madre:</span> {mother ? `${mother.tag} ${mother.name}` : '—'}</p>
			<p><span class="font-bold">Padre:</span> {father ? `${father.tag} ${father.name}` : '—'}</p>
			{#if offspring.length > 0}
				<p class="mt-2 font-bold">Crías:</p>
				<ul class="ml-4 list-disc">
					{#each offspring as calf (calf.id)}
						<li>
							<a href="/animals/{calf.id}" class="underline">{calf.tag} {calf.name}</a>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section class="rounded-md border-2 border-black p-4">
			<h2 class="mb-2 text-xl font-extrabold">Pesajes</h2>
			<ul class="flex flex-col gap-1">
				{#each weighings as w (w.id)}
					<li class="flex justify-between"><span>{w.date}</span><span class="font-extrabold">{w.weight_kg} kg</span></li>
				{:else}
					<li class="text-neutral-600">Sin pesajes.</li>
				{/each}
			</ul>
		</section>

		<section class="rounded-md border-2 border-black p-4">
			<h2 class="mb-2 text-xl font-extrabold">Ordeños</h2>
			<ul class="flex flex-col gap-1">
				{#each milkings as m (m.id)}
					<li class="flex justify-between"><span>{m.date} {m.shift}</span><span class="font-extrabold">{m.liters} L</span></li>
				{:else}
					<li class="text-neutral-600">Sin ordeños.</li>
				{/each}
			</ul>
		</section>

		<section class="rounded-md border-2 border-black p-4">
			<h2 class="mb-2 text-xl font-extrabold">Reproducción</h2>
			<ul class="flex flex-col gap-1">
				{#each reproEvents as e (e.id)}
					<li class="flex justify-between">
						<span>{e.date}</span>
						<span class="font-extrabold">{TYPE_LABELS[e.type] ?? e.type}</span>
					</li>
					{#if e.estimated_calving_date}
						<li class="ml-4 text-sm">Parto estimado: {e.estimated_calving_date} · Secado: {e.suggested_drying_off_date}</li>
					{/if}
				{:else}
					<li class="text-neutral-600">Sin eventos reproductivos.</li>
				{/each}
			</ul>
		</section>

		<section class="rounded-md border-2 border-black p-4">
			<h2 class="mb-2 text-xl font-extrabold">Sanidad</h2>
			<ul class="flex flex-col gap-1">
				{#each healthEvents as e (e.id)}
					<li class="flex justify-between">
						<span>{e.date}</span>
						<span class="font-extrabold">{TYPE_LABELS[e.type] ?? e.type}: {e.product}</span>
					</li>
					{#if e.withdrawal_end_date}
						<li class="ml-4 text-sm font-bold text-red-700">Retiro hasta: {e.withdrawal_end_date}</li>
					{/if}
				{:else}
					<li class="text-neutral-600">Sin eventos sanitarios.</li>
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

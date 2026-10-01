<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	import { Badge } from '$lib/components/ui/badge';
	import * as Tabs from '$lib/components/ui/tabs';
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
	const STATUS_LABELS: Record<string, string> = {
		active: 'Activo', sold: 'Vendido', dead: 'Muerto', culled: 'Descarte'
	};
	const CATEGORY_LABELS: Record<string, string> = {
		calf: 'Ternero/a', heifer: 'Novillo/a', cow_lactating: 'Vaca en ordeño',
		cow_dry: 'Vaca seca', bull: 'Toro reproductor'
	};

	let weightCurve = $derived.by(() => {
		if (weighings.length < 2) return null;
		const points = [...weighings].reverse();
		const values = points.map((w) => parseFloat(w.weight_kg));
		const min = Math.min(...values);
		const max = Math.max(...values);
		const span = max - min || 1;
		const coords = points.map((w, i) => {
			const x = (i / (points.length - 1)) * 300;
			const y = 60 - ((parseFloat(w.weight_kg) - min) / span) * 60;
			return `${x.toFixed(1)},${y.toFixed(1)}`;
		});
		return { path: coords.join(' '), min, max };
	});
</script>

<svelte:head><title>Ficha {animal?.tag ?? ''} · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	{#if notFound}
		<p class="rounded-md border-2 border-red-700 bg-red-50 p-4 font-bold text-red-700">
			Animal no encontrado en este dispositivo.
		</p>
	{:else if animal}
		<div class="rounded-md border-2 border-black p-4">
			{#if animal.photo_url}
				<img
					src={animal.photo_url}
					alt="Foto de {animal.tag}"
					class="mb-3 w-full rounded-md border-2 border-black object-cover"
				/>
			{/if}
			<div class="flex items-start justify-between gap-2">
				<div>
					<p class="text-3xl font-extrabold">{animal.tag}</p>
					<p class="text-lg">{animal.name || 'Sin nombre'}</p>
					<p class="text-sm font-bold uppercase text-neutral-600">
						{animal.sex} · {CATEGORY_LABELS[animal.category] ?? animal.category}
					</p>
				</div>
				<div class="flex flex-col items-end gap-1">
					<Badge
						class={animal.status === 'active'
							? 'bg-green-700 text-white'
							: 'bg-red-700 text-white'}
					>
						{STATUS_LABELS[animal.status] ?? animal.status}
					</Badge>
					{#if activeWithdrawal}
						<Badge class="bg-red-700 text-white">Retiro hasta {activeWithdrawal}</Badge>
					{/if}
				</div>
			</div>
			{#if animal.status !== 'active' && animal.status_changed_at}
				<p class="mt-1 text-sm font-bold text-red-700">
					{STATUS_LABELS[animal.status]} el {animal.status_changed_at}{animal.status_reason
						? ` — ${animal.status_reason}`
						: ''}
				</p>
			{/if}
		</div>

		<Tabs.Root value="general">
			<Tabs.List class="grid w-full grid-cols-4">
				<Tabs.Trigger value="general">General</Tabs.Trigger>
				<Tabs.Trigger value="production">Producción</Tabs.Trigger>
				<Tabs.Trigger value="reproduction">Repro</Tabs.Trigger>
				<Tabs.Trigger value="health">Sanidad</Tabs.Trigger>
			</Tabs.List>

			<Tabs.Content value="general">
				<div class="flex flex-col gap-4 pt-2">
					<section class="rounded-md border-2 border-black p-4">
						<h2 class="mb-2 text-lg font-extrabold">Datos</h2>
						{#if animal.birth_date}
							<p><span class="font-bold">Nacimiento:</span> {animal.birth_date}</p>
						{/if}
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
				</div>
			</Tabs.Content>

			<Tabs.Content value="production">
				<div class="flex flex-col gap-4 pt-2">
					<section class="rounded-md border-2 border-black p-4">
						<h2 class="mb-2 text-lg font-extrabold">Pesajes</h2>
						{#if weightCurve}
							<svg viewBox="0 0 300 60" class="mb-2 w-full" role="img" aria-label="Curva de peso">
								<polyline points={weightCurve.path} fill="none" stroke="black" stroke-width="2" />
							</svg>
							<p class="mb-2 flex justify-between text-xs font-bold">
								<span>Mín {weightCurve.min} kg</span>
								<span>Máx {weightCurve.max} kg</span>
							</p>
						{/if}
						<ul class="flex flex-col gap-1">
							{#each weighings as w (w.id)}
								<li class="flex justify-between">
									<span>{w.date}</span>
									<span class="font-extrabold">{w.weight_kg} kg</span>
								</li>
							{:else}
								<li class="text-neutral-600">Sin pesajes.</li>
							{/each}
						</ul>
					</section>
					<section class="rounded-md border-2 border-black p-4">
						<h2 class="mb-2 text-lg font-extrabold">Ordeños</h2>
						<ul class="flex flex-col gap-1">
							{#each milkings as m (m.id)}
								<li class="flex justify-between">
									<span>{m.date} {m.shift}</span>
									<span class="font-extrabold">{m.liters} L</span>
								</li>
							{:else}
								<li class="text-neutral-600">Sin ordeños.</li>
							{/each}
						</ul>
					</section>
				</div>
			</Tabs.Content>

			<Tabs.Content value="reproduction">
				<section class="mt-2 rounded-md border-2 border-black p-4">
					<h2 class="mb-2 text-lg font-extrabold">Eventos reproductivos</h2>
					<ul class="flex flex-col gap-1">
						{#each reproEvents as e (e.id)}
							<li>
								<div class="flex justify-between">
									<span>{e.date}</span>
									<span class="font-extrabold">{TYPE_LABELS[e.type] ?? e.type}</span>
								</div>
								{#if e.estimated_calving_date}
									<p class="ml-4 text-sm">
										Parto estimado: {e.estimated_calving_date} · Secado: {e.suggested_drying_off_date}
									</p>
								{/if}
							</li>
						{:else}
							<li class="text-neutral-600">Sin eventos reproductivos.</li>
						{/each}
					</ul>
				</section>
			</Tabs.Content>

			<Tabs.Content value="health">
				<section class="mt-2 rounded-md border-2 border-black p-4">
					<h2 class="mb-2 text-lg font-extrabold">Eventos sanitarios</h2>
					<ul class="flex flex-col gap-1">
						{#each healthEvents as e (e.id)}
							<li>
								<div class="flex justify-between">
									<span>{e.date}</span>
									<span class="font-extrabold">{TYPE_LABELS[e.type] ?? e.type}: {e.product}</span>
								</div>
								{#if e.withdrawal_end_date || e.withdrawal_days}
									<p class="ml-4 text-sm font-bold text-red-700">
										Retiro hasta: {e.withdrawal_end_date ?? addDays(e.date, e.withdrawal_days ?? 0)}
									</p>
								{/if}
							</li>
						{:else}
							<li class="text-neutral-600">Sin eventos sanitarios.</li>
						{/each}
					</ul>
				</section>
			</Tabs.Content>
		</Tabs.Root>
	{/if}

	<button
		type="button"
		onclick={() => goto('/herd')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver al hato
	</button>
</div>

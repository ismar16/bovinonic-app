<script lang="ts">
	import { farmDate, addDateDays } from '$lib/dates';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { liveQuery } from 'dexie';

	import { Pencil, ArrowLeft, ArrowRightLeft } from 'lucide-svelte';
	import { currentFarm } from '$lib/stores';
	import { Badge } from '$lib/components/ui/badge';
	import * as Tabs from '$lib/components/ui/tabs';
	import { db, type AnimalAgreement, type Animal, type HealthEvent, type Milking, type ReproductiveEvent, type Weighing } from '$lib/db';

	let agreements = $state<AnimalAgreement[]>([]);
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
	let pending = $state(false);
	let paddockName = $state('Sin asignar');
	let lotName = $state('Sin lote');
	let ownerName = $state('Sin asignar');
	const canEdit = $derived(['admin','technician'].includes($currentFarm?.role ?? ''));

	function addDays(isoDate: string, days: number): string {
		return addDateDays(isoDate, days);
	}

	async function loadAnimal() {
		const id = page.params.id;
		if (!id) {
			notFound = true;
			return;
		}
		const found = await db.animals.get(id);
		if (!found || found.farm !== $currentFarm?.id) {
			notFound = true;
			return;
		}
		pending = (await db.outbox.toArray()).some((r) => r.collection === 'animals' && r.record_id === found.id);
		lotName = found.lot ? (await db.lots.get(found.lot))?.name ?? 'Sin datos' : 'Sin lote';
		if (found.paddock) paddockName = (await db.paddocks.get(found.paddock))?.name ?? 'Sin asignar';
		if (found.owner) ownerName = (await db.owners.get(found.owner))?.name ?? 'Sin asignar';
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
		const allHealth = (await db.health_events.where('animal').equals(found.id).sortBy('date')).reverse();
		healthEvents = allHealth.slice(0, 10);
		const today = farmDate();
		const active = allHealth
			.filter((e) => e.withdrawal_days > 0 && e.date <= today)
			.map((e) => e.withdrawal_end_date ?? addDays(e.date, e.withdrawal_days ?? 0))
			.filter((end) => end >= today)
			.sort()
			.reverse();
		activeWithdrawal = active[0] ?? null;
		agreements = $currentFarm?.role === 'admin' ? (await db.agreements.where('farm').equals(found.farm).toArray()).filter((a) => a.animals.some((r) => r.animal === found.id)) : [];
		animal = found;
	}
	onMount(() => {
		const subscription = liveQuery(loadAnimal).subscribe({ error() { notFound = true; } });
		return () => subscription.unsubscribe();
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

<div class="workspace-page flex flex-col gap-5">
	{#if notFound}
		<p class="rounded-md border-2 border-red-700 bg-red-50 p-4 font-bold text-red-700">
			Animal no encontrado en este dispositivo.
		</p>
	{:else if animal}
        <header class="flex flex-wrap items-center justify-between gap-3"><a href="/herd" class="inline-flex items-center gap-2 text-xs text-[#7a886b]"><ArrowLeft class="h-4 w-4" /> Volver al hato</a>{#if canEdit}<a href="/animals/{animal.id}/edit" class="action-button"><Pencil class="h-4 w-4" /> Editar datos</a>{/if}</header>
        <div class="panel p-5 sm:p-7">
			{#if animal.photo_url}
				<img
					src={animal.photo_url}
					alt="Foto de {animal.tag}"
					class="mb-4 h-48 w-full rounded-xl object-cover sm:h-64"
				/>
			{/if}
			<div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
				<div>
					<p class="eyebrow mb-2">Ficha individual del animal</p><h1 class="page-title">{animal.tag}</h1>
					<p class="mt-2 font-serif text-xl text-[#7a8969]">{animal.name || 'Sin nombre'}</p>
					<p class="text-sm font-bold uppercase text-neutral-600">
						{animal.sex} · {CATEGORY_LABELS[animal.category] ?? animal.category}
					</p>
				</div>
				<div class="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end">{#if pending}<span class="status-pill pending">Cambios pendientes de envío</span>{/if}
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

        <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {#each [{label:'Lote',value:lotName}, {label:'Potrero',value:paddockName}, {label:'Propietario',value:ownerName}, {label:'Último peso',value:weighings[0] ? `${weighings[0].weight_kg} kg` : 'Sin registro'}, {label:'Nacimiento',value:animal.birth_date ?? 'Sin registrar'}] as item}<div class="panel p-4"><p class="eyebrow">{item.label}</p><p class="mt-2 text-sm font-semibold">{item.value}</p></div>{/each}
        </div>
        <section class="panel space-y-3 p-5"><h2 class="section-title">Acuerdos y estadías</h2>{#if $currentFarm?.role === 'admin'}{#each agreements as agreement}<a class="block rounded-xl border p-3 text-sm" href="/agreements/{agreement.id}"><strong>{agreement.title}</strong><span class="mt-1 block text-xs text-[#7c8e70]">{agreement.external_farm} · {agreement.partner_name} · {agreement.status === 'active' ? 'En curso' : 'Liquidado'}</span></a>{:else}<p class="field-help">Sin acuerdos registrados para este animal.</p>{/each}<a class="back-link mb-0" href="/agreements/new?animal={animal.id}">Registrar un acuerdo para este animal</a>{:else}<p class="field-help">Los acuerdos y sus liquidaciones están disponibles para administradores.</p>{/if}</section>
        <Tabs.Root value="general">
			<Tabs.List class="grid h-auto min-h-11 w-full grid-cols-4">
				<Tabs.Trigger value="general">General</Tabs.Trigger>
				<Tabs.Trigger value="production">Producción</Tabs.Trigger>
				<Tabs.Trigger value="reproduction">Repro</Tabs.Trigger>
				<Tabs.Trigger value="health">Sanidad</Tabs.Trigger>
			</Tabs.List>

			<Tabs.Content value="general">
				<div class="flex flex-col gap-4 pt-2">
					<section class="panel p-5 sm:p-7">
						<h2 class="section-title mb-3">Datos del animal</h2>{#if animal.lot}<a class="back-link" href="/lots/{animal.lot}">Ver lote: {lotName}</a>{/if}
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
					{#if canEdit}<div class="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
						<a
							href="/animals/{animal.id}/edit"
							class="quiet-button min-h-12 w-full whitespace-nowrap"
							><Pencil class="h-4 w-4 shrink-0" /> Editar datos</a
						>
						<a
							href="/animals/{animal.id}/status"
							class="flex min-h-12 w-full items-center justify-center gap-2 whitespace-nowrap rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-800 hover:bg-red-100"
							><ArrowRightLeft class="h-4 w-4 shrink-0" /> Cambio de estado</a
						>
					</div>{/if}
				</div>
			</Tabs.Content>

			<Tabs.Content value="production">
				<div class="flex flex-col gap-4 pt-2">
					<section class="panel p-5 sm:p-7">
						<h2 class="section-title mb-3">Pesajes</h2><a class="back-link" href="/weighing?animal={animal.id}">Registrar pesaje</a>
						{#if weightCurve}
							<svg viewBox="0 0 300 60" class="mb-2 w-full" role="img" aria-label="Curva de peso">
								<polyline points={weightCurve.path} fill="none" stroke="#31583c" stroke-width="2" />
							</svg>
							<p class="mb-2 flex justify-between text-xs font-bold">
								<span>Mín {weightCurve.min} kg</span>
								<span>Máx {weightCurve.max} kg</span>
							</p>
						{/if}
						<ul class="flex flex-col gap-1">
							{#each weighings as w (w.id)}
								<li class="flex flex-wrap justify-between gap-2">
									<span>{w.date}</span>
									<span class="font-extrabold">{w.weight_kg} kg</span>
								</li>
							{:else}
								<li class="text-neutral-600">Sin pesajes.</li>
							{/each}
						</ul>
					</section>
					<section class="panel p-5 sm:p-7">
						<h2 class="section-title mb-3">Ordeños</h2>{#if animal.category === 'cow_lactating'}<a class="back-link" href="/milking?animal={animal.id}">Registrar ordeño</a>{/if}
						<ul class="flex flex-col gap-1">
							{#each milkings as m (m.id)}
								<li class="flex flex-wrap justify-between gap-2">
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
				<section class="mt-2 rounded-xl border border-[#dde3d3] bg-white p-4">
					<h2 class="section-title mb-3">Eventos reproductivos</h2>{#if canEdit && animal.sex === 'H'}<a class="back-link" href="/reproduction?animal={animal.id}">Registrar evento</a>{/if}
					<ul class="flex flex-col gap-1">
						{#each reproEvents as e (e.id)}
							<li>
								<div class="flex flex-wrap justify-between gap-2">
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
				<section class="mt-2 rounded-xl border border-[#dde3d3] bg-white p-4">
					<h2 class="section-title mb-3">Eventos sanitarios</h2>{#if canEdit}<a class="back-link" href="/health?animal={animal.id}">Registrar atención</a>{/if}
					<ul class="flex flex-col gap-1">
						{#each healthEvents as e (e.id)}
							<li>
								<div class="flex flex-wrap justify-between gap-2">
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
		class="h-14 w-full rounded-xl border border-[#dde3d3] bg-white font-extrabold"
	>
		Volver al hato
	</button>
</div>

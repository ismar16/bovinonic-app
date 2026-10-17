<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { liveQuery } from 'dexie';
	import { db, type Animal, type AnimalLot, type Paddock, type PaddockMovement, type OutboxRecord } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueue, reviewFinancialPending } from '$lib/sync';
	import { pull } from '$lib/api';
	import { farmDate } from '$lib/dates';
	import { movementRows } from '$lib/paddocks';
	import { errorMessage } from '$lib/forms';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	let { form = false }: { form?: boolean } = $props();
	let animals = $state<Animal[]>([]), paddocks = $state<Paddock[]>([]), lots = $state<AnimalLot[]>([]), history = $state<PaddockMovement[]>([]), pending = $state<OutboxRecord[]>([]);
	let destination = $state(''), lot = $state(''), mode = $state('lot'), date = $state(farmDate()), notes = $state(''), query = $state('');
	let selected = $state<string[]>([]), error = $state(''), loading = $state(true), saving = $state(false), saved = $state(false), reviewing = $state(false);
	let successMessage = $state('Traslado guardado. Revisá en el historial si ya fue confirmado o sigue pendiente.');
	let id = $state<string>(crypto.randomUUID());
	const canMove = $derived(['admin','technician'].includes($currentFarm?.role ?? ''));
	const eligible = $derived(animals.filter((a) => a.status === 'active' && (!lot || mode !== 'lot' || a.lot === lot) && a.paddock !== destination));
	const visible = $derived(eligible.filter((a) => `${a.tag} ${a.name}`.toLowerCase().includes(query.toLowerCase())));
	const selectedAnimals = $derived(animals.filter((a) => selected.includes(a.id)));
	const pendingIds = $derived(new Set(pending.filter((r) => r.collection === 'paddock_movements').map((r) => r.record_id)));
	const paddockName = (id: string | null) => paddocks.find((p) => p.id === id)?.name ?? 'Sin asignar';
	function chooseLot() { selected = mode === 'lot' && lot ? eligible.map((a) => a.id) : []; }
	onMount(() => {
		const farm = $currentFarm;
		if (!farm) { loading = false; return; }
		let subscription: { unsubscribe(): void } | undefined;
		(async () => {
			try {
				destination = page.url.searchParams.get('destination') ?? ''; lot = page.url.searchParams.get('lot') ?? '';
				const single = page.url.searchParams.get('animal');
				const pendingId = page.url.searchParams.get('pending');
				if (form && pendingId) {
					if (!canMove) throw new Error('Tu rol no permite revisar traslados.');
					if (await reviewFinancialPending('paddock_movements', pendingId)) { saved = true; }
					else {
						const draft = await db.paddock_movements.get(pendingId);
						if (!draft || draft.farm !== farm.id) throw new Error('El traslado pendiente no está disponible.');
						const data = await pull(farm.id);
						const outbox = await db.outbox.toArray();
						const unsentAnimals = new Set(outbox.filter((r) => r.collection === 'animals').map((r) => r.record_id));
						await db.animals.bulkPut((data.animals as Animal[] ?? []).filter((a) => !unsentAnimals.has(a.id)));
						id = draft.id; destination = draft.destination; date = draft.date; notes = draft.notes; lot = draft.lot ?? ''; mode = lot ? 'lot' : 'animal'; selected = draft.animals.map((r) => r.animal); reviewing = true;
					}
				}
				subscription = liveQuery(async () => ({ animals: await db.animals.where('farm').equals(farm.id).toArray(), paddocks: await db.paddocks.where('farm').equals(farm.id).toArray(), lots: await db.lots.where('farm').equals(farm.id).toArray(), history: await db.paddock_movements.where('farm').equals(farm.id).toArray(), pending: await db.outbox.toArray() })).subscribe({ next(data) { animals = data.animals; paddocks = data.paddocks; lots = data.lots; history = data.history; pending = data.pending; if (loading && !reviewing && !saved) { if (single) { mode = 'animal'; selected = [single]; } else if (lot) chooseLot(); } loading = false; }, error() { error = 'No se pudieron cargar los movimientos.'; loading = false; } });
			} catch (cause) { error = errorMessage(cause); loading = false; }
		})();
		return () => subscription?.unsubscribe();
	});
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (!canMove || saving || saved) return; saving = true; error = '';
		try {
			if (!paddocks.some((p) => p.id === destination)) throw new Error('Elegí un potrero de esta finca.');
			if (mode === 'lot' && !lot) throw new Error('Elegí un lote.');
			const rows = movementRows(animals, selected, destination, date, farmDate(), mode === 'lot' ? lot : null);
			const blocking = pending.some((r) => (r.collection === 'animals' && selected.includes(r.record_id)) || (r.collection === 'paddock_movements' && r.record_id !== id && (r.payload.animals as PaddockMovement['animals']).some((a) => selected.includes(a.animal))));
			if (blocking) throw new Error('Hay cambios o traslados pendientes de estos animales. Sincronizalos antes de guardar otro movimiento.');
			await enqueue('paddock_movements', { id, date, destination, lot: mode === 'lot' ? lot : null, animals: rows, notes: notes.trim() });
			saved = true;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
	async function discard() {
		if (saving || saved) return; saving = true; error = '';
		try { const confirmed = await reviewFinancialPending('paddock_movements', id, true); successMessage = confirmed ? 'El servidor ya confirmó el traslado. Su historial se conservó.' : 'Se descartó el pendiente sin confirmar. Las ubicaciones no se modificaron.'; saved = true; reviewing = false; }
		catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>
<svelte:head><title>{form ? 'Mover animales' : 'Movimientos de potreros'} · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-5">
	<PageHeader title={form ? 'Mover animales de potrero' : 'Movimientos de potreros'} eyebrow="Manejo y rotación" description="Trasladá por lote o elegí animales individuales. Cada movimiento conserva la fecha y el potrero de origen." backHref={form ? '/paddocks/movements' : '/catalogs/paddocks'} backLabel={form ? 'Historial de movimientos' : 'Potreros'} />
	<Notice tone="error" message={error} />
	{#if loading}<p class="empty-state">Cargando…</p>{:else if form && !canMove}<Notice tone="warning" message="Los traslados requieren un técnico o administrador." />{:else if form}
		{#if reviewing}<Notice tone="warning" message="Este traslado aún no está confirmado. Se consultó la ubicación actual del servidor: revisá la selección y el destino antes de volver a guardarlo." /><button type="button" class="quiet-button" disabled={saving || saved} onclick={discard}>Descartar pendiente sin confirmar</button>{/if}
		{#if !paddocks.length}<Notice tone="warning" message="Primero agregá un potrero en Catálogos." />{/if}
		<form onsubmit={save} class="space-y-5"><fieldset disabled={saving || saved} class="form-section space-y-5">
			<div class="form-grid"><label class="field-label">Fecha del traslado *<input class="field" type="date" max={farmDate()} bind:value={date} required /></label><label class="field-label">Potrero de destino *<select class="field" bind:value={destination} onchange={chooseLot} required><option value="">Elegí un potrero</option>{#each paddocks as p}<option value={p.id}>{p.name}</option>{/each}</select></label></div>
			<div class="form-grid"><label class="field-label">Seleccionar animales<select class="field" bind:value={mode} onchange={() => { lot = ''; selected = []; }}><option value="lot">Por lote</option><option value="animal">Por animal</option></select></label>{#if mode === 'lot'}<label class="field-label">Lote *<select class="field" bind:value={lot} onchange={chooseLot} required><option value="">Elegí un lote</option>{#each lots as l}<option value={l.id}>{l.name}</option>{/each}</select></label>{/if}</div>
			<p class="field-help">Se seleccionan los animales activos que todavía no están en el destino. Podés desmarcar excepciones; su pertenencia al lote se conserva.</p>
			<label class="field-label">Buscar animales<input class="field" bind:value={query} placeholder="Arete o nombre" /></label>
			{#if mode !== 'lot' || lot}<div class="max-h-80 overflow-y-auto rounded-xl border divide-y">{#each visible as a}<label class="flex cursor-pointer items-center gap-3 p-4"><input type="checkbox" value={a.id} bind:group={selected} /><span class="min-w-0 break-words"><strong>{a.tag}</strong> · {a.name || 'Sin nombre'}<span class="block field-help">Origen: {paddockName(a.paddock)}</span></span></label>{:else}<p class="empty-state m-3">No hay animales disponibles con esta selección.</p>{/each}</div>{/if}
			<div class="notice"><strong>{selected.length} animales seleccionados</strong><p class="field-help break-words">{selectedAnimals.map((a) => a.tag).join(', ')}</p></div>
			<label class="field-label">Observaciones<textarea class="field" maxlength="500" bind:value={notes}></textarea></label>
		</fieldset><p class="field-help">La ubicación se actualizará al confirmar el servidor. Sin internet, el traslado queda pendiente de envío. Un movimiento confirmado se corrige con otro traslado.</p>
		{#if saved}<Notice tone="success" message={successMessage} />{/if}
		<div class="form-actions"><button class="action-button" disabled={saving || saved || !selected.length || !destination}>{saving ? 'Guardando…' : saved ? 'Guardado' : `Guardar traslado de ${selected.length} animales`}</button><a class="quiet-button" href="/paddocks/movements">Ver historial</a></div></form>
	{:else}
		{#if canMove}<a class="action-button" href="/paddocks/movements/new">Registrar traslado</a>{/if}
		<div class="space-y-4">{#each [...history].sort((a,b) => b.date.localeCompare(a.date) || (b.updated_at ?? '').localeCompare(a.updated_at ?? '')) as movement}<article class="panel p-5 space-y-3"><p class="field-help">{movement.date} · {movement.lot ? lots.find((l) => l.id === movement.lot)?.name ?? 'Lote' : 'Selección por animal'}</p><h2 class="section-title">Hacia {paddockName(movement.destination)}</h2><span class="status-pill">{pendingIds.has(movement.id) ? 'Pendiente de confirmación' : 'Confirmado'}</span><p>{movement.animals.length} animales</p><details><summary class="cursor-pointer text-sm font-semibold">Ver animales y orígenes</summary><ul class="mt-3 space-y-2">{#each movement.animals as row}<li class="text-sm"><a class="underline" href="/animals/{row.animal}">{animals.find((a) => a.id === row.animal)?.tag ?? 'Animal'}</a> · {paddockName(row.from_paddock)} → {paddockName(movement.destination)}</li>{/each}</ul></details>{#if movement.notes}<p class="field-help break-words">{movement.notes}</p>{/if}{#if canMove && pendingIds.has(movement.id)}<a class="quiet-button" href="/paddocks/movements/new?pending={movement.id}">Revisar traslado pendiente</a>{/if}</article>{:else}<p class="empty-state">Todavía no hay movimientos. Las ubicaciones anteriores se conservan sin inventar fechas de ingreso.</p>{/each}</div>
	{/if}
</div>

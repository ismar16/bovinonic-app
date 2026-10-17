<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { liveQuery } from 'dexie';
	import { Syringe, Check, Layers } from 'lucide-svelte';
	import { db, type Animal, type AnimalLot, type HealthEvent } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueueMany } from '$lib/sync';
	import { farmDate, addDateDays } from '$lib/dates';
	import { errorMessage, validDate } from '$lib/forms';
	import { buildLotHealthEvents, existingLotHealthAnimals } from '$lib/lot-health';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	let animals = $state<Animal[]>([]), lots = $state<AnimalLot[]>([]), events = $state<HealthEvent[]>([]);
	let lot = $state(''), date = $state(farmDate()), type = $state<HealthEvent['type']>('vaccine'), product = $state(''), withdrawal = $state('0'), defaultDose = $state('');
	let selected = $state<string[]>([]), doses = $state<Record<string,string>>({}), eventIds = $state<Record<string,string>>({});
	let loading = $state(true), saving = $state(false), saved = $state(false), error = $state(''), duplicateAccepted = $state(false);
	let savedIds = $state<string[]>([]), pendingIds = $state<string[]>([]);
	const canWrite = $derived(['admin','technician'].includes($currentFarm?.role ?? ''));
	const members = $derived(animals.filter((a) => a.lot === lot && a.status === 'active').sort((a,b) => a.tag.localeCompare(b.tag,'es',{numeric:true})));
	const excluded = $derived(animals.filter((a) => a.lot === lot && a.status !== 'active').length);
	const duplicates = $derived(existingLotHealthAnimals(events, selected, date, type, product, Object.values(eventIds)));
	const duplicateSignature = $derived(JSON.stringify([lot,date,type,product.trim().toLocaleLowerCase('es'),selected,duplicates]));
	const withdrawalEnd = $derived(validDate(date) && /^\d+$/.test(withdrawal) && Number(withdrawal) > 0 && Number(withdrawal) <= 3650 ? addDateDays(date, Number(withdrawal)) : null);
	const pendingSaved = $derived(savedIds.filter((id) => pendingIds.includes(id)).length);
	$effect(() => { void duplicateSignature; duplicateAccepted = false; });
	function chooseLot() {
		selected = members.map((a) => a.id); doses = {}; eventIds = {}; error = ''; savedIds = []; saved = false;
	}
	function fillDoses() {
		for (const id of selected) if (!doses[id]?.trim()) doses[id] = defaultDose.trim();
	}
	onMount(() => {
		const farm = $currentFarm;
		if (!farm) { loading = false; return; }
		const initialLot = page.url.searchParams.get('lot');
		const subscription = liveQuery(async () => ({ animals: await db.animals.where('farm').equals(farm.id).toArray(), lots: await db.lots.where('farm').equals(farm.id).toArray(), events: await db.health_events.toArray(), pending: (await db.outbox.toArray()).filter((r) => r.collection === 'health_events').map((r) => r.record_id) })).subscribe({ next(data) { animals = data.animals; lots = data.lots; events = data.events; pendingIds = data.pending; if (loading && initialLot && lots.some((row) => row.id === initialLot)) { lot = initialLot; chooseLot(); } loading = false; }, error() { error = 'No se pudieron cargar los animales del lote.'; loading = false; } });
		return () => subscription.unsubscribe();
	});
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (!canWrite || saving || saved) return; saving = true; error = '';
		try {
			const farm = $currentFarm;
			if (!farm || !lots.some((row) => row.id === lot && row.farm === farm.id)) throw new Error('Elegí un lote de la finca actual.');
			if (duplicates.length && !duplicateAccepted) throw new Error('Revisá los animales que ya tienen este producto en la misma fecha.');
			for (const id of selected) eventIds[id] ??= crypto.randomUUID();
			// Recheck local animal state at save time; the server validates dates and farm again.
			const currentAnimals = await db.animals.where('farm').equals(farm.id).toArray();
			if ($currentFarm?.id !== farm.id) throw new Error('La finca cambió. Volvé a abrir el formulario antes de guardar.');
			const records = buildLotHealthEvents({ farm: farm.id, lot, date, type, product, withdrawal, selected, doses, eventIds }, currentAnimals, farmDate());
			await enqueueMany(records.map((payload) => ({ collection: 'health_events', payload: { ...payload } })));
			savedIds = records.map((r) => r.id); pendingIds = [...new Set([...pendingIds, ...savedIds])]; saved = true;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>
<svelte:head><title>Sanidad por lote · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-5">
	<PageHeader title="Atención sanitaria por lote" eyebrow="Salud del hato" description="Un mismo producto para los animales del lote, con la dosis aplicada a cada uno. Se guarda un evento individual en cada ficha." backHref="/operations" backLabel="Operaciones" />
	<nav class="flex flex-wrap gap-2" aria-label="Forma de registro sanitario"><a class="quiet-button" href="/health">Por animal</a><a class="action-button" href="/health/bulk" aria-current="page"><Layers class="h-4 w-4" />Por lote</a></nav>
	<Notice tone="error" message={error} />
	{#if loading}<p class="empty-state">Cargando lotes…</p>{:else if !canWrite}<Notice tone="warning" message="La atención sanitaria requiere un técnico o administrador." />{:else if !lots.length}<p class="empty-state">Primero creá un lote y agregale animales.</p><a href="/lots" class="quiet-button">Ir a lotes</a>{:else}
		<form onsubmit={save} class="space-y-5">
			<fieldset disabled={saving || saved} class="form-section space-y-5">
				<div class="flex items-center gap-3"><Syringe class="h-6 w-6" /><h2 class="section-title">Producto y fecha comunes</h2></div>
				<div class="form-grid"><label class="field-label">Lote *<select class="field" bind:value={lot} onchange={chooseLot} required><option value="">Elegí un lote</option>{#each lots as row}<option value={row.id}>{row.name}</option>{/each}</select></label><label class="field-label">Fecha de aplicación *<input class="field" type="date" bind:value={date} max={farmDate()} required /></label><label class="field-label">Tipo de atención<select class="field" bind:value={type}><option value="vaccine">Vacunación</option><option value="deworming">Desparasitación</option><option value="antibiotic">Antibiótico</option><option value="vitamin">Vitamina</option></select></label><label class="field-label">Producto aplicado *<input class="field" maxlength="150" bind:value={product} placeholder="Nombre del producto" required /></label><label class="field-label">Días de retiro *<input class="field" inputmode="numeric" pattern="[0-9]+" bind:value={withdrawal} required /><span class="field-help">El plazo indicado para este producto y su aplicación.</span></label></div>
				{#if withdrawalEnd}<Notice tone="warning" message={`Retiro registrado hasta ${withdrawalEnd} para cada animal seleccionado.`} />{/if}
			</fieldset>
			{#if lot}<fieldset disabled={saving || saved} class="form-section space-y-5">
				<h2 class="section-title">Animales y dosis</h2><p class="field-help">El lote completo queda seleccionado. Desmarcá los animales que no recibieron el producto. {excluded ? `Inactivos excluidos: ${excluded}.` : ''}</p>
				<div class="grid gap-3 sm:flex sm:flex-wrap sm:items-end"><label class="field-label min-w-0 sm:flex-1">Dosis común opcional<input class="field" bind:value={defaultDose} maxlength="100" placeholder="Cantidad y unidad" /></label><button type="button" class="quiet-button" disabled={!defaultDose.trim() || !selected.length} onclick={fillDoses}>Completar dosis vacías</button></div>
				<p class="field-help">La dosis común solo completa campos vacíos; conserva los ajustes individuales. Registrá la cantidad aplicada y su unidad.</p>
				<div class="flex flex-wrap gap-2"><button type="button" class="quiet-button" onclick={() => selected = members.map((a) => a.id)}>Seleccionar todo el lote</button><button type="button" class="quiet-button" onclick={() => selected = []}>Quitar selección</button><span class="status-pill">{selected.length} de {members.length} seleccionados</span></div>
				<div class="space-y-3">{#each members as animal (animal.id)}<div class="grid gap-3 rounded-xl border p-4 sm:grid-cols-2 sm:items-center"><label class="flex min-w-0 cursor-pointer items-center gap-3"><input type="checkbox" value={animal.id} bind:group={selected} /><span class="min-w-0 break-words"><strong>{animal.tag}</strong><span class="block text-sm text-[#7f8e72]">{animal.name || 'Sin nombre'}</span></span></label><label class="field-label">Dosis de {animal.tag}{selected.includes(animal.id) ? ' *' : ''}<input class="field" maxlength="100" bind:value={doses[animal.id]} placeholder="Cantidad y unidad" required={selected.includes(animal.id)} disabled={!selected.includes(animal.id)} /></label></div>{:else}<p class="empty-state">Este lote no tiene animales activos.</p>{/each}</div>
			</fieldset>{/if}
			{#if duplicates.length && !saved}<div class="notice warning space-y-3"><p>{duplicates.length} animales ya tienen este producto y tipo de atención en la misma fecha: {animals.filter((a) => duplicates.includes(a.id)).map((a) => a.tag).join(', ')}.</p><label class="flex items-start gap-2"><input type="checkbox" class="mt-1" bind:checked={duplicateAccepted} disabled={saving} /><span>Revisé sus fichas: corresponde registrar otra aplicación.</span></label></div>{/if}
			{#if saved}<Notice tone="success" message={pendingSaved ? `${savedIds.length} eventos guardados en este dispositivo. ${pendingSaved} pendientes de envío; ${savedIds.length - pendingSaved} confirmados.` : `${savedIds.length} eventos guardados y confirmados. Cada animal tiene su dosis en Sanidad.`} />{/if}
			<div class="form-actions"><button type="submit" class="action-button" disabled={saving || saved || !selected.length || !lot}>{#if saved}<Check class="h-4 w-4" />{/if}{saving ? 'Guardando…' : saved ? 'Registros guardados' : `Guardar atención de ${selected.length} animales`}</button>{#if saved}<a href="/lots/{lot}" class="quiet-button">Ver lote</a><a href="/health/withdrawals" class="quiet-button">Ver retiros activos</a>{/if}</div>
			{#if saved}<section class="panel p-5"><h2 class="section-title">Fichas de los animales atendidos</h2><div class="mt-3 flex flex-wrap gap-3">{#each animals.filter((a) => selected.includes(a.id)) as animal}<a class="quiet-button" href="/animals/{animal.id}">{animal.tag}</a>{/each}</div></section>{/if}
		</form>
	{/if}
</div>

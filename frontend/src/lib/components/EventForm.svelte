<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { ArrowRight, Check, Milk, Scale, HeartPulse, Syringe } from 'lucide-svelte';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	import TagSearch from './TagSearch.svelte';
	import { db, type Animal, type Weighing, type OutboxRecord } from '$lib/db';
	import { farmDate, addDateDays } from '$lib/dates';
	import { decimalValue, errorMessage, validDate } from '$lib/forms';
	import { enqueue } from '$lib/sync';
	import { currentFarm, pendingCount } from '$lib/stores';

	let { kind }: { kind: 'milking' | 'weighing' | 'health' | 'reproduction' } = $props();
	const options = {
		milking: { title: 'Registrar ordeño', eyebrow: 'Producción de leche', icon: Milk, description: 'Producción por animal, fecha y turno. Si el turno ya existe, se actualiza ese registro.', collection: 'milkings' },
		weighing: { title: 'Registrar pesaje', eyebrow: 'Crecimiento del hato', icon: Scale, description: 'Registrá el peso y comparalo con un pesaje anterior a la fecha elegida.', collection: 'weighings' },
		health: { title: 'Registrar atención sanitaria', eyebrow: 'Salud del animal', icon: Syringe, description: 'Anotá el producto, la dosis aplicada y los días de retiro indicados para ese tratamiento.', collection: 'health_events' },
		reproduction: { title: 'Registrar evento reproductivo', eyebrow: 'Seguimiento reproductivo', icon: HeartPulse, description: 'Llevá el control de servicios, diagnósticos, partos y secados de cada hembra.', collection: 'reproductive_events' }
	} as const;
	const config = $derived(options[kind]);
	const canWrite = $derived(kind === 'milking' || kind === 'weighing' || ['admin', 'technician'].includes($currentFarm?.role ?? ''));
	let animal = $state<Animal | null>(null);
	let date = $state(farmDate());
	let quantity = $state('');
	let shift = $state<'AM' | 'PM'>('AM');
	let eventType = $state('service');
	let healthType = $state('vaccine');
	let method = $state<'natural' | 'ai'>('natural');
	let result = $state<'pregnant' | 'empty'>('pregnant');
	let bull = $state('');
	let product = $state('');
	let dose = $state('');
	let withdrawal = $state('0');
	let includeInactive = $state(false);
	let saving = $state(false);
	let saved = $state(false);
	let error = $state('');
	let weighings = $state<Weighing[]>([]);
	let existingMilking = $state<string | null>(null);
	let milkingLookup = 0;
	const previous = $derived([...weighings].filter((w) => w.date < date).sort((a, b) => b.date.localeCompare(a.date))[0]);
	const gmd = $derived.by(() => {
		if (!previous || !validDate(date)) return null;
		const value = Number(quantity.replace(',', '.'));
		if (!quantity.trim() || !Number.isFinite(value) || value <= 0) return null;
		const days = (Date.parse(date) - Date.parse(previous.date)) / 86_400_000;
		return days > 0 ? (value - Number(previous.weight_kg)) / days : null;
	});
	const estimated = $derived(validDate(date) && eventType === 'service' ? addDateDays(date, 283) : null);
	const drying = $derived(estimated ? addDateDays(estimated, -60) : null);
	const withdrawalEnd = $derived(validDate(date) && /^\d+$/.test(withdrawal) && Number(withdrawal) > 0 && Number(withdrawal) <= 3650 ? addDateDays(date, Number(withdrawal)) : null);

	async function selectAnimal(selected: Animal) {
		animal = selected; error = ''; saved = false; quantity = '';
		weighings = kind === 'weighing' ? await db.weighings.where('animal').equals(selected.id).filter((w) => !w.voided).toArray() : [];
	}
	onMount(() => {
		const id = page.url.searchParams.get('animal');
		if (id) void db.animals.get(id).then((found) => {
			if (found && found.farm === $currentFarm?.id && (kind !== 'reproduction' || found.sex === 'H') && (kind !== 'milking' || found.category === 'cow_lactating')) void selectAnimal(found);
		});
	});
	$effect(() => {
		const id = animal?.id; const chosenDate = date; const chosenShift = shift; const lookup = ++milkingLookup;
		existingMilking = null;
		if (kind === 'milking' && id) void db.milkings.where('animal').equals(id).filter((m) => m.date === chosenDate && m.shift === chosenShift).first().then((row) => { if (lookup === milkingLookup) existingMilking = row?.id ?? null; });
	});
	function nextAnimal() { animal = null; quantity = ''; saved = false; error = ''; weighings = []; existingMilking = null; }
	async function save(event: SubmitEvent) {
		event.preventDefault();
		if (!animal || saving || saved || !canWrite) return;
		error = ''; saving = true;
		try {
			if (animal.birth_date && date < animal.birth_date) throw new Error('El evento no puede ser anterior al nacimiento del animal.');
			if (!validDate(date) || date > farmDate()) throw new Error('Elegí una fecha válida que no sea futura.');
			const payload: Record<string, unknown> & { id: string } = { id: crypto.randomUUID(), animal: animal.id, date };
			if (kind === 'milking') {
				const liters = decimalValue(quantity, true);
				if (liters > 9999.99) throw new Error('La cantidad de litros supera el máximo permitido.');
				// Recheck in the save path so a fast submit cannot create a local duplicate.
				const existing = await db.milkings.where('animal').equals(animal.id).filter((m) => m.date === date && m.shift === shift).first();
				payload.id = existing?.id ?? payload.id; payload.liters = liters.toFixed(2); payload.shift = shift;
			} else if (kind === 'weighing') {
				const weight = decimalValue(quantity);
				if (weight > 99999.99) throw new Error('El peso supera el máximo permitido.');
				payload.weight_kg = weight.toFixed(2);
			} else if (kind === 'health') {
				if (!product.trim()) throw new Error('Escribí el producto aplicado.');
				if (!/^\d+$/.test(withdrawal) || Number(withdrawal) > 3650) throw new Error('Los días de retiro deben ser un número entero entre 0 y 3650.');
				Object.assign(payload, { type: healthType, product: product.trim(), dose: dose.trim(), withdrawal_days: Number(withdrawal), withdrawal_end_date: withdrawalEnd });
			} else {
				if (animal.sex !== 'H') throw new Error('Seleccioná una hembra para este evento.');
				payload.type = eventType;
				if (eventType === 'service') Object.assign(payload, { service_method: method, bull_straw: bull.trim(), estimated_calving_date: estimated, suggested_drying_off_date: drying });
				if (eventType === 'palpation') payload.palpation_result = result;
			}
			await enqueue(config.collection as OutboxRecord['collection'], payload); saved = true;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>

<svelte:head><title>{config.title} · Bovinonic</title></svelte:head>
<div class="record-form mt-5 space-y-5">
	<PageHeader title={config.title} eyebrow={config.eyebrow} description={config.description} backHref="/operations" backLabel="Operaciones" />
	{#if !canWrite}<Notice tone="warning" message="Tu rol permite consultar estos datos. Un técnico o administrador puede registrarlos." />
	{:else if !animal}
		<section class="space-y-4"><div class="flex items-center gap-3"><span class="status-pill">1 · Seleccionar animal</span></div><TagSearch onSelect={selectAnimal} category={kind === 'milking' ? 'cow_lactating' : null} sex={kind === 'reproduction' ? 'H' : null} filterStatus={includeInactive ? null : 'active'} />
		<label class="flex items-center gap-2 text-xs text-[#7f8d74]"><input type="checkbox" bind:checked={includeInactive} /> Incluir animales inactivos para un registro histórico</label></section>
	{:else}
		<form onsubmit={save} class="space-y-5">
			<div class="form-section selected-animal"><div><p class="eyebrow">Animal seleccionado</p><p class="mt-2 text-lg font-semibold">{animal.tag}</p><p class="text-sm text-[#7f8e72]">{animal.name || 'Sin nombre'}</p></div><config.icon class="h-8 w-8 text-[#98ad84]" /></div>
			{#if animal.status !== 'active'}<Notice tone="warning" message="Este animal está inactivo. El registro se conservará como histórico." />{/if}
			<fieldset disabled={saving || saved} class="space-y-5">
				<div class="form-grid">
					<label class="field-label">Fecha del evento<input type="date" class="field" bind:value={date} max={farmDate()} required /></label>
					{#if kind === 'milking'}<label class="field-label">Turno<select class="field" bind:value={shift}><option value="AM">Mañana</option><option value="PM">Tarde</option></select></label>{/if}
					{#if kind === 'milking' || kind === 'weighing'}<label class="field-label">{kind === 'milking' ? 'Producción (litros)' : 'Peso (kg)'}<input class="field" bind:value={quantity} inputmode="decimal" placeholder="0.00" required /><span class="field-help">Podés usar punto o coma decimal.</span></label>{/if}
					{#if kind === 'health'}
						<label class="field-label">Tipo de atención<select class="field" bind:value={healthType}><option value="vaccine">Vacunación</option><option value="deworming">Desparasitación</option><option value="antibiotic">Antibiótico</option><option value="vitamin">Vitamina</option></select></label>
						<label class="field-label">Producto aplicado<input class="field" bind:value={product} maxlength="150" placeholder="Nombre del producto" required /></label>
						<label class="field-label">Dosis aplicada<input class="field" bind:value={dose} maxlength="100" placeholder="Cantidad y unidad" /></label>
						<label class="field-label">Días de retiro<input class="field" bind:value={withdrawal} inputmode="numeric" pattern="[0-9]+" required /><span class="field-help">Usá el plazo indicado para el producto y la aplicación.</span></label>
					{/if}
					{#if kind === 'reproduction'}
						<label class="field-label">Tipo de evento<select class="field" bind:value={eventType}><option value="service">Servicio (monta / inseminación)</option><option value="heat">Celo detectado</option><option value="palpation">Diagnóstico de preñez</option><option value="calving">Parto</option><option value="drying_off">Secado</option><option value="abortion">Aborto</option></select></label>
						{#if eventType === 'service'}<label class="field-label">Método<select class="field" bind:value={method}><option value="natural">Monta natural</option><option value="ai">Inseminación artificial</option></select></label><label class="field-label">Toro o pajilla<input class="field" bind:value={bull} maxlength="150" placeholder="Identificación (opcional)" /></label>{/if}
						{#if eventType === 'palpation'}<label class="field-label">Resultado<select class="field" bind:value={result}><option value="pregnant">Preñada</option><option value="empty">Vacía</option></select></label>{/if}
					{/if}
				</div>
				{#if kind === 'weighing'}<Notice message={previous ? `Pesaje anterior: ${previous.weight_kg} kg el ${previous.date}.${gmd === null ? '' : ` Ganancia media: ${gmd.toFixed(2)} kg/día.`}` : 'No hay un pesaje anterior a esta fecha para comparar.'} />{/if}
				{#if kind === 'milking' && existingMilking}<Notice tone="warning" message="Ya existe un ordeño para esta fecha y turno. Al guardar se reemplazará la cantidad de litros de ese registro." />{/if}
				{#if kind === 'health' && withdrawalEnd}<Notice tone="warning" message={`Retiro registrado hasta ${withdrawalEnd}. Revisá este plazo antes de guardar.`} />{/if}
				{#if kind === 'reproduction' && estimated}<Notice message={`Fechas orientativas: parto estimado ${estimated}; secado sugerido ${drying}. Se calculan a partir de la fecha de servicio.`} />{/if}
			</fieldset>
			<Notice tone="error" message={error} />
			{#if saved}<Notice tone="success" message={$pendingCount ? 'Guardado en este dispositivo. Hay registros pendientes de sincronizar.' : 'Guardado. No hay registros pendientes de envío.'} />{/if}
			<div class="form-actions"><button type="submit" class="action-button" disabled={saving || saved}>{#if saved}<Check class="h-4 w-4" />{/if}{saving ? 'Guardando…' : saved ? 'Registro guardado' : 'Guardar registro'}</button><button type="button" class="quiet-button" disabled={saving} onclick={nextAnimal}>{saved ? 'Registrar otro animal' : 'Cambiar animal'}<ArrowRight class="h-4 w-4" /></button>{#if saved}<a href="/animals/{animal.id}" class="back-link mb-0">Ver ficha</a>{/if}</div>
		</form>
	{/if}
</div>

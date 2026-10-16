<script lang="ts">
	import { onMount } from 'svelte';
	import { liveQuery } from 'dexie';
	import { db, type DailyMilkProduction } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueue } from '$lib/sync';
	import { farmDate } from '$lib/dates';
	import { errorMessage, decimalValue, validDate } from '$lib/forms';
	import { exportMilkTotalsCsv } from '$lib/reports';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	let date = $state(farmDate()), liters = $state(''), notes = $state(''), error = $state(''), message = $state('');
	let records = $state<DailyMilkProduction[]>([]), pending = $state<string[]>([]);
	let selecting = $state(false);
	let saving = $state(false), loading = $state(true), editing = $state(false), requested = 0;
	const history = $derived([...new Map([...records].sort((a,b) => Number(pending.includes(a.id))-Number(pending.includes(b.id)) || (a.updated_at ?? '').localeCompare(b.updated_at ?? '')).map((r) => [r.date,r])).values()].sort((a,b) => b.date.localeCompare(a.date)).slice(0,60));
	onMount(() => {
		if (!$currentFarm) { loading=false; return; }
		let first = true;
		const subscription = liveQuery(async () => ({records: await db.daily_milk.where('farm').equals($currentFarm!.id).toArray(),pending:(await db.outbox.toArray()).filter((r) => r.collection === 'daily_milk').map((r) => r.record_id)})).subscribe({next(data) { records=data.records; pending=data.pending; if(first) { first=false; void selectDay(date).finally(() => loading=false); } else loading=false; },error() { error='No se pudo leer la producción diaria.';loading=false; }});
		return () => subscription.unsubscribe();
	});
	async function selectDay(day: string) {
		const ticket = ++requested; selecting=true; date=day; error=''; message='';
		try {
		const rows = await db.daily_milk.where('farm').equals($currentFarm?.id ?? '').filter((r) => r.date === day).toArray();
		const row = rows.sort((a,b) => Number(pending.includes(b.id))-Number(pending.includes(a.id)) || (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))[0];
		if(ticket !== requested) return;
		liters=row?.liters ?? '';notes=row?.notes ?? '';editing=!!row;
		} catch(cause) { error=errorMessage(cause); } finally { if(ticket===requested) selecting=false; }
	}
	async function save(event: SubmitEvent) {
		event.preventDefault(); if(saving || selecting || !$currentFarm) return;saving=true;error='';message='';
		try {
			if(!validDate(date) || date > farmDate()) throw new Error('Elegí una fecha válida, no futura.');
			const amount=decimalValue(liters,true); if(amount > 999999.99) throw new Error('El máximo diario es 999,999.99 litros.');
			const existing=await db.daily_milk.where('farm').equals($currentFarm.id).filter((r) => r.date === date).first();
			await enqueue('daily_milk',{id:existing?.id ?? crypto.randomUUID(),farm:$currentFarm.id,date,liters:amount.toFixed(2),notes:notes.trim(),updated_at:new Date().toISOString()});
			editing=true;message='Producción guardada. El envío es automático. Podés seleccionar otro día o corregir el total de este día.';
		} catch(cause) { error=errorMessage(cause); } finally { saving=false; }
	}
</script>
<svelte:head><title>Producción diaria de leche · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6">
	<PageHeader title="Producción diaria de leche" eyebrow="El ordeño de la finca" description="Anotá en un solo registro todos los litros producidos durante el día, sin seleccionar cada animal." backHref="/operations" backLabel="Operaciones" />
	<Notice tone="error" message={error} /><Notice tone="success" message={message} />
	<div class="flex flex-wrap gap-3"><a href="/reports/milk" class="quiet-button">Ver reporte de producción</a><a href="/milking/individual" class="quiet-button">Registrar por animal (opcional)</a><button type="button" class="quiet-button" onclick={async () => { try { if($currentFarm) await exportMilkTotalsCsv($currentFarm.id); } catch(cause) { error=errorMessage(cause); } }}>Descargar totales CSV</button></div>
	{#if loading}<p class="empty-state">Cargando producción…</p>{:else}
	<form onsubmit={save} class="panel space-y-5 p-5 sm:p-6"><h2 class="section-title">{editing ? 'Actualizar total del día' : 'Registrar total del día'}</h2><fieldset disabled={saving || selecting} class="space-y-5"><div class="form-grid">
		<label class="field-label">Fecha de producción *<input class="field" type="date" bind:value={date} onchange={(event) => selectDay(event.currentTarget.value)} max={farmDate()} required /></label>
		<label class="field-label">Total de litros del día *<input class="field" inputmode="decimal" bind:value={liters} placeholder="Ej. 125.50" required /><span class="field-help">Incluí toda la producción del día. Podés registrar 0 si ese día no se produjo leche.</span></label>
	</div><label class="field-label">Observaciones<textarea class="field" bind:value={notes} maxlength="1000" placeholder="Incidencias del ordeño, cambios en la producción…"></textarea></label>
	<Notice message="Hay un solo total por fecha. Si lo corregís, se reemplaza el valor anterior. En los reportes, este total tiene prioridad sobre los registros por animal de ese día: no se suman dos veces." />
	<button class="action-button" type="submit">{saving ? 'Guardando…' : editing ? 'Actualizar producción del día' : 'Guardar producción del día'}</button></fieldset></form>
	<section class="panel space-y-4 p-5 sm:p-6"><h2 class="section-title">Últimos días registrados</h2><p class="field-help">Seleccioná una fecha para consultar o corregir su total. Se muestran hasta 60 días con registros.</p><ul class="divide-y">{#each history as row}<li class="flex flex-wrap items-center justify-between gap-3 py-4"><div><p class="font-semibold">{row.date} · {row.liters} L</p>{#if row.notes}<p class="field-help break-words">{row.notes}</p>{/if}<p class="field-help">{pending.includes(row.id) ? 'Pendiente de envío automático' : 'Confirmado por el servidor'}</p></div><button class="quiet-button" type="button" disabled={saving || selecting} onclick={() => selectDay(row.date)}>Consultar / editar</button></li>{:else}<li class="empty-state">Todavía no hay totales diarios. Registrá los litros producidos en la fecha seleccionada.</li>{/each}</ul></section>{/if}
</div>

<script lang="ts">
	import { db, type AnimalSale, type SaleExpense } from '$lib/db';
	import { enqueue, reviewFinancialPending } from '$lib/sync';
	import { currentFarm } from '$lib/stores';
	import { farmDate } from '$lib/dates';
	import { errorMessage } from '$lib/forms';
	import { moneyLabel } from '$lib/agreements';
	import { saleWithExpenses, validateSaleExpense } from '$lib/sales';
	import Notice from './Notice.svelte';
	let { sale, expenses, editing, onDone }: { sale: AnimalSale; expenses: SaleExpense[]; editing?: SaleExpense; onDone: () => void } = $props();
	let animal = $state(''), date = $state(farmDate()), concept = $state(''), amount = $state(''), paidBy = $state<'owner'|'partner'>('owner'), acceptLoss = $state(false);
	let saving = $state(false), error = $state(''), saved = $state(false), loaded = '';
	$effect(() => { if ((editing?.id ?? '') !== loaded) { loaded = editing?.id ?? ''; animal = editing?.animal ?? ''; date = editing?.date ?? farmDate(); concept = editing?.concept ?? ''; amount = editing?.amount ?? ''; paidBy = editing?.paid_by ?? 'owner'; saved = false; } });
	let signature = '';
	$effect(() => { const next = JSON.stringify([animal,date,concept,amount,paidBy,expenses]); if (signature !== next) { acceptLoss = false; signature = next; } });
	const line = $derived(sale.lines.find((r) => r.animal === animal));
	const draft = $derived<SaleExpense>({ id:editing?.id ?? 'preview',farm:sale.farm,sale:sale.id,animal,date,concept,amount,paid_by:paidBy,accept_loss:acceptLoss });
	const preview = $derived.by(() => {
		try { if (!line || !amount) return null; return saleWithExpenses($state.snapshot(sale),[...expenses.filter((e) => e.id !== editing?.id),draft]).lines.find((r) => r.animal === animal)?.settlement ?? null; } catch { return null; }
	});
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (saving || saved || $currentFarm?.role !== 'admin') return; saving = true; error = '';
		try {
			if (editing && await reviewFinancialPending('sale_expenses',editing.id)) { onDone(); return; }
			const data = validateSaleExpense({...$state.snapshot(draft),id:editing?.id ?? crypto.randomUUID()},$state.snapshot(sale),$state.snapshot(expenses));
			const animalRecord = await db.animals.get(animal);
			if (animalRecord?.birth_date && data.date < animalRecord.birth_date) throw new Error('El gasto no puede ser anterior al nacimiento del animal.');
			await enqueue('sale_expenses',{...data}); saved = true;
			if (editing) onDone();
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>
<section class="panel space-y-5 p-5 sm:p-6">
	<h2 class="section-title">{editing ? 'Corregir gasto pendiente' : 'Agregar gasto a esta venta'}</h2>
	<p class="field-help">Registrá el gasto que faltó. Se descuenta del animal seleccionado y actualiza su liquidación, incluso si el acuerdo ya estaba cerrado. Los cobros al comprador conservan sus importes.</p>
	<Notice tone="error" message={error} />
	{#if saved}<Notice tone="success" message="Gasto guardado. El envío es automático; su estado aparece en el historial de gastos posteriores." /><button type="button" class="quiet-button" onclick={() => { saved=false; concept=''; amount=''; acceptLoss=false; }}>Agregar otro gasto</button>{:else}
	<form onsubmit={save} class="space-y-4"><fieldset disabled={saving} class="space-y-4"><div class="form-grid">
		<label class="field-label">Animal del gasto *<select class="field" bind:value={animal} required><option value="">Seleccioná un animal</option>{#each sale.lines as row}<option value={row.animal}>{row.tag} · {row.name || 'Sin nombre'}</option>{/each}</select></label>
		<label class="field-label">Fecha del gasto *<input class="field" type="date" bind:value={date} max={farmDate()} required /></label>
		<label class="field-label">Concepto del gasto *<input class="field" bind:value={concept} maxlength="200" placeholder="Ej. Medicamentos, transporte…" required /></label>
		<label class="field-label">Importe del gasto *<input class="field" inputmode="decimal" bind:value={amount} required /><span class="field-help">Moneda de la venta: {sale.currency}</span></label>
		<label class="field-label">Quién pagó el gasto<select class="field" bind:value={paidBy}><option value="owner">Propietario</option>{#if line?.agreement}<option value="partner">Responsable de la otra finca</option>{/if}</select></label>
	</div>
	{#if preview}<div class="notice space-y-2"><p>Gastos actualizados: {moneyLabel(preview.expenses,sale.currency)}</p>{#if line?.kind === 'pasture'}<p>Reembolso al responsable: {moneyLabel(preview.partner_reimbursement,sale.currency)}</p>{:else}<p>Ganancia neta: {moneyLabel(preview.net_gain,sale.currency)}</p><p>Total propietario: {moneyLabel(preview.owner_total,sale.currency)}</p><p>Total responsable: {moneyLabel(preview.partner_total,sale.currency)}</p>{/if}</div>{/if}
	{#if Number(preview?.net_gain ?? 0) < 0}<label class="flex items-start gap-3 text-sm"><input type="checkbox" bind:checked={acceptLoss} />Confirmo el reparto de la pérdida mostrada según los porcentajes del acuerdo.</label>{/if}
	<button type="submit" class="action-button">{saving ? 'Guardando…' : editing ? 'Guardar corrección pendiente' : 'Guardar gasto posterior'}</button>
	{#if editing}<button type="button" class="quiet-button" onclick={onDone}>Volver</button>{/if}
	</fieldset></form>{/if}
</section>

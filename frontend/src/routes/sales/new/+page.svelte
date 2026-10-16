<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { Plus, Trash2 } from 'lucide-svelte';
	import { db, type Animal, type AnimalAgreement, type AnimalSale } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueue, reviewFinancialPending } from '$lib/sync';
	import { farmDate } from '$lib/dates';
	import { errorMessage } from '$lib/forms';
	import { moneyLabel } from '$lib/agreements';
	import { saleLinePreview, validateSale } from '$lib/sales';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	let draft = $state<AnimalSale>({ id: '', farm: '', buyer: '', buyer_phone: '', currency: 'NIO', date: farmDate(), notes: '', lines: [] });
	let animals = $state<Animal[]>([]), agreements = $state<AnimalAgreement[]>([]);
	let query = $state(''), error = $state(''), loading = $state(true), saving = $state(false);
	let unavailable = $state<string[]>([]);
	let editingPending = $state(false);
	const choices = $derived(animals.filter((a) => a.status === 'active' && !unavailable.includes(a.id) && !draft.lines.some((l) => l.animal === a.id) && `${a.tag} ${a.name}`.toLowerCase().includes(query.toLowerCase())).slice(0, 20));
	function agreementFor(id: string) { return agreements.find((a) => a.status === 'active' && a.animals.some((r) => r.animal === id)); }
	function preview(line: AnimalSale['lines'][number]) { try { return saleLinePreview(line, agreementFor(line.animal)); } catch { return null; } }
	const total = $derived(draft.lines.reduce((sum, line) => sum + Number(preview(line)?.value ?? 0), 0).toFixed(2));
	let previous = '';
	$effect(() => { const signature = JSON.stringify([draft.lines, draft.currency, draft.date]); if (signature !== previous) { draft.accept_loss = false; previous = signature; } });
	onMount(async () => {
		try {
			if (!$currentFarm || $currentFarm.role !== 'admin') return;
			draft.id = crypto.randomUUID(); draft.farm = $currentFarm.id;
			const pendingId = page.url.searchParams.get('pending');
			if (pendingId) {
				if (await reviewFinancialPending('sales',pendingId)) { await goto(`/sales/${pendingId}`); return; }
				const record = await db.sales.get(pendingId);
				if (!record || record.farm !== draft.farm || !(await db.outbox.toArray()).some((r) => r.collection === 'sales' && r.record_id === pendingId)) throw new Error('Esta venta ya no está pendiente. Volvé al historial.');
				draft = record; editingPending = true;
			}
			[animals, agreements] = await Promise.all([db.animals.where('farm').equals(draft.farm).toArray(), db.agreements.where('farm').equals(draft.farm).toArray()]);
			unavailable = (await db.sales.where('farm').equals(draft.farm).toArray()).filter((s) => s.id !== draft.id).flatMap((s) => s.lines.map((r) => r.animal));
			const id = page.url.searchParams.get('animal'); const animal = animals.find((a) => a.id === id && a.status === 'active' && !unavailable.includes(a.id)); if (animal) add(animal);
		} catch (cause) { error = errorMessage(cause); } finally { loading = false; }
	});
	function add(animal: Animal) {
		const agreement = agreementFor(animal.id);
		if (!draft.lines.length && agreement) draft.currency = agreement.currency;
		draft.lines.push({ animal: animal.id, tag: animal.tag, name: animal.name, weight_kg: '', price_per_kg: '', agreement: agreement?.id ?? null, agreement_version: agreement?.updated_at ?? null, expenses: [] });
	}
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (saving || $currentFarm?.role !== 'admin') return; saving = true; error = '';
		try {
			if (editingPending && await reviewFinancialPending('sales',draft.id)) { await goto(`/sales/${draft.id}`); return; }
			if ((await db.outbox.toArray()).some((r) => r.collection === 'animals' || r.collection === 'agreements')) throw new Error('Sincronizá los cambios pendientes del hato y acuerdos antes de registrar la venta.');
			const latestSales = await db.sales.where('farm').equals(draft.farm).toArray();
			if (latestSales.some((s) => s.id !== draft.id && s.lines.some((r) => draft.lines.some((l) => l.animal === r.animal)))) throw new Error('Uno de estos animales ya tiene una venta. Revisá el historial.');
			for (const line of draft.lines) { const animal = await db.animals.get(line.animal); if (!animal || animal.status !== 'active' || (animal.birth_date && draft.date < animal.birth_date)) throw new Error('Revisá el estado y nacimiento de los animales seleccionados.'); }
			const data = validateSale($state.snapshot(draft), $state.snapshot(agreements));
			await enqueue('sales', { ...data }); await goto(`/sales/${data.id}`);
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>
<svelte:head><title>Registrar venta · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6">
	<PageHeader title="Registrar venta" eyebrow="Salidas del hato" backHref="/sales" backLabel="Ventas y cobros" description="Vendé uno o varios animales y conservá el comprador, precio y liquidación de cada uno." />
	<Notice tone="error" message={error} />
	{#if $currentFarm?.role !== 'admin'}<Notice tone="warning" message="Las ventas y cobros requieren el rol de administrador." />{:else if loading}<p class="empty-state">Cargando hato…</p>{:else}
	<form onsubmit={save} class="space-y-6"><fieldset disabled={saving} class="space-y-6">
	<section class="panel space-y-5 p-5 sm:p-6"><h2 class="section-title">Comprador y fecha</h2><div class="form-grid">
		<label class="field-label">Comprador *<input class="field" bind:value={draft.buyer} maxlength="150" required /></label>
		<label class="field-label">Teléfono<input class="field" bind:value={draft.buyer_phone} maxlength="30" type="tel" /></label>
		<label class="field-label">Fecha de venta *<input type="date" class="field" bind:value={draft.date} max={farmDate()} required /></label>
		<label class="field-label">Moneda<select class="field" bind:value={draft.currency}><option value="NIO">Córdobas (NIO)</option><option value="USD">Dólares (USD)</option></select></label>
	</div><label class="field-label">Observaciones<textarea class="field" bind:value={draft.notes} maxlength="2000"></textarea></label></section>
	<section class="panel space-y-5 p-5 sm:p-6"><h2 class="section-title">Animales a vender · {draft.lines.length}</h2>
		<label class="field-label">Buscar por arete o nombre<input class="field" bind:value={query} placeholder="Buscar en el hato activo…" /></label>
		<ul class="max-h-52 divide-y overflow-y-auto rounded-xl border">{#each choices as animal}<li><button type="button" class="flex min-h-12 w-full items-center justify-between gap-3 p-3 text-left text-sm" onclick={() => add(animal)}><span>{animal.tag} · {animal.name || 'Sin nombre'}</span><Plus class="h-4 w-4 shrink-0" /></button></li>{:else}<li class="p-4 text-sm">No hay animales disponibles con esa búsqueda.</li>{/each}</ul>
		{#each draft.lines as line (line.animal)}{@const agreement = agreementFor(line.animal)}{@const result = preview(line)}
		<div class="form-section space-y-4"><div class="flex items-center justify-between gap-3"><h3 class="font-semibold">{line.tag} · {line.name || 'Sin nombre'}</h3><button type="button" class="p-2 text-red-700" aria-label="Quitar {line.tag}" onclick={() => draft.lines = draft.lines.filter((r) => r.animal !== line.animal)}><Trash2 class="h-4 w-4" /></button></div>
		{#if agreement}<p class="field-help">{agreement.title} · {agreement.partner_name} · {agreement.currency}{agreement.kind === 'weight_gain' ? ` · Peso inicial: ${agreement.animals.find((r) => r.animal === line.animal)?.initial_weight} kg` : ''}</p>{/if}
		<div class="form-grid"><label class="field-label">Peso de venta (kg) *<input class="field" inputmode="decimal" bind:value={line.weight_kg} required /></label><label class="field-label">Precio por kg *<input class="field" inputmode="decimal" bind:value={line.price_per_kg} required /></label></div>
		<p class="field-help">Usá el peso y precio pactados con el comprador. Los importes usan dos decimales.</p>
		{#if result}<p class="text-lg font-semibold">Venta: {moneyLabel(result.value,draft.currency)}</p>{/if}
		<h4 class="text-sm font-semibold">Gastos adicionales pagados de este animal</h4><p class="field-help">Incluí solamente gastos nuevos, que todavía no estén en el acuerdo. Los gastos comunes originales se reparten por igual entre todos sus animales.</p>
		{#each line.expenses as expense, index}<div class="rounded-xl border p-3 space-y-3"><label class="field-label">Concepto<input class="field" bind:value={expense.concept} maxlength="200" required /></label><div class="form-grid"><label class="field-label">Importe<input class="field" inputmode="decimal" bind:value={expense.amount} required /></label><label class="field-label">Quién pagó<select class="field" bind:value={expense.paid_by}><option value="owner">Propietario</option>{#if agreement}<option value="partner">Responsable de la otra finca</option>{/if}</select></label></div><button type="button" class="quiet-button" onclick={() => line.expenses.splice(index,1)}>Quitar gasto</button></div>{/each}
		<button type="button" class="quiet-button" onclick={() => line.expenses.push({ concept:'', amount:'', paid_by:'owner' })}><Plus class="h-4 w-4" />Agregar gasto</button>
		{#if result?.settlement}{@const s = result.settlement}<div class="notice space-y-2"><p>Gastos descontados: {moneyLabel(s.expenses,draft.currency)}</p>{#if agreement?.kind === 'pasture'}<p>A reembolsar al responsable: {moneyLabel(s.partner_reimbursement,draft.currency)}</p>{:else}<p>Ganancia neta a repartir: {moneyLabel(s.net_gain,draft.currency)}</p><p>Corresponde al propietario: <strong>{moneyLabel(s.owner_total,draft.currency)}</strong></p><p>Corresponde al responsable: <strong>{moneyLabel(s.partner_total,draft.currency)}</strong></p>{/if}</div>{/if}
		</div>{/each}
	</section>
	<section class="panel space-y-4 p-5 sm:p-6"><h2 class="section-title">Total de la venta: {moneyLabel(total,draft.currency)}</h2>
		<Notice message="Al confirmar el servidor, los animales salen del hato activo y se liquida solamente su parte del acuerdo. Los demás siguen en curso. Las condiciones y gastos originales del acuerdo quedan protegidos desde su primera venta; los nuevos gastos se agregan en las siguientes ventas. El cobro al comprador se registra después, en el detalle de la venta." />
		{#if draft.lines.some((r) => Number(preview(r)?.settlement?.net_gain ?? 0) < 0)}<label class="flex items-start gap-3 text-sm"><input type="checkbox" bind:checked={draft.accept_loss} />Confirmo el reparto de las pérdidas mostradas según los porcentajes del acuerdo.</label>{/if}
		<button class="action-button" type="submit" disabled={saving || !draft.lines.length}>{saving ? 'Guardando…' : 'Registrar venta'}</button>
	</section></fieldset></form>{/if}
</div>

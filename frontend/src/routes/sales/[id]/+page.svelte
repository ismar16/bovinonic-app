<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { liveQuery } from 'dexie';
	import { db, type AnimalSale, type SalePayment, type SaleExpense } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { syncNow, enqueue, reviewFinancialPending } from '$lib/sync';
	import { moneyLabel, units, decimal } from '$lib/agreements';
	import SaleExpenseForm from '$lib/components/SaleExpenseForm.svelte';
	import { saleReference, saleWithExpenses, paymentMethods } from '$lib/sales';
	import { farmDate } from '$lib/dates';
	import { errorMessage, validDate } from '$lib/forms';
	import { downloadCsv, toCsv } from '$lib/reports';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	let sale = $state<AnimalSale | undefined>(), payments = $state<SalePayment[]>([]), pendingIds = $state<string[]>([]);
	let loading = $state(true), error = $state(''), saving = $state(false), amount = $state(''), date = $state(farmDate()), method = $state<SalePayment['method']>('cash'), reference = $state('');
	let editingPayment = $state('');
	let expenses = $state<SaleExpense[]>([]), editingExpense = $state<SaleExpense | undefined>();
	const pending = $derived(!!sale && pendingIds.includes(sale.id));
	const paid = $derived(decimal(payments.reduce((sum,p) => sum + units(p.amount),0n)));
	const balance = $derived(decimal(units(sale?.total ?? '0') - units(paid)));
	onMount(() => {
		if ($currentFarm?.role !== 'admin') { loading = false; return; }
		const subscription = liveQuery(async () => ({ sale: await db.sales.get(page.params.id ?? ''), payments: await db.sale_payments.where('sale').equals(page.params.id ?? '').toArray(), expenses: await db.sale_expenses.where('sale').equals(page.params.id ?? '').toArray(), pending: (await db.outbox.toArray()).map((r) => r.record_id) })).subscribe({ next(data) { sale = data.sale?.farm === $currentFarm?.id ? saleWithExpenses(data.sale,data.expenses) : undefined; expenses = data.expenses; payments = data.payments.sort((a,b) => a.date.localeCompare(b.date)); pendingIds = data.pending; loading = false; }, error() { error = 'No se pudo leer la venta.'; loading = false; } });
		return () => subscription.unsubscribe();
	});
	async function savePayment(event: SubmitEvent) {
		event.preventDefault(); if (!sale || pending || saving) return; saving = true; error = '';
		try {
			if (editingPayment && await reviewFinancialPending('sale_payments',editingPayment)) { editingPayment = ''; amount = ''; reference = ''; return; }
			if (!validDate(date) || date < sale.date || date > farmDate()) throw new Error('La fecha del abono debe estar entre la venta y hoy.');
			const value = units(amount,1n,999999999999999999n);
			const latest = await db.sale_payments.where('sale').equals(sale.id).toArray();
			if (value + latest.filter((p) => p.id !== editingPayment).reduce((sum,p) => sum + units(p.amount),0n) > units(sale.total ?? '0')) throw new Error('El abono supera el saldo pendiente.');
			await enqueue('sale_payments', { id:editingPayment || crypto.randomUUID(), farm:sale.farm, sale:sale.id, date, amount:decimal(value), method, reference:reference.trim() }); editingPayment = ''; amount = ''; reference = '';
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
	async function reviewPayment(payment: SalePayment) {
		try {
			error = '';
			if (await reviewFinancialPending('sale_payments',payment.id)) return;
			editingPayment = payment.id; amount = payment.amount; date = payment.date; method = payment.method; reference = payment.reference;
		} catch (cause) { error = errorMessage(cause); }
	}
	async function reviewExpense(expense: SaleExpense) { try { error = ''; if (await reviewFinancialPending('sale_expenses',expense.id)) return; editingExpense = expense; } catch(cause) { error = errorMessage(cause); } }
	function exportCsv() {
		if (!sale) return;
		const rows: (string | number | null)[][] = [['Numero de venta',saleReference(sale)],['Estado',pending ? 'Pendiente de confirmación' : 'Confirmada'],['Fecha',sale.date],['Comprador',sale.buyer],['Teléfono',sale.buyer_phone],['Moneda',sale.currency],['Observaciones',sale.notes],['Total',sale.total ?? ''],['Cobrado',paid],['Saldo',balance]];
		for (const r of sale.lines) {
			rows.push(['Animal',r.tag],['Peso kg',r.weight_kg],['Precio kg',r.price_per_kg],['Importe',r.value ?? ''],['Acuerdo',r.agreement_title ?? ''],['Propietario',r.owner_name ?? ''],['Responsable',r.partner_name ?? ''],['Gastos totales',r.expenses_total ?? ''],['Ingreso menos gastos',r.net_after_expenses ?? '']);
			for (const e of [...r.allocated_expenses ?? [], ...r.expenses]) rows.push(['Gasto',`${e.concept} · ${e.paid_by === 'owner' ? 'Propietario' : 'Responsable'}`,e.amount]);
			if (r.original_settlement) for (const [k,v] of Object.entries(r.original_settlement)) if (typeof v === 'string') rows.push(['Liquidación original',labels[k] ?? k,v]);
			if (r.settlement) for (const [k,v] of Object.entries(r.settlement)) if (typeof v === 'string') rows.push(['Liquidación',labels[k] ?? k,v]);
		}
		for (const e of expenses) rows.push(['Gasto posterior',`${e.date} · ${e.concept} · ${e.paid_by === 'owner' ? 'Propietario' : 'Responsable'} · ${pendingIds.includes(e.id) ? 'Pendiente' : 'Confirmado'} · ${e.id}`,e.amount]);
		for (const p of payments) rows.push(['Abono',`${p.date} · ${paymentMethods[p.method]} · ${p.reference} · ${pendingIds.includes(p.id) ? 'Pendiente' : 'Confirmado'}`,p.amount]);
		downloadCsv(`venta-${sale.number ? saleReference(sale) : 'pendiente'}.csv`,toCsv(['Concepto','Detalle','Importe'],rows));
	}
	const labels: Record<string,string> = { expenses:'Gastos descontados',owner_paid:'Gastos pagados por el propietario',partner_paid:'Gastos pagados por el responsable',initial_value:'Valor inicial del propietario',gain_value:'Valor de ganancia de peso',net_gain:'Ganancia neta a repartir',owner_part:'Parte del propietario',partner_part:'Parte del responsable',owner_total:'Total del propietario',partner_total:'Total del responsable',partner_reimbursement:'Reembolso al responsable' };
</script>
<svelte:head><title>Detalle de venta · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6"><PageHeader title={sale ? `Venta a ${sale.buyer}` : 'Detalle de venta'} eyebrow="Ventas y cobros" backHref="/sales" backLabel="Todas las ventas" /><Notice tone="error" message={error} />
{#if $currentFarm?.role !== 'admin'}<Notice tone="warning" message="Las ventas y cobros requieren el rol de administrador." />{:else if loading}<p class="empty-state">Cargando venta…</p>{:else if !sale}<p class="empty-state">Venta no disponible. Sincronizá y volvé a intentar.</p>{:else}
<div class="flex flex-wrap items-center gap-3"><span class="status-pill {pending ? 'pending' : ''}">{pending ? 'Pendiente de confirmación' : 'Venta confirmada · Historial protegido'}</span><button type="button" class="quiet-button" onclick={exportCsv}>Descargar comprobante CSV</button></div>
{#if pending}<Notice tone="warning" message="La venta está guardada en este dispositivo. La salida del hato y liquidación se confirman al sincronizar. Si el servidor encuentra un conflicto, la operación completa queda pendiente y conserva los datos originales." /><button type="button" class="quiet-button" onclick={() => syncNow()}>Sincronizar ahora</button><a class="quiet-button" href="/sales/new?pending={sale.id}">Revisar y corregir pendiente</a>{/if}
<section class="panel space-y-5 p-5 sm:p-6"><h2 class="section-title">Comprador y resumen</h2><dl class="grid gap-4 sm:grid-cols-2"><div><dt class="field-help">Comprador</dt><dd>{sale.buyer}</dd></div><div><dt class="field-help">Fecha</dt><dd>{sale.date}</dd></div><div><dt class="field-help">Teléfono</dt><dd>{sale.buyer_phone || 'Sin registrar'}</dd></div><div><dt class="field-help">Número de venta</dt><dd class="mt-1 font-semibold tracking-wide text-[#24533f]">{pending ? 'Pendiente de confirmación' : saleReference(sale)}</dd></div></dl>{#if sale.notes}<p class="whitespace-pre-wrap break-words text-sm">{sale.notes}</p>{/if}<div class="grid gap-3 sm:grid-cols-3">{#each [['Total',sale.total ?? '0'],['Cobrado',paid],['Por cobrar',balance]] as [label,value]}<div class="form-section"><p class="field-help">{label}</p><p class="text-xl font-semibold">{moneyLabel(value,sale.currency)}</p></div>{/each}</div></section>
{#each sale.lines as line}<section class="panel space-y-4 p-5 sm:p-6"><h2 class="section-title"><a href="/animals/{line.animal}">{line.tag} · {line.name || 'Sin nombre'}</a></h2><p>{line.weight_kg} kg × {moneyLabel(line.price_per_kg,sale.currency)} = <strong>{moneyLabel(line.value,sale.currency)}</strong></p>
{#if !line.agreement}<p class="notice">Gastos registrados: {moneyLabel(line.expenses_total,sale.currency)} · Ingreso menos gastos: {moneyLabel(line.net_after_expenses,sale.currency)}</p>{/if}{#if line.agreement}<a class="back-link mb-0" href="/agreements/{line.agreement}">{line.agreement_title || 'Ver acuerdo'} · {line.partner_name}</a>{/if}
{#if line.settlement}<div class="grid gap-3 sm:grid-cols-2">{#each Object.entries(labels).filter(([key]) => key in line.settlement!) as [key,label]}<div class="form-section"><p class="field-help">{label}</p><p class="font-semibold">{moneyLabel(line.settlement[key as keyof typeof line.settlement] as string,sale.currency)}</p></div>{/each}</div><p class="field-help">Estos importes corresponden al reparto, no registran un pago entre las partes. Los abonos inferiores corresponden al cobro al comprador.</p>{/if}
{#if line.subsequent_expenses?.length}<p class="notice">Liquidación actualizada con gastos posteriores. El comprobante original y los cobros se conservan.</p>{/if}<ul class="divide-y text-sm">{#each [...line.allocated_expenses ?? [], ...line.expenses, ...line.subsequent_expenses ?? []] as expense}<li class="flex flex-wrap justify-between gap-3 py-3"><span>{expense.concept} · Pagó {expense.paid_by === 'owner' ? 'el propietario' : 'el responsable'}</span><strong>{moneyLabel(expense.amount,sale.currency)}</strong></li>{:else}<li class="field-help">Sin gastos descontados.</li>{/each}</ul></section>{/each}
{#if !pending}<SaleExpenseForm {sale} {expenses} editing={editingExpense} onDone={() => editingExpense = undefined} /><section class="panel space-y-4 p-5 sm:p-6"><h2 class="section-title">Historial de gastos posteriores</h2><p class="field-help">Cada gasto se conserva como un registro independiente. La liquidación muestra el resultado actualizado.</p><ul class="divide-y">{#each expenses as expense}<li class="space-y-2 py-4"><p class="text-sm font-semibold break-words">{expense.concept} · {moneyLabel(expense.amount,sale.currency)}</p><p class="field-help">{expense.date} · {sale.lines.find((r) => r.animal === expense.animal)?.tag} · Pagó {expense.paid_by === 'owner' ? 'el propietario' : 'el responsable'}</p><p class="field-help">{pendingIds.includes(expense.id) ? 'Gasto pendiente de confirmación · Cálculo provisional' : 'Gasto confirmado · Liquidación actualizada'}</p>{#if pendingIds.includes(expense.id)}<button class="quiet-button" type="button" onclick={() => reviewExpense(expense)}>Revisar gasto pendiente</button>{/if}</li>{:else}<li class="field-help">Sin gastos posteriores registrados.</li>{/each}</ul></section>{/if}<section class="panel space-y-5 p-5 sm:p-6"><h2 class="section-title">Cobros al comprador</h2><ul class="divide-y">{#each payments as payment}<li class="flex flex-wrap justify-between gap-3 py-4"><div><p class="text-sm">{payment.date} · {paymentMethods[payment.method]}</p><p class="field-help break-words">{payment.reference}</p><p class="field-help">{pendingIds.includes(payment.id) ? 'Abono pendiente de confirmación' : 'Abono confirmado'}</p></div><strong>{moneyLabel(payment.amount,sale.currency)}</strong>{#if pendingIds.includes(payment.id)}<button type="button" class="quiet-button" onclick={() => reviewPayment(payment)}>Revisar abono pendiente</button>{/if}</li>{:else}<li class="field-help">Todavía no hay abonos registrados.</li>{/each}</ul>
{#if !pending && (Number(balance) > 0 || editingPayment)}<form onsubmit={savePayment} class="form-section space-y-4"><h3 class="font-semibold">{editingPayment ? 'Corregir abono pendiente' : 'Registrar abono'}</h3><fieldset disabled={saving} class="space-y-4"><div class="form-grid"><label class="field-label">Importe *<input class="field" inputmode="decimal" bind:value={amount} required /></label><label class="field-label">Fecha *<input class="field" type="date" bind:value={date} min={sale.date} max={farmDate()} required /></label><label class="field-label">Medio de pago<select class="field" bind:value={method}>{#each Object.entries(paymentMethods) as [value,label]}<option {value}>{label}</option>{/each}</select></label><label class="field-label">Referencia<input class="field" bind:value={reference} maxlength="150" /></label></div><button type="submit" class="action-button">{saving ? 'Guardando…' : 'Registrar abono'}</button></fieldset></form>{/if}</section>{/if}</div>

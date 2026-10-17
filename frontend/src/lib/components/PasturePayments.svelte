<script lang="ts">
	import { onMount } from 'svelte';
	import { liveQuery } from 'dexie';
	import { db, type AnimalAgreement, type Animal, type PasturePayment } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueue, reviewFinancialPending, syncNow } from '$lib/sync';
	import { pull } from '$lib/api';
	import { moneyLabel, decimal, units } from '$lib/agreements';
	import { farmDate } from '$lib/dates';
	import { errorMessage } from '$lib/forms';
	import { eligibleRentAnimals, paymentAnimals, rentTotal, validatePasturePayment } from '$lib/pasture';
	import Notice from './Notice.svelte';
	let { agreement, pendingAgreement = false }: { agreement: AnimalAgreement; pendingAgreement?: boolean } = $props();
	let payments = $state<PasturePayment[]>([]), animals = $state<Animal[]>([]), pendingIds = $state<string[]>([]);
	let id = $state<string>(''), period = $state(''), date = $state(farmDate()), price = $state(''), notes = $state(''), selected = $state<string[]>([]);
	let show = $state(false), saving = $state(false), error = $state(''), message = $state(''), editing = $state(false), loading = $state(true);
	const eligible = $derived(eligibleRentAnimals(agreement,animals,period));
	const covered = $derived(new Set(payments.filter((p) => p.id !== id && p.period === period+'-01').flatMap(paymentAnimals)));
	const available = $derived(eligible.filter((a) => !covered.has(a.animal)));
	const confirmedTotal = $derived(decimal(payments.filter((p) => !pendingIds.includes(p.id)).reduce((sum,p) => sum+units(rentTotal(p)),0n)));
	const pendingTotal = $derived(decimal(payments.filter((p) => pendingIds.includes(p.id)).reduce((sum,p) => sum+units(rentTotal(p)),0n)));
	const preview = $derived.by(() => { try { return decimal(units(price,1n,999999999n)*BigInt(selected.length)); } catch { return null; } });
	onMount(() => {
		const subscription = liveQuery(async () => ({ payments: await db.pasture_payments.where('agreement').equals(agreement.id).toArray(), animals: await db.animals.where('farm').equals(agreement.farm).toArray(), pending: (await db.outbox.toArray()).filter((r) => r.collection === 'pasture_payments').map((r) => r.record_id) })).subscribe({ next(data) { payments = data.payments.filter((p) => p.farm === agreement.farm); animals = data.animals; pendingIds = data.pending; loading = false; }, error() { error = 'No se pudo leer el historial de mensualidades.'; loading = false; } });
		return () => subscription.unsubscribe();
	});
	function choosePeriod() { selected = available.map((a) => a.animal); }
	function start() {
		id = crypto.randomUUID(); editing = false; period = (agreement.end_date && agreement.end_date < farmDate() ? agreement.end_date : farmDate()).slice(0,7); date = farmDate(); price = ''; notes = ''; error = ''; message = ''; show = true; choosePeriod();
	}
	async function review(payment: PasturePayment) {
		if (saving) return; saving = true; error = ''; message = '';
		try {
			if (await reviewFinancialPending('pasture_payments',payment.id)) { show = false; message = 'El servidor ya confirmó este pago. Se recuperó su comprobante.'; await syncNow(); return; }
			const data = await pull(agreement.farm);
			await db.transaction('rw',[db.agreements,db.pasture_payments,db.animals,db.outbox],async () => {
				if ($currentFarm?.id !== agreement.farm) throw new Error('La finca cambió.');
				const outbox = await db.outbox.toArray();
				for (const table of ['agreements','pasture_payments','animals'] as const) {
					const pending = new Set(outbox.filter((r) => r.collection === table).map((r) => r.record_id));
					await db.table(table).bulkPut(((data[table] ?? []) as {id:string}[]).filter((r) => !pending.has(r.id)));
				}
			});
			const latest = await db.pasture_payments.where('agreement').equals(agreement.id).toArray();
			const occupied = new Set(latest.filter((p) => p.id !== payment.id && p.period === payment.period).flatMap(paymentAnimals));
			id = payment.id; period = payment.period.slice(0,7); date = payment.date; price = payment.price_per_animal; notes = payment.notes; selected = paymentAnimals(payment).filter((a) => !occupied.has(a)); editing = true; show = true;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (saving || pendingAgreement || $currentFarm?.role !== 'admin') return; saving = true; error = ''; message = '';
		try {
			if (editing && await reviewFinancialPending('pasture_payments',id)) { message = 'Este pago ya fue confirmado. Se conservó el comprobante.'; show = false; return; }
			if (selected.some((a) => !eligible.some((r) => r.animal === a))) throw new Error('Revisá los animales que corresponden a este período.');
			const draft = validatePasturePayment({ id, farm:agreement.farm, agreement:agreement.id, period:period+'-01', date, price_per_animal:price, notes, animal_ids:selected },agreement,payments,farmDate());
			await enqueue('pasture_payments',{...draft}); pendingIds = [...pendingIds,id]; show = false; message = 'Mensualidad guardada. Revisá su confirmación en el historial.';
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
	async function discard() {
		saving = true; error = '';
		try { const confirmed = await reviewFinancialPending('pasture_payments',id,true); show = false; message = confirmed ? 'El pago ya estaba confirmado y su comprobante se conservó.' : 'Se descartó el pendiente sin confirmar.'; }
		catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>
<section id="mensualidades" class="panel space-y-5 p-5 sm:p-6">
	<div class="flex flex-wrap items-center justify-between gap-3"><h2 class="section-title">Mensualidades del alquiler</h2><button class="action-button" type="button" disabled={saving || pendingAgreement || loading} onclick={start}>Registrar mensualidad</button></div>
	<p class="field-help">Registrá un pago ya realizado por el propietario de los animales a {agreement.partner_name}. Precio mensual por animal × animales seleccionados, sin prorrateo automático. No lo repitas en los gastos originales.</p>
	<div class="grid gap-3 sm:grid-cols-2"><div class="form-section"><p class="field-help">Alquiler pagado y confirmado</p><p class="text-xl font-semibold">{moneyLabel(confirmedTotal,agreement.currency)}</p></div><div class="form-section"><p class="field-help">Pendiente de confirmación</p><p class="text-xl font-semibold">{moneyLabel(pendingTotal,agreement.currency)}</p></div></div>
	<Notice tone="error" message={error} /><Notice tone="success" message={message} />
	{#if pendingAgreement}<Notice tone="warning" message="Sincronizá el acuerdo antes de registrar mensualidades." />{/if}
	{#if show}<form onsubmit={save} class="form-section space-y-5"><fieldset disabled={saving} class="space-y-4"><h3 class="section-title">{editing ? 'Revisar mensualidad pendiente' : 'Pago de mensualidad'}</h3><div class="form-grid"><label class="field-label">Mes que se paga *<input class="field" type="month" min={agreement.start_date.slice(0,7)} max={(agreement.end_date && agreement.end_date < farmDate() ? agreement.end_date : farmDate()).slice(0,7)} bind:value={period} onchange={choosePeriod} required /></label><label class="field-label">Fecha del pago *<input class="field" type="date" bind:value={date} max={farmDate()} required /></label><label class="field-label">Precio mensual por animal ({agreement.currency}) *<input class="field" inputmode="decimal" bind:value={price} placeholder="0.00" required /></label></div>
		<p class="field-help">{covered.size} animales ya tienen pago o pendiente en este mes. Se excluyen de una nueva mensualidad.</p><button class="quiet-button" type="button" onclick={choosePeriod}>Seleccionar todos los disponibles</button>
		<div class="max-h-72 overflow-y-auto rounded-xl border divide-y">{#each eligible as row}<label class="flex min-w-0 items-center gap-3 p-3"><input type="checkbox" value={row.animal} bind:group={selected} disabled={covered.has(row.animal)} /><span class="break-words">{row.tag} · {row.name || 'Sin nombre'}{covered.has(row.animal) ? ' · Ya registrado' : ''}</span></label>{:else}<p class="empty-state m-3">No hay animales disponibles para ese mes.</p>{/each}</div>
		<p class="notice font-semibold">{selected.length} animales × {price ? moneyLabel(preview ? decimal(units(price)) : '0',agreement.currency) : 'precio por animal'} = {preview ? moneyLabel(preview,agreement.currency) : '—'}</p>
		<label class="field-label">Observaciones<textarea class="field" maxlength="500" bind:value={notes}></textarea></label></fieldset>
		<div class="form-actions"><button class="action-button" disabled={saving || !selected.length || !preview}>{saving ? 'Guardando…' : 'Registrar pago realizado'}</button><button class="quiet-button" type="button" disabled={saving} onclick={() => show = false}>Cerrar formulario</button>{#if editing}<button class="quiet-button" type="button" disabled={saving} onclick={discard}>Descartar pendiente sin confirmar</button>{/if}</div></form>{/if}
	<div class="divide-y">{#each [...payments].sort((a,b) => b.period.localeCompare(a.period) || b.date.localeCompare(a.date)) as payment}<article class="space-y-3 py-4"><div class="flex flex-wrap justify-between gap-3"><div><h3 class="font-semibold">Mensualidad {payment.period.slice(0,7)}</h3><p class="field-help">Pago: {payment.date} · A {payment.recipient ?? agreement.partner_name}</p></div><span class="status-pill">{pendingIds.includes(payment.id) ? 'Pendiente de confirmación' : 'Pago confirmado'}</span></div><p>{paymentAnimals(payment).length} animales × {moneyLabel(payment.price_per_animal,agreement.currency)} = <strong>{moneyLabel(rentTotal(payment),agreement.currency)}</strong></p><details><summary class="cursor-pointer text-sm font-semibold">Ver animales incluidos</summary><p class="mt-2 break-words field-help">{paymentAnimals(payment).map((id) => payment.animals?.find((r) => r.animal === id)?.tag ?? agreement.animals.find((r) => r.animal === id)?.tag ?? 'Animal').join(', ')}</p></details>{#if payment.notes}<p class="field-help break-words">{payment.notes}</p>{/if}{#if pendingIds.includes(payment.id)}<button class="quiet-button" type="button" disabled={saving} onclick={() => review(payment)}>Revisar pendiente</button>{/if}</article>{:else}<p class="empty-state">{loading ? 'Cargando mensualidades…' : 'Todavía no hay mensualidades registradas.'}</p>{/each}</div>
</section>

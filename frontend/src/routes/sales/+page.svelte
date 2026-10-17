<script lang="ts">
	import { onMount } from 'svelte';
	import { liveQuery } from 'dexie';
	import { Plus, ArrowUpRight } from 'lucide-svelte';
	import { db, type AnimalSale, type SalePayment } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { saleReference } from '$lib/sales';
	import { moneyLabel } from '$lib/agreements';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	let sales = $state<AnimalSale[]>([]), payments = $state<SalePayment[]>([]), pending = $state<string[]>([]);
	let query = $state(''), filter = $state(''), error = $state(''), loading = $state(true);
	function balance(sale: AnimalSale) { return (Number(sale.total ?? 0) - payments.filter((p) => p.sale === sale.id).reduce((sum,p) => sum + Number(p.amount),0)).toFixed(2); }
	const filtered = $derived(sales.filter((s) => `${saleReference(s)} ${s.buyer} ${s.lines.map((r) => r.tag).join(' ')}`.toLowerCase().includes(query.toLowerCase()) && (!filter || (filter === 'pending' ? Number(balance(s)) > 0 : Number(balance(s)) === 0))));
	onMount(() => {
		if ($currentFarm?.role !== 'admin') { loading = false; return; }
		const subscription = liveQuery(async () => ({ sales: await db.sales.where('farm').equals($currentFarm!.id).toArray(), payments: await db.sale_payments.where('farm').equals($currentFarm!.id).toArray(), pending: (await db.outbox.toArray()).map((r) => r.record_id) })).subscribe({ next(data) { sales = data.sales.sort((a,b) => b.date.localeCompare(a.date) || (b.updated_at ?? '').localeCompare(a.updated_at ?? '')); payments = data.payments; pending = data.pending; loading = false; }, error() { error = 'No se pudieron leer las ventas.'; loading = false; } });
		return () => subscription.unsubscribe();
	});
</script>
<svelte:head><title>Ventas y cobros · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6"><PageHeader title="Ventas y cobros" eyebrow="Comercialización del hato" description="Consultá qué animales vendiste, sus liquidaciones y el saldo de cada comprador." />
<Notice tone="error" message={error} />
{#if $currentFarm?.role !== 'admin'}<Notice tone="warning" message="Las ventas y cobros requieren el rol de administrador." />{:else}
<div class="flex flex-wrap gap-3"><a href="/sales/new" class="action-button"><Plus class="h-4 w-4" />Registrar venta</a><a href="/agreements" class="quiet-button">Acuerdos y estadías</a></div>
<section class="panel space-y-4 p-5"><div class="form-grid"><label class="field-label">Buscar número de venta, comprador o arete<input class="field" bind:value={query} placeholder="Buscar ventas…" /></label><label class="field-label">Cobro<select class="field" bind:value={filter}><option value="">Todos</option><option value="pending">Con saldo pendiente</option><option value="paid">Pagadas</option></select></label></div><p class="field-help">{filtered.length} ventas · Las monedas se muestran por separado. Los abonos pendientes de envío se incluyen en el saldo local.</p></section>
<div class="space-y-3">{#if loading}<p class="empty-state">Cargando ventas…</p>{:else}{#each filtered as sale}<a href="/sales/{sale.id}" class="panel flex flex-wrap items-center justify-between gap-4 p-5"><div class="min-w-0"><p class="eyebrow mb-2">{pending.includes(sale.id) ? 'Pendiente de confirmación' : saleReference(sale)}</p><p class="font-semibold break-words">{sale.buyer}</p><p class="field-help">{sale.date} · {sale.lines.length} animales · {sale.lines.map((r) => r.tag).join(', ')}</p><p class="field-help">{pending.includes(sale.id) ? 'Pendiente de confirmación' : 'Venta confirmada'}</p></div><div><p class="font-semibold">{moneyLabel(sale.total,sale.currency)}</p><p class="field-help">Por cobrar: {moneyLabel(balance(sale),sale.currency)}</p></div><ArrowUpRight class="h-5 w-5" /></a>{:else}<p class="empty-state">No hay ventas con estos filtros. Registrá la primera venta para comenzar.</p>{/each}{/if}</div>{/if}</div>

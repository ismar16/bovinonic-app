<script lang="ts">
	import { onMount } from 'svelte';
	import { liveQuery } from 'dexie';
	import { Plus, ArrowUpRight, Handshake } from 'lucide-svelte';
	import { db, type AnimalAgreement } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { agreementKinds } from '$lib/agreements';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Notice from '$lib/components/Notice.svelte';
	let agreements = $state<AnimalAgreement[]>([]); let pending = $state<string[]>([]);
	let query = $state(''); let status = $state('active'); let loading = $state(true); let error = $state('');
	const filtered = $derived(agreements.filter((a) => (!status || a.status === status) && `${a.title} ${a.partner_name} ${a.external_farm} ${a.animals.map((r) => r.tag).join(' ')}`.toLowerCase().includes(query.trim().toLowerCase())).sort((a,b) => b.start_date.localeCompare(a.start_date)));
	onMount(() => {
		const farm = $currentFarm;
		if (!farm || farm.role !== 'admin') { loading = false; return; }
		const subscription = liveQuery(async () => ({ records: await db.agreements.where('farm').equals(farm.id).toArray(), pending: (await db.outbox.toArray()).filter((r) => r.collection === 'agreements').map((r) => r.record_id) })).subscribe({ next(data) { agreements = data.records; pending = data.pending; loading = false; }, error() { error = 'No se pudieron leer los acuerdos de este dispositivo.'; loading = false; } });
		return () => subscription.unsubscribe();
	});
</script>
<svelte:head><title>Acuerdos y otras fincas · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6">
	<PageHeader title="Acuerdos y otras fincas" eyebrow="Propiedad y manejo" description="Tus animales siguen siendo tuyos aunque estén al cuidado de otra persona. Controlá entregas, pesos, gastos y liquidaciones." backHref="/herd" backLabel="Volver al hato" />
	{#if $currentFarm?.role !== 'admin'}<Notice tone="warning" message="Los acuerdos y sus liquidaciones están disponibles para administradores." />{:else}
	<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">{#each [{label:'Acuerdos en curso',value:agreements.filter((a) => a.status === 'active').length},{label:'Animales en otras fincas',value:new Set(agreements.filter((a) => a.status === 'active').flatMap((a) => a.animals.filter((r) => !a.sale_receipts?.some((s) => s.animals.includes(r.animal))).map((r) => r.animal))).size},{label:'Acuerdos liquidados',value:agreements.filter((a) => a.status === 'settled').length}] as item}<div class="panel p-4"><p class="eyebrow">{item.label}</p><p class="stat-value mt-2">{loading ? '—' : item.value}</p></div>{/each}</div>
	<div class="flex flex-wrap gap-3"><label class="field-label min-w-40 flex-1">Buscar acuerdo<input class="field" bind:value={query} placeholder="Persona, finca o arete…" /></label><label class="field-label">Estado<select class="field" bind:value={status}><option value="active">En curso</option><option value="settled">Liquidados</option><option value="">Todos</option></select></label><a class="action-button self-end" href="/agreements/new"><Plus class="h-4 w-4" />Nuevo acuerdo</a></div>
	<Notice tone="error" message={error} />
	<div class="grid gap-4 lg:grid-cols-2">{#each filtered as agreement (agreement.id)}<a class="panel space-y-4 p-5 sm:p-6" href="/agreements/{agreement.id}"><div class="flex items-center justify-between gap-3"><Handshake class="h-6 w-6 text-[#8ba075]" /><span class="status-pill {agreement.status === 'active' ? '' : 'historical'}">{agreement.status === 'active' ? 'En curso' : 'Liquidado'}</span></div><h2 class="section-title break-words">{agreement.title}</h2><p class="text-sm text-[#788970]">{agreementKinds[agreement.kind]}</p><dl class="grid grid-cols-2 gap-4 text-sm"><div><dt class="field-help">Responsable</dt><dd class="break-words">{agreement.partner_name}</dd></div><div><dt class="field-help">Finca de destino</dt><dd class="break-words">{agreement.external_farm}</dd></div></dl><div class="flex flex-wrap items-center justify-between gap-2 text-xs"><span>{agreement.animals.length} animales · Desde {agreement.start_date}</span><ArrowUpRight class="h-4 w-4" /></div>{#if pending.includes(agreement.id)}<p class="text-xs text-amber-700">Pendiente de envío automático</p>{/if}</a>{:else}<p class="empty-state col-span-full">{loading ? 'Cargando acuerdos…' : agreements.length ? 'No hay acuerdos con estos filtros.' : 'Creá un acuerdo para registrar animales a medias o en pasto alquilado.'}</p>{/each}</div>
	{/if}
</div>

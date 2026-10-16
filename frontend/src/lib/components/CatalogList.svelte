<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { liveQuery } from 'dexie';
	import { Plus, Pencil, Search } from 'lucide-svelte';
	import { db, type Owner } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { catalogConfig, catalogKind, type CatalogRecord } from '$lib/catalogs';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	const kind = $derived(catalogKind(page.params.collection));
	const config = $derived(kind ? catalogConfig[kind] : null);
	let rows = $state<CatalogRecord[]>([]); let owners = $state<Owner[]>([]); let pending = $state<string[]>([]);
	let query = $state(''); let loading = $state(true); let error = $state('');
	const filtered = $derived(rows.filter((row) => `${row.name ?? row.code} ${row.phone ?? ''} ${row.id_number ?? ''}`.toLowerCase().includes(query.trim().toLowerCase())).sort((a,b) => (a.name ?? a.code ?? '').localeCompare(b.name ?? b.code ?? '', 'es')));
	onMount(() => {
		const farm = $currentFarm; const collection = kind;
		if (!farm || !collection) { loading = false; return; }
		const subscription = liveQuery(async () => ({ rows: await db[collection].where('farm').equals(farm.id).toArray(), owners: await db.owners.where('farm').equals(farm.id).toArray(), pending: (await db.outbox.toArray()).filter((r) => r.collection === collection).map((r) => r.record_id) })).subscribe({ next(data) { rows = data.rows; owners = data.owners; pending = data.pending; loading = false; }, error() { error = 'No se pudo leer este catálogo.'; loading = false; } });
		return () => subscription.unsubscribe();
	});
</script>
<svelte:head><title>{config?.title ?? 'Catálogo'} · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-5">
	<PageHeader title={config?.title ?? 'Catálogo no encontrado'} description={config?.description} eyebrow="Catálogos de la finca" backHref="/catalogs" backLabel="Todos los catálogos" />
	{#if config && kind}
		<div class="flex flex-wrap gap-3"><label class="relative min-w-40 flex-1"><Search class="absolute left-3 top-3.5 h-4 w-4 text-[#95a287]" /><input class="field pl-10" bind:value={query} aria-label="Buscar en {config.title.toLowerCase()}" placeholder="Buscar…" /></label>{#if $currentFarm?.role === 'admin'}<a href="/catalogs/{kind}/new" class="action-button"><Plus class="h-4 w-4" />Agregar {config.singular}</a>{/if}</div>
		<Notice tone="error" message={error} />
		<section class="panel overflow-hidden"><div class="border-b px-5 py-4 text-xs text-[#7f8f72]">{filtered.length} de {rows.length} registros</div><ul class="divide-y">{#each filtered as row (row.id)}<li class="flex flex-wrap items-center gap-3 px-5 py-4"><div class="min-w-0 flex-1"><p class="break-words text-sm font-semibold">{row.name ?? row.code}</p>{#if kind === 'owners'}<p class="mt-1 text-xs text-[#849477]">Identificación: {row.id_number || 'Sin registrar'} · Teléfono: {row.phone || 'Sin registrar'}</p>{:else if kind === 'brands'}<p class="mt-1 text-xs text-[#849477]">Titular: {owners.find((o) => o.id === row.title_owner)?.name ?? 'Sin asignar'}</p>{/if}{#if pending.includes(row.id)}<span class="mt-2 inline-block text-xs text-amber-700">Pendiente de envío</span>{/if}</div>{#if $currentFarm?.role === 'admin'}<a href="/catalogs/{kind}/{row.id}/edit" class="quiet-button" aria-label="Editar {row.name ?? row.code}"><Pencil class="h-3.5 w-3.5" />Editar</a>{/if}</li>{:else}<li class="empty-state m-5">{loading ? 'Cargando registros…' : rows.length ? 'No hay coincidencias con esa búsqueda.' : 'Este catálogo todavía no tiene registros.'}</li>{/each}</ul></section>
	{/if}
</div>

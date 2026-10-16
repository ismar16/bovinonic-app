<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { liveQuery } from 'dexie';
	import { Plus, Layers, ArrowUpRight, Pencil } from 'lucide-svelte';
	import { db, type AnimalLot, type Animal } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	let { detail = false }: { detail?: boolean } = $props();
	let lots = $state<AnimalLot[]>([]); let animals = $state<Animal[]>([]); let loading = $state(true); let error = $state(''); let query = $state('');
	const lot = $derived(lots.find((row) => row.id === page.params.id));
	const members = $derived(animals.filter((a) => a.lot === lot?.id && `${a.tag} ${a.name}`.toLowerCase().includes(query.trim().toLowerCase())));
	const canEdit = $derived(['admin','technician'].includes($currentFarm?.role ?? ''));
	onMount(() => {
		const farm = $currentFarm; if (!farm) { loading = false; return; }
		const subscription = liveQuery(async () => ({ lots: await db.lots.where('farm').equals(farm.id).toArray(), animals: await db.animals.where('farm').equals(farm.id).toArray() })).subscribe({ next(rows) { lots = rows.lots; animals = rows.animals; loading = false; }, error() { error = 'No se pudieron leer los lotes.'; loading = false; } });
		return () => subscription.unsubscribe();
	});
</script>
<svelte:head><title>{detail ? lot?.name ?? 'Lote' : 'Lotes de animales'} · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-5"><PageHeader title={detail ? lot?.name ?? 'Lote de animales' : 'Lotes de animales'} eyebrow="Manejo del hato" description={detail ? lot?.description || 'Animales que forman este grupo de manejo.' : 'Organizá grupos de animales, revisá su composición y registrá varios nuevos a la vez.'} backHref={detail ? '/lots' : '/herd'} backLabel={detail ? 'Todos los lotes' : 'Volver al hato'} />
	<Notice tone="error" message={error} />
	{#if loading}<p class="empty-state">Cargando lotes…</p>{:else if detail && !lot}<p class="empty-state">Este lote no está disponible en la finca actual. Sincronizá los datos y volvé a intentar.</p>{:else}
		{#if canEdit}<div class="flex flex-wrap gap-2">{#if detail}<a href="/lots/{lot?.id}/edit" class="action-button"><Pencil class="h-4 w-4" />Editar lote y seleccionar animales</a><a href="/animals/bulk?lot={lot?.id}" class="quiet-button"><Plus class="h-4 w-4" />Registrar varios animales nuevos</a>{:else}<a href="/lots/new" class="action-button"><Plus class="h-4 w-4" />Crear lote</a><a href="/animals/bulk" class="quiet-button">Ingreso de varios animales</a>{/if}</div>{/if}
		{#if detail}<label class="field-label">Buscar dentro del lote<input class="field" bind:value={query} placeholder="Arete o nombre…" /></label><section class="panel overflow-hidden"><p class="border-b px-5 py-4 text-xs text-[#819374]">{members.length} animales · El lote no determina el potrero</p><ul class="divide-y">{#each members as animal}<li><a href="/animals/{animal.id}" class="flex items-center justify-between gap-3 px-5 py-4"><span><span class="block text-sm font-semibold">{animal.tag}</span><span class="text-xs text-[#819374]">{animal.name || 'Sin nombre'}</span></span><span class="status-pill {animal.status !== 'active' ? 'historical' : ''}">{animal.status === 'active' ? 'Activo' : 'Inactivo'}</span><ArrowUpRight class="h-4 w-4" /></a></li>{:else}<li class="empty-state m-5">No hay animales que mostrar. Editá el lote para seleccionar animales existentes o registrá varios nuevos.</li>{/each}</ul></section>
		{:else}<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{#each lots.filter((lot) => lot.name.toLowerCase().includes(query.toLowerCase())) as row}<a href="/lots/{row.id}" class="panel p-6"><Layers class="mb-5 h-6 w-6 text-[#92a87b]" /><h2 class="section-title">{row.name}</h2><p class="mt-2 text-sm leading-6 text-[#839573]">{row.description || 'Sin descripción'}</p><span class="status-pill mt-5">{animals.filter((a) => a.lot === row.id).length} animales</span></a>{:else}<p class="empty-state col-span-full">Todavía no hay lotes. Creá uno y elegí los animales que lo componen.</p>{/each}</div>{/if}
	{/if}
</div>

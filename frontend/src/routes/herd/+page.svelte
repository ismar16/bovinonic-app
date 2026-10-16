<script lang="ts">
	import CattleMark from '$lib/components/CattleMark.svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/state';
    import { onMount } from 'svelte';
    import { liveQuery } from 'dexie';
    import { Beef, Plus, Search, ArrowUpRight, Pencil, Download, SlidersHorizontal, X } from 'lucide-svelte';
    import { db, type Animal, type Paddock } from '$lib/db';
    import { currentFarm } from '$lib/stores';
    import { exportAnimalsCsv } from '$lib/reports';

    const categories: Record<string, string> = { calf: 'Ternero/a', heifer: 'Novillo/a', cow_lactating: 'Vaca en ordeño', cow_dry: 'Vaca seca', bull: 'Toro reproductor' };
    const statuses: Record<string, string> = { active: 'Activo', sold: 'Vendido', dead: 'Muerto', culled: 'Descarte' };
    let query = $state('');
    let animals = $state<Animal[]>([]);
    let paddocks = $state<Paddock[]>([]);
    let pending = $state<string[]>([]);
    let ready = $state(false);
    let category = $state('');
    let paddock = $state('');
    let status = $state('active');
    let sort = $state('tag');
    let error = $state('');
    let showFilters = $state(false);
    const canEdit = $derived(['admin', 'technician'].includes($currentFarm?.role ?? ''));
    $effect(() => { query = page.url.searchParams.get('q') ?? ''; });
    onMount(() => {
        const farm = $currentFarm;
        if (!farm) { void goto('/'); return; }
        const subscription = liveQuery(async () => ({
            animals: await db.animals.where('farm').equals(farm.id).toArray(),
            paddocks: await db.paddocks.where('farm').equals(farm.id).toArray(),
            pending: (await db.outbox.toArray()).filter((r) => r.collection === 'animals').map((r) => r.record_id)
        })).subscribe({ next(data) { animals = data.animals; paddocks = data.paddocks; pending = data.pending; ready = true; }, error() { error = 'No pudimos leer el hato en este dispositivo.'; } });
        return () => subscription.unsubscribe();
    });
    const filtered = $derived(animals.filter((a) => {
        const term = query.trim().toLowerCase();
        return (!term || `${a.tag} ${a.name}`.toLowerCase().includes(term)) && (!category || a.category === category) && (!paddock || a.paddock === paddock) && (!status || a.status === status);
    }).sort((a, b) => sort === 'recent' ? (b.updated_at ?? '').localeCompare(a.updated_at ?? '') : sort === 'name' ? a.name.localeCompare(b.name, 'es') : a.tag.localeCompare(b.tag, 'es', { numeric: true })));
    const active = $derived(animals.filter((a) => a.status === 'active').length);
    const lactating = $derived(animals.filter((a) => a.status === 'active' && a.category === 'cow_lactating').length);
    function clearFilters() { query = ''; category = ''; paddock = ''; status = 'active'; }
</script>

<svelte:head><title>Mi hato · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6">
    <header class="flex flex-wrap items-end justify-between gap-4">
        <div><p class="eyebrow">Inventario ganadero</p><h1 class="page-title mt-2">Conocé tu hato.</h1><p class="page-description">Buscá un animal, revisá su historia y mantené sus datos al día.</p></div>
        <div class="flex gap-2"><button type="button" class="quiet-button" onclick={() => $currentFarm && exportAnimalsCsv($currentFarm.id)}><Download class="h-4 w-4" /> Exportar hato</button>{#if canEdit}<a href="/animals/new" class="action-button"><Plus class="h-4 w-4" /> Nuevo animal</a>{/if}</div>
    </header>
    <div class="grid grid-cols-3 gap-3">
        {#each [{ label: 'Animales activos', value: active }, { label: 'Vacas en ordeño', value: lactating }, { label: 'Cambios por enviar', value: pending.length }] as stat}
            <div class="panel p-4 sm:p-5"><p class="text-[10px] font-semibold uppercase tracking-wider text-[#87917f]">{stat.label}</p><p class="mt-2 font-serif text-3xl text-[#254634]">{ready ? stat.value : '—'}</p></div>
        {/each}
    </div>
    <section class="panel overflow-hidden" aria-label="Listado del hato">
        <div class="space-y-4 border-b p-4 sm:p-5">
            <div class="flex flex-wrap items-center gap-3">
                <label class="relative min-w-40 flex-1"><Search class="absolute left-3 top-3.5 h-4 w-4 text-[#8b9685]" /><input bind:value={query} aria-label="Buscar arete o nombre" placeholder="Buscar por arete o nombre…" class="field pl-10" /></label>
                <select bind:value={sort} aria-label="Ordenar animales" class="field hidden w-auto sm:block"><option value="tag">Ordenar por arete</option><option value="name">Ordenar por nombre</option><option value="recent">Cambios recientes</option></select>
                <button type="button" class="quiet-button mobile-filters sm:hidden" aria-expanded={showFilters} onclick={() => showFilters = !showFilters}><SlidersHorizontal class="h-4 w-4" /> Filtros</button>
            </div>
            <div class="flex-wrap items-center gap-2 {showFilters ? 'flex' : 'hidden sm:flex'}">
                <SlidersHorizontal class="mr-1 h-4 w-4 text-[#8b9685]" />
                <select bind:value={category} aria-label="Filtrar por categoría" class="field w-auto flex-1 sm:flex-none"><option value="">Todas las categorías</option>{#each Object.entries(categories) as [key, label]}<option value={key}>{label}</option>{/each}</select>
                <select bind:value={paddock} aria-label="Filtrar por potrero" class="field w-auto flex-1 sm:flex-none"><option value="">Todos los potreros</option>{#each paddocks as p}<option value={p.id}>{p.name}</option>{/each}</select>
                <select bind:value={status} aria-label="Filtrar por estado" class="field w-auto flex-1 sm:flex-none"><option value="">Todos los estados</option>{#each Object.entries(statuses) as [key, label]}<option value={key}>{label}</option>{/each}</select>
                {#if query || category || paddock || status !== 'active'}<button type="button" class="quiet-button border-0" onclick={clearFilters}><X class="h-3 w-3" /> Limpiar</button>{/if}
            </div>
        </div>
        {#if error}<p role="alert" class="p-6 text-red-700">{error}</p>{:else if !ready}<p class="p-10 text-center text-sm text-[#7b8577]">Cargando el hato…</p>{:else}
            <div class="hidden grid-cols-[2fr_1.3fr_1fr_1fr_120px] gap-4 border-b bg-[#fafbf7] px-6 py-3 text-[10px] font-semibold uppercase tracking-widest text-[#8d9586] lg:grid"><span>Animal</span><span>Categoría</span><span>Potrero</span><span>Estado</span><span class="text-right">Acciones</span></div>
            <ul class="divide-y divide-[#edf0e7]">
                {#each filtered as animal (animal.id)}
                    <li class="grid grid-cols-[1fr_auto] items-center gap-3 px-4 py-4 transition-colors hover:bg-[#fafbf7] sm:px-6 lg:grid-cols-[2fr_1.3fr_1fr_1fr_120px] lg:gap-4">
                        <a href="/animals/{animal.id}" class="flex min-w-0 items-center gap-3"><span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#eef1e7] text-[#7d916c]"><CattleMark class="h-5 w-5" /></span><span class="min-w-0"><span class="block truncate text-sm font-bold text-[#284a35]">{animal.tag}</span><span class="block truncate text-xs text-[#7c8675]">{animal.name || 'Sin nombre'} · {animal.sex === 'H' ? 'Hembra' : 'Macho'}</span></span></a>
                        <span class="hidden text-xs text-[#697761] lg:block">{categories[animal.category] ?? animal.category}</span>
                        <span class="hidden text-xs text-[#697761] lg:block">{paddocks.find((p) => p.id === animal.paddock)?.name ?? 'Sin asignar'}</span>
                        <div class="flex flex-col items-end gap-1 lg:items-start"><span class="status-pill {animal.status !== 'active' ? 'historical' : ''}">{statuses[animal.status]}</span>{#if pending.includes(animal.id)}<span class="text-[10px] text-amber-700">Pendiente de envío</span>{/if}</div>
                        <div class="col-span-2 flex items-center justify-end gap-2 lg:col-span-1">{#if canEdit}<a href="/animals/{animal.id}/edit" aria-label="Editar {animal.tag}" class="rounded-lg p-2 text-[#8a957f] hover:bg-[#edf2e7]"><Pencil class="h-4 w-4" /></a>{/if}<a href="/animals/{animal.id}" class="flex items-center gap-1 whitespace-nowrap text-xs font-semibold text-[#31583c]">Ver ficha <ArrowUpRight class="h-3.5 w-3.5" /></a></div>
                    </li>
                {:else}<li class="px-6 py-14 text-center"><CattleMark class="mx-auto h-8 w-8 text-[#adb89b]" /><p class="mt-3 font-serif text-xl text-[#40533c]">{animals.length ? 'No encontramos coincidencias' : 'El hato empieza aquí'}</p><p class="mt-2 text-sm text-[#8a927f]">{animals.length ? 'Probá otro nombre, arete o filtro.' : 'Registrá tu primer animal o sincronizá los datos de la finca.'}</p>{#if animals.length}<button class="quiet-button mt-4" onclick={clearFilters}>Restablecer filtros</button>{:else if canEdit}<a href="/animals/new" class="action-button mt-4">Registrar primer animal</a>{/if}</li>{/each}
            </ul>
            <div class="border-t bg-[#fafbf7] px-6 py-3 text-xs text-[#89917f]">{filtered.length} de {animals.length} animales · Datos guardados en este dispositivo</div>
        {/if}
    </section>
</div>

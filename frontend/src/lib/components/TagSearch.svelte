<script lang="ts">
    import { onMount } from 'svelte';
    import { liveQuery } from 'dexie';
    import { Search, ArrowUpRight } from 'lucide-svelte';
    import { db, type Animal } from '$lib/db';
    import { currentFarm } from '$lib/stores';
    import Notice from './Notice.svelte';
    let { onSelect, filterStatus = 'active', category = null, sex = null, label = 'Buscar animal', excludeId }: {
        onSelect: (animal: Animal) => void; filterStatus?: string | null; category?: string | null;
        sex?: 'M' | 'H' | null; label?: string; excludeId?: string;
    } = $props();
    let query = $state('');
    let animals = $state<Animal[]>([]);
    let ready = $state(false);
    let error = $state('');
    function normalize(value: string) { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); }
    const matches = $derived(animals.filter((animal) => animal.id !== excludeId && (!filterStatus || animal.status === filterStatus)
        && (!category || animal.category === category) && (!sex || animal.sex === sex)
        && normalize(`${animal.tag} ${animal.name}`).includes(normalize(query.trim())))
        .sort((a,b) => a.tag.localeCompare(b.tag, 'es', {numeric:true})));
    onMount(() => {
        const farm = $currentFarm;
        if (!farm) { ready = true; return; }
        const subscription = liveQuery(() => db.animals.where('farm').equals(farm.id).toArray()).subscribe({
            next(rows) { animals = rows; ready = true; }, error() { error = 'No se pudieron leer los animales de este dispositivo.'; ready = true; }
        });
        return () => subscription.unsubscribe();
    });
</script>
<div class="space-y-3">
    <label class="field-label">{label}<span class="relative"><Search class="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-[#8b9a7b]" /><input bind:value={query} class="field pl-10" inputmode="search" placeholder="Arete o nombre…" /></span></label>
    <Notice tone="error" message={error} />
    {#if !ready}<p class="field-help">Cargando animales…</p>{:else if matches.length}
        <ul aria-label="Animales disponibles" class="divide-y overflow-hidden rounded-xl border bg-white">
            {#each matches.slice(0,8) as animal (animal.id)}<li><button type="button" onclick={() => { onSelect(animal); query = ''; }} class="flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left hover:bg-[#f4f7ef]"><span class="min-w-0 flex-1"><span class="block text-sm font-semibold">{animal.tag}</span><span class="block truncate text-xs text-[#819171]">{animal.name || 'Sin nombre'}{animal.status !== 'active' ? ' · Inactivo' : ''}</span></span><ArrowUpRight class="h-4 w-4 shrink-0 text-[#92a67f]" /></button></li>{/each}
        </ul><p class="field-help">{matches.length > 8 ? `Mostrando 8 de ${matches.length}. Escribí para acotar la búsqueda.` : `${matches.length} animales disponibles.`}</p>
    {:else}<p class="empty-state">{query ? 'No hay coincidencias. Probá otro arete o nombre.' : 'No hay animales que cumplan estas condiciones. Revisá el hato o sincronizá la finca.'}</p>{/if}
</div>

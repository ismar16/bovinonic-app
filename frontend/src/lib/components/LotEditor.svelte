<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { db, type Animal, type AnimalLot } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueueMany, type PendingWrite } from '$lib/sync';
	import { errorMessage } from '$lib/forms';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	let { mode }: { mode: 'new' | 'edit' } = $props();
	let original = $state<AnimalLot | null>(null); let animals = $state<Animal[]>([]); let lots = $state<AnimalLot[]>([]);
	let name = $state(''); let description = $state(''); let selected = $state<string[]>([]); let query = $state(''); let includeInactive = $state(false);
	let loading = $state(true); let saving = $state(false); let savedId = $state(''); let error = $state('');
	const canEdit = $derived(['admin','technician'].includes($currentFarm?.role ?? ''));
	const filtered = $derived(animals.filter((a) => (includeInactive || a.status === 'active' || a.lot === original?.id) && `${a.tag} ${a.name}`.toLowerCase().includes(query.trim().toLowerCase())).sort((a,b) => a.tag.localeCompare(b.tag,'es',{numeric:true})));
	const transfers = $derived(animals.filter((a) => selected.includes(a.id) && a.lot && a.lot !== original?.id).length);
	onMount(async () => {
		const farm = $currentFarm; if (!farm) { loading = false; return; }
		try {
			[animals, lots] = await Promise.all([db.animals.where('farm').equals(farm.id).toArray(), db.lots.where('farm').equals(farm.id).toArray()]);
			if (mode === 'edit') {
				original = lots.find((lot) => lot.id === page.params.id) ?? null;
				if (!original) throw new Error('Este lote no está disponible en la finca actual.');
				name = original.name; description = original.description; selected = animals.filter((a) => a.lot === original?.id).map((a) => a.id);
			}
		} catch (cause) { error = errorMessage(cause); } finally { loading = false; }
	});
	function toggle(id: string) { selected = selected.includes(id) ? selected.filter((value) => value !== id) : [...selected,id]; }
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (!canEdit || saving || savedId) return;
		saving = true; error = '';
		try {
			if (!name.trim()) throw new Error('Escribí un nombre para el lote.');
			if (lots.some((lot) => lot.id !== original?.id && lot.name.toLowerCase() === name.trim().toLowerCase())) throw new Error('Ya existe un lote con ese nombre.');
			const id = original?.id ?? crypto.randomUUID();
			const records: PendingWrite[] = [{ collection: 'lots', payload: { ...original, id, name: name.trim(), description: description.trim() } }];
			for (const animal of animals) {
				if (selected.includes(animal.id) && animal.lot !== id) records.push({ collection: 'animals', payload: { ...animal, lot: id } });
				else if (!selected.includes(animal.id) && animal.lot === id) records.push({ collection: 'animals', payload: { ...animal, lot: null } });
			}
			await enqueueMany(records); savedId = id;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>
<svelte:head><title>{mode === 'new' ? 'Crear lote' : 'Editar lote'} · Bovinonic</title></svelte:head>
<div class="record-form mt-5 space-y-5"><PageHeader title={mode === 'new' ? 'Crear un lote de animales' : 'Editar lote'} eyebrow="Organización del hato" description="Agrupá animales por manejo o propósito. Cada animal pertenece a un lote a la vez; el potrero se conserva por separado." backHref={original ? `/lots/${original.id}` : '/lots'} backLabel="Volver a lotes" />
	<Notice tone="error" message={error} />
	{#if loading}<p class="empty-state">Cargando el hato…</p>{:else if !canEdit}<Notice tone="warning" message="La edición de lotes requiere un técnico o administrador." />{:else if mode === 'new' || original}
	<form onsubmit={save} class="space-y-5"><fieldset disabled={saving || !!savedId} class="space-y-5">
		<label class="field-label">Nombre del lote *<input class="field" bind:value={name} maxlength="100" placeholder="Ej. Novillas de reemplazo" required /></label><label class="field-label">Descripción<textarea class="field min-h-24" bind:value={description} maxlength="500" placeholder="Propósito o criterio del grupo"></textarea></label>
		<section class="form-section"><div class="flex flex-wrap items-center justify-between gap-2"><h2 class="section-title">Seleccionar animales existentes</h2><span class="status-pill">{selected.length} seleccionados</span></div><label class="field-label">Buscar animal<input class="field" bind:value={query} placeholder="Arete o nombre…" /></label><label class="flex items-center gap-2 text-xs text-[#7c8e70]"><input type="checkbox" bind:checked={includeInactive} /> Incluir animales inactivos</label><div class="flex flex-wrap gap-2"><button type="button" class="quiet-button" onclick={() => selected = [...new Set([...selected, ...filtered.map((a) => a.id)])]}>Seleccionar visibles ({filtered.length})</button><button type="button" class="quiet-button" onclick={() => selected = []}>Quitar selección</button></div>
		<div class="max-h-96 overflow-y-auto rounded-xl border bg-white"><ul class="divide-y">{#each filtered as animal (animal.id)}<li><label class="flex min-h-14 cursor-pointer items-center gap-3 px-4 py-3"><input type="checkbox" checked={selected.includes(animal.id)} onchange={() => toggle(animal.id)} /><span class="min-w-0 flex-1"><span class="block text-sm font-semibold">{animal.tag} · {animal.name || 'Sin nombre'}</span><span class="text-xs text-[#88997a]">{animal.lot ? `Lote actual: ${lots.find((lot) => lot.id === animal.lot)?.name ?? 'Sin datos'}` : 'Sin lote'}{animal.status !== 'active' ? ' · Inactivo' : ''}</span></span></label></li>{:else}<li class="empty-state m-3">No hay animales con esos filtros. También podés crear el lote vacío y registrar animales nuevos después.</li>{/each}</ul></div>
		{#if transfers}<Notice tone="warning" message={`${transfers} animales seleccionados saldrán de su lote actual para pasar a este lote. Su potrero no cambia.`} />{/if}</section>
	</fieldset>{#if savedId}<Notice tone="success" message="El lote y su composición se guardaron juntos. El envío es automático; revisá su estado en la barra superior." />{/if}<div class="form-actions"><button type="submit" class="action-button" disabled={saving || !!savedId}>{saving ? 'Guardando lote…' : savedId ? 'Lote guardado' : 'Guardar lote y animales'}</button>{#if savedId}<a href="/lots/{savedId}" class="quiet-button">Ver lote</a><a href="/animals/bulk?lot={savedId}" class="quiet-button">Registrar animales nuevos aquí</a>{:else}<a href="/lots" class="quiet-button">Cancelar</a>{/if}</div></form>{/if}
</div>

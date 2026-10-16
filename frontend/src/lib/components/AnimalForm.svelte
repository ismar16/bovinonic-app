<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { liveQuery } from 'dexie';
	import { Check, Plus, ArrowUpRight } from 'lucide-svelte';
	import { db, type Animal, type Owner, type Brand, type Paddock, type AnimalLot } from '$lib/db';
	import { currentFarm, pendingCount } from '$lib/stores';
	import { enqueue } from '$lib/sync';
	import { errorMessage, validDate } from '$lib/forms';
	import { farmDate } from '$lib/dates';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	import TagSearch from './TagSearch.svelte';
	let { mode }: { mode: 'new' | 'edit' } = $props();
	let original = $state<Animal | null>(null);
	let tag = $state(''); let name = $state(''); let sex = $state<'H' | 'M'>('H');
	let category = $state('calf'); let birthDate = $state(''); let owner = $state(''); let brand = $state(''); let paddock = $state('');
	let lot = $state(''); let lots = $state<AnimalLot[]>([]);
	let mother = $state<Animal | null>(null); let father = $state<Animal | null>(null);
	let owners = $state<Owner[]>([]); let brands = $state<Brand[]>([]); let paddocks = $state<Paddock[]>([]);
	let loading = $state(true); let saving = $state(false); let savedId = $state(''); let error = $state(''); let notFound = $state(false);
	const canEdit = $derived(['admin', 'technician'].includes($currentFarm?.role ?? ''));
	const categories = $derived([{ value: 'calf', label: 'Ternero/a' }, { value: 'heifer', label: 'Novillo/a' }, ...(sex === 'H' ? [{ value: 'cow_lactating', label: 'Vaca en ordeño' }, { value: 'cow_dry', label: 'Vaca seca' }] : [{ value: 'bull', label: 'Toro reproductor' }])]);
	const suggested = $derived(brands.find((b) => b.title_owner === owner));
	$effect(() => { if (!categories.some((c) => c.value === category)) category = 'calf'; });
	onMount(() => {
		const farm = $currentFarm;
		if (!farm) { loading = false; return; }
		const catalogs = liveQuery(async () => ({ owners: await db.owners.where('farm').equals(farm.id).toArray(), brands: await db.brands.where('farm').equals(farm.id).toArray(), lots: await db.lots.where('farm').equals(farm.id).toArray(), paddocks: await db.paddocks.where('farm').equals(farm.id).toArray() })).subscribe({ next(data) { lots = data.lots; owners = data.owners; brands = data.brands; paddocks = data.paddocks; }, error(cause) { error = errorMessage(cause); } });
		void (async () => {
			try {
				if (mode === 'edit') {
					const animal = await db.animals.get(page.params.id ?? '');
					if (!animal || animal.farm !== farm.id) { notFound = true; return; }
					lot = animal.lot ?? ''; original = animal; tag = animal.tag; name = animal.name; sex = animal.sex; category = animal.category; birthDate = animal.birth_date ?? ''; owner = animal.owner ?? ''; paddock = animal.paddock ?? ''; brand = animal.brand ?? '';
					if (animal.mother) mother = await db.animals.get(animal.mother) ?? null;
					if (animal.father) father = await db.animals.get(animal.father) ?? null;
				}
			} catch (cause) { error = errorMessage(cause); } finally { loading = false; }
		})();
		return () => catalogs.unsubscribe();
	});
	function reset() { tag = ''; name = ''; sex = 'H'; category = 'calf'; birthDate = ''; lot = ''; owner = ''; paddock = ''; brand = ''; mother = null; father = null; savedId = ''; error = ''; }
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (saving || savedId || !canEdit) return;
		saving = true; error = '';
		try {
			const cleanTag = tag.trim();
			if (!cleanTag) throw new Error('El arete es obligatorio.');
			if (birthDate && (!validDate(birthDate) || birthDate > farmDate())) throw new Error('La fecha de nacimiento debe ser válida y no futura.');
			const duplicate = await db.animals.where('tag').equalsIgnoreCase(cleanTag).first();
			if (duplicate && duplicate.id !== original?.id) throw new Error(`El arete ${cleanTag} ya está registrado en este dispositivo.`);
			const id = original?.id ?? crypto.randomUUID();
			await enqueue('animals', { ...original, id, tag: cleanTag, name: name.trim(), sex, category, birth_date: birthDate || null, lot: lot || null, owner: owner || null, paddock: paddock || null, brand: brand || null, mother: mother?.id ?? null, father: father?.id ?? null, status: original?.status ?? 'active' });
			savedId = id;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>

<svelte:head><title>{mode === 'new' ? 'Nuevo animal' : `Editar ${original?.tag ?? 'animal'}`} · Bovinonic</title></svelte:head>
<div class="record-form mt-5 space-y-6">
	<PageHeader title={mode === 'new' ? 'Registrar un animal' : `Editar ${original?.tag ?? 'animal'}`} eyebrow="Ficha del hato" description="Identificación, ubicación y parentesco en un solo registro. Los campos marcados con * son obligatorios." backHref={mode === 'edit' ? `/animals/${page.params.id}` : '/herd'} backLabel={mode === 'edit' ? 'Volver a la ficha' : 'Volver al hato'} />
	{#if loading}<p class="empty-state">Cargando ficha…</p>{:else if notFound}<Notice tone="warning" message="Este animal no está disponible en la finca de este dispositivo. Sincronizá el hato y volvé a intentar." />{:else if !canEdit}<Notice tone="warning" message="Tu rol permite consultar animales. La edición requiere un técnico o administrador." />{:else}
	<form onsubmit={save} class="space-y-6">
		<fieldset disabled={saving || !!savedId} class="space-y-5">
			<section class="form-section"><h2 class="section-title">Identificación</h2><div class="form-grid">
				<label class="field-label">Arete *<input class="field" bind:value={tag} maxlength="50" required placeholder="Ej. NI-0101" /></label>
				<label class="field-label">Nombre<input class="field" bind:value={name} maxlength="150" placeholder="Nombre del animal" /></label>
				<label class="field-label">Sexo *<select class="field" bind:value={sex}><option value="H">Hembra</option><option value="M">Macho</option></select></label>
				<label class="field-label">Categoría *<select class="field" bind:value={category}>{#each categories as c}<option value={c.value}>{c.label}</option>{/each}</select></label>
				<label class="field-label">Fecha de nacimiento<input type="date" class="field" bind:value={birthDate} max={farmDate()} /><span class="field-help">Dejala vacía si no la conocés.</span></label>
			</div></section>
			<section class="form-section"><h2 class="section-title">Ubicación y propiedad</h2><div class="form-grid">
				<label class="field-label">Lote<select class="field" bind:value={lot}><option value="">Sin lote</option>{#each lots as l}<option value={l.id}>{l.name}</option>{/each}</select><a class="field-help underline" href="/lots">Administrar lotes de animales</a></label>
				<label class="field-label">Potrero<select class="field" bind:value={paddock}><option value="">Sin asignar</option>{#each paddocks as p}<option value={p.id}>{p.name}</option>{/each}</select></label>
				<label class="field-label">Propietario<select class="field" bind:value={owner}><option value="">Sin asignar</option>{#each owners as o}<option value={o.id}>{o.name}</option>{/each}</select></label>
				<label class="field-label">Fierro<select class="field" bind:value={brand}><option value="">Orejano (sin fierro)</option>{#each brands as b}<option value={b.id}>{b.code}</option>{/each}</select></label>
			</div>{#if suggested && suggested.id !== brand}<button type="button" class="back-link mb-0" onclick={() => brand = suggested.id}>Usar el fierro {suggested.code} del propietario</button>{/if}
			{#if $currentFarm?.role === 'admin'}<a href="/catalogs" class="field-help underline">Administrar potreros, propietarios y fierros</a>{/if}</section>
			<details class="form-section"><summary class="cursor-pointer text-sm font-semibold">Parentesco (opcional){mother || father ? ' · Registrado' : ''}</summary><div class="form-grid mt-4"><div class="space-y-3">{#if mother}<p class="notice">Madre: {mother.tag} · {mother.name}</p><button type="button" class="quiet-button" onclick={() => mother = null}>Quitar madre</button>{:else}<TagSearch onSelect={(a) => mother = a} sex="H" label="Buscar madre" excludeId={original?.id} />{/if}</div><div class="space-y-3">{#if father}<p class="notice">Padre: {father.tag} · {father.name}</p><button type="button" class="quiet-button" onclick={() => father = null}>Quitar padre</button>{:else}<TagSearch onSelect={(a) => father = a} sex="M" label="Buscar padre" excludeId={original?.id} />{/if}</div></div></details>
		</fieldset>
		<Notice tone="error" message={error} />
		{#if savedId}<Notice tone="success" message={$pendingCount ? 'Animal guardado en este dispositivo. Los cambios están pendientes de envío.' : 'Animal guardado. No hay registros pendientes de envío.'} />{/if}
		<div class="form-actions"><button type="submit" class="action-button" disabled={saving || !!savedId}>{#if savedId}<Check class="h-4 w-4" />{/if}{saving ? 'Guardando…' : savedId ? 'Guardado' : mode === 'new' ? 'Guardar animal' : 'Guardar cambios'}</button>{#if savedId}<a href="/animals/{savedId}" class="quiet-button">Ver ficha<ArrowUpRight class="h-4 w-4" /></a>{#if mode === 'new'}<button type="button" onclick={reset} class="quiet-button"><Plus class="h-4 w-4" /> Registrar otro</button>{/if}{:else}<a href={mode === 'edit' ? `/animals/${page.params.id}` : '/herd'} class="quiet-button">Cancelar</a>{/if}</div>
	</form>{/if}
</div>

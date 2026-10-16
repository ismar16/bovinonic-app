<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { Plus, Trash2, Check } from 'lucide-svelte';
	import { db, type AnimalLot, type Paddock, type Owner, type Brand } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueueMany } from '$lib/sync';
	import { errorMessage, validDate } from '$lib/forms';
	import { farmDate } from '$lib/dates';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	interface Row { key: string; tag: string; name: string; sex: 'H' | 'M'; category: string; birth: string; }
	function blank(): Row { return { key: crypto.randomUUID(), tag: '', name: '', sex: 'H', category: 'calf', birth: '' }; }
	let rows = $state<Row[]>([]); let lots = $state<AnimalLot[]>([]); let paddocks = $state<Paddock[]>([]); let owners = $state<Owner[]>([]); let brands = $state<Brand[]>([]);
	let lot = $state(''); let paddock = $state(''); let owner = $state(''); let brand = $state(''); let saving = $state(false); let saved = $state(0); let errors = $state<string[]>([]);
	const canEdit = $derived(['admin','technician'].includes($currentFarm?.role ?? ''));
	const used = $derived(rows.filter((row) => row.tag.trim() || row.name.trim() || row.birth));
	onMount(async () => {
		rows = [blank(), blank(), blank()];
		if (!$currentFarm) return;
		try {
			[lots,paddocks,owners,brands] = await Promise.all([db.lots.where('farm').equals($currentFarm.id).toArray(),db.paddocks.where('farm').equals($currentFarm.id).toArray(),db.owners.where('farm').equals($currentFarm.id).toArray(),db.brands.where('farm').equals($currentFarm.id).toArray()]);
			const selected = page.url.searchParams.get('lot'); if (selected && lots.some((l) => l.id === selected)) lot = selected;
		} catch (cause) { errors = [errorMessage(cause)]; }
	});
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (saving || saved || !canEdit) return;
		errors = []; saving = true;
		try {
			if (!used.length) throw new Error('Completá al menos un arete para registrar animales.');
			const existing = await db.animals.where('farm').equals($currentFarm?.id ?? '').toArray();
			const tags = new Set(existing.map((a) => a.tag.toLowerCase()));
			const problems: string[] = [];
			for (const [index,row] of rows.entries()) {
				if (!used.includes(row)) continue;
				const tag = row.tag.trim();
				if (!tag) problems.push(`Fila ${index+1}: el arete es obligatorio.`);
				else if (tags.has(tag.toLowerCase())) problems.push(`Fila ${index+1}: el arete ${tag} está repetido o ya existe en el hato.`);
				else tags.add(tag.toLowerCase());
				if ((row.sex === 'H' && row.category === 'bull') || (row.sex === 'M' && ['cow_lactating','cow_dry'].includes(row.category))) problems.push(`Fila ${index+1}: revisá el sexo y la categoría.`);
				if (row.birth && (!validDate(row.birth) || row.birth > farmDate())) problems.push(`Fila ${index+1}: la fecha de nacimiento debe ser válida y no futura.`);
			}
			if (problems.length) { errors = problems; return; }
			await enqueueMany(used.map((row) => ({ collection: 'animals' as const, payload: { id: crypto.randomUUID(), tag: row.tag.trim(), name: row.name.trim(), sex: row.sex, category: row.category, birth_date: row.birth || null, lot: lot || null, paddock: paddock || null, owner: owner || null, brand: brand || null, mother: null, father: null, status: 'active' } })));
			saved = used.length;
		} catch (cause) { errors = [errorMessage(cause)]; } finally { saving = false; }
	}
</script>
<svelte:head><title>Ingreso de varios animales · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-5"><PageHeader title="Registrar varios animales" eyebrow="Ingreso al hato" description="Completá una fila por animal. Los datos comunes se aplican a todos; las filas vacías se omiten. Todo se guarda junto en este dispositivo." backHref={lot ? `/lots/${lot}` : '/herd'} backLabel={lot ? 'Volver al lote' : 'Volver al hato'} />
	{#if !canEdit}<Notice tone="warning" message="El ingreso de animales requiere un técnico o administrador." />{:else}
	<form onsubmit={save} class="space-y-5"><fieldset disabled={saving || !!saved} class="space-y-5">
		<section class="panel p-5"><h2 class="section-title mb-4">Datos comunes</h2><div class="form-grid"><label class="field-label">Lote<select class="field" bind:value={lot}><option value="">Sin lote</option>{#each lots as l}<option value={l.id}>{l.name}</option>{/each}</select></label><label class="field-label">Potrero<select class="field" bind:value={paddock}><option value="">Sin asignar</option>{#each paddocks as p}<option value={p.id}>{p.name}</option>{/each}</select></label><label class="field-label">Propietario<select class="field" bind:value={owner}><option value="">Sin asignar</option>{#each owners as o}<option value={o.id}>{o.name}</option>{/each}</select></label><label class="field-label">Fierro<select class="field" bind:value={brand}><option value="">Orejano (sin fierro)</option>{#each brands as b}<option value={b.id}>{b.code}</option>{/each}</select></label></div></section>
		<div class="flex items-center justify-between gap-3"><h2 class="section-title">Animales · {used.length} filas completas o iniciadas</h2><button type="button" class="quiet-button" onclick={() => rows = [...rows,blank()]} disabled={rows.length >= 200}><Plus class="h-4 w-4" />Agregar fila</button></div>
		<div class="space-y-3">{#each rows as row,index (row.key)}<section class="panel p-4"><div class="mb-3 flex items-center justify-between"><p class="eyebrow">Animal {index+1}</p><button type="button" class="rounded-lg p-2 text-[#9b7468]" aria-label="Quitar fila {index+1}" onclick={() => rows = rows.filter((r) => r.key !== row.key)} disabled={rows.length === 1}><Trash2 class="h-4 w-4" /></button></div><div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><label class="field-label">Arete *<input class="field" bind:value={row.tag} maxlength="50" placeholder="NI-0000" /></label><label class="field-label">Nombre<input class="field" bind:value={row.name} maxlength="150" /></label><label class="field-label">Sexo<select class="field" bind:value={row.sex} onchange={() => { if ((row.sex === 'H' && row.category === 'bull') || (row.sex === 'M' && ['cow_lactating','cow_dry'].includes(row.category))) row.category = 'calf'; }}><option value="H">Hembra</option><option value="M">Macho</option></select></label><label class="field-label">Categoría<select class="field" bind:value={row.category}><option value="calf">Ternero/a</option><option value="heifer">Novillo/a</option>{#if row.sex === 'H'}<option value="cow_lactating">Vaca en ordeño</option><option value="cow_dry">Vaca seca</option>{:else}<option value="bull">Toro reproductor</option>{/if}</select></label><label class="field-label">Nacimiento<input type="date" class="field" bind:value={row.birth} max={farmDate()} /></label></div></section>{/each}</div>
	</fieldset>{#each errors as message}<Notice tone="error" {message} />{/each}{#if saved}<Notice tone="success" message={`${saved} animales guardados en este dispositivo. El envío es automático; revisá su estado en la barra superior.`} />{/if}<div class="form-actions"><button type="submit" class="action-button" disabled={saving || !!saved || !used.length}>{#if saved}<Check class="h-4 w-4" />{/if}{saving ? 'Guardando animales…' : saved ? `${saved} animales guardados` : `Guardar ${used.length} animales`}</button>{#if saved}<a href={lot ? `/lots/${lot}` : '/herd'} class="quiet-button">Ver animales</a>{:else}<a href={lot ? `/lots/${lot}` : '/herd'} class="quiet-button">Cancelar</a>{/if}</div></form>{/if}
</div>

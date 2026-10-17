<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { db, type Owner } from '$lib/db';
	import { catalogConfig, catalogKind, type CatalogRecord } from '$lib/catalogs';
	import { currentFarm } from '$lib/stores';
	import { enqueue } from '$lib/sync';
	import { errorMessage } from '$lib/forms';
	import { paddockSettings } from '$lib/paddocks';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	let { mode }: { mode: 'new' | 'edit' } = $props();
	const kind = $derived(catalogKind(page.params.collection));
	const config = $derived(kind ? catalogConfig[kind] : null);
	let original = $state<CatalogRecord | null>(null); let owners = $state<Owner[]>([]);
	let name = $state(''); let idNumber = $state(''); let phone = $state(''); let titleOwner = $state('');
	let area = $state(''); let areaUnit = $state('mz'); let maxDays = $state('');
	let loading = $state(true); let saving = $state(false); let saved = $state(false); let error = $state('');
	onMount(async () => {
		if (!kind || !$currentFarm) { loading = false; return; }
		try {
			owners = await db.owners.where('farm').equals($currentFarm.id).toArray();
			if (mode === 'edit') {
				const row: CatalogRecord | undefined = await db[kind].get(page.params.id ?? '');
				if (!row || row.farm !== $currentFarm.id) throw new Error('Este registro no está disponible en la finca actual.');
				original = row; name = row.code ?? row.name ?? '';
				idNumber = row.id_number ?? ''; phone = row.phone ?? ''; titleOwner = row.title_owner ?? '';
				area = row.area ?? ''; areaUnit = row.area_unit ?? 'mz'; maxDays = row.max_occupation_days?.toString() ?? '';
			}
		} catch (cause) { error = errorMessage(cause); } finally { loading = false; }
	});
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (!kind || !config || saving || saved) return;
		saving = true; error = '';
		try {
			if (!name.trim()) throw new Error('Completá el nombre o código.');
			if (kind !== 'owners') {
				const rows = await db[kind].where('farm').equals($currentFarm?.id ?? '').toArray();
				if (rows.some((row) => row.id !== original?.id && ('code' in row ? row.code : row.name).toLowerCase() === name.trim().toLowerCase())) throw new Error('Ya existe un registro con ese nombre o código en esta finca.');
			}
			await enqueue(kind, { ...original, id: original?.id ?? crypto.randomUUID(), ...(kind === 'brands' ? { code: name.trim(), title_owner: titleOwner || null } : { name: name.trim() }), ...(kind === 'owners' ? { id_number: idNumber.trim(), phone: phone.trim() } : {}), ...(kind === 'paddocks' ? paddockSettings(area, areaUnit, maxDays) : {}) });
			saved = true;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>
<svelte:head><title>{mode === 'new' ? 'Agregar' : 'Editar'} {config?.singular ?? 'registro'} · Bovinonic</title></svelte:head>
<div class="record-form mt-5 space-y-5"><PageHeader title={`${mode === 'new' ? 'Agregar' : 'Editar'} ${config?.singular ?? 'registro'}`} eyebrow="Catálogos de la finca" description={config?.description} backHref={kind ? `/catalogs/${kind}` : '/catalogs'} backLabel={config?.title ?? 'Catálogos'} />
	<Notice tone="error" message={error} />
	{#if loading}<p class="empty-state">Cargando…</p>{:else if $currentFarm?.role !== 'admin'}<Notice tone="warning" message="La administración de catálogos requiere el rol de administrador." />{:else if config && kind && (mode === 'new' || original)}
	<form onsubmit={save} class="space-y-5"><fieldset disabled={saving || saved} class="form-grid"><label class="field-label">{kind === 'brands' ? 'Código del fierro' : 'Nombre'} *<input class="field" bind:value={name} maxlength={config.max} required /></label>{#if kind === 'owners'}<label class="field-label">Identificación<input class="field" bind:value={idNumber} maxlength="50" /></label><label class="field-label">Teléfono<input class="field" bind:value={phone} maxlength="30" type="tel" /></label>{:else if kind === 'brands'}<label class="field-label">Titular<select class="field" bind:value={titleOwner}><option value="">Sin asignar</option>{#each owners as o}<option value={o.id}>{o.name}</option>{/each}</select></label>{/if}</fieldset>
	{#if kind === 'paddocks'}<fieldset disabled={saving || saved} class="form-section space-y-4"><h2 class="section-title">Superficie y rotación</h2><div class="form-grid"><label class="field-label">Superficie aproximada<input class="field" inputmode="decimal" bind:value={area} placeholder="Ej. 5,50" /></label><label class="field-label">Unidad<select class="field" bind:value={areaUnit}><option value="mz">Manzanas</option><option value="ha">Hectáreas</option><option value="m2">Metros cuadrados</option></select></label><label class="field-label">Máximo de días de ocupación<input class="field" inputmode="numeric" bind:value={maxDays} placeholder="Ej. 3" /><span class="field-help">Es un aviso para planificar el traslado. Podés dejarlo sin definir.</span></label></div></fieldset>{/if}
	{#if saved}<Notice tone="success" message="Guardado en este dispositivo. El envío es automático; revisá su estado en la barra superior." />{/if}
	<div class="form-actions"><button class="action-button" type="submit" disabled={saving || saved}>{saving ? 'Guardando…' : saved ? 'Guardado' : 'Guardar datos'}</button><a href="/catalogs/{kind}" class="quiet-button">{saved ? 'Volver al catálogo' : 'Cancelar'}</a></div></form>{/if}
</div>

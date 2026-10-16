<script lang="ts">
    import { onMount } from 'svelte';
    import { page } from '$app/state';
    import { db, type Animal } from '$lib/db';
    import { currentFarm } from '$lib/stores';
    import { farmDate } from '$lib/dates';
    import { errorMessage, validDate } from '$lib/forms';
    import { enqueue } from '$lib/sync';
    import PageHeader from '$lib/components/PageHeader.svelte';
    import Notice from '$lib/components/Notice.svelte';
    const statuses = {active:'Activo',sold:'Vendido',dead:'Muerto',culled:'Descarte'};
    let animal = $state<Animal | null>(null); let status = $state<Animal['status']>('sold'); let date = $state(farmDate()); let reason = $state(''); let error = $state(''); let loading = $state(true); let saving = $state(false); let saved = $state(false);
    const canEdit = $derived(['admin','technician'].includes($currentFarm?.role ?? ''));
    onMount(async () => { try { const found = await db.animals.get(page.params.id ?? ''); if (!found || found.farm !== $currentFarm?.id) throw new Error('Animal no disponible en la finca actual.'); animal = found; } catch(cause) { error = errorMessage(cause); } finally { loading = false; } });
    async function save(event: SubmitEvent) { event.preventDefault(); if (!animal || saving || saved || !canEdit) return; saving = true; error = ''; try { if (!validDate(date) || date > farmDate() || (animal.birth_date && date < animal.birth_date)) throw new Error('Elegí una fecha válida entre el nacimiento del animal y hoy.'); await enqueue('animals',{...animal,status,status_changed_at:date,status_reason:reason.trim()}); saved = true; } catch(cause) { error = errorMessage(cause); } finally { saving = false; } }
</script>
<svelte:head><title>Cambio de estado · Bovinonic</title></svelte:head>
<div class="record-form mt-5 space-y-5"><PageHeader title="Cambiar estado del animal" eyebrow="Historial del hato" description="La venta, baja o reactivación cambia el inventario activo. Los registros históricos se conservan." backHref={`/animals/${page.params.id}`} backLabel="Volver a la ficha" /><Notice tone="error" message={error} />
{#if loading}<p class="empty-state">Cargando ficha…</p>{:else if !canEdit}<Notice tone="warning" message="Esta acción requiere un técnico o administrador." />{:else if animal}<div class="form-section"><p class="text-lg font-semibold">{animal.tag} · {animal.name || 'Sin nombre'}</p><p class="field-help">Estado actual: {statuses[animal.status]}</p></div><form onsubmit={save} class="space-y-5"><fieldset class="space-y-5" disabled={saving || saved}><label class="field-label">Nuevo estado<select class="field" bind:value={status}>{#each Object.entries(statuses) as [value,label]}<option value={value}>{label}</option>{/each}</select></label><label class="field-label">Fecha del cambio<input type="date" class="field" bind:value={date} min={animal.birth_date ?? undefined} max={farmDate()} required /></label><label class="field-label">Motivo<input class="field" bind:value={reason} maxlength="255" placeholder="Descripción del cambio (opcional)" /></label><Notice tone="warning" message={`Al confirmar, ${animal.tag} pasará de ${statuses[animal.status]} a ${statuses[status]}. Su historial se mantiene.`} /></fieldset>{#if saved}<Notice tone="success" message="Cambio guardado en este dispositivo. El envío es automático; revisá su estado en la barra superior." />{/if}<div class="form-actions"><button type="submit" class="action-button" disabled={saving || saved || status === animal.status}>{saving ? 'Guardando…' : saved ? 'Cambio guardado' : 'Confirmar cambio de estado'}</button><a href={`/animals/${animal.id}`} class="quiet-button">{saved ? 'Ver ficha' : 'Cancelar'}</a></div></form>{/if}</div>

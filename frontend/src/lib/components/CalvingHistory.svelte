<script lang="ts">
	import { onMount } from 'svelte';
	import { liveQuery } from 'dexie';
	import { db, type CalvingRecord, type Animal } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { maternalLabels, deliveryLabels } from '$lib/calvings';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	let { id }: { id?: string } = $props();
	let records=$state<CalvingRecord[]>([]),animals=$state<Animal[]>([]),pending=$state<string[]>([]),loading=$state(true),error=$state('');
	const selected=$derived(records.find((r)=>r.id===id));
	const canWrite=$derived(['admin','technician'].includes($currentFarm?.role??''));
	function name(aid:string|null|undefined){const a=animals.find((r)=>r.id===aid);return a?`${a.tag} · ${a.name||'Sin nombre'}`:'Ficha no disponible';}
	onMount(()=>{const farm=$currentFarm;if(!farm){loading=false;return;}const sub=liveQuery(async()=>({records:await db.calvings.where('farm').equals(farm.id).toArray(),animals:await db.animals.where('farm').equals(farm.id).toArray(),pending:(await db.outbox.toArray()).filter((r)=>r.collection==='calvings').map((r)=>r.record_id)})).subscribe({next(data){records=data.records.sort((a,b)=>b.date.localeCompare(a.date));animals=data.animals;pending=data.pending;loading=false;},error(){error='No se pudo cargar el historial de partos.';loading=false;}});return()=>sub.unsubscribe();});
</script>
<svelte:head><title>Partos y crías · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-5">
<PageHeader title={id?'Detalle del parto':'Partos y crías'} eyebrow="Historial reproductivo" description="Cada parto reúne la madre, sus crías y los cambios registrados." backHref={id?'/reproduction/calvings':'/operations'} backLabel={id?'Todos los partos':'Operaciones'} />
<Notice tone="error" message={error}/>
{#if loading}<p class="empty-state">Cargando…</p>{:else if id}
{#if selected}
<section class="panel p-5 sm:p-7 space-y-4"><div class="flex flex-wrap items-center justify-between gap-3"><h2 class="section-title">{selected.date}</h2><span class="status-pill">{pending.includes(selected.id)?'Pendiente de confirmación':'Confirmado por el servidor'}</span></div><a class="back-link" href="/animals/{selected.mother}">Madre: {name(selected.mother)}</a><p>Parto {deliveryLabels[selected.delivery]?.toLowerCase()}. {maternalLabels[selected.maternal_status]}.</p>
{#if pending.includes(selected.id)}<Notice tone="warning" message="Las crías y los cambios de la madre se aplican juntos cuando el servidor confirma. Si hay un rechazo, revisá el pendiente antes de reintentar." />{#if canWrite}<a class="quiet-button" href="/reproduction/calving?pending={selected.id}">Revisar parto pendiente</a>{/if}{/if}
{#if selected.result?.movement}<a class="back-link" href="/paddocks/movements">Ver historial de traslado de la madre</a>{/if}
{#if selected.notes}<p class="whitespace-pre-wrap break-words">{selected.notes}</p>{/if}</section>
<section class="panel p-5 sm:p-7 space-y-4"><h2 class="section-title">Crías · {selected.calves.length}</h2>{#each selected.result?.calves??selected.calves as calf,index}<div class="rounded-xl border p-4 space-y-2"><h3 class="font-semibold">Cría {index+1} · {calf.mode==='stillborn'?'Nacido muerto':calf.mode==='existing'?'Ficha vinculada':'Cría nueva'}</h3>{#if calf.mode==='stillborn'}<p>Sexo: {calf.sex==='H'?'Hembra':calf.sex==='M'?'Macho':'Sin determinar'}. Se conserva en el parto sin ingresar al hato activo.</p>{:else if calf.animal && selected.result}<a class="back-link" href="/animals/{calf.animal}">{calf.tag||name(calf.animal)}{calf.name?` · ${calf.name}`:''}</a>{:else}<p>{calf.mode==='existing'?name(calf.animal):calf.tag||'Identificación provisional pendiente'}</p>{/if}{#if calf.weight_kg}<p>Peso al nacer: {calf.weight_kg} kg</p>{/if}</div>{/each}</section>
{:else}<p class="empty-state">Este parto no está disponible en el dispositivo. Sincronizá para actualizar el historial.</p>{/if}
{:else}
{#if canWrite}<a class="action-button" href="/reproduction/calving">Registrar parto y crías</a>{/if}
<div class="space-y-3">{#each records as record}<a class="panel block p-5" href="/reproduction/calvings/{record.id}"><div class="flex flex-wrap justify-between gap-2"><strong>{name(record.mother)}</strong><span>{record.date}</span></div><p class="mt-2 text-sm">{record.calves.filter((r)=>r.mode!=='stillborn').length} crías vivas · {record.calves.filter((r)=>r.mode==='stillborn').length} nacidas muertas</p><span class="status-pill mt-3">{pending.includes(record.id)?'Pendiente de confirmación':'Confirmado'}</span></a>{:else}<p class="empty-state">Aún no hay partos con crías registrados.</p>{/each}</div>
{/if}</div>

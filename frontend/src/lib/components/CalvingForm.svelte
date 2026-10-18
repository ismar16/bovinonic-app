<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { liveQuery } from 'dexie';
	import { db, type Animal, type AnimalLot, type Owner, type Paddock, type CalvingCalf, type CalvingRecord } from '$lib/db';
	import { enqueue, reviewFinancialPending, syncNow } from '$lib/sync';
	import { pull } from '$lib/api';
	import { currentFarm } from '$lib/stores';
	import { farmDate } from '$lib/dates';
	import { errorMessage, validDate } from '$lib/forms';
	import { validateCalving, maternalLabels, deliveryLabels } from '$lib/calvings';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	import TagSearch from './TagSearch.svelte';
	type Row=CalvingCalf & {key:string;provisional:boolean;query:string};
	function newRow():Row { return {key:crypto.randomUUID(),mode:'new',animal:crypto.randomUUID(),sex:'H',tag:'',name:'',weight_kg:null,provisional:false,query:''}; }
	let mother=$state<Animal|null>(null), animals=$state<Animal[]>([]),lots=$state<AnimalLot[]>([]),paddocks=$state<Paddock[]>([]),owners=$state<Owner[]>([]);
	let id=$state<string>(''),date=$state(farmDate()),delivery=$state<CalvingRecord['delivery']>('normal'),maternalStatus=$state<CalvingRecord['maternal_status']>('keep'),notes=$state('');
	let rows=$state<Row[]>([]),changeLot=$state(false),motherLot=$state(''),changePaddock=$state(false),motherPaddock=$state(''),calfLot=$state(''),calfPaddock=$state(''),calfOwner=$state('');
	let loading=$state(true),saving=$state(false),saved=$state(false),error=$state(''),editing=$state(false),message=$state(''),discarded=$state(false);
	const canWrite=$derived(['admin','technician'].includes($currentFarm?.role??''));
	const hasNew=$derived(rows.some((r)=>r.mode==='new'));
	function chooseMother(animal:Animal) { mother=animal;calfOwner=animal.owner??'';motherLot=animal.lot??'';motherPaddock=animal.paddock??'';changeLot=false;changePaddock=false;error=''; }
	function changeMode(row:Row) { row.animal=row.mode==='new'?crypto.randomUUID():null;row.sex=row.mode==='stillborn'?'unknown':'H';row.tag='';row.name='';row.weight_kg=null;row.provisional=false; }
	function choices(row:Row) { return animals.filter((a)=>a.id!==mother?.id && !a.birth_record && (!a.mother || a.mother===mother?.id) && (!a.birth_date || a.birth_date===date) && !rows.some((other)=>other.key!==row.key && other.mode==='existing' && other.animal===a.id) && `${a.tag} ${a.name}`.toLowerCase().includes(row.query.toLowerCase())).sort((a,b)=>a.tag.localeCompare(b.tag,'es',{numeric:true})); }
	onMount(()=>{
		const farm=$currentFarm;if(!farm){loading=false;return;}
		let disposed=false,subscription:{unsubscribe():void}|undefined;
		(async()=>{try{
			id=crypto.randomUUID();rows=[newRow()];
			const requestedDate=page.url.searchParams.get('date');if(requestedDate && validDate(requestedDate))date=requestedDate;
			const pending=page.url.searchParams.get('pending');
			let original:CalvingRecord|undefined;
			if(pending){
				if(await reviewFinancialPending('calvings',pending)){id=pending;saved=true;message='El servidor ya confirmó el parto. Se recuperó el registro completo.';await syncNow();}
				else {
					original=await db.calvings.get(pending);if(!original || original.farm!==farm.id)throw new Error('El parto pendiente no está disponible.');
					const data=await pull(farm.id);const outbox=await db.outbox.toArray();
					await db.transaction('rw',[db.animals,db.calvings],async()=>{if($currentFarm?.id!==farm.id)throw new Error('La finca cambió.');for(const table of ['animals','calvings'] as const){const pendingIds=new Set(outbox.filter((r)=>r.collection===table).map((r)=>r.record_id));await db.table(table).bulkPut(((data[table]??[]) as {id:string}[]).filter((r)=>!pendingIds.has(r.id)));}});
				}
			}
			const selected=await db.animals.get(original?.mother??page.url.searchParams.get('animal')??'');
			if(selected && selected.farm===farm.id && selected.sex==='H')chooseMother(selected);
			if(original){id=original.id;date=original.date;delivery=original.delivery;maternalStatus=original.maternal_status;notes=original.notes;rows=original.calves.map((r)=>({...r,key:crypto.randomUUID(),provisional:r.mode==='new'&&!r.tag,query:''}));const loc=original.location;changeLot=loc.change_mother_lot;motherLot=loc.mother_lot??'';changePaddock=loc.change_mother_paddock;motherPaddock=loc.mother_paddock??'';calfLot=loc.calf_lot??'';calfPaddock=loc.calf_paddock??'';calfOwner=loc.calf_owner??'';editing=true;}
			if(disposed)return;
			subscription=liveQuery(async()=>({animals:await db.animals.where('farm').equals(farm.id).toArray(),lots:await db.lots.where('farm').equals(farm.id).toArray(),paddocks:await db.paddocks.where('farm').equals(farm.id).toArray(),owners:await db.owners.where('farm').equals(farm.id).toArray()})).subscribe({next(data){animals=data.animals;lots=data.lots;paddocks=data.paddocks;owners=data.owners;loading=false;},error(){error='No se pudieron cargar los datos del parto.';loading=false;}});
		}catch(cause){error=errorMessage(cause);loading=false;}})();
		return()=>{disposed=true;subscription?.unsubscribe();};
	});
	async function save(event:SubmitEvent){
		event.preventDefault();if(!mother || saving || saved || !canWrite)return;saving=true;error='';
		try{
			if(editing && await reviewFinancialPending('calvings',id)){saved=true;message='Este parto ya fue confirmado. Se conservan sus crías y su historial.';return;}
			for(const row of rows)if(row.mode==='new' && !row.provisional && !row.tag?.trim())throw new Error('Indicá el arete de cada cría nueva o elegí identificación provisional.');
			const pending=await db.outbox.toArray();const related=new Set([mother.id,...rows.filter((r)=>r.mode==='existing').map((r)=>r.animal!)]);
			if(pending.some((r)=>r.collection==='animals' && related.has(r.record_id)))throw new Error('Sincronizá las fichas pendientes de la madre y las crías antes de registrar el parto.');
			const data=validateCalving({id,farm:mother.farm,mother:mother.id,date,delivery,maternal_status:maternalStatus,mother_version:mother.updated_at,notes,calves:rows.map(({key,provisional,query,...r})=>({...r,tag:provisional?'':r.tag})),location:{change_mother_lot:changeLot,mother_lot:motherLot||null,change_mother_paddock:changePaddock,mother_paddock:motherPaddock||null,calf_lot:calfLot||null,calf_paddock:calfPaddock||null,calf_owner:calfOwner||null}},mother,animals,farmDate());
			if($currentFarm?.id!==mother.farm)throw new Error('La finca cambió. Volvé a abrir el formulario.');
			await enqueue('calvings',{...data});saved=true;message='Parto guardado. El servidor confirmará juntos el evento, las crías y los cambios elegidos. Consultá su estado en el detalle.';
		}catch(cause){error=errorMessage(cause);}finally{saving=false;}
	}
	async function discard(){if(saving)return;saving=true;try{const confirmed=await reviewFinancialPending('calvings',id,true);saved=true;editing=false;discarded=!confirmed;message=confirmed?'El parto ya estaba confirmado y se conservó.':'Se descartó el pendiente sin confirmar. No se crearon crías ni se cambió la madre.';}catch(cause){error=errorMessage(cause);}finally{saving=false;}}
</script>
<svelte:head><title>Registrar parto · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-5"><PageHeader title="Registrar parto y crías" eyebrow="Reproducción del hato" description="Vinculá una cría existente o registrá las nuevas junto con el parto de su madre." backHref="/reproduction/calvings" backLabel="Historial de partos" /><Notice tone="error" message={error} />
{#if loading}<p class="empty-state">Cargando…</p>{:else if !canWrite}<Notice tone="warning" message="El registro de partos requiere un técnico o administrador." />{:else if saved}<Notice tone="success" message={message} /><a class="action-button" href="/reproduction/calvings/{id}">Ver detalle y confirmación</a>{:else if !mother}<section class="form-section"><h2 class="section-title mb-4">Seleccionar madre</h2><TagSearch onSelect={chooseMother} sex="H" filterStatus={null} label="Buscar madre por arete o nombre" /></section>{:else}
{#if editing}<Notice tone="warning" message="Se consultó la ficha actual de la madre. Revisá el parto pendiente antes de guardarlo nuevamente." />{/if}
<form onsubmit={save} class="space-y-5"><fieldset disabled={saving} class="space-y-5">
<section class="form-section space-y-4"><div class="flex flex-wrap items-center justify-between gap-3"><div><p class="eyebrow">Madre</p><h2 class="section-title">{mother.tag} · {mother.name || 'Sin nombre'}</h2></div><button type="button" class="quiet-button" onclick={()=>mother=null}>Cambiar madre</button></div><div class="form-grid"><label class="field-label">Fecha del parto *<input class="field" type="date" max={farmDate()} bind:value={date} required /></label><label class="field-label">Cómo fue el parto<select class="field" bind:value={delivery}>{#each Object.entries(deliveryLabels) as [value,label]}<option value={value}>{label}</option>{/each}</select></label></div></section>
<section class="form-section space-y-4"><div class="flex flex-wrap items-center justify-between gap-3"><h2 class="section-title">Crías · {rows.length}</h2><button type="button" class="quiet-button" disabled={rows.length>=5} onclick={()=>rows.push(newRow())}>Agregar otra cría / gemelo</button></div>
{#each rows as row,index (row.key)}<div class="rounded-xl border p-4 space-y-4"><div class="flex flex-wrap items-center justify-between gap-2"><h3 class="font-semibold">Cría {index+1}</h3>{#if rows.length>1}<button type="button" class="quiet-button" onclick={()=>rows=rows.filter((r)=>r.key!==row.key)}>Quitar cría {index+1}</button>{/if}</div><label class="field-label">Registro de la cría {index+1}<select class="field" bind:value={row.mode} onchange={()=>changeMode(row)}><option value="new">Registrar cría nueva</option><option value="existing">Vincular cría ya registrada</option><option value="stillborn">Nacido muerto</option></select></label>
{#if row.mode==='existing'}<label class="field-label">Buscar cría {index+1}<input class="field" bind:value={row.query} placeholder="Arete o nombre" /></label><label class="field-label">Cría existente {index+1} *<select class="field" bind:value={row.animal} required><option value={null}>Elegí la cría</option>{#each choices(row) as calf}<option value={calf.id}>{calf.tag} · {calf.name || 'Sin nombre'}</option>{/each}</select></label><p class="field-help">Se vincula su ficha con esta madre y nacimiento. Conserva su propietario, lote, potrero y estado; no se crea otro animal.</p>
{:else}<div class="form-grid"><label class="field-label">Sexo de la cría {index+1}<select class="field" bind:value={row.sex}><option value="H">Hembra</option><option value="M">Macho</option>{#if row.mode==='stillborn'}<option value="unknown">Sin determinar</option>{/if}</select></label>{#if row.mode==='new'}<label class="field-label">Arete de la cría {index+1}<input class="field" maxlength="50" bind:value={row.tag} disabled={row.provisional} required={!row.provisional} /></label>{/if}<label class="field-label">Nombre de la cría {index+1} (opcional)<input class="field" maxlength="150" bind:value={row.name} /></label></div>{#if row.mode==='new'}<label class="flex items-start gap-2 text-sm"><input type="checkbox" class="mt-1" bind:checked={row.provisional} /><span>No tiene arete: usar identificación provisional TEMP. Podrás cambiarla después en su ficha.</span></label>{:else}<Notice message="Esta cría queda en el historial del parto y no se agrega al hato activo." />{/if}{/if}
<label class="field-label">Peso al nacer de la cría {index+1} (kg, opcional)<input class="field" inputmode="decimal" bind:value={row.weight_kg} placeholder="Cantidad en kg" /></label></div>{/each}</section>
<section class="form-section space-y-4"><h2 class="section-title">Situación de la madre</h2><label class="field-label">Categoría después del parto<select class="field" bind:value={maternalStatus}>{#each Object.entries(maternalLabels) as [value,label]}<option value={value}>{label}</option>{/each}</select></label><p class="field-help">Elegí ordeño si la vaca se incorpora a producción, o vaca con cría si queda criando. No se inventan registros de leche.</p><label class="flex items-center gap-2"><input type="checkbox" bind:checked={changeLot} />Cambiar el lote de la madre</label>{#if changeLot}<label class="field-label">Nuevo lote de la madre<select class="field" bind:value={motherLot}><option value="">Sin lote</option>{#each lots as l}<option value={l.id}>{l.name}</option>{/each}</select></label>{/if}<label class="flex items-center gap-2"><input type="checkbox" bind:checked={changePaddock} />Trasladar la madre de potrero</label>{#if changePaddock}<label class="field-label">Potrero de destino de la madre *<select class="field" bind:value={motherPaddock} required><option value="">Elegí destino</option>{#each paddocks as p}<option value={p.id}>{p.name}</option>{/each}</select><span class="field-help">Se registra el movimiento con la fecha del parto.</span></label>{/if}</section>
{#if hasNew}<section class="form-section space-y-4"><h2 class="section-title">Datos iniciales de las crías nuevas</h2><p class="field-help">Estas opciones se aplican solo a los animales que vas a crear. Las crías existentes conservan su ubicación y propietario.</p><div class="form-grid"><label class="field-label">Propietario de crías nuevas<select class="field" bind:value={calfOwner}><option value="">Sin asignar</option>{#each owners as o}<option value={o.id}>{o.name}</option>{/each}</select></label><label class="field-label">Lote de crías nuevas<select class="field" bind:value={calfLot}><option value="">Sin lote</option>{#each lots as l}<option value={l.id}>{l.name}</option>{/each}</select></label><label class="field-label">Potrero de crías nuevas<select class="field" bind:value={calfPaddock}><option value="">Sin asignar</option>{#each paddocks as p}<option value={p.id}>{p.name}</option>{/each}</select></label></div></section>{/if}
<label class="field-label">Observaciones del parto<textarea class="field" maxlength="1000" bind:value={notes}></textarea></label>
</fieldset><p class="field-help">Hasta confirmar la sincronización, el parto queda pendiente. El servidor aplica el evento, las crías y los cambios elegidos en una sola operación.</p><div class="form-actions"><button class="action-button" disabled={saving}>{saving?'Guardando…':'Guardar parto y crías'}</button>{#if editing}<button type="button" class="quiet-button" disabled={saving} onclick={discard}>Descartar pendiente sin confirmar</button>{/if}</div></form>{/if}</div>

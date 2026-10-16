<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { Plus, Trash2 } from 'lucide-svelte';
	import { db, type Animal, type AnimalAgreement, type Weighing } from '$lib/db';
	import { agreementKinds, agreementSettlement, moneyLabel, validateAgreement } from '$lib/agreements';
	import { farmDate } from '$lib/dates';
	import { errorMessage } from '$lib/forms';
	import { enqueue } from '$lib/sync';
	import { currentFarm } from '$lib/stores';
	import PageHeader from './PageHeader.svelte';
	import Notice from './Notice.svelte';
	let { edit = false }: { edit?: boolean } = $props();
	let draft = $state<AnimalAgreement>({ id: '', farm: '', title: '', owner_name: '', partner_name: '', external_farm: '', kind: 'weight_gain', currency: 'NIO', owner_share: '50.00', start_date: farmDate(), end_date: null, status: 'active', notes: '', animals: [], expenses: [] });
	let animals = $state<Animal[]>([]);
	let weights = $state<Weighing[]>([]);
	let others = $state<AnimalAgreement[]>([]);
	let query = $state(''); let loading = $state(true); let saving = $state(false); let saved = $state(false); let error = $state(''); let settle = $state(false); let ownerNames = $state<Map<string,string>>(new Map());
	let lastFinancialSignature = '';
	$effect(() => {
		const signature = JSON.stringify([draft.kind, draft.owner_share, draft.animals, draft.expenses]);
		if (signature !== lastFinancialSignature) { draft.accept_loss = false; lastFinancialSignature = signature; }
	});
	const canEdit = $derived($currentFarm?.role === 'admin');
	const locked = $derived(draft.status === 'settled');
	const unavailable = $derived(new Set(others.filter((a) => a.id !== draft.id && a.status === 'active').flatMap((a) => a.animals.map((r) => r.animal))));
	const choices = $derived(animals.filter((a) => a.status === 'active' && !unavailable.has(a.id) && !draft.animals.some((r) => r.animal === a.id) && `${a.tag} ${a.name}`.toLowerCase().includes(query.trim().toLowerCase())).sort((a,b) => a.tag.localeCompare(b.tag,'es',{numeric:true})).slice(0,20));
	const preview = $derived.by(() => {
		if (!draft.animals.length) return null;
		try { return agreementSettlement(draft); } catch { return null; }
	});
	onMount(async () => {
		if (!$currentFarm || !canEdit) { loading = false; return; }
		try {
			[animals, weights, others] = await Promise.all([db.animals.where('farm').equals($currentFarm.id).toArray(), db.weighings.toArray(), db.agreements.where('farm').equals($currentFarm.id).toArray()]);
			ownerNames = new Map((await db.owners.where('farm').equals($currentFarm.id).toArray()).map((o) => [o.id,o.name]));
			if (edit) {
				const record = others.find((a) => a.id === page.params.id);
				if (!record) throw new Error('Acuerdo no disponible. Sincronizá la finca y volvé a intentar.');
				draft = $state.snapshot(record);
			} else {
				draft.id = crypto.randomUUID(); draft.farm = $currentFarm.id;
				const animal = animals.find((a) => a.id === page.url.searchParams.get('animal'));
				if (animal && animal.status === 'active' && !unavailable.has(animal.id)) addAnimal(animal);
			}
		} catch (cause) { error = errorMessage(cause); } finally { loading = false; }
	});
	function addAnimal(animal: Animal) {
		if (draft.animals.some((row) => row.animal === animal.id)) return;
		draft.animals.push({ animal: animal.id, tag: animal.tag, name: animal.name, initial_weight: null, final_weight: null, price_per_kg: null, final_date: null });
		if (!draft.owner_name && animal.owner) draft.owner_name = ownerNames.get(animal.owner) ?? '';
	}
	function useWeight(animal: string, final: boolean) {
		const row = draft.animals.find((a) => a.animal === animal);
		if (!row) return;
		const record = weights.filter((w) => w.animal === animal && w.date <= (final ? draft.end_date || farmDate() : draft.start_date) && (!final || w.date >= draft.start_date)).sort((a,b) => b.date.localeCompare(a.date) || (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))[0];
		if (!record) { error = 'No hay un pesaje registrado dentro de ese periodo. Podés ingresar el peso manualmente.'; return; }
		if (final) { row.final_weight = record.weight_kg; row.final_date = record.date; } else row.initial_weight = record.weight_kg;
		error = '';
	}
	function addExpense() {
		draft.expenses.push({ id: crypto.randomUUID(), date: farmDate(), concept: '', amount: '', paid_by: 'owner', animal: null });
	}
	async function save(event: SubmitEvent) {
		event.preventDefault(); if (saving || saved || locked || !canEdit) return;
		saving = true; error = '';
		try {
			const data = validateAgreement($state.snapshot(draft), settle);
			if (others.some((a) => a.id !== draft.id && a.status === 'active' && a.animals.some((r) => data.animals.some((row) => row.animal === r.animal)))) throw new Error('Hay un animal asignado a otro acuerdo en curso.');
			await enqueue('agreements', { ...data });
			saved = true;
		} catch (cause) { error = errorMessage(cause); } finally { saving = false; }
	}
</script>

<svelte:head><title>{edit ? 'Editar acuerdo' : 'Nuevo acuerdo'} · Bovinonic</title></svelte:head>
<div class="workspace-page space-y-6">
	<PageHeader title={edit ? 'Actualizar acuerdo' : 'Animales en otra finca'} eyebrow="Acuerdos y estadías" description="Registrá la entrega, quién cuida los animales y las condiciones de reparto o pasto alquilado. La propiedad y el lote de manejo se conservan por separado." backHref={edit ? `/agreements/${page.params.id}` : '/agreements'} backLabel="Volver a acuerdos" />
	<Notice tone="error" message={error} />
	{#if !canEdit}<Notice tone="warning" message="Los acuerdos y sus liquidaciones requieren el rol de administrador." />
	{:else if loading}<p class="empty-state">Cargando datos del hato…</p>
	{:else if locked}<Notice message="Este acuerdo ya fue liquidado. Se conserva como historial y no se puede editar." /><a class="quiet-button" href="/agreements/{draft.id}">Ver liquidación</a>
	{:else if draft.id}
	<form onsubmit={save} class="space-y-6">
		<fieldset disabled={saving || saved} class="space-y-6">
			<section class="panel space-y-5 p-5 sm:p-6">
				<h2 class="section-title">Personas y condiciones</h2>
				<div class="form-grid">
					<label class="field-label">Nombre del acuerdo *<input class="field" bind:value={draft.title} maxlength="150" placeholder="Ej. Terneros a medias · Don Juan" required /></label>
					<label class="field-label">Modalidad<select class="field" bind:value={draft.kind}>{#each Object.entries(agreementKinds) as [value,label]}<option {value}>{label}</option>{/each}</select></label>
					<label class="field-label">Propietario de los animales *<input class="field" bind:value={draft.owner_name} maxlength="150" required /></label>
					<label class="field-label">Responsable en la otra finca *<input class="field" bind:value={draft.partner_name} maxlength="150" required /></label>
					<label class="field-label">Finca donde permanecen *<input class="field" bind:value={draft.external_farm} maxlength="150" required /><span class="field-help">Es una ubicación externa; los animales siguen en tu inventario.</span></label>
					<label class="field-label">Fecha de entrega *<input type="date" class="field" bind:value={draft.start_date} max={farmDate()} required /></label>
					<label class="field-label">Moneda del acuerdo<select class="field" bind:value={draft.currency}><option value="NIO">Córdobas (NIO)</option><option value="USD">Dólares (USD)</option></select><span class="field-help">Todos los precios y gastos usan esta moneda. Cambiarla no convierte importes.</span></label>
					{#if draft.kind !== 'pasture'}<label class="field-label">Parte del propietario (%) *<input class="field" bind:value={draft.owner_share} inputmode="decimal" required /><span class="field-help">La otra persona recibe {Number.isFinite(Number(draft.owner_share.replace(',','.'))) ? (100-Number(draft.owner_share.replace(',','.'))).toFixed(2) : '—'} %. Se reparte después de descontar gastos.</span></label>{/if}
				</div>
				<label class="field-label">Condiciones y observaciones<textarea class="field min-h-24" bind:value={draft.notes} maxlength="2000" placeholder="Condiciones acordadas, entrega y devolución…"></textarea></label>
				<Notice message={draft.kind === 'weight_gain' ? 'Se reparte el valor de los kilos ganados, menos los gastos. El valor del peso inicial corresponde al propietario. Todos los pesos están en kg y el precio es por kg.' : draft.kind === 'pasture' ? 'Registrá el alquiler y otros gastos con quién los pagó. No se reparte la ganancia del animal: el responsable recupera los gastos que haya adelantado.' : draft.kind === 'offspring' ? 'Seleccioná las crías cuyo valor de venta se repartirá. Esta modalidad reparte dinero de su venta, no asigna crías físicamente ni registra partos.' : 'Se reparte el valor completo de la venta de los animales seleccionados, después de descontar los gastos.'} />
			</section>
			<section class="panel space-y-5 p-5 sm:p-6">
				<h2 class="section-title">Animales del acuerdo · {draft.animals.length}</h2>
				<p class="field-help">{draft.kind === 'pasture' ? 'Los animales siguen en tu inventario durante esta estadía. Registrá el alquiler y otros importes efectivamente pagados en la sección de gastos.' : 'El peso de entrega se conserva en este acuerdo aunque registres nuevos pesajes. Si se liquidan por separado, podés crear un acuerdo para cada animal.'}</p>
				<label class="field-label">Buscar animal para agregar<input class="field" bind:value={query} placeholder="Arete o nombre…" /></label>
				<div class="max-h-60 overflow-y-auto rounded-xl border"><ul class="divide-y">{#each choices as animal}<li><button type="button" class="flex min-h-12 w-full items-center justify-between gap-3 p-3 text-left text-sm" onclick={() => addAnimal(animal)}><span>{animal.tag} · {animal.name || 'Sin nombre'}</span><Plus class="h-4 w-4 shrink-0" /></button></li>{:else}<li class="p-4 text-sm text-[#819174]">No hay coincidencias disponibles. Se excluyen animales inactivos y los que están en otro acuerdo en curso.</li>{/each}</ul></div>
				{#each draft.animals as row (row.animal)}
					<div class="form-section">
						<div class="flex items-center justify-between gap-3"><h3 class="text-sm font-semibold">{row.tag} · {row.name || 'Sin nombre'}</h3><button type="button" aria-label="Quitar {row.tag}" class="p-2 text-red-700" onclick={() => { if (draft.expenses.some((e) => e.animal === row.animal)) error = 'Reasigná o quitá sus gastos antes de retirar el animal.'; else draft.animals = draft.animals.filter((a) => a.animal !== row.animal); }}><Trash2 class="h-4 w-4" /></button></div>
						{#if draft.kind !== 'pasture'}<div class="form-grid">
							{#if draft.kind === 'weight_gain'}<label class="field-label">Peso de entrega (kg) *<input class="field" inputmode="decimal" bind:value={row.initial_weight} required /><button class="back-link mb-0" type="button" onclick={() => useWeight(row.animal,false)}>Usar último pesaje anterior a la entrega</button></label>{/if}
							<label class="field-label">Peso final (kg){settle ? ' *' : ''}<input class="field" inputmode="decimal" bind:value={row.final_weight} required={settle} /><button class="back-link mb-0" type="button" onclick={() => useWeight(row.animal,true)}>Usar último pesaje del periodo</button></label>
							<label class="field-label">Precio de venta por kg ({draft.currency}){settle ? ' *' : ''}<input class="field" inputmode="decimal" bind:value={row.price_per_kg} required={settle} /></label>
							<label class="field-label">Fecha final / venta{settle ? ' *' : ''}<input class="field" type="date" bind:value={row.final_date} min={draft.start_date} max={draft.end_date || farmDate()} required={settle} /></label>
						</div>{/if}
					</div>
				{/each}
			</section>
			<section class="panel space-y-5 p-5 sm:p-6">
				<div class="flex flex-wrap items-center justify-between gap-3"><h2 class="section-title">Gastos pagados · {draft.expenses.length}</h2><button class="quiet-button" type="button" onclick={addExpense}><Plus class="h-4 w-4" />Agregar gasto</button></div>
				<p class="field-help">{draft.kind === 'pasture' ? 'Anotá alquiler, medicamentos, transporte u otros gastos ya pagados. Si el responsable adelantó dinero, su importe se muestra como reembolso.' : 'Medicamentos, pasto, transporte u otros gastos acordados. Se descuentan antes del reparto y se reconoce ese importe a quien lo pagó.'} No se importan automáticamente los tratamientos sanitarios.</p>
				{#each draft.expenses as expense,index (expense.id)}<div class="form-section"><div class="flex items-center justify-between"><p class="eyebrow">Gasto {index+1}</p><button type="button" aria-label="Quitar gasto {index+1}" class="p-2 text-red-700" onclick={() => draft.expenses = draft.expenses.filter((e) => e.id !== expense.id)}><Trash2 class="h-4 w-4" /></button></div><div class="form-grid">
					<label class="field-label">Concepto *<input class="field" bind:value={expense.concept} maxlength="200" placeholder="Ej. Medicamentos" required /></label>
					<label class="field-label">Importe ({draft.currency}) *<input class="field" bind:value={expense.amount} inputmode="decimal" required /></label>
					<label class="field-label">Quién lo pagó<select class="field" bind:value={expense.paid_by}><option value="owner">Propietario · {draft.owner_name || 'Sin nombre'}</option><option value="partner">Responsable · {draft.partner_name || 'Sin nombre'}</option></select></label>
					<label class="field-label">Fecha del gasto *<input type="date" class="field" bind:value={expense.date} min={draft.start_date} max={draft.end_date || farmDate()} required /></label>
					<label class="field-label">Corresponde a<select class="field" bind:value={expense.animal}><option value={null}>Todo el acuerdo</option>{#each draft.animals as row}<option value={row.animal}>{row.tag}</option>{/each}</select></label>
				</div></div>{:else}<p class="empty-state">No hay gastos registrados. Agregalos antes de cerrar la liquidación.</p>{/each}
			</section>
			<section class="panel space-y-5 p-5 sm:p-6"><h2 class="section-title">Revisar y liquidar</h2><label class="flex items-center gap-3 text-sm font-semibold"><input type="checkbox" bind:checked={settle} onchange={(event) => { if (!event.currentTarget.checked) draft.end_date = null; }} />Cerrar el acuerdo y guardar su liquidación</label>{#if settle}<label class="field-label">Fecha de liquidación *<input type="date" class="field" bind:value={draft.end_date} min={draft.start_date} max={farmDate()} required /></label><Notice tone="warning" message="Al liquidar se bloquean los datos y gastos de este acuerdo. No cambia el propietario ni marca los animales como vendidos; revisá esos datos en sus fichas." />{/if}
				{#if preview}<div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
					{#each (draft.kind === 'pasture' ? [{label:'Gastos de la estadía',value:preview.expenses},{label:'Pagados por el propietario',value:preview.owner_paid},{label:'A reembolsar al responsable',value:preview.partner_reimbursement}] : [{label:'Valor de venta total',value:preview.sale_value},{label:'Valor inicial del propietario',value:preview.initial_value},{label:'Valor a repartir antes de gastos',value:preview.gain_value},{label:'Gastos a reembolsar',value:preview.expenses},{label:'Ganancia neta a repartir',value:preview.net_gain},{label:`Parte de ${draft.owner_name || 'propietario'}`,value:preview.owner_part},{label:`Parte de ${draft.partner_name || 'responsable'}`,value:preview.partner_part},{label:'Total correspondiente al propietario',value:preview.owner_total},{label:'Total correspondiente al responsable',value:preview.partner_total}]) as item}<div class="rounded-xl border bg-[#f5f7ef] p-4"><p class="field-help">{item.label}</p><p class="mt-2 text-lg font-semibold">{moneyLabel(item.value,draft.currency)}</p></div>{/each}
				</div><p class="field-help">Vista previa. La liquidación se verifica de nuevo en el servidor al sincronizar. Los totales incluyen los reembolsos; no son pagos realizados.</p>
				{#if Number(preview.net_gain ?? 0) < 0}<Notice tone="warning" message="El peso disminuyó o los gastos superan la ganancia. El saldo es negativo y los porcentajes también reparten esa pérdida." /><label class="flex items-center gap-3 text-sm"><input type="checkbox" bind:checked={draft.accept_loss} />Confirmo el saldo negativo y su reparto según este acuerdo.</label>{/if}
				{:else}<p class="empty-state">Completá los pesos finales, los precios y los gastos para calcular la liquidación.</p>{/if}
			</section>
		</fieldset>
		<Notice tone="error" message={error} />{#if saved}<Notice tone="success" message="Acuerdo guardado en este dispositivo. El envío es automático; revisá su estado en la barra superior." />{/if}
		<div class="form-actions"><button type="submit" class="action-button" disabled={saving || saved || !draft.animals.length}>{saving ? 'Guardando…' : saved ? 'Guardado' : settle ? 'Confirmar liquidación y cerrar' : 'Guardar acuerdo en curso'}</button>{#if saved}<a class="quiet-button" href="/agreements/{draft.id}">Ver acuerdo</a>{:else}<a class="quiet-button" href="/agreements">Cancelar</a>{/if}</div>
	</form>{/if}
</div>

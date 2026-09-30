<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import TagSearch from '$lib/components/TagSearch.svelte';
	import { db, type Animal, type Brand, type Owner, type Paddock } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueue } from '$lib/sync';

	const CATEGORIES = [
		{ value: 'calf', label: 'Ternero/a' },
		{ value: 'heifer', label: 'Novillo/a' },
		{ value: 'cow_lactating', label: 'Vaca en ordeño' },
		{ value: 'cow_dry', label: 'Vaca seca' },
		{ value: 'bull', label: 'Toro reproductor' }
	] as const;

	let tag = $state('');
	let name = $state('');
	let sex = $state<'M' | 'H'>('H');
	let category = $state<(typeof CATEGORIES)[number]['value']>('calf');
	let birthDate = $state('');
	let mother = $state<Animal | null>(null);
	let father = $state<Animal | null>(null);
	let paddockId = $state('');
	let ownerId = $state('');
	let brandId = $state('');

	let owners = $state<Owner[]>([]);
	let paddocks = $state<Paddock[]>([]);
	let brands = $state<Brand[]>([]);
	let error = $state('');
	let saved = $state(false);
	let checking = $state(false);

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm) {
			await goto('/');
			return;
		}
		owners = await db.owners.where('farm').equals(farm.id).toArray();
		paddocks = await db.paddocks.where('farm').equals(farm.id).toArray();
		brands = await db.brands.where('farm').equals(farm.id).toArray();
	});

	let suggestedBrand = $derived(
		ownerId ? (brands.find((b) => b.title_owner === ownerId) ?? null) : null
	);

	$effect(() => {
		if (suggestedBrand && !brandId) {
			brandId = suggestedBrand.id;
		}
	});

	async function save() {
		const farm = $currentFarm;
		if (!farm) return;
		error = '';
		const cleanTag = tag.trim();
		if (!cleanTag) {
			error = 'El arete es obligatorio.';
			return;
		}
		checking = true;
		const duplicate = await db.animals
			.where('tag')
			.equalsIgnoreCase(cleanTag)
			.first();
		checking = false;
		if (duplicate) {
			error = `El arete ${cleanTag} ya existe en este dispositivo (${duplicate.name || duplicate.tag}).`;
			return;
		}

		await enqueue('animals', {
			id: crypto.randomUUID(),
			tag: cleanTag,
			name: name.trim(),
			sex,
			category,
			birth_date: birthDate || null,
			mother: mother?.id ?? null,
			father: father?.id ?? null,
			paddock: paddockId || null,
			owner: ownerId || null,
			brand: brandId || null,
			status: 'active'
		});
		saved = true;
		setTimeout(() => goto('/'), 1000);
	}
</script>

<svelte:head><title>Nuevo animal · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Nuevo animal</h1>

	<label class="flex flex-col gap-1 font-bold">
		Arete (único nacional) *
		<input
			bind:value={tag}
			class="h-14 rounded-md border-2 border-black px-4 text-xl uppercase"
			placeholder="NI-0000"
		/>
	</label>

	<label class="flex flex-col gap-1 font-bold">
		Nombre
		<input
			bind:value={name}
			class="h-14 rounded-md border-2 border-black px-4 text-xl"
		/>
	</label>

	<div class="grid grid-cols-2 gap-2">
		<button
			type="button"
			onclick={() => (sex = 'H')}
			class="h-14 rounded-md border-2 border-black text-xl font-extrabold {sex === 'H'
				? 'bg-black text-white'
				: 'bg-white'}"
		>
			Hembra
		</button>
		<button
			type="button"
			onclick={() => (sex = 'M')}
			class="h-14 rounded-md border-2 border-black text-xl font-extrabold {sex === 'M'
				? 'bg-black text-white'
				: 'bg-white'}"
		>
			Macho
		</button>
	</div>

	<label class="flex flex-col gap-1 font-bold">
		Categoría
		<select
			bind:value={category}
			class="h-14 rounded-md border-2 border-black bg-white px-4 text-xl"
		>
			{#each CATEGORIES as c}
				<option value={c.value}>{c.label}</option>
			{/each}
		</select>
	</label>

	<label class="flex flex-col gap-1 font-bold">
		Fecha de nacimiento
		<input
			bind:value={birthDate}
			type="date"
			class="h-14 rounded-md border-2 border-black px-4 text-xl"
		/>
	</label>

	<div class="rounded-md border-2 border-black p-3">
		<p class="mb-2 font-bold">Madre {mother ? `: ${mother.tag} ${mother.name}` : '(opcional)'}</p>
		{#if mother}
			<button
				type="button"
				onclick={() => (mother = null)}
				class="h-12 w-full rounded-md border-2 border-black font-bold"
			>
				Quitar madre
			</button>
		{:else}
			<TagSearch onSelect={(a) => (mother = a)} sex="H" />
		{/if}
	</div>

	<div class="rounded-md border-2 border-black p-3">
		<p class="mb-2 font-bold">Padre {father ? `: ${father.tag} ${father.name}` : '(opcional)'}</p>
		{#if father}
			<button
				type="button"
				onclick={() => (father = null)}
				class="h-12 w-full rounded-md border-2 border-black font-bold"
			>
				Quitar padre
			</button>
		{:else}
			<TagSearch onSelect={(a) => (father = a)} sex="M" />
		{/if}
	</div>

	<label class="flex flex-col gap-1 font-bold">
		Potrero
		<select
			bind:value={paddockId}
			class="h-14 rounded-md border-2 border-black bg-white px-4 text-xl"
		>
			<option value="">Sin potrero</option>
			{#each paddocks as p (p.id)}
				<option value={p.id}>{p.name}</option>
			{/each}
		</select>
	</label>

	<label class="flex flex-col gap-1 font-bold">
		Propietario
		<select
			bind:value={ownerId}
			class="h-14 rounded-md border-2 border-black bg-white px-4 text-xl"
		>
			<option value="">Sin propietario</option>
			{#each owners as o (o.id)}
				<option value={o.id}>{o.name}</option>
			{/each}
		</select>
	</label>

	<label class="flex flex-col gap-1 font-bold">
		Fierro {suggestedBrand ? '(sugerido del propietario)' : '(vacío = orejano)'}
		<select
			bind:value={brandId}
			class="h-14 rounded-md border-2 border-black bg-white px-4 text-xl"
		>
			<option value="">Orejano (sin fierro)</option>
			{#each brands as b (b.id)}
				<option value={b.id}>{b.code}</option>
			{/each}
		</select>
	</label>

	{#if error}
		<p class="rounded-md border-2 border-red-700 bg-red-50 p-3 font-bold text-red-700">
			{error}
		</p>
	{/if}

	<button
		type="button"
		onclick={save}
		disabled={saved || checking}
		class="h-14 w-full rounded-md bg-green-700 text-xl font-extrabold text-white disabled:opacity-50"
	>
		{saved ? 'Guardado ✓' : checking ? 'Verificando…' : 'Guardar animal'}
	</button>

	<button
		type="button"
		onclick={() => goto('/')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Cancelar
	</button>
</div>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

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

	let animal = $state<Animal | null>(null);
	let category = $state<Animal['category']>('calf');
	let name = $state('');
	let paddockId = $state('');
	let ownerId = $state('');
	let brandId = $state('');
	let owners = $state<Owner[]>([]);
	let paddocks = $state<Paddock[]>([]);
	let brands = $state<Brand[]>([]);
	let saved = $state(false);
	let notFound = $state(false);

	onMount(async () => {
		const farm = $currentFarm;
		const id = page.params.id;
		if (!farm || !id) {
			await goto('/');
			return;
		}
		const found = await db.animals.get(id);
		if (!found) {
			notFound = true;
			return;
		}
		animal = found;
		name = found.name;
		category = found.category;
		paddockId = found.paddock ?? '';
		ownerId = found.owner ?? '';
		brandId = found.brand ?? '';
		owners = await db.owners.where('farm').equals(farm.id).toArray();
		paddocks = await db.paddocks.where('farm').equals(farm.id).toArray();
		brands = await db.brands.where('farm').equals(farm.id).toArray();
	});

	let suggestedBrand = $derived(
		ownerId ? (brands.find((b) => b.title_owner === ownerId) ?? null) : null
	);

	async function save() {
		if (!animal) return;
		await enqueue('animals', {
			...animal,
			name: name.trim(),
			category,
			paddock: paddockId || null,
			owner: ownerId || null,
			brand: brandId || null
		});
		saved = true;
		const targetId = animal.id;
		setTimeout(() => goto(`/animals/${targetId}`), 900);
	}
</script>

<svelte:head><title>Editar {animal?.tag ?? ''} · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	{#if notFound}
		<p class="rounded-md border-2 border-red-700 bg-red-50 p-4 font-bold text-red-700">
			Animal no encontrado en este dispositivo.
		</p>
	{:else if animal}
		<h1 class="text-2xl font-extrabold">Editar {animal.tag}</h1>

		<label class="flex flex-col gap-1 font-bold">
			Nombre
			<input
				bind:value={name}
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

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
			Fierro {suggestedBrand && suggestedBrand.id !== brandId ? `(sugerido: ${suggestedBrand.code})` : '(vacío = orejano)'}
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

		<button
			type="button"
			onclick={save}
			disabled={saved}
			class="h-14 w-full rounded-md bg-green-700 text-xl font-extrabold text-white disabled:opacity-50"
		>
			{saved ? 'Guardado ✓' : 'Guardar cambios'}
		</button>
	{/if}

	<button
		type="button"
		onclick={() => goto(`/animals/${page.params.id}`)}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Cancelar
	</button>
</div>

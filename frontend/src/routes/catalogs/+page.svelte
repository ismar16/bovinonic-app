<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { db, type Brand, type Owner, type Paddock } from '$lib/db';
	import { currentFarm } from '$lib/stores';
	import { enqueue } from '$lib/sync';

	let owners = $state<Owner[]>([]);
	let paddocks = $state<Paddock[]>([]);
	let brands = $state<Brand[]>([]);

	let newPaddock = $state('');
	let newOwner = $state('');
	let newBrandCode = $state('');
	let newBrandOwner = $state('');
	let message = $state('');

	async function load() {
		const farm = $currentFarm;
		if (!farm) return;
		owners = await db.owners.where('farm').equals(farm.id).toArray();
		paddocks = await db.paddocks.where('farm').equals(farm.id).toArray();
		brands = await db.brands.where('farm').equals(farm.id).toArray();
	}

	onMount(async () => {
		const farm = $currentFarm;
		if (!farm || farm.role !== 'admin') {
			await goto('/');
			return;
		}
		await load();
	});

	async function addPaddock() {
		const farm = $currentFarm;
		const name = newPaddock.trim();
		if (!farm || !name) return;
		if (paddocks.some((p) => p.name.toLowerCase() === name.toLowerCase())) {
			message = `Ya existe el potrero "${name}".`;
			return;
		}
		message = '';
		await enqueue('paddocks', { id: crypto.randomUUID(), name });
		newPaddock = '';
		await load();
	}

	async function addOwner() {
		const farm = $currentFarm;
		const name = newOwner.trim();
		if (!farm || !name) return;
		message = '';
		await enqueue('owners', { id: crypto.randomUUID(), name, id_number: '', phone: '' });
		newOwner = '';
		await load();
	}

	async function addBrand() {
		const farm = $currentFarm;
		const code = newBrandCode.trim();
		if (!farm || !code) return;
		if (brands.some((b) => b.code.toLowerCase() === code.toLowerCase())) {
			message = `Ya existe el fierro "${code}".`;
			return;
		}
		message = '';
		await enqueue('brands', {
			id: crypto.randomUUID(),
			code,
			title_owner: newBrandOwner || null
		});
		newBrandCode = '';
		newBrandOwner = '';
		await load();
	}
</script>

<svelte:head><title>Catálogos · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-6 pt-4">
	<h1 class="text-2xl font-extrabold">Catálogos</h1>

	{#if message}
		<p class="rounded-md border-2 border-red-700 bg-red-50 p-3 font-bold text-red-700">{message}</p>
	{/if}

	<section class="rounded-md border-2 border-black p-4">
		<h2 class="mb-2 text-xl font-extrabold">Potreros ({paddocks.length})</h2>
		<ul class="mb-3 ml-4 list-disc">
			{#each paddocks as p (p.id)}
				<li>{p.name}</li>
			{/each}
		</ul>
		<div class="flex gap-2">
			<input
				bind:value={newPaddock}
				placeholder="Nombre del potrero"
				class="h-14 flex-1 rounded-md border-2 border-black px-4 text-xl"
			/>
			<button
				type="button"
				onclick={addPaddock}
				class="h-14 rounded-md bg-green-700 px-6 font-extrabold text-white"
			>
				+
			</button>
		</div>
	</section>

	<section class="rounded-md border-2 border-black p-4">
		<h2 class="mb-2 text-xl font-extrabold">Propietarios ({owners.length})</h2>
		<ul class="mb-3 ml-4 list-disc">
			{#each owners as o (o.id)}
				<li>{o.name}</li>
			{/each}
		</ul>
		<div class="flex gap-2">
			<input
				bind:value={newOwner}
				placeholder="Nombre del propietario"
				class="h-14 flex-1 rounded-md border-2 border-black px-4 text-xl"
			/>
			<button
				type="button"
				onclick={addOwner}
				class="h-14 rounded-md bg-green-700 px-6 font-extrabold text-white"
			>
				+
			</button>
		</div>
	</section>

	<section class="rounded-md border-2 border-black p-4">
		<h2 class="mb-2 text-xl font-extrabold">Fierros ({brands.length})</h2>
		<ul class="mb-3 ml-4 list-disc">
			{#each brands as b (b.id)}
				<li>
					{b.code}
					{#if b.title_owner}
						— {owners.find((o) => o.id === b.title_owner)?.name ?? ''}
					{/if}
				</li>
			{/each}
		</ul>
		<div class="flex flex-col gap-2">
			<input
				bind:value={newBrandCode}
				placeholder="Código del fierro"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
			<select
				bind:value={newBrandOwner}
				class="h-14 rounded-md border-2 border-black bg-white px-4 text-xl"
			>
				<option value="">Sin titular</option>
				{#each owners as o (o.id)}
					<option value={o.id}>{o.name}</option>
				{/each}
			</select>
			<button
				type="button"
				onclick={addBrand}
				class="h-14 rounded-md bg-green-700 font-extrabold text-white"
			>
				Agregar fierro
			</button>
		</div>
	</section>

	<button
		type="button"
		onclick={() => goto('/')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

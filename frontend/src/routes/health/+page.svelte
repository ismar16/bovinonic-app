<script lang="ts">
	import { goto } from '$app/navigation';

	import TagSearch from '$lib/components/TagSearch.svelte';
	import type { Animal } from '$lib/db';
	import { enqueue } from '$lib/sync';

	const TYPES = [
		{ value: 'vaccine', label: 'Vacunación' },
		{ value: 'deworming', label: 'Desparasitación' },
		{ value: 'antibiotic', label: 'Antibiótico' },
		{ value: 'vitamin', label: 'Vitamina' }
	] as const;

	let animal = $state<Animal | null>(null);
	let type = $state<(typeof TYPES)[number]['value']>('vaccine');
	let product = $state('');
	let dose = $state('');
	let date = $state(new Date().toISOString().slice(0, 10));
	let withdrawalDays = $state('0');
	let saved = $state(false);
	let inactiveWarning = $state(false);
	let error = $state('');

	function selectAnimal(selected: Animal) {
		animal = selected;
		inactiveWarning = selected.status !== 'active';
	}

	function addDays(isoDate: string, days: number): string {
		const d = new Date(`${isoDate}T00:00:00`);
		d.setDate(d.getDate() + days);
		return d.toISOString().slice(0, 10);
	}

	let days = $derived(Math.max(0, parseInt(withdrawalDays) || 0));
	let withdrawalEnd = $derived(days > 0 ? addDays(date, days) : null);

	async function save() {
		if (!animal) return;
		error = '';
		if (!product.trim()) {
			error = 'El producto es obligatorio.';
			return;
		}
		await enqueue('health_events', {
			id: crypto.randomUUID(),
			animal: animal.id,
			date,
			type,
			product: product.trim(),
			dose: dose.trim(),
			withdrawal_days: days
		});
		saved = true;
		setTimeout(() => {
			animal = null;
			product = '';
			dose = '';
			withdrawalDays = '0';
			saved = false;
			inactiveWarning = false;
		}, 1200);
	}
</script>

<svelte:head><title>Evento sanitario · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Evento sanitario</h1>

	{#if !animal}
		<TagSearch onSelect={selectAnimal} filterStatus={null} category={null} />
	{:else}
		<div class="rounded-md border-2 border-black p-4">
			<p class="text-2xl font-extrabold">{animal.tag}</p>
			<p>{animal.name || 'Sin nombre'}</p>
			{#if inactiveWarning}
				<p class="mt-2 rounded-md border-2 border-yellow-600 bg-yellow-50 p-2 font-bold text-yellow-800">
					Atención: el animal figura como {animal.status}. Se guardará como histórico.
				</p>
			{/if}
		</div>

		<label class="flex flex-col gap-1 font-bold">
			Tipo
			<select
				bind:value={type}
				class="h-14 rounded-md border-2 border-black bg-white px-4 text-xl"
			>
				{#each TYPES as t}
					<option value={t.value}>{t.label}</option>
				{/each}
			</select>
		</label>

		<label class="flex flex-col gap-1 font-bold">
			Producto *
			<input
				bind:value={product}
				placeholder="Ej. Ivermectina 1%"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		<label class="flex flex-col gap-1 font-bold">
			Dosis
			<input
				bind:value={dose}
				placeholder="Ej. 10 ml"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		<label class="flex flex-col gap-1 font-bold">
			Fecha de aplicación
			<input
				bind:value={date}
				type="date"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		<label class="flex flex-col gap-1 font-bold">
			Días de retiro (leche/carne)
			<input
				bind:value={withdrawalDays}
				inputmode="numeric"
				pattern="[0-9]*"
				placeholder="0"
				class="h-16 rounded-md border-2 border-black px-4 text-3xl font-extrabold"
			/>
		</label>

		{#if withdrawalEnd}
			<p class="rounded-md border-2 border-red-700 bg-red-50 p-3 font-bold text-red-700">
				Retiro vigente hasta: {withdrawalEnd} — no consumir ni vender leche/carne de este animal antes de esa fecha.
			</p>
		{/if}

		{#if error}
			<p class="rounded-md border-2 border-red-700 bg-red-50 p-3 font-bold text-red-700">
				{error}
			</p>
		{/if}

		<button
			type="button"
			onclick={save}
			disabled={saved}
			class="h-14 w-full rounded-md bg-green-700 text-xl font-extrabold text-white disabled:opacity-50"
		>
			{saved ? 'Guardado ✓' : 'Guardar evento sanitario'}
		</button>

		<button
			type="button"
			onclick={() => {
				animal = null;
				inactiveWarning = false;
			}}
			class="h-14 w-full rounded-md border-2 border-black font-extrabold"
		>
			Cambiar animal
		</button>
	{/if}

	<button
		type="button"
		onclick={() => goto('/operations')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { db, type Animal, type Weighing } from '$lib/db';
	import TagSearch from '$lib/components/TagSearch.svelte';
	import { enqueue } from '$lib/sync';

	let animal = $state<Animal | null>(null);
	let weight = $state('');
	let date = $state(new Date().toISOString().slice(0, 10));
	let lastWeighing = $state<Weighing | null>(null);
	let saved = $state(false);
	let inactiveWarning = $state(false);

	onMount(() => {
		// page guard placeholder
	});

	async function selectAnimal(selected: Animal) {
		animal = selected;
		inactiveWarning = selected.status !== 'active';
		const history = await db.weighings
			.where('animal')
			.equals(selected.id)
			.sortBy('date');
		lastWeighing = history.length > 0 ? history[history.length - 1] : null;
	}

	let gmd = $derived.by(() => {
		if (!animal || !lastWeighing || !weight) return null;
		const current = parseFloat(weight);
		const previous = parseFloat(lastWeighing.weight_kg);
		const days = Math.max(
			1,
			Math.round(
				(new Date(date).getTime() - new Date(lastWeighing.date).getTime()) /
					86_400_000
			)
		);
		return (current - previous) / days;
	});

	async function save() {
		if (!animal || !weight) return;
		await enqueue('weighings', {
			id: crypto.randomUUID(),
			animal: animal.id,
			date,
			weight_kg: parseFloat(weight).toFixed(2)
		});
		saved = true;
		setTimeout(() => {
			animal = null;
			weight = '';
			lastWeighing = null;
			saved = false;
			inactiveWarning = false;
		}, 1200);
	}
</script>

<svelte:head><title>Pesaje rápido · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Pesaje rápido</h1>

	{#if !animal}
		<TagSearch onSelect={selectAnimal} />
	{:else}
		<div class="rounded-md border-2 border-black p-4">
			<p class="text-2xl font-extrabold">{animal.tag}</p>
			<p>{animal.name || 'Sin nombre'} · {animal.category}</p>
			{#if inactiveWarning}
				<p class="mt-2 rounded-md border-2 border-yellow-600 bg-yellow-50 p-2 font-bold text-yellow-800">
					Atención: el animal figura como {animal.status}. Se guardará como histórico.
				</p>
			{/if}
		</div>

		{#if lastWeighing}
			<p class="text-sm font-bold text-neutral-700">
				Último pesaje: {lastWeighing.weight_kg} kg el {lastWeighing.date}
			</p>
		{:else}
			<p class="text-sm font-bold text-neutral-700">Primer pesaje registrado.</p>
		{/if}

		<label class="flex flex-col gap-1 font-bold">
			Fecha
			<input
				bind:value={date}
				type="date"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		<label class="flex flex-col gap-1 font-bold">
			Peso (kg)
			<input
				bind:value={weight}
				inputmode="decimal"
				pattern="[0-9]*[.]?[0-9]*"
				placeholder="0.00"
				class="h-16 rounded-md border-2 border-black px-4 text-3xl font-extrabold"
			/>
		</label>

		{#if gmd !== null}
			<p
				class="rounded-md border-2 p-3 text-center text-xl font-extrabold {gmd >= 0
					? 'border-green-700 text-green-700'
					: 'border-red-700 text-red-700'}"
			>
				GMD: {gmd.toFixed(2)} kg/día
			</p>
		{/if}

		<Button
			type="button"
			onclick={save}
			disabled={!weight || saved}
			class="h-14 w-full text-xl font-extrabold"
		>
			{saved ? 'Guardado ✓' : 'Guardar pesaje'}
		</Button>

		<button
			type="button"
			onclick={() => {
				animal = null;
				weight = '';
				lastWeighing = null;
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

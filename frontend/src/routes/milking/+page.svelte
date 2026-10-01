<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { goto } from '$app/navigation';

	import TagSearch from '$lib/components/TagSearch.svelte';
	import { db, type Animal } from '$lib/db';
	import { enqueue } from '$lib/sync';

	let animal = $state<Animal | null>(null);
	let shift = $state<'AM' | 'PM'>('AM');
	let liters = $state('');
	let date = $state(new Date().toISOString().slice(0, 10));
	let saved = $state(false);
	let inactiveWarning = $state(false);

	function selectAnimal(selected: Animal) {
		animal = selected;
		inactiveWarning = selected.status !== 'active';
	}

	async function save() {
		if (!animal || !liters) return;
		await enqueue('milkings', {
			id: crypto.randomUUID(),
			animal: animal.id,
			date,
			shift,
			liters: parseFloat(liters).toFixed(2)
		});
		saved = true;
		setTimeout(() => {
			animal = null;
			liters = '';
			saved = false;
			inactiveWarning = false;
		}, 1200);
	}
</script>

<svelte:head><title>Control lechero · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Control lechero</h1>

	{#if !animal}
		<TagSearch onSelect={selectAnimal} filterStatus={null} category="cow_lactating" />
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
			Fecha
			<input
				bind:value={date}
				type="date"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		<div class="grid grid-cols-2 gap-2">
			<button
				type="button"
				onclick={() => (shift = 'AM')}
				class="h-14 rounded-md border-2 border-black text-xl font-extrabold {shift === 'AM'
					? 'bg-black text-white'
					: 'bg-white'}"
			>
				Mañana
			</button>
			<button
				type="button"
				onclick={() => (shift = 'PM')}
				class="h-14 rounded-md border-2 border-black text-xl font-extrabold {shift === 'PM'
					? 'bg-black text-white'
					: 'bg-white'}"
			>
				Tarde
			</button>
		</div>

		<label class="flex flex-col gap-1 font-bold">
			Litros
			<input
				bind:value={liters}
				inputmode="decimal"
				pattern="[0-9]*[.]?[0-9]*"
				placeholder="0.00"
				class="h-16 rounded-md border-2 border-black px-4 text-3xl font-extrabold"
			/>
		</label>

		<Button
			type="button"
			onclick={save}
			disabled={!liters || saved}
			class="h-14 w-full text-xl font-extrabold"
		>
			{saved ? 'Guardado ✓' : 'Guardar ordeño'}
		</Button>

		<button
			type="button"
			onclick={() => {
				animal = null;
				liters = '';
				inactiveWarning = false;
			}}
			class="h-14 w-full rounded-md border-2 border-black font-extrabold"
		>
			Siguiente vaca
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

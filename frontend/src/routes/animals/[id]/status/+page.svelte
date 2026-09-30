<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	import { db, type Animal } from '$lib/db';
	import { enqueue } from '$lib/sync';

	const TARGET_STATUSES = [
		{ value: 'sold', label: 'Vendido' },
		{ value: 'dead', label: 'Muerto' },
		{ value: 'culled', label: 'Descarte' },
		{ value: 'active', label: 'Reactivar (activo)' }
	] as const;

	let animal = $state<Animal | null>(null);
	let newStatus = $state<(typeof TARGET_STATUSES)[number]['value']>('sold');
	let date = $state(new Date().toISOString().slice(0, 10));
	let reason = $state('');
	let saved = $state(false);
	let notFound = $state(false);

	onMount(async () => {
		const id = page.params.id;
		if (!id) {
			await goto('/');
			return;
		}
		const found = await db.animals.get(id);
		if (!found) {
			notFound = true;
			return;
		}
		animal = found;
	});

	async function save() {
		if (!animal) return;
		await enqueue('animals', {
			...animal,
			status: newStatus,
			status_changed_at: date,
			status_reason: reason.trim()
		});
		saved = true;
		const targetId = animal.id;
		setTimeout(() => goto(`/animals/${targetId}`), 900);
	}
</script>

<svelte:head><title>Cambio de estado {animal?.tag ?? ''} · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	{#if notFound}
		<p class="rounded-md border-2 border-red-700 bg-red-50 p-4 font-bold text-red-700">
			Animal no encontrado en este dispositivo.
		</p>
	{:else if animal}
		<h1 class="text-2xl font-extrabold">Cambio de estado</h1>
		<div class="rounded-md border-2 border-black p-4">
			<p class="text-2xl font-extrabold">{animal.tag}</p>
			<p>{animal.name || 'Sin nombre'} · estado actual: <span class="font-bold uppercase">{animal.status}</span></p>
		</div>

		<div class="grid grid-cols-2 gap-2">
			{#each TARGET_STATUSES as s}
				<button
					type="button"
					onclick={() => (newStatus = s.value)}
					class="h-14 rounded-md border-2 border-black font-extrabold {newStatus === s.value
						? s.value === 'active'
							? 'bg-green-700 text-white'
							: 'bg-red-700 text-white'
						: 'bg-white'}"
				>
					{s.label}
				</button>
			{/each}
		</div>

		<label class="flex flex-col gap-1 font-bold">
			Fecha del evento
			<input
				bind:value={date}
				type="date"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		<label class="flex flex-col gap-1 font-bold">
			Motivo
			<input
				bind:value={reason}
				placeholder="Ej. venta en feria, baja productividad…"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		{#if newStatus !== 'active'}
			<p class="rounded-md border-2 border-yellow-600 bg-yellow-50 p-3 font-bold text-yellow-800">
				El animal pasará a estado {TARGET_STATUSES.find((s) => s.value === newStatus)?.label}.
				Los registros históricos se conservan.
			</p>
		{/if}

		<button
			type="button"
			onclick={save}
			disabled={saved || newStatus === animal.status}
			class="h-14 w-full rounded-md bg-red-700 text-xl font-extrabold text-white disabled:opacity-50"
		>
			{saved ? 'Guardado ✓' : 'Confirmar cambio de estado'}
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

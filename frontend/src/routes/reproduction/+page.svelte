<script lang="ts">
	import { goto } from '$app/navigation';

	import TagSearch from '$lib/components/TagSearch.svelte';
	import type { Animal } from '$lib/db';
	import { enqueue } from '$lib/sync';

	const GESTATION_DAYS = 283;
	const DRYING_OFF_DAYS = 60;

	const TYPES = [
		{ value: 'heat', label: 'Celo detectado' },
		{ value: 'service', label: 'Servicio (monta/IA)' },
		{ value: 'palpation', label: 'Palpación' },
		{ value: 'calving', label: 'Parto' },
		{ value: 'drying_off', label: 'Secado' },
		{ value: 'abortion', label: 'Aborto' }
	] as const;

	let animal = $state<Animal | null>(null);
	let type = $state<(typeof TYPES)[number]['value']>('service');
	let date = $state(new Date().toISOString().slice(0, 10));
	let serviceMethod = $state<'natural' | 'ai'>('natural');
	let bullStraw = $state('');
	let palpationResult = $state<'pregnant' | 'empty'>('pregnant');
	let saved = $state(false);
	let inactiveWarning = $state(false);

	function selectAnimal(selected: Animal) {
		animal = selected;
		inactiveWarning = selected.status !== 'active';
	}

	function addDays(isoDate: string, days: number): string {
		const d = new Date(`${isoDate}T00:00:00`);
		d.setDate(d.getDate() + days);
		return d.toISOString().slice(0, 10);
	}

	let estimatedCalving = $derived(
		type === 'service' ? addDays(date, GESTATION_DAYS) : null
	);
	let suggestedDryingOff = $derived(
		estimatedCalving ? addDays(estimatedCalving, -DRYING_OFF_DAYS) : null
	);

	async function save() {
		if (!animal) return;
		const payload: Record<string, unknown> = {
			id: crypto.randomUUID(),
			animal: animal.id,
			date,
			type
		};
		if (type === 'service') {
			payload.service_method = serviceMethod;
			payload.bull_straw = bullStraw;
			payload.estimated_calving_date = estimatedCalving;
			payload.suggested_drying_off_date = suggestedDryingOff;
		}
		if (type === 'palpation') {
			payload.palpation_result = palpationResult;
		}
		await enqueue('reproductive_events', payload as never);
		saved = true;
		setTimeout(() => {
			animal = null;
			bullStraw = '';
			saved = false;
			inactiveWarning = false;
		}, 1200);
	}
</script>

<svelte:head><title>Evento reproductivo · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Evento reproductivo</h1>

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
			Tipo de evento
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
			Fecha
			<input
				bind:value={date}
				type="date"
				class="h-14 rounded-md border-2 border-black px-4 text-xl"
			/>
		</label>

		{#if type === 'service'}
			<div class="grid grid-cols-2 gap-2">
				<button
					type="button"
					onclick={() => (serviceMethod = 'natural')}
					class="h-14 rounded-md border-2 border-black font-extrabold {serviceMethod === 'natural'
						? 'bg-black text-white'
						: 'bg-white'}"
				>
					Monta natural
				</button>
				<button
					type="button"
					onclick={() => (serviceMethod = 'ai')}
					class="h-14 rounded-md border-2 border-black font-extrabold {serviceMethod === 'ai'
						? 'bg-black text-white'
						: 'bg-white'}"
				>
					Inseminación
				</button>
			</div>
			<label class="flex flex-col gap-1 font-bold">
				Toro / Pajilla
				<input
					bind:value={bullStraw}
					class="h-14 rounded-md border-2 border-black px-4 text-xl"
				/>
			</label>
			<div class="rounded-md border-2 border-black bg-neutral-50 p-3 text-sm font-bold">
				<p>Parto estimado: {estimatedCalving}</p>
				<p>Secado sugerido: {suggestedDryingOff}</p>
			</div>
		{/if}

		{#if type === 'palpation'}
			<div class="grid grid-cols-2 gap-2">
				<button
					type="button"
					onclick={() => (palpationResult = 'pregnant')}
					class="h-14 rounded-md border-2 border-green-700 text-xl font-extrabold {palpationResult ===
					'pregnant'
						? 'bg-green-700 text-white'
						: 'bg-white text-green-700'}"
				>
					Preñada
				</button>
				<button
					type="button"
					onclick={() => (palpationResult = 'empty')}
					class="h-14 rounded-md border-2 border-red-700 text-xl font-extrabold {palpationResult ===
					'empty'
						? 'bg-red-700 text-white'
						: 'bg-white text-red-700'}"
				>
					Vacía
				</button>
			</div>
		{/if}

		<button
			type="button"
			onclick={save}
			disabled={saved}
			class="h-14 w-full rounded-md bg-green-700 text-xl font-extrabold text-white disabled:opacity-50"
		>
			{saved ? 'Guardado ✓' : 'Guardar evento'}
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
		onclick={() => goto('/')}
		class="h-14 w-full rounded-md border-2 border-black font-extrabold"
	>
		Volver
	</button>
</div>

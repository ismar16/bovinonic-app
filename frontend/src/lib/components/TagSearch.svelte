<script lang="ts">
	import { db, type Animal } from '$lib/db';
	import { currentFarm } from '$lib/stores';

	let {
		onSelect,
		filterStatus = 'active',
		category = null
	}: {
		onSelect: (animal: Animal) => void;
		filterStatus?: string | null;
		category?: string | null;
	} = $props();

	let query = $state('');
	let results = $state<Animal[]>([]);

	async function search(value: string) {
		const farm = $currentFarm;
		if (!farm) return;
		const term = value.trim().toLowerCase();
		let all = await db.animals.where('farm').equals(farm.id).toArray();
		if (filterStatus) all = all.filter((a) => a.status === filterStatus);
		if (category) all = all.filter((a) => a.category === category);
		results = term === '' ? [] : all.filter((a) => a.tag.toLowerCase().includes(term) || a.name.toLowerCase().includes(term)).slice(0, 8);
	}

	$effect(() => {
		void search(query);
	});
</script>

<div>
	<input
		bind:value={query}
		inputmode="search"
		placeholder="Arete o nombre…"
		class="h-14 w-full rounded-md border-2 border-black px-4 text-xl"
	/>
	{#if results.length > 0}
		<ul class="mt-2 flex flex-col gap-2">
			{#each results as animal (animal.id)}
				<li>
					<button
						type="button"
						onclick={() => {
							onSelect(animal);
							query = '';
							results = [];
						}}
						class="flex h-14 w-full items-center justify-between rounded-md border-2 border-black bg-white px-4 text-left"
					>
						<span class="text-xl font-extrabold">{animal.tag}</span>
						<span class="text-sm">{animal.name || 'Sin nombre'}</span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

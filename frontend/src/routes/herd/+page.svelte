<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { Badge } from '$lib/components/ui/badge';
	import { db, type Animal, type Paddock } from '$lib/db';
	import { currentFarm } from '$lib/stores';

	const STATUS_LABELS: Record<string, string> = {
		active: 'Activo',
		sold: 'Vendido',
		dead: 'Muerto',
		culled: 'Descarte'
	};
	const CATEGORY_LABELS: Record<string, string> = {
		calf: 'Ternero/a',
		heifer: 'Novillo/a',
		cow_lactating: 'Vaca en ordeño',
		cow_dry: 'Vaca seca',
		bull: 'Toro reproductor'
	};

	let query = $state('');
	let animals = $state<Animal[]>([]);
	let paddocks = $state<Paddock[]>([]);
	let ready = $state(false);
	let categoryFilter = $state('');
	let paddockFilter = $state('');
	let statusFilter = $state('active');

	onMount(async () => {
		if (!$currentFarm) {
			await goto('/');
			return;
		}
		animals = await db.animals.where('farm').equals($currentFarm.id).toArray();
		paddocks = await db.paddocks.where('farm').equals($currentFarm.id).toArray();
		ready = true;
	});

	let filtered = $derived(
		animals.filter((a) => {
			const term = query.trim().toLowerCase();
			if (term && !a.tag.toLowerCase().includes(term) && !a.name.toLowerCase().includes(term))
				return false;
			if (categoryFilter && a.category !== categoryFilter) return false;
			if (paddockFilter && a.paddock !== paddockFilter) return false;
			if (statusFilter && a.status !== statusFilter) return false;
			return true;
		})
	);
</script>

<svelte:head><title>Hato · Gestión Ganadera</title></svelte:head>

{#if ready}
	<div class="pt-4">
		<input
			bind:value={query}
			placeholder="Buscar arete o nombre…"
			class="mb-3 h-14 w-full rounded-md border-2 border-black px-4 text-xl"
		/>

		<div class="mb-2 flex gap-2 overflow-x-auto pb-1">
			{#each ['', 'calf', 'heifer', 'cow_lactating', 'cow_dry', 'bull'] as cat}
				<button
					type="button"
					onclick={() => (categoryFilter = cat)}
					class="shrink-0"
				>
					<Badge
						class="px-3 py-1.5 text-xs {categoryFilter === cat
							? 'bg-black text-white'
							: 'bg-neutral-100 text-black'}"
					>
						{cat === '' ? 'Todas' : CATEGORY_LABELS[cat]}
					</Badge>
				</button>
			{/each}
		</div>

		{#if paddocks.length > 0}
			<div class="mb-2 flex gap-2 overflow-x-auto pb-1">
				<button type="button" onclick={() => (paddockFilter = '')} class="shrink-0">
					<Badge class="px-3 py-1.5 text-xs {paddockFilter === '' ? 'bg-black text-white' : 'bg-neutral-100 text-black'}">
						Todos los potreros
					</Badge>
				</button>
				{#each paddocks as p (p.id)}
					<button type="button" onclick={() => (paddockFilter = p.id)} class="shrink-0">
						<Badge class="px-3 py-1.5 text-xs {paddockFilter === p.id ? 'bg-black text-white' : 'bg-neutral-100 text-black'}">
							{p.name}
						</Badge>
					</button>
				{/each}
			</div>
		{/if}

		<div class="mb-4 flex gap-2 overflow-x-auto pb-1">
			{#each ['active', '', 'sold', 'dead', 'culled'] as st}
				<button type="button" onclick={() => (statusFilter = st)} class="shrink-0">
					<Badge
						class="px-3 py-1.5 text-xs {statusFilter === st
							? 'bg-black text-white'
							: 'bg-neutral-100 text-black'}"
					>
						{st === '' ? 'Todos los estados' : STATUS_LABELS[st]}
					</Badge>
				</button>
			{/each}
		</div>

		<p class="mb-2 text-sm font-bold text-neutral-600">{filtered.length} animales</p>

		<ul class="flex flex-col gap-2">
			{#each filtered as animal (animal.id)}
				<li>
					<a
						href="/animals/{animal.id}"
						class="flex items-center justify-between rounded-md border-2 border-black p-4"
					>
						<div>
							<p class="text-xl font-extrabold">{animal.tag}</p>
							<p class="text-sm">{animal.name || 'Sin nombre'} · {CATEGORY_LABELS[animal.category] ?? animal.category}</p>
						</div>
						<Badge
							class={animal.status === 'active'
								? 'bg-green-700 text-white'
								: 'bg-red-700 text-white'}
						>
							{STATUS_LABELS[animal.status] ?? animal.status}
						</Badge>
					</a>
				</li>
			{:else}
				<li class="rounded-md border-2 border-dashed border-neutral-400 p-6 text-center">
					Sin animales con esos filtros.
				</li>
			{/each}
		</ul>
	</div>
{/if}

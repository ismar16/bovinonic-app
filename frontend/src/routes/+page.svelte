<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { me } from '$lib/api';
	import { computeReproAlerts, computeWithdrawalCount } from '$lib/alerts';
	import { db, type Animal } from '$lib/db';
	import { availableFarms, currentFarm, online, sessionUser } from '$lib/stores';
	import { syncNow } from '$lib/sync';

	let animals = $state<Animal[]>([]);
	let ready = $state(false);
	let calvingSoonCount = $state(0);
	let dryingOffCount = $state(0);
	let daysOpenCount = $state(0);
	let withdrawalsCount = $state(0);

	onMount(async () => {
		if (!getFarm()) {
			try {
				const user = await me();
				sessionUser.set({ id: user.id, username: user.username });
				availableFarms.set(
					user.farms.map((f) => ({ id: f.farm, name: f.farm_name, role: f.role }))
				);
				if (user.farms.length === 0) {
					ready = true;
					return;
				}
				const first = user.farms[0];
				currentFarm.set({ id: first.farm, name: first.farm_name, role: first.role });
			} catch {
				await goto('/login');
				return;
			}
		}
		await loadDashboard();
		if ($online) void syncNow().then(loadDashboard);
		ready = true;
	});

	function getFarm(): { id: string; name: string; role: string } | null {
		let value: { id: string; name: string; role: string } | null = null;
		currentFarm.subscribe((v) => (value = v))();
		return value;
	}

	async function loadDashboard() {
		const farm = getFarm();
		if (!farm) return;
		animals = await db.animals.where('farm').equals(farm.id).toArray();
		const alerts = await computeReproAlerts(farm.id);
		calvingSoonCount = alerts.calvingSoon.length;
		dryingOffCount = alerts.dryingOffSoon.length;
		daysOpenCount = alerts.daysOpen.length;
		withdrawalsCount = await computeWithdrawalCount(farm.id);
	}

	let activeCount = $derived(animals.filter((a) => a.status === 'active').length);
</script>

<svelte:head><title>Inicio · Gestión Ganadera</title></svelte:head>

{#if ready}
	<div class="pt-4">
		{#if $currentFarm}
			<div class="mb-4 grid grid-cols-2 gap-2 text-center">
				<a href="/herd" class="rounded-md border-2 border-black p-3">
					<p class="text-3xl font-extrabold">{activeCount}</p>
					<p class="text-xs font-bold">Animales activos</p>
				</a>
				<a href="/alerts" class="rounded-md border-2 border-black p-3">
					<p class="text-3xl font-extrabold">{calvingSoonCount}</p>
					<p class="text-xs font-bold">Próximas a parir</p>
				</a>
				<a href="/alerts" class="rounded-md border-2 border-yellow-600 p-3">
					<p class="text-3xl font-extrabold">{dryingOffCount + daysOpenCount}</p>
					<p class="text-xs font-bold">Alertas reproductivas</p>
				</a>
				<a href="/health/withdrawals" class="rounded-md border-2 border-red-700 p-3">
					<p class="text-3xl font-extrabold text-red-700">{withdrawalsCount}</p>
					<p class="text-xs font-bold text-red-700">Retiros activos</p>
				</a>
			</div>
		{:else}
			<p class="pt-8 text-center">Sin finca asignada. Contactá al administrador.</p>
		{/if}
	</div>
{/if}

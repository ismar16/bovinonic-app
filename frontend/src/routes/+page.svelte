<script lang="ts">
	import { goto } from '$app/navigation';
	import { Beef, Bell, Milk, Ban } from 'lucide-svelte';
	import { onMount } from 'svelte';

	import { me } from '$lib/api';
	import { computeReproAlerts, computeWithdrawalCount } from '$lib/alerts';
	import * as Card from '$lib/components/ui/card';
	import { db, type Animal } from '$lib/db';
	import { milkTodayTotal } from '$lib/reports';
	import { availableFarms, currentFarm, online, sessionUser } from '$lib/stores';
	import { syncNow } from '$lib/sync';

	let animals = $state<Animal[]>([]);
	let ready = $state(false);
	let milkToday = $state(0);
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
		milkToday = await milkTodayTotal(farm.id);
	}

	let activeCount = $derived(animals.filter((a) => a.status === 'active').length);

	let kpis = $derived([
		{
			href: '/herd',
			value: activeCount,
			label: 'Animales activos',
			icon: Beef,
			tone: 'default'
		},
		{
			href: '/reports/milk',
			value: `${milkToday} L`,
			label: 'Producción de hoy',
			icon: Milk,
			tone: 'default'
		},
		{
			href: '/alerts',
			value: calvingSoonCount + dryingOffCount + daysOpenCount,
			label: 'Alertas reproductivas',
			icon: Bell,
			tone: 'warn'
		},
		{
			href: '/health/withdrawals',
			value: withdrawalsCount,
			label: 'Retiros activos',
			icon: Ban,
			tone: 'danger'
		}
	]);
</script>

<svelte:head><title>Inicio · Gestión Ganadera</title></svelte:head>

{#if ready}
	<div class="pt-4">
		{#if $currentFarm}
			<div class="grid grid-cols-2 gap-3">
				{#each kpis as kpi (kpi.label)}
					<a href={kpi.href}>
						<Card.Root
							class="h-full {kpi.tone === 'danger' && kpi.value !== 0 && kpi.value !== '0 L'
								? 'border-red-700'
								: kpi.tone === 'warn' && kpi.value !== 0
									? 'border-yellow-600'
									: ''}"
						>
							<Card.Header class="flex-row items-center justify-between p-4 pb-2">
								<Card.Title class="text-xs font-bold uppercase text-neutral-600">
									{kpi.label}
								</Card.Title>
								<kpi.icon
									class="h-5 w-5 {kpi.tone === 'danger'
										? 'text-red-700'
										: kpi.tone === 'warn'
											? 'text-yellow-700'
											: 'text-primary'}"
								/>
							</Card.Header>
							<Card.Content class="p-4 pt-0">
								<p class="text-3xl font-extrabold">{kpi.value}</p>
							</Card.Content>
						</Card.Root>
					</a>
				{/each}
			</div>
		{:else}
			<p class="pt-8 text-center">Sin finca asignada. Contactá al administrador.</p>
		{/if}
	</div>
{/if}

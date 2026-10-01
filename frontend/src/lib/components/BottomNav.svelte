<script lang="ts">
	import { page } from '$app/state';
	import { Bell, Beef, ClipboardList, Home, Settings } from 'lucide-svelte';
	import { onMount } from 'svelte';

	import { computeReproAlerts } from '$lib/alerts';
	import { alertCount, currentFarm, online } from '$lib/stores';
	import { syncNow } from '$lib/sync';

	const items = [
		{ href: '/', label: 'Inicio', icon: Home },
		{ href: '/herd', label: 'Hato', icon: Beef },
		{ href: '/operations', label: 'Operaciones', icon: ClipboardList },
		{ href: '/alerts', label: 'Alertas', icon: Bell },
		{ href: '/settings', label: 'Ajustes', icon: Settings }
	];

	let path = $derived(page.url.pathname);

	async function refreshAlertCount() {
		const farm = $currentFarm;
		if (!farm) {
			alertCount.set(0);
			return;
		}
		const alerts = await computeReproAlerts(farm.id);
		alertCount.set(
			alerts.calvingSoon.length + alerts.dryingOffSoon.length + alerts.daysOpen.length
		);
	}

	onMount(() => {
		void refreshAlertCount();
		const unsubscribe = currentFarm.subscribe(() => void refreshAlertCount());
		const interval = setInterval(() => {
			if ($online) void syncNow().then(refreshAlertCount);
		}, 60_000);
		return () => {
			unsubscribe();
			clearInterval(interval);
		};
	});
</script>

<nav
	class="fixed inset-x-0 bottom-0 z-10 mx-auto grid h-16 w-full max-w-xl grid-cols-5 border-t bg-white"
	aria-label="Navegación principal"
>
	{#each items as item (item.href)}
		{@const active = item.href === '/' ? path === '/' : path.startsWith(item.href)}
		<a
			href={item.href}
			class="relative flex flex-col items-center justify-center gap-0.5 text-[11px] font-bold {active
				? 'text-primary'
				: 'text-neutral-500'}"
			aria-current={active ? 'page' : undefined}
		>
			<item.icon class="h-6 w-6" strokeWidth={active ? 2.5 : 2} />
			{item.label}
			{#if item.href === '/alerts' && $alertCount > 0}
				<span
					class="absolute right-1/2 top-1 translate-x-4 rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-extrabold leading-none text-white"
				>
					{$alertCount}
				</span>
			{/if}
		</a>
	{/each}
</nav>

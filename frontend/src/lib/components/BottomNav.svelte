<script lang="ts">
	import CattleMark from '$lib/components/CattleMark.svelte';
	import { page } from '$app/state';
	import { Bell, Beef, ChartNoAxesCombined, ClipboardList, Home, Settings, Handshake } from 'lucide-svelte';
	import { onMount } from 'svelte';
	import { liveQuery } from 'dexie';

	import { computeReproAlerts } from '$lib/alerts';
	import { alertCount, currentFarm, online } from '$lib/stores';

	const items = [
		{ href: '/', label: 'Inicio', icon: Home },
		{ href: '/herd', label: 'Hato', icon: CattleMark },
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
		let query: { unsubscribe(): void } | undefined;
		const unsubscribe = currentFarm.subscribe(() => {
			query?.unsubscribe();
			query = liveQuery(refreshAlertCount).subscribe({ error() { alertCount.set(0); } });
		});
		return () => {
			unsubscribe();
			query?.unsubscribe();
		};
	});
</script>

<nav
	class="fixed inset-x-0 bottom-0 z-10 mx-auto grid h-16 w-full max-w-xl grid-cols-5 border-t bg-white lg:overflow-y-auto lg:inset-y-0 lg:left-0 lg:right-auto lg:mx-0 lg:flex lg:h-screen lg:w-60 lg:max-w-none lg:flex-col lg:gap-2 lg:border-r lg:border-t-0 lg:border-[#1e3e30] lg:bg-[#183b2d] lg:px-4 lg:py-7"
	aria-label="Navegación principal"
>
	<a href="/" class="mb-9 hidden items-center gap-3 px-3 text-lg font-semibold text-white lg:flex">
		<span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#a7b49b]/30 bg-white/5"><CattleMark class="h-6 w-6 text-[#d4c79a]" /></span>
		<span><span class="block font-serif text-2xl tracking-tight">Bovinonic</span><span class="block pt-1 text-[9px] uppercase tracking-[.2em] text-white/40">Gestión de finca</span></span>
	</a>
	{#each items as item (item.href)}
		{@const active = item.href === '/' ? path === '/' : item.href === '/herd'
			? path.startsWith('/herd') || path.startsWith('/animals/') || path.startsWith('/lots') || path.startsWith('/agreements')
			: item.href === '/operations' ? ['/operations', '/milking', '/weighing', '/health', '/reproduction'].some((p) => path.startsWith(p))
			: path.startsWith(item.href)}
		<a
			href={item.href}
			class="relative flex flex-col items-center justify-center gap-0.5 text-[11px] font-bold lg:min-h-12 lg:flex-row lg:justify-start lg:gap-3 lg:rounded-lg lg:px-3 lg:text-sm {active
				? path.startsWith('/agreements') && item.href === '/herd' ? 'text-primary lg:text-white/60' : 'text-primary lg:bg-white/10 lg:text-white'
				: 'text-neutral-500 lg:text-white/60 lg:hover:bg-white/5 lg:hover:text-white'}"
			aria-current={active ? 'page' : undefined}
		>
			<item.icon class="h-6 w-6" strokeWidth={active ? 2.5 : 2} />
			{item.label}
			{#if item.href === '/alerts' && $alertCount > 0}
				<span
					class="absolute right-1/2 top-1 translate-x-4 rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-extrabold leading-none text-white lg:right-3 lg:top-auto lg:translate-x-0"
				>
					{$alertCount}
				</span>
			{/if}
		</a>
	{/each}
	<a href="/lots" class="hidden min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-bold text-white/60 hover:bg-white/5 lg:flex"><Beef class="h-6 w-6" /> Lotes de animales</a>
	{#if $currentFarm?.role === 'admin'}<a href="/agreements" class="hidden min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-bold lg:flex {path.startsWith('/agreements') ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5'}"><Handshake class="h-6 w-6" /> Acuerdos y estadías</a>{/if}
	<a href="/reports" aria-current={path.startsWith('/reports') ? 'page' : undefined}
		class="hidden min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-bold lg:flex {path.startsWith('/reports') ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5'}">
		<ChartNoAxesCombined class="h-6 w-6" /> Reportes
	</a>
	<div class="mt-auto hidden rounded-xl border border-white/10 bg-white/5 p-4 lg:block">
		<p class="text-[10px] font-semibold uppercase tracking-[.2em] text-[#c6b78b]">Tu finca, conectada</p>
		<p class="mt-2 text-xs leading-5 text-white/50">Cada animal tiene una historia. Mantenela al día.</p>
	</div>
</nav>

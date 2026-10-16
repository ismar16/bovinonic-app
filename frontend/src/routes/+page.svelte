<script lang="ts">
	import CattleMark from '$lib/components/CattleMark.svelte';
	import { goto } from '$app/navigation';
	import { Beef, Bell, Milk, Ban, ArrowUpRight, Plus, Search, ArrowRight, Check, Leaf } from 'lucide-svelte';
	import { onMount } from 'svelte';

	import { me } from '$lib/api';
	import { computeReproAlerts, computeWithdrawalCount } from '$lib/alerts';
	import { farmDate } from '$lib/dates';
	import { db, type Animal } from '$lib/db';
	import { milkTodayTotal, milkByDay, daysAgo, type MilkDayRow } from '$lib/reports';
	import { availableFarms, currentFarm, lastSyncResult, online, sessionUser } from '$lib/stores';
	import { syncNow } from '$lib/sync';

	let animals = $state<Animal[]>([]);
	let query = $state('');
	let week = $state<MilkDayRow[]>([]);
	const canEdit = $derived(['admin', 'technician'].includes($currentFarm?.role ?? ''));
	const recent = $derived([...animals].sort((a,b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? '')).slice(0,4));
	const weekBars = $derived(Array.from({length:7}, (_,i) => { const date = daysAgo(6-i); return {date, total: week.find((row) => row.date === date)?.total ?? 0}; }));
	const maxMilk = $derived(Math.max(1, ...weekBars.map((r) => r.total)));
	const hasMilk = $derived(weekBars.some((r) => r.total > 0));
	let ready = $state(false);
	let milkToday = $state(0);
	let calvingSoonCount = $state(0);
	let dryingOffCount = $state(0);
	let daysOpenCount = $state(0);
	let withdrawalsCount = $state(0);

	$effect(() => {
		if (ready && $lastSyncResult) void loadDashboard();
	});

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
		week = await milkByDay(farm.id, daysAgo(6), farmDate());
	}

	let activeCount = $derived(animals.filter((a) => a.status === 'active').length);

	let kpis = $derived([
		{
			href: '/herd',
			value: activeCount,
			label: 'Animales activos',
			icon: CattleMark,
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

<svelte:head><title>La finca hoy · Bovinonic</title></svelte:head>
{#if ready && $currentFarm}
<div class="workspace-page space-y-6">
    <section class="relative overflow-hidden rounded-2xl border border-[#dfe3d2] bg-[#e9eddf] p-6 sm:p-8">
        <div class="pointer-events-none absolute -right-12 -top-12 h-64 w-64 rounded-full border border-[#bdc9ab]/40"></div><div class="pointer-events-none absolute -bottom-36 right-5 h-80 w-80 rounded-full border border-[#bdc9ab]/50"></div>
        <div class="relative max-w-xl"><p class="eyebrow">Tu finca, al día · {new Date(`${farmDate()}T12:00:00`).toLocaleDateString('es-NI',{weekday:'long',day:'numeric',month:'long'})}</p><h1 class="page-title mt-4">Cada animal cuenta.<br /><span class="text-[#6c8058]">Cada dato también.</span></h1><p class="page-description max-w-md">Consultá el hato, encontrá lo que necesita atención y llevá un registro claro de tu finca.</p><div class="mt-6 flex flex-wrap gap-2"><a href="/herd" class="action-button">Consultar mi hato <ArrowRight class="h-4 w-4" /></a>{#if canEdit}<a href="/animals/new" class="quiet-button bg-white/60"><Plus class="h-4 w-4" /> Registrar animal</a>{/if}</div></div>
        <div class="absolute bottom-7 right-10 hidden items-center gap-2 text-[#7b8e63] xl:flex"><Leaf class="h-6 w-6" /><span class="text-[10px] uppercase tracking-[.2em]">Cuidar · Registrar · Crecer</span></div>
    </section>
    <div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {#each kpis as kpi}
        <a href={kpi.href} class="panel group p-4 sm:p-5"><div class="flex items-center justify-between"><span class="flex h-9 w-9 items-center justify-center rounded-xl {kpi.tone === 'danger' ? 'bg-[#f6eee5] text-[#b28c52]' : kpi.tone === 'warn' ? 'bg-[#f0eedc] text-[#9b965b]' : 'bg-[#edf2e7] text-[#709066]'}"><kpi.icon class="h-4 w-4" /></span><ArrowUpRight class="h-4 w-4 text-[#bbc2b2] transition-transform group-hover:-translate-y-0.5" /></div><p class="mt-4 font-serif text-3xl text-[#294632]">{kpi.value}</p><p class="mt-1 text-[11px] text-[#7d8773]">{kpi.label}</p></a>
        {/each}
    </div>
    <div class="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <section class="panel p-5 sm:p-6"><div class="flex items-center justify-between"><div><p class="eyebrow">Consulta rápida</p><h2 class="mt-2 font-serif text-xl text-[#304d36]">Encontrá un animal</h2></div><CattleMark class="h-6 w-6 text-[#94a783]" /></div><form class="mt-5 flex gap-2" onsubmit={(e) => {e.preventDefault();void goto(`/herd?q=${encodeURIComponent(query.trim())}`);}}><label class="relative flex-1"><Search class="absolute left-3 top-3.5 h-4 w-4 text-[#98a18e]" /><input bind:value={query} aria-label="Buscar un animal en el hato" class="field pl-10" placeholder="Arete o nombre del animal…" /></label><button class="action-button" type="submit">Buscar</button></form><div class="mt-5 divide-y divide-[#eef0e8]">{#each recent as animal}<a href="/animals/{animal.id}" class="flex items-center gap-3 py-3"><span class="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f1f3ec] text-[#819774]"><CattleMark class="h-4 w-4" /></span><span class="flex-1"><span class="block text-xs font-bold">{animal.tag}</span><span class="text-[11px] text-[#8b937f]">{animal.name || 'Sin nombre'}</span></span><span class="status-pill">{animal.status === 'active' ? 'Activo' : 'Histórico'}</span><ArrowUpRight class="h-4 w-4 text-[#aab49d]" /></a>{:else}<p class="py-8 text-sm text-[#87917e]">Todavía no hay animales en este dispositivo. Registrá uno o sincronizá tu finca.</p>{/each}</div><a href="/herd" class="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-[#486b43]">Ver todo el hato <ArrowRight class="h-3 w-3" /></a></section>
        <section class="panel p-5 sm:p-6"><p class="eyebrow">Lo que necesita atención</p><h2 class="mt-2 font-serif text-xl text-[#304d36]">Agenda de la finca</h2><div class="mt-5 space-y-3">{#each [{label:'Partos en los próximos 30 días', value:calvingSoonCount,href:'/alerts'}, {label:'Secados en los próximos 7 días',value:dryingOffCount,href:'/alerts'}, {label:'Animales con retiro registrado',value:withdrawalsCount,href:'/health/withdrawals'}] as task}<a href={task.href} class="flex items-center gap-3 rounded-xl border border-[#e8ebdf] p-3"><span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full {task.value ? 'bg-[#f2ecd8] text-[#9c7c3c]' : 'bg-[#eef3e8] text-[#87a177]'}">{#if task.value}<span class="text-xs font-bold">{task.value}</span>{:else}<Check class="h-3.5 w-3.5" />{/if}</span><span class="flex-1 text-xs text-[#6f7d64]">{task.label}</span><ArrowUpRight class="h-3.5 w-3.5 text-[#b0b9a2]" /></a>{/each}</div><p class="mt-4 text-[10px] leading-4 text-[#98a08e]">Calculado con los registros disponibles. Sin registros no se puede determinar el estado de cada animal.</p></section>
    </div>
    <section class="panel p-5 sm:p-6"><div class="flex items-center justify-between"><div><p class="eyebrow">Producción registrada</p><h2 class="mt-2 font-serif text-xl">La semana en litros</h2></div><a href="/reports/milk" class="quiet-button text-xs">Ver reporte <ArrowUpRight class="h-3.5 w-3.5" /></a></div>{#if hasMilk}<div class="mt-7 flex h-36 items-end gap-3 sm:gap-6">{#each weekBars as bar}<div class="flex h-full flex-1 flex-col justify-end text-center"><span class="mb-2 text-[10px] text-[#708367]">{bar.total.toFixed(1)}</span><div class="mx-auto w-full max-w-16 rounded-t bg-[#9aaf82]" style:height={`${Math.max(3,bar.total/maxMilk*85)}px`}></div><span class="mt-2 text-[10px] text-[#97a08c]">{bar.date.slice(8)}/{bar.date.slice(5,7)}</span></div>{/each}</div>{:else}<div class="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#f5f6f0] p-5"><p class="text-sm text-[#859077]">Sin ordeños registrados en los últimos 7 días.</p><a href="/milking" class="quiet-button">Registrar ordeño</a></div>{/if}</section>
</div>
{:else if ready}<p class="panel mt-6 p-6 text-sm">No tenés una finca asignada. Contactá al administrador.</p>{:else}<p class="py-12 text-center text-sm text-[#89957b]">Preparando tu finca…</p>{/if}

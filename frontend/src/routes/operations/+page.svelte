<script lang="ts">
	import { currentFarm } from '$lib/stores';
	import { ArrowUpRight, Milk, Plus, Scale, Syringe, HeartPulse, Ban, Beef, Handshake } from 'lucide-svelte';

	const actions = [
		{ href: '/sales', label: 'Ventas y cobros', icon: Beef, primary: true },
		{ href: '/agreements', label: 'Acuerdos y otras fincas', icon: Handshake, primary: true },
		{ href: '/lots', label: 'Lotes de animales', icon: Beef, primary: true },
		{ href: '/animals/bulk', label: 'Ingreso de varios animales', icon: Plus, primary: true },
		{ href: '/animals/new', label: 'Nuevo animal', icon: Plus, primary: true },
		{ href: '/weighing', label: 'Pesaje rápido', icon: Scale, primary: true },
		{ href: '/milking', label: 'Producción diaria de leche', icon: Milk, primary: true },
		{ href: '/reproduction', label: 'Evento reproductivo', icon: HeartPulse, primary: true },
		{ href: '/health', label: 'Evento sanitario', icon: Syringe, primary: true },
		{ href: '/health/withdrawals', label: 'Retiros activos', icon: Ban, primary: false }
	];
</script>

<svelte:head><title>Operaciones · Gestión Ganadera</title></svelte:head>

<div class="workspace-page space-y-6">
    <header><p class="eyebrow">El trabajo de cada día</p><h1 class="page-title mt-2">Registrar para cuidar.</h1><p class="page-description">Elegí una tarea. Cada registro se guarda en tu dispositivo y se envía al sincronizar.</p></header>
    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {#each actions.filter((a) => (!['/agreements','/sales'].includes(a.href) || $currentFarm?.role === 'admin') && (['admin','technician'].includes($currentFarm?.role ?? '') || ['/weighing','/milking','/health/withdrawals','/lots'].includes(a.href))) as action}
            <a href={action.href} class="panel group flex min-h-44 flex-col items-start p-6 transition-colors hover:border-[#9aaf80]"><div class="flex w-full items-center justify-between"><span class="flex h-11 w-11 items-center justify-center rounded-xl bg-[#edf1e4] text-[#6c8a57]"><action.icon class="h-5 w-5" /></span><ArrowUpRight class="h-4 w-4 text-[#aeb99d]" /></div><h2 class="mt-5 font-serif text-xl text-[#345235]">{action.label}</h2><p class="mt-2 text-xs leading-5 text-[#8b957c]">{action.href === '/sales' ? 'Registrá ventas, liquidaciones por animal y abonos del comprador.' : action.href === '/agreements' ? 'Entregas a medias, pasto alquilado, gastos y liquidaciones.' : action.href === '/lots' ? 'Agrupá animales y administrá la composición del lote.' : action.href === '/animals/bulk' ? 'Ingresá varios animales con lote y ubicación comunes.' : action.href === '/animals/new' ? 'Identificá un animal y agregalo al inventario.' : action.href === '/weighing' ? 'Registrá el peso y consultá su evolución.' : action.href === '/milking' ? 'Anotá en un solo registro los litros totales de la finca por día.' : action.href === '/reproduction' ? 'Llevá el control de servicios, palpaciones y partos.' : action.href === '/health' ? 'Registrá tratamientos y sus días de retiro.' : 'Consultá los periodos de retiro registrados.'}</p></a>
        {/each}
    </div>
</div>

<script lang="ts">
	import { Milk, Plus, Scale, Syringe, HeartPulse, Ban } from 'lucide-svelte';

	const actions = [
		{ href: '/animals/new', label: 'Nuevo animal', icon: Plus, primary: true },
		{ href: '/weighing', label: 'Pesaje rápido', icon: Scale, primary: true },
		{ href: '/milking', label: 'Control lechero', icon: Milk, primary: true },
		{ href: '/reproduction', label: 'Evento reproductivo', icon: HeartPulse, primary: true },
		{ href: '/health', label: 'Evento sanitario', icon: Syringe, primary: true },
		{ href: '/health/withdrawals', label: 'Retiros activos', icon: Ban, primary: false }
	];
</script>

<svelte:head><title>Operaciones · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-3 pt-4">
	<h1 class="text-2xl font-extrabold">Operaciones</h1>
	{#each actions as action (action.href)}
		<a
			href={action.href}
			class="flex h-14 items-center gap-3 rounded-md px-4 text-lg font-extrabold {action.primary
				? 'bg-primary text-primary-foreground'
				: 'border-2 border-red-700 text-red-700'}"
		>
			<action.icon class="h-6 w-6" />
			{action.label}
		</a>
	{/each}
</div>

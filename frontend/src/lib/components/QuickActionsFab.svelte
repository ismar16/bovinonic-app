<script lang="ts">
	import { Milk, Plus, PlusCircle, Scale, Syringe, HeartPulse } from 'lucide-svelte';

	import * as Sheet from '$lib/components/ui/sheet';
	import { currentFarm } from '$lib/stores';

	let open = $state(false);

	const actions = [
		{ href: '/weighing', label: 'Pesaje rápido', icon: Scale },
		{ href: '/milking', label: 'Ordeño', icon: Milk },
		{ href: '/reproduction', label: 'Evento reproductivo', icon: HeartPulse },
		{ href: '/health', label: 'Evento sanitario', icon: Syringe },
		{ href: '/animals/new', label: 'Nuevo animal', icon: PlusCircle },
		{ href: '/animals/bulk', label: 'Registrar varios animales', icon: PlusCircle }
	];
</script>

<Sheet.Root bind:open>
	<Sheet.Trigger
		class="fixed bottom-20 right-4 z-20 flex h-14 w-14 items-center justify-center gap-2 rounded-full bg-primary text-primary-foreground shadow-lg lg:bottom-6 lg:right-8 lg:w-auto lg:px-5"
		aria-label="Registro rápido"
	>
		<Plus class="h-8 w-8" strokeWidth={2.5} />
		<span class="hidden text-sm font-bold lg:inline">Registrar</span>
	</Sheet.Trigger>
	<Sheet.Content side="bottom" class="mx-auto w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-t-xl">
		<Sheet.Header>
			<Sheet.Title>Registro rápido</Sheet.Title>
		</Sheet.Header>
		<div class="flex flex-col gap-2 p-4">
			{#each actions.filter((a) => ['admin','technician'].includes($currentFarm?.role ?? '') || ['/weighing','/milking'].includes(a.href)) as action (action.href)}
				<a
					href={action.href}
					onclick={() => (open = false)}
					class="quiet-button min-h-12 w-full"
				>
					<action.icon class="h-6 w-6" />
					{action.label}
				</a>
			{/each}
		</div>
	</Sheet.Content>
</Sheet.Root>

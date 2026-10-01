<script lang="ts">
	import { Milk, Plus, PlusCircle, Scale, Syringe, HeartPulse } from 'lucide-svelte';

	import * as Sheet from '$lib/components/ui/sheet';

	let open = $state(false);

	const actions = [
		{ href: '/weighing', label: 'Pesaje rápido', icon: Scale },
		{ href: '/milking', label: 'Ordeño', icon: Milk },
		{ href: '/reproduction', label: 'Evento reproductivo', icon: HeartPulse },
		{ href: '/health', label: 'Evento sanitario', icon: Syringe },
		{ href: '/animals/new', label: 'Nuevo animal', icon: PlusCircle }
	];
</script>

<Sheet.Root bind:open>
	<Sheet.Trigger
		class="fixed bottom-20 right-4 z-20 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg"
		aria-label="Registro rápido"
	>
		<Plus class="h-8 w-8" strokeWidth={2.5} />
	</Sheet.Trigger>
	<Sheet.Content side="bottom" class="mx-auto w-full max-w-xl rounded-t-xl">
		<Sheet.Header>
			<Sheet.Title>Registro rápido</Sheet.Title>
		</Sheet.Header>
		<div class="flex flex-col gap-2 p-4">
			{#each actions as action (action.href)}
				<a
					href={action.href}
					onclick={() => (open = false)}
					class="flex h-14 items-center gap-3 rounded-md border-2 border-black px-4 text-lg font-extrabold"
				>
					<action.icon class="h-6 w-6" />
					{action.label}
				</a>
			{/each}
		</div>
	</Sheet.Content>
</Sheet.Root>

<script lang="ts">
	import { LogOut } from 'lucide-svelte';

	import { logoutAndWipe, switchFarm } from '$lib/session';
	import { syncNow } from '$lib/sync';
	import {
		availableFarms,
		currentFarm,
		online,
		pendingCount,
		sessionUser,
		sessionChanging,
		sessionNotice,
		syncing,
		syncError,
		syncWarnings
	} from '$lib/stores';

	let statusColor = $derived(
		$syncError
			? 'bg-red-600'
			: !$online || $pendingCount > 0
				? 'bg-yellow-500'
				: 'bg-green-600'
	);
	let statusLabel = $derived(
		$syncError
			? 'Error de sincronización'
			: !$online
				? `Modo campo · ${$pendingCount} pendientes`
				: $pendingCount > 0
					? `${$pendingCount} pendientes`
					: 'Sincronizado'
	);
</script>

<header class="sticky top-0 z-10 flex h-11 items-center justify-between border-b bg-white px-3 lg:h-16 lg:px-8">
	<div class="flex min-w-0 items-center gap-2">
		<span
			class="inline-block h-3 w-3 shrink-0 rounded-full {statusColor} {$syncing
				? 'animate-pulse'
				: ''}"
			title={statusLabel}
			aria-label={statusLabel}
		></span>
		{#if $availableFarms.length > 1 && $currentFarm}
			<select
				class="max-w-[60vw] truncate rounded-md border-0 bg-transparent py-1 text-sm font-bold"
				value={$currentFarm.id}
				disabled={$sessionChanging}
				onchange={async (e) => {
					const select = e.currentTarget;
					const selected = $availableFarms.find((f) => f.id === e.currentTarget.value);
					if (selected && !(await switchFarm(selected))) select.value = $currentFarm?.id ?? '';
				}}
			>
				{#each $availableFarms as farm (farm.id)}
					<option value={farm.id}>{farm.name}</option>
				{/each}
			</select>
		{:else}
			<span class="truncate text-sm font-bold">{$currentFarm?.name ?? 'Gestión Ganadera'}</span>
		{/if}
	</div>
	{#if $sessionUser}
		<button
			type="button"
			onclick={() => logoutAndWipe()}
			class="flex h-8 w-8 items-center justify-center rounded-md text-neutral-600"
			aria-label="Cerrar sesión"
			title="Cerrar sesión"
		>
			<LogOut class="h-5 w-5" />
		</button>
	{/if}
</header>

{#if $sessionNotice}
	<div role="alert" class="border-b border-amber-300 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-900 lg:px-8">
		{$sessionNotice}
		{#if $pendingCount > 0}
			<button type="button" disabled={!$online || $syncing} onclick={() => syncNow()}
				class="ml-2 underline disabled:opacity-50">Sincronizar ahora</button>
		{/if}
	</div>
{/if}

{#if $syncError}
	<div class="border-b border-red-700 bg-red-50 px-4 py-2 text-sm font-bold text-red-700">
		Error de sincronización: {$syncError}
	</div>
{/if}
{#if $syncWarnings.length > 0}
	<div class="border-b border-yellow-600 bg-yellow-50 px-4 py-2 text-sm font-bold text-yellow-800">
		{#each $syncWarnings as warning}
			<p>{warning}</p>
		{/each}
		<button type="button" onclick={() => syncWarnings.set([])} class="mt-1 underline">
			Descartar
		</button>
	</div>
{/if}

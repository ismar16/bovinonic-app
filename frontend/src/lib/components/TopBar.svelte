<script lang="ts">
	import { LogOut, RefreshCw, Search, MapPin } from 'lucide-svelte';
	import { goto } from '$app/navigation';

	import { logoutAndWipe, switchFarm } from '$lib/session';
	import { syncNow } from '$lib/sync';
	import {
		availableFarms,
		currentFarm,
		online,
		pendingCount,
		sessionUser,
		lastSyncResult,
		sessionChanging,
		sessionNotice,
		syncing,
		syncError,
		syncWarnings
	} from '$lib/stores';
	let query = $state('');

	let statusColor = $derived(
		$syncError
			? 'bg-red-600'
			: !$online || $pendingCount > 0 || !$lastSyncResult
				? 'bg-yellow-500'
				: 'bg-green-600'
	);
	let statusLabel = $derived(
		$syncing ? 'Sincronizando…' : $syncError
			? 'Error de sincronización'
			: !$online
				? `Modo campo · ${$pendingCount} pendientes`
				: $pendingCount > 0
					? `${$pendingCount} pendientes`
					: $lastSyncResult ? 'Datos al día' : 'Sin verificar'
	);
</script>

<header class="sticky top-0 z-10 flex min-h-16 items-center justify-between gap-3 border-b bg-[#fafaf7]/95 px-4 lg:px-8">
	<div class="flex min-w-0 items-center gap-2">
		<MapPin class="hidden h-4 w-4 text-[#8d987e] sm:block" />
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
	<form class="hidden w-full max-w-xs items-center gap-2 rounded-lg border bg-white px-3 lg:flex" onsubmit={(e) => {
		e.preventDefault(); void goto(`/herd?q=${encodeURIComponent(query.trim())}`);
	}}>
		<Search class="h-4 w-4 text-neutral-400" />
		<input bind:value={query} aria-label="Buscar un animal" placeholder="Buscar arete o nombre…" class="h-10 w-full bg-transparent text-xs outline-none" />
	</form>
	<div class="flex shrink-0 items-center gap-2">
		<button type="button" onclick={() => syncNow()} disabled={!$online || $syncing || $sessionChanging}
			class="flex min-h-10 items-center gap-2 rounded-lg border bg-white px-3 text-xs font-medium text-[#596c5c] disabled:opacity-60"
			title="Comprobar y sincronizar datos">
			<RefreshCw class="h-3.5 w-3.5 {$syncing ? 'animate-spin' : ''}" />
			<span class="hidden sm:inline">{statusLabel}</span>
			<span class="sm:hidden">{$pendingCount ? $pendingCount : 'Sync'}</span>
		</button>
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
	</div>
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

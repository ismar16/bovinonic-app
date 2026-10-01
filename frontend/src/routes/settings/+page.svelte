<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	import { logoutAndWipe } from '$lib/session';
	import { currentFarm, sessionUser } from '$lib/stores';

	const links = [
		{ href: '/reports', label: 'Reportes y exportación CSV', adminOnly: false },
		{ href: '/catalogs', label: 'Catálogos (potreros, propietarios, fierros)', adminOnly: true },
		{ href: '/users', label: 'Usuarios y roles', adminOnly: true }
	];

	onMount(() => {
		if (!$currentFarm) void goto('/');
	});
</script>

<svelte:head><title>Ajustes · Gestión Ganadera</title></svelte:head>

<div class="flex flex-col gap-4 pt-4">
	<h1 class="text-2xl font-extrabold">Ajustes</h1>

	<section class="rounded-md border-2 border-black p-4">
		<p class="text-sm text-neutral-600">Usuario</p>
		<p class="text-xl font-extrabold">{$sessionUser?.username ?? '—'}</p>
		<p class="mt-2 text-sm text-neutral-600">Finca</p>
		<p class="font-bold">{$currentFarm?.name ?? '—'}</p>
		<p class="mt-1 text-sm uppercase text-neutral-600">Rol: {$currentFarm?.role ?? '—'}</p>
	</section>

	{#each links as link (link.href)}
		{#if !link.adminOnly || $currentFarm?.role === 'admin'}
			<a
				href={link.href}
				class="flex h-14 items-center rounded-md border-2 border-black px-4 text-lg font-extrabold"
			>
				{link.label}
			</a>
		{/if}
	{/each}

	<button
		type="button"
		onclick={() => logoutAndWipe()}
		class="h-14 w-full rounded-md bg-red-700 text-xl font-extrabold text-white"
	>
		Cerrar sesión
	</button>
</div>

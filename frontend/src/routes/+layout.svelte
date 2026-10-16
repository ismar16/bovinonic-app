<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { useRegisterSW } from 'virtual:pwa-register/svelte';

	import BottomNav from '$lib/components/BottomNav.svelte';
	import QuickActionsFab from '$lib/components/QuickActionsFab.svelte';
	import TopBar from '$lib/components/TopBar.svelte';
	import { syncNow, refreshPendingCount, startAutoSync } from '$lib/sync';
	import { currentFarm, sessionUser, pendingCount, syncing } from '$lib/stores';
	import { restoreSession } from '$lib/session';
	import { ApiError } from '$lib/api';
	import { errorMessage } from '$lib/forms';
	import Notice from '$lib/components/Notice.svelte';

	let { children } = $props();

	const { needRefresh, updateServiceWorker } = useRegisterSW({});

	let sessionReady = $state(false);
	let initializing = $state(false);
	let startupError = $state('');
	async function initialize() {
		if (initializing) return;
		initializing = true; startupError = '';
		try { await restoreSession(); await syncNow(); sessionReady = true; }
		catch (cause) {
			if (cause instanceof ApiError && cause.statusCode === 401) await goto(`/login?next=${encodeURIComponent(page.url.pathname + page.url.search)}`);
			else startupError = errorMessage(cause, 'No se pudo abrir la finca. Revisá la conexión y volvé a intentar.');
		} finally { initializing = false; }
	}
	$effect(() => {
		if (browser && !isLogin && !sessionReady && !initializing && !startupError) {
			if ($sessionUser) sessionReady = true;
			else void initialize();
		}
	});

	let isLogin = $derived(page.url.pathname === '/login');
	const isForm = $derived(/\/(new|edit|status|bulk)$/.test(page.url.pathname) || ['/milking','/weighing','/health','/reproduction','/users'].includes(page.url.pathname));

	onMount(() => {
		void refreshPendingCount();
		return startAutoSync();
	});
</script>

<div class="min-h-screen bg-background pb-20 text-foreground lg:pb-0 {isLogin ? '' : 'lg:pl-60'}">
	{#if !isLogin && sessionReady}
		<TopBar />
	{/if}
	<main class="mx-auto w-full px-4 pb-8 {isLogin ? 'max-w-xl' : 'max-w-xl lg:max-w-7xl lg:px-8 lg:pt-4 lg:pb-28'}">
		{#if $needRefresh}<div class="notice mt-3">Hay una actualización disponible. Guardá tu formulario antes de continuar. <button type="button" disabled={$pendingCount > 0 || $syncing} onclick={() => updateServiceWorker(true)} class="ml-2 underline">Actualizar aplicación</button></div>{/if}
		{#if isLogin || sessionReady}
		{#key `${$currentFarm?.id}:${$currentFarm?.dataVersion ?? 0}:${page.params.collection ?? ''}:${page.params.id ?? ''}`}
			{@render children()}
		{/key}
		{:else if startupError}<div class="panel mt-8 space-y-4 p-6"><Notice tone="error" message={startupError} /><button type="button" class="action-button" onclick={initialize}>Volver a intentar</button><a href="/login" class="quiet-button ml-2">Iniciar sesión</a></div>{:else}<p class="empty-state mt-8">Abriendo tu finca…</p>{/if}
	</main>
	{#if !isLogin && sessionReady}
		<BottomNav />
		{#if !isForm}<QuickActionsFab />{/if}
	{/if}
</div>

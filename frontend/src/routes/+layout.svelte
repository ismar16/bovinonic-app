<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { useRegisterSW } from 'virtual:pwa-register/svelte';

	import BottomNav from '$lib/components/BottomNav.svelte';
	import QuickActionsFab from '$lib/components/QuickActionsFab.svelte';
	import TopBar from '$lib/components/TopBar.svelte';
	import { refreshPendingCount, startAutoSync } from '$lib/sync';
	import { currentFarm } from '$lib/stores';

	let { children } = $props();

	const { needRefresh, updateServiceWorker } = useRegisterSW({});

	$effect(() => {
		if ($needRefresh) {
			void updateServiceWorker(true);
		}
	});

	let isLogin = $derived(page.url.pathname === '/login');

	onMount(() => {
		void refreshPendingCount();
		return startAutoSync();
	});
</script>

<div class="min-h-screen bg-background pb-20 text-foreground lg:pb-0 {isLogin ? '' : 'lg:pl-60'}">
	{#if !isLogin}
		<TopBar />
	{/if}
	<main class="mx-auto w-full px-4 pb-8 {isLogin ? 'max-w-xl' : 'max-w-xl lg:max-w-7xl lg:px-8 lg:pt-4 lg:pb-28'}">
		{#key `${$currentFarm?.id}:${page.params.id ?? ''}`}
			{@render children()}
		{/key}
	</main>
	{#if !isLogin}
		<BottomNav />
		<QuickActionsFab />
	{/if}
</div>

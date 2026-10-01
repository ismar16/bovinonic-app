<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { useRegisterSW } from 'virtual:pwa-register/svelte';

	import BottomNav from '$lib/components/BottomNav.svelte';
	import TopBar from '$lib/components/TopBar.svelte';
	import { refreshPendingCount, startAutoSync } from '$lib/sync';

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

<div class="min-h-screen bg-white pb-20 text-black">
	{#if !isLogin}
		<TopBar />
	{/if}
	<main class="mx-auto w-full max-w-xl px-4 pb-8">
		{@render children()}
	</main>
	{#if !isLogin}
		<BottomNav />
	{/if}
</div>

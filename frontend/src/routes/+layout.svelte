<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { useRegisterSW } from 'virtual:pwa-register/svelte';

	import StatusBar from '$lib/components/StatusBar.svelte';
	import { refreshPendingCount, startAutoSync } from '$lib/sync';

	let { children } = $props();

	const { needRefresh, updateServiceWorker } = useRegisterSW({});

	$effect(() => {
		if ($needRefresh) {
			void updateServiceWorker(true);
		}
	});

	onMount(() => {
		void refreshPendingCount();
		return startAutoSync();
	});
</script>

<div class="min-h-screen bg-white text-black">
	<StatusBar />
	<main class="mx-auto w-full max-w-xl px-4 pb-8">
		{@render children()}
	</main>
</div>

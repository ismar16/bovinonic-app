<script lang="ts">
	import { online, pendingCount, syncing } from '$lib/stores';
</script>

<header
	class="sticky top-0 z-10 flex h-12 items-center justify-between border-b-2 border-black px-4 text-sm font-bold {$online
		? 'bg-green-600 text-white'
		: 'bg-yellow-400 text-black'}"
>
	<span>Gestión Ganadera</span>
	<span aria-live="polite">
		{#if $syncing}
			Sincronizando…
		{:else if $online}
			Conectado{#if $pendingCount > 0}&nbsp;· {$pendingCount} pendiente{$pendingCount === 1 ? '' : 's'}{/if}
		{:else}
			Modo campo · {$pendingCount} pendiente{$pendingCount === 1 ? '' : 's'}
		{/if}
	</span>
</header>

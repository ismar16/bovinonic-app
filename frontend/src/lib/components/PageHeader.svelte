<script lang="ts">
	import { ArrowLeft } from 'lucide-svelte';
	let { title, description = '', eyebrow = 'Gestión de la finca', backHref, backLabel = 'Volver' }:
		{ title: string; description?: string; eyebrow?: string; backHref?: string; backLabel?: string } = $props();
</script>

<header class="page-header">
	{#if backHref}<a href={backHref} class="back-link"><ArrowLeft class="h-4 w-4" />{backLabel}</a>{/if}
	<p class="eyebrow">{eyebrow}</p>
	<h1 class="page-title">{title}</h1>
	{#if description}<p class="page-description">{description}</p>{/if}
</header>

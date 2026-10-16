<script lang="ts">
	let { class: className = '', strokeWidth = 1.6 }: { class?: string; strokeWidth?: number | string } = $props();
</script>

<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width={strokeWidth} stroke-linecap="round" stroke-linejoin="round" class={className} aria-hidden="true">
	<path d="M10 11C5 11 3 8 4 4c2 3 4 4 7 3M22 11c5 0 7-3 6-7-2 3-4 4-7 3" />
	<path d="M9 12 4 13l3 5 3-1m13-5 5 1-3 5-3-1M11 8c2-1 8-1 10 0l2 13c0 5-3 7-7 7s-7-2-7-7z" />
	<path d="M10 22c2-2 10-2 12 0" />
	<circle cx="12.5" cy="15" r=".9" fill="currentColor" stroke="none" /><circle cx="19.5" cy="15" r=".9" fill="currentColor" stroke="none" />
	<path d="M13 24h.5m5 0h.5" />
</svg>

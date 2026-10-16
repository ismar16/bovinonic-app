<script lang="ts">
	let { message, tone = 'info' }: { message: string; tone?: 'info' | 'error' | 'success' | 'warning' } = $props();
</script>
{#if message}<p class="notice {tone}" role={tone === 'error' ? 'alert' : 'status'}>{message}</p>{/if}

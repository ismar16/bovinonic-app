<script lang="ts">import { page } from '$app/state';import CalvingHistory from '$lib/components/CalvingHistory.svelte';</script>
<CalvingHistory id={page.params.id} />

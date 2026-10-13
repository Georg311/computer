<script lang="ts">
	import { UnifiedButton } from './UnifiedButton.svelte';
	import { chatEnabled } from '$lib/stores/chat';
</script>

{#if chatEnabled}
	<UnifiedButton 
		mode="standalone" 
	/>
{/if}

<script lang="ts">
	import MarkdownRenderer from '$lib/components/markdown/MarkdownRenderer.svelte';

	let { content }: { content: string } = $props();
</script>

<div class="h-full overflow-y-auto px-6 py-5">
	<div class="mx-auto max-w-3xl"><MarkdownRenderer {content} /></div>
</div>

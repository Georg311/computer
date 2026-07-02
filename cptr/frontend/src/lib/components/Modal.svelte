<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		onclose: () => void;
		class?: string;
		overlayClass?: string;
		children: Snippet;
	}

	let {
		onclose,
		class: className = '',
		overlayClass = 'bg-black/50 items-center justify-center',
		children
	}: Props = $props();

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="fixed inset-0 z-[100] flex {overlayClass}" onmousedown={onclose} onkeydown={() => {}}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="bg-white dark:bg-[#0a0a0a] dark:border dark:border-white/8 rounded-3xl overflow-visible shadow-2xl {className}"
		onmousedown={(e) => e.stopPropagation()}
		onkeydown={() => {}}
	>
		{@render children()}
	</div>
</div>

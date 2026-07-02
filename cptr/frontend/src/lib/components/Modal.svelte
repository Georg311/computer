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
		class="app-theme app-surface border rounded-3xl overflow-visible shadow-2xl {className}"
		style="background: var(--app-bg); color: var(--app-fg);"
		onmousedown={(e) => e.stopPropagation()}
		onkeydown={() => {}}
	>
		{@render children()}
	</div>
</div>

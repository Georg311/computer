<script lang="ts">
	interface Props {
		/** The formatted shortcut text to display (e.g. "⌘N", "⌃`"). */
		text: string;
		/** Additional CSS classes (e.g. layout utilities from the parent). */
		class?: string;
	}
	let { text, class: className = '' }: Props = $props();
</script>

<span
	class="key-pill inline-flex items-center justify-center h-[1.125rem] px-[0.3125rem] rounded-full text-[0.625rem] font-medium leading-none {className}"
	>{text}</span
>

<style>
	.key-pill {
		background: var(--app-hover);
		color: var(--app-fg-muted);
	}
</style>

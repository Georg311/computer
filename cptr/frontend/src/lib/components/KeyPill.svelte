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
	class="inline-flex items-center justify-center h-[1.125rem] px-[0.3125rem] rounded-full text-[0.625rem] font-medium leading-none bg-[#e8e8e8] text-[#555] dark:bg-[#1e1e1e] dark:text-[#999] {className}"
	>{text}</span
>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	interface Props {
		title: string;
		summary?: string;
		open?: boolean;
		indent?: boolean;
		children: Snippet;
	}

	let { title, summary = '', open = false, indent = false, children }: Props = $props();
	let expanded = $state(open);
</script>

<div>
	<button class="flex items-center gap-1.5 w-full text-left" onclick={() => (expanded = !expanded)}>
		<span
			class="flex items-center justify-center w-4 h-4 shrink-0 text-gray-400 dark:text-gray-600 transition-transform duration-100"
			style="transform: rotate({expanded ? '90deg' : '0deg'})"
		>
			<Icon name="chevron-right" size={11} />
		</span>
		<span class="text-xs text-gray-400 dark:text-gray-600">{title}</span>
		{#if !expanded && summary}
			<span
				class="text-[0.6875rem] text-gray-400 dark:text-gray-600 font-mono ml-auto truncate max-w-[60%] text-right"
				>{summary}</span
			>
		{/if}
	</button>
	{#if expanded}
		<div class="mt-2" class:pl-5.5={indent}>
			{@render children()}
		</div>
	{/if}
</div>

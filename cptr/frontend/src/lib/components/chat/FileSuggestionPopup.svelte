<script lang="ts">
	import Icon from '../Icon.svelte';
	import { fileIconName } from '$lib/utils/fileIcon';

	interface SuggestionItem {
		id: string;
		label: string;
		type: string;
	}

	interface Props {
		items: SuggestionItem[];
		selectedIndex: number;
		onselect: (index: number) => void;
	}
	let { items, selectedIndex, onselect }: Props = $props();

	let listEl: HTMLDivElement | undefined = $state();

	// Scroll selected item into view
	$effect(() => {
		if (listEl && selectedIndex >= 0) {
			const el = listEl.children[selectedIndex] as HTMLElement | undefined;
			el?.scrollIntoView({ block: 'nearest' });
		}
	});

	function relativePath(fullPath: string): string {
		// Show last 2 path segments as context
		const parts = fullPath.split('/');
		if (parts.length <= 2) return '';
		return parts.slice(-3, -1).join('/');
	}
</script>

<div
	class="fixed z-50 w-60 max-h-40 overflow-y-auto rounded-xl bg-white dark:bg-[#1a1a1a] border border-gray-150 dark:border-white/6 shadow-xl p-0.5"
>
	{#if items.length === 0}
		<div class="flex items-center h-6 px-2 text-xs text-gray-400 dark:text-gray-600">
			No files found
		</div>
	{:else}
		<div
			class="mb-0.5 px-2 pt-1 pb-0.5 text-[0.625rem] leading-none text-gray-400 dark:text-gray-600"
		>
			Files
		</div>
		<div bind:this={listEl}>
			{#each items as item, i (item.id)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<button
					class="flex items-center gap-2 w-full h-6 px-2 rounded-xl text-xs text-left transition-colors duration-75
						{i === selectedIndex
						? 'bg-gray-50 dark:bg-white/5 text-gray-900 dark:text-white'
						: 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-white/5 hover:text-gray-900 dark:hover:text-white'}"
					onmousedown={(e) => {
						e.preventDefault();
						onselect(i);
					}}
					onmouseenter={() => (selectedIndex = i)}
				>
					<span
						class="flex items-center justify-center w-4 shrink-0 {item.type === 'directory'
							? 'text-gray-500 dark:text-gray-400'
							: 'text-gray-400 dark:text-gray-500'}"
					>
						<Icon name={fileIconName(item.label, item.type)} size={14} />
					</span>
					<span class="flex-1 min-w-0 flex items-baseline gap-1.5 overflow-hidden">
						<span class="truncate">{item.label}</span>
						{#if relativePath(item.id)}
							<span class="text-[0.625rem] text-gray-400 dark:text-gray-600 truncate shrink-0"
								>{relativePath(item.id)}</span
							>
						{/if}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

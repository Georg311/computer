<script lang="ts">
	import Icon from '../Icon.svelte';
	import { fileIconName } from '$lib/utils/fileIcon';
	import { t } from '$lib/i18n';
	import { tooltip } from '$lib/tooltip';

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
	class="app-theme app-surface fixed z-50 w-64 max-h-40 overflow-y-auto rounded-xl border shadow-xl p-0.5"
>
	{#if items.length === 0}
		<div class="app-muted flex items-center h-6 px-2 text-xs">{$t('quickOpen.noFiles')}</div>
	{:else}
		<div class="app-muted mb-0.5 px-2 pt-1 pb-0.5 text-[0.625rem] leading-none">
			{$t('search.files')}
		</div>
		<div bind:this={listEl}>
			{#each items as item, i (item.id)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<button
					class="suggestion-row flex items-center gap-2 w-full h-6 px-2 rounded-xl text-xs text-left transition-colors duration-75
						{i === selectedIndex ? 'app-interactive-active' : ''}"
					onmousedown={(e) => {
						e.preventDefault();
						onselect(i);
					}}
					onmouseenter={() => (selectedIndex = i)}
					use:tooltip={{ content: item.id, placement: 'top' }}
				>
					<span class="app-icon-muted flex items-center justify-center w-4 shrink-0">
						<Icon name={fileIconName(item.label, item.type)} size={14} />
					</span>
					<span class="flex-1 min-w-0 flex items-baseline gap-1.5 overflow-hidden">
						<span class="truncate">{item.label}</span>
						{#if relativePath(item.id)}
							<span class="app-muted text-[0.625rem] truncate shrink-0"
								>{relativePath(item.id)}</span
							>
						{/if}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.suggestion-row {
		color: color-mix(in oklab, var(--app-fg) 62%, var(--app-bg));
	}

	.suggestion-row:hover {
		background: color-mix(in oklab, var(--app-fg) 6%, transparent);
		color: var(--app-fg);
	}
</style>

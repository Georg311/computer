<script lang="ts">
	interface SuggestionItem {
		id: string;
		label: string;
		description?: string;
		source?: string;
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
</script>

<div
	class="app-theme app-surface fixed z-50 w-60 max-h-40 overflow-y-auto rounded-xl border shadow-xl p-0.5"
>
	{#if items.length === 0}
		<div class="app-muted flex items-center h-6 px-2 text-xs">No skills found</div>
	{:else}
		<div class="app-muted px-2 pt-1 pb-0.5 text-[0.625rem] leading-none">Skills</div>
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
					title={item.description}
				>
					<span class="app-icon-muted flex items-center justify-center w-4 shrink-0">
						<svg viewBox="0 0 16 16" fill="currentColor" class="size-3.5">
							<path
								d="M8.75 1a.75.75 0 0 0-1.5 0v1.249c-1.373.158-2.476.682-3.33 1.536C3.066 4.639 2.5 5.77 2.5 7.25c0 1.296-.266 2.193-.613 2.852-.35.663-.83 1.132-1.268 1.507a.75.75 0 0 0 .494 1.315h3.137a3.75 3.75 0 0 0 7.5 0h3.137a.75.75 0 0 0 .494-1.315c-.438-.375-.919-.844-1.268-1.507-.347-.659-.613-1.556-.613-2.852 0-1.48-.566-2.611-1.42-3.465-.854-.854-1.957-1.378-3.33-1.536V1ZM6.5 12.924a2.25 2.25 0 0 0 3 0h-3Z"
							/>
						</svg>
					</span>
					<span class="flex-1 min-w-0 flex items-baseline gap-1.5 overflow-hidden">
						<span class="truncate">{item.label}</span>
						{#if item.source && item.source !== 'workspace'}
							<span class="app-muted text-[0.625rem] truncate shrink-0">{item.source}</span>
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

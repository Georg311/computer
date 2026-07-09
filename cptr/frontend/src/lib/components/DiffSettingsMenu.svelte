<script lang="ts">
	import { diffDisplayMode, hideWhitespaceChanges } from '$lib/stores/gitDiffSettings';
	import DropdownMenu from './DropdownMenu.svelte';
	import Icon from './Icon.svelte';

	interface Props {
		anchor: HTMLElement;
		onclose: () => void;
		preferAbove?: boolean;
		forceAbove?: boolean;
	}

	let { anchor, onclose, preferAbove = false, forceAbove = false }: Props = $props();

	function toggleWhitespace() {
		hideWhitespaceChanges.set(!$hideWhitespaceChanges);
	}
</script>

<DropdownMenu
	items={[]}
	{anchor}
	{onclose}
	{preferAbove}
	{forceAbove}
	align="end"
	className="w-56"
	headerDivider={false}
	footerDivider={false}
>
	<div class="px-1 pb-1 text-xs">
		<div
			class="px-2 pb-0.5 pt-1 text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600"
		>
			Whitespace
		</div>

		<button
			type="button"
			class="app-interactive app-muted flex h-7 w-full items-center gap-2 rounded-xl px-2 text-left text-xs transition-colors duration-75"
			onclick={toggleWhitespace}
			aria-pressed={$hideWhitespaceChanges}
		>
			<Icon name="code" size={14} class="app-icon-muted shrink-0" />
			<span class="min-w-0 flex-1 truncate">Hide whitespace</span>
			<span
				class="relative h-4 w-7 shrink-0 rounded-full transition-colors duration-150 {$hideWhitespaceChanges
					? 'bg-gray-900 dark:bg-white'
					: 'bg-gray-300 dark:bg-gray-700'}"
			>
				<span
					class="absolute top-[0.125rem] h-3 w-3 rounded-full transition-all duration-150 {$hideWhitespaceChanges
						? 'left-[0.875rem] bg-white dark:bg-black'
						: 'left-[0.125rem] bg-white dark:bg-gray-500'}"
				></span>
			</span>
		</button>

		<div
			class="px-2 pb-0.5 pt-1.5 text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600"
		>
			Diff Display
		</div>

		<button
			type="button"
			class="flex h-7 w-full items-center gap-2 rounded-xl px-2 text-left text-xs transition-colors duration-75 {$diffDisplayMode ===
			'unified'
				? 'app-interactive-active'
				: 'app-interactive app-muted'}"
			onclick={() => diffDisplayMode.set('unified')}
		>
			<Icon name="list" size={14} class="app-icon-muted shrink-0" />
			<span class="min-w-0 flex-1 truncate text-left">Unified</span>
			{#if $diffDisplayMode === 'unified'}
				<Icon name="check" size={12} class="app-icon-muted shrink-0" />
			{/if}
		</button>
		<button
			type="button"
			class="flex h-7 w-full items-center gap-2 rounded-xl px-2 text-left text-xs transition-colors duration-75 {$diffDisplayMode ===
			'split'
				? 'app-interactive-active'
				: 'app-interactive app-muted'}"
			onclick={() => diffDisplayMode.set('split')}
		>
			<Icon name="split-view" size={14} class="app-icon-muted shrink-0" />
			<span class="min-w-0 flex-1 truncate">Split</span>
			{#if $diffDisplayMode === 'split'}
				<Icon name="check" size={12} class="app-icon-muted shrink-0" />
			{/if}
		</button>
	</div>
</DropdownMenu>

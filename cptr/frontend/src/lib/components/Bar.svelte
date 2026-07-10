<script lang="ts">
	import {
		activeWorkspace,
		sidebarOpen,
		splitActive,
		splitCurrentTab,
		setSplitDirection
	} from '$lib/stores';
	import type { SplitDirection } from '$lib/stores';
	import Icon from './Icon.svelte';
	import DropdownMenu from './DropdownMenu.svelte';
	import { tooltip } from '$lib/tooltip';
	import { t } from '$lib/i18n';

	let splitBtnEl: HTMLButtonElement | undefined = $state();
	let showSplitMenu = $state(false);

	// Only show split controls on wider screens
	let isWideScreen = $state(typeof window !== 'undefined' ? window.innerWidth >= 1024 : false);

	function toggleSidebar() {
		sidebarOpen.update((v) => !v);
	}

	function handleResize() {
		isWideScreen = window.innerWidth >= 1024;
	}

	const splitMenuItems = $derived.by(() => {
		const direction = $activeWorkspace?.splitDirection ?? 'horizontal';
		return [
			{
				label: $t('bar.splitRight'),
				icon: 'split-horizontal',
				active: direction === 'horizontal',
				onclick: () => {
					setSplitDirection('horizontal');
					splitCurrentTab('horizontal');
				}
			},
			{
				label: $t('bar.splitDown'),
				icon: 'split-vertical',
				active: direction === 'vertical',
				onclick: () => {
					setSplitDirection('vertical');
					splitCurrentTab('vertical');
				}
			}
		];
	});

	import { onMount, onDestroy } from 'svelte';

	onMount(() => {
		window.addEventListener('resize', handleResize);
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('resize', handleResize);
		}
	});
</script>

<nav
	class="wco-bar flex items-center h-9 px-1.5 gap-1 shrink-0 select-none border-b border-gray-200 dark:border-white/6"
>
	<!-- Sidebar toggle (only when closed) -->
	{#if !$sidebarOpen}
		<button
			class="flex items-center justify-center w-7 h-7 rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-100"
			onclick={toggleSidebar}
			aria-label={$t('bar.toggleSidebar')}
			use:tooltip={$t('bar.sidebar')}
		>
			<Icon name="sidebar-expand" size={14} />
		</button>
	{/if}

	<!-- Workspace name -->
	{#if $activeWorkspace}
		<span
			class="text-[0.6875rem] font-medium text-gray-500 dark:text-gray-500 px-1 truncate flex-1 min-w-0"
		>
			{$activeWorkspace.name}
		</span>
	{:else}
		<span class="flex-1"></span>
	{/if}

	<!-- Right-side controls -->
	<div class="flex items-center gap-0.5 shrink-0">
		<!-- Split button (only on wide screens with a workspace open) -->
		{#if $activeWorkspace && isWideScreen}
			<button
				bind:this={splitBtnEl}
				class="flex items-center justify-center w-7 h-7 rounded-lg transition-colors duration-100 shrink-0
					{$splitActive
					? 'bg-gray-200 text-gray-900 dark:bg-white/8 dark:text-white'
					: 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'}"
				onclick={() => (showSplitMenu = !showSplitMenu)}
				aria-label={$t('a11y.splitEditor')}
				use:tooltip={$t('a11y.splitEditor')}
			>
				<Icon
					name={$activeWorkspace?.splitDirection === 'vertical'
						? 'split-vertical'
						: 'split-horizontal'}
					size={14}
				/>
			</button>
		{/if}
	</div>
</nav>

{#if showSplitMenu && splitBtnEl}
	<DropdownMenu
		items={splitMenuItems}
		anchor={splitBtnEl}
		onclose={() => (showSplitMenu = false)}
	/>
{/if}

<style>
	@media (display-mode: window-controls-overlay) {
		.wco-bar {
			padding-left: env(titlebar-area-x, 0);
			width: env(titlebar-area-width, 100%);
			height: env(titlebar-area-height, 2.25rem);
			app-region: drag;
		}
		.wco-bar button,
		.wco-bar a {
			app-region: no-drag;
		}
	}
</style>

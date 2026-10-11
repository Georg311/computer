<script lang="ts">
	import { chatEnabled } from '$lib/stores/chat';
	import { openChatTab, activeWorkspace, openBrowserTab, homeState, activeGroup } from '$lib/stores';
	import { get } from 'svelte/store';
	import Icon from './Icon.svelte';
	import { t } from '$lib/i18n';
	import { createEntry } from '$lib/apis/files';
	import { createSession } from '$lib/apis/terminal';
	import { tooltip } from '$lib/tooltip';

	interface Props {
		/** Optional: if provided, the FAB will attempt to open a chat in this specific group. */
		groupId?: string;
	}

	let { groupId }: Props = $props();

	let open = $state(false);
	let btnEl: HTMLButtonElement | undefined = $state();
	let menuEl: HTMLDivElement | undefined = $state();
	let pos = $state<{ x: number; bottom: number }>({ x: -9999, bottom: -9999 });
	let ready = $state(false);

	function handleNewChat() {
		const ag = get(activeGroup);
		const hs = get(homeState);
		const targetGroupId = groupId || 
			(ag ? ag.id : (hs ? hs.groups[0].id : undefined));

		if (targetGroupId) {
			openChatTab(undefined, targetGroupId);
		} else {
			openChatTab(undefined);
		}
		closeMenu();
	}


	async function handleNewFile() {
		const workspace = get(activeWorkspace);
		if (!workspace) return;
		const cwd = workspace.fileBrowserCwd ?? workspace.path;
		const newFilePath = cwd.endsWith('/') ? cwd + 'new_file.txt' : cwd + '/new_file.txt';
		try {
			await createEntry(newFilePath, 'file');
		} catch (e) {
			console.error(e);
		}
		closeMenu();
	}

	async function handleNewTerminal() {
		const workspace = get(activeWorkspace);
		if (!workspace) return;
		const cwd = workspace.fileBrowserCwd ?? workspace.path;
		try {
			await createSession(cwd);
		} catch (e) {
			console.error(e);
		}
		closeMenu();
	}

	function handleNewBrowser() {
		openBrowserTab(undefined, 'about:blank');
		closeMenu();
	}

	function toggle() {
		if (open) {
			closeMenu();
		} else {
			open = true;
		}
	}

	$effect(() => {
		if (open && btnEl && menuEl) {
			setTimeout(() => updatePosition(), 0);
		}
	});

	function updatePosition() {
		if (!btnEl || !menuEl) return;
		const rect = btnEl.getBoundingClientRect();
		const mw = menuEl.offsetWidth;
		const vh = window.innerHeight;
		let x = rect.left;
		if (x + mw > window.innerWidth - 8) x = window.innerWidth - mw - 8;
		if (x < 8) x = 8;
		pos = { x, bottom: vh - rect.top + 4 };
		ready = true;
	}

	function closeMenu() {
		open = false;
		ready = false;
	}
</script>

{#if $chatEnabled}
	{#if open}
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="fixed inset-0 z-[49]" onclick={closeMenu}></div>

		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			bind:this={menuEl}
			class="app-theme app-surface fixed z-[50] w-48 rounded-2xl border shadow-xl p-1 overflow-hidden"
			style="left: {pos.x}px; bottom: {pos.bottom}px; opacity: {ready ? 1 : 0}; pointer-events: {ready ? 'auto' : 'none'};"
			onclick={(e) => e.stopPropagation()}
		>
			<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
				onclick={handleNewChat}
				use:tooltip={$t('bar.newChat')}
			>
				<Icon name="chat-bubble" size={20} />
				<span class="flex-1 text-left truncate">{$t('bar.newChat')}</span>
			</button>

			<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
				onclick={handleNewFile}
				use:tooltip={$t('files.newFile')}
			>
				<Icon name="page-text" size={20} />
				<span class="flex-1 text-left truncate">{$t('files.newFile')}</span>
			</button>

			<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
				onclick={handleNewTerminal}
				use:tooltip={$t('bar.newTerminal')}
			>
				<Icon name="terminal" size={20} />
				<span class="flex-1 text-left truncate">{$t('bar.newTerminal')}</span>
			</button>

			<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
				onclick={handleNewBrowser}
				use:tooltip={$t('bar.newBrowser')}
			>
				<Icon name="globe" size={20} />
				<span class="flex-1 text-left truncate">{$t('bar.newBrowser')}</span>
			</button>
		</div>
	{/if}

	<button
		bind:this={btnEl}
		class="fab-button fixed bottom-16 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-sky-500 text-white shadow-lg transition-transform active:scale-95 md:hidden"
		onclick={toggle}
		aria-label={$t('bar.newChat')}
		use:tooltip={$t('bar.newChat')}
	>
		<Icon name={open ? 'xmark' : 'plus'} size={28} />
	</button>
{/if}

<style>
	.fab-button::after {
		content: '';
		position: absolute;
		top: -10px;
		left: -10px;
		right: -10px;
		bottom: -10px;
	}
</style>

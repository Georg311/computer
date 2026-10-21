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
		/** 'fab' for the floating action button, 'chat' to be used inside the chat input, 'files' for file browser. */
		mode?: 'fab' | 'chat' | 'files';
		/** If in 'chat' mode, whether the user can send a message. */
		canSend?: boolean;
		/** If in 'chat' mode, whether a message is currently being streamed. */
		streaming?: boolean;
		/** If in 'chat' mode, the function to call when the send action is triggered. */
		onsend?: () => void;
		/** If in 'chat' mode, the function to call when the stop action is triggered. */
		oncancel?: () => void;
		/** If in 'chat' mode, the function to call when the queue action is triggered. */
		onqueue?: () => void;
		/** If in 'chat' mode, what color/icon to show for queue/steer. */
		isQueued?: boolean;
	}

	let { 
		groupId, 
		mode = 'fab',
		canSend = false,
		streaming = false,
		onsend,
		oncancel,
		onqueue,
		isQueued = false
	}: Props = $props();

	let open = $state(false);
	let btnEl: HTMLButtonElement | undefined = $state();
	let menuEl: HTMLDivElement | undefined = $state();
	let pos = $state<{ x: number; bottom: number }>({ x: -9999, bottom: -9999 });
	let ready = $state(false);

	function handleClick() {
		if (mode === 'fab' || mode === 'files') {
			toggle();
		} else {
			if (streaming && oncancel) {
				oncancel();
			} else if (isQueued && onqueue) {
				onqueue();
			} else if (onsend) {
				onsend();
			}
		}
	}

	function getIcon() {
		if (mode === 'fab' || mode === 'files') {
			return open ? 'xmark' : 'plus';
		}
		
		if (streaming) {
			if (isQueued) return 'arrow-up-circle';
			if (oncancel) return 'stop';
		}
		
		return 'arrow-right-circle';
	}

	function getButtonClass() {
		if (mode === 'fab') {
			return 'fab-button fixed bottom-16 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-sky-500 text-white shadow-lg transition-transform active:scale-95';
		}
		if (mode === 'files') {
			return 'files-fab-button fixed bottom-2 right-2 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-sky-500 text-white shadow-md transition-transform active:scale-95 hover:bg-sky-600';
		}
		
		let base = 'flex items-center justify-center rounded-full p-3 transition ';
		if (streaming && oncancel && !isQueued) {
			return base + 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600';
		}
		if (isQueued) {
			return base + 'bg-orange-500 text-white hover:bg-orange-600';
		}
		if (canSend) {
			return base + 'bg-black text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-white/90';
		}
		return base + 'text-white bg-gray-200 dark:text-gray-900 dark:bg-gray-700 cursor-default';
	}

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
		const newFilePath = cwd.endsWith('/') ? cwd + '/new_file.txt' : cwd + '/new_file.txt';
		try {
			await createEntry(newFilePath, 'file');
		} catch (e) {
			console.error(e);
		}
		closeMenu();
	}

	async function handleNewFolder() {
		const workspace = get(activeWorkspace);
		if (!workspace) return;
		const cwd = workspace.fileBrowserCwd ?? workspace.path;
		const newFolderPath = cwd.endsWith('/') ? cwd + '/new_folder' : cwd + '/new_folder';
		try {
			await createEntry(newFolderPath, 'folder');
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
			{#if mode === 'files'}
				<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
					onclick={handleNewFile}
					use:tooltip={$t('files.newFile')}
				>
					<Icon name="page-text" size={20} />
					<span class="flex-1 text-left truncate">{$t('files.newFile')}</span>
				</button>

				<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
					onclick={handleNewFolder}
					use:tooltip={$t('files.newFolder')}
				>
					<Icon name="folder" size={20} />
					<span class="flex-1 text-left truncate">{$t('files.newFolder')}</span>
				</button>

				<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
					onclick={handleNewTerminal}
					use:tooltip={$t('bar.newTerminal')}
				>
					<Icon name="terminal" size={20} />
					<span class="flex-1 text-left truncate">{$t('bar.newTerminal')}</span>
				</button>
			{:else}
				{#if chatEnabled}
				<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
					onclick={handleNewChat}
					use:tooltip={$t('bar.newChat')}
				>
					<Icon name="chat-bubble" size={20} />
					<span class="flex-1 text-left truncate">{$t('bar.newChat')}</span>
				</button>
				{/if}

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
			{/if}
		</div>
	{/if}

	<button
		bind:this={btnEl}
		class={getButtonClass()}
		class:md:hidden={mode === 'fab'}
		onclick={handleClick}
		aria-label={mode === 'files' ? $t('files.newFile') : $t('bar.newChat')}
		use:tooltip={mode === 'files' ? $t('files.newFile') : $t('bar.newChat')}
	>
		<Icon name={getIcon()} size={36} />
	</button>

<style>
	.fab-button::after {
		content: '';
		position: absolute;
		top: -10px;
		left: -10px;
		right: -10px;
		bottom: -10px;
	}
	.files-fab-button::after {
		content: '';
		position: absolute;
		top: -8px;
		left: -8px;
		right: -8px;
		bottom: -8px;
	}
</style>

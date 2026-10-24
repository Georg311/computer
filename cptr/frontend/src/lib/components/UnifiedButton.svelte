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

	// Long press detection for chat mode
	let pressTimer: ReturnType<typeof setTimeout> | null = null;
	let isLongPress = false;
	const LONG_PRESS_MS = 500;

	// Filename dialog state
	let showFilenameDialog = $state(false);
	let filenameInput: HTMLInputElement | undefined = $state();
	let filenameType = $state(''); // 'file' or 'folder'

	// Action dialog state (for long press in chat)
	let showActionDialog = $state(false);

	function handleClick(e: Event) {
		// Always clear the timer on click (prevents late long-press)
		if (pressTimer) {
			clearTimeout(pressTimer);
			pressTimer = null;
		}

		if (mode === 'fab' || mode === 'files') {
			toggle();
			return;
		}

		// Chat mode
		// If menu is open, close it
		if (open) {
			closeMenu();
			return;
		}

		// Prevent default click behavior for long press
		if (isLongPress) {
			e.preventDefault();
			isLongPress = false;
			showActionDialog = true;
			return;
		}

		// Normal click
		console.log('[UnifiedButton] handleClick — mode:', mode, 'streaming:', streaming, 'canSend:', canSend, 'onqueue:', !!onqueue, 'oncancel:', !!oncancel, 'onsend:', !!onsend);
		if (streaming && canSend) {
			// Streaming + text = queue the message
			console.log('[UnifiedButton] → calling onqueue');
			if (onqueue) {
				onqueue();
			}
		} else if (streaming && !canSend && oncancel) {
			// Streaming + no text = stop generation
			console.log('[UnifiedButton] → calling oncancel');
			oncancel();
		} else if (canSend && onsend) {
			// Not streaming + text = send message
			console.log('[UnifiedButton] → calling onsend');
			onsend();
		} else {
			// No text, not streaming: open menu (like FAB)
			console.log('[UnifiedButton] → calling toggle');
			toggle();
		}
	}

	function handlePointerDown() {
		if (mode !== 'chat') return;
		isLongPress = false;
		pressTimer = setTimeout(() => {
			isLongPress = true;
			console.log('[UnifiedButton] LONG PRESS triggered!', mode);
		}, LONG_PRESS_MS);
		console.log('[UnifiedButton] handlePointerDown — mode:', mode, 'timer started');
	}

	function handlePointerUp(e: Event) {
		// Don't clear the timer here — let the click handler decide
		// On touch devices pointerup fires before the 500ms timeout
		console.log('[UnifiedButton] handlePointerUp');
	}

	function handlePointerCancel() {
		if (pressTimer) {
			clearTimeout(pressTimer);
			pressTimer = null;
		}
		console.log('[UnifiedButton] handlePointerCancel');
	}

	function getIcon() {
		if (mode === 'fab' || mode === 'files') {
			return open ? 'xmark' : 'plus';
		}

		// Chat mode
		if (streaming) {
			if (isQueued) return 'arrow-up-circle';
			if (oncancel) return 'stop';
		}

		// Not streaming, no text: blue plus
		if (!canSend && !streaming) {
			return 'plus';
		}

		return 'arrow-right';
	}

	function getButtonClass() {
		if (mode === 'fab') {
			return 'fab-button fixed bottom-16 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-indigo-800 text-white shadow-lg shadow-indigo-600/30 transition-transform active:scale-95 hover:shadow-xl hover:shadow-indigo-600/40';
		}
		if (mode === 'files') {
			return 'files-fab-button fixed bottom-2 right-2 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-indigo-800 text-white shadow-md shadow-indigo-600/20 transition-transform active:scale-95 hover:bg-indigo-800';
		}

		let base = 'flex items-center justify-center rounded-full p-3 transition ';

		if (streaming && oncancel && !isQueued) {
			// Stop button: gray
			return base + 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600';
		}
		if (isQueued || (streaming && isQueued)) {
			// Queue button: orange
			return base + 'bg-orange-500 text-white hover:bg-orange-600';
		}
		if (canSend) {
			// Send button: gradient
			return base + 'bg-gradient-to-br from-blue-600 to-indigo-800 text-white hover:from-blue-700 hover:to-indigo-900 shadow-md shadow-indigo-600/20';
		}
		// No text, not streaming: blue plus
		return base + 'bg-gradient-to-br from-blue-600 to-indigo-800 text-white hover:from-blue-700 hover:to-indigo-900 cursor-pointer shadow-md shadow-indigo-600/20';
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

	async function handleCreateFile(name: string) {
		const workspace = get(activeWorkspace);
		if (!workspace) return;
		const cwd = workspace.fileBrowserCwd ?? workspace.path;
		const newFilePath = cwd.endsWith('/') ? cwd + name : cwd + '/' + name;
		try {
			await createEntry(newFilePath, 'file');
		} catch (e) {
			console.error(e);
		}
		closeMenu();
	}

	async function handleCreateFolder(name: string) {
		const workspace = get(activeWorkspace);
		if (!workspace) return;
		const cwd = workspace.fileBrowserCwd ?? workspace.path;
		const newFolderPath = cwd.endsWith('/') ? cwd + name : cwd + '/' + name;
		try {
			await createEntry(newFolderPath, 'directory');
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

	function startFilenameDialog(type: 'file' | 'folder') {
		filenameType = type;
		showFilenameDialog = true;
		setTimeout(() => {
			if (filenameInput) {
				filenameInput.focus();
				filenameInput.select();
			}
		}, 50);
	}

	async function confirmFilename() {
		if (!filenameInput?.value) {
			showFilenameDialog = false;
			return;
		}
		const name = filenameInput.value.trim();
		if (filenameType === 'file' && !name) {
			showFilenameDialog = false;
			return;
		}
		if (filenameType === 'folder' && !name) {
			showFilenameDialog = false;
			return;
		}

		if (filenameType === 'file') {
			await handleCreateFile(name);
		} else {
			await handleCreateFolder(name);
		}
		showFilenameDialog = false;
	}

	function cancelFilenameDialog() {
		showFilenameDialog = false;
	}

	function handleActionSelect(action: 'queue' | 'steer') {
		showActionDialog = false;
		if (action === 'queue' && onqueue) {
			onqueue();
		} else if (action === 'steer' && oncancel) {
			oncancel();
		}
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

<!-- FAB Menu -->
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
			<!-- Files mode menu: show all options including chat -->
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
				onclick={() => startFilenameDialog('file')}
				use:tooltip={$t('files.newFile')}
			>
				<Icon name="page-text" size={20} />
				<span class="flex-1 text-left truncate">{$t('files.newFile')}</span>
			</button>

			<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
				onclick={() => startFilenameDialog('folder')}
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
			<!-- Chat mode or fab mode: show all options -->
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
				onclick={() => startFilenameDialog('file')}
				use:tooltip={$t('files.newFile')}
			>
				<Icon name="page-text" size={20} />
				<span class="flex-1 text-left truncate">{$t('files.newFile')}</span>
			</button>

			<button class="flex items-center gap-3 w-full h-12 px-3 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-white/5 rounded-xl transition-colors"
				onclick={() => startFilenameDialog('folder')}
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

<!-- Filename Dialog -->
{#if showFilenameDialog}
	<div class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50" onclick={cancelFilenameDialog}>
		<div class="app-theme app-surface rounded-2xl border shadow-xl p-6 w-80">
			<h3 class="text-base font-semibold mb-3">
				{filenameType === 'file' ? $t('files.newFile') : $t('files.newFolder')}
			</h3>
			<input
				bind:this={filenameInput}
				type="text"
				class="w-full px-3 py-2 rounded-lg border text-sm bg-transparent"
				placeholder={filenameType === 'file' ? 'new_file.txt' : 'new_folder'}
				onkeydown={(e) => {
					if (e.key === 'Enter') confirmFilename();
					if (e.key === 'Escape') cancelFilenameDialog();
				}}
			/>
			<div class="flex gap-2 mt-4 justify-end">
				<button class="px-4 py-2 rounded-lg text-sm bg-gray-200 dark:bg-gray-700" onclick={cancelFilenameDialog}>
					{$t('common.cancel')}
				</button>
				<button class="px-4 py-2 rounded-lg text-sm bg-sky-500 text-white" onclick={confirmFilename}>
					{$t('common.create')}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Action Dialog (long press in chat) -->
{#if showActionDialog}
	<div class="fixed inset-0 z-[60] flex items-center justify-center bg-black/50" onclick={() => showActionDialog = false}>
		<div class="app-theme app-surface rounded-2xl border shadow-xl p-6 w-80">
			<h3 class="text-base font-semibold mb-3">{$t('chat.queueAction')}</h3>
			<div class="flex flex-col gap-2">
				<button class="w-full px-4 py-3 rounded-lg text-sm text-left bg-orange-500 text-white hover:bg-orange-600" onclick={() => handleActionSelect('queue')}>
					<Icon name="arrow-up-circle" size={18} />
					<span class="ml-2">{$t('chat.queueMessage')}</span>
				</button>
				<button class="w-full px-4 py-3 rounded-lg text-sm text-left bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600" onclick={() => handleActionSelect('steer')}>
					<Icon name="stop" size={18} />
					<span class="ml-2">{$t('chat.stopGeneration')}</span>
				</button>
			</div>
		</div>
	</div>
{/if}

	<button
	bind:this={btnEl}
	class={getButtonClass()}
	class:md:hidden={mode === 'fab'}
	onclick={handleClick}
	onpointerdown={handlePointerDown}
	onpointerup={handlePointerUp}
	onpointercancel={handlePointerCancel}
	aria-label={mode === 'files' ? $t('files.newFile') : $t('bar.newChat')}
	use:tooltip={mode === 'files' ? $t('files.newFile') : $t('bar.newChat')}
	>
	<Icon name={getIcon()} size={mode === 'chat' && getIcon() === 'arrow-right' ? 20 : (mode === 'chat' ? 24 : 36)} />
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

	/* Gradient background for all modes */
	:global(.bg-gradient-to-br) {
		background-image: linear-gradient(135deg, #2563eb, #312e81);
	}
	:global(.hover\\:from-blue-700\\:hover\\:to-indigo-900:hover) {
		background-image: linear-gradient(135deg, #1d4ed8, #1e1b4e);
	}

	/* Subtle pulse animation for FAB */
	@keyframes fab-pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.85; }
	}
	.fab-button {
		animation: fab-pulse 3s ease-in-out infinite;
	}
	.files-fab-button {
		animation: fab-pulse 3s ease-in-out infinite;
	}
</style>

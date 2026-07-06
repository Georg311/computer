<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import {
		workspaceList,
		currentWorkspace,
		removeWorkspace,
		reorderWorkspaces,
		sidebarOpen,
		sidebarWidth,
		appVersion,
		showChangelog,
		showSearch
	} from '$lib/stores';
	import Sortable from 'sortablejs';
	import Icon from './Icon.svelte';
	import KeyPill from './KeyPill.svelte';
	import DirectoryPicker from './DirectoryPicker.svelte';
	import DropdownMenu from './DropdownMenu.svelte';
	import SettingsModal from './SettingsModal.svelte';
	import SystemInfoModal from './SystemInfoModal.svelte';

	import { tooltip } from '$lib/tooltip';
	import { session, clearSession } from '$lib/session';
	import { getWelcome } from '$lib/apis/state';
	import { getChats, type ChatInfo } from '$lib/apis/chat';
	import ChatItem from './common/ChatItem.svelte';
	import { chatEnabled } from '$lib/stores/chat';
	import { socketStore } from '$lib/stores/socket.svelte';
	import { t } from '$lib/i18n';
	import { keybindings, formatChord } from '$lib/stores/keybindings';

	import { onMount, onDestroy } from 'svelte';

	let showPicker = $state(false);
	let showMenu = $state(false);
	let showSettings = $state(false);
	let showSystemInfo = $state(false);
	let settingsTab = $state<string>('general');
	let wsMenuPath = $state<string | null>(null);
	let wsMenuAnchor = $state<HTMLElement | null>(null);

	let menuButtonEl: HTMLButtonElement | undefined = $state();
	let wsListEl: HTMLDivElement | undefined = $state();
	let sortable: Sortable | null = null;
	let unbindSocketListener: (() => void) | null = null;

	// ── Per-workspace chat history ──────────────────────────────
	let expandedWorkspaces = $state<Set<string>>(new Set());
	let wsChatsCache = $state<Map<string, ChatInfo[]>>(new Map());
	let wsChatsLoading = $state<Set<string>>(new Set());

	// Keybinding shortcut display for search
	let searchShortcut = $derived(formatChord($keybindings.quickOpen));

	function toggleWorkspaceExpand(path: string) {
		const next = new Set(expandedWorkspaces);
		if (next.has(path)) {
			next.delete(path);
		} else {
			next.add(path);
			// Lazy-fetch chats if not cached
			if (!wsChatsCache.has(path)) {
				fetchWorkspaceChats(path);
			}
		}
		expandedWorkspaces = next;
	}

	async function fetchWorkspaceChats(path: string) {
		if (wsChatsLoading.has(path)) return;
		wsChatsLoading = new Set([...wsChatsLoading, path]);
		try {
			const data = await getChats(path, 5, 0, 'updated_at', 'desc');
			wsChatsCache = new Map([...wsChatsCache, [path, data.chats || []]]);
		} catch {
			wsChatsCache = new Map([...wsChatsCache, [path, []]]);
		} finally {
			const next = new Set(wsChatsLoading);
			next.delete(path);
			wsChatsLoading = next;
		}
	}

	function relativeTime(ts: number): string {
		// ts is in milliseconds
		const now = Date.now();
		const diffMs = now - ts;
		const diffSec = Math.floor(diffMs / 1000);
		if (diffSec < 60) return 'now';
		const diffMin = Math.floor(diffSec / 60);
		if (diffMin < 60) return `${diffMin}m`;
		const diffHr = Math.floor(diffMin / 60);
		if (diffHr < 24) return `${diffHr}h`;
		const diffDay = Math.floor(diffHr / 24);
		if (diffDay < 30) return `${diffDay}d`;
		const diffMonth = Math.floor(diffDay / 30);
		return `${diffMonth}mo`;
	}

	function handleSidebarChatClick(chatId: string, wsPath: string, title: string) {
		goto(`/?workspace=${encodeURIComponent(wsPath)}&chatId=${encodeURIComponent(chatId)}`);
		if (typeof window !== 'undefined' && window.innerWidth < 768) {
			sidebarOpen.set(false);
		}
	}

	function handleShowMoreChats(wsPath: string) {
		goto(`/?workspace=${encodeURIComponent(wsPath)}&chatId`);
		if (typeof window !== 'undefined' && window.innerWidth < 768) {
			sidebarOpen.set(false);
		}
	}

	function handleNewChat(wsPath: string) {
		goto(`/?workspace=${encodeURIComponent(wsPath)}&chatId`);
		if (typeof window !== 'undefined' && window.innerWidth < 768) {
			sidebarOpen.set(false);
		}
	}

	// Socket listener for chat events — invalidate cache when chats update
	const seenChatIds = new Set<string>();

	function handleChatEvent(data: {
		chat_id: string;
		done?: boolean;
		title?: string;
		delta?: string;
		workspace?: string;
	}) {
		// Re-fetch on done, title update, or first event of a new chat
		const isNew = !seenChatIds.has(data.chat_id);
		seenChatIds.add(data.chat_id);

		if (!data.done && !data.title && !isNew) return;

		// Invalidate cache for ALL workspaces so re-expanding shows fresh data
		wsChatsCache = new Map();

		// Re-fetch immediately for any currently expanded workspaces
		for (const path of expandedWorkspaces) {
			fetchWorkspaceChats(path);
		}
	}

	const MIN_WIDTH = 160;
	const MAX_WIDTH = 400;
	let isResizing = $state(false);

	function startResize(e: PointerEvent) {
		// Only allow resize on md+ screens
		if (typeof window !== 'undefined' && window.innerWidth < 768) return;
		e.preventDefault();
		isResizing = true;
		const startX = e.clientX;
		const startWidth = $sidebarWidth;

		function onMove(ev: PointerEvent) {
			const delta = ev.clientX - startX;
			const newWidth = Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + delta)));
			sidebarWidth.set(newWidth);
		}

		function onUp() {
			isResizing = false;
			window.removeEventListener('pointermove', onMove);
			window.removeEventListener('pointerup', onUp);
			document.body.style.cursor = '';
			document.body.style.userSelect = '';
		}

		window.addEventListener('pointermove', onMove);
		window.addEventListener('pointerup', onUp);
		document.body.style.cursor = 'col-resize';
		document.body.style.userSelect = 'none';
	}

	// Current workspace path from URL
	const currentPath = $derived($page.url.searchParams.get('workspace'));

	function isTouchDevice(): boolean {
		return (
			typeof window !== 'undefined' && ('ontouchstart' in window || navigator.maxTouchPoints > 0)
		);
	}

	function handleWorkspaceClick(e: MouseEvent, path: string) {
		// Let Cmd/Ctrl+click open in new tab naturally (it's an <a>)
		if (e.metaKey || e.ctrlKey) return;
		e.preventDefault();
		goto(`/?workspace=${encodeURIComponent(path)}`);
		if (typeof window !== 'undefined' && window.innerWidth < 768) {
			sidebarOpen.set(false);
		}
	}

	function openWsMenu(e: MouseEvent, path: string) {
		e.stopPropagation();
		e.preventDefault();
		wsMenuAnchor = e.currentTarget as HTMLElement;
		wsMenuPath = path;
	}

	function closeWsMenu() {
		wsMenuPath = null;
		wsMenuAnchor = null;
	}

	function closeSidebar() {
		sidebarOpen.set(false);
	}

	function openSettings() {
		showMenu = false;
		showSettings = true;
	}

	function openSystemInfo() {
		showMenu = false;
		showSystemInfo = true;
	}

	function logout() {
		clearSession();
	}

	async function handleRemoveWorkspace(path: string) {
		closeWsMenu();
		await removeWorkspace(path);
		// If we removed the workspace we're currently viewing, go home
		if (currentPath === path) {
			goto('/');
		}
	}

	onMount(() => {
		// Enable drag-reorder on non-touch devices
		if (wsListEl && !isTouchDevice()) {
			sortable = Sortable.create(wsListEl, {
				animation: 150,
				ghostClass: 'opacity-30',
				dragClass: 'cursor-grabbing',
				direction: 'vertical',
				onEnd: (evt) => {
					if (evt.oldIndex != null && evt.newIndex != null && evt.oldIndex !== evt.newIndex) {
						reorderWorkspaces(evt.oldIndex, evt.newIndex);
					}
				}
			});
		}

		// Bind socket listener for chat cache invalidation
		unbindSocketListener = socketStore.on('events:chat', handleChatEvent);
	});

	onDestroy(() => {
		sortable?.destroy();
		unbindSocketListener?.();
		unbindSocketListener = null;
	});
</script>

{#if $sidebarOpen}
	<button
		class="fixed inset-0 bg-black/50 z-40 cursor-default md:hidden"
		onclick={closeSidebar}
		aria-label={$t('sidebar.closeSidebar')}
	></button>

	<aside class="sidebar" style="--sw: {$sidebarWidth}px;">
		<!-- Resize handle (md+ only) -->
		<div
			class="resize-handle"
			class:active={isResizing}
			role="separator"
			aria-orientation="vertical"
			onpointerdown={startResize}
			ondblclick={() => sidebarWidth.set(220)}
		></div>
		<!-- Logo header with collapse button -->
		<div
			class="flex items-center justify-between h-9 pl-3.5 pr-1.5 shrink-0 border-b border-gray-200 dark:border-white/6"
			style="border-color: var(--app-border);"
		>
			<a
				href="/"
				class="flex items-center gap-1.5 text-xs font-semibold tracking-tight text-gray-900 dark:text-white"
				onclick={(e) => {
					e.preventDefault();
					goto('/');
					if (typeof window !== 'undefined' && window.innerWidth < 768) sidebarOpen.set(false);
				}}><img src="/favicon.png" alt="Computer logo" class="w-4 h-4" />Computer</a
			>
			<button
				class="flex items-center justify-center w-7 h-7 rounded-lg text-gray-300 hover:text-gray-500 dark:text-gray-600 dark:hover:text-gray-400 transition-colors duration-100"
				onclick={() => sidebarOpen.set(false)}
				aria-label={$t('sidebar.collapse')}
				use:tooltip={$t('sidebar.collapse')}
			>
				<Icon name="sidebar-expand" size={14} />
			</button>
		</div>

		<!-- Search -->
		<div class="px-1.5 mt-1 shrink-0">
			<button
				class="group flex items-center gap-1.5 w-full h-7 px-2 rounded-lg text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-100"
				onclick={() => showSearch.set(true)}
			>
				<Icon name="search" size={14} />
				<span class="flex-1 text-left overflow-hidden text-ellipsis whitespace-nowrap"
					>{$t('search.search')}</span
				>
				<KeyPill
					text={searchShortcut}
					class="ml-auto shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-100"
				/>
			</button>
		</div>

		<!-- Automations (only when chat/LLM backend is available) -->
		{#if $chatEnabled}
			<div class="px-1.5 shrink-0">
				<a
					href="/automations"
					class="flex items-center gap-1.5 w-full h-7 px-2 rounded-lg text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-100 no-underline"
					onclick={(e) => {
						e.preventDefault();
						goto('/automations');
						if (typeof window !== 'undefined' && window.innerWidth < 768) sidebarOpen.set(false);
					}}
				>
					<Icon name="clock" size={14} />
					<span class="flex-1 text-left overflow-hidden text-ellipsis whitespace-nowrap"
						>{$t('automations.title')}</span
					>
				</a>
			</div>
		{/if}

		<!-- Workspace section header -->
		<div class="flex items-center justify-between h-8 pl-3.5 pr-1.5 shrink-0">
			<span class="text-xs text-gray-400 dark:text-gray-500">{$t('sidebar.workspaces')}</span>
			<button
				class="flex items-center justify-center w-7 h-7 rounded-lg text-gray-300 hover:text-gray-500 dark:text-gray-600 dark:hover:text-gray-400 transition-colors duration-100"
				onclick={() => (showPicker = true)}
				aria-label={$t('sidebar.addWorkspace')}
				use:tooltip={$t('sidebar.addWorkspace')}
			>
				<Icon name="plus" size={14} />
			</button>
		</div>

		<!-- Workspace list -->
		<div bind:this={wsListEl} class="flex-1 overflow-y-auto px-1.5">
			{#each $workspaceList as ws (ws.path)}
				{@const isExpanded = expandedWorkspaces.has(ws.path)}
				{@const chats = wsChatsCache.get(ws.path)}
				{@const isLoading = wsChatsLoading.has(ws.path)}
				<div class="ws-item">
					<div
						class="group flex items-center gap-1 w-full h-7 px-2 rounded-lg text-xs font-medium transition-colors duration-100
						{ws.path === currentPath
							? 'bg-gray-200/50 text-gray-900 dark:bg-white/8 dark:text-white'
							: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
					>
						<a
							href="/?workspace={encodeURIComponent(ws.path)}"
							class="flex items-center gap-1.5 flex-1 min-w-0 no-underline text-inherit"
							onclick={(e) => handleWorkspaceClick(e, ws.path)}
						>
							<!-- Icon: folder by default, chevron on hover (when chat enabled) -->
							{#if $chatEnabled}
								<span
									class="ws-icon-toggle shrink-0"
									role="button"
									tabindex="-1"
									onclick={(e) => {
										e.stopPropagation();
										e.preventDefault();
										toggleWorkspaceExpand(ws.path);
									}}
									aria-label={isExpanded ? $t('sidebar.collapse') : $t('sidebar.addWorkspace')}
								>
									<span class="ws-icon-folder"><Icon name="folder" size={14} /></span>
									<span
										class="ws-icon-chevron"
										style="transform: rotate({isExpanded ? '90deg' : '0deg'})"
									>
										<Icon name="chevron-right" size={11} />
									</span>
								</span>
							{:else}
								<Icon name="folder" size={14} />
							{/if}
							<span class="flex-1 text-left overflow-hidden text-ellipsis whitespace-nowrap"
								>{ws.name}</span
							>
						</a>
						<span
							class="flex items-center justify-center w-4 h-4 shrink-0 text-gray-400 opacity-0 group-hover:opacity-100 hover:text-gray-600 dark:hover:text-gray-300 transition-all duration-75"
							role="button"
							tabindex="-1"
							onclick={(e) => openWsMenu(e, ws.path)}
							aria-label={$t('sidebar.workspaceOptions')}
						>
							<Icon name="three-dots" size={11} />
						</span>
						{#if $chatEnabled}
							<span
								class="flex items-center justify-center w-4 h-4 shrink-0 text-gray-400 opacity-0 group-hover:opacity-100 hover:text-gray-600 dark:hover:text-gray-300 transition-all duration-75"
								role="button"
								tabindex="-1"
								onclick={() => handleNewChat(ws.path)}
								aria-label={$t('bar.newChat')}
								use:tooltip={$t('bar.newChat')}
							>
								<Icon name="pencil" size={11} />
							</span>
						{/if}
					</div>

					<!-- Collapsible chat list -->
					{#if $chatEnabled && isExpanded}
						<div class="ws-chats">
							{#if isLoading && !chats}
								<div class="ws-chat-loading">
									<span class="ws-chat-loading-dot"></span>
									<span class="ws-chat-loading-dot"></span>
									<span class="ws-chat-loading-dot"></span>
								</div>
							{:else if chats && chats.length > 0}
								{#each chats as chat (chat.id)}
									<ChatItem
										{chat}
										onclick={() => handleSidebarChatClick(chat.id, ws.path, chat.title)}
									/>
								{/each}
								<button class="ws-chat-show-more" onclick={() => handleShowMoreChats(ws.path)}>
									{$t('sidebar.showMore')}
								</button>
							{:else if chats}
								<!-- No chats yet, show nothing -->
							{/if}
						</div>
					{/if}
				</div>
			{/each}

			{#if $workspaceList.length === 0}
				<div class="flex flex-col items-center justify-center py-12">
					<p class="text-xs text-gray-400 dark:text-gray-600">{$t('sidebar.noWorkspaces')}</p>
				</div>
			{/if}
		</div>

		<!-- Settings and profile footer pinned to the bottom -->
		<div class="relative px-1 pb-0.5 shrink-0">
			<button
				bind:this={menuButtonEl}
				class="flex items-center gap-2 w-full h-8 px-2 rounded-lg text-xs font-medium text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-100"
				onclick={() => (showMenu = !showMenu)}
			>
				<img
					src={$session?.profile_image_url || '/user.png'}
					alt="Avatar"
					class="w-5 h-5 rounded-full object-cover shrink-0"
				/>
				<span class="truncate"
					>{$session?.display_name || $session?.username || $t('sidebar.settings')}</span
				>
				{#if $appVersion}
					<button
						onclick={(e) => {
							e.stopPropagation();
							showChangelog.set(true);
						}}
						class="ml-auto text-[0.625rem] text-gray-400 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 font-mono hover:underline cursor-pointer"
					>
						v{$appVersion}
					</button>
				{/if}
			</button>
		</div>
	</aside>
{/if}

{#if showMenu && menuButtonEl}
	<DropdownMenu
		anchor={menuButtonEl}
		matchWidth
		items={[
			...($session
				? [
						{
							label: $session.display_name || $session.username,
							image: $session.profile_image_url || '/user.png',
							onclick: () => {
								settingsTab = 'account';
								showMenu = false;
								showSettings = true;
							}
						}
					]
				: []),
			...($session ? [{ divider: true, label: '', onclick: () => {} }] : []),
			{
				label: $t('sidebar.settings'),
				icon: 'settings',
				shortcut: formatChord($keybindings.openSettings),
				onclick: openSettings
			},
			{
				label: $t('system.infoTitle'),
				icon: 'info',
				onclick: openSystemInfo
			},
			{ divider: true, label: '', onclick: () => {} },
			{ label: $t('sidebar.logOut'), icon: 'log-out', onclick: logout }
		]}
		onclose={() => (showMenu = false)}
	/>
{/if}

{#if showPicker}
	<DirectoryPicker onclose={() => (showPicker = false)} />
{/if}

{#if wsMenuPath && wsMenuAnchor}
	<DropdownMenu
		anchor={wsMenuAnchor}
		items={[
			{
				label: $t('sidebar.remove'),
				icon: 'xmark',
				onclick: () => handleRemoveWorkspace(wsMenuPath!)
			}
		]}
		onclose={closeWsMenu}
	/>
{/if}

{#if showSettings}
	<SettingsModal
		initialTab={settingsTab}
		onclose={() => {
			showSettings = false;
			settingsTab = 'general';
		}}
	/>
{/if}

{#if showSystemInfo}
	<SystemInfoModal onclose={() => (showSystemInfo = false)} />
{/if}

<style>
	@reference "../../app.css";

	.sidebar {
		position: fixed;
		left: 0;
		top: 0;
		bottom: 0;
		width: 13.75rem;
		z-index: 50;
		display: flex;
		flex-direction: column;
		background: var(--app-bg);
		color: var(--app-fg);
		border-right: 1px solid var(--app-border);
		padding-top: env(safe-area-inset-top, 0);
	}

	:global(.dark) .sidebar {
		border-right-color: var(--app-border);
	}

	@media (min-width: 768px) {
		.sidebar {
			position: relative;
			z-index: auto;
			width: var(--sw, 13.75rem);
		}
	}

	.resize-handle {
		display: none;
	}

	@media (min-width: 768px) {
		.resize-handle {
			display: block;
			position: absolute;
			right: -0.1875rem;
			top: 0;
			bottom: 0;
			width: 0.375rem;
			cursor: col-resize;
			z-index: 10;
			transition: background 0.15s;
		}

		.resize-handle:hover,
		.resize-handle.active {
			background: rgba(150, 150, 150, 0.12);
		}
	}

	/* ── Workspace chat items ────────────────────────────── */

	.ws-item {
		margin-bottom: 0.125rem;
	}

	.ws-expand-btn {
		display: none;
	}

	/* Icon toggle: folder by default, chevron on hover */
	.ws-icon-toggle {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 0.875rem;
		height: 0.875rem;
		cursor: pointer;
	}

	.ws-icon-folder {
		display: flex;
		transition: opacity 0.1s;
	}

	.ws-icon-chevron {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0;
		transition:
			opacity 0.1s,
			transform 0.1s;
		color: #9ca3af;
	}

	:global(.dark) .ws-icon-chevron {
		color: #6b7280;
	}

	/* On icon hover only, swap folder → chevron */
	.ws-icon-toggle:hover .ws-icon-folder {
		opacity: 0;
	}

	.ws-icon-toggle:hover .ws-icon-chevron {
		opacity: 1;
	}

	.ws-chats {
		margin-top: 0.125rem;
		padding-bottom: 0.25rem;
	}

	.ws-chat-show-more {
		display: block;
		width: 100%;
		padding: 0.125rem 0.5rem;
		border: none;
		background: none;
		cursor: pointer;
		font-size: 0.6875rem;
		color: #b0b5be;
		text-align: left;
		transition: color 0.1s;
	}

	.ws-chat-show-more:hover {
		color: #6b7280;
	}

	:global(.dark) .ws-chat-show-more {
		color: #6b7280;
	}

	:global(.dark) .ws-chat-show-more:hover {
		color: #9ca3af;
	}

	.ws-chat-loading {
		display: flex;
		gap: 0.25rem;
		padding: 0.375rem 0.5rem;
	}

	.ws-chat-loading-dot {
		width: 0.25rem;
		height: 0.25rem;
		border-radius: 50%;
		background: #9ca3af;
		animation: dotPulse 1s ease-in-out infinite;
	}

	:global(.dark) .ws-chat-loading-dot {
		background: #6b7280;
	}

	.ws-chat-loading-dot:nth-child(2) {
		animation-delay: 0.15s;
	}

	.ws-chat-loading-dot:nth-child(3) {
		animation-delay: 0.3s;
	}

	@keyframes dotPulse {
		0%,
		100% {
			opacity: 0.3;
		}
		50% {
			opacity: 1;
		}
	}
</style>

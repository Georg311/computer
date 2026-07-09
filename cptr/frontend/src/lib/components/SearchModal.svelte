<script lang="ts">
	import { workspaceList, currentWorkspace, showSearch } from '$lib/stores';
	import { getPathDisplayName } from '$lib/utils/paths';
	import {
		unifiedSearch,
		getRecentChats,
		type ChatSearchResult,
		type FileSearchResult
	} from '$lib/apis/search';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Modal from './Modal.svelte';
	import Icon from './Icon.svelte';
	import KeyPill from './KeyPill.svelte';
	import Spinner from './common/Spinner.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	let query = $state('');
	let chatResults = $state<ChatSearchResult[]>([]);
	let fileResults = $state<FileSearchResult[]>([]);
	let recentChats = $state<ChatSearchResult[]>([]);
	let loading = $state(false);
	let selectedIndex = $state(0);
	let inputEl: HTMLInputElement | undefined = $state();
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	let resultsEl: HTMLDivElement | undefined = $state();

	// Determine active workspace from the URL, not the store.
	// When on /scheduled or other non-workspace pages, $currentWorkspace
	// retains the last workspace but we should search across all.
	const urlWorkspacePath = $derived($page.url.searchParams.get('workspace'));
	const effectiveWorkspace = $derived(urlWorkspacePath ? $currentWorkspace : null);

	// Show recents when no query, search results when query exists
	const showingRecents = $derived(!query.trim());
	const filteredRecents = $derived(
		effectiveWorkspace
			? recentChats.filter((c) => c.workspace === effectiveWorkspace!.path)
			: recentChats
	);
	const displayedChats = $derived(showingRecents ? filteredRecents : chatResults);
	const totalResults = $derived(displayedChats.length + fileResults.length);

	$effect(() => {
		requestAnimationFrame(() => inputEl?.focus());
	});

	// Load recent chats on mount
	$effect(() => {
		loadRecents();
	});

	async function loadRecents() {
		try {
			const data = await getRecentChats(9);
			recentChats = data.chats;
		} catch {
			// ignore
		}
	}

	$effect(() => {
		if (debounceTimer) clearTimeout(debounceTimer);
		if (!query.trim()) {
			chatResults = [];
			fileResults = [];
			loading = false;
			selectedIndex = 0;
			return;
		}
		loading = true;
		debounceTimer = setTimeout(() => doSearch(query), 250);
	});

	// When a workspace is explicitly active via URL, scope to files from that workspace only
	const isWorkspaceScoped = $derived(!!effectiveWorkspace);

	async function doSearch(q: string) {
		const activeWs = effectiveWorkspace;

		if (activeWs) {
			// Workspace active: search chats + files scoped to this workspace
			try {
				const data = await unifiedSearch(q, [activeWs.path], activeWs.path);
				chatResults = data.chats;
				fileResults = data.files;
				selectedIndex = 0;
			} catch {
				// ignore
			} finally {
				loading = false;
			}
		} else {
			// No workspace: full search across all workspaces
			const wsPaths = $workspaceList.map((w) => w.path);
			if (wsPaths.length === 0) {
				chatResults = [];
				fileResults = [];
				loading = false;
				return;
			}
			try {
				const data = await unifiedSearch(q, wsPaths);
				chatResults = data.chats;
				fileResults = data.files;
				selectedIndex = 0;
			} catch {
				// ignore
			} finally {
				loading = false;
			}
		}
	}

	function getWorkspaceDisplayName(workspacePath: string): string {
		const workspace = $workspaceList.find((item) => item.path === workspacePath);
		if (workspace) return workspace.name;
		return getPathDisplayName(workspacePath, workspacePath);
	}

	function selectChat(chat: ChatSearchResult) {
		onclose();
		goto(`/?workspace=${encodeURIComponent(chat.workspace)}&chatId=${encodeURIComponent(chat.id)}`);
	}

	function selectFile(file: FileSearchResult) {
		onclose();
		if (file.type === 'file') {
			goto(
				`/?workspace=${encodeURIComponent(file.workspace)}&file=${encodeURIComponent(file.path)}`
			);
		} else if (file.type === 'directory') {
			goto(
				`/?workspace=${encodeURIComponent(file.workspace)}&dir=${encodeURIComponent(file.path)}`
			);
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		// Cmd+1-9: jump to recent chat
		if ((e.metaKey || e.ctrlKey) && e.key >= '1' && e.key <= '9' && showingRecents) {
			const idx = parseInt(e.key) - 1;
			if (idx < recentChats.length) {
				e.preventDefault();
				selectChat(recentChats[idx]);
				return;
			}
		}
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			selectedIndex = Math.min(selectedIndex + 1, totalResults - 1);
			scrollSelectedIntoView();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			selectedIndex = Math.max(selectedIndex - 1, 0);
			scrollSelectedIntoView();
		} else if (e.key === 'Enter' && totalResults > 0) {
			e.preventDefault();
			activateSelected();
		}
	}

	function scrollSelectedIntoView() {
		requestAnimationFrame(() => {
			const el = resultsEl?.querySelector(`[data-idx="${selectedIndex}"]`);
			el?.scrollIntoView({ block: 'nearest', behavior: 'instant' });
		});
	}

	function activateSelected() {
		if (selectedIndex < displayedChats.length) {
			selectChat(displayedChats[selectedIndex]);
		} else {
			const fileIdx = selectedIndex - displayedChats.length;
			if (fileIdx < fileResults.length) {
				selectFile(fileResults[fileIdx]);
			}
		}
	}

	function relPath(fullPath: string, wsPath: string): string {
		return fullPath.startsWith(wsPath) ? fullPath.slice(wsPath.length + 1) : fullPath;
	}

	function relativeTime(ts: number): string {
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
</script>

<svelte:window onkeydown={handleKeydown} />

<Modal
	{onclose}
	class="w-full max-w-[35rem] mx-4 max-md:mx-0 max-md:rounded-none max-h-[30rem] max-md:max-h-dvh flex flex-col mb-[6vh] max-md:mb-0"
>
	<!-- Search input -->
	<div class="flex items-center px-3.5 py-3 gap-2">
		<Icon name="search" size={14} class="text-gray-400 shrink-0" />
		<input
			bind:this={inputEl}
			type="text"
			class="flex-1 border-none outline-none bg-transparent text-xs text-gray-900 dark:text-white font-sans placeholder:text-gray-400"
			placeholder={$t('search.placeholder')}
			bind:value={query}
		/>
	</div>

	<!-- Results -->
	<div bind:this={resultsEl} class="overflow-y-auto px-1.5 pb-1.5 flex-1 min-h-0">
		{#if showingRecents && filteredRecents.length > 0}
			<!-- Recent chats (empty query) -->
			<div
				class="text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600 px-2 pt-1 pb-0.5"
			>
				{$t('search.recentChats')}
			</div>
			{#each filteredRecents as chat, i (chat.id)}
				<button
					data-idx={i}
					class="group flex items-center gap-2 w-full h-7 px-2 rounded-xl text-left transition-colors duration-75
						{i === selectedIndex
						? 'bg-gray-200/50 text-gray-900 dark:bg-white/6 dark:text-white'
						: 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-white/4'}"
					onclick={() => selectChat(chat)}
					onmouseenter={() => (selectedIndex = i)}
				>
					<span class="text-xs font-medium truncate flex-1">{chat.title}</span>
					{#if i < 9 && !isWorkspaceScoped}
						<KeyPill
							text={`⌘${i + 1}`}
							class="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-100"
						/>
					{/if}
					<span class="text-[0.625rem] text-gray-400 dark:text-gray-600 shrink-0"
						>{getWorkspaceDisplayName(chat.workspace)}</span
					>
				</button>
			{/each}
		{:else if showingRecents}
			<div class="py-6 text-center text-xs text-gray-400 dark:text-gray-600">
				{$t('search.noRecentChats')}
			</div>
		{:else if !showingRecents}
			{#if displayedChats.length > 0}
				<!-- Chat search results -->
				<div
					class="text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600 px-2 pt-1 pb-0.5"
				>
					{$t('search.chats')}
				</div>
				{#each displayedChats as chat, i (chat.id)}
					{@const idx = i}
					<button
						data-idx={idx}
						class="flex items-start gap-2 w-full px-2 py-1.5 rounded-xl text-left transition-colors duration-75
							{idx === selectedIndex
							? 'bg-gray-200/50 text-gray-900 dark:bg-white/6 dark:text-white'
							: 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-white/4'}"
						onclick={() => selectChat(chat)}
						onmouseenter={() => (selectedIndex = idx)}
					>
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<span class="text-xs font-medium truncate">{chat.title}</span>
								<span class="text-[0.625rem] text-gray-400 dark:text-gray-600 shrink-0"
									>{relativeTime(chat.updated_at)}</span
								>
							</div>
							{#if chat.snippet}
								<div class="text-[0.6875rem] text-gray-400 dark:text-gray-600 truncate mt-0.5">
									{chat.snippet}
								</div>
							{/if}
						</div>
						<span class="text-[0.625rem] text-gray-400 dark:text-gray-600 shrink-0"
							>{getWorkspaceDisplayName(chat.workspace)}</span
						>
					</button>
				{/each}
			{/if}

			{#if fileResults.length > 0}
				<!-- File search results -->
				<div
					class="text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600 px-2 pt-1 pb-0.5 {displayedChats.length >
					0
						? 'mt-1'
						: ''}"
				>
					{$t('search.files')}
				</div>
				{#each fileResults as file, i (file.path)}
					{@const idx = displayedChats.length + i}
					<button
						data-idx={idx}
						class="flex items-center gap-2 w-full h-7 px-2 rounded-xl text-left transition-colors duration-75
							{idx === selectedIndex
							? 'bg-gray-200/50 text-gray-900 dark:bg-white/6 dark:text-white'
							: 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-white/4'}"
						onclick={() => selectFile(file)}
						onmouseenter={() => (selectedIndex = idx)}
					>
						<Icon
							name={file.type === 'directory' ? 'folder' : 'empty-page'}
							size={14}
							class="shrink-0 text-gray-400"
						/>
						<span class="text-xs font-medium shrink-0">{file.name}</span>
						<span
							class="text-[0.6875rem] text-gray-400 overflow-hidden text-ellipsis whitespace-nowrap"
							>{relPath(file.path, file.workspace)}</span
						>
						<span class="text-[0.625rem] text-gray-400 dark:text-gray-600 shrink-0 ml-auto"
							>{getWorkspaceDisplayName(file.workspace)}</span
						>
					</button>
				{/each}
			{/if}

			{#if loading}
				<div class="flex items-center justify-center py-8">
					<Spinner size={16} />
				</div>
			{:else if query && totalResults === 0}
				<div class="p-6 text-center text-xs text-gray-400">{$t('search.noResults')}</div>
			{/if}
		{/if}
	</div>
</Modal>

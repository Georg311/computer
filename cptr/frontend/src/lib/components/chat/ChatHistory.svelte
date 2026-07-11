<script lang="ts">
	import type { ChatInfo } from '$lib/apis/chat';
	import { t } from '$lib/i18n';
	import ChatItem from '../common/ChatItem.svelte';
	import DropdownMenu from '../DropdownMenu.svelte';
	import Pagination from '../common/Pagination.svelte';

	interface Props {
		chats: ChatInfo[];
		onopen: (id: string) => void;
		ondelete: (id: string) => void;
		onrename: (id: string) => void;
		oncopy?: (id: string) => void;
		page?: number;
		totalPages?: number;
		perPage?: number;
		onpagechange?: (page: number) => void;
		sortBy?: 'title' | 'updated_at';
		sortDir?: 'asc' | 'desc';
		onsort?: (field: 'title' | 'updated_at') => void;
	}
	let {
		chats,
		onopen,
		ondelete,
		onrename,
		oncopy,
		page = 1,
		totalPages = 1,
		perPage = 10,
		onpagechange,
		sortBy = 'updated_at',
		sortDir = 'desc',
		onsort
	}: Props = $props();

	let menuChatId = $state<string | null>(null);
	let menuAnchor = $state<HTMLElement | null>(null);

	function openMenu(e: MouseEvent, chatId: string) {
		e.stopPropagation();
		menuChatId = chatId;
		menuAnchor = e.currentTarget as HTMLElement;
	}

	function closeMenu() {
		menuChatId = null;
		menuAnchor = null;
	}

	function formatTime(ts: number): string {
		const d = new Date(ts);
		const now = new Date();
		const diffMs = now.getTime() - d.getTime();
		const diffM = Math.floor(diffMs / 60000);
		if (diffM < 1) return $t('chat.history.justNow');
		if (diffM < 60) return $t('chat.history.minutesAgo', { count: diffM });
		const diffH = Math.floor(diffM / 60);
		if (diffH < 24) return $t('chat.history.hoursAgo', { count: diffH });
		const diffD = Math.floor(diffH / 24);
		if (diffD < 7) return $t('chat.history.daysAgo', { count: diffD });
		return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}

	// Not used directly anymore (ChatItem has its own formatTime),
	// but kept for the sort header display
</script>

{#snippet chevronUp()}
	<svg
		class="w-2 h-2"
		viewBox="0 0 10 6"
		fill="none"
		stroke="currentColor"
		stroke-width="2"
		stroke-linecap="round"
		stroke-linejoin="round"
	>
		<path d="M1 5L5 1L9 5" />
	</svg>
{/snippet}

{#snippet chevronDown()}
	<svg
		class="w-2 h-2"
		viewBox="0 0 10 6"
		fill="none"
		stroke="currentColor"
		stroke-width="2"
		stroke-linecap="round"
		stroke-linejoin="round"
	>
		<path d="M1 1L5 5L9 1" />
	</svg>
{/snippet}

{#if chats.length > 0}
	<div class="w-full mt-4 pt-2">
		<!-- Sort header -->
		{#if onsort}
			<div
				class="flex items-center text-[0.625rem] font-medium text-gray-400 dark:text-gray-600 mb-1 px-2 select-none"
			>
				<button
					class="flex-1 flex items-center gap-1 hover:text-gray-600 dark:hover:text-gray-400 transition-colors"
					onclick={() => onsort?.('title')}
				>
					{$t('chat.history.title')}
					{#if sortBy === 'title'}
						{#if sortDir === 'asc'}
							{@render chevronUp()}
						{:else}
							{@render chevronDown()}
						{/if}
					{:else}
						<span class="invisible">{@render chevronUp()}</span>
					{/if}
				</button>
				<button
					class="shrink-0 flex items-center gap-1 hover:text-gray-600 dark:hover:text-gray-400 transition-colors"
					onclick={() => onsort?.('updated_at')}
				>
					{$t('chat.history.updated')}
					{#if sortBy === 'updated_at'}
						{#if sortDir === 'asc'}
							{@render chevronUp()}
						{:else}
							{@render chevronDown()}
						{/if}
					{:else}
						<span class="invisible">{@render chevronUp()}</span>
					{/if}
				</button>
			</div>
		{/if}

		{#each chats as chat (chat.id)}
			<ChatItem {chat} onclick={() => onopen(chat.id)} onmenu={(e) => openMenu(e, chat.id)} />
		{/each}
		{#if onpagechange}
			<Pagination {page} {totalPages} {onpagechange} />
		{/if}
	</div>
{/if}

{#if menuChatId && menuAnchor}
	<DropdownMenu
		anchor={menuAnchor}
		align="end"
		items={[
			...(oncopy
				? [
						{
							label: $t('files.copyPath'),
							icon: 'copy',
							onclick: () => {
								if (menuChatId) oncopy(menuChatId);
							}
						}
					]
				: []),
			{
				label: $t('files.rename'),
				icon: 'pencil',
				onclick: () => {
					if (menuChatId) onrename(menuChatId);
				}
			},
			{
				label: $t('chat.history.delete'),
				icon: 'trash',
				onclick: () => {
					if (menuChatId) ondelete(menuChatId);
				}
			}
		]}
		onclose={closeMenu}
	/>
{/if}

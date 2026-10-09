<script lang="ts">
	import { chatEnabled } from '$lib/stores/chat';
	import { openChatTab } from '$lib/stores';
	import { activeGroup, homeState } from '$lib/stores';
	import Icon from './Icon.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		/** Optional: if provided, the FAB will attempt to open a chat in this specific group. */
		groupId?: string;
	}

	let { groupId }: Props = $props();

	function handleNewChat() {
		// Determine which group to use for the new chat tab.
		// If a groupId is provided, use it. Otherwise, fallback to the active group or home group.
		const targetGroupId = groupId || 
			($activeGroup ? $activeGroup.id : ($homeState ? $homeState.groups[0].id : undefined));

		if (targetGroupId) {
			openChatTab(undefined, targetGroupId);
		} else {
			// Fallback to just opening a chat tab in the default way if no group context is available.
			// This might require a bit more logic depending on how openChatTab handles undefined groups.
			openChatTab(undefined);
		}
	}
</script>

{#if $chatEnabled}
	<button
		class="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-sky-500 text-white shadow-lg transition-transform active:scale-95 md:hidden"
		onclick={handleNewChat}
		aria-label={$t('bar.newChat')}
		use:tooltip={$t('bar.newChat')}
	>
		<Icon name="chat-bubble" size={28} />
	</button>
{/if}

<style>
	/* Any additional mobile specific styling if needed */
</style>

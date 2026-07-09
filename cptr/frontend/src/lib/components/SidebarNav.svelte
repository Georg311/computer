<script lang="ts">
	import { goto } from '$app/navigation';
	import { sidebarOpen, showSearch } from '$lib/stores';
	import { chatEnabled } from '$lib/stores/chat';
	import { keybindings, formatChord } from '$lib/stores/keybindings';
	import { t } from '$lib/i18n';
	import Icon from './Icon.svelte';
	import KeyPill from './KeyPill.svelte';

	let searchShortcut = $derived(formatChord($keybindings.quickOpen));

	function openAutomations(e: MouseEvent) {
		e.preventDefault();
		goto('/scheduled');
		if (typeof window !== 'undefined' && window.innerWidth < 768) sidebarOpen.set(false);
	}
</script>

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

{#if $chatEnabled}
	<div class="px-1.5 shrink-0">
		<a
			href="/scheduled"
			class="flex items-center gap-1.5 w-full h-7 px-2 rounded-lg text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-100 no-underline"
			onclick={openAutomations}
		>
			<Icon name="clock" size={14} />
			<span class="flex-1 text-left overflow-hidden text-ellipsis whitespace-nowrap"
				>{$t('automations.title')}</span
			>
		</a>
	</div>
{/if}

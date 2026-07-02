<script lang="ts">
	import Modal from './Modal.svelte';
	import type { LaunchIntent, ShareBehavior } from '$lib/intents/types';
	import { t } from '$lib/i18n';

	interface Props {
		intent: LaunchIntent;
		workspaces: { path: string; name: string }[];
		onchoose: (path: string, behavior?: ShareBehavior) => void;
		oncancel: () => void;
	}

	let { intent, workspaces, onchoose, oncancel }: Props = $props();
	let behavior = $state<ShareBehavior>('noteFile');
	let selectedIndex = $state(0);

	const title = $derived($t('intent.chooseWorkspace'));

	const needsShareBehavior = $derived(
		intent.kind === 'share' && (!intent.shareBehavior || intent.shareBehavior === 'ask')
	);

	function chooseWorkspace(ws: { path: string; name: string }) {
		onchoose(ws.path, needsShareBehavior ? behavior : undefined);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!workspaces.length) return;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			selectedIndex = Math.min(selectedIndex + 1, workspaces.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			selectedIndex = Math.max(selectedIndex - 1, 0);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			chooseWorkspace(workspaces[selectedIndex]);
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<Modal
	onclose={oncancel}
	class="w-full max-w-[35rem] mx-4 max-md:mx-0 max-md:rounded-none max-h-[30rem] max-md:max-h-dvh flex flex-col mb-[6vh] max-md:mb-0"
>
	<div class="flex items-center px-3.5 py-3 gap-2">
		<div class="flex-1 min-w-0">
			<h2 class="text-sm text-gray-900 dark:text-white truncate">{title}</h2>
		</div>
	</div>

	{#if needsShareBehavior}
		<div class="flex items-center gap-3 px-3.5 pb-2">
			<label
				class="text-[0.6875rem] text-gray-400 dark:text-gray-600 shrink-0"
				for="share-behavior"
			>
				{$t('pwa.shareBehavior')}
			</label>
			<select
				id="share-behavior"
				bind:value={behavior}
				class="flex-1 min-w-0 bg-transparent text-xs text-gray-700 dark:text-gray-300 outline-none cursor-pointer"
			>
				<option value="chatDraft">{$t('pwa.shareChatDraft')}</option>
				<option value="noteFile">{$t('pwa.shareNoteFile')}</option>
			</select>
		</div>
	{/if}

	<div class="overflow-y-auto px-1.5 pb-1.5 flex-1 min-h-0">
		{#if workspaces.length}
			{#each workspaces as ws, i (ws.path)}
				<button
					class="flex items-center gap-2 w-full h-7 px-2 rounded-xl text-left transition-colors duration-75
						{i === selectedIndex
						? 'bg-gray-200/50 text-gray-900 dark:bg-white/6 dark:text-white'
						: 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-white/4'}"
					onclick={() => chooseWorkspace(ws)}
					onmouseenter={() => (selectedIndex = i)}
				>
					<span class="text-xs shrink-0 truncate max-w-[34%]">{ws.name}</span>
					<span
						class="text-[0.6875rem] text-gray-400 overflow-hidden text-ellipsis whitespace-nowrap font-mono"
					>
						{ws.path}
					</span>
				</button>
			{/each}
		{:else}
			<div class="flex flex-col items-center justify-center gap-3 py-10 text-center">
				<p class="text-xs text-gray-400 dark:text-gray-600">{$t('pwa.noWorkspaces')}</p>
			</div>
		{/if}
	</div>

	<div class="flex items-center justify-end gap-2 px-3.5 pb-3 pt-1 shrink-0">
		<button
			class="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-3 py-1.5 rounded-lg transition-colors duration-100 shrink-0"
			onclick={oncancel}
		>
			{$t('pwa.cancel')}
		</button>
	</div>
</Modal>

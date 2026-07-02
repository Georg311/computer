<script lang="ts">
	import { pwaPreferences } from '$lib/stores';
	import { i18next } from '$lib/i18n';
	import type { PwaPreferences } from '$lib/intents/types';

	const tr = (key: string, opts?: Record<string, unknown>) => i18next.t(key, opts) as string;

	function updatePref<K extends keyof PwaPreferences>(key: K, value: PwaPreferences[K]) {
		pwaPreferences.set({ ...$pwaPreferences, [key]: value });
	}

	function updateShareBehavior(e: Event) {
		updatePref(
			'shareBehavior',
			(e.currentTarget as HTMLSelectElement).value as PwaPreferences['shareBehavior']
		);
	}

	function updateImportDestination(e: Event) {
		updatePref(
			'importDestination',
			(e.currentTarget as HTMLSelectElement).value as PwaPreferences['importDestination']
		);
	}

	let resetting = $state(false);

	async function resetPwa() {
		resetting = true;

		try {
			if ('serviceWorker' in navigator) {
				const registrations = await navigator.serviceWorker.getRegistrations();
				await Promise.all(registrations.map((registration) => registration.unregister()));
			}

			if ('caches' in window) {
				const keys = await caches.keys();
				await Promise.all(
					keys.filter((key) => key.startsWith('cptr-')).map((key) => caches.delete(key))
				);
			}
		} finally {
			location.reload();
		}
	}
</script>

<div class="flex flex-col h-full">
	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5 -mr-1.5">
		<h2 class="text-sm text-gray-900 dark:text-white mb-4">{tr('pwa.settingsTitle')}</h2>

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2">{tr('pwa.shareBehavior')}</h3>
		<select
			class="w-full max-w-[12.5rem] bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-1 cursor-pointer"
			value={$pwaPreferences.shareBehavior}
			onchange={updateShareBehavior}
		>
			<option value="ask">{tr('pwa.shareAsk')}</option>
			<option value="chatDraft">{tr('pwa.shareChatDraft')}</option>
			<option value="noteFile">{tr('pwa.shareNoteFile')}</option>
		</select>

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{tr('pwa.fileImports')}</h3>
		<select
			class="w-full max-w-[12.5rem] bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-1 cursor-pointer"
			value={$pwaPreferences.importDestination}
			onchange={updateImportDestination}
		>
			<option value="workspaceRoot">{tr('pwa.workspaceRoot')}</option>
			<option value="askFolder">{tr('pwa.askFolder')}</option>
			<option value="configuredFolder">{tr('pwa.configuredFolder')}</option>
		</select>
		{#if $pwaPreferences.importDestination === 'configuredFolder'}
			<input
				class="mt-2 w-full h-8 bg-gray-100 dark:bg-white/6 rounded-lg px-2 text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none"
				placeholder={tr('pwa.importFolderPlaceholder')}
				value={$pwaPreferences.importFolder ?? ''}
				oninput={(e) =>
					updatePref('importFolder', (e.currentTarget as HTMLInputElement).value || undefined)}
			/>
		{/if}

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{tr('pwa.resetTitle')}</h3>
		<button
			class="text-[0.8125rem] text-gray-500 dark:text-gray-500 hover:text-gray-900 dark:hover:text-white transition-colors disabled:opacity-40 disabled:pointer-events-none"
			onclick={resetPwa}
			disabled={resetting}
		>
			{resetting ? tr('pwa.resetting') : tr('pwa.reset')}
		</button>
		<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mt-1">
			{tr('pwa.resetDesc')}
		</p>
	</div>
</div>

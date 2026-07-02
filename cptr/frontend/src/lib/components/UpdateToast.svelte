<script lang="ts">
	import { t } from '$lib/i18n';
	import { latestVersion } from '$lib/stores';
	import Icon from './Icon.svelte';
	import { fade } from 'svelte/transition';

	let { onclose }: { onclose: () => void } = $props();
</script>

<div class="fixed bottom-4 right-4 z-50" in:fade={{ duration: 100 }} out:fade={{ duration: 75 }}>
	<div
		class="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-white/6 bg-white dark:bg-[#1a1a1a] px-3 py-2"
	>
		<span class="text-[0.6875rem] text-gray-500 dark:text-gray-400">
			{$t('update.available', { version: $latestVersion })}
		</span>

		<a
			href="https://github.com/open-webui/computer/releases"
			target="_blank"
			rel="noopener noreferrer"
			class="text-[0.6875rem] text-gray-900 dark:text-white hover:underline font-medium"
		>
			{$t('update.viewRelease')}
		</a>

		<button
			onclick={onclose}
			class="ml-0.5 flex items-center justify-center w-5 h-5 rounded text-gray-300 hover:text-gray-500 dark:text-gray-600 dark:hover:text-gray-400 transition-colors duration-75"
			aria-label="Dismiss"
		>
			<Icon name="xmark" size={12} />
		</button>
	</div>
</div>

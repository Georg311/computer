<script lang="ts">
	import { t } from '$lib/i18n';
	import { latestVersion } from '$lib/stores';
	import Icon from './Icon.svelte';
	import { fade } from 'svelte/transition';

	let { onclose }: { onclose: () => void } = $props();
</script>

<div class="fixed bottom-4 right-4 z-50" in:fade={{ duration: 100 }} out:fade={{ duration: 75 }}>
	<div class="app-theme app-surface flex items-center gap-2 rounded-lg border px-3 py-2">
		<span class="app-muted text-[0.6875rem]">
			{$t('update.available', { version: $latestVersion })}
		</span>

		<a
			href="https://github.com/open-webui/computer/releases"
			target="_blank"
			rel="noopener noreferrer"
			class="text-[0.6875rem] hover:underline font-medium"
		>
			{$t('update.viewRelease')}
		</a>

		<button
			onclick={onclose}
			class="app-icon-muted app-interactive ml-0.5 flex items-center justify-center w-5 h-5 rounded transition-colors duration-75"
			aria-label={$t('a11y.dismissNotification')}
		>
			<Icon name="xmark" size={12} />
		</button>
	</div>
</div>

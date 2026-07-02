<script lang="ts">
	import { t } from '$lib/i18n';
	import { appVersion, showChangelog, updateAvailable, latestVersion } from '$lib/stores';

	const REPO_URL = 'https://github.com/open-webui/computer';
	const SHARE_TEXT = 'Check out Computer. Your computer, from anywhere.';

	const shareLinks = [
		{
			label: 'X',
			href: `https://x.com/intent/tweet?text=${encodeURIComponent(SHARE_TEXT)}&url=${encodeURIComponent(REPO_URL)}`
		},
		{
			label: 'Reddit',
			href: `https://reddit.com/submit?url=${encodeURIComponent(REPO_URL)}&title=${encodeURIComponent(SHARE_TEXT)}`
		},
		{
			label: 'LinkedIn',
			href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(REPO_URL)}`
		}
	];

	let copied = $state(false);

	function copyLink() {
		navigator.clipboard.writeText(REPO_URL);
		copied = true;
		setTimeout(() => (copied = false), 2000);
	}
</script>

<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">
	{$t('about.title')}
</h2>

<div>
	<div class="flex items-baseline gap-2">
		<a
			href="https://github.com/open-webui/computer"
			target="_blank"
			rel="noopener noreferrer"
			class="text-xs font-semibold text-gray-900 dark:text-white hover:underline">Computer</a
		>
		{#if $appVersion}
			<button
				onclick={() => showChangelog.set(true)}
				class="text-[0.6875rem] text-gray-400 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 font-mono hover:underline cursor-pointer"
				>v{$appVersion}</button
			>
		{/if}
		{#if $updateAvailable}
			<span class="text-[0.6875rem] text-gray-300 dark:text-gray-600">·</span>
			<a
				href="https://github.com/open-webui/computer/releases"
				target="_blank"
				rel="noopener noreferrer"
				class="text-[0.6875rem] text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
				>{$t('about.updateAvailable', { version: $latestVersion })}</a
			>
		{/if}
	</div>

	<p class="text-[0.8125rem] text-gray-500 mt-0.5 mb-4">{$t('app.tagline')}</p>

	<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-1">
		{$t('about.license')}
	</h3>
	<p class="text-[0.6875rem] text-gray-500 leading-relaxed font-mono whitespace-pre-line">
		<a
			href="https://github.com/open-webui/computer/blob/main/LICENSE"
			target="_blank"
			rel="noopener noreferrer"
			class="underline hover:text-gray-700 dark:hover:text-gray-300">{$t('about.licenseName')}</a
		>

		<br />
		{$t('about.copyright')}
	</p>
</div>

<div class="flex items-center gap-1.5 pt-6">
	<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mr-1">{$t('about.share')}</span>
	{#each shareLinks as link, i}
		{#if i > 0}
			<span class="text-[0.6875rem] text-gray-200 dark:text-gray-700">·</span>
		{/if}
		<a
			href={link.href}
			target="_blank"
			rel="noopener noreferrer"
			class="text-[0.6875rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-500 transition-colors"
			>{link.label}</a
		>
	{/each}
	<span class="text-[0.6875rem] text-gray-200 dark:text-gray-700">·</span>
	<button
		onclick={copyLink}
		class="text-[0.6875rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-500 transition-colors cursor-pointer"
	>
		{copied ? $t('about.copied') : $t('about.copyLink')}
	</button>
</div>

<p class="text-[0.6875rem] text-gray-300 dark:text-gray-700 pt-4">
	{$t('about.createdBy')}
</p>

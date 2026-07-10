<script lang="ts">
	import { fetchJSON } from '$lib/apis';
	import Modal from './Modal.svelte';
	import Icon from './Icon.svelte';
	import { savePreferences } from '$lib/apis/state';
	import { appVersion, lastSeenVersion, showChangelog } from '$lib/stores';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { t } from '$lib/i18n';

	type ChangelogEntry = { title: string; content: string; raw: string };
	type VersionData = { date: string; [section: string]: string | ChangelogEntry[] };

	let changelog = $state<Record<string, VersionData> | null>(null);
	let error = $state(false);

	const versions = $derived.by(() => (changelog ? Object.entries(changelog) : []));

	$effect(() => {
		if ($showChangelog && !changelog && !error) {
			fetchJSON<Record<string, VersionData>>('/api/changelog')
				.then((data) => {
					changelog = data;
				})
				.catch(() => {
					error = true;
				});
		}
	});

	function handleClose() {
		if ($appVersion) {
			lastSeenVersion.set($appVersion);
			// Persist immediately so Done and the close button survive a quick reload.
			savePreferences({ version: $appVersion }).catch(() => {});
		}
		showChangelog.set(false);
	}

	function formatDate(dateStr: string): string {
		if (!dateStr) return '';
		const parts = dateStr.split('-');
		if (parts.length !== 3) return dateStr;
		const months = [
			'Jan',
			'Feb',
			'Mar',
			'Apr',
			'May',
			'Jun',
			'Jul',
			'Aug',
			'Sep',
			'Oct',
			'Nov',
			'Dec'
		];
		const year = parts[0];
		const monthIdx = parseInt(parts[1], 10) - 1;
		const day = parseInt(parts[2], 10);
		return monthIdx >= 0 && monthIdx < 12 ? `${months[monthIdx]} ${day}, ${year}` : dateStr;
	}
</script>

{#if $showChangelog}
	<Modal onclose={handleClose} class="w-full max-w-3xl mx-4 md:mx-0 flex flex-col max-h-[52vh]">
		<div class="flex items-center gap-3 px-4 pt-4 pb-2 shrink-0">
			<div class="min-w-0 flex-1">
				<h2 class="text-sm font-medium text-gray-900 dark:text-white">
					{$t('changelog.whatsNew')}
				</h2>
				{#if $appVersion}
					<p class="mt-0.5 text-[0.6875rem] text-gray-400 dark:text-gray-600">
						{$t('changelog.releaseNotes')}
					</p>
				{/if}
			</div>

			<button
				class="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-600 dark:hover:bg-white/6 dark:hover:text-gray-300 transition-colors duration-75"
				onclick={handleClose}
				aria-label={$t('common.close')}
			>
				<Icon name="xmark" size={14} />
			</button>
		</div>

		<div class="flex-1 min-h-0 overflow-y-auto px-4 py-3">
			{#if versions.length > 0}
				<div class="space-y-6">
					{#each versions as [ver, data], i}
						<div>
							<div class="mb-2">
								<h3 class="text-[0.8125rem] font-semibold text-gray-900 dark:text-white">v{ver}</h3>
								<p class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-0.5">
									{formatDate(data.date)}
								</p>
							</div>

							{#each Object.entries(data).filter(([key]) => key !== 'date') as [section, items]}
								{#if Array.isArray(items) && items.length > 0}
									<div class="mb-3">
										<span
											class="inline-block text-[0.625rem] font-semibold uppercase tracking-wide rounded-full px-2 py-0.5 my-1.5
											{section === 'added'
												? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
												: section === 'fixed'
													? 'bg-green-500/10 text-green-600 dark:text-green-400'
													: section === 'changed'
														? 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
														: section === 'removed'
															? 'bg-red-500/10 text-red-600 dark:text-red-400'
															: 'text-gray-400 dark:text-gray-600'}"
										>
											{section}
										</span>
										<ul class="space-y-2 mt-1.5">
											{#each items as entry}
												<li class="flex gap-2.5 text-xs leading-relaxed">
													<span
														class="mt-[0.45em] h-1 w-1 shrink-0 rounded-full bg-gray-300 dark:bg-gray-700"
													></span>
													<div class="min-w-0">
														{#if entry.title}
															<span class="font-medium text-gray-900 dark:text-white"
																>{entry.title}</span
															>
															{#if entry.content}
																<span class="ml-1 text-gray-500 dark:text-gray-400"
																	>{entry.content}</span
																>
															{/if}
														{:else}
															<span class="text-gray-600 dark:text-gray-400"
																>{entry.content || entry.raw}</span
															>
														{/if}
													</div>
												</li>
											{/each}
										</ul>
									</div>
								{/if}
							{/each}
						</div>
					{/each}
				</div>
			{:else if error}
				<div class="flex flex-col items-center justify-center py-16 gap-2 text-center">
					<p class="text-xs text-gray-500 dark:text-gray-400">{$t('changelog.loadError')}</p>
					<button
						class="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 dark:bg-white/6 dark:text-gray-400 dark:hover:text-white transition-colors duration-75"
						onclick={() => (error = false)}
					>
						{$t('changelog.retry')}
					</button>
				</div>
			{:else}
				<div class="flex flex-col items-center justify-center py-16 gap-3">
					<Spinner size={16} />
					<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600"
						>{$t('changelog.loading')}</span
					>
				</div>
			{/if}
		</div>

		<div class="flex items-center justify-end px-4 pt-1 pb-4 shrink-0">
			<button
				class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
				onclick={handleClose}
			>
				{$t('changelog.done')}
			</button>
		</div>
	</Modal>
{/if}

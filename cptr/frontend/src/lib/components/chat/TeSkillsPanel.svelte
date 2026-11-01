<script lang="ts">
	import { onMount } from 'svelte';
	import DropdownMenu from '../DropdownMenu.svelte';
	import { getTeRepoFacts, type TeRepoFact } from '$lib/apis/chat';
	import { t } from '$lib/i18n';

	interface Props {
		chatId: string | null;
		anchor: HTMLElement | { x: number; y: number };
		onclose: () => void;
	}

	let { chatId, anchor, onclose }: Props = $props();

	let facts = $state<TeRepoFact[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(() => {
		if (!chatId) return;
		getTeRepoFacts(chatId).then((data) => {
			facts = data || [];
			loading = false;
		}).catch((err) => {
			error = err?.message || 'Failed to load repo facts';
			loading = false;
		});
	});

	function factIcon(fact: TeRepoFact): string {
		if (fact.fire_status > 0) return '\u{1F525}';
		return '\u{1F4A1}';
	}

	function factText(fact: TeRepoFact): string {
		const text = fact.fact_text;
		if (text.length > 200) return text.substring(0, 200) + '…';
		return text;
	}
</script>

<DropdownMenu
	items={[]}
	{anchor}
	{onclose}
	align="end"
	className="w-80 max-w-[calc(100vw-1.5rem)] p-0"
>
	<div class="max-h-[70dvh] overflow-y-auto px-2 py-1 text-xs sm:max-h-[min(72dvh,32.5rem)]">

		{#if loading}
			<div class="rounded-xl px-1.5 py-1.5 flex items-center gap-2 text-gray-400 dark:text-gray-600">
				<svg class="size-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M12 2a10 10 0 0 1 10 10"/>
				</svg>
				<span>{$t('chat.teRepoFactsLoading')}</span>
			</div>
		{:else if error}
			<div class="rounded-xl px-1.5 py-1.5 text-red-400 dark:text-red-500">
				{error}
			</div>
		{:else if facts.length === 0}
			<div class="px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600">
				{$t('chat.teRepoFactsNoFacts')}
			</div>
		{:else}
			<section>
				<div class="px-1.5 pb-0.5 pt-1.5 text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600">
					{$t('chat.teRepoFactsTitle')} ({facts.length})
				</div>

				{#each facts as fact}
					<div class="flex items-start gap-2 rounded-xl px-2 py-1.5 text-gray-600 dark:text-gray-400">
						<span class="shrink-0 pt-0.5 text-[0.8125rem] w-5 text-center">{factIcon(fact)}</span>
						<span class="min-w-0 flex-1 truncate font-mono text-xs leading-relaxed">
							{factText(fact)}
						</span>
					</div>
				{/each}

				<!-- Info about fact learning -->
				<div class="px-2 py-1.5 text-xs leading-relaxed text-gray-400 dark:text-gray-600">
					{$t('chat.teRepoFactsLearned')}: {facts.filter(f => f.fire_status > 0).length} {$t('chat.teRepoFactsUsed')}
				</div>
			</section>
		{/if}

		<!-- Empty State -->
		{#if !loading && !error && facts.length === 0}
			<div class="px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600">
				{$t('chat.teRepoFactsNoData')}
			</div>
		{/if}
	</div>
</DropdownMenu>

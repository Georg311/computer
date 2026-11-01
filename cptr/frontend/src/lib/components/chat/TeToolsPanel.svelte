<script lang="ts">
	import { onMount } from 'svelte';
	import DropdownMenu from '../DropdownMenu.svelte';
	import Icon from '../Icon.svelte';
	import { getTeToolPruning, applyTeToolPruning, type TeToolPruningRecommendation } from '$lib/apis/chat';
	import { t } from '$lib/i18n';

	interface Props {
		chatId: string | null;
		anchor: HTMLElement | { x: number; y: number };
		onclose: () => void;
	}

	let { chatId, anchor, onclose }: Props = $props();

	let data = $state<null | {
		recommendations: TeToolPruningRecommendation[];
		evidence_threshold: number;
		total_tools: number;
	}> (null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(() => {
		if (!chatId) return;
		getTeToolPruning(chatId).then((d) => {
			data = d;
			loading = false;
		}).catch((err) => {
			error = err?.message || 'Failed to load tool pruning data';
			loading = false;
		});
	});

	let appliedTools = $state<string[]>([]);

	async function handleApply(toolName: string, event: Event) {
		event.preventDefault();
		event.stopPropagation();
		if (appliedTools.includes(toolName)) return;
		try {
			await applyTeToolPruning(chatId!, [toolName]);
			appliedTools = [...appliedTools, toolName];
		} catch (e) {
			error = e?.message || 'Failed to apply pruning';
		}
	}

	function toolIcon(name: string): string {
		switch (name) {
			case 'bash': return '$';
			case 'edit': return '\u{1F4DD}';
			case 'web_search': return '\u{1F50D}';
			case 'read_file':
			case 'write_file': return '\u{1F4C4}';
			default: return '\u2699\uFE0F';
		}
	}

	function toolLabel(name: string): string {
		const labels: Record<string, string> = {
			bash: 'Shell',
			edit: 'Edit File',
			create_file: 'Create File',
			read_file: 'Read File',
			write_file: 'Write File',
			web_search: 'Web Search',
			google_drive: 'Google Drive',
			display_file: 'Display File',
		};
		return labels[name] || name;
	}

	function recommendationLabel(rec: string): string {
		return rec === 'immediate' ? '\u26A0\uFE0F sofort' : '\u{1F4A1} empfohlen';
	}

	function recommendationColor(rec: string): string {
		return rec === 'immediate' ? 'text-red-400' : 'text-yellow-400';
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
				<span>{$t('chat.teToolPruningLoading')}</span>
			</div>
		{:else if error}
			<div class="rounded-xl px-1.5 py-1.5 text-red-400 dark:text-red-500">
				{error}
			</div>
		{:else if data && data.recommendations.length === 0}
			<div class="px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600">
				{$t('chat.teToolPruningNoRecommendations')}
			</div>
		{:else if data}
			<section>
				<div class="px-1.5 pb-0.5 pt-1.5 text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600">
					{$t('chat.teToolPruningTitle')} ({data.recommendations.length})
				</div>

					{#each data.recommendations as rec}
						<div class="flex h-9 items-center gap-3 rounded-xl px-2 text-gray-600 dark:text-gray-400">
							<span class="shrink-0 text-[0.8125rem] w-5 text-center">{toolIcon(rec.tool_name)}</span>
							<span class="min-w-0 flex-1 truncate font-mono text-xs">{toolLabel(rec.tool_name)}</span>
							<span class="{recommendationColor(rec.recommendation)} text-xs shrink-0">
								{recommendationLabel(rec.recommendation)}
							</span>
						</div>
					{/each}

					<!-- Apply buttons for immediate recommendations -->
					{#if data.recommendations.some(r => r.recommendation === 'immediate')}
						<div class="flex flex-wrap gap-1 px-1.5 py-2">
							{#each data.recommendations as rec}
								{#if rec.recommendation === 'immediate' && !appliedTools.includes(rec.tool_name)}
									<button
										onclick={(e) => handleApply(rec.tool_name, e)}
										class="text-[0.5625rem] px-1.5 py-0.5 rounded-lg bg-red-900/30 text-red-400 border border-red-800/30 hover:bg-red-900/50 transition-colors"
									>
										{rec.tool_name} → {t('chat.teToolPruningApply')}
									</button>
								{/if}
							{/each}
						</div>
					{/if}

					<!-- Evidence threshold info -->
					<div class="px-1.5 py-0.5 text-[0.5625rem] leading-relaxed text-gray-400 dark:text-gray-600">
						{$t('chat.teToolPruningEvidence')}: {data.evidence_threshold} {$t('chat.teToolPruningSessions')}
					</div>
			</section>
		{/if}

		<!-- Empty State (when no data at all) -->
		{#if !loading && !error && !data}
			<div class="px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600">
				{$t('chat.teToolPruningNoData')}
			</div>
		{/if}
	</div>
</DropdownMenu>

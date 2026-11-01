<script lang="ts">
	import { onMount } from 'svelte';
	import DropdownMenu from '../DropdownMenu.svelte';
	import Icon from '../Icon.svelte';
	import { getTeStatus, type TeToolUsageItem } from '$lib/apis/chat';
	import { t } from '$lib/i18n';

	interface Props {
		chatId: string | null;
		anchor: HTMLElement | { x: number; y: number };
		onclose: () => void;
	}

	let { chatId, anchor, onclose }: Props = $props();

	let teData = $state<null | {
		effective_tokens: number;
		total_tokens: number;
		cache_savings_pct: number;
		pricing_overhead: number;
		session_cost_usd: number;
		tool_usage: TeToolUsageItem[];
	}>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(() => {
		if (!chatId) return;
		getTeStatus(chatId).then((data) => {
			teData = data;
			loading = false;
		}).catch((err) => {
			error = err?.message || 'Failed to load TE status';
			loading = false;
		});
	});

	function formatTokenCount(value: number): string {
		if (value >= 1_000_000) return `${trimNumber(value / 1_000_000)}m`;
		if (value >= 1_000) return `${trimNumber(value / 1_000)}k`;
		return String(value);
	}

	function trimNumber(value: number): string {
		return value >= 10 ? String(Math.round(value)) : value.toFixed(1).replace(/\.0$/, '');
	}

	function formatCurrency(usd: number): string {
		if (usd < 0.001) return `$<${Math.round(usd * 1000)}k`;
		return `$${usd.toFixed(4)}`;
	}

	let effectiveTokens = '';
	let totalTokens = '';
	let savingsPct = '';
	let pricingOverhead = '';
	let sessionCost = '';

	$effect(() => {
		if (teData) {
			effectiveTokens = formatTokenCount(teData.effective_tokens);
			totalTokens = formatTokenCount(teData.total_tokens);
			savingsPct = `${teData.cache_savings_pct}%`;
			pricingOverhead = teData.pricing_overhead > 0 ? `+${formatTokenCount(teData.pricing_overhead)}` : '0';
			sessionCost = formatCurrency(teData.session_cost_usd);
		} else {
			effectiveTokens = '—';
			totalTokens = '—';
			savingsPct = '—';
			pricingOverhead = '—';
			sessionCost = '—';
		}
	});

	function toolIcon(name: string): string {
		switch (name) {
			case 'bash': return '$';
			case 'edit': return '📝';
			case 'web_search': return '🔍';
			case 'read_file':
			case 'write_file': return '📄';
			default: return '⚙️';
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
</script>

<DropdownMenu
	items={[]}
	{anchor}
	{onclose}
	align="end"
	className="w-80 max-w-[calc(100vw-1.5rem)] p-0"
>
	<div class="max-h-[70dvh] overflow-y-auto px-1 py-0.5 text-xs sm:max-h-[min(72dvh,32.5rem)]">

		{#if loading}
			<div class="rounded-xl px-1.5 py-1.5 flex items-center gap-2 text-gray-400 dark:text-gray-600">
				<svg class="size-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M12 2a10 10 0 0 1 10 10"/>
				</svg>
				<span>{$t('chat.teStatusLoading')}</span>
			</div>
		{:else if error}
			<div class="rounded-xl px-1.5 py-1.5 text-red-400 dark:text-red-500">
				{error}
			</div>
		{:else if teData}
			<!-- Token Stats Section -->
			<section>
				<div class="px-1.5 pb-0.5 pt-1.5 text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600">
					{$t('chat.teStatusTokenStats')}
				</div>

				<!-- Effective Tokens -->
				<div class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate">{$t('chat.teStatusEffectiveTokens')}</span>
					<span class="shrink-0 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">{effectiveTokens}</span>
				</div>

				<!-- Total Tokens -->
				<div class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate">{$t('chat.teStatusTotalTokens')}</span>
					<span class="shrink-0 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">{totalTokens}</span>
				</div>

				<!-- Cache Savings -->
				<div class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate">{$t('chat.teStatusCacheSavings')}</span>
					<span class="shrink-0 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">{savingsPct}</span>
				</div>

				<!-- Pricing Overhead -->
				<div class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate">{$t('chat.teStatusPricingOverhead')}</span>
					<span class="shrink-0 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">{pricingOverhead}</span>
				</div>

				<!-- Session Cost -->
				<div class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate">{$t('chat.teStatusSessionCost')}</span>
					<span class="shrink-0 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">{sessionCost}</span>
				</div>
			</section>

			<!-- Tool Usage Section -->
			{#if teData.tool_usage && teData.tool_usage.length > 0}
				<section class="mt-1">
					<div class="px-1.5 pb-0.5 pt-1.5 text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600">
						{$t('chat.teStatusToolUsage')} ({teData.tool_usage.length})
					</div>

					{#each teData.tool_usage as tool}
						<div class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400">
							<span class="shrink-0 text-[0.8125rem] w-5 text-center">{toolIcon(tool.tool_name)}</span>
							<span class="min-w-0 flex-1 truncate font-mono text-[0.625rem]">{toolLabel(tool.tool_name)}</span>
							<span class="shrink-0 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">
								{tool.call_count}x
							</span>
						</div>
					{/each}
				</section>
			{:else if teData && teData.tool_usage.length === 0}
				<div class="px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600">
					{$t('chat.teStatusNoTools')}
				</div>
			{/if}

			<!-- Empty State -->
			{#if !loading && !error}
				<div class="px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600">
					{$t('chat.teStatusNoData')}
				</div>
			{/if}
		{/if}
	</div>
</DropdownMenu>

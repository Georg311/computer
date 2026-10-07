<script lang="ts">
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import { t } from '$lib/i18n';

	interface Props {
		metrics: Record<string, number> | null;
		streaming?: boolean;
	}
	let { metrics, streaming = false }: Props = $props();

	let expanded = $state(false);

	const promptTokens = $derived(metrics?.prompt_tokens ?? 0);
	const reasoningTokens = $derived(metrics?.reasoning_tokens ?? 0);
	const responseTokens = $derived(metrics?.response_tokens ?? 0);
	// Live snapshots carry no flag (always estimated); the final persisted
	// snapshot sets estimated=false when real provider usage was available.
	const estimated = $derived(metrics?.estimated ?? true);
	const ttftMs = $derived(metrics?.ttft_ms ?? 0);
	const reasoningTimeS = $derived(metrics?.reasoning_time_s ?? 0);
	const responseTimeS = $derived(metrics?.response_time_s ?? 0);
	const wallTimeS = $derived(metrics?.wall_time_s ?? 0);

	const totalTokens = $derived(reasoningTokens + responseTokens);

	function rate(tokens: number, timeS: number): number | null {
		return timeS > 0.001 ? tokens / timeS : null;
	}

	function fmtRate(tokens: number, timeS: number): string {
		const r = rate(tokens, timeS);
		return r == null ? '—' : `${r.toFixed(2)} t/s`;
	}

	function fmtMsPerToken(tokens: number, timeS: number): string {
		const r = rate(tokens, timeS);
		return r == null ? '—' : `${(1000 / r).toFixed(1)} ms`;
	}

	function fmtTimeS(s: number): string {
		if (s <= 0) return '—';
		if (s < 1) return `${Math.round(s * 1000)}ms`;
		return `${s.toFixed(1)}s`;
	}

	const rows = $derived([
		{
			key: 'prompt',
			label: $t('chat.phase.prompt'),
			tokens: promptTokens,
			estimated,
			timeS: ttftMs / 1000
		},
		{
			key: 'reasoning',
			label: $t('chat.phase.reasoning'),
			tokens: reasoningTokens,
			estimated,
			timeS: reasoningTimeS
		},
		{
			key: 'response',
			label: $t('chat.phase.response'),
			tokens: responseTokens,
			estimated,
			timeS: responseTimeS
		},
		{
			key: 'generation',
			label: $t('chat.phase.generation'),
			tokens: totalTokens,
			estimated,
			timeS: wallTimeS
		}
	]);

	const livePhase = $derived(responseTokens > 0 ? 'response' : 'reasoning');
	const liveTokens = $derived(livePhase === 'response' ? responseTokens : reasoningTokens);
	const liveTimeS = $derived(livePhase === 'response' ? responseTimeS : reasoningTimeS);

	const labelTokens = $derived($t('chat.stats.tokens'));
	const labelTime = $derived($t('chat.stats.time'));
	const labelSpeed = $derived($t('chat.stats.speed'));
	const labelPerToken = $derived($t('chat.stats.perToken'));
</script>

{#if streaming}
	<!-- Live metrics line while the model is generating -->
	<div class="flex items-center gap-1.5 text-[0.6875rem] font-mono text-gray-400 dark:text-gray-500 select-none">
		<span class="inline-block size-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-pulse"></span>
		<span>{livePhase === 'response' ? $t('chat.phase.response') : $t('chat.phase.reasoning')}</span>
		<span>·</span>
		<span>~{liveTokens} tok</span>
		<span>·</span>
		<span>{fmtTimeS(wallTimeS)}</span>
		<span>·</span>
		<span>~{fmtRate(liveTokens, liveTimeS).replace(' t/s', '')} t/s</span>
	</div>
{:else if totalTokens > 0 || promptTokens > 0}
	<!-- Collapsible stats table after the turn is done -->
	<div class="w-full min-w-0 flex flex-col">
		<button
			class="w-full min-w-0 text-left text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition cursor-pointer"
			aria-expanded={expanded}
			onclick={() => (expanded = !expanded)}
		>
			<div class="flex items-center gap-1.5 text-sm min-w-0">
				<div class="text-gray-400 dark:text-gray-500">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.75"
						stroke="currentColor"
						class="size-3.5"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3.75 9.75h16.5m-16.5 0v3.75m0 0h16.5v-3.75m-16.5 0h3m9 0h3m-16.5 12.75V18c0-.5.5-1 1-1h16.5c.5 0 1 .5 1 1v3.75"
						/>
					</svg>
				</div>

				<div class="flex-1 min-w-0 line-clamp-1">
					<span class="font-normal">{$t('chat.llamaStats')}</span>
				</div>

				<div class="flex shrink-0 self-center translate-y-[0.0625rem]">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="3.5"
						stroke="currentColor"
						class="size-3 transition-transform duration-200 text-gray-400 dark:text-gray-500 {expanded
							? 'rotate-180'
							: ''}"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
					</svg>
				</div>
			</div>
		</button>

		{#if expanded}
			<div transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
				<table class="mt-1 mb-0.5 px-1 text-[0.6875rem] font-mono text-gray-500 dark:text-gray-400">
					<thead>
						<tr class="text-left text-gray-400 dark:text-gray-500">
							<th class="font-normal pr-3"></th>
							<th class="font-normal pr-3">{labelTokens}</th>
							<th class="font-normal pr-3">{labelTime}</th>
							<th class="font-normal pr-3">{labelSpeed}</th>
							<th class="font-normal">{labelPerToken}</th>
						</tr>
					</thead>
					<tbody>
						{#each rows as row}
							<tr class="tabular-nums">
								<td class="pr-3">{row.label}</td>
								<td class="pr-3">{row.estimated ? '~' : ''}{Math.round(row.tokens)}</td>
								<td class="pr-3">{fmtTimeS(row.timeS)}</td>
								<td class="pr-3">{row.estimated ? '~' : ''}{fmtRate(row.tokens, row.timeS)}</td>
								<td>{fmtMsPerToken(row.tokens, row.timeS)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
{/if}

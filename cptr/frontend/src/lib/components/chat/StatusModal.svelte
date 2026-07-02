<script lang="ts">
	import Modal from '../Modal.svelte';
	import Terminal from '../Terminal.svelte';
	import DropdownMenu from '../DropdownMenu.svelte';
	import Icon from '../Icon.svelte';
	import type { ContextUsage } from '$lib/apis/chat';
	import type { CommandSession } from '$lib/apis/terminal';
	import { t } from '$lib/i18n';

	interface Props {
		chatId: string | null;
		contextUsage: ContextUsage | null;
		commandSessions?: CommandSession[];
		queuedMessages?: { id: string; content: string }[];
		initialCommandSessionId?: string | null;
		anchor: HTMLElement | { x: number; y: number };
		onclose: () => void;
	}

	let {
		chatId,
		contextUsage,
		commandSessions = [],
		queuedMessages = [],
		initialCommandSessionId = null,
		anchor,
		onclose
	}: Props = $props();

	let copied = $state(false);
	let selectedSessionId = $state<string | null>(null);
	let appliedInitialSessionId = $state<string | null>(null);
	let missingSessionId = $state<string | null>(null);
	let forceStopSignal = $state(0);
	let terminatingSessionId = $state<string | null>(null);

	const runningSessions = $derived(commandSessions.filter((session) => !session.done));
	const selectedSession = $derived(
		runningSessions.find((session) => session.command_session_id === selectedSessionId) ?? null
	);
	const terminatingSelectedSession = $derived(
		!!selectedSession && terminatingSessionId === selectedSession.command_session_id
	);
	const contextPercent = $derived(Math.max(0, Math.round(contextUsage?.percent ?? 0)));
	const contextValue = $derived(
		contextUsage
			? `${contextPercent}% ${formatTokenCount(contextUsage.estimated_tokens || contextUsage.tokens)}/${formatTokenCount(contextUsage.threshold)}`
			: $t('chat.statusUnknown')
	);
	const contextBarPercent = $derived(Math.min(contextPercent, 100));

	function copyChatId() {
		if (!chatId) return;
		navigator.clipboard.writeText(chatId);
		copied = true;
		setTimeout(() => (copied = false), 1600);
	}

	function elapsedLabel(ts: number): string {
		const seconds = Math.max(0, Math.floor(Date.now() / 1000 - ts));
		if (seconds < 60) return `${seconds}s`;
		const minutes = Math.floor(seconds / 60);
		if (minutes < 60) return `${minutes}m`;
		return `${Math.floor(minutes / 60)}h`;
	}

	function shortCommand(command: string): string {
		return command.length > 92 ? `${command.slice(0, 92)}...` : command;
	}

	function formatTokenCount(value: number): string {
		if (value >= 1_000_000) return `${trimNumber(value / 1_000_000)}m`;
		if (value >= 1_000) return `${trimNumber(value / 1_000)}k`;
		return String(value);
	}

	function trimNumber(value: number): string {
		return value >= 10 ? String(Math.round(value)) : value.toFixed(1).replace(/\.0$/, '');
	}

	function sessionLabel(session: CommandSession): string {
		return session.command_session_id;
	}

	function statusLabel(session: CommandSession): string {
		if (!session.done) return elapsedLabel(session.created_at);
		if (session.exit_code && session.exit_code !== 0) {
			return $t('chat.failedWithCode', { code: session.exit_code });
		}
		return $t('chat.finished');
	}

	function terminateSelectedSession() {
		if (!selectedSession || terminatingSelectedSession) return;
		terminatingSessionId = selectedSession.command_session_id;
		forceStopSignal += 1;
	}

	$effect(() => {
		if (!initialCommandSessionId) return;
		const exists = runningSessions.some(
			(session) => session.command_session_id === initialCommandSessionId
		);
		if (exists) {
			selectedSessionId = initialCommandSessionId;
			appliedInitialSessionId = initialCommandSessionId;
			missingSessionId = null;
		} else if (initialCommandSessionId !== appliedInitialSessionId) {
			selectedSessionId = null;
			appliedInitialSessionId = initialCommandSessionId;
			missingSessionId = initialCommandSessionId;
		}
	});
</script>

{#if selectedSession}
	<Modal
		{onclose}
		class="mx-4 flex h-[min(47.5rem,82dvh)] w-full max-w-[min(60rem,calc(100vw-2rem))] flex-col overflow-hidden max-sm:mx-0 max-sm:h-[100dvh] max-sm:max-w-none max-sm:rounded-none"
	>
		<div class="flex h-full min-h-0 flex-col overflow-hidden">
			<div
				class="flex h-9 shrink-0 items-center gap-3 border-b border-gray-100 px-3 dark:border-white/8"
			>
				<button
					type="button"
					class="flex h-7 shrink-0 items-center gap-1.5 rounded-lg pr-2 text-xs text-gray-400 transition-colors duration-75 hover:text-gray-700 dark:text-gray-600 dark:hover:text-gray-300"
					onclick={onclose}
				>
					<Icon name="chevron-left" size={12} />
					<span>{$t('settings.back')}</span>
				</button>
				<div class="min-w-0 flex-1">
					<div class="truncate font-mono text-xs font-medium text-gray-900 dark:text-white">
						{sessionLabel(selectedSession)}
					</div>
				</div>
				<button
					type="button"
					class="h-7 shrink-0 px-1.5 text-xs text-gray-400 underline-offset-2 transition-colors duration-75 hover:text-gray-700 hover:underline disabled:cursor-default disabled:text-gray-300 disabled:no-underline dark:text-gray-600 dark:hover:text-gray-200 dark:disabled:text-gray-700"
					title={terminatingSelectedSession ? $t('chat.terminating') : $t('chat.forceTerminate')}
					disabled={terminatingSelectedSession}
					onclick={terminateSelectedSession}
				>
					{terminatingSelectedSession ? $t('chat.terminating') : $t('chat.terminate')}
				</button>
			</div>
			<div class="min-h-0 flex-1" style="background: var(--app-bg); color: var(--app-fg);">
				<Terminal
					wsPath={`/api/terminal/sessions/${selectedSession.command_session_id}/ws`}
					initialOutput={selectedSession.output ?? ''}
					initialOffset={selectedSession.total_bytes ?? 0}
					{forceStopSignal}
					readOnly={true}
				/>
			</div>
		</div>
	</Modal>
{:else}
	<DropdownMenu
		items={[]}
		{anchor}
		{onclose}
		align="end"
		className="w-80 max-w-[calc(100vw-1.5rem)] p-0"
	>
		<div class="max-h-[70dvh] overflow-y-auto px-1 py-0.5 text-xs sm:max-h-[min(72dvh,32.5rem)]">
			{#if missingSessionId}
				<div
					class="rounded-xl px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600"
				>
					{$t('chat.sessionUnavailable')}
				</div>
			{/if}

			{#if runningSessions.length}
				<section>
					<div
						class="px-1.5 pb-0.5 pt-1.5 text-[0.625rem] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600"
					>
						{$t('chat.sessions')}
					</div>
					{#each runningSessions as session}
						<div
							class="flex h-7 min-w-0 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400"
						>
							<button
								type="button"
								class="min-w-0 flex-1 truncate text-left font-mono text-[0.6875rem] text-gray-400 underline-offset-2 transition-colors duration-75 hover:text-gray-700 hover:underline dark:text-gray-600 dark:hover:text-gray-200"
								title={shortCommand(session.command)}
								onclick={() => (selectedSessionId = session.command_session_id)}
							>
								{sessionLabel(session)}
							</button>
							<span class="shrink-0 text-[0.625rem] text-gray-400 dark:text-gray-600">
								{statusLabel(session)}
							</span>
						</div>
					{/each}
				</section>
			{/if}

			<section>
				<div class="rounded-xl px-1.5 py-1.5 text-gray-600 dark:text-gray-400">
					<div class="flex h-5 items-center gap-3">
						<span class="min-w-0 flex-1 truncate">{$t('chat.statusContextUsage')}</span>
						<span class="shrink-0 font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">
							{contextValue}
						</span>
					</div>
					<div class="mt-2 h-px overflow-hidden rounded-full bg-gray-100 dark:bg-white/8">
						<div
							class="h-full rounded-full bg-gray-300 dark:bg-white/20"
							style={`width: ${contextBarPercent}%`}
						></div>
					</div>
				</div>

				{#if queuedMessages.length}
					<div
						class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400"
					>
						<span class="min-w-0 flex-1 truncate">{$t('chat.queuedMessages')}</span>
						<span class="font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">
							{queuedMessages.length}
						</span>
					</div>
				{/if}

				{#if chatId}
					<div
						class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400"
					>
						<span class="min-w-0 flex-1 truncate">{$t('chat.statusChatId')}</span>
						<button
							type="button"
							class="min-w-0 max-w-[11rem] truncate font-mono text-[0.625rem] text-gray-400 underline-offset-2 transition-colors duration-75 hover:text-gray-700 hover:underline dark:text-gray-600 dark:hover:text-gray-200"
							onclick={copyChatId}
						>
							{copied ? $t('about.copied') : chatId}
						</button>
					</div>
				{:else}
					<div
						class="flex h-7 items-center gap-3 rounded-xl px-1.5 text-gray-600 dark:text-gray-400"
					>
						<span class="min-w-0 flex-1 truncate">{$t('chat.statusChatId')}</span>
						<span class="font-mono text-[0.625rem] text-gray-400 dark:text-gray-600">
							{$t('chat.statusNoChat')}
						</span>
					</div>
				{/if}
			</section>
		</div>
	</DropdownMenu>
{/if}

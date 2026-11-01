<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { t } from '$lib/i18n';
	import { socketStore } from '$lib/stores/socket.svelte';

	interface Props {
		chatId: string;
		message: string;
		envelopeSize?: number;
		onAcknowledge?: () => void;
	}

	let { chatId, message, envelopeSize = 0, onAcknowledge = () => {} }: Props = $props();

	let visible = false;
	let timeout: ReturnType<typeof setTimeout>;
	const DISMISS_DELAY_MS = 8000;

	function dismiss() {
		visible = false;
		if (timeout) clearTimeout(timeout);
		onAcknowledge();
	}

	function handleDismiss(e: MouseEvent) {
		// Only dismiss on close button click, not on the whole toast
		const target = e.target as HTMLElement;
		if (target.closest('[data-dismiss]')) {
			dismiss();
		}
	}

	onMount(() => {
		visible = true;
		timeout = setTimeout(dismiss, DISMISS_DELAY_MS);
	});

	onDestroy(() => {
		if (timeout) clearTimeout(timeout);
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="loop-nudge-toast app-theme app-surface relative flex gap-3 text-left w-full border shadow-lg rounded-xl py-3 px-4 cursor-pointer select-none"
	onpointerup={handleDismiss}
>
	<!-- Close button -->
	<button
		data-dismiss
		class="app-subtle-surface app-muted app-interactive absolute -top-1 -left-1 p-0.5 rounded-full opacity-0 group-hover:opacity-100 border-none cursor-pointer transition-opacity duration-150 z-10"
		aria-label={$t('a11y.dismissNotification')}
		onclick={(e) => {
			e.stopPropagation();
			dismiss();
		}}
	>
		<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3 h-3">
			<path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
		</svg>
	</button>

	<!-- Icon -->
	<div class="shrink-0 self-start -translate-y-0.5">
		<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5 text-orange-500">
			<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
		</svg>
	</div>

	<!-- Content -->
	<div class="min-w-0">
		<div class="text-[0.8125rem] font-medium mb-0.5 text-orange-600 dark:text-orange-400">
			{$t('loopGuard.nudge.title', { default: 'Turn scheint festzusteigen' })}
		</div>
		<div class="app-muted text-xs font-normal line-clamp-2">{message}</div>
		{#if envelopeSize > 0}
			<div class="text-[0.6875rem] app-dim mt-1">
				{$t('loopGuard.nudge.envelope', { default: 'Envelope: {count} Calls' })} {envelopeSize}
			</div>
		{/if}
	</div>
</div>

<style>
	.loop-nudge-toast {
		min-width: var(--width, 18.75rem);
		border-color: #f59e0b;
		background: linear-gradient(to right, rgba(245, 158, 11, 0.05), transparent);
	}
</style>

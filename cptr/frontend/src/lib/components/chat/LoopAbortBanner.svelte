<script lang="ts">
	import { t } from '$lib/i18n';
	import { socketStore } from '$lib/stores/socket.svelte';

	interface Props {
		chatId: string;
		message: string;
		onConfirm?: () => void;
		onCancel?: () => void;
	}

	let { chatId, message, onConfirm = () => {}, onCancel = () => {} }: Props = $props();

	function handleAbort() {
		// Acknowledge the abort request via socket
		socketStore.emit('loop_guard:acknowledge', {
			chat_id: chatId,
			type: 'abort'
		});
		onConfirm();
	}

	function handleContinue() {
		// Acknowledge nudge as resolved (user chooses to continue)
		socketStore.emit('loop_guard:acknowledge', {
			chat_id: chatId,
			type: 'nudge'
		});
		onCancel();
	}
</script>

<div class="loop-abort-banner app-surface border rounded-xl p-4 flex gap-3 items-start">
	<!-- Icon -->
	<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6 text-red-500 shrink-0 mt-0.5">
		<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm3.5 14H8.5a1 1 0 010-2h1v-4h1V9h2v2h1v4a1 1 0 010 2z"/>
	</svg>

	<!-- Content -->
	<div class="min-w-0 flex-1">
		<div class="text-sm font-medium mb-1 text-red-600 dark:text-red-400">
			{$t('loopGuard.abort.title', { default: 'Turn scheint festzusteigen' })}
		</div>
		<div class="text-xs app-muted mb-3">{message}</div>

		<!-- Action buttons -->
		<div class="flex gap-2">
			<button
				class="app-muted app-interactive px-3 py-1.5 rounded-md border bg-red-600 hover:bg-red-700 text-white text-xs font-medium transition-colors"
				onclick={handleAbort}
			>
				{$t('loopGuard.abort.confirm', { default: 'Abbrechen' })}
			</button>
			<button
				class="app-subtle-surface app-interactive px-3 py-1.5 rounded-md border text-xs font-medium transition-colors"
				onclick={handleContinue}
			>
				{$t('loopGuard.abort.continue', { default: 'Weiter' })}
			</button>
		</div>
	</div>
</div>

<style>
	.loop-abort-banner {
		border-color: #ef4444;
		background: linear-gradient(to right, rgba(239, 68, 68, 0.05), transparent);
	}
</style>

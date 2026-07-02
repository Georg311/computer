<script lang="ts">
	import { systemEvents, type PortInfo } from '$lib/stores/systemEvents.svelte';
	import { activeWorkspace, openPreviewTab } from '$lib/stores';
	import Icon from './Icon.svelte';
	import { t } from '$lib/i18n';

	// ONLY show ports that belong to a terminal session in the active workspace
	let relevantPorts = $derived(
		systemEvents.newPorts.filter((p) => {
			if (!p.session_id) return false; // unknown origin, don't show
			// Check if this session belongs to the active workspace
			return (
				$activeWorkspace?.groups.some((g) => g.tabs.some((t) => t.sessionId === p.session_id)) ??
				false
			);
		})
	);

	// Auto-dismiss after 10s
	let dismissTimers = new Map<number, ReturnType<typeof setTimeout>>();

	$effect(() => {
		for (const port of relevantPorts) {
			if (!dismissTimers.has(port.port)) {
				dismissTimers.set(
					port.port,
					setTimeout(() => {
						systemEvents.dismissPort(port.port);
						dismissTimers.delete(port.port);
					}, 10000)
				);
			}
		}
	});

	function preview(port: PortInfo) {
		openPreviewTab(port.port);
		systemEvents.dismissPort(port.port);
	}

	function dismiss(port: PortInfo) {
		systemEvents.dismissPort(port.port);
		const timer = dismissTimers.get(port.port);
		if (timer) {
			clearTimeout(timer);
			dismissTimers.delete(port.port);
		}
	}

	// Find terminal tab label for a session_id
	function terminalLabel(sessionId: string | null): string | null {
		if (!sessionId || !$activeWorkspace) return null;
		const tab = $activeWorkspace.groups
			.flatMap((g) => g.tabs)
			.find((t) => t.sessionId === sessionId);
		return tab?.label ?? null;
	}
</script>

{#if relevantPorts.length > 0}
	<div class="fixed bottom-8 right-3 z-[200] flex flex-col gap-1.5 pointer-events-none">
		{#each relevantPorts as port (port.port)}
			<div
				class="app-theme app-surface flex items-center gap-2 px-3 py-2 rounded-lg border shadow-lg pointer-events-auto animate-in"
			>
				<span class="app-icon-muted text-xs shrink-0">🌐</span>
				<span class="text-xs font-medium font-mono">:{port.port}</span>
				<span class="app-muted text-[0.6875rem]">({port.process})</span>
				{#if terminalLabel(port.session_id)}
					<span class="app-muted text-[0.625rem] italic"
						>{$t('port.via', { name: terminalLabel(port.session_id) })}</span
					>
				{/if}
				<button
					class="ml-1 px-2 py-0.5 rounded text-[0.6875rem] font-medium text-white bg-blue-500 hover:bg-blue-600 transition-colors duration-100 shrink-0"
					onclick={() => preview(port)}>{$t('port.preview')}</button
				>
				<button
					class="app-icon-muted app-interactive flex items-center justify-center w-4 h-4 rounded transition-colors duration-100 shrink-0"
					onclick={() => dismiss(port)}
				>
					<Icon name="xmark" size={9} />
				</button>
			</div>
		{/each}
	</div>
{/if}

<style>
	.animate-in {
		animation: slideIn 0.15s ease-out;
	}

	@keyframes slideIn {
		from {
			transform: translateY(0.375rem);
			opacity: 0;
		}
		to {
			transform: translateY(0);
			opacity: 1;
		}
	}
</style>

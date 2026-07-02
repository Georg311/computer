<script lang="ts">
	import Collapsible from './Collapsible.svelte';
	import { t } from '$lib/i18n';

	interface SystemInfo {
		os: string;
		arch: string;
		python: string;
		cpu_count: number;
		cpu_usage?: number;
		memory_total?: number;
		memory_available?: number;
		disk_total?: number;
		disk_used?: number;
		disk_free?: number;
		uptime_seconds?: number;
		load_avg?: number[];
		network?: { name: string; ip: string }[];
	}

	interface Process {
		pid: number;
		cpu: number;
		mem: number;
		name: string;
	}

	interface Props {
		system: SystemInfo;
		processes?: Process[];
		defaultOpen?: boolean;
	}

	let { system: sys, processes = [], defaultOpen = false }: Props = $props();

	function formatBytes(bytes: number): string {
		if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(0)} MB`;
		return `${(bytes / 1073741824).toFixed(1)} GB`;
	}

	function formatUptime(seconds: number): string {
		const days = Math.floor(seconds / 86400);
		const hours = Math.floor((seconds % 86400) / 3600);
		if (days > 0) return `${days}d ${hours}h`;
		const mins = Math.floor((seconds % 3600) / 60);
		if (hours > 0) return `${hours}h ${mins}m`;
		return `${mins}m`;
	}

	const summary = $derived.by(() => {
		const parts: string[] = [];
		if (sys.cpu_usage != null) parts.push($t('system.summaryCpu', { percent: sys.cpu_usage }));
		if (sys.memory_total) {
			const memPct = Math.round(
				((sys.memory_total - (sys.memory_available ?? 0)) / sys.memory_total) * 100
			);
			parts.push($t('system.summaryMemory', { percent: memPct }));
		}
		if (sys.disk_total) {
			const diskPct = Math.round(((sys.disk_used ?? 0) / sys.disk_total) * 100);
			parts.push($t('system.summaryDisk', { percent: diskPct }));
		}
		if (sys.uptime_seconds)
			parts.push($t('system.uptime', { value: formatUptime(sys.uptime_seconds) }));
		return parts.join('  ');
	});
</script>

<Collapsible title={$t('system.title')} {summary} open={defaultOpen}>
	<div class="flex flex-col gap-3">
		{#if sys.cpu_usage != null}
			<div>
				<div class="flex items-center justify-between mb-1">
					<span class="text-[0.6875rem] text-gray-500 dark:text-gray-500">{$t('system.cpu')}</span>
					<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600 font-mono"
						>{sys.cpu_usage}%</span
					>
				</div>
				<div class="h-1.5 rounded-full bg-gray-100 dark:bg-white/6 overflow-hidden">
					<div
						class="h-full rounded-full bg-gray-400 dark:bg-gray-500 transition-all"
						style="width: {sys.cpu_usage}%"
					></div>
				</div>
			</div>
		{/if}

		{#if sys.memory_total}
			{@const memUsed = sys.memory_total - (sys.memory_available ?? 0)}
			{@const memPct = Math.round((memUsed / sys.memory_total) * 100)}
			<div>
				<div class="flex items-center justify-between mb-1">
					<span class="text-[0.6875rem] text-gray-500 dark:text-gray-500"
						>{$t('system.memory')}</span
					>
					<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600 font-mono"
						>{formatBytes(memUsed)} / {formatBytes(sys.memory_total)}</span
					>
				</div>
				<div class="h-1.5 rounded-full bg-gray-100 dark:bg-white/6 overflow-hidden">
					<div
						class="h-full rounded-full bg-gray-400 dark:bg-gray-500 transition-all"
						style="width: {memPct}%"
					></div>
				</div>
			</div>
		{/if}

		{#if sys.disk_total}
			{@const diskPct = Math.round(((sys.disk_used ?? 0) / sys.disk_total) * 100)}
			<div>
				<div class="flex items-center justify-between mb-1">
					<span class="text-[0.6875rem] text-gray-500 dark:text-gray-500">{$t('system.disk')}</span>
					<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600 font-mono"
						>{formatBytes(sys.disk_used ?? 0)} / {formatBytes(sys.disk_total)}</span
					>
				</div>
				<div class="h-1.5 rounded-full bg-gray-100 dark:bg-white/6 overflow-hidden">
					<div
						class="h-full rounded-full bg-gray-400 dark:bg-gray-500 transition-all"
						style="width: {diskPct}%"
					></div>
				</div>
			</div>
		{/if}

		<div
			class="flex items-center gap-4 text-[0.6875rem] text-gray-400 dark:text-gray-600 font-mono"
		>
			<span>{$t('system.cores', { count: sys.cpu_count })}</span>
			<span>{sys.arch}</span>
			{#if sys.uptime_seconds}
				<span>{$t('system.uptime', { value: formatUptime(sys.uptime_seconds) })}</span>
			{/if}
			{#if sys.load_avg}
				<span>{$t('system.load', { value: sys.load_avg.join(' ') })}</span>
			{/if}
		</div>

		{#if sys.network?.length}
			<div
				class="flex flex-wrap gap-x-4 gap-y-0.5 text-[0.6875rem] font-mono text-gray-400 dark:text-gray-600"
			>
				{#each sys.network as iface}
					<span>{iface.name} {iface.ip}</span>
				{/each}
			</div>
		{/if}

		{#if processes.length}
			<div class="mt-1 font-mono text-[0.6875rem]">
				<div class="flex items-center gap-2 text-gray-400 dark:text-gray-600 mb-1">
					<span class="w-14 text-right">{$t('system.cpuShort')}</span>
					<span class="w-12 text-right">{$t('system.memoryShort')}</span>
					<span class="flex-1">{$t('system.process')}</span>
				</div>
				{#each processes as proc}
					<div class="flex items-center gap-2 text-gray-500 dark:text-gray-500 py-px">
						<span class="w-14 text-right text-gray-700 dark:text-gray-300"
							>{proc.cpu.toFixed(1)}%</span
						>
						<span class="w-12 text-right">{proc.mem.toFixed(1)}%</span>
						<span class="flex-1 truncate">{proc.name}</span>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</Collapsible>

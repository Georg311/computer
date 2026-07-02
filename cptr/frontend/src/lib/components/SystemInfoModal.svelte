<script lang="ts">
	import { onMount } from 'svelte';
	import Modal from './Modal.svelte';
	import SystemInfo from './SystemInfo.svelte';
	import Spinner from './common/Spinner.svelte';
	import { getWelcome } from '$lib/apis/state';
	import { t } from '$lib/i18n';

	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	let loading = $state(true);
	let welcomeData = $state<{
		hostname?: string;
		system?: {
			os: string;
			arch: string;
			python: string;
			cpu_count: number;
			memory_total?: number;
			memory_available?: number;
			disk_total?: number;
			disk_used?: number;
			disk_free?: number;
			uptime_seconds?: number;
			load_avg?: number[];
			cpu_usage?: number;
			network?: { name: string; ip: string }[];
		};
		processes?: { pid: number; cpu: number; mem: number; name: string }[];
	} | null>(null);

	onMount(() => {
		getWelcome()
			.then((data) => {
				welcomeData = data as typeof welcomeData;
			})
			.catch(() => {
				welcomeData = null;
			})
			.finally(() => {
				loading = false;
			});
	});
</script>

<Modal {onclose} class="w-full max-w-[26.25rem] mx-4">
	<div class="px-4 py-3.5">
		<div class="mb-3 flex items-baseline justify-between gap-3">
			<div class="min-w-0">
				<h2 class="text-sm font-medium text-gray-900 dark:text-white">{$t('system.infoTitle')}</h2>
				{#if welcomeData?.hostname}
					<p class="mt-0.5 truncate font-mono text-[0.6875rem] text-gray-400 dark:text-gray-600">
						{welcomeData.hostname}
					</p>
				{/if}
			</div>
		</div>

		{#if loading}
			<div class="flex h-28 items-center justify-center">
				<Spinner size={18} />
			</div>
		{:else if welcomeData?.system}
			<SystemInfo system={welcomeData.system} processes={welcomeData.processes ?? []} defaultOpen />
		{:else}
			<div class="py-8 text-center text-xs text-gray-400 dark:text-gray-600">
				{$t('system.unavailable')}
			</div>
		{/if}
	</div>
</Modal>

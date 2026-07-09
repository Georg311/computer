<script lang="ts">
	/**
	 * Automations panel — list + detail view.
	 * Rendered as a full-page SvelteKit route.
	 */
	import { goto } from '$app/navigation';
	import Icon from '../Icon.svelte';
	import ToggleSwitch from '../common/ToggleSwitch.svelte';
	import Spinner from '../common/Spinner.svelte';
	import AutomationModal from './AutomationModal.svelte';
	import { sidebarOpen } from '$lib/stores';
	import { getPathDisplayName } from '$lib/utils/paths';
	import {
		getAutomations,
		toggleAutomation,
		deleteAutomation,
		runAutomation,
		getAutomationById,
		getAutomationRuns,
		generateWebhook,
		deleteWebhook,
		type AutomationData,
		type AutomationRunData
	} from '$lib/apis/automations';
	import { toast } from 'svelte-sonner';
	import { t } from '$lib/i18n';

	interface Props {
		automationId?: string;
	}

	let { automationId }: Props = $props();

	// ── List state ──
	let items = $state<AutomationData[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let searchQuery = $state('');
	let statusFilter = $state('all');
	let showModal = $state(false);
	let editingAutomation = $state<AutomationData | null>(null);

	// ── Detail state ──
	let detail = $state<AutomationData | null>(null);
	let runs = $state<AutomationRunData[]>([]);
	let detailLoading = $state(false);

	async function loadList() {
		loading = true;
		try {
			const res = await getAutomations(undefined, searchQuery || undefined, statusFilter);
			items = res.items;
			total = res.total;
		} catch (e: any) {
			toast.error(e.message || $t('automations.failedToLoad'));
		} finally {
			loading = false;
		}
	}

	async function loadDetail(id: string) {
		detailLoading = true;
		try {
			detail = await getAutomationById(id);
			runs = await getAutomationRuns(id);
		} catch (e: any) {
			toast.error(e.message || $t('automations.failedToLoadOne'));
		} finally {
			detailLoading = false;
		}
	}

	$effect(() => {
		if (!automationId) {
			loadList();
		}
	});

	$effect(() => {
		if (automationId) {
			loadDetail(automationId);
		}
	});

	async function handleToggle(a: AutomationData) {
		try {
			const updated = await toggleAutomation(a.id);
			items = items.map((i) => (i.id === a.id ? updated : i));
			if (detail?.id === a.id) detail = updated;
		} catch (e: any) {
			toast.error(e.message || $t('automations.failedToToggle'));
		}
	}

	async function handleDelete(a: AutomationData) {
		if (!confirm($t('automations.deleteConfirm', { name: a.name }))) return;
		try {
			await deleteAutomation(a.id);
			items = items.filter((i) => i.id !== a.id);
			if (detail?.id === a.id) goto('/scheduled');
			toast.success($t('automations.deleted'));
		} catch (e: any) {
			toast.error(e.message || $t('automations.failedToDelete'));
		}
	}

	async function handleRunNow(a: AutomationData) {
		try {
			await runAutomation(a.id);
			toast.success($t('automations.triggered', { name: a.name }));
		} catch (e: any) {
			toast.error(e.message || $t('automations.failedToRun'));
		}
	}

	function handleSave(saved: AutomationData) {
		const idx = items.findIndex((i) => i.id === saved.id);
		if (idx >= 0) {
			items[idx] = saved;
			items = [...items];
		} else {
			items = [saved, ...items];
		}
		if (detail?.id === saved.id) detail = saved;
		showModal = false;
		editingAutomation = null;
	}

	function formatTime(ns: number | null): string {
		if (!ns) return '-';
		return new Date(ns / 1_000_000).toLocaleString(undefined, {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function parseFrequency(rrule: string): string {
		if (rrule.includes('COUNT=1')) return 'Once';
		const match = rrule.match(/FREQ=(\w+)/);
		if (!match) return 'Custom';
		const freq = match[1].toLowerCase();
		return freq.charAt(0).toUpperCase() + freq.slice(1);
	}

	// ── Webhook ──
	let webhookLoading = $state(false);
	let webhookCopied = $state(false);

	async function handleGenerateWebhook() {
		if (!detail) return;
		webhookLoading = true;
		try {
			const updated = await generateWebhook(detail.id);
			detail = updated;
			items = items.map((i) => (i.id === updated.id ? updated : i));
			toast.success($t('automations.webhookEnabled'));
		} catch (e: any) {
			toast.error(e.message || $t('automations.failedToGenerateWebhook'));
		} finally {
			webhookLoading = false;
		}
	}

	async function handleRevokeWebhook() {
		if (!detail) return;
		webhookLoading = true;
		try {
			const updated = await deleteWebhook(detail.id);
			detail = updated;
			items = items.map((i) => (i.id === updated.id ? updated : i));
			toast.success($t('automations.webhookDisabled'));
		} catch (e: any) {
			toast.error(e.message || $t('automations.failedToRevokeWebhook'));
		} finally {
			webhookLoading = false;
		}
	}

	function copyWebhookUrl() {
		if (!detail?.webhook_url) return;
		navigator.clipboard.writeText(detail.webhook_url);
		webhookCopied = true;
		setTimeout(() => (webhookCopied = false), 2000);
	}
</script>

<div class="flex flex-col h-full overflow-hidden">
	{#if automationId}
		<!-- ── Detail ── -->
		{#if detailLoading}
			<div class="flex items-center justify-center py-12">
				<Spinner size={16} />
			</div>
		{:else if detail}
			<!-- Header -->
			<div
				class="flex items-center gap-2 h-9 {$sidebarOpen
					? 'px-3'
					: 'px-1.5'} border-b border-gray-200 dark:border-white/6 shrink-0"
			>
				{#if !$sidebarOpen}
					<button
						class="flex items-center justify-center w-7 h-7 rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-100"
						onclick={() => sidebarOpen.set(true)}
						title={$t('automations.toggleSidebar')}
					>
						<Icon name="sidebar-expand" size={14} />
					</button>
				{/if}
				<button
					class="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
					onclick={() => goto('/scheduled')}
				>
					<Icon name="chevron-left" size={12} />
					<span>{$t('automations.title')}</span>
				</button>
				<span class="text-gray-300 dark:text-gray-600">/</span>
				<span class="text-xs text-gray-900 dark:text-white truncate">{detail.name}</span>

				<div class="ml-auto flex items-center gap-2">
					<ToggleSwitch value={detail.is_active} onchange={() => handleToggle(detail!)} />
					<button
						class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
						onclick={() => handleRunNow(detail!)}
						title={$t('automations.runNow')}
					>
						<Icon name="play" size={11} />
					</button>
					<button
						class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
						onclick={() => {
							editingAutomation = detail;
							showModal = true;
						}}
						title={$t('automationModal.save')}
					>
						<Icon name="pencil" size={11} />
					</button>
					<button
						class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-red-500 transition-colors duration-75"
						onclick={() => handleDelete(detail!)}
						title={$t('admin.delete')}
					>
						<Icon name="trash" size={11} />
					</button>
				</div>
			</div>

			<!-- Content -->
			<div class="flex-1 overflow-y-auto">
				<!-- Info rows -->
				<div class="border-b border-gray-200 dark:border-white/6">
					<div class="flex items-center h-7 px-3">
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500 w-20 shrink-0"
							>{$t('automations.status')}</span
						>
						<div class="flex items-center gap-1.5">
							<span
								class="w-1.5 h-1.5 rounded-full {detail.is_active
									? 'bg-emerald-500'
									: 'bg-gray-400'}"
							></span>
							<span class="text-xs text-gray-700 dark:text-gray-300"
								>{detail.is_active ? $t('automations.active') : $t('automations.paused')}</span
							>
						</div>
					</div>
					<div class="flex items-center h-7 px-3">
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500 w-20 shrink-0"
							>{$t('automations.schedule')}</span
						>
						<span class="text-xs text-gray-700 dark:text-gray-300"
							>{parseFrequency(detail.rrule)}</span
						>
					</div>
					<div class="flex items-center h-7 px-3">
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500 w-20 shrink-0"
							>{$t('automations.model')}</span
						>
						<span class="text-[0.6875rem] text-gray-500 dark:text-gray-400 font-mono"
							>{detail.model_id}</span
						>
					</div>
					<div class="flex items-center h-7 px-3">
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500 w-20 shrink-0"
							>{$t('automations.nextRun')}</span
						>
						<span class="text-xs text-gray-700 dark:text-gray-300"
							>{formatTime(detail.next_run_at)}</span
						>
					</div>
					<div class="flex items-center h-7 px-3">
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500 w-20 shrink-0"
							>{$t('automations.lastRun')}</span
						>
						<span class="text-xs text-gray-700 dark:text-gray-300"
							>{formatTime(detail.last_run_at)}</span
						>
					</div>
					<div class="flex items-center min-h-[1.75rem] px-3">
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500 w-20 shrink-0"
							>{$t('automations.webhook')}</span
						>
						{#if detail.webhook_url}
							<div class="flex items-center gap-1.5 min-w-0 flex-1">
								<span class="text-[0.6875rem] text-gray-500 dark:text-gray-400 font-mono truncate"
									>...?token={detail.webhook_url.split('token=')[1]?.slice(0, 12)}...</span
								>
								<button
									class="text-[0.6875rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75 shrink-0"
									onclick={copyWebhookUrl}
								>
									{webhookCopied ? $t('automations.copied') : $t('automations.copy')}
								</button>
							</div>
						{:else if detail.has_webhook}
							<!-- Webhook enabled, URL not available -->
							<div class="flex items-center gap-1.5">
								<span class="text-[0.6875rem] text-gray-700 dark:text-gray-300"
									>{$t('automations.enabled')}</span
								>
								<span class="text-gray-300 dark:text-gray-600">·</span>
								<button
									class="text-[0.6875rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
									onclick={handleGenerateWebhook}
									disabled={webhookLoading}
								>
									{$t('automations.regenerate')}
								</button>
								<span class="text-gray-300 dark:text-gray-600">·</span>
								<button
									class="text-[0.6875rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
									onclick={handleRevokeWebhook}
									disabled={webhookLoading}
								>
									{$t('automations.disable')}
								</button>
							</div>
						{:else}
							<button
								class="text-[0.6875rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
								onclick={handleGenerateWebhook}
								disabled={webhookLoading}
							>
								{$t('automations.enable')}
							</button>
						{/if}
					</div>
				</div>

				<!-- Prompt -->
				<div class="border-b border-gray-200 dark:border-white/6 px-3 py-2">
					<div class="text-[0.6875rem] text-gray-400 dark:text-gray-500 mb-1">
						{$t('automations.prompt')}
					</div>
					<div
						class="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono leading-relaxed max-h-32 overflow-y-auto"
					>
						{detail.prompt}
					</div>
				</div>

				<!-- Runs -->
				<div class="px-3 py-2">
					<div class="text-[0.6875rem] text-gray-400 dark:text-gray-500 mb-1">
						{$t('automations.runs')}
					</div>
					{#if runs.length === 0}
						<div class="text-[0.6875rem] text-gray-400 dark:text-gray-600 py-2">
							{$t('automations.noRuns')}
						</div>
					{:else}
						{#each runs as run}
							<div class="flex items-center gap-2 h-7 text-xs">
								<span
									class="w-1.5 h-1.5 rounded-full shrink-0 {run.status === 'success'
										? 'bg-emerald-500'
										: 'bg-red-400'}"
								></span>
								<span class="text-gray-500 dark:text-gray-400">{formatTime(run.created_at)}</span>
								{#if run.chat_id}
									<button
										class="text-[0.6875rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
										onclick={() => {
											const workspacePath = detail?.workspace;
											const workspaceQuery = workspacePath
												? `workspace=${encodeURIComponent(workspacePath)}&`
												: '';
											goto(`/?${workspaceQuery}chatId=${encodeURIComponent(run.chat_id!)}`);
										}}
									>
										{$t('automations.viewChat')}
									</button>
								{/if}
								{#if run.error}
									<span class="text-[0.6875rem] text-red-400 truncate" title={run.error}
										>{run.error}</span
									>
								{/if}
							</div>
						{/each}
					{/if}
				</div>
			</div>
		{/if}
	{:else}
		<!-- ── List ── -->
		<!-- Header -->
		<div
			class="flex items-center gap-2 h-9 {$sidebarOpen
				? 'px-3'
				: 'px-1.5'} border-b border-gray-200 dark:border-white/6 shrink-0"
		>
			{#if !$sidebarOpen}
				<button
					class="flex items-center justify-center w-7 h-7 rounded-md text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-100"
					onclick={() => sidebarOpen.set(true)}
					title={$t('automations.toggleSidebar')}
				>
					<Icon name="sidebar-expand" size={14} />
				</button>
			{/if}
			<span class="text-xs text-gray-900 dark:text-white">{$t('automations.title')}</span>
			{#if total > 0}
				<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600">{total}</span>
			{/if}

			<div class="ml-auto flex items-center gap-1">
				<select
					class="text-[0.6875rem] bg-transparent text-gray-400 dark:text-gray-500 outline-none cursor-pointer"
					bind:value={statusFilter}
					onchange={loadList}
				>
					<option value="all">{$t('automations.all')}</option>
					<option value="active">{$t('automations.active')}</option>
					<option value="paused">{$t('automations.paused')}</option>
				</select>
				<button
					class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
					onclick={() => {
						editingAutomation = null;
						showModal = true;
					}}
					title={$t('automations.newAutomation')}
				>
					<Icon name="plus" size={13} />
				</button>
			</div>
		</div>

		<!-- Search -->
		<div
			class="flex items-center gap-1.5 h-8 px-3 border-b border-gray-200 dark:border-white/6 shrink-0"
		>
			<Icon name="search" size={13} class="text-gray-400 shrink-0" />
			<input
				type="text"
				class="flex-1 border-none outline-none bg-transparent text-xs text-gray-900 dark:text-white placeholder:text-gray-400"
				placeholder={$t('automations.filter')}
				bind:value={searchQuery}
				oninput={loadList}
			/>
			{#if searchQuery}
				<button
					class="text-gray-400 flex items-center"
					onclick={() => {
						searchQuery = '';
						loadList();
					}}
				>
					<Icon name="xmark" size={11} />
				</button>
			{/if}
		</div>

		<!-- List -->
		<div class="flex-1 overflow-y-auto p-1">
			{#if loading}
				<div class="flex items-center justify-center py-12">
					<Spinner size={16} />
				</div>
			{:else if items.length === 0}
				<div class="flex flex-col items-center justify-center py-12 gap-2">
					<p class="text-xs text-gray-400 dark:text-gray-600">
						{searchQuery ? $t('automations.noMatches') : $t('automations.noAutomations')}
					</p>
					{#if !searchQuery}
						<button
							class="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-3 py-1 rounded-lg bg-gray-100 dark:bg-white/6 transition-colors duration-75"
							onclick={() => {
								editingAutomation = null;
								showModal = true;
							}}
						>
							{$t('automations.create')}
						</button>
					{/if}
				</div>
			{:else}
				{#each items as a (a.id)}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div class="flex items-center gap-2 h-7 px-2 rounded-md">
						<span
							class="w-1.5 h-1.5 rounded-full shrink-0 {a.is_active
								? 'bg-emerald-500'
								: 'bg-gray-400'}"
						></span>
						<button
							class="text-xs text-gray-700 dark:text-gray-300 truncate flex-1 text-left hover:underline cursor-pointer transition-colors duration-75"
							onclick={() => goto(`/scheduled/${a.id}`)}
						>
							{a.name}
						</button>
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600 shrink-0"
							>{getPathDisplayName(a.workspace, a.workspace)}</span
						>
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600 shrink-0">·</span>
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600 shrink-0"
							>{parseFrequency(a.rrule)}</span
						>

						<div class="flex items-center gap-2 shrink-0" onclick={(e) => e.stopPropagation()}>
							<button
								class="flex items-center justify-center w-5 h-5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
								onclick={() => handleRunNow(a)}
								title={$t('automations.runNow')}
							>
								<Icon name="play" size={11} />
							</button>
							<div class="flex items-center" onclick={(e) => e.stopPropagation()}>
								<ToggleSwitch value={a.is_active} onchange={() => handleToggle(a)} />
							</div>
						</div>
					</div>
				{/each}
			{/if}
		</div>
	{/if}
</div>

{#if showModal}
	<AutomationModal
		automation={editingAutomation}
		onclose={() => {
			showModal = false;
			editingAutomation = null;
		}}
		onsave={handleSave}
	/>
{/if}

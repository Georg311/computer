<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getTePricing, updateTePricing, resetTePricing, addCustomModel, deleteCustomModel, type TePricingEntry } from '$lib/apis/admin';
	import { t } from '$lib/i18n';
	import Icon from '../Icon.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	type ProviderGroup = [string, [string, TePricingEntry][]];

	let loading = $state(true);
	let saving = $state(false);
	let pricingData = $state<{
		defaults: Record<string, Record<string, number>>;
		custom: Record<string, Record<string, number>>;
		merged: Record<string, TePricingEntry>;
	} | null>(null);
	let error = $state<string | null>(null);

	// Provider-grouped data for template rendering
	let groupedProviders = $state<ProviderGroup[]>([]);
	let customModels = $state<Record<string, Record<string, number>>>({});

	// Edit state
	let editingModel = $state<string | null>(null);
	let editingPricing = $state<Record<string, string>>({
		input: '',
		cache_read: '',
		cache_write: '',
		output: ''
	});

	// Custom model form state
	let showAddCustomForm = $state(false);
	let newModelId = $state('');
	let newPricing = $state<Record<string, string>>({
		input: '',
		cache_read: '',
		cache_write: '',
		output: ''
	});

	const PRICING_FIELDS = ['input', 'cache_read', 'cache_write', 'output'] as const;

	onMount(() => {
		loadPricing();
	});

	async function loadPricing() {
		try {
			pricingData = await getTePricing();
			if (pricingData?.merged) {
				groupedProviders = groupByProvider(pricingData.merged);
				customModels = pricingData.custom || {};
			} else {
				groupedProviders = [];
				customModels = {};
			}
			loading = false;
		} catch (e) {
			error = e?.message || 'Failed to load pricing';
			groupedProviders = [];
			customModels = {};
			loading = false;
		}
	}

	function groupByProvider(merged: Record<string, TePricingEntry>): ProviderGroup[] {
		if (!merged || typeof merged !== 'object') return [];
		const groups: Record<string, [string, TePricingEntry][]> = {};
		for (const [modelId, entry] of Object.entries(merged)) {
			const provider = getProviderLabel(modelId);
			if (!groups[provider]) groups[provider] = [];
			groups[provider].push([modelId, entry]);
		}
		return Object.entries(groups) as ProviderGroup[];
	}

	function startEdit(modelId: string) {
		editingModel = modelId;
		const entry = pricingData?.merged[modelId];
		if (entry) {
			editingPricing = {
				input: String(entry.current.input),
				cache_read: String(entry.current.cache_read),
				cache_write: String(entry.current.cache_write),
				output: String(entry.current.output)
			};
		}
	}

	function cancelEdit() {
		editingModel = null;
	}

	async function saveEdit() {
		if (!editingModel || !pricingData) return;
		saving = true;
		try {
			const pricing: Record<string, number> = {};
			for (const field of PRICING_FIELDS) {
				const val = parseFloat(editingPricing[field]);
				if (!isNaN(val)) {
					pricing[field] = val;
				}
			}
			await updateTePricing(editingModel, pricing);
			toast.success(`Pricing updated for ${editingModel}`);
			pricingData = await getTePricing();
			groupedProviders = groupByProvider(pricingData.merged);
			customModels = pricingData.custom || {};
			cancelEdit();
		} catch (e) {
			error = e?.message || 'Failed to save pricing';
			setTimeout(() => { error = null; }, 3000);
		} finally {
			saving = false;
		}
	}

	async function handleReset() {
		if (!confirm('Reset all TE pricing to defaults? This cannot be undone.')) return;
		try {
			await resetTePricing();
			toast.success('Pricing reset to defaults');
			pricingData = await getTePricing();
			groupedProviders = groupByProvider(pricingData.merged);
			customModels = pricingData.custom || {};
		} catch (e) {
			error = e?.message || 'Failed to reset pricing';
			setTimeout(() => { error = null; }, 3000);
		}
	}

	async function handleAddCustomModel() {
		if (!newModelId.trim()) {
			toast.error('Model ID is required');
			return;
		}
		const pricing: Record<string, number> = {};
		let hasValue = false;
		for (const field of PRICING_FIELDS) {
			const val = parseFloat(newPricing[field]);
			if (!isNaN(val) && val >= 0) {
				pricing[field] = val;
				hasValue = true;
			}
		}
		if (!hasValue) {
			toast.error('At least one pricing field is required');
			return;
		}
		try {
			await addCustomModel(newModelId.trim(), pricing);
			toast.success(`Custom model ${newModelId} added`);
			newModelId = '';
			newPricing = { input: '', cache_read: '', cache_write: '' };
			showAddCustomForm = false;
			pricingData = await getTePricing();
			groupedProviders = groupByProvider(pricingData.merged);
			customModels = pricingData.custom || {};
		} catch (e) {
			error = e?.message || 'Failed to add custom model';
			setTimeout(() => { error = null; }, 3000);
		}
	}

	async function handleDeleteCustomModel(modelId: string) {
		if (!confirm(`Remove custom pricing for ${modelId}?`)) return;
		try {
			await deleteCustomModel(modelId);
			toast.success(`Custom pricing removed for ${modelId}`);
			pricingData = await getTePricing();
			groupedProviders = groupByProvider(pricingData.merged);
			customModels = pricingData.custom || {};
		} catch (e) {
			error = e?.message || 'Failed to delete custom model';
			setTimeout(() => { error = null; }, 3000);
		}
	}

	function formatPrice(value: number): string {
		return value < 0.001 ? `$${Math.round(value * 1_000_000)}/M` : `$${value.toFixed(4)}`;
	}

	function getProviderIcon(modelId: string): string {
		if (modelId.startsWith('gpt')) return '🤖';
		if (modelId.startsWith('claude')) return '🟣';
		if (modelId.startsWith('gemini')) return '🔶';
		return '🛠️';
	}

	function getProviderLabel(modelId: string): string {
		if (modelId.startsWith('gpt')) return 'OpenAI';
		if (modelId.startsWith('claude')) return 'Anthropic';
		if (modelId.startsWith('gemini')) return 'Google';
		return 'Custom';
	}

	function getProviderColor(modelId: string): string {
		if (modelId.startsWith('gpt')) return 'text-blue-400';
		if (modelId.startsWith('claude')) return 'text-purple-400';
		if (modelId.startsWith('gemini')) return 'text-yellow-400';
		return 'text-orange-400';
	}

	function getGroupColor(group: string): string {
		switch (group) {
			case 'gpt-5': return 'text-blue-300';
			case 'claude-opus': return 'text-purple-300';
			case 'claude-sonnet': return 'text-violet-300';
			case 'claude-haiku': return 'text-sky-300';
			case 'gemini': return 'text-yellow-300';
			case 'Custom': return 'text-orange-400';
			default: return 'text-gray-400';
		}
	}
</script>

<div class="flex flex-col gap-3">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-2">
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5 text-green-500 dark:text-green-400 shrink-0">
				<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm3.5 6.5c.28 0 .5.22.5.5v1.89l1.78 1.78a.75.75 0 0 1-1.06 1.06L16 14.11v2.39a.75.75 0 0 1-.5.72l-3 1a.75.75 0 0 1-.5 0l-3-1A.75.75 0 0 1 8 16.5v-2.39L6.22 15.47a.75.75 0 0 1-1.06-1.06L6.5 12.61V10.7a.75.75 0 0 1 .72-.5h3l.78-.78a.75.75 0 0 1 1.06 0l.78.78h3Z"/>
			</svg>
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{$t('admin.tePricing')}</span>
		</div>
		<div class="flex items-center gap-2">
			<button
				class="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
				onclick={handleReset}
			>
				{$t('admin.tePricingReset')}
			</button>
			<button
				class="text-xs px-2 py-1 rounded-lg bg-orange-600 text-white hover:bg-orange-700 transition-colors"
				onclick={() => showAddCustomForm = !showAddCustomForm}
			>
				{showAddCustomForm ? '×' : '+ '}{$t('admin.tePricingAddCustom')}
			</button>
		</div>
	</div>

	{#if loading}
		<div class="flex items-center gap-2 text-gray-400">
			<svg class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M12 2a10 10 0 0 1 10 10"/>
			</svg>
			<span>{$t('admin.tePricingLoading')}</span>
		</div>
	{:else if error}
		<div class="text-red-400 text-sm">{error}</div>
	{:else}
		<!-- Add Custom Model Form -->
		{#if showAddCustomForm}
			<div class="p-3 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
				<div class="flex flex-col gap-2">
					<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
						{$t('admin.tePricingCustomModelId')}
					</label>
					<input
						type="text"
						value={newModelId}
						onchange={(e) => { newModelId = e.currentTarget.value; }}
						placeholder="my-custom-model"
						class="w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-2 py-1 text-xs font-mono outline-none focus:ring-1 focus:ring-orange-400"
					/>
					<div class="grid grid-cols-2 gap-2">
						{#each PRICING_FIELDS as field}
							<div class="flex flex-col gap-0.5">
								<label class="text-[0.6rem] text-gray-500 dark:text-gray-500 uppercase">{field}</label>
								<input
									type="number"
									value={newPricing[field]}
									onchange={(e) => { newPricing[field] = e.currentTarget.value; }}
									class="w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-1 py-0.5 text-xs font-mono text-center outline-none focus:ring-1 focus:ring-orange-400"
									step="0.001"
									min="0"
								/>
							</div>
						{/each}
					</div>
					<div class="flex gap-2 mt-1">
						<button
							class="text-xs px-3 py-1 rounded bg-orange-600 text-white hover:bg-orange-700 transition-colors"
							onclick={handleAddCustomModel}
							disabled={saving}
						>
							{saving ? '...' : '✓ Add'}
						</button>
						<button
							class="text-xs px-3 py-1 rounded bg-gray-300 dark:bg-gray-700 hover:bg-gray-400 transition-colors"
							onclick={() => { showAddCustomForm = false; newModelId = ''; newPricing = { input: '', cache_read: '', cache_write: '' }; }}
						>
							{$t('admin.tePricingCancel')}
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- Custom Models Section -->
		{#if Object.keys(customModels).length > 0}
			<div class="mt-3">
				<div class="text-xs font-medium uppercase tracking-wide text-orange-400 dark:text-orange-600 mb-1 flex items-center gap-2">
					<span>🛠️</span> {$t('admin.tePricingCustomModels')} ({Object.keys(customModels).length})
				</div>
				<div class="space-y-0.5">
					{#each Object.entries(customModels) as [modelId, pricing]}
						<div class="flex items-center gap-2 p-1.5 rounded-lg bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 hover:bg-orange-100 dark:hover:bg-orange-900/30 transition-colors">
							<span class="shrink-0 text-base">🛠️</span>
							<span class="text-xs font-mono flex-1 truncate text-orange-600 dark:text-orange-400">
								{modelId}
							</span>
							<span class="text-[0.5rem] px-1 py-0.5 rounded bg-orange-100 dark:bg-orange-900/40 text-orange-600 dark:text-orange-400 font-medium">
								CUSTOM
							</span>
							<span class="text-xs font-mono text-gray-500 dark:text-gray-400 shrink-0">
								{formatPrice(pricing.input || 0)}
							</span>
							<button
								class="text-xs px-1.5 py-0.5 rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
								onclick={() => handleDeleteCustomModel(modelId)}
							>
								✕
							</button>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Provider Groups -->
		{#each groupedProviders as [provider, entries]}
			<div class="mt-2">
				<div class="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600 mb-1 {getGroupColor(provider)}">
					{provider} ({entries.length})
				</div>
				<div class="space-y-0.5">
					{#each entries as [modelId, entry]}
						{#if editingModel === modelId}
							<!-- Edit Row -->
							<div class="flex items-center gap-2 p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
								<span class="text-xs font-mono flex-1 truncate {getProviderColor(modelId)}">
									{modelId}
								</span>
								{#each PRICING_FIELDS as field}
									<div class="flex flex-col items-center gap-0.5">
										<input
											type="number"
											value={editingPricing[field]}
											onchange={(e) => { editingPricing[field] = e.currentTarget.value; }}
											class="w-16 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-1 py-0.5 text-xs font-mono text-center outline-none focus:ring-1 focus:ring-blue-400"
											step="0.001"
											min="0"
										/>
										<span class="text-[0.5rem] text-gray-400">{field}</span>
									</div>
								{/each}
								<div class="flex gap-1">
									<button
										class="text-xs px-2 py-0.5 rounded bg-green-600 text-white hover:bg-green-700 transition-colors"
										onclick={saveEdit}
										disabled={saving}
									>
										{saving ? '...' : '✓'}
									</button>
									<button
										class="text-xs px-2 py-0.5 rounded bg-gray-300 dark:bg-gray-700 hover:bg-gray-400 transition-colors"
										onclick={cancelEdit}
									>
										✕
									</button>
								</div>
							</div>
						{:else}
							<!-- Normal Row -->
							<div class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors cursor-pointer" onclick={() => startEdit(modelId)}>
								<span class="shrink-0 text-base">{getProviderIcon(modelId)}</span>
								<span class="text-xs font-mono flex-1 truncate text-gray-600 dark:text-gray-400">
									{modelId}
								</span>
								<!-- Override badge -->
								{#if entry.overridden}
									<span class="text-[0.5rem] px-1 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400">
										override
									</span>
								{/if}
								<span class="text-xs font-mono text-gray-500 dark:text-gray-400 shrink-0">
									{formatPrice(entry.current.input)}
								</span>
							</div>
						{/if}
					{/each}
				</div>
			</div>
		{/each}

		<!-- Info -->
		<div class="text-xs text-gray-400 dark:text-gray-600 mt-2 pt-2 border-t border-gray-200 dark:border-gray-800">
			{$t('admin.tePricingInfo')} — Click a row to edit pricing. Changes are saved to config.toml [te_pricing].
		</div>
	{/if}
</div>

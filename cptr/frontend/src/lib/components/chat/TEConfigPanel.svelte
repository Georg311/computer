<script lang="ts">
	import { onMount } from 'svelte';
	import DropdownMenu from '../DropdownMenu.svelte';
	import Icon from '../Icon.svelte';
	import ToggleSwitch from '../common/ToggleSwitch.svelte';
	import { getTEConfig, updateTEConfig, type TEConfigData } from '$lib/apis/chat';
	import { t } from '$lib/i18n';

	interface Props {
		chatId: string | null;
		anchor: HTMLElement | { x: number; y: number };
		onclose: () => void;
	}

	let { chatId, anchor, onclose }: Props = $props();

	let configData = $state<TEConfigData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let successMsg = $state<string | null>(null);
	let saveTimeout: ReturnType<typeof setTimeout> | null = null;

	const defaults = {
		microskills_on: true,
		toolpruning_on: true,
		loopguard_on: true,
		max_facts: 5,
		max_tokens: 200,
		evidence_threshold: 3,
		min_sessions: 5,
		max_envelope_size: 10,
		nudge_threshold: 3,
		spiral_level: 'default' as 'conservative' | 'default' | 'aggressive'
	};

	let microskills_on = $state(defaults.microskills_on);
	let toolpruning_on = $state(defaults.toolpruning_on);
	let loopguard_on = $state(defaults.loopguard_on);
	let max_facts = $state(defaults.max_facts);
	let max_tokens = $state(defaults.max_tokens);
	let evidence_threshold = $state(defaults.evidence_threshold);
	let min_sessions = $state(defaults.min_sessions);
	let max_envelope_size = $state(defaults.max_envelope_size);
	let nudge_threshold = $state(defaults.nudge_threshold);
	let spiral_level = $state(defaults.spiral_level);

	let advancedOpen = $state(false);

	const SPIRAL_OPTIONS = ['conservative', 'default', 'aggressive'] as const;

	onMount(() => {
		if (!chatId) return;
		getTEConfig(chatId).then((data) => {
			configData = data;
			if (data) {
				microskills_on = data.microskills?.on ?? defaults.microskills_on;
				toolpruning_on = data.toolpruning?.on ?? defaults.toolpruning_on;
				loopguard_on = data.loopguard?.on ?? defaults.loopguard_on;
				max_facts = data.pricing?.max_facts ?? defaults.max_facts;
				max_tokens = data.pricing?.max_tokens ?? defaults.max_tokens;
				evidence_threshold = data.pricing?.evidence_threshold ?? defaults.evidence_threshold;
				min_sessions = data.pricing?.min_sessions ?? defaults.min_sessions;
				max_envelope_size = data.loopguard?.max_envelope_size ?? defaults.max_envelope_size;
				nudge_threshold = data.loopguard?.nudge_threshold ?? defaults.nudge_threshold;
				spiral_level = (data.loopguard?.spiral_level as typeof spiral_level) ?? defaults.spiral_level;
			}
			loading = false;
		}).catch((err) => {
			error = err?.message || 'Failed to load TE config';
			loading = false;
		});
	});

	function showSuccess(msg: string) {
		successMsg = msg;
		setTimeout(() => { successMsg = null; }, 2000);
	}

	async function debouncedSave(section: string, values: Record<string, unknown>) {
		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = setTimeout(async () => {
			try {
				await updateTEConfig(chatId!, section, values);
				showSuccess('Saved');
				// Reload config to reflect server state
				const data = await getTEConfig(chatId!);
				if (data) configData = data;
			} catch (err) {
				error = err?.message || 'Failed to save';
				setTimeout(() => { error = null; }, 3000);
			}
		}, 500);
	}

	function toggleMicroskills() {
		microskills_on = !microskills_on;
		void debouncedSave('microskills', { on: microskills_on });
	}

	function toggleToolPruning() {
		toolpruning_on = !toolpruning_on;
		void debouncedSave('toolpruning', { on: toolpruning_on });
	}

	function toggleLoopGuard() {
		loopguard_on = !loopguard_on;
		void debouncedSave('loopguard', { on: loopguard_on });
	}

	function setAdvanced(key: string, value: number) {
		const v = Math.max(1, value);
		switch (key) {
			case 'max_facts': max_facts = v; break;
			case 'max_tokens': max_tokens = v; break;
			case 'evidence_threshold': evidence_threshold = v; break;
			case 'min_sessions': min_sessions = v; break;
			case 'max_envelope_size': max_envelope_size = v; break;
			case 'nudge_threshold': nudge_threshold = v; break;
		}
		void debouncedSave('pricing', { [key]: v });
	}

	function setLoopGuardThreshold(key: string, value: number) {
		const v = Math.max(1, value);
		switch (key) {
			case 'max_envelope_size': max_envelope_size = v; break;
			case 'nudge_threshold': nudge_threshold = v; break;
		}
		void debouncedSave('loopguard', { [key]: v });
	}

	function setSpiralLevel(level: typeof spiral_level) {
		spiral_level = level;
		void debouncedSave('loopguard', { spiral_level: level });
	}

	const spiralLabel = $derived.by(() => {
		switch (spiral_level) {
			case 'conservative': return $t('teConfig.conservative');
			case 'aggressive': return $t('teConfig.aggressive');
			default: return $t('teConfig.default');
		}
	});

	function formatSectionLabel(section: string): string {
		switch (section) {
			case 'microskills': return $t('teConfig.microskills');
			case 'toolpruning': return $t('teConfig.toolPruning');
			case 'loopguard': return $t('teConfig.loopGuard');
			default: return section;
		}
	}
</script>

<DropdownMenu
	items={[]}
	{anchor}
	{onclose}
	align="end"
	className="w-80 max-w-[calc(100vw-1.5rem)] p-0"
>
	<div class="max-h-[70dvh] overflow-y-auto px-2 py-1 text-xs sm:max-h-[min(72dvh,32.5rem)]">

		<!-- Header -->
		<div class="px-1.5 pb-0.5 pt-1.5 flex items-center gap-2">
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4 text-blue-500 dark:text-blue-400 shrink-0">
				<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.88-7.88L19.3 7.7 10 17z"/>
			</svg>
			<span class="text-[0.6875rem] font-medium text-gray-700 dark:text-gray-300">{$t('teConfig.title')}</span>
		</div>

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
		{:else if configData}
			<!-- Core Toggles Section -->
			<section>
				<div class="px-2 pb-1 pt-1.5 text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600">
					{$t('teConfig.coreToggles')}
				</div>

				<!-- Micro-skills Toggle -->
				<div class="flex h-9 items-center gap-3 rounded-xl px-2 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate" title={$t('teConfig.microskills')}>
						{$t('teConfig.microskills')}
					</span>
					<ToggleSwitch value={microskills_on} onchange={toggleMicroskills} ariaLabel={$t('teConfig.microskills')} />
				</div>

				<!-- Tool Pruning Toggle -->
				<div class="flex h-9 items-center gap-3 rounded-xl px-2 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate" title={$t('teConfig.toolPruning')}>
						{$t('teConfig.toolPruning')}
					</span>
					<ToggleSwitch value={toolpruning_on} onchange={toggleToolPruning} ariaLabel={$t('teConfig.toolPruning')} />
				</div>

				<!-- Loop Guard Toggle -->
				<div class="flex h-9 items-center gap-3 rounded-xl px-2 text-gray-600 dark:text-gray-400">
					<span class="min-w-0 flex-1 truncate" title={$t('teConfig.loopGuard')}>
						{$t('teConfig.loopGuard')}
					</span>
					<ToggleSwitch value={loopguard_on} onchange={toggleLoopGuard} ariaLabel={$t('teConfig.loopGuard')} />
				</div>
			</section>

			<!-- Advanced Expandable Section -->
			<section class="mt-1">
				<button
					class="flex items-center gap-2 w-full h-9 px-2 rounded-xl text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-white/5 hover:text-gray-900 dark:hover:text-white transition-colors duration-75"
					onclick={() => advancedOpen = !advancedOpen}
				>
					<Icon name="chevron-down" size={12} class="shrink-0 transition-transform duration-150 {advancedOpen ? 'rotate-0' : '-rotate-90'}" />
					<span class="flex-1 text-left truncate">{$t('teConfig.advancedSettings')}</span>
				</button>

				{#if advancedOpen}
					<div class="mt-1 space-y-1">
						<!-- Pricing Section Header -->
						<div class="px-2 pb-1 pt-1.5 text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600">
							{$t('teConfig.pricing')}
						</div>

						<!-- max_facts -->
						<div class="flex h-9 items-center gap-3 rounded-xl px-2">
							<span class="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-400">
								{$t('teConfig.maxFacts')}
							</span>
							<input
								type="number"
								value={max_facts}
								onchange={(e) => setAdvanced('max_facts', +e.currentTarget.value)}
								class="w-14 shrink-0 bg-transparent text-xs font-mono text-gray-600 dark:text-gray-400 placeholder:text-gray-300 dark:placeholder:text-gray-600 outline-none border border-gray-200 dark:border-gray-700 rounded px-1.5 h-7 text-center"
								min={1}
							/>
						</div>

						<!-- max_tokens -->
						<div class="flex h-9 items-center gap-3 rounded-xl px-2">
							<span class="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-400">
								{$t('teConfig.maxTokens')}
							</span>
							<input
								type="number"
								value={max_tokens}
								onchange={(e) => setAdvanced('max_tokens', +e.currentTarget.value)}
								class="w-14 shrink-0 bg-transparent text-xs font-mono text-gray-600 dark:text-gray-400 placeholder:text-gray-300 dark:placeholder:text-gray-600 outline-none border border-gray-200 dark:border-gray-700 rounded px-1.5 h-7 text-center"
								min={1}
							/>
						</div>

						<!-- evidence_threshold -->
						<div class="flex h-9 items-center gap-3 rounded-xl px-2">
							<span class="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-400">
								{$t('teConfig.evidenceThreshold')}
							</span>
							<input
								type="number"
								value={evidence_threshold}
								onchange={(e) => setAdvanced('evidence_threshold', +e.currentTarget.value)}
								class="w-14 shrink-0 bg-transparent text-xs font-mono text-gray-600 dark:text-gray-400 placeholder:text-gray-300 dark:placeholder:text-gray-600 outline-none border border-gray-200 dark:border-gray-700 rounded px-1.5 h-7 text-center"
								min={1}
							/>
						</div>

						<!-- min_sessions -->
						<div class="flex h-9 items-center gap-3 rounded-xl px-2">
							<span class="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-400">
								{$t('teConfig.minSessions')}
							</span>
							<input
								type="number"
								value={min_sessions}
								onchange={(e) => setAdvanced('min_sessions', +e.currentTarget.value)}
								class="w-14 shrink-0 bg-transparent text-xs font-mono text-gray-600 dark:text-gray-400 placeholder:text-gray-300 dark:placeholder:text-gray-600 outline-none border border-gray-200 dark:border-gray-700 rounded px-1.5 h-7 text-center"
								min={1}
							/>
						</div>

						<!-- Loop Guard Thresholds Header -->
						<div class="px-2 pb-1 pt-1.5 text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-600">
							{$t('teConfig.loopGuardThresholds')}
						</div>

						<!-- max_envelope_size -->
						<div class="flex h-9 items-center gap-3 rounded-xl px-2">
							<span class="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-400">
								{$t('teConfig.maxEnvelopeSize')}
							</span>
							<input
								type="number"
								value={max_envelope_size}
								onchange={(e) => setLoopGuardThreshold('max_envelope_size', +e.currentTarget.value)}
								class="w-14 shrink-0 bg-transparent text-xs font-mono text-gray-600 dark:text-gray-400 placeholder:text-gray-300 dark:placeholder:text-gray-600 outline-none border border-gray-200 dark:border-gray-700 rounded px-1.5 h-7 text-center"
								min={1}
							/>
						</div>

						<!-- nudge_threshold -->
						<div class="flex h-9 items-center gap-3 rounded-xl px-2">
							<span class="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-400">
								{$t('teConfig.nudgeThreshold')}
							</span>
							<input
								type="number"
								value={nudge_threshold}
								onchange={(e) => setLoopGuardThreshold('nudge_threshold', +e.currentTarget.value)}
								class="w-14 shrink-0 bg-transparent text-xs font-mono text-gray-600 dark:text-gray-400 placeholder:text-gray-300 dark:placeholder:text-gray-600 outline-none border border-gray-200 dark:border-gray-700 rounded px-1.5 h-7 text-center"
								min={1}
							/>
						</div>

						<!-- spiral_level Select -->
						<div class="flex h-9 items-center gap-3 rounded-xl px-2">
							<span class="min-w-0 flex-1 truncate text-xs text-gray-600 dark:text-gray-400">
								{$t('teConfig.spiralLevel')}
							</span>
							<select
								value={spiral_level}
								onchange={(e) => setSpiralLevel(e.currentTarget.value as typeof spiral_level)}
								class="w-auto shrink-0 bg-transparent text-xs font-mono text-gray-600 dark:text-gray-400 outline-none border border-gray-200 dark:border-gray-700 rounded px-1.5 h-7 text-center appearance-none cursor-pointer"
							>
								{#each SPIRAL_OPTIONS as level}
									<option value={level} class="bg-white dark:bg-gray-800">
										{formatSectionLabel(level)}
									</option>
								{/each}
							</select>
						</div>

						<!-- Save feedback -->
						{#if successMsg}
							<div class="flex h-7 items-center gap-2 px-1.5 text-[0.6875rem] text-green-500 dark:text-green-400">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-3.5 h-3.5 shrink-0">
									<path d="M16.972 15.972a.75.75 0 0 1-.53-.218l-4.25-4.25a.75.75 0 0 1 .218-1.218h6.5a.75.75 0 0 1 .75.75v6.5a.75.75 0 0 1-.218.53l-4.25 4.25a.75.75 0 0 1-1.06-.06z"/>
									<path d="M10.5 1.75a.75.75 0 0 0-1.5 0v8.75L5.22 9.47a.75.75 0 0 0-1.06 1.06l5.5 5.5a.75.75 0 0 0 1.06 0l5.5-5.5a.75.75 0 0 0-1.06-1.06L10.5 10.5V1.75Z"/>
								</svg>
								<span>{$successMsg}</span>
							</div>
						{/if}
					</div>
				{/if}
			</section>

			<!-- Empty State -->
			{#if !loading && !error && !configData}
				<div class="px-1.5 py-1.5 text-[0.6875rem] leading-relaxed text-gray-400 dark:text-gray-600">
					{@html $t('chat.teStatusNoData')}
				</div>
			{/if}
		{/if}
	</div>
</DropdownMenu>

<style>
	@reference "../../../app.css";

	select {
		background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M4 6l4 4 4-4'/%3e%3c/svg%3e");
		background-position: right 4px center;
		background-repeat: no-repeat;
		background-size: 12px 12px;
		padding-right: 20px;
	}

	input[type='number'] {
		-moz-appearance: textfield;
	}

	input[type='number']::-webkit-outer-spin-button,
	input[type='number']::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}
</style>

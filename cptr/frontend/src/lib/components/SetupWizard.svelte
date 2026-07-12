<script lang="ts">
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';

	import { createConnection } from '$lib/apis/admin';
	import { refreshChatState } from '$lib/stores/chat';
	import { formatChord, keybindings } from '$lib/stores/keybindings';
	import { t } from '$lib/i18n';
	import { ApiError } from '$lib/apis';
	import DirectoryPicker from './DirectoryPicker.svelte';
	import Spinner from './common/Spinner.svelte';

	interface Props {
		oncomplete: () => void;
	}

	let { oncomplete }: Props = $props();

	let step = $state(0);
	const totalSteps = 4;

	// ── Step 2: Folder ──────────────────────────────────────────
	let selectedPath = $state('');
	let showPicker = $state(false);

	// ── Step 3: AI connection ───────────────────────────────────
	let provider = $state<'openai' | 'anthropic'>('openai');
	let apiType = $state<'chat_completions' | 'responses'>('chat_completions');
	let baseUrl = $state('https://api.openai.com/v1');
	let apiKey = $state('');
	let connecting = $state(false);
	let aiConnected = $state(false);

	const providerConfig = {
		openai: { name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', placeholder: 'sk-...' },
		anthropic: {
			name: 'Anthropic',
			baseUrl: 'https://api.anthropic.com/v1',
			placeholder: 'sk-ant-...'
		}
	};

	const config = $derived(providerConfig[provider]);

	// Auto-fill base URL when provider changes
	$effect(() => {
		baseUrl = providerConfig[provider].baseUrl;
	});

	function next() {
		if (step < totalSteps - 1) step++;
	}

	function skipFolder() {
		next();
	}

	async function connectAi() {
		if (!apiKey.trim()) return;
		connecting = true;
		try {
			await createConnection({
				name: config.name,
				provider,
				api_type: provider === 'openai' ? apiType : 'chat_completions',
				base_url: baseUrl.trim(),
				api_key: apiKey.trim()
			});
			await refreshChatState();
			aiConnected = true;
			next();
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : $t('auth.connectionFailed'));
		} finally {
			connecting = false;
		}
	}

	function skipAi() {
		next();
	}

	async function finish() {
		oncomplete();

		if (selectedPath) {
			await goto(`/?workspace=${encodeURIComponent(selectedPath)}`);
		}
	}

	let searchShortcut = $derived(formatChord($keybindings.quickOpen));
</script>

<div
	class="app-theme flex items-center justify-center h-dvh bg-white dark:bg-black p-6"
	style="background: var(--app-bg); color: var(--app-fg);"
>
	<div class="w-full max-w-md">
		<!-- Progress dots -->
		<div class="flex gap-1.5 mb-6">
			{#each Array(totalSteps) as _, i}
				<div
					class="h-0.5 flex-1 rounded-full transition-colors duration-200
						{i <= step ? 'bg-gray-900 dark:bg-white' : 'bg-gray-200 dark:bg-white/8'}"
				></div>
			{/each}
		</div>

		{#if step === 0}
			<!-- Welcome -->
			<div class="animate-in">
				<h1 class="text-lg tracking-tight text-gray-900 dark:text-white mb-1">
					{$t('onboarding.welcomeTitle')}
				</h1>
				<p class="text-[0.8125rem] text-gray-500 dark:text-gray-500 mb-6 leading-relaxed">
					{$t('onboarding.welcomeDesc')}
				</p>

				<button
					class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
					onclick={next}
				>
					{$t('onboarding.getStarted')}
				</button>
			</div>
		{:else if step === 1}
			<!-- Open folder -->
			<div class="animate-in">
				<h2 class="text-xs text-gray-400 dark:text-gray-600 mb-1">
					{$t('onboarding.openFolder')}
				</h2>
				<p class="text-[0.8125rem] text-gray-500 dark:text-gray-500 mb-4 leading-relaxed">
					{$t('onboarding.openFolderDesc')}
				</p>

				{#if selectedPath}
					<p class="text-[0.75rem] font-mono text-gray-700 dark:text-gray-300 mb-3">
						{selectedPath}
					</p>
				{/if}

				<button
					class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
					onclick={() => (showPicker = true)}
				>
					{$t('onboarding.openFolder')}
				</button>

				<div class="mt-4">
					<button
						class="text-[0.6875rem] text-gray-400 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 transition-colors duration-100"
						onclick={skipFolder}
					>
						{$t('onboarding.skip')}
					</button>
				</div>
			</div>
		{:else if step === 2}
			<!-- Connect AI -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="animate-in"
				onkeydown={(e) => {
					if (e.key === 'Enter' && apiKey.trim()) connectAi();
				}}
			>
				<h2 class="text-xs text-gray-400 dark:text-gray-600 mb-1">
					{$t('onboarding.connectAi')}
				</h2>
				<p class="text-[0.8125rem] text-gray-500 dark:text-gray-500 mb-4 leading-relaxed">
					{$t('onboarding.connectAiDesc')}
				</p>

				{#if aiConnected}
					<p class="text-[0.8125rem] text-gray-700 dark:text-gray-300 mb-4">
						{$t('onboarding.connected', { name: config.name })}
					</p>
					<button
						class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
						onclick={next}
					>
						{$t('onboarding.next')}
					</button>
				{:else}
					<div class="mb-3">
						<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mb-0.5">
							{$t('onboarding.provider')}
						</p>
						<select
							bind:value={provider}
							class="bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-0.5 border-none cursor-pointer"
						>
							<option value="openai">OpenAI</option>
							<option value="anthropic">Anthropic</option>
						</select>
					</div>

					{#if provider === 'openai'}
						<div class="mb-3">
							<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mb-0.5">
								{$t('onboarding.apiType')}
							</p>
							<select
								bind:value={apiType}
								class="bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-0.5 border-none cursor-pointer"
							>
								<option value="chat_completions">{$t('connections.chatCompletions')}</option>
								<option value="responses">{$t('connections.responses')}</option>
							</select>
						</div>
					{/if}

					<div class="mb-3">
						<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mb-0.5">
							{$t('connections.baseUrl')}
						</p>
						<input
							type="text"
							placeholder="https://api.openai.com/v1"
							bind:value={baseUrl}
							autocomplete="off"
							spellcheck="false"
							list="setup-base-url-suggestions"
							class="block w-full bg-transparent text-[0.8125rem] font-mono text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
						/>
						<datalist id="setup-base-url-suggestions">
							<option value="https://api.openai.com/v1" />
							<option value="https://api.anthropic.com/v1" />
							<option value="https://openrouter.ai/api/v1" />
							<option value="http://localhost:11434/v1" />
						</datalist>
					</div>

					<div class="mb-2">
						<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mb-0.5">
							{$t('connections.apiKey')}
						</p>
						<input
							type="password"
							placeholder={config.placeholder}
							bind:value={apiKey}
							autocomplete="new-password"
							class="block w-full bg-transparent text-[0.8125rem] font-mono text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-1"
						/>
					</div>

					<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mb-4">
						{$t('onboarding.keyStaysLocal')}
					</p>

					<button
						class="flex items-center gap-2 text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100
							disabled:opacity-30 disabled:pointer-events-none"
						onclick={connectAi}
						disabled={connecting || !apiKey.trim()}
					>
						{#if connecting}
							<Spinner size={14} />
						{:else}
							{$t('onboarding.connect')}
						{/if}
					</button>

					<div class="mt-4">
						<button
							class="text-[0.6875rem] text-gray-400 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400 transition-colors duration-100"
							onclick={skipAi}
						>
							{$t('onboarding.connectAiSkip')}
						</button>
					</div>
				{/if}
			</div>
		{:else if step === 3}
			<!-- Ready -->
			<div class="animate-in">
				<h2 class="text-xs text-gray-400 dark:text-gray-600 mb-1">
					{$t('onboarding.ready')}
				</h2>
				<p class="text-[0.8125rem] text-gray-500 dark:text-gray-500 mb-5 leading-relaxed">
					{$t('onboarding.readyDesc')}
				</p>

				<div class="flex flex-col gap-1.5 mb-6">
					<p class="text-[0.75rem] text-gray-500 dark:text-gray-500">
						{$t('onboarding.tipSearch', { shortcut: searchShortcut })}
					</p>
					<p class="text-[0.75rem] text-gray-500 dark:text-gray-500">
						{$t('onboarding.tipTerminal')}
					</p>
					<p class="text-[0.75rem] text-gray-500 dark:text-gray-500">
						{$t('onboarding.tipMobile')}
					</p>
				</div>

				<button
					class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100"
					onclick={finish}
				>
					{$t('onboarding.startUsing')}
				</button>
			</div>
		{/if}
	</div>
</div>

{#if showPicker}
	<DirectoryPicker
		onclose={() => {
			showPicker = false;
			const params = new URLSearchParams(window.location.search);
			const wsPath = params.get('workspace');
			if (wsPath) {
				selectedPath = wsPath;
				const url = new URL(window.location.href);
				url.searchParams.delete('workspace');
				window.history.replaceState({}, '', url.toString());
				next();
			}
		}}
	/>
{/if}

<style>
	.animate-in {
		animation: fadeIn 0.15s ease-out;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(0.25rem);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>

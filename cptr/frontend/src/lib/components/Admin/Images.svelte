<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import ToggleSwitch from '../common/ToggleSwitch.svelte';
	import Spinner from '../common/Spinner.svelte';
	import { getAdminConfig, updateConfig } from '$lib/apis/admin';
	import { t } from '$lib/i18n';

	let loading = $state(true);
	let saving = $state(false);

	let generationEnabled = $state(false);
	let generationBaseUrl = $state('https://api.openai.com/v1');
	let generationApiKey = $state('');
	let generationModel = $state('gpt-image-1');
	let generationSize = $state('');
	let hasGenerationKey = $state(false);

	let editEnabled = $state(false);
	let editBaseUrl = $state('https://api.openai.com/v1');
	let editApiKey = $state('');
	let editModel = $state('gpt-image-1');
	let editSize = $state('');
	let hasEditKey = $state(false);

	onMount(async () => {
		try {
			const config = await getAdminConfig();
			generationEnabled = config['images.generation_enabled'] === true;
			generationBaseUrl =
				(config['images.generation_base_url'] as string) || 'https://api.openai.com/v1';
			generationModel = (config['images.generation_model'] as string) || 'gpt-image-1';
			generationSize = (config['images.generation_size'] as string) || '';
			hasGenerationKey = !!config['images.generation_api_key'];

			editEnabled = config['images.edit_enabled'] === true;
			editBaseUrl = (config['images.edit_base_url'] as string) || 'https://api.openai.com/v1';
			editModel = (config['images.edit_model'] as string) || 'gpt-image-1';
			editSize = (config['images.edit_size'] as string) || '';
			hasEditKey = !!config['images.edit_api_key'];
		} catch {}
		loading = false;
	});

	async function save() {
		saving = true;
		try {
			const cfg: Record<string, unknown> = {
				'images.generation_enabled': generationEnabled,
				'images.generation_base_url': generationBaseUrl,
				'images.generation_model': generationModel,
				'images.generation_size': generationSize,
				'images.edit_enabled': editEnabled,
				'images.edit_base_url': editBaseUrl,
				'images.edit_model': editModel,
				'images.edit_size': editSize
			};
			if (generationApiKey) {
				cfg['images.generation_api_key'] = generationApiKey;
			}
			if (editApiKey) {
				cfg['images.edit_api_key'] = editApiKey;
			}
			await updateConfig(cfg);
			if (generationApiKey) hasGenerationKey = true;
			if (editApiKey) hasEditKey = true;
			generationApiKey = '';
			editApiKey = '';
			toast.success($t('settings.saved'));
		} catch {
			toast.error($t('admin.images.saveFailed'));
		} finally {
			saving = false;
		}
	}
</script>

<div class="flex flex-col h-full">
	{#if loading}
		<div class="flex justify-center py-8"><Spinner size={16} /></div>
	{:else}
		<div class="flex-1 min-h-0 overflow-y-auto">
			<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">
				{$t('admin.images.title')}
			</h2>

			<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2">
				{$t('admin.images.generation')}
			</h3>
			<div class="flex flex-col gap-2.5">
				<label class="flex items-center justify-between cursor-pointer">
					<span class="text-xs text-gray-600 dark:text-gray-400"
						>{$t('admin.images.enableGeneration')}</span
					>
					<ToggleSwitch
						value={generationEnabled}
						onchange={(v) => {
							generationEnabled = v;
						}}
					/>
				</label>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{$t('admin.images.generationHint')}
				</p>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-generation-base-url"
						>{$t('connections.baseUrl')}</label
					>
					<input
						id="image-generation-base-url"
						type="text"
						bind:value={generationBaseUrl}
						placeholder="https://api.openai.com/v1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-generation-api-key"
						>{$t('connections.apiKey')}</label
					>
					<input
						id="image-generation-api-key"
						type="password"
						bind:value={generationApiKey}
						placeholder={hasGenerationKey ? '••••••••' : 'sk-...'}
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-generation-model"
						>{$t('automations.model')}</label
					>
					<input
						id="image-generation-model"
						type="text"
						bind:value={generationModel}
						placeholder="gpt-image-1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-generation-size"
						>{$t('admin.images.size')}</label
					>
					<input
						id="image-generation-size"
						type="text"
						bind:value={generationSize}
						placeholder="1024x1024"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
			</div>

			<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">
				{$t('admin.images.editing')}
			</h3>
			<div class="flex flex-col gap-2.5">
				<label class="flex items-center justify-between cursor-pointer">
					<span class="text-xs text-gray-600 dark:text-gray-400"
						>{$t('admin.images.enableEditing')}</span
					>
					<ToggleSwitch
						value={editEnabled}
						onchange={(v) => {
							editEnabled = v;
						}}
					/>
				</label>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
					{$t('admin.images.editHint')}
				</p>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-edit-base-url"
						>{$t('connections.baseUrl')}</label
					>
					<input
						id="image-edit-base-url"
						type="text"
						bind:value={editBaseUrl}
						placeholder="https://api.openai.com/v1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-edit-api-key"
						>{$t('connections.apiKey')}</label
					>
					<input
						id="image-edit-api-key"
						type="password"
						bind:value={editApiKey}
						placeholder={hasEditKey ? '••••••••' : $t('admin.images.editKeyPlaceholder')}
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-edit-model"
						>{$t('automations.model')}</label
					>
					<input
						id="image-edit-model"
						type="text"
						bind:value={editModel}
						placeholder="gpt-image-1"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="image-edit-size"
						>{$t('admin.images.size')}</label
					>
					<input
						id="image-edit-size"
						type="text"
						bind:value={editSize}
						placeholder="1024x1024"
						class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
				</div>
			</div>
		</div>

		<!-- Save -->
		<div class="shrink-0 pt-3 flex justify-end">
			<button
				class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100 disabled:opacity-50"
				onclick={() => save()}
				disabled={saving}
			>
				{#if saving}{$t('settings.saving')}{:else}{$t('settings.save')}{/if}
			</button>
		</div>
	{/if}
</div>

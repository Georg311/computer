<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getAdminConfig, updateConfig } from '$lib/apis/admin';
	import { t } from '$lib/i18n';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const DEFAULT_SCROLLBACK_KB = 64;

	let loading = $state(true);
	let saving = $state(false);
	let scrollbackKb = $state(DEFAULT_SCROLLBACK_KB);

	onMount(async () => {
		try {
			const config = await getAdminConfig();
			scrollbackKb = Number(config['terminal.scrollback_kb']) || DEFAULT_SCROLLBACK_KB;
		} catch {
			toast.error($t('admin.failedToLoadConfig'));
		} finally {
			loading = false;
		}
	});

	async function save() {
		saving = true;
		try {
			await updateConfig({
				'terminal.scrollback_kb': Math.max(1, Number(scrollbackKb) || DEFAULT_SCROLLBACK_KB)
			});
			toast.success($t('settings.saved'));
		} catch {
			toast.error($t('admin.failedToSave'));
		} finally {
			saving = false;
		}
	}
</script>

<div class="flex flex-col min-h-full">
	<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">{$t('admin.terminal')}</h2>

	{#if loading}
		<div class="flex justify-center py-8"><Spinner size={16} /></div>
	{:else}
		<div class="flex flex-col gap-2.5">
			<div>
				<label class="text-xs text-gray-600 dark:text-gray-400" for="terminal-scrollback-kb">
					{$t('admin.terminalScrollback')}
				</label>
				<div class="flex items-center gap-1.5 mt-1">
					<input
						id="terminal-scrollback-kb"
						type="number"
						bind:value={scrollbackKb}
						min="1"
						max="1024"
						step="1"
						class="w-24 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
					/>
					<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600">KB</span>
				</div>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mt-0.5">
					{$t('admin.terminalScrollbackHint')}
				</p>
			</div>
		</div>

		<div class="mt-auto pt-6 flex justify-end">
			<button
				class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100 disabled:opacity-50"
				onclick={save}
				disabled={saving}>{$t('settings.save')}</button
			>
		</div>
	{/if}
</div>

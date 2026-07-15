<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getAdminConfig, updateConfig } from '$lib/apis/admin';
	import { t } from '$lib/i18n';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ToggleSwitch from '$lib/components/common/ToggleSwitch.svelte';

	let loading = $state(true);
	let saving = $state(false);
	let autoGitignoreDotCptr = $state(true);

	onMount(async () => {
		try {
			const config = await getAdminConfig();
			autoGitignoreDotCptr = config['workspace.auto_gitignore_dot_cptr'] !== false;
		} catch {
			toast.error($t('admin.failedToLoadConfig'));
		} finally {
			loading = false;
		}
	});

	async function save() {
		saving = true;
		try {
			await updateConfig({ 'workspace.auto_gitignore_dot_cptr': autoGitignoreDotCptr });
			toast.success($t('settings.saved'));
		} catch {
			toast.error($t('admin.failedToSave'));
		} finally {
			saving = false;
		}
	}
</script>

<div class="flex flex-col min-h-full">
	<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">{$t('admin.workspace')}</h2>

	{#if loading}
		<div class="flex justify-center py-8"><Spinner size={16} /></div>
	{:else}
		<div class="flex flex-col gap-2.5">
			<label class="flex items-center justify-between cursor-pointer">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>{$t('admin.workspaceAutoGitignoreDotCptr')}</span
				>
				<ToggleSwitch
					value={autoGitignoreDotCptr}
					onchange={(value) => {
						autoGitignoreDotCptr = value;
					}}
					disabled={saving}
				/>
			</label>
			<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
				{$t('admin.workspaceAutoGitignoreDotCptrHint')}
			</p>
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

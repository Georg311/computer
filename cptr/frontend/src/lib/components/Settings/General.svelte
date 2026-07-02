<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { streamingBehavior, showUpdateToastPref } from '$lib/stores';
	import type { StreamingBehavior } from '$lib/stores';
	import { t, locale, changeLocale, supportedLocales } from '$lib/i18n';
	import { notificationsEnabled, notificationSound } from '$lib/stores/chat';
	import { fetchJSON } from '$lib/apis';
	import { updateConfig } from '$lib/apis/admin';
	import { session } from '$lib/session';
	import ToggleSwitch from '../common/ToggleSwitch.svelte';
	import { onMount } from 'svelte';

	// ── Webhook URL ─────────────────────────────────────────────
	let webhookUrl = $state('');
	let webhookUrlOriginal = $state('');
	let saving = $state(false);

	let dirty = $derived(webhookUrl.trim() !== webhookUrlOriginal);

	onMount(async () => {
		try {
			const data = await fetchJSON<{ config: Record<string, any> }>(
				'/api/admin/config/notifications'
			);
			const url = data.config?.['notifications.webhook_url'] || '';
			webhookUrl = url;
			webhookUrlOriginal = url;
		} catch {}
	});

	async function save() {
		saving = true;
		try {
			await updateConfig({ 'notifications.webhook_url': webhookUrl.trim() || null });
			webhookUrlOriginal = webhookUrl.trim();
			toast.success($t('settings.saved'));
		} catch {
			toast.error($t('general.webhookUrlSaveFailed'));
		} finally {
			saving = false;
		}
	}

	async function toggleNotifications() {
		if (!$notificationsEnabled) {
			if ('Notification' in window) {
				const permission = await Notification.requestPermission();
				if (permission === 'granted') {
					notificationsEnabled.set(true);
				} else {
					toast.error($t('general.notificationPermissionDenied'));
				}
			}
		} else {
			notificationsEnabled.set(false);
		}
	}
</script>

<div class="flex flex-col h-full">
	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5 -mr-1.5">
		<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">{$t('general.title')}</h2>

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2">{$t('general.language')}</h3>
		<select
			class="w-full max-w-[12.5rem] bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-1 cursor-pointer"
			value={$locale}
			onchange={(e) => changeLocale((e.currentTarget as HTMLSelectElement).value)}
		>
			{#each supportedLocales as loc}
				<option value={loc.code}>{loc.label}</option>
			{/each}
		</select>

		<!-- Notifications -->
		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">
			{$t('general.notifications')}
		</h3>

		<div class="flex flex-col gap-2.5">
			<!-- Browser notifications toggle -->
			<label class="flex items-center justify-between cursor-pointer">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>{$t('general.browserNotifications')}</span
				>
				<ToggleSwitch value={$notificationsEnabled} onchange={() => toggleNotifications()} />
			</label>
			<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
				{$t('general.browserNotificationsDesc')}
			</p>

			<!-- Sound toggle -->
			<label class="flex items-center justify-between cursor-pointer">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>{$t('general.notificationSound')}</span
				>
				<ToggleSwitch value={$notificationSound} onchange={(v) => notificationSound.set(v)} />
			</label>

			<!-- Webhook URL -->
			<div class="mt-1">
				<label class="text-xs text-gray-600 dark:text-gray-400" for="webhook-url">
					{$t('general.webhookUrl')}
				</label>
				<input
					id="webhook-url"
					type="url"
					bind:value={webhookUrl}
					placeholder="https://hooks.slack.com/services/..."
					class="w-full mt-1 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
				/>
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mt-1">
					{$t('general.webhookUrlHint')}
				</p>
			</div>
		</div>

		{#if $session?.role === 'admin'}
			<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{$t('general.updates')}</h3>
			<label class="flex items-center justify-between cursor-pointer">
				<span class="text-xs text-gray-600 dark:text-gray-400"
					>{$t('general.updateNotifications')}</span
				>
				<ToggleSwitch value={$showUpdateToastPref} onchange={(v) => showUpdateToastPref.set(v)} />
			</label>
			<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mt-1">
				{$t('general.updateNotificationsDesc')}
			</p>
		{/if}

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{$t('general.messageQueue')}</h3>
		<div class="flex gap-1">
			{#each [{ value: 'queue' as StreamingBehavior, label: $t('general.queue') }, { value: 'interrupt' as StreamingBehavior, label: $t('general.interrupt') }] as opt}
				<button
					class="flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-xs transition-colors duration-100
					{$streamingBehavior === opt.value
						? 'bg-gray-200/50 dark:bg-white/8 text-gray-900 dark:text-white font-medium'
						: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
					onclick={() => streamingBehavior.set(opt.value)}
				>
					{opt.label}
				</button>
			{/each}
		</div>
		<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 mt-1">
			{$streamingBehavior === 'queue' ? $t('general.queueDesc') : $t('general.interruptDesc')}
		</p>
	</div>

	<div class="shrink-0 pt-3 flex justify-end">
		<button
			class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100
			disabled:opacity-30 disabled:pointer-events-none"
			onclick={save}
			disabled={saving}
		>
			{#if saving}{$t('settings.saving')}{:else}{$t('settings.save')}{/if}
		</button>
	</div>
</div>

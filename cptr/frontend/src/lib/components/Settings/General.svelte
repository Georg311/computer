<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Icon from '../Icon.svelte';
	import { theme, streamingBehavior, showUpdateToastPref, textScale } from '$lib/stores';
	import type { Theme, StreamingBehavior } from '$lib/stores';
	import { t, locale, changeLocale, supportedLocales } from '$lib/i18n';
	import { notificationsEnabled, notificationSound } from '$lib/stores/chat';
	import { fetchJSON } from '$lib/apis';
	import { updateConfig } from '$lib/apis/admin';
	import { session } from '$lib/session';
	import ToggleSwitch from '../common/ToggleSwitch.svelte';
	import { onMount } from 'svelte';

	function setTheme(v: Theme) {
		theme.set(v);
	}

	// ── Webhook URL ─────────────────────────────────────────────
	let webhookUrl = $state('');
	let webhookUrlOriginal = $state('');
	let saving = $state(false);
	let scaleEnabled = $state(false);
	let scaleDraft = $state(1);
	const minTextScale = 1;
	const maxTextScale = 1.5;

	let dirty = $derived(webhookUrl.trim() !== webhookUrlOriginal);

	$effect(() => {
		if ($textScale !== null) {
			scaleEnabled = true;
			scaleDraft = $textScale;
		}
	});

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

	function toggleTextScale() {
		if (scaleEnabled) {
			scaleEnabled = false;
			scaleDraft = 1;
			textScale.set(null);
		} else {
			scaleEnabled = true;
			scaleDraft = $textScale ?? 1;
		}
	}

	function normalizeTextScale(scale: number | string) {
		const value = Number(scale);
		if (!Number.isFinite(value)) return minTextScale;
		return Math.max(minTextScale, Math.min(maxTextScale, Number(value.toFixed(2))));
	}

	function scaleLabel(scale: number) {
		return `${scale.toFixed(scale % 1 === 0 ? 0 : 2)}x`;
	}

	function setTextScalePreference(scale: number | string) {
		const next = normalizeTextScale(scale);
		scaleDraft = next;
		if (next === minTextScale) {
			scaleEnabled = false;
			textScale.set(null);
		} else {
			scaleEnabled = true;
			textScale.set(next);
		}
	}
</script>

<div class="flex flex-col h-full">
	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5 -mr-1.5">
		<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">{$t('general.title')}</h2>

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2">{$t('general.theme')}</h3>
		<div class="flex gap-1">
			{#each [{ value: 'light' as Theme, label: $t('general.light'), icon: 'sun-light' }, { value: 'dark' as Theme, label: $t('general.dark'), icon: 'half-moon' }, { value: 'system' as Theme, label: $t('general.system'), icon: 'monitor' }] as opt}
				<button
					class="flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-xs transition-colors duration-100
					{$theme === opt.value
						? 'bg-gray-200/50 dark:bg-white/8 text-gray-900 dark:text-white font-medium'
						: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
					onclick={() => setTheme(opt.value)}
				>
					<Icon name={opt.icon} size={13} />
					{opt.label}
				</button>
			{/each}
		</div>

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{$t('general.language')}</h3>
		<select
			class="w-full max-w-[12.5rem] bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-1 cursor-pointer"
			value={$locale}
			onchange={(e) => changeLocale((e.currentTarget as HTMLSelectElement).value)}
		>
			{#each supportedLocales as loc}
				<option value={loc.code}>{loc.label}</option>
			{/each}
		</select>

		<h3 class="text-xs text-gray-400 dark:text-gray-600 mb-2 mt-5">{$t('general.uiScale')}</h3>
		<div class="w-full">
			<div class="flex items-center gap-2">
				<span id="ui-scale-label" class="text-xs text-gray-600 dark:text-gray-400">
					{$t('general.uiScale')}
				</span>
				<button
					type="button"
					class="ml-auto h-6 px-2 rounded-lg text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/6 transition-colors"
					aria-live="polite"
					onclick={toggleTextScale}
				>
					{scaleEnabled ? scaleLabel(scaleDraft) : $t('general.default')}
				</button>
			</div>

			{#if scaleEnabled}
				<div class="flex items-center gap-1.5 pt-1.5">
					<button
						type="button"
						class="flex items-center justify-center w-6 h-6 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/6 transition-colors"
						aria-labelledby="ui-scale-label"
						aria-label={$t('general.decreaseUiScale')}
						onclick={() => setTextScalePreference(scaleDraft - 0.1)}
					>
						<Icon name="minus" size={12} />
					</button>
					<input
						id="ui-scale-slider"
						class="ui-scale-range flex-1 min-w-0"
						type="range"
						min={minTextScale}
						max={maxTextScale}
						step="0.01"
						bind:value={scaleDraft}
						aria-labelledby="ui-scale-label"
						aria-valuemin={minTextScale}
						aria-valuemax={maxTextScale}
						aria-valuenow={scaleDraft}
						aria-valuetext={scaleLabel(scaleDraft)}
						oninput={() => setTextScalePreference(scaleDraft)}
					/>
					<button
						type="button"
						class="flex items-center justify-center w-6 h-6 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/6 transition-colors"
						aria-labelledby="ui-scale-label"
						aria-label={$t('general.increaseUiScale')}
						onclick={() => setTextScalePreference(scaleDraft + 0.1)}
					>
						<Icon name="plus" size={12} />
					</button>
				</div>
			{/if}
		</div>

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

<style>
	.ui-scale-range {
		appearance: none;
		height: 1rem;
		background: transparent;
		cursor: pointer;
	}

	.ui-scale-range::-webkit-slider-runnable-track {
		height: 0.125rem;
		border-radius: 624.9375rem;
		background: rgb(209 213 219 / 0.7);
	}

	.ui-scale-range::-webkit-slider-thumb {
		appearance: none;
		width: 0.75rem;
		height: 0.75rem;
		margin-top: -0.3125rem;
		border-radius: 624.9375rem;
		border: 1px solid rgb(156 163 175 / 0.45);
		background: rgb(255 255 255);
	}

	.ui-scale-range::-moz-range-track {
		height: 0.125rem;
		border-radius: 624.9375rem;
		background: rgb(209 213 219 / 0.7);
	}

	.ui-scale-range::-moz-range-thumb {
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 624.9375rem;
		border: 1px solid rgb(156 163 175 / 0.45);
		background: rgb(255 255 255);
	}

	:global(.dark) .ui-scale-range::-webkit-slider-runnable-track,
	:global(.dark) .ui-scale-range::-moz-range-track {
		background: rgb(255 255 255 / 0.12);
	}

	:global(.dark) .ui-scale-range::-webkit-slider-thumb,
	:global(.dark) .ui-scale-range::-moz-range-thumb {
		border-color: rgb(255 255 255 / 0.18);
		background: rgb(229 231 235);
	}
</style>

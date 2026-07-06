<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { t } from '$lib/i18n';
	import { notificationsEnabled, notificationSound } from '$lib/stores/chat';
	import {
		createNotificationTarget,
		CHAT_NOTIFICATION_EVENTS,
		deleteNotificationTarget,
		listNotificationBotOptions,
		listNotificationTargets,
		testNotificationTarget,
		updateNotificationTarget,
		type BotOption,
		type ChatNotificationEvent,
		type NotificationDelivery,
		type NotificationTarget,
		type NotificationTargetType
	} from '$lib/apis/notifications';
	import Icon from '../Icon.svelte';
	import Modal from '../Modal.svelte';
	import ToggleSwitch from '../common/ToggleSwitch.svelte';

	const eventOptions: { value: ChatNotificationEvent; label: string }[] = [
		{ value: CHAT_NOTIFICATION_EVENTS.FINISHED, label: 'general.chatFinished' },
		{ value: CHAT_NOTIFICATION_EVENTS.FAILED, label: 'general.chatFailed' }
	];

	let targets = $state<NotificationTarget[]>([]);
	let botOptions = $state<BotOption[]>([]);
	let loadingTargets = $state(false);
	let savingTarget = $state(false);
	let editingId = $state<string | null>(null);
	let formOpen = $state(false);
	let form = $state({
		id: '',
		type: 'webhook' as NotificationTargetType,
		url: '',
		bot_id: '',
		destination_chat_id: '',
		enabled: true,
		events: [] as ChatNotificationEvent[],
		delivery: 'away' as NotificationDelivery
	});
	let targetTypes = $derived<NotificationTargetType[]>(
		botOptions.length ? ['webhook', 'bot'] : ['webhook']
	);

	onMount(() => {
		void loadNotificationTargets();
	});

	async function loadNotificationTargets() {
		loadingTargets = true;
		try {
			const [nextTargets, bots] = await Promise.all([
				listNotificationTargets(),
				listNotificationBotOptions()
			]);
			targets = nextTargets;
			botOptions = bots;
		} catch {
			toast.error($t('general.notificationTargetsLoadFailed'));
		} finally {
			loadingTargets = false;
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

	function openNewTarget(type: NotificationTargetType = 'webhook') {
		if (type === 'bot' && !botOptions.length) type = 'webhook';
		editingId = null;
		formOpen = true;
		form = {
			id: '',
			type,
			url: '',
			bot_id: botOptions[0]?.id || '',
			destination_chat_id: '',
			enabled: true,
			events: [],
			delivery: 'away'
		};
	}

	function openEditTarget(target: NotificationTarget) {
		editingId = target.id;
		formOpen = true;
		form = {
			id: target.id,
			type: target.type,
			url: '',
			bot_id: target.config.bot_id || botOptions[0]?.id || '',
			destination_chat_id: target.config.destination_chat_id || '',
			enabled: target.enabled,
			events: [...target.events],
			delivery: target.delivery
		};
	}

	function toggleFormEvent(event: ChatNotificationEvent) {
		form.events = form.events.includes(event)
			? form.events.filter((item) => item !== event)
			: [...form.events, event];
	}

	async function saveTarget() {
		savingTarget = true;
		try {
			const originalId = editingId;
			const payload: any = {
				id: form.id.trim(),
				type: form.type,
				enabled: form.enabled,
				events: form.events,
				delivery: form.delivery
			};
			if (form.type === 'webhook') {
				if (!editingId || form.url.trim()) payload.config = { url: form.url.trim() };
			} else {
				payload.config = {
					bot_id: form.bot_id,
					destination_chat_id: form.destination_chat_id.trim()
				};
			}
			const saved = originalId
				? await updateNotificationTarget(originalId, payload)
				: await createNotificationTarget(payload);
			targets = originalId
				? targets.map((target) => (target.id === originalId ? saved : target))
				: [...targets, saved];
			formOpen = false;
			toast.success($t('settings.saved'));
		} catch (error) {
			toast.error(error instanceof Error ? error.message : $t('general.notificationTargetSaveFailed'));
		} finally {
			savingTarget = false;
		}
	}

	async function patchTarget(target: NotificationTarget, patch: Partial<NotificationTarget>) {
		try {
			const saved = await updateNotificationTarget(target.id, patch as any);
			targets = targets.map((item) => (item.id === saved.id ? saved : item));
		} catch (error) {
			toast.error(error instanceof Error ? error.message : $t('general.notificationTargetSaveFailed'));
		}
	}

	async function removeTarget(target: NotificationTarget) {
		try {
			await deleteNotificationTarget(target.id);
			targets = targets.filter((item) => item.id !== target.id);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : $t('general.notificationTargetSaveFailed'));
		}
	}

	async function sendTest(target: NotificationTarget) {
		try {
			await testNotificationTarget(target.id);
			toast.success($t('general.testSent'));
		} catch (error) {
			toast.error(error instanceof Error ? error.message : $t('general.notificationTargetSaveFailed'));
		}
	}
</script>

<div class="flex flex-col h-full">
	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5 -mr-1.5">
		<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">
			{$t('general.notifications')}
		</h2>

		<div class="flex flex-col gap-2.5">
			<label class="flex items-center justify-between cursor-pointer">
				<span class="text-xs text-gray-600 dark:text-gray-400">
					{$t('general.browserNotifications')}
				</span>
				<ToggleSwitch value={$notificationsEnabled} onchange={() => toggleNotifications()} />
			</label>
			<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
				{$t('general.browserNotificationsDesc')}
			</p>

			<label class="flex items-center justify-between cursor-pointer">
				<span class="text-xs text-gray-600 dark:text-gray-400">
					{$t('general.notificationSound')}
				</span>
				<ToggleSwitch value={$notificationSound} onchange={(v) => notificationSound.set(v)} />
			</label>

			<div class="mt-3 flex items-center justify-between">
				<span class="text-xs font-medium text-gray-700 dark:text-gray-300">
					{$t('general.notificationTargets')}
				</span>
				<button
					class="flex items-center justify-center w-6 h-6 rounded-lg text-gray-400 hover:text-gray-700 dark:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
					onclick={() => openNewTarget()}
					title={$t('general.addNotificationTarget')}
					aria-label={$t('general.addNotificationTarget')}
				>
					<Icon name="plus" size={14} />
				</button>
			</div>

			{#if loadingTargets}
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">{$t('common.loading')}</p>
			{:else if !targets.length}
				<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">
					{$t('general.noNotificationTargets')}
				</p>
			{:else}
				<div class="flex flex-col gap-2">
					{#each targets as target}
						<div class="rounded-lg border border-gray-200 dark:border-white/8 p-2">
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0">
									<div class="flex items-center gap-2">
										<span class="truncate text-xs font-medium text-gray-800 dark:text-gray-200">
											{target.id}
										</span>
										<span class="text-[0.625rem] uppercase text-gray-400 dark:text-gray-600">
											{target.type === 'webhook' ? $t('general.webhook') : $t('general.bot')}
										</span>
									</div>
									<p class="truncate text-[0.6875rem] text-gray-400 dark:text-gray-600">
										{target.type === 'webhook'
											? target.config.url_masked
											: target.config.destination_chat_id}
									</p>
								</div>
								<ToggleSwitch
									value={target.enabled}
									onchange={(v) => patchTarget(target, { enabled: v })}
								/>
							</div>

							<div class="mt-2">
								<div class="mb-1 text-[0.625rem] font-medium text-gray-400 dark:text-gray-600">
									{$t('general.automaticEvents')}
								</div>
								{#if target.events.length}
									<div class="flex flex-wrap gap-1">
										{#each eventOptions.filter((event) => target.events.includes(event.value)) as event}
											<button
												class="h-6 rounded-md bg-gray-200/60 px-2 text-[0.6875rem] text-gray-900 transition-colors hover:bg-gray-200 dark:bg-white/10 dark:text-white dark:hover:bg-white/15"
												onclick={() =>
													patchTarget(target, {
														events: target.events.filter((item) => item !== event.value)
													})}
											>
												{$t(event.label)}
											</button>
										{/each}
									</div>
								{:else}
									<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600">
											{$t('general.noChatAlerts')}
									</p>
								{/if}
							</div>

							<div class="mt-2 flex items-end justify-between gap-2">
								{#if target.events.length}
									<div>
										<div class="mb-1 text-[0.625rem] font-medium text-gray-400 dark:text-gray-600">
											{$t('general.automaticDelivery')}
										</div>
										<div class="flex gap-1">
											{#each ['away', 'always'] as mode}
												<button
													class="h-6 rounded-md px-2 text-[0.6875rem] transition-colors
													{target.delivery === mode
														? 'bg-gray-200/60 text-gray-900 dark:bg-white/10 dark:text-white'
														: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-300'}"
													onclick={() =>
														patchTarget(target, { delivery: mode as NotificationDelivery })}
												>
													{mode === 'away' ? $t('general.onlyWhenAway') : $t('general.always')}
												</button>
											{/each}
										</div>
									</div>
								{:else}
									<div></div>
								{/if}
								<div class="flex gap-2">
									<button
										class="text-[0.6875rem] text-gray-500 hover:text-gray-900 dark:hover:text-white"
										onclick={() => sendTest(target)}
									>
										{$t('general.sendTest')}
									</button>
									<button
										class="text-[0.6875rem] text-gray-500 hover:text-gray-900 dark:hover:text-white"
										onclick={() => openEditTarget(target)}
									>
										{$t('common.edit')}
									</button>
									<button
										class="text-[0.6875rem] text-red-500 hover:text-red-600"
										onclick={() => removeTarget(target)}
									>
										{$t('common.remove')}
									</button>
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>

{#if formOpen}
	<Modal onclose={() => (formOpen = false)} class="w-full max-w-md mx-4">
		<div class="p-4">
			<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-3">
				{editingId ? $t('common.edit') : $t('general.addNotificationTarget')}
			</h2>

			<div class="mb-2 flex gap-1">
				{#each targetTypes as type}
					<button
						class="h-7 rounded-md px-2 text-xs transition-colors
						{form.type === type
							? 'bg-gray-200/60 text-gray-900 dark:bg-white/10 dark:text-white'
							: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-300'}"
						onclick={() => (form.type = type)}
					>
						{type === 'webhook' ? $t('general.webhook') : $t('general.bot')}
					</button>
				{/each}
			</div>

			<label class="text-[0.625rem] text-gray-400 dark:text-gray-600">
				{$t('general.targetIdForNotify')}
			</label>
			<input
				bind:value={form.id}
				placeholder={$t('general.targetId')}
				autofocus
				autocomplete="off"
				spellcheck="false"
				class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5 font-mono"
			/>

			{#if form.type === 'webhook'}
				<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-2">
					{$t('general.webhook')}
				</label>
				<input
					type="url"
					bind:value={form.url}
					placeholder={editingId ? $t('general.keepWebhookUrl') : 'https://hooks.slack.com/services/...'}
					autocomplete="off"
					spellcheck="false"
					class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5 font-mono"
				/>
			{:else}
				<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-2">
					{$t('general.bot')}
				</label>
				<select
					bind:value={form.bot_id}
					class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-0.5 cursor-pointer"
				>
					{#each botOptions as bot}
						<option value={bot.id}>
							{bot.name} ({bot.platform}){bot.is_running ? '' : ' - stopped'}
						</option>
					{/each}
				</select>

				<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-2">
					{$t('general.platformDestinationId')}
				</label>
				<input
					bind:value={form.destination_chat_id}
					placeholder={$t('general.platformDestinationId')}
					autocomplete="off"
					spellcheck="false"
					class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5 font-mono"
				/>
			{/if}

			<label class="block text-[0.625rem] text-gray-400 dark:text-gray-600 mt-3 mb-1">
				{$t('general.automaticEvents')}
			</label>
			<div class="flex flex-wrap gap-1">
				{#each eventOptions as event}
					<button
						class="h-6 rounded-md px-2 text-[0.6875rem] transition-colors
						{form.events.includes(event.value)
							? 'bg-gray-200/60 text-gray-900 dark:bg-white/10 dark:text-white'
							: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-300'}"
						onclick={() => toggleFormEvent(event.value)}
					>
						{$t(event.label)}
					</button>
				{/each}
			</div>

			{#if form.events.length}
				<label class="block text-[0.625rem] text-gray-400 dark:text-gray-600 mt-3 mb-1">
					{$t('general.automaticDelivery')}
				</label>
				<div class="flex gap-1">
					{#each ['away', 'always'] as mode}
						<button
							class="h-6 rounded-md px-2 text-[0.6875rem] transition-colors
							{form.delivery === mode
								? 'bg-gray-200/60 text-gray-900 dark:bg-white/10 dark:text-white'
								: 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-300'}"
							onclick={() => (form.delivery = mode as NotificationDelivery)}
						>
							{mode === 'away' ? $t('general.onlyWhenAway') : $t('general.always')}
						</button>
					{/each}
				</div>
			{/if}

			<p class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-3">
				{$t('general.notifyToolAlwaysSends')}
			</p>

			<div class="flex justify-end gap-3 mt-4">
				<button
					class="text-[0.8125rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-100"
					onclick={() => (formOpen = false)}
				>
					{$t('common.cancel')}
				</button>
				<button
					class="text-[0.8125rem] text-gray-700 hover:text-gray-900 disabled:opacity-30 dark:text-gray-300 dark:hover:text-white transition-colors duration-100"
					onclick={saveTarget}
					disabled={savingTarget || (form.type === 'bot' && !botOptions.length)}
				>
					{savingTarget ? $t('settings.saving') : $t('settings.save')}
				</button>
			</div>
		</div>
	</Modal>
{/if}

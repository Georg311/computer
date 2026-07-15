<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Icon from '../Icon.svelte';
	import CreateBotModal from './CreateBotModal.svelte';
	import { onMount } from 'svelte';
	import { listBots, deleteBot, startBot, stopBot, type BotData } from '$lib/apis/bots';
	import { t } from '$lib/i18n';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ToggleSwitch from '$lib/components/common/ToggleSwitch.svelte';

	let bots = $state<BotData[]>([]);
	let loading = $state(true);

	let showCreate = $state(false);
	let editBot = $state<BotData | null>(null);

	async function load() {
		try {
			bots = await listBots();
		} catch {
			toast.error($t('messaging.failedToLoad'));
		} finally {
			loading = false;
		}
	}

	function handleSaved() {
		showCreate = false;
		editBot = null;
		load();
	}

	async function toggleRunning(bot: BotData) {
		const wasRunning = bot.is_running;
		// Optimistic
		bot.is_running = !wasRunning;
		bots = [...bots];
		try {
			if (wasRunning) {
				await stopBot(bot.id);
			} else {
				await startBot(bot.id);
			}
			await load();
		} catch {
			bot.is_running = wasRunning;
			bots = [...bots];
			toast.error($t('messaging.failedToToggle'));
		}
	}

	async function handleDelete(e: Event, bot: BotData) {
		e.stopPropagation();
		try {
			await deleteBot(bot.id);
			await load();
		} catch {
			toast.error($t('messaging.failedToDelete'));
		}
	}

	onMount(load);
</script>

<div class="flex items-center justify-between mb-4">
	<h2 class="text-sm font-medium text-gray-900 dark:text-white">{$t('admin.messaging')}</h2>
	<button
		class="flex items-center justify-center w-6 h-6 rounded-lg text-gray-400 hover:text-gray-700 dark:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
		onclick={() => (showCreate = true)}
	>
		<Icon name="plus" size={14} />
	</button>
</div>

{#if loading}
	<div class="flex justify-center py-8">
		<Spinner size={16} />
	</div>
{:else}
	<div>
		{#each bots as bot}
			<div class="group flex items-center gap-2 w-full h-7">
				<!-- Platform icon -->
				<span
					class="shrink-0
					{bot.is_running ? 'text-gray-400 dark:text-gray-500' : 'text-gray-300 dark:text-gray-700'}"
				>
					<Icon name={bot.platform} size={14} />
				</span>

				<!-- Name (clickable to edit) -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<span
					class="flex-1 text-[0.8125rem] truncate cursor-pointer
					{bot.is_running ? 'text-gray-700 dark:text-gray-300' : 'text-gray-400 dark:text-gray-600'}"
					onclick={() => (editBot = bot)}
					onkeydown={() => {}}
				>
					{bot.name}
				</span>

				<!-- Delete (hover) -->
				<button
					type="button"
					class="opacity-0 group-hover:opacity-100 text-gray-300 dark:text-gray-700 hover:text-red-500 dark:hover:text-red-400 transition-all p-0.5"
					onclick={(e) => handleDelete(e, bot)}
				>
					<Icon name="trash" size={11} />
				</button>

				<ToggleSwitch value={bot.is_running} onchange={() => toggleRunning(bot)} />
			</div>
		{/each}

		{#if bots.length === 0}
			<p class="text-[0.8125rem] text-gray-400 dark:text-gray-600 py-4">{$t('messaging.noBots')}</p>
		{/if}
	</div>
{/if}

{#if showCreate}
	<CreateBotModal onclose={() => (showCreate = false)} onsave={handleSaved} />
{/if}

{#if editBot}
	<CreateBotModal bot={editBot} onclose={() => (editBot = null)} onsave={handleSaved} />
{/if}

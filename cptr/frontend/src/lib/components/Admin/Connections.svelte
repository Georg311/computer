<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Icon from '../Icon.svelte';
	import CreateConnectionModal from './CreateConnectionModal.svelte';
	import EditConnectionModal from './EditConnectionModal.svelte';
	import { onMount } from 'svelte';
	import { listConnections, updateConnection, type Connection } from '$lib/apis/admin';
	import { refreshChatState } from '$lib/stores/chat';
	import { t } from '$lib/i18n';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ToggleSwitch from '$lib/components/common/ToggleSwitch.svelte';

	let connections = $state<Connection[]>([]);
	let loading = $state(true);

	let showCreate = $state(false);
	let editConn = $state<Connection | null>(null);

	async function load() {
		try {
			connections = await listConnections();
		} catch {
			toast.error($t('connections.loadError'));
		} finally {
			loading = false;
		}
	}

	function handleCreated() {
		showCreate = false;
		load();
	}

	function handleChanged() {
		editConn = null;
		load();
	}

	async function toggleEnabled(conn: Connection, newVal: boolean) {
		// Optimistic update
		conn.enabled = newVal;
		connections = [...connections];
		try {
			await updateConnection(conn.id, { enabled: newVal });
			refreshChatState();
		} catch {
			// Revert
			conn.enabled = !newVal;
			connections = [...connections];
			toast.error($t('connections.failedToUpdate'));
		}
	}

	onMount(load);
</script>

<div class="flex items-center justify-between mb-4">
	<h2 class="text-sm font-medium text-gray-900 dark:text-white">{$t('admin.connections')}</h2>
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
		{#each connections as conn}
			<div class="group flex items-center gap-2 w-full h-7 text-left">
				<button
					type="button"
					class="flex-1 min-w-0 text-left text-[0.8125rem] truncate
					{conn.enabled ? 'text-gray-700 dark:text-gray-300' : 'text-gray-400 dark:text-gray-600'}"
					onclick={() => (editConn = conn)}
				>
					{conn.name}
				</button>
				<ToggleSwitch value={conn.enabled} onchange={(value) => toggleEnabled(conn, value)} />
			</div>
		{/each}

		{#if connections.length === 0}
			<p class="text-[0.8125rem] text-gray-400 dark:text-gray-600 py-4">
				{$t('connections.empty')}
			</p>
		{/if}
	</div>
{/if}

{#if showCreate}
	<CreateConnectionModal onclose={() => (showCreate = false)} oncreated={handleCreated} />
{/if}

{#if editConn}
	<EditConnectionModal
		connection={editConn}
		onclose={() => (editConn = null)}
		onchanged={handleChanged}
	/>
{/if}

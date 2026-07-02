<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Icon from '../Icon.svelte';
	import CreateUserModal from './CreateUserModal.svelte';
	import EditUserModal from './EditUserModal.svelte';
	import { onMount } from 'svelte';
	import { listUsers, getAdminConfig, updateConfig } from '$lib/apis/admin';
	import { session } from '$lib/session';
	import { t } from '$lib/i18n';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ToggleSwitch from '$lib/components/common/ToggleSwitch.svelte';

	interface User {
		user_id: string;
		username: string;
		display_name: string | null;
		profile_image_url: string | null;
		role: string;
		created_at: number;
	}

	const PAGE_SIZE = 10;

	let users = $state<User[]>([]);
	let loading = $state(true);
	let page = $state(0);

	// Auth config
	let signupEnabled = $state(false);
	let savingConfig = $state(false);

	let showCreate = $state(false);
	let editUser = $state<User | null>(null);

	let totalPages = $derived(Math.max(1, Math.ceil(users.length / PAGE_SIZE)));
	let pagedUsers = $derived(users.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE));
	let adminCount = $derived(users.filter((u) => u.role === 'admin').length);

	async function loadUsers() {
		try {
			users = await listUsers();
		} catch {
			toast.error($t('admin.failedToLoadUsers'));
		} finally {
			loading = false;
		}
	}

	async function loadAuthConfig() {
		try {
			const config = await getAdminConfig();
			signupEnabled = config['auth.signup_enabled'] === true;
		} catch {}
	}

	async function toggleSignup(value: boolean) {
		savingConfig = true;
		try {
			await updateConfig({ 'auth.signup_enabled': value });
			signupEnabled = value;
			toast.success($t('settings.saved'));
		} catch {
			toast.error($t('admin.failedToSave'));
		} finally {
			savingConfig = false;
		}
	}

	function handleCreated() {
		showCreate = false;
		loadUsers();
	}

	function handleChanged() {
		editUser = null;
		loadUsers();
		if (page >= totalPages) page = Math.max(0, totalPages - 1);
	}

	onMount(() => {
		loadUsers();
		loadAuthConfig();
	});
</script>

<div class="flex items-center justify-between mb-4">
	<h2 class="text-sm font-medium text-gray-900 dark:text-white">{$t('admin.users')}</h2>
	<button
		class="flex items-center justify-center w-6 h-6 rounded-lg text-gray-400 hover:text-gray-700 dark:text-gray-600 dark:hover:text-gray-300 transition-colors duration-75"
		onclick={() => (showCreate = true)}
	>
		<Icon name="plus" size={14} />
	</button>
</div>

<!-- Sign-up toggle -->
<div class="flex flex-col gap-2.5 mb-3">
	<label class="flex items-center justify-between cursor-pointer">
		<span class="text-xs text-gray-600 dark:text-gray-400">{$t('admin.allowSignUp')}</span>
		<ToggleSwitch value={signupEnabled} onchange={(v) => toggleSignup(v)} disabled={savingConfig} />
	</label>
	<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
		{signupEnabled ? $t('admin.signUpEnabled') : $t('admin.signUpDisabled')}
	</p>
</div>

{#if loading}
	<div class="flex justify-center py-8">
		<Spinner size={16} />
	</div>
{:else}
	<div>
		{#each pagedUsers as user}
			<button
				class="group flex items-center gap-2 w-full h-7 text-left"
				onclick={() => (editUser = user)}
			>
				<img
					src={user.profile_image_url || '/user.png'}
					alt=""
					class="w-4 h-4 rounded-full object-cover shrink-0"
				/>
				<span class="flex-1 text-[0.8125rem] text-gray-700 dark:text-gray-300 truncate"
					>{user.display_name || user.username}</span
				>
				<span
					class="text-[0.6875rem] transition-colors duration-75
					{user.role === 'admin'
						? 'text-gray-900 dark:text-white font-medium'
						: 'text-gray-400 dark:text-gray-600'}">{user.role}</span
				>
			</button>
		{/each}

		{#if users.length === 0}
			<p class="text-[0.8125rem] text-gray-400 dark:text-gray-600 py-4">{$t('admin.noUsers')}</p>
		{/if}
	</div>

	{#if totalPages > 1}
		<div
			class="flex items-center justify-between mt-4 pt-3 border-t border-gray-200 dark:border-white/6"
		>
			<button
				class="text-[0.6875rem] text-gray-400 dark:text-gray-600 hover:text-gray-700 dark:hover:text-gray-300 transition-colors disabled:opacity-30 disabled:pointer-events-none"
				disabled={page === 0}
				onclick={() => page--}>← {$t('admin.prev').replace('← ', '')}</button
			>
			<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600"
				>{page + 1} / {totalPages}</span
			>
			<button
				class="text-[0.6875rem] text-gray-400 dark:text-gray-600 hover:text-gray-700 dark:hover:text-gray-300 transition-colors disabled:opacity-30 disabled:pointer-events-none"
				disabled={page >= totalPages - 1}
				onclick={() => page++}>{$t('admin.next')}</button
			>
		</div>
	{/if}
{/if}

{#if showCreate}
	<CreateUserModal onclose={() => (showCreate = false)} oncreated={handleCreated} />
{/if}

{#if editUser}
	<EditUserModal
		user={editUser}
		{adminCount}
		currentUserId={$session?.user_id ?? ''}
		onclose={() => (editUser = null)}
		onchanged={handleChanged}
	/>
{/if}

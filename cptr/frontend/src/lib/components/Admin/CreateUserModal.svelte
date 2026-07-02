<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Modal from '../Modal.svelte';
	import { createUser as apiCreateUser } from '$lib/apis/admin';
	import { ApiError } from '$lib/apis';
	import { t } from '$lib/i18n';
	import Spinner from '$lib/components/common/Spinner.svelte';

	interface Props {
		onclose: () => void;
		oncreated: () => void;
	}

	const ROLES = ['admin', 'user', 'pending'] as const;

	let { onclose, oncreated }: Props = $props();

	let username = $state('');
	let password = $state('');
	let displayName = $state('');
	let role = $state<string>('user');
	let creating = $state(false);

	async function create() {
		if (!username.trim()) {
			toast.error($t('admin.usernameRequired'));
			return;
		}
		if (password.length < 6) {
			toast.error($t('admin.minCharsPassword'));
			return;
		}
		creating = true;
		try {
			await apiCreateUser(username.trim(), password, role);
			toast.success($t('admin.userCreated'));
			oncreated();
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : $t('auth.connectionFailed'));
		} finally {
			creating = false;
		}
	}
</script>

<Modal {onclose} class="w-full max-w-sm mx-4">
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="p-4"
		onkeydown={(e) => {
			if (e.key === 'Enter' && username.trim() && password.length >= 6) create();
		}}
	>
		<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-2">{$t('admin.newUser')}</h2>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1"
			>{$t('admin.username')}</label
		>
		<input
			type="text"
			placeholder={$t('admin.enterUsername')}
			bind:value={username}
			autofocus
			autocomplete="off"
			spellcheck="false"
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
		/>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1"
			>{$t('admin.displayName')}</label
		>
		<input
			type="text"
			placeholder={$t('admin.optional')}
			bind:value={displayName}
			autocomplete="off"
			spellcheck="false"
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
		/>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1"
			>{$t('admin.passwordLabel')}</label
		>
		<input
			type="password"
			placeholder={$t('admin.minChars')}
			bind:value={password}
			autocomplete="new-password"
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
		/>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1">{$t('admin.role')}</label>
		<select
			bind:value={role}
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-0.5 cursor-pointer"
		>
			{#each ROLES as r}<option value={r}>{r}</option>{/each}
		</select>
		<div class="flex justify-end mt-2">
			<button
				disabled={creating || !username.trim() || password.length < 6}
				onclick={create}
				class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100 disabled:opacity-30 disabled:pointer-events-none"
			>
				{#if creating}
					<Spinner size={14} />
				{:else}
					{$t('admin.create')}
				{/if}
			</button>
		</div>
	</div>
</Modal>

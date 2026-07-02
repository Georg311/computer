<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Modal from '../Modal.svelte';
	import {
		updateRole,
		updateUserProfile,
		resetPassword,
		updateUsername,
		deleteUser as apiDeleteUser
	} from '$lib/apis/admin';
	import { ApiError } from '$lib/apis';
	import { t } from '$lib/i18n';

	interface User {
		user_id: string;
		username: string;
		display_name: string | null;
		profile_image_url: string | null;
		role: string;
		created_at: number;
	}

	interface Props {
		user: User;
		adminCount: number;
		currentUserId: string;
		onclose: () => void;
		onchanged: () => void;
	}

	const ROLES = ['admin', 'user', 'pending'] as const;

	let { user, adminCount, currentUserId, onclose, onchanged }: Props = $props();

	let isSelf = $derived(user.user_id === currentUserId);

	let username = $state(user.username);
	let displayName = $state(user.display_name ?? '');
	let newPassword = $state('');
	let role = $state(user.role);
	let saving = $state(false);

	async function save() {
		saving = true;
		try {
			const trimmedUsername = username.trim();
			if (!trimmedUsername) {
				toast.error($t('admin.usernameRequired'));
				saving = false;
				return;
			}
			if (newPassword && newPassword.length < 6) {
				toast.error($t('admin.minCharsPassword'));
				saving = false;
				return;
			}

			if (trimmedUsername !== user.username) {
				await updateUsername(user.user_id, trimmedUsername);
			}
			const trimmedDisplay = displayName.trim() || null;
			if (trimmedDisplay !== user.display_name) {
				await updateUserProfile(user.user_id, trimmedDisplay);
			}
			if (role !== user.role) {
				await updateRole(user.user_id, role);
			}
			if (newPassword) {
				await resetPassword(user.user_id, newPassword);
			}
			toast.success($t('admin.userUpdated'));
			onchanged();
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : $t('auth.connectionFailed'));
		} finally {
			saving = false;
		}
	}

	async function deleteUser() {
		try {
			await apiDeleteUser(user.user_id);
			toast.success($t('admin.userDeleted', { username: user.username }));
			onchanged();
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : $t('auth.connectionFailed'));
		}
	}
</script>

<Modal {onclose} class="w-full max-w-sm mx-4">
	<div class="p-4">
		<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-2">{$t('admin.editUser')}</h2>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1"
			>{$t('admin.username')}</label
		>
		<input
			type="text"
			placeholder={$t('admin.username')}
			bind:value={username}
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
		/>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1"
			>{$t('admin.displayName')}</label
		>
		<input
			type="text"
			placeholder={$t('admin.optional')}
			bind:value={displayName}
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
		/>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1"
			>{$t('admin.newPasswordLabel')}</label
		>
		<input
			type="password"
			placeholder={$t('admin.leaveBlank')}
			bind:value={newPassword}
			autocomplete="new-password"
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-none py-0.5"
		/>
		<label class="text-[0.625rem] text-gray-400 dark:text-gray-600 mt-1">{$t('admin.role')}</label>
		<select
			bind:value={role}
			disabled={isSelf}
			class="block w-full bg-transparent text-[0.8125rem] text-gray-700 dark:text-gray-300 outline-none py-0.5 cursor-pointer disabled:opacity-50"
		>
			{#each ROLES as r}<option value={r}>{r}</option>{/each}
		</select>
		<div class="flex items-center justify-between mt-3">
			{#if !isSelf && (user.role !== 'admin' || adminCount > 1)}
				<button
					class="text-[0.8125rem] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors duration-100"
					onclick={deleteUser}>{$t('admin.delete')}</button
				>
			{:else}
				<span></span>
			{/if}
			<button
				disabled={saving}
				onclick={save}
				class="text-[0.8125rem] text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-100 disabled:opacity-30 disabled:pointer-events-none"
			>
				{#if saving}{$t('settings.saving')}{:else}{$t('settings.save')}{/if}
			</button>
		</div>
	</div>
</Modal>

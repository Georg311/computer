<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getAdminConfig, updateConfig } from '$lib/apis/admin';
	import ToggleSwitch from '$lib/components/common/ToggleSwitch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	let loading = $state(true);
	let saving = $state(false);
	let backgroundReview = $state(true);
	let reviewInterval = $state(10);

	onMount(async () => {
		try {
			const config = await getAdminConfig();
			backgroundReview =
				config['skills.background_review_enabled'] !== false &&
				config['skills.background_review_enabled'] !== 'false';
			reviewInterval = Number(config['skills.review_interval_turns']) || 10;
		} catch {
			toast.error('Failed to load config');
		}
		loading = false;
	});

	async function save() {
		saving = true;
		try {
			await updateConfig({
				'skills.background_review_enabled': backgroundReview,
				'skills.review_interval_turns': Math.max(1, Number(reviewInterval) || 10)
			});
			toast.success('Saved');
		} catch {
			toast.error('Failed to save');
		} finally {
			saving = false;
		}
	}
</script>

<div class="flex flex-col min-h-full">
	<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">Skills</h2>

	{#if loading}
		<div class="flex justify-center py-8"><Spinner size={16} /></div>
	{:else}
		<div class="flex flex-col gap-2.5">
			<label class="flex items-center justify-between cursor-pointer">
				<span class="text-xs text-gray-600 dark:text-gray-400">Background review</span>
				<ToggleSwitch
					value={backgroundReview}
					onchange={(v) => {
						backgroundReview = v;
					}}
				/>
			</label>
			<p class="text-[0.6875rem] text-gray-400 dark:text-gray-600 -mt-1">
				Let Computer create or update managed skills after successful reusable work.
			</p>

			{#if backgroundReview}
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400" for="skills-review-interval"
						>Review interval</label
					>
					<div class="flex items-center gap-1.5 mt-1">
						<input
							id="skills-review-interval"
							type="number"
							bind:value={reviewInterval}
							min="1"
							class="w-16 h-7 px-2 rounded-lg text-xs bg-gray-100 dark:bg-white/6 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-white/8 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
						/>
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-600">turns</span>
					</div>
				</div>
			{/if}
		</div>

		<div class="mt-5 pt-4 border-t border-gray-100 dark:border-white/8">
			<button
				class="h-8 px-3 rounded-lg text-xs bg-gray-900 dark:bg-white text-white dark:text-black hover:bg-gray-700 dark:hover:bg-gray-200 transition-colors disabled:opacity-50"
				disabled={saving}
				onclick={save}
			>
				{saving ? 'Saving...' : 'Save'}
			</button>
		</div>
	{/if}
</div>

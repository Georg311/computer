<script lang="ts">
	import Icon from '../Icon.svelte';
	import { t } from '$lib/i18n';
	import type { ChatTask } from '$lib/apis/chat';

	interface Props {
		tasks: ChatTask[];
	}

	let { tasks }: Props = $props();
	let collapsed = $state(false);

	const completedCount = $derived(tasks.filter((task) => task.status === 'completed').length);
	const totalCount = $derived(tasks.length);
</script>

{#if tasks.length > 0}
	<div class="app-subtle-surface my-1 overflow-hidden rounded-3xl border shadow-sm">
		<div class="flex items-center justify-between px-3.5 pt-1.5 pb-1">
			<div class="app-muted flex min-w-0 items-center gap-2 text-xs">
				<Icon name="list" size={14} />
				<span class="truncate">
					{completedCount}
					{$t('chat.tasksOutOf')}
					{totalCount}
					{$t('chat.tasksCompleted')}
				</span>
			</div>
			<button
				type="button"
				class="app-muted flex size-6 items-center justify-center rounded-full bg-transparent transition-colors hover:text-gray-600 dark:hover:text-gray-300"
				onclick={() => (collapsed = !collapsed)}
				aria-label={collapsed ? $t('chat.tasksExpand') : $t('chat.tasksCollapse')}
			>
				<Icon name={collapsed ? 'chevron-down' : 'chevron-up'} size={12} />
			</button>
		</div>

		{#if !collapsed}
			<div class="space-y-1 px-2.5 pb-3">
				{#each tasks as task, idx (task.id)}
					<div class="flex items-start gap-2 rounded-2xl px-1 py-0.5 text-xs">
						<span class="app-muted mt-0.5 flex size-3.5 shrink-0 items-center justify-center">
							{#if task.status === 'completed'}
								<Icon name="check" size={14} strokeWidth={2.5} />
							{:else if task.status === 'in_progress'}
								<span
									class="size-3 rounded-full border-2 border-current border-t-transparent opacity-70 animate-spin"
								></span>
							{:else if task.status === 'cancelled'}
								<span class="size-3 rounded-full border border-dashed border-current"></span>
							{:else}
								<span class="size-3 rounded-full border border-current"></span>
							{/if}
						</span>
						<span
							class="line-clamp-2 {task.status === 'completed'
								? 'app-muted line-through'
								: task.status === 'cancelled'
									? 'app-muted line-through'
									: 'text-gray-700 dark:text-gray-300'}"
						>
							{idx + 1}. {task.content}
						</span>
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { goal$, pauseGoal, resumeGoal, completeTask as apiCompleteTask, skipTask } from '$lib/stores/goal';

	let goalState = $state(get(goal$));
	let currentTaskList = $derived.by(() => {
		if (!goalState) return null;
		return goalState.task_list || [];
	});
	let currentTaskId = $derived(goalState?.current_task_id || null);
	let showTasks = $state(false);

	$: if (goalState) {
		const completed = goalState.task_list?.filter((t) => t.status === 'complete').length ?? 0;
		const total = goalState.task_list?.length || 1;
		progress = Math.round(((completed / total) * 100));
	}

	let progress = $state(0);

	async function handlePause() {
		await pauseGoal();
		goalState = get(goal$);
	}

	async function handleResume() {
		await resumeGoal();
		goalState = get(goal$);
	}

	async function handleCompleteTask(taskId: string, evidence?: string) {
		try {
			await apiCompleteTask(taskId, evidence);
			goalState = get(goal$);
		} catch (e) {
			console.warn('[goal] Complete task failed:', e);
		}
	}

	async function handleSkipTask(taskId: string, reason?: string) {
		try {
			await skipTask(taskId, reason);
			goalState = get(goal$);
		} catch (e) {
			console.warn('[goal] Skip task failed:', e);
		}
	}

	onMount(async () => {});
</script>

{#if goalState && goalState.task_list?.length > 0}
<div class="goal-dashboard">
	<!-- Header -->
	<div class="goal-header">
		<span class="status-badge {goalState.status}" title={goalState.status}>●</span>
		<h3>{goalState.objective}</h3>
	</div>

	<!-- Progress Bar -->
	{#if goalState.task_list.length > 0}
	<div class="progress-bar" on:click={() => showTasks = !showTasks}>
		<div class="progress-fill" style="width: {progress}%"></div>
		<span>{progress}%</span>
	</div>
	{/if}

	<!-- Current Task Highlight -->
	{#if goalState.current_task_id && goalState.task_list.length > 0}
	<div class="current-task">
		<span class="label">Current:</span>
		<strong>
			{goalState.task_list.find(t => t.id === goalState.current_task_id)?.title || 'Unknown'}
		</strong>
	</div>
	{/if}

	<!-- Task List (collapsible) -->
	{#if goalState.task_list.length > 0}
	<div class="task-section">
		<button class="toggle-tasks" on:click={() => showTasks = !showTasks}>
			Tasks ({goalState.task_list.filter(t => t.status === 'complete').length}/{goalState.task_list.length})
			<span class="arrow">{showTasks ? '▾' : '▸'}</span>
		</button>

		{#if showTasks}
		<ul class="task-list">
			{#each goalState.task_list as task (task.id)}
				<li class="{task.status}" data-task-id={task.id}>
					<span class="task-title">{task.title}</span>
					{#if task.evidence}
						<small class="evidence" title={task.evidence}>📎</small>
					{/if}
					{#if task.status === 'skipped'}<em class="skipped">(skipped)</em>{/if}

					{#if task.status !== 'complete' && goalState.status !== 'paused' && goalState.status !== 'complete'}
						<div class="task-actions">
							<button class="btn-complete" on:click={() => handleCompleteTask(task.id)} title="Mark complete">✓</button>
							<button class="btn-skip" on:click={() => handleSkipTask(task.id, 'Skipped by user')} title="Skip task">~</button>
						</div>
					{/if}
				</li>
			{/each}
		</ul>
		{/if}
	</div>
	{/if}

	<!-- Actions -->
	<div class="goal-actions">
		{#if goalState.status === 'active'}
			<button class="btn-action" on:click={handlePause}>⏸ Pause Goal</button>
		{:else if goalState.status === 'paused'}
			<button class="btn-action" on:click={handleResume}>▶ Resume Goal</button>
		{/if}
	</div>
</div>
{/if}

<style>
	.goal-dashboard {
		background: var(--bg-secondary, #1a1b2e);
		border: 1px solid var(--border-color, #333);
		border-radius: 8px;
		padding: 12px;
		margin-bottom: 16px;
		font-size: 0.9em;
	}

	.goal-header {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 8px;
	}

	.goal-header h3 {
		margin: 0;
		font-size: 1em;
		font-weight: 600;
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.status-badge {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		display: inline-block;
		font-size: 0.8em;
		line-height: 1;
	}

	.status-badge.active { background-color: #4ade80; }
	.status-badge.paused { background-color: #facc15; }
	.status-badge.blocked { background-color: #f87171; }
	.status-badge.complete { background-color: #60a5fa; }

	.progress-bar {
		height: 4px;
		background: var(--bg-tertiary, #2d3748);
		border-radius: 2px;
		margin: 8px 0;
		position: relative;
		cursor: pointer;
	}

	.progress-fill {
		height: 100%;
		background: #3b82f6;
		border-radius: 2px;
		transition: width 0.3s ease;
	}

	.progress-bar span {
		position: absolute;
		right: 4px;
		top: -16px;
		font-size: 0.75em;
		color: #9ca3af;
	}

	.current-task {
		margin: 8px 0;
		padding: 6px 8px;
		background: var(--bg-tertiary, #2d3748);
		border-radius: 4px;
		font-size: 0.85em;
		display: flex;
		gap: 4px;
		align-items: center;
	}

	.current-task .label {
		color: #9ca3af;
		margin-right: 4px;
	}

	.task-section {
		margin-top: 8px;
	}

	.toggle-tasks {
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 0.85em;
		padding: 4px 0;
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.toggle-tasks .arrow {
		margin-left: auto;
		color: #9ca3af;
	}

	.task-list {
		list-style: none;
		padding: 0;
		margin: 8px 0 0 0;
		max-height: 200px;
		overflow-y: auto;
	}

	.task-list li {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		border-radius: 4px;
		margin-bottom: 2px;
		font-size: 0.85em;
	}

	.task-list li.pending { background: rgba(255, 255, 255, 0.03); }
	.task-list li.complete { opacity: 0.6; text-decoration: line-through; }
	.task-list li.skipped { color: #facc15; }

	.task-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

	.evidence { cursor: help; font-size: 0.9em; }

	.skipped { margin-left: auto; font-size: 0.8em; color: #facc15; }

	.task-actions {
		display: flex;
		gap: 4px;
		margin-left: auto;
	}

	.btn-complete, .btn-skip {
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 0.9em;
		padding: 2px 4px;
		border-radius: 3px;
	}

	.btn-complete:hover { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
	.btn-skip:hover { background: rgba(250, 204, 21, 0.2); color: #facc15; }

	.goal-actions {
		display: flex;
		gap: 8px;
		margin-top: 12px;
	}

	.btn-action {
		background: var(--bg-tertiary, #2d3748);
		border: 1px solid var(--border-color, #333);
		color: inherit;
		padding: 6px 10px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.85em;
	}

	.btn-action:hover {
		background: var(--bg-primary, #1a1b2e);
	}
</style>

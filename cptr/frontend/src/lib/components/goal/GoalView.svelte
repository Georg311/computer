<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { goal$, pauseGoal, resumeGoal, completeGoal, completeTask as apiCompleteTask, skipTask, createGoal, type GoalState } from '../../stores/goal';

	let state = $state(get(goal$));
	let objective = $state('');
	let isCreating = $state(false);
	let error = $state<string | null>(null);

	let progress = $derived(() => {
		if (!state) return 0;
		const completed = state.task_list?.filter(t => t.status === 'complete').length ?? 0;
		const total = state.task_list?.length || 1;
		return Math.round(((completed / total) * 100));
	});

	async function handleCreateGoal() {
		if (!objective.trim()) return;
		isCreating = true;
		error = null;
		try {
			await createGoal(objective.trim());
			state = get(goal$);
		} catch (e) {
			error = e?.message || 'Failed to create goal';
		} finally {
			isCreating = false;
		}
	}

	async function handlePause() {
		await pauseGoal();
		state = get(goal$);
	}

	async function handleResume() {
		await resumeGoal();
		state = get(goal$);
	}

	async function handleComplete() {
		await completeGoal();
		state = get(goal$);
	}

	async function handleCompleteTask(taskId: string) {
		try {
			await apiCompleteTask(taskId);
			state = get(goal$);
		} catch (e) {
			console.warn('Complete task failed:', e);
		}
	}

	async function handleSkipTask(taskId: string) {
		try {
			await skipTask(taskId, 'Skipped by user');
			state = get(goal$);
		} catch (e) {
			console.warn('Skip task failed:', e);
		}
	}

	onMount(() => {});
</script>

<div class="goal-view">
	<!-- Active Goal -->
	{#if state && (state.task_list?.length || 0) > 0}
		<div class="active-goal">
			<span class="status {state.status}" title={state.status}></span>
			<h3>{state.objective}</h3>

			<!-- Progress -->
			{#if state.task_list.length > 0}
				<div class="progress-bar" on:click={() => showTasks = !showTasks}>
					<div class="fill" style="width: {progress}%"></div>
					<span>{progress}%</span>
				</div>
			{/if}

			<!-- Current Task -->
			{#if state.current_task_id && state.task_list.length > 0}
				<div class="current-task">
					Current: <strong>{state.task_list.find(t => t.id === state.current_task_id)?.title || 'Unknown'}</strong>
				</div>
			{/if}

			<!-- Task List -->
			{#if state.task_list.length > 0}
				<div class="task-section">
					<button class="toggle" on:click={() => showTasks = !showTasks}>
						Tasks ({state.task_list.filter(t => t.status === 'complete').length}/{state.task_list.length})
						<span>{showTasks ? '▾' : '▸'}</span>
					</button>

					{#if showTasks}
						<ul class="task-list">
							{#each state.task_list as task (task.id)}
								<li class="{task.status}" data-task-id={task.id}>
									<span class="title">{task.title}</span>
									{#if task.evidence}<small title={task.evidence}>📎</small>{/if}
									{#if task.status === 'skipped'}<em>(skipped)</em>{/if}

									{#if task.status !== 'complete' && state.status !== 'paused' && state.status !== 'complete'}
										<div class="actions">
											<button on:click={() => handleCompleteTask(task.id)} title="Mark complete">✓</button>
											<button on:click={() => handleSkipTask(task.id)} title="Skip task">~</button>
										</div>
									{/if}
								</li>
							{/each}
						</ul>
					{/if}
				</div>
			{/if}

			<!-- Actions -->
			<div class="actions">
				{#if state.status === 'active'}
					<button on:click={handlePause}>⏸ Pause Goal</button>
					<button on:click={handleComplete}>✅ Complete Goal</button>
				{:else if state.status === 'paused'}
					<button on:click={handleResume}>▶ Resume Goal</button>
				{/if}
			</div>
		</div>
	{:else}
		<div class="no-goal">
			<p>No active goal.</p>
		</div>
	{/if}
</div>

<style>
	.goal-view {
		padding: 16px;
		border-bottom: 1px solid var(--border-color, #333);
	}

	.active-goal {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.status {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		display: inline-block;
		margin-right: 8px;
		vertical-align: middle;
	}

	.status.active { background-color: #4ade80; }
	.status.paused { background-color: #facc15; }
	.status.blocked { background-color: #f87171; }
	.status.complete { background-color: #60a5fa; }

	h3 {
		margin: 0;
		font-size: 0.9em;
		font-weight: 600;
		flex: 1;
	}

	.progress-bar {
		height: 4px;
		background: var(--bg-secondary, #2d3748);
		border-radius: 2px;
		position: relative;
		cursor: pointer;
	}

	.progress-bar .fill {
		height: 100%;
		background: #3b82f6;
		border-radius: 2px;
		transition: width 0.3s ease;
	}

	.progress-bar span {
		position: absolute;
		right: 4px;
		top: -16px;
		font-size: 0.7em;
		color: #9ca3af;
	}

	.current-task {
		padding: 4px 8px;
		background: var(--bg-secondary, #2d3748);
		border-radius: 4px;
		font-size: 0.8em;
	}

	.task-section {
		margin-top: 8px;
	}

	.toggle {
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 0.8em;
		padding: 4px 0;
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.task-list {
		list-style: none;
		padding: 0;
		margin: 8px 0 0 0;
		max-height: 200px;
		overflow-y: auto;
		font-size: 0.8em;
	}

	.task-list li {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px;
		border-radius: 4px;
		margin-bottom: 2px;
	}

	.task-list li.pending { background: rgba(255, 255, 255, 0.03); }
	.task-list li.complete { opacity: 0.6; text-decoration: line-through; }
	.task-list li.skipped { color: #facc15; }

	.title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

	.actions {
		display: flex;
		gap: 4px;
		margin-left: auto;
	}

	.no-goal {
		text-align: center;
		padding: 16px 0;
		color: #9ca3af;
		font-size: 0.85em;
	}
</style>

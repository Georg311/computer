<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { get } from 'svelte/store';
	import Icon from '../Icon.svelte';

	import {
		goal$,
		focusedGoal as goalStore,
		pauseGoal,
		resumeGoal,
		completeTask as apiCompleteTask,
		skipTask,
		createGoal,
		allGoals,
		fetchAllGoals,
		type GoalState
	} from '$lib/stores/goal';

	let { oncreategoal }: { oncreategoal?: (description: string) => void } = $props();

	let state = $state<GoalState | null>(get(goal$));
	const allGoalsList = $derived(get(allGoals) as GoalState[]);

	let objectiveInput = $state('');
	let isCreating = $state(false);
	let error = $state<string | null>(null);

	// Expanded goals (by id) — show task list for each
	const expandedGoals = $state(new Set<string>());

	// Polling timer
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	async function loadActiveGoal() {
		try {
			const res = await fetch('/api/goal/active');
			if (res.ok) {
				state = await res.json();
			} else if (res.status !== 404) {
				console.warn('[GoalPanel] Failed to load active goal:', res.status);
			}
		} catch (e) {
			console.warn('[GoalPanel] Fetch error:', e);
		}
	}

	async function handleCreateGoal() {
		if (!objectiveInput.trim()) return;
		isCreating = true;
		error = null;
		try {
			await createGoal(objectiveInput.trim());
			objectiveInput = '';
		} catch (e: any) {
			error = e?.message || 'Failed to create goal';
		} finally {
			isCreating = false;
		}
	}

	async function handlePause(goalId?: string) {
		try {
			await pauseGoal();
			state = get(goal$);
		} catch (e) {
			console.warn('[GoalPanel] Pause failed:', e);
		}
	}

	async function handleResume(goalId?: string) {
		try {
			await resumeGoal();
			state = get(goal$);
		} catch (e) {
			console.warn('[GoalPanel] Resume failed:', e);
		}
	}

	async function handleCompleteTask(taskId: string) {
		try {
			await apiCompleteTask(taskId);
			state = get(goal$);
		} catch (e) {
			console.warn('[GoalPanel] Complete task failed:', e);
		}
	}

	async function handleSkipTask(taskId: string) {
		try {
			await skipTask(taskId, 'Skipped by user');
			state = get(goal$);
		} catch (e) {
			console.warn('[GoalPanel] Skip task failed:', e);
		}
	}

	function toggleExpand(goalId: string) {
		if (expandedGoals.has(goalId)) {
			expandedGoals.delete(goalId);
		} else {
			expandedGoals.add(goalId);
		}
	}

	async function handleGoalCompleteTask(goalId: string, taskId: string) {
		try {
			const res = await fetch('/api/goal/task/complete', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ task_id: taskId })
			});
			if (res.ok) {
				await fetchAllGoals();
			} else if (res.status === 404 || res.status === 400) {
				const body = JSON.stringify({ description: '', task_id: taskId });
				const res2 = await fetch('/api/goal/complete-task', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body
				});
				if (res2.ok) {
					await fetchAllGoals();
				} else {
					console.warn('[GoalPanel] Complete task error:', res2.status);
				}
			} else {
				console.warn('[GoalPanel] Complete task error:', res.status);
			}
		} catch (e) {
			console.warn('[GoalPanel] Complete task error:', e);
		}
	}

	async function handleGoalSkipTask(goalId: string, taskId: string) {
		try {
			const res = await fetch('/api/goal/skip-task', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ task_id: taskId, evidence: 'Skipped by user' })
			});
			if (res.ok) {
				await fetchAllGoals();
			} else {
				console.warn('[GoalPanel] Skip task error:', res.status);
			}
		} catch (e) {
			console.warn('[GoalPanel] Skip task error:', e);
		}
	}

	async function handleDeleteGoal(goalId: string) {
		if (!confirm('Goal wirklich löschen?')) return;
		try {
			const res = await fetch(`/api/goal/${goalId}`, { method: 'DELETE' });
			if (res.ok) {
				await fetchAllGoals();
			} else {
				console.warn('[GoalPanel] Delete goal error:', res.status);
			}
		} catch (e) {
			console.warn('[GoalPanel] Delete goal error:', e);
		}
	}

	onMount(() => {
		loadActiveGoal();
		fetchAllGoals();
	});

	function startPolling() {
		stopPolling();
		const g = get(goal$);
		if (g && (g.status === 'active' || g.status === 'paused')) {
			pollTimer = setInterval(() => {
				loadActiveGoal();
				fetchAllGoals();
			}, 30_000);
		}
	}

	function stopPolling() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	$effect(() => {
		const g = get(goalStore);
		state = g;
		if (g && (g.status === 'active' || g.status === 'paused')) {
			startPolling();
		} else {
			stopPolling();
		}
	});

	onDestroy(stopPolling);

	function statusDotColor(status: string): string {
		switch (status) {
			case 'active': return '#4ade80';
			case 'paused': return '#facc15';
			case 'blocked': return '#f87171';
			case 'complete': return '#60a5fa';
			default: return '#9ca3af';
		}
	}

	function statusLabel(status: string): string {
		switch (status) {
			case 'active': return 'Active';
			case 'paused': return 'Paused';
			case 'blocked': return 'Blocked';
			case 'complete': return 'Complete';
			default: return status;
		}
	}

	let completedCount = $derived(() => {
		if (!state || !state.task_list?.length) return 0;
		return (state.task_list as GoalState['task_list']).filter((t: GoalTask) => t.status === 'complete').length;
	});

	let totalCount = $derived(() => state?.task_list?.length ?? 0);

	let progress = $derived(() => {
		if (!state || !state.task_list?.length) return 0;
		const completed = (state.task_list as GoalState['task_list']).filter((t: GoalTask) => t.status === 'complete').length;
		return Math.round((completed / state.task_list.length) * 100);
	});

	const activeGoalObj = $derived(get(goal$));

	const displayedGoalsList = $derived((get(allGoals) as GoalState[]).filter(
		g => g.id !== activeGoalObj?.id
	));
</script>

<!-- Active / focused goal — always show it prominently -->
{#if state && (state.task_list?.length || 0) > 0}
<div class="goal-panel active-goal">
	<!-- Header: Status dot + Objective -->
	<div class="header" onclick={() => toggleExpand(state.id)} role="button" tabindex="0" aria-label="Toggle goal details">
		<span class="status-dot {state.status}" title={state.status}></span>
		<span class="objective truncate">{state.objective}</span>
		<button class="collapse-btn" type="button" onclick={(e) => { e.stopPropagation(); toggleExpand(state.id); }} aria-label={expandedGoals.has(state.id) ? 'Collapse' : 'Expand'}>
			<Icon name={expandedGoals.has(state.id) ? 'chevron-up' : 'chevron-down'} size={12} />
		</button>
	</div>

	{#if expandedGoals.has(state.id)}
		<!-- Progress -->
		<div class="progress">
			<span>{completedCount()}/{totalCount()} tasks ({progress()}%)</span>
			<div class="progress-bar">
				<div class="fill" style="width: {progress()}%"></div>
			</div>
		</div>

		<!-- Current Task -->
		{#if state.current_task_id && state.task_list.length > 0}
			<div class="current-task">
				<span class="label">Current:</span>
				<span>{state.task_list.find(t => t.id === state.current_task_id)?.title || 'Unknown'}</span>
				{#if state.status !== 'paused'}
					<div class="task-actions">
						<button type="button" onclick={() => handleCompleteTask(state.current_task_id)} title="Mark complete">✓</button>
						<button type="button" onclick={() => handleSkipTask(state.current_task_id)} title="Skip task">~</button>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Pause/Resume -->
		{#if state.status === 'active'}
			<button type="button" class="action-btn pause" onclick={handlePause}>⏸ Pause Goal</button>
		{:else if state.status === 'paused'}
			<button type="button" class="action-btn resume" onclick={handleResume}>▶ Resume Goal</button>
		{/if}

		<!-- Task List (collapsible) -->
		{#if state.task_list.length > 1}
			<div class="task-section">
				<ul class="task-list">
					{#each state.task_list as task (task.id)}
						<li class="{task.status}" data-task-id={task.id}>
							<span class="title">{task.title}</span>
							{#if task.evidence}<small title={task.evidence} class="evidence">📎</small>{/if}
							{#if task.status === 'skipped'}<em>(skipped)</em>{/if}
							{#if task.status !== 'complete' && state.status !== 'paused' && state.status !== 'complete'}
								<div class="actions">
									<button onclick={() => handleCompleteTask(task.id)} title="Mark complete">✓</button>
									<button onclick={() => handleSkipTask(task.id)} title="Skip task">~</button>
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	{/if}
</div>

<!-- Other goals (not active/focused) -->
{#if displayedGoalsList.length > 0}
<div class="goal-panel all-goals">
	<div class="all-goals-header" onclick={() => {}}>
		<span class="icon">🎯</span>
		<span class="title">{displayedGoalsList.length} Goal{displayedGoalsList.length !== 1 ? 's' : ''}</span>
	</div>

	{#each displayedGoalsList as goal (goal.id)}
		<div class="goal-card {goal.status}" onclick={() => toggleExpand(goal.id)}>
			<span class="status-dot" style="background-color: {statusDotColor(goal.status)}" title={statusLabel(goal.status)}></span>
			<span class="objective truncate">{goal.objective}</span>
			<button class="collapse-btn" type="button" onclick={(e) => { e.stopPropagation(); toggleExpand(goal.id); }} aria-label={expandedGoals.has(goal.id) ? 'Collapse' : 'Expand'}>
				<Icon name={expandedGoals.has(goal.id) ? 'chevron-up' : 'chevron-down'} size={10} />
			</button>
		</div>

		{#if expandedGoals.has(goal.id)}
			<div class="goal-card-expanded">
				<!-- Progress -->
				<div class="progress">
					<span>{goal.task_list.filter((t: GoalTask) => t.status === 'complete').length}/{goal.task_list.length} tasks ({Math.round(goal.task_list.length ? (goal.task_list.filter((t: GoalTask) => t.status === 'complete').length / goal.task_list.length) * 100 : 0)}%)</span>
					<div class="progress-bar">
						<div class="fill" style="width: {goal.task_list.length ? (goal.task_list.filter((t: GoalTask) => t.status === 'complete').length / goal.task_list.length) * 100 : 0}%"></div>
					</div>
				</div>

				<!-- Current Task -->
				{#if goal.current_task_id && goal.task_list.length > 0}
					<div class="current-task">
						<span class="label">Current:</span>
						<span>{goal.task_list.find(t => t.id === goal.current_task_id)?.title || 'Unknown'}</span>
					</div>
				{/if}

				<!-- Task List -->
				{#if goal.task_list.length > 0}
					<ul class="task-list">
						{#each goal.task_list as task (task.id)}
							<li class="{task.status}" data-task-id={task.id}>
								<span class="title">{task.title}</span>
								{#if task.evidence}<small title={task.evidence} class="evidence">📎</small>{/if}
								{#if task.status === 'skipped'}<em>(skipped)</em>{/if}
								{#if goal.status !== 'paused' && goal.status !== 'complete' && task.status !== 'complete'}
									<div class="actions">
										<button onclick={(e) => { e.stopPropagation(); handleGoalCompleteTask(goal.id, task.id); }} title="Mark complete">✓</button>
										<button onclick={(e) => { e.stopPropagation(); handleGoalSkipTask(goal.id, task.id); }} title="Skip task">~</button>
									</div>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}

				<!-- Delete goal (not for active/focused goals) -->
				{#if goal.status !== 'active'}
					<button type="button" class="action-btn delete" onclick={(e) => { e.stopPropagation(); handleDeleteGoal(goal.id); }}>🗑 Delete</button>
				{/if}
			</div>
		{/if}
	{/each}

	<!-- Create form (only shown when no active goal or always available) -->
	<div class="create-section">
		<form class="create-form" onsubmit={(e) => { e.preventDefault(); handleCreateGoal(); }}>
			<input
				bind:value={objectiveInput}
				class="goal-objective-input"
				placeholder="/goal — einen neuen Goal starten..."
				onfocus={(e) => e.target.select()}
			/>
			<button type="submit" disabled={isCreating || !objectiveInput.trim()}>
				{isCreating ? 'Creating...' : '+'}
			</button>
		</form>
		{#if error}<span class="error">{error}</span>{/if}
	</div>
</div>
{/if}

<!-- No goals at all — show create form -->
{:else}
<div class="goal-panel no-goal">
	<form class="create-form" onsubmit={(e) => { e.preventDefault(); handleCreateGoal(); }}>
		<input
			bind:value={objectiveInput}
			class="goal-objective-input"
			placeholder="/goal — einen neuen Goal starten..."
			onfocus={(e) => e.target.select()}
		/>
		<button type="submit" disabled={isCreating || !objectiveInput.trim()}>
			{isCreating ? 'Creating...' : '+ Start Goal'}
		</button>
	</form>

	{#if error}<span class="error">{error}</span>{/if}
</div>
{/if}

<style>
	.goal-panel {
		padding: 10px 12px;
		border-bottom: 1px solid var(--border-color, #333);
		font-size: 0.8rem;
		line-height: 1.4;
	}

	/* ── Active goal card ─────────────────────────── */
	.active-goal {
		background: rgba(59, 130, 246, 0.08);
		border-radius: 8px;
		margin-bottom: 8px;
	}

	.header {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		user-select: none;
		padding: 2px 0;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.objective {
		flex: 1;
		min-width: 0;
		font-weight: 600;
	}

	.collapse-btn {
		padding: 2px;
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		display: flex;
		align-items: center;
		opacity: 0.5;
		transition: opacity 0.1s;
	}

	.collapse-btn:hover {
		opacity: 1;
	}

	.progress {
		margin-top: 6px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		font-size: 0.75rem;
		color: #9ca3af;
	}

	.progress-bar {
		height: 4px;
		background: var(--bg-secondary, #2d3748);
		border-radius: 2px;
		flex: 1;
		min-width: 40px;
	}

	.progress-bar .fill {
		height: 100%;
		background: #3b82f6;
		border-radius: 2px;
		transition: width 0.3s ease;
	}

	.current-task {
		margin-top: 8px;
		padding: 4px 8px;
		background: var(--bg-secondary, #2d3748);
		border-radius: 4px;
		font-size: 0.75rem;
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.current-task .label {
		color: #9ca3af;
		margin-right: 2px;
	}

	.task-actions {
		display: flex;
		gap: 4px;
		margin-left: auto;
	}

	.task-actions button {
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		padding: 2px 4px;
		font-size: 0.75rem;
		opacity: 0.6;
		transition: opacity 0.1s;
	}

	.task-actions button:hover {
		opacity: 1;
	}

	.action-btn {
		margin-top: 8px;
		padding: 4px 12px;
		background: transparent;
		border: 1px solid var(--border-color, #333);
		color: inherit;
		cursor: pointer;
		font-size: 0.75rem;
		border-radius: 4px;
		transition: background 0.1s;
		width: 100%;
	}

	.action-btn:hover {
		background: var(--bg-secondary, #2d3748);
	}

	.task-section {
		margin-top: 8px;
	}

	.task-list {
		list-style: none;
		padding: 0;
		margin: 8px 0 0 0;
		max-height: 200px;
		overflow-y: auto;
		font-size: 0.75rem;
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

	.evidence {
		cursor: help;
	}

	/* ── All goals section (like Tasks.svelte) ─────── */
	.all-goals {
		background: var(--bg-secondary, #2d3748);
		border-radius: 10px;
		margin-top: 8px;
		padding: 8px 10px;
	}

	.all-goals-header {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		user-select: none;
		font-size: 0.75rem;
		color: #9ca3af;
		padding-bottom: 4px;
	}

	.all-goals-header .icon {
		font-size: 12px;
	}

	.all-goals-header .title {
		font-weight: 600;
	}

	.goal-card {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		border-radius: 6px;
		cursor: pointer;
		user-select: none;
		margin-bottom: 2px;
		font-size: 0.75rem;
		transition: background-color 0.1s;
	}

	.goal-card:hover {
		background: rgba(255, 255, 255, 0.06);
	}

	.goal-card.paused {
		opacity: 0.7;
	}

	.goal-card.complete {
		opacity: 0.5;
		text-decoration: line-through;
	}

	.goal-card .status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.goal-card .objective {
		flex: 1;
		min-width: 0;
		font-weight: 500;
		color: #e5e7eb;
	}

	.goal-card-expanded {
		padding: 8px 8px 4px 22px;
	}

	/* ── Create form ──────────────────────────────── */
	.create-section {
		margin-top: 8px;
	}

	.create-form {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.goal-objective-input {
		flex: 1;
		background: var(--bg-tertiary, #1f2937);
		border: 1px solid var(--border-color, #333);
		color: inherit;
		padding: 6px 8px;
		border-radius: 4px;
		font-size: 0.75rem;
		outline: none;
	}

	.goal-objective-input:focus {
		border-color: #3b82f6;
	}

	.create-form button {
		background: #3b82f6;
		border: none;
		color: white;
		padding: 6px 10px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.75rem;
		flex-shrink: 0;
		width: 32px;
	}

	.create-form button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error {
		color: #f87171;
		font-size: 0.7rem;
		margin-top: 4px;
		display: block;
	}

	.no-goal {
		text-align: center;
		padding: 16px 0;
		color: #9ca3af;
		font-size: 0.75rem;
	}

	.actions {
		display: flex;
		gap: 4px;
		margin-left: auto;
	}

	.actions button {
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		padding: 2px 4px;
		font-size: 0.7rem;
		opacity: 0.6;
		transition: opacity 0.1s;
	}

	.actions button:hover {
		opacity: 1;
	}

	.action-btn.delete {
		color: #f87171;
		border-color: rgba(248, 113, 113, 0.3);
	}

	.action-btn.delete:hover {
		background: rgba(248, 113, 113, 0.1);
	}
</style>

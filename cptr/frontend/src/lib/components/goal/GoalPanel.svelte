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
		type GoalState
	} from '$lib/stores/goal';

	let { oncreategoal }: { oncreategoal?: (description: string) => void } = $props();

	let state = $state<GoalState | null>(get(goal$));
	let objectiveInput = $state('');
	let isCreating = $state(false);
	let error = $state<string | null>(null);
	let collapsed = $state(true);
	let showCreateForm = $state(false);
	let showTasks = $state(false);

	// Load initial goal from store
	async function loadGoal() {
		try {
			const res = await fetch('/api/goal/active');
			if (res.ok) {
				const data: GoalState = await res.json();
				state = data;
			} else if (res.status !== 404) {
				console.warn('[GoalPanel] Failed to load active goal:', res.status);
			}
		} catch (e) {
			console.warn('[GoalPanel] Fetch error:', e);
		}
	}

	let progress = $derived(() => {
		if (!state || !state.task_list?.length) return 0;
		const completed = (state.task_list as GoalState['task_list']).filter((t: GoalTask) => t.status === 'complete').length;
		return Math.round((completed / state.task_list.length) * 100);
	});

	let completedCount = $derived(() => {
		if (!state || !state.task_list?.length) return 0;
		return (state.task_list as GoalState['task_list']).filter((t: GoalTask) => t.status === 'complete').length;
	});

	let totalCount = $derived(() => state?.task_list?.length ?? 0);

	async function handleCreateGoal() {
		if (!objectiveInput.trim()) return;
		isCreating = true;
		error = null;
		try {
			await createGoal(objectiveInput.trim());
			state = get(goal$);
			showCreateForm = false;
			objectiveInput = '';
		} catch (e: any) {
			error = e?.message || 'Failed to create goal';
		} finally {
			isCreating = false;
		}
	}

	async function handlePause() {
		try {
			await pauseGoal();
			state = get(goal$);
		} catch (e) {
			console.warn('[GoalPanel] Pause failed:', e);
		}
	}

	async function handleResume() {
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

	onMount(() => {
		loadGoal();
	});

	// Poll for updates every 30s when active goal exists
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	function startPolling() {
		stopPolling();
		const g = get(goal$);
		if (g && (g.status === 'active' || g.status === 'paused')) {
			pollTimer = setInterval(loadGoal, 30_000);
		}
	}

	function stopPolling() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	// React to store changes
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

	function toggleCollapse() {
		collapsed = !collapsed;
	}

	function focusObjectiveInput(e: MouseEvent) {
		e.preventDefault();
		showCreateForm = true;
		setTimeout(() => {
			const input = document.querySelector('.goal-objective-input') as HTMLInputElement;
			input?.focus();
		}, 50);
	}
</script>

{#if state && (state.task_list?.length || 0) > 0}
	<div class="goal-panel">
		<!-- Header: Status dot + Objective -->
		<div class="header" onclick={toggleCollapse} role="button" tabindex="0" aria-label="Toggle goal details">
			<span class="status-dot {state.status}" title={state.status}></span>
			<span class="objective truncate">{state.objective}</span>
			<button class="collapse-btn" type="button" onclick={(e) => { e.stopPropagation(); toggleCollapse(); }} aria-label={collapsed ? 'Expand' : 'Collapse'}>
				<Icon name={collapsed ? 'chevron-down' : 'chevron-up'} size={12} />
			</button>
		</div>

		{#if !collapsed}
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
					<button type="button" class="toggle-tasks" onclick={() => showTasks = !showTasks}>
						Tasks ({completedCount()}/{totalCount()}) <span>{showTasks ? '▾' : '▸'}</span>
					</button>
					{#if showTasks}
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
					{/if}
				</div>
			{/if}
		{/if}
	</div>

{:else if !isCreating && !state}
	<!-- No active goal — show create hint -->
	<div class="goal-panel no-goal">
		{#if showCreateForm}
			<form class="create-form" onsubmit={(e) => { e.preventDefault(); handleCreateGoal(); }}>
				<input
					bind:value={objectiveInput}
					class="goal-objective-input"
					placeholder="What should be achieved?"
					onfocus={(e) => e.target.select()}
				/>
				<button type="submit" disabled={isCreating || !objectiveInput.trim()}>
					{isCreating ? 'Creating...' : 'Start Goal'}
				</button>
			</form>
		{:else}
			<span class="hint" onclick={focusObjectiveInput} role="button" tabindex="0">/goal — einen neuen Goal starten</span>
		{/if}

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

	.header {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
		user-select: none;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.status-dot.active { background-color: #4ade80; }
	.status-dot.paused { background-color: #facc15; }
	.status-dot.blocked { background-color: #f87171; }
	.status-dot.complete { background-color: #60a5fa; }

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

	.toggle-tasks {
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 0.75rem;
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

	.no-goal {
		text-align: center;
		padding: 10px 0;
		color: #9ca3af;
		font-size: 0.75rem;
	}

	.hint {
		cursor: pointer;
		transition: color 0.1s;
	}

	.hint:hover {
		color: #60a5fa;
	}

	.create-form {
		display: flex;
		gap: 8px;
		margin-top: 4px;
		align-items: center;
	}

	.create-form input {
		flex: 1;
		background: var(--bg-secondary, #2d3748);
		border: 1px solid var(--border-color, #333);
		color: inherit;
		padding: 5px 8px;
		border-radius: 4px;
		font-size: 0.75rem;
		outline: none;
	}

	.create-form input:focus {
		border-color: #3b82f6;
	}

	.create-form button {
		background: #3b82f6;
		border: none;
		color: white;
		padding: 5px 10px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.75rem;
		flex-shrink: 0;
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
</style>

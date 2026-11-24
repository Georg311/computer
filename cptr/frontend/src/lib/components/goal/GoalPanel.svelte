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
		type GoalState,
		fetchLedger,
		getLedgerCache,
		fetchBudget,
		runAudit,
		recoverGoals,
		checkAutoContinue,
		type GoalLedgerEntry,
		type BudgetStatus,
		type AuditResult
	} from '$lib/stores/goal';

	let { oncreategoal }: { oncreategoal?: (description: string) => void } = $props();

	let state = $state<GoalState | null>(get(goal$));
	const allGoalsList = $derived(get(allGoals) as GoalState[]);

	let objectiveInput = $state('');
	let isCreating = $state(false);
	let error = $state<string | null>(null);

	// Expanded goals (by id) — show task list for each
	const expandedGoals = $state(new Set<string>());

	// Tab selection per goal_id: 'tasks' | 'ledger' | 'budget' | 'audit'
	const activeTab = new Map<string, string>();

	// Ledger loading state
	let ledgerLoading = $state(false);
	let ledgerEntries = $derived.by(() => {
		if (!state?.id) return [];
		return getLedgerCache(state.id) || [];
	});

	// Budget status for active goal
	let budgetStatus: BudgetStatus | null = $derived(null);

	// Audit result for active goal
	let auditResult: AuditResult | null = $derived(null);

	// Recovery state
	let isRecovering = $state(false);
	let recoveryMsg = $state<string | null>(null);

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
		activeTab.set(goalId, activeTab.get(goalId) || 'tasks'); // default to tasks tab
	}

	function switchTab(goalId: string, tab: string) {
		activeTab.set(goalId, tab);
		if (tab === 'ledger' && goalId === state?.id) loadLedgerForActive();
		if (tab === 'budget' && goalId === state?.id) loadBudgetForActive();
		if (tab === 'audit' && goalId === state?.id) runAuditForActive(goalId);
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

	async function loadLedgerForActive() {
		if (!state?.id) return;
		ledgerLoading = true;
		try {
			await fetchLedger(state.id, 50);
		} finally {
			ledgerLoading = false;
		}
	}

	async function loadBudgetForActive() {
		if (!state?.id) return;
		budgetStatus = await fetchBudget(state.id);
	}

	async function runAuditForActive(goalId: string) {
		auditResult = await runAudit(goalId);
	}

	async function handleRecovery() {
		isRecovering = true;
		recoveryMsg = null;
		try {
			const result = await recoverGoals();
			if (result) {
				recoveryMsg = `Recovered: ${result.recovered.length}, Skipped: ${result.skipped.length}`;
			} else {
				recoveryMsg = 'Recovery failed — check logs';
			}
		} catch (e) {
			console.warn('[GoalPanel] Recovery error:', e);
			recoveryMsg = 'Recovery error';
		} finally {
			isRecovering = false;
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

	function formatEventLabel(event: string): string {
		const labels: Record<string, string> = {
			goal_created: '🎯 Created',
			task_completed: '✅ Task Done',
			task_skipped: '⏭ Skipped',
			goal_paused: '⏸ Paused',
			goal_resumed: '▶ Resumed',
			goal_complete: '🏁 Complete',
			budget_limited: '💰 Budget Limit',
			auto_continue: '🔄 Auto-Continue',
			recovery_attempted: '🔧 Recovery',
			audit_run: '📋 Audit',
			task_created: '➕ Task Created'
		};
		return labels[event] || `• ${event}`;
	}

	function formatTimestamp(ts?: string): string {
		if (!ts) return '';
		try {
			const d = new Date(ts);
			return d.toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
		} catch {
			return ts;
		}
	}

	function formatBudget(num?: number): string {
		if (num === undefined || num === null) return '--';
		if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
		if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
		return String(num);
	}
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
		<!-- Tabs: Tasks | Ledger | Budget -->
		<div class="goal-tabs">
			<button class="tab {activeTab.get(state.id) === 'tasks' ? 'active' : ''}" onclick={() => switchTab(state.id, 'tasks')}>📋 Tasks</button>
			<button class="tab {activeTab.get(state.id) === 'ledger' ? 'active' : ''}" onclick={() => switchTab(state.id, 'ledger')}>📒 Ledger</button>
			<button class="tab {activeTab.get(state.id) === 'budget' ? 'active' : ''}" onclick={() => switchTab(state.id, 'budget')} title={state.token_budget ? `Budget: ${formatBudget(state.token_budget)}` : 'No budget set'}>💰 Budget</button>
		</div>

		<!-- Tasks Tab -->
		{#if activeTab.get(state.id) === 'tasks'}
			<div class="tab-content">
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

				<!-- Task List -->
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

				<!-- Quick Actions -->
				<div class="quick-actions">
					<button type="button" class="action-btn" onclick={() => runAuditForActive(state.id)} title="Run completion audit">📋 Audit</button>
					{#if auditResult && (activeTab.get(state.id) === 'audit')}
						<div class="audit-result {auditResult.is_complete ? 'ok' : ''}">
							<strong>Audit Result:</strong> {auditResult.message}
							{#if auditResult.is_complete}
								<button type="button" class="action-btn complete-goal" onclick={() => fetch('/api/goal/complete', { method: 'POST' }).then(() => loadActiveGoal())}>Mark Complete</button>
							{/if}
						</div>
					{/if}
				</div>
			</div>

		<!-- Ledger Tab -->
		{:else if activeTab.get(state.id) === 'ledger'}
			<div class="tab-content">
				{#if ledgerLoading}
					<p class="loading">Loading ledger...</p>
				{:else if ledgerEntries.length > 0}
					<ul class="ledger-list">
						{#each ledgerEntries as entry (entry._id || entry.timestamp + '-' + entry.event)}
							<li class="ledger-entry" title={JSON.stringify(entry.details)}>
								<span class="event-icon">{formatEventLabel(entry.event).split(' ')[0]}</span>
								<span class="event-label">{formatEventLabel(entry.event)}</span>
								<span class="timestamp">{formatTimestamp(entry.timestamp)}</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="empty">No ledger entries yet.</p>
				{/if}
			</div>

		<!-- Budget Tab -->
		{:else if activeTab.get(state.id) === 'budget'}
			<div class="tab-content">
				{#if budgetStatus}
					<div class="budget-info">
						<div class="budget-row">
							<span class="label">Budget:</span>
							<span>{formatBudget(budgetStatus.token_budget)}</span>
						</div>
						<div class="budget-row">
							<span class="label">Used:</span>
							<span>{formatBudget(budgetStatus.token_usage)}</span>
						</div>
						<div class="budget-row {budgetStatus.budget_exceeded ? 'warning' : ''}">
							<span class="label">Remaining:</span>
							<span>{formatBudget(budgetStatus.remaining)}</span>
						</div>
						{#if budgetStatus.budget_exceeded}
							<div class="budget-alert">⚠️ Budget limit reached — goal paused</div>
						{/if}
					</div>
				{:else}
					<p class="empty">No budget data available.</p>
				{/if}
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

	/* ── Tabs ─────────────────────────────────────── */
	.goal-tabs {
		display: flex;
		gap: 4px;
		margin-top: 8px;
		padding-bottom: 6px;
		border-bottom: 1px solid var(--border-color, #333);
	}

	.tab {
		background: transparent;
		border: none;
		color: #9ca3af;
		cursor: pointer;
		font-size: 0.75rem;
		padding: 4px 8px;
		border-radius: 4px;
		transition: all 0.1s;
	}

	.tab:hover {
		background: rgba(255, 255, 255, 0.06);
		color: inherit;
	}

	.tab.active {
		background: var(--bg-secondary, #2d3748);
		color: inherit;
		font-weight: 600;
	}

	.tab-content {
		padding-top: 8px;
	}

	/* ── Progress ─────────────────────────────────── */
	.progress {
		margin-bottom: 6px;
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
		margin-top: 4px;
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

	/* ── Buttons ──────────────────────────────────── */
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
	}

	.action-btn:hover {
		background: var(--bg-secondary, #2d3748);
	}

	.action-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.action-btn.pause { color: #facc15; border-color: rgba(250, 204, 21, 0.3); }
	.action-btn.resume { color: #4ade80; border-color: rgba(74, 222, 128, 0.3); }
	.action-btn.recover { color: #60a5fa; border-color: rgba(96, 165, 250, 0.3); }
	.action-btn.complete-goal { background: rgba(74, 222, 128, 0.1); color: #4ade80; margin-left: auto; }

	/* ── Task List ────────────────────────────────── */
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

	.evidence { cursor: help; }

	.actions { display: flex; gap: 4px; margin-left: auto; }
	.actions button { background: transparent; border: none; color: inherit; cursor: pointer; padding: 2px 4px; font-size: 0.7rem; opacity: 0.6; transition: opacity 0.1s; }
	.actions button:hover { opacity: 1; }

	/* ── Ledger ───────────────────────────────────── */
	.loading, .empty { color: #9ca3af; font-size: 0.8rem; padding: 8px 0; text-align: center; }

	.ledger-list { list-style: none; padding: 0; margin: 0; max-height: 250px; overflow-y: auto; }

	.ledger-entry {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 6px;
		border-radius: 4px;
		margin-bottom: 2px;
		font-size: 0.75rem;
	}

	.ledger-entry:hover { background: rgba(255, 255, 255, 0.03); }

	.event-icon { font-size: 1em; width: 24px; text-align: center; flex-shrink: 0; }
	.event-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #e5e7eb; }
	.timestamp { font-size: 0.65rem; color: #9ca3af; flex-shrink: 0; }

	/* ── Budget ───────────────────────────────────── */
	.budget-info { padding: 8px 0; display: flex; flex-direction: column; gap: 4px; }

	.budget-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 2px 0;
		font-size: 0.8rem;
	}

	.budget-row .label { color: #9ca3af; }
	.budget-row.warning { color: #facc15; font-weight: 600; }

	.budget-alert { background: rgba(250, 204, 21, 0.1); border: 1px solid rgba(250, 204, 21, 0.3); padding: 6px 8px; border-radius: 4px; margin-top: 8px; font-size: 0.75rem; color: #facc15; }

	/* ── Audit Result ─────────────────────────────── */
	.audit-result { background: rgba(74, 222, 128, 0.08); border: 1px solid rgba(74, 222, 128, 0.2); padding: 6px 8px; border-radius: 4px; margin-top: 8px; font-size: 0.75rem; display: flex; align-items: center; gap: 8px; }
	.audit-result.ok { background: rgba(74, 222, 128, 0.12); border-color: rgba(74, 222, 128, 0.3); color: #4ade80; }

	/* ── Recovery Section ─────────────────────────── */
	.recovery-section { margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-color, #333); display: flex; align-items: center; gap: 8px; }

	.recovery-msg { font-size: 0.7rem; color: #9ca3af; margin-left: auto; }

	/* ── Quick Actions ────────────────────────────── */
	.quick-actions { display: flex; gap: 4px; margin-top: 8px; flex-wrap: wrap; align-items: center; }

	/* ── All goals section (like Tasks.svelte) ─────── */
	.all-goals { background: var(--bg-secondary, #2d3748); border-radius: 10px; margin-top: 8px; padding: 8px 10px; }

	.all-goals-header { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; font-size: 0.75rem; color: #9ca3af; padding-bottom: 4px; }
	.all-goals-header .icon { font-size: 12px; }
	.all-goals-header .title { font-weight: 600; }

	.goal-card { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: pointer; user-select: none; margin-bottom: 2px; font-size: 0.75rem; transition: background-color 0.1s; }
	.goal-card:hover { background: rgba(255, 255, 255, 0.06); }
	.goal-card.paused { opacity: 0.7; }
	.goal-card.complete { opacity: 0.5; text-decoration: line-through; }

	.goal-card .status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
	.goal-card .objective { flex: 1; min-width: 0; font-weight: 500; color: #e5e7eb; }

	.goal-card-expanded { padding: 8px 8px 4px 22px; }

	/* ── Create form ──────────────────────────────── */
	.create-section { margin-top: 8px; }

	.create-form { display: flex; gap: 8px; align-items: center; }

	.goal-objective-input { flex: 1; background: var(--bg-tertiary, #1f2937); border: 1px solid var(--border-color, #333); color: inherit; padding: 6px 8px; border-radius: 4px; font-size: 0.75rem; outline: none; }
	.goal-objective-input:focus { border-color: #3b82f6; }

	.create-form button { background: #3b82f6; border: none; color: white; padding: 6px 10px; border-radius: 4px; cursor: pointer; font-size: 0.75rem; flex-shrink: 0; width: 32px; }
	.create-form button:disabled { opacity: 0.5; cursor: not-allowed; }

	.error { color: #f87171; font-size: 0.7rem; margin-top: 4px; display: block; }

	.no-goal { text-align: center; padding: 16px 0; color: #9ca3af; font-size: 0.75rem; }
</style>

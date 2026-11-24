<script lang="ts">
	import type { GoalTask } from '$lib/stores/goal';

	let { tasks, depth = 0, onComplete, onSkip }: { 
		tasks: GoalTask[]; 
		depth?: number; 
		onComplete?: (taskId: string) => void;
		onSkip?: (taskId: string, reason?: string) => void;
	} = $props();

	let status = '';
	const expandedTasks = new Map<string, boolean>();
	
	function toggleExpand(taskId: string) {
		expandedTasks.set(taskId, !expandedTasks.get(taskId));
	}

	function hasSubtasks(task: GoalTask): boolean {
		return task.subtasks && task.subtasks.length > 0;
	}
</script>

{#if tasks && tasks.length > 0}
	<ul class="subtask-tree" style="--depth: {depth};">
		{#each tasks as task (task.id)}
			<li class="task-item {task.status}" data-task-id={task.id}>
				<span class="title">{task.title}</span>

				{#if task.evidence}
					<small title={task.evidence} class="evidence">📎</small>
				{/if}

				{#if task.status === 'skipped'}
					<em>(skipped)</em>
				{/if}

				{#if hasSubtasks(task)}
					<button type="button" class="expand-btn" onclick={() => toggleExpand(task.id)}>
						<span>{expandedTasks.get(task.id) ? '▾' : '▸'}</span>
					</button>

					{#if expandedTasks.get(task.id)}
						<div class="subtask-list">
							<Subtasks tasks={task.subtasks || []} depth={depth + 1} onComplete={onComplete} onSkip={onSkip} />
						</div>
					{/if}
				{/if}

				{#if task.status !== 'complete' && status !== 'paused'}
					<div class="actions">
						<button onclick={() => onComplete?.(task.id)} title="Mark complete">✓</button>
						<button onclick={() => onSkip?.(task.id, 'Skipped by user')} title="Skip task">~</button>
					</div>
				{/if}
			</li>
		{/each}
	</ul>
{/if}

<style>
	.subtask-tree { list-style: none; padding: 0; margin: 0; }
	.task-item { display: flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; margin-bottom: 2px; }
	.task-item.pending { background: rgba(255, 255, 255, 0.03); }
	.task-item.complete { opacity: 0.6; text-decoration: line-through; }
	.task-item.skipped { color: #facc15; }
	.expand-btn { background: transparent; border: none; color: inherit; cursor: pointer; padding: 2px; font-size: 0.7rem; display: flex; align-items: center; }
	.subtask-list { list-style: none; padding-left: calc(16px + var(--depth, 0) * 16px); margin-top: 2px; border-left: 1px solid rgba(255, 255, 255, 0.1); }
	.title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.evidence { cursor: help; font-size: 0.9em; }
	.actions { display: flex; gap: 4px; margin-left: auto; }
	.actions button { background: transparent; border: none; color: inherit; cursor: pointer; padding: 2px 4px; font-size: 0.7rem; opacity: 0.6; transition: opacity 0.1s; }
	.actions button:hover { opacity: 1; }
</style>

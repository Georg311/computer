/** @filegoal */
import { writable, get } from 'svelte/store';

export interface GoalTask {
	id: string;
	title: string;
	status: 'pending' | 'complete' | 'skipped';
	evidence?: string;
}

export interface GoalState {
	id: string;
	objective: string;
	status: 'active' | 'paused' | 'blocked' | 'complete';
	current_task_id?: string;
	task_list: GoalTask[];
	created_at?: string;
	updated_at?: string;
}

const goal = writable<GoalState | null>(null);
export const focusedGoal = goal;

// All goals store — separate from the single focused goal
const allGoalsStore = writable<GoalState[]>([]);
export const allGoals = allGoalsStore;

export function setGoal(g: GoalState) {
	goal.set(g);
}

export function clearGoal() {
	goal.set(null);
}

/** Fetch the active goal and update store. */
export async function fetchActiveGoal(): Promise<void> {
	try {
		const res = await fetch('/api/goal/active');
		if (res.ok) {
			const data: GoalState = await res.json();
			goal.set(data);
		} else if (res.status !== 404) {
			console.warn('[goal] Failed to load active goal:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Fetch error:', e);
	}
}

/** Create a new goal from user description. */
export async function createGoal(description: string): Promise<void> {
	try {
		const res = await fetch('/api/goal/create', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ description })
		});
		if (!res.ok) {
			const err = await res.json();
			throw new Error(err.detail || 'Failed to create goal');
		}
		await fetchActiveGoal();
	} catch (e) {
		console.warn('[goal] Create error:', e);
		throw e;
	}
}

/** Confirm the current goal and request task plan. */
export async function confirmGoal(): Promise<void> {
	try {
		const res = await fetch('/api/goal/confirm', { method: 'POST' });
		if (!res.ok) {
			console.warn('[goal] Confirm error:', res.status);
		} else {
			await fetchActiveGoal();
		}
	} catch (e) {
		console.warn('[goal] Confirm error:', e);
	}
}

/** Pause the active goal. */
export async function pauseGoal(): Promise<void> {
	try {
		const res = await fetch('/api/goal/pause', { method: 'POST' });
		if (res.ok) {
			await fetchActiveGoal();
		} else {
			console.warn('[goal] Pause error:', res.status);
		}
	} catch (e) {
		console.warn('[goal] Pause error:', e);
	}
}

/** Resume the active goal. */
export async function resumeGoal(): Promise<void> {
	try {
		const res = await fetch('/api/goal/resume', { method: 'POST' });
		if (res.ok) {
			await fetchActiveGoal();
		} else {
			console.warn('[goal] Resume error:', res.status);
		}
	} catch (e) {
		console.warn('[goal] Resume error:', e);
	}
}

/** Mark a task as complete. */
export async function completeTask(taskId: string, evidence?: string): Promise<void> {
	try {
		const res = await fetch('/api/goal/task/complete', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ task_id: taskId, evidence })
		});
		if (res.ok) {
			await fetchActiveGoal();
		} else if (res.status === 404 || res.status === 400) {
			// Fallback to old endpoint format for MVP compatibility
			const body = JSON.stringify({ description: evidence || '', task_id: taskId });
			const res2 = await fetch('/api/goal/complete-task', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body
			});
			if (res2.ok) {
				await fetchActiveGoal();
			} else {
				console.warn('[goal] Complete task error:', res2.status);
			}
		} else {
			console.warn('[goal] Complete task error:', res.status);
		}
	} catch (e) {
		console.warn('[goal] Complete task error:', e);
	}
}

/** Fetch all goals and update the allGoals store. */
export async function fetchAllGoals(): Promise<void> {
	try {
		const res = await fetch('/api/goal/all');
		if (res.ok) {
			const data = await res.json();
			allGoalsStore.set(data.goals || []);
		} else if (res.status !== 404) {
			console.warn('[goal] Failed to load all goals:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Fetch error:', e);
	}
}

/** Skip a task. */
export async function skipTask(taskId: string, reason?: string): Promise<void> {
	try {
		const res = await fetch('/api/goal/skip-task', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ task_id: taskId, evidence: reason || '' })
		});
		if (res.ok) {
			await fetchActiveGoal();
		} else {
			console.warn('[goal] Skip task error:', res.status);
		}
	} catch (e) {
		console.warn('[goal] Skip task error:', e);
	}
}

export const goal$ = goal;

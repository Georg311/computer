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
	token_budget?: number;
	token_usage?: number;
	auto_continue?: boolean;
	sisyphus_mode?: boolean;
	pause_reason?: string;
}

// ── pi-goal-x types ───────────────────────────────────────

export interface GoalLedgerEntry {
	timestamp: string;
	event: string;
	details?: Record<string, unknown>;
	_id?: string; // persisted ID from ledger file
}

export interface LedgerResponse {
	goal_id: string;
	entries: GoalLedgerEntry[];
	count: number;
}

export interface BudgetStatus {
	goal_id: string;
	token_budget: number | null;
	token_usage: number;
	remaining: number;
	budget_exceeded: boolean;
}

export interface AuditResult {
	goal_id: string;
	is_complete: boolean;
	pending_tasks: number;
	message: string;
	ok?: boolean;
}

export interface AutoContinueResult {
	should_continue: boolean;
	goal_id?: string;
	reason?: string;
	next_task_title?: string;
}

export interface RecoveryResult {
	ok: boolean;
	recovered: string[];
	skipped: string[];
}

const goal = writable<GoalState | null>(null);
export const focusedGoal = goal;

// All goals store — separate from the single focused goal
const allGoalsStore = writable<GoalState[]>([]);
export const allGoals = allGoalsStore;

// Ledger cache per goal_id
const ledgerCache = new Map<string, GoalLedgerEntry[]>();
export function getLedgerCache(goalId: string): GoalLedgerEntry[] {
	return ledgerCache.get(goalId) || [];
}
export function clearLedgerCache() {
	ledgerCache.clear();
}

// Budget status for active goal (cached)
const budgetStatus = writable<BudgetStatus | null>(null);
export const budget$ = budgetStatus;

// Audit result cache per goal_id
const auditCache = new Map<string, AuditResult>();
export function getAuditCache(goalId: string): AuditResult | undefined {
	return auditCache.get(goalId);
}

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

// ── pi-goal-x API functions ───────────────────────────────

/** Fetch ledger entries for a goal. */
export async function fetchLedger(goalId: string, limit = 100): Promise<GoalLedgerEntry[]> {
	try {
		const res = await fetch(`/api/goal/ledger/${goalId}?limit=${limit}`);
		if (res.ok) {
			const data: LedgerResponse = await res.json();
			ledgerCache.set(goalId, data.entries || []);
			return data.entries || [];
		} else if (res.status !== 404) {
			console.warn('[goal] Failed to load ledger:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Ledger fetch error:', e);
	}
	return [];
}

/** Append an event to the goal ledger. */
export async function appendLedgerEntry(
	goalId: string,
	eventType: string,
	details?: Record<string, unknown>
): Promise<boolean> {
	try {
		const res = await fetch(`/api/goal/ledger/${goalId}`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ event: eventType, details })
		});
		if (res.ok) {
			// Refresh ledger cache
			await fetchLedger(goalId);
			return true;
		} else {
			console.warn('[goal] Ledger append error:', res.status);
		}
	} catch (e) {
		console.warn('[goal] Ledger append error:', e);
	}
	return false;
}

/** Fetch token budget status for a goal. */
export async function fetchBudget(goalId: string): Promise<BudgetStatus | null> {
	try {
		const res = await fetch(`/api/goal/budget/${goalId}`);
		if (res.ok) {
			const data: BudgetStatus = await res.json();
			budget$.set(data);
			return data;
		} else if (res.status !== 404) {
			console.warn('[goal] Failed to load budget:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Budget fetch error:', e);
	}
	return null;
}

/** Track token usage for a task. */
export async function trackTokens(
	goalId: string,
	usage: number
): Promise<{ ok?: boolean; budget_exceeded?: boolean }> {
	try {
		const res = await fetch('/api/goal/task/track-tokens', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ goal_id: goalId, usage })
		});
		if (res.ok) {
			const data = await res.json();
			budget$.set(data);
			return data;
		} else if (res.status !== 404) {
			console.warn('[goal] Token tracking error:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Token tracking error:', e);
	}
	return {};
}

/** Check auto-continue for focused goal. */
export async function checkAutoContinue(): Promise<AutoContinueResult | null> {
	try {
		const res = await fetch('/api/goal/auto-continue');
		if (res.ok) {
			const data: AutoContinueResult = await res.json();
			return data;
		} else if (res.status !== 404) {
			console.warn('[goal] Auto-continue check error:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Auto-continue check error:', e);
	}
	return null;
}

/** Run audit on a goal. */
export async function runAudit(goalId: string): Promise<AuditResult | null> {
	try {
		const res = await fetch(`/api/goal/audit/${goalId}`, { method: 'POST' });
		if (res.ok) {
			const data: AuditResult = await res.json();
			auditCache.set(goalId, data);
			return data;
		} else if (res.status !== 404) {
			console.warn('[goal] Audit error:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Audit error:', e);
	}
	return null;
}

/** Recover corrupt goal files. */
export async function recoverGoals(): Promise<RecoveryResult | null> {
	try {
		const res = await fetch('/api/goal/recover', { method: 'POST' });
		if (res.ok) {
			const data: RecoveryResult = await res.json();
			return data;
		} else if (res.status !== 404) {
			console.warn('[goal] Recovery error:', res.status, res.statusText);
		}
	} catch (e) {
		console.warn('[goal] Recovery error:', e);
	}
	return null;
}

export const goal$ = goal;

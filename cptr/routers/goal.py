"""Goal management API endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from cptr.utils.config import AuthResult, check_access
from cptr.utils.goals import (
    GoalRecord,
    GoalStatus,
    GoalStateManager,
    Task,
    TaskStatus,
    GoalLedger,
    GoalBudgetManager,
    GoalRecoveryManager,
    GoalAutoContinueManager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/goal", tags=["goal"])
COOKIE_NAME = "cptr_session"


def _get_auth(request: Request) -> AuthResult:
    token = request.cookies.get(COOKIE_NAME)
    client_host = request.client.host if request.client else "127.0.0.1"
    auth = check_access(client_host=client_host, jwt_token=token)
    if not auth or not auth.user_id:
        raise HTTPException(status_code=401, detail="authentication required")
    return auth


def _get_user(request: Request) -> str:
    return _get_auth(request).user_id or ""


class GoalCreateRequest(BaseModel):
    description: str  # User's goal description


class TaskCompleteRequest(BaseModel):
    task_id: str
    evidence: str = ""


class TaskCreateRequest(BaseModel):
    goal_id: str | None = None  # If not provided, uses focused goal
    title: str
    description: str = ""


# ── Core Goal Endpoints ────────────────────────────────────────

@router.post("/create")
async def create_goal(request: Request, body: GoalCreateRequest):
    """POST /api/goal/create — Create a new goal from user description."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if state.get_focused_goal():
        raise HTTPException(status_code=409, detail="A goal is already in progress")

    goal_id = str(uuid.uuid4())
    draft = GoalRecord(
        id=goal_id,
        objective=body.description.strip(),
        status=GoalStatus.ACTIVE,
        auto_continue=False,
        sisyphus_mode=False,
    )

    state.persistence.save_goal(draft)
    return {"goal_id": goal_id, "status": "draft", "objective": body.description}


@router.post("/confirm")
async def confirm_goal(request: Request):
    """POST /api/goal/confirm — Confirm draft and request task plan."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    goal = state.get_focused_goal()
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal")

    goal.auto_continue = True
    goal.updated_at = datetime.now().isoformat()
    state.persistence.save_goal(goal)

    return {
        "status": "confirmed",
        "message": "Generating task plan...",
    }


@router.get("/active")
async def get_active_goal(request: Request):
    """GET /api/goal/active — Get the currently focused goal (for Dashboard)."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    goal = state.get_focused_goal()
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal")

    return {
        "id": goal.id,
        "objective": goal.objective,
        "status": goal.status.value,
        "current_task_id": goal.current_task_id,
        "task_list": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "evidence": t.evidence or "",
            }
            for t in goal.task_list
        ],
    }


@router.post("/pause")
async def pause_goal(request: Request):
    """POST /api/goal/pause — Pause the focused goal."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    goal = state.goals_by_id[state.focused_goal_id]
    goal.status = GoalStatus.PAUSED
    goal.pause_reason = "User paused"
    goal.updated_at = datetime.now().isoformat()
    state.persistence.save_goal(goal)
    return {"ok": True, "status": "paused"}


@router.post("/resume")
async def resume_goal(request: Request):
    """POST /api/goal/resume — Resume the focused goal (manual continuation)."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    goal = state.goals_by_id[state.focused_goal_id]
    goal.status = GoalStatus.ACTIVE
    goal.pause_reason = None
    goal.updated_at = datetime.now().isoformat()
    state.persistence.save_goal(goal)

    pending_tasks = [t for t in goal.task_list if t.status == TaskStatus.PENDING]
    followup = f"[GOAL CONTINUATION] Goal: {goal.objective}\n"
    if pending_tasks:
        next_task = pending_tasks[0]
        followup += f"Next task: {next_task.title}"

    return {"ok": True, "status": "active", "followup": followup}


@router.post("/complete")
async def complete_goal(request: Request):
    """POST /api/goal/complete — Mark the focused goal as complete."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    goal = state.goals_by_id[state.focused_goal_id]

    pending_tasks = [t for t in goal.task_list if t.status != TaskStatus.COMPLETE and t.status != TaskStatus.SKIPPED]
    if pending_tasks:
        raise HTTPException(status_code=409, detail=f"Cannot complete goal: {len(pending_tasks)} tasks still pending")

    goal.status = GoalStatus.COMPLETE
    goal.updated_at = datetime.now().isoformat()
    state.save_all_goals()

    return {"ok": True, "status": "complete"}


# ── Task Endpoints ─────────────────────────────────────────────

@router.post("/task/complete")
async def complete_task_with_evidence(request: Request, body: TaskCompleteRequest):
    """POST /api/goal/task/complete — Mark a task as complete with optional evidence."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    goal = state.goals_by_id[state.focused_goal_id]
    task = next((t for t in goal.task_list if t.id == body.task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {body.task_id} not found")

    task.status = TaskStatus.COMPLETE
    task.completed_at = datetime.now().isoformat()
    task.evidence = body.evidence

    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, body.task_id)
    goal.updated_at = datetime.now().isoformat()

    state.save_all_goals()
    return {
        "ok": True,
        "task": task.title,
        "status": task.status.value,
        "next_task_id": goal.current_task_id,
    }


@router.post("/skip-task")
async def skip_task(request: Request, body: TaskCompleteRequest):
    """POST /api/goal/skip-task — Skip a task (mark as skipped)."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    goal = state.goals_by_id[state.focused_goal_id]
    task = next((t for t in goal.task_list if t.id == body.task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {body.task_id} not found")

    task.status = TaskStatus.SKIPPED
    task.skip_reason = body.evidence
    task.completed_at = datetime.now().isoformat()

    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, body.task_id)
    goal.updated_at = datetime.now().isoformat()

    state.save_all_goals()
    return {
        "ok": True,
        "task": task.title,
        "status": task.status.value,
        "next_task_id": goal.current_task_id,
    }


@router.post("/task/create")
async def create_task(request: Request, body: TaskCreateRequest):
    """POST /api/goal/task/create — Create a new task for a goal."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    if body.goal_id and body.goal_id in state.goals_by_id:
        goal = state.goals_by_id[body.goal_id]
    elif state.focused_goal_id and state.focused_goal_id in state.goals_by_id:
        goal = state.goals_by_id[state.focused_goal_id]
    else:
        raise HTTPException(status_code=404, detail="No active goal found")

    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        title=body.title.strip(),
        status=TaskStatus.PENDING,
    )

    goal.task_list.append(task)

    if not goal.current_task_id:
        goal.current_task_id = task_id

    goal.updated_at = datetime.now().isoformat()
    state.save_all_goals()

    return {
        "task_id": task_id,
        "goal_id": goal.id,
        "title": body.title.strip(),
        "status": "pending",
    }


# ── Query Endpoints ────────────────────────────────────────────

@router.get("/all")
async def get_all_goals(request: Request):
    """GET /api/goal/all — Get all goals with full task lists, sorted by status/date."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    priority = {GoalStatus.ACTIVE: 0, GoalStatus.PAUSED: 1, GoalStatus.BLOCKED: 2, GoalStatus.COMPLETE: 3}
    sorted_goals = sorted(state.goals_by_id.values(), key=lambda g: (priority.get(g.status, 99), g.created_at or ""))

    return {
        "goals": [
            {
                "id": g.id,
                "objective": g.objective,
                "status": g.status.value,
                "created_at": g.created_at,
                "updated_at": g.updated_at,
                "current_task_id": g.current_task_id,
                "task_list": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status.value,
                        "evidence": t.evidence or "",
                    }
                    for t in g.task_list
                ],
            }
            for g in sorted_goals
        ],
    }


@router.get("/list")
async def list_goals(request: Request):
    """GET /api/goal/list — List all active goals (not just focused)."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    return {
        "goals": [
            {
                "id": g.id,
                "objective": g.objective,
                "status": g.status.value,
                "created_at": g.created_at,
                "task_count": len(g.task_list),
            }
            for g in state.goals_by_id.values()
        ],
    }


@router.get("/{goal_id}")
async def get_goal(request: Request, goal_id: str):
    """GET /api/goal/{goal_id} — Get a specific goal by ID."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = state.goals_by_id[goal_id]
    return {
        "id": goal.id,
        "objective": goal.objective,
        "status": goal.status.value,
        "current_task_id": goal.current_task_id,
        "task_list": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description or "",
                "status": t.status.value,
                "evidence": t.evidence or "",
            }
            for t in goal.task_list
        ],
    }


@router.delete("/{goal_id}")
async def delete_goal(request: Request, goal_id: str):
    """DELETE /api/goal/{goal_id} — Delete a specific goal."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = state.goals_by_id[goal_id]
    if goal.status == GoalStatus.ACTIVE and state.focused_goal_id == goal_id:
        raise HTTPException(status_code=409, detail="Cannot delete active focused goal")

    state.persistence.delete_goal(goal_id)

    return {"ok": True, "deleted": goal_id}


# ── pi-goal-x New Features ─────────────────────────────────────

@router.get("/ledger/{goal_id}")
async def get_ledger(request: Request, goal_id: str, limit: int = Query(100)):
    """GET /api/goal/ledger/{goal_id} — Read the last N ledger entries."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    ledger = GoalLedger(state.persistence.goal_dir)
    entries = ledger.read_lines(goal_id, limit)

    return {
        "goal_id": goal_id,
        "entries": entries,
        "count": len(entries),
    }


@router.post("/ledger/{goal_id}")
async def append_ledger_entry(request: Request, goal_id: str):
    """POST /api/goal/ledger/{goal_id} — Append an event to the goal ledger."""
    _get_user(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = body.get("event", "goal_created")
    details = body.get("details", {})

    state = GoalStateManager()
    state.load_all_active_goals()

    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    ledger = GoalLedger(state.persistence.goal_dir)
    ledger.append(goal_id, event_type, details)

    return {"ok": True, "goal_id": goal_id, "event": event_type}


@router.get("/budget/{goal_id}")
async def get_goal_budget(request: Request, goal_id: str):
    """GET /api/goal/budget/{goal_id} — Check token budget status."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = state.goals_by_id[goal_id]
    budget_mgr = GoalBudgetManager()

    return {
        "goal_id": goal.id,
        "token_budget": goal.token_budget,
        "token_usage": goal.token_usage,
        "remaining": budget_mgr.remaining_tokens(goal),
        "budget_exceeded": budget_mgr.check_budget_exceeded(goal),
    }


@router.post("/task/track-tokens")
async def track_tokens(request: Request):
    """POST /api/goal/task/track-tokens — Track token usage for budget management."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    goal_id = raw.get("goal_id", "")
    usage = int(raw.get("usage", 0)) if isinstance(raw.get("usage"), (int, float)) else 0

    if not goal_id:
        raise HTTPException(status_code=400, detail="goal_id is required")

    goal = state.goals_by_id.get(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    budget_mgr = GoalBudgetManager()
    exceeded = budget_mgr.track_tokens(goal, usage)
    goal.updated_at = datetime.now().isoformat()
    state.save_all_goals()

    if exceeded:
        ledger = GoalLedger(state.persistence.goal_dir)
        ledger.append(goal_id, "budget_limited", {"usage": usage, "total": goal.token_usage})

    return {
        "ok": True,
        "goal_id": goal.id,
        "token_usage": goal.token_usage,
        "token_budget": goal.token_budget,
        "remaining": budget_mgr.remaining_tokens(goal),
        "budget_exceeded": exceeded,
    }


@router.get("/auto-continue")
async def get_auto_continue(request: Request):
    """GET /api/goal/auto-continue — Check if focused goal should auto-continue."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    ac_mgr = GoalAutoContinueManager(state)
    result = ac_mgr.should_continue()

    return result


@router.post("/recover")
async def recover_goals(request: Request):
    """POST /api/goal/recover — Scan and repair corrupt goal files."""
    _get_user(request)

    persistence = GoalStateManager().persistence
    manager = GoalRecoveryManager(persistence)
    result = manager.recover_all()

    return {
        "ok": True,
        "recovered": result.get("recovered", []),
        "skipped": result.get("skipped", []),
    }


@router.post("/audit/{goal_id}")
async def run_goal_audit(request: Request, goal_id: str):
    """POST /api/goal/audit/{goal_id} — Run the completion auditor for a goal."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Audit runs synchronously — checks task completion and goal status consistency
    audit_result = _run_audit(goal_id, state)

    return {
        "ok": True,
        **audit_result,
    }


def _run_audit(goal_id: str, state: GoalStateManager) -> dict:
    """Run the completion auditor for a goal."""
    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = state.goals_by_id[goal_id]
    tasks = goal.task_list

    # Check all tasks are completed
    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    incomplete = len(pending)

    is_complete = False
    message = ""

    if not pending:
        is_complete = True
        message = "All tasks complete — goal can be marked as complete"
    else:
        message = f"{incomplete} task(s) still pending"

    return {
        "goal_id": goal.id,
        "is_complete": is_complete,
        "pending_tasks": incomplete,
        "message": message,
    }


# ── Legacy/Deprecated Endpoints (keep for compat) ──────────────

@router.post("/complete-task")
async def complete_task(request: Request, body: GoalCreateRequest):
    """POST /api/goal/complete-task — Mark a task as complete.

    DEPRECATED: Use POST /api/goal/task/complete instead.
    """
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    task_id = getattr(body, 'task_id', None) or getattr(body, 'description', '')

    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    goal = state.goals_by_id[state.focused_goal_id]
    task = next((t for t in goal.task_list if t.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    task.status = TaskStatus.COMPLETE
    task.completed_at = datetime.now().isoformat()

    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, task_id)
    goal.updated_at = datetime.now().isoformat()

    state.save_all_goals()
    return {
        "ok": True,
        "task": task.title,
        "status": task.status.value,
        "next_task_id": goal.current_task_id,
    }


@router.post("/complete-task-with-tokens")
async def complete_task_with_tokens(request: Request, body: TaskCompleteRequest):
    """POST /api/goal/complete-task — Mark task complete with token tracking.

    DEPRECATED: Use POST /api/goal/task/track-tokens after completion.
    """
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    goal = state.goals_by_id[state.focused_goal_id]
    task = next((t for t in goal.task_list if t.id == body.task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {body.task_id} not found")

    # Track tokens (simulated usage per task completion)
    token_usage = len(body.evidence or "") * 10
    budget_mgr = GoalBudgetManager()
    exceeded = budget_mgr.track_tokens(goal, token_usage)
    goal.updated_at = datetime.now().isoformat()
    state.save_all_goals()

    if exceeded:
        goal.status = GoalStatus.PAUSED
        goal.pause_reason = "Budget limit reached"
        ledger = GoalLedger(state.persistence.goal_dir)
        ledger.append(goal.id, "budget_limited", {"usage": token_usage, "total": goal.token_usage})

    task.status = TaskStatus.COMPLETE
    task.completed_at = datetime.now().isoformat()
    task.evidence = body.evidence

    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, body.task_id)
    goal.updated_at = datetime.now().isoformat()

    state.save_all_goals()

    return {
        "ok": True,
        "task": task.title,
        "status": task.status.value,
        "next_task_id": goal.current_task_id,
        "token_usage": goal.token_usage,
        "budget_exceeded": exceeded,
    }

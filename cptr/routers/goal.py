"""Goal management API endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from cptr.utils.config import AuthResult, check_access
from cptr.utils.goals import (
    GoalRecord,
    GoalStatus,
    GoalStateManager,
    TaskStatus,
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


@router.post("/create")
async def create_goal(request: Request, body: GoalCreateRequest):
    """POST /api/goal/create — Create a new goal from user description."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if state.get_focused_goal():
        raise HTTPException(status_code=409, detail="A goal is already in progress")

    # Create draft GoalRecord (autoContinue=false during drafting)
    goal_id = str(uuid.uuid4())
    draft = GoalRecord(
        id=goal_id,
        objective=body.description.strip(),
        status=GoalStatus.ACTIVE,
        auto_continue=False,  # No auto-continuation in cptr MVP
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

    # Mark auto_continue as confirmed (LLM will generate tasks via separate call)
    goal.auto_continue = True  # LLM-driven continuation in cptr context
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
                "evidence": t.evidence,
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

    # Build continuation message for the LLM to pick up
    pending_tasks = [t for t in goal.task_list if t.status == TaskStatus.PENDING]
    followup = f"[GOAL CONTINUATION] Goal: {goal.objective}\n"
    if pending_tasks:
        next_task = pending_tasks[0]
        followup += f"Next task: {next_task.title}"

    return {"ok": True, "status": "active", "followup": followup}


@router.post("/complete-task")
async def complete_task(request: Request, body: GoalCreateRequest):
    """POST /api/goal/complete-task — Mark a task as complete.
    
    Note: For MVP, uses description field for evidence. A dedicated endpoint
    would use TaskCompleteRequest with task_id + evidence fields.
    """
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    # Extract task_id from body (for MVP simplicity we use a different approach)
    task_id = getattr(body, 'task_id', None) or getattr(body, 'description', '')
    
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    goal = state.goals_by_id[state.focused_goal_id]
    task = next((t for t in goal.task_list if t.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    task.status = TaskStatus.COMPLETE
    task.completed_at = datetime.now().isoformat()
    
    # Update current_task_id to next pending task (if any)
    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, task_id)
    goal.updated_at = datetime.now().isoformat()

    state.persistence.save_goal(goal)
    return {
        "ok": True,
        "task": task.title,
        "status": task.status.value,
        "next_task_id": goal.current_task_id,
    }


# Also add a proper complete-task endpoint with evidence support
class TaskCompleteRequest(BaseModel):
    task_id: str
    evidence: str = ""


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

    # Update current_task_id to next pending task (if any)
    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, body.task_id)
    goal.updated_at = datetime.now().isoformat()

    state.persistence.save_goal(goal)
    return {
        "ok": True,
        "task": task.title,
        "status": task.status.value,
        "next_task_id": goal.current_task_id,
    }


@router.post("/complete")
async def complete_goal(request: Request):
    """POST /api/goal/complete — Mark the focused goal as complete."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.get_focused_goal():
        raise HTTPException(status_code=404, detail="No active goal")

    goal = state.goals_by_id[state.focused_goal_id]
    
    # Verify all tasks are complete before allowing goal completion
    pending_tasks = [t for t in goal.task_list if t.status != TaskStatus.COMPLETE and t.status != TaskStatus.SKIPPED]
    if pending_tasks:
        raise HTTPException(status_code=409, detail=f"Cannot complete goal: {len(pending_tasks)} tasks still pending")

    goal.status = GoalStatus.COMPLETE
    goal.updated_at = datetime.now().isoformat()
    state.persistence.save_goal(goal)
    
    return {"ok": True, "status": "complete"}


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
    task.skip_reason = body.evidence  # Use evidence field for skip reason
    task.completed_at = datetime.now().isoformat()
    
    # Update current_task_id to next pending task (if any)
    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, body.task_id)
    goal.updated_at = datetime.now().isoformat()

    state.persistence.save_goal(goal)
    return {
        "ok": True,
        "task": task.title,
        "status": task.status.value,
        "next_task_id": goal.current_task_id,
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


class TaskCreateRequest(BaseModel):
    goal_id: str | None = None  # If not provided, uses focused goal
    title: str
    description: str = ""


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

    # Cannot delete active/focused goals — must pause or complete first
    goal = state.goals_by_id[goal_id]
    if goal.status == GoalStatus.ACTIVE and state.focused_goal_id == goal_id:
        raise HTTPException(status_code=409, detail="Cannot delete active focused goal")

    # Soft-delete by removing from persistence
    state.persistence.delete_goal(goal_id)
    
    return {"ok": True, "deleted": goal_id}


@router.post("/task/create")
async def create_task(request: Request, body: TaskCreateRequest):
    """POST /api/goal/task/create — Create a new task for a goal."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    # Determine which goal to use
    if body.goal_id and body.goal_id in state.goals_by_id:
        goal = state.goals_by_id[body.goal_id]
    elif state.focused_goal_id and state.focused_goal_id in state.goals_by_id:
        goal = state.goals_by_id[state.focused_goal_id]
    else:
        raise HTTPException(status_code=404, detail="No active goal found")

    # Create new task
    task_id = str(uuid.uuid4())
    from datetime import datetime as _dt
    task = type('Task', (), {
        'id': task_id,
        'title': body.title.strip(),
        'description': body.description or "",
        'status': TaskStatus.PENDING,
        'evidence': None,
        'completed_at': None,
        'skip_reason': None,
    })()

    goal.task_list.append(task)
    
    # Set as current task if first pending
    if not goal.current_task_id:
        goal.current_task_id = task_id
    
    goal.updated_at = _dt.now().isoformat()
    state.persistence.save_goal(goal)

    return {
        "task_id": task_id,
        "goal_id": goal.id,
        "title": body.title.strip(),
        "status": "pending",
    }


@router.get("/audit/{goal_id}")
async def get_audit_log(request: Request, goal_id: str):
    """GET /api/goal/audit/{goal_id} — Get audit log for a specific goal."""
    _get_user(request)

    state = GoalStateManager()
    state.load_all_active_goals()

    if goal_id not in state.goals_by_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = state.goals_by_id[goal_id]
    
    # Build audit log from task history and status changes
    audit_entries = []
    
    # Goal creation
    audit_entries.append({
        "timestamp": goal.created_at,
        "event": "goal_created",
        "details": {"objective": goal.objective},
    })
    
    # Status transitions
    for task in goal.task_list:
        if task.completed_at:
            audit_entries.append({
                "timestamp": task.completed_at,
                "event": f"task_{task.status.value}",
                "details": {"task_id": task.id, "title": task.title},
            })

    # Goal completion status
    audit_entries.append({
        "timestamp": goal.updated_at,
        "event": "goal_status_updated",
        "details": {"status": goal.status.value},
    })

    return {
        "goal_id": goal.id,
        "objective": goal.objective,
        "audit_log": sorted(audit_entries, key=lambda x: x["timestamp"]),
    }

"""Goal management system for cptr.

Persistent goal state stored as JSON files under DATA_DIR/goals/.
Provides task decomposition, status tracking, and an optional completion auditor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────


class TaskStatus(Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    SKIPPED = "skipped"


class GoalStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETE = "complete"


# ── Dataclasses ────────────────────────────────────────────────


@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    completed_at: Optional[str] = None
    skip_reason: Optional[str] = None
    evidence: Optional[str] = None  # Verification evidence for this task
    subtasks: list["Task"] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"id": self.id, "title": self.title}
        if self.status != TaskStatus.PENDING:
            d["status"] = self.status.value
        if self.completed_at:
            d["completed_at"] = self.completed_at
        if self.skip_reason:
            d["skip_reason"] = self.skip_reason
        if self.evidence:
            d["evidence"] = self.evidence
        if self.subtasks:
            d["subtasks"] = [s.to_dict() for s in self.subtasks]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        subtasks_data = data.pop("subtasks", [])
        task = cls(
            id=data["id"],
            title=data["title"],
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
            completed_at=data.get("completed_at"),
            skip_reason=data.get("skip_reason"),
            evidence=data.get("evidence"),
        )
        task.subtasks = [cls.from_dict(st) for st in subtasks_data] if isinstance(subtasks_data, list) else []
        return task


@dataclass
class GoalRecord:
    id: str  # UUID v4
    objective: str  # Free-text objective description
    status: GoalStatus = GoalStatus.ACTIVE
    auto_continue: bool = True  # unused in cptr MVP, kept for spec compatibility
    created_at: str = ""  # ISO 8601 timestamp
    updated_at: str = ""  # Last state change timestamp
    sisyphus_mode: bool = False  # Ordered step-by-step vs flexible plan
    current_task_id: Optional[str] = None  # Task the agent is currently working on
    task_list: list[Task] = field(default_factory=list)
    pause_reason: Optional[str] = None  # Why paused (agent or user)
    verification_contract: Optional[str] = None  # What must be true to mark complete

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    @classmethod
    def from_dict(cls, data: dict) -> "GoalRecord":
        """Reconstruct GoalRecord from a JSON dict (strips version field)."""
        data.pop("version", None)  # strip metadata
        task_list_data = data.pop("task_list", [])
        record = cls(
            id=data.get("id", ""),
            objective=data.get("objective", ""),
            status=GoalStatus(data.get("status", GoalStatus.ACTIVE.value)),
            auto_continue=data.get("auto_continue", True),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            sisyphus_mode=data.get("sisyphus_mode", False),
            current_task_id=data.get("current_task_id"),
            pause_reason=data.get("pause_reason"),
            verification_contract=data.get("verification_contract"),
        )
        record.task_list = [Task.from_dict(t) for t in task_list_data] if isinstance(task_list_data, list) else []
        return record

    def to_dict(self) -> dict:
        """Serialize GoalRecord to a JSON-serializable dict."""
        d = {
            "version": 1,
            "id": self.id,
            "objective": self.objective,
            "status": self.status.value,
            "auto_continue": self.auto_continue,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sisyphus_mode": self.sisyphus_mode,
            "current_task_id": self.current_task_id,
            "pause_reason": self.pause_reason,
            "verification_contract": self.verification_contract,
            "task_list": [t.to_dict() for t in self.task_list],
        }
        return d


# ── Persistence ────────────────────────────────────────────────

from cptr.env import DATA_DIR  # local import to avoid circular deps


class GoalPersistence:
    """Store goal state as JSON files on disk under DATA_DIR.

    Uses the same pattern as memory.py: synchronous file operations,
    atomic writes via tmp+rename, no external dependencies.
    """

    GOALS_SUBDIR = "goals"  # Unterhalb von DATA_DIR (z.B. ~/.cptr/goals/)

    def __init__(self):
        self.goal_dir: Path = DATA_DIR / self.GOALS_SUBDIR
        os.makedirs(self.goal_dir, exist_ok=True)

    def save_goal(self, goal: GoalRecord) -> None:
        """Save a goal as an atomic JSON file (sync)."""
        filepath = self.goal_dir / f"goal_{goal.id}.json"
        data = goal.to_dict()
        # Atomic write: write to temp, then rename (POSIX safe)
        tmp_path = str(filepath) + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, filepath)

    def load_goal(self, goal_id: str) -> Optional[GoalRecord]:
        """Load a goal from its JSON file (sync)."""
        filepath = self.goal_dir / f"goal_{goal_id}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            data = json.load(f)
        return GoalRecord.from_dict(data)

    def list_goals(self) -> list[GoalRecord]:
        """List all non-archived goals by scanning the goal directory (sync)."""
        results = []
        if not self.goal_dir.is_dir():
            return results
        for filename in sorted(self.goal_dir.iterdir()):
            if not filename.name.startswith("goal_") or not filename.name.endswith(".json"):
                continue
            try:
                with open(filename) as f:
                    data = json.load(f)
                goal = GoalRecord.from_dict(data)
                # Exclude completed/archived goals from active list
                if goal.status != GoalStatus.COMPLETE:
                    results.append(goal)
            except Exception as e:
                logger.warning("Failed to load goal %s: %s", filename.name, e)
        return results

    def archive_goal(self, goal_id: str) -> None:
        """Move a completed goal to an archive subdirectory (sync)."""
        src = self.goal_dir / f"goal_{goal_id}.json"
        if not src.exists():
            return
        archive_dir = self.goal_dir.parent / "goals_archive"
        os.makedirs(archive_dir, exist_ok=True)
        dst = archive_dir / f"goal_{goal_id}.json"
        shutil.move(str(src), str(dst))


# ── State Manager ──────────────────────────────────────────────


class GoalStateManager:
    """Manages goal state in the assistant: load from files, mutate, persist back.

    All operations are synchronous to match cptr's I/O pattern.
    """

    def __init__(self):
        self.persistence = GoalPersistence()
        # In-memory cache for active goals during a session
        self.goals_by_id: dict[str, GoalRecord] = {}
        self.focused_goal_id: Optional[str] = None

    def load_all_active_goals(self) -> None:
        """Load all non-archived goals from disk into memory."""
        self.goals_by_id.clear()
        for goal in self.persistence.list_goals():
            if goal.status != GoalStatus.COMPLETE:
                self.goals_by_id[goal.id] = goal
        # Auto-select first active regular (non-Sisyphus) goal as focused
        if not self.focused_goal_id and self.goals_by_id:
            self.focused_goal_id = next(
                (g.id for g in self.goals_by_id.values() if not g.sisyphus_mode),
                next(iter(self.goals_by_id)),
            )

    def save_all_goals(self) -> None:
        """Persist all goals from memory back to disk."""
        for goal in self.goals_by_id.values():
            self.persistence.save_goal(goal)

    def get_focused_goal(self) -> Optional[GoalRecord]:
        if not self.focused_goal_id:
            return None
        return self.goals_by_id.get(self.focused_goal_id)

    @staticmethod
    def find_next_pending_task(task_list: list[Task], skip_id: str = "") -> Optional[str]:
        """Find the next pending task after the given one."""
        for i, t in enumerate(task_list):
            if t.id == skip_id and i + 1 < len(task_list):
                remaining = task_list[i + 1 :]
                for rt in remaining:
                    if rt.status == TaskStatus.PENDING:
                        return rt.id
        # If no next pending, try to find any other pending (for non-sequential)
        for t in task_list:
            if t.status == TaskStatus.PENDING and t.id != skip_id:
                return t.id
        return None


# ── Tool Functions for the Assistant ───────────────────────────


def complete_task(task_id: str, evidence: str = "") -> dict:
    """Tool function the assistant can call to mark a task as complete."""
    state = GoalStateManager()
    state.load_all_active_goals()
    if not state.focused_goal_id:
        return {"error": "No focused goal"}

    goal = state.goals_by_id[state.focused_goal_id]
    task = next((t for t in goal.task_list if t.id == task_id), None)
    if not task:
        return {"error": f"Task {task_id} not found"}

    task.status = TaskStatus.COMPLETE
    task.completed_at = datetime.now().isoformat()
    task.evidence = evidence

    # Update current_task_id to next pending task (if any)
    goal.current_task_id = GoalStateManager.find_next_pending_task(goal.task_list, task_id)
    state.save_all_goals()
    return {"ok": True, "task": task.title, "status": task.status.value}


def list_tasks() -> dict:
    """Tool function the assistant can call to see current tasks."""
    state = GoalStateManager()
    state.load_all_active_goals()
    goal = state.get_focused_goal()
    if not goal:
        return {"error": "No active goal"}

    return {
        "goal_objective": goal.objective,
        "current_task_id": goal.current_task_id,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "evidence": t.evidence,
            }
            for t in goal.task_list
        ],
    }


# ── Completion Auditor ─────────────────────────────────────────

AUDITOR_SYSTEM_PROMPT = """\
You are an independent auditor reviewing a completed goal.
You have NO knowledge of the main agent's work context — only what is presented here.

Your job: Verify that the objective was truly met based on evidence, not just claims.
Be strict. Disapprove if there is any doubt.

Rules:
1. Check each completed task's evidence against the objective
2. Look for gaps: Are all parts of the objective addressed?
3. Do NOT accept "I did it" without concrete evidence
4. If verification_contract exists, check EVERY requirement explicitly

Respond with JSON only (no markdown): {"approved": true/false, "report": "detailed feedback"}\
"""


async def audit_goal(goal_id: str) -> dict[str, Any]:
    """Run the auditor as a separate LLM API call (not a Sub-Agent process).

    Uses a dedicated model connection configured in cptr settings.
    This is equivalent to pi-goal-x's createAgentSession approach,
    but implemented as a standalone API request with no main agent context.
    """
    from cptr.utils.runtime import Runtime

    persistence = GoalPersistence()
    goal = persistence.load_goal(goal_id)
    if not goal or goal.status != GoalStatus.ACTIVE:
        return {"error": "Goal not active"}

    # Gather evidence from completed tasks
    completed_tasks = [t for t in goal.task_list if t.status == TaskStatus.COMPLETE]
    task_evidence = "\n".join(
        f"- {t.title}: {t.evidence or 'No evidence'}" for t in completed_tasks
    )

    # Build auditor prompt (no main agent context!)
    audit_prompt = f"""\
{AUDITOR_SYSTEM_PROMPT}

Objective: {goal.objective}
Verification Contract: {goal.verification_contract or "N/A"}

Completed Tasks and Evidence:
{task_evidence}

Does the evidence support that the objective is fully met?
Respond with JSON only (no markdown): {"approved": true/false, "report": "detailed feedback"}"""

    try:
        runtime = Runtime()

        # Use the configured auditor model, or fall back to default
        auditor_model = "llama-3.1-8b"  # Could be configurable later

        response = await asyncio.wait_for(
            runtime.chat(
                [
                    {"role": "system", "content": AUDITOR_SYSTEM_PROMPT},
                    {"role": "user", "content": audit_prompt},
                ],
                model=auditor_model,
                temperature=0.1,  # Low temp for consistency
            ),
            timeout=30.0,
        )

        # Parse JSON response (strip markdown code fences if present)
        content = response.choices[0].message.content.strip()
        json_match = re.search(r"\{[^{}]+\}", content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {"approved": False, "report": f"Failed to parse response: {content}"}

        # Update goal status based on audit result
        if result.get("approved"):
            goal.status = GoalStatus.COMPLETE
            persistence.archive_goal(goal_id)
        else:
            goal.pause_reason = f"Audit rejected: {result.get('report', '')}"
            persistence.save_goal(goal)

        return {"ok": True, **result}

    except Exception as e:
        # Auditor failure is non-critical — log but don't block goal completion
        logger.warning("Goal audit failed for %s: %s", goal_id, e)
        return {"approved": False, "report": f"Audit error: {str(e)}"}

"""MicroSkillsStage – DB-backed wrapper around PrefixStage for cptr.

Follows the LoopGuard pattern: per-chat state persisted to DB, render() 
called before system_prompt builds, after_task() called after completion.

Starts with envfacts profile (LLM-free). Paid distiller can be enabled later.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select as sa_select

from cptr.models.te import MicroskillsFact as _MicroSkillStateModel
from cptr.utils.db import get_session_factory

logger = logging.getLogger(__name__)


@dataclass
class _MicroSkillState:
    """In-memory state for one chat's micro-skills lifecycle."""
    facts: dict[str, str] = field(default_factory=dict)  # id -> fact_text
    injected_ids: list[str] = field(default_factory=list)
    task_count: int = 0
    last_render: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "facts": self.facts,
            "injected_ids": self.injected_ids,
            "task_count": self.task_count,
            "last_render": self.last_render,
        })

    @classmethod
    def from_json(cls, raw: str | None) -> "_MicroSkillState":
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
            return cls(
                facts=data.get("facts", {}),
                injected_ids=data.get("injected_ids", []),
                task_count=data.get("task_count", 0),
                last_render=data.get("last_render", ""),
            )
        except Exception:
            return cls()


class MicroSkillsStage:
    """DB-backed micro-skills lifecycle hook for cptr.

    Pattern (same as LoopGuard):
      1. __init__ loads state from DB
      2. render() returns prefix text to inject into system prompt
      3. after_task(task, transcript_path) folds session back and persists

    Uses the existing MicroskillsFact table for persistence (like 
    LoopEnvelope is used by LoopGuard).
    """

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self._state = _MicroSkillState()

        # Load persisted state from DB
        self._load_from_db()

    # ---- render -----------------------------------------------------------

    def render(self) -> str:
        """Return the micro-skills prefix to inject into system prompt.

        Returns formatted fact lines, or empty string if no facts available.
        """
        if not self._state.facts:
            return ""

        header = "# environment facts learned from earlier tasks in this checkout"
        lines = [header] + [f"- {text}" for text in self._state.facts.values()]
        result = "\n".join(lines) + "\n"
        self._state.last_render = result
        return result

    # ---- after_task -------------------------------------------------------

    def after_task(self, task: dict, transcript_path: str) -> tuple[int, str]:
        """Fold the finished task into the fact lifecycle; persist to DB.

        Args:
            task: The completed task dict (from chat_task).
            transcript_path: Path to the session transcript JSONL file.

        Returns:
            (opt_tokens_delta, reason) - always 0 for envfacts profile.
        """
        self._state.task_count += 1
        
        # Parse transcript JSONL and learn facts from recurring tool-call errors
        try:
            import json as _json
            from .repo_facts import _error_tracker
            
            if transcript_path:
                with open(transcript_path, "r") as f:
                    for line in f:
                        try:
                            entry = _json.loads(line.strip())
                            # Match tool-call errors (status=failed/error)
                            if isinstance(entry, dict):
                                msg_type = entry.get("type", "")
                                error_text = None
                                tool_name = None
                                
                                if msg_type == "tool_call":
                                    status = entry.get("status")
                                    if status in ("error", "failed"):
                                        error_text = entry.get("error", str(entry.get("output")))
                                        tool_name = entry.get("name", "")
                                        
                                elif isinstance(entry, dict) and "content" in entry:
                                    # Check for tool call results with errors
                                    output = entry.get("output", "")
                                    if output and "error" in str(output).lower():
                                        error_text = str(output)[:500]
                                        tool_name = entry.get("name", "")
                                
                                if tool_name and error_text:
                                    _error_tracker.record_error(self.chat_id, tool_name, error_text)
                        except Exception:
                            continue  # skip malformed JSONL lines
        except Exception as e:
            logger.debug("[microskills] Transcript parse failed for %s: %s", self.chat_id, e)

        # Persist to DB after each task
        try:
            self._persist_to_db()
        except Exception as e:
            logger.warning("[microskills] Failed to persist after_task for %s: %s", 
                          self.chat_id, e)

        return (0, "envfacts")

    # ---- DB persistence --------------------------------------------------

    def _load_from_db(self) -> None:
        """Load persisted state from the MicroskillsState table."""
        try:
            import asyncio
            
            existing_loop = None
            try:
                existing_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            
            async def _load():
                from cptr.utils.db import get_session_factory
                
                async with get_session_factory()() as sess:
                    stmt = sa_select(_MicroSkillStateModel).where(
                        _MicroSkillStateModel.chat_id == self.chat_id
                    )
                    result = await sess.execute(stmt)
                    return result.scalar_one_or_none()
            
            try:
                import nest_asyncio
                nest_asyncio.apply()
            except (RuntimeError, ImportError):
                pass
            env = asyncio.run(_load())
            self._state = _MicroSkillState.from_json(env.state_json)
        except Exception as e:
            logger.warning("[microskills] Failed to load state for %s: %s", 
                          self.chat_id, e)

    def _persist_to_db(self) -> None:
        """Persist current state to the _MicroSkillStateModel table."""
        try:
            import asyncio
            
            existing_loop = None
            try:
                existing_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            
            async def _db_op():
                from cptr.utils.db import get_session_factory
                
                async with get_session_factory()() as sess:
                    stmt = sa_select(_MicroSkillStateModel).where(
                        _MicroSkillStateModel.chat_id == self.chat_id
                    )
                    result = await sess.execute(stmt)
                    env = result.scalar_one_or_none()

                    if env is None:
                        env = _MicroSkillStateModel(chat_id=self.chat_id)
                        sess.add(env)

                    env.state_json = self._state.to_json()
                    env.task_count = self._state.task_count
                    
                    await sess.commit()

            try:
                import nest_asyncio
                nest_asyncio.apply()
            except (RuntimeError, ImportError):
                pass
            asyncio.run(_db_op())
        except Exception as e:
            logger.warning("[microskills] Failed to persist state for %s: %s", 
                         self.chat_id, e)

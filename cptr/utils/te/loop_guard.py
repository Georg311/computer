"""LoopGuard – turn-level failure-loop intervention for cptr sessions.

Wraps the existing TE loopguard (rules, state, envelope) into a per-chat,
DB-backed controller that persists its state after every tool call.

Usage::

    guard = LoopGuard(chat_id="...")
    guard.fold_call("edit", {"path": "a.py"}, "ok")
    guard.fold_call("bash", {"command": "pytest"}, "FAILED")
    abort, reason = guard.assess_abort()
    if abort:
        # propose abort to user – never auto-stop!
        ...

Design decisions (matching TE reference):
  * Envelope = rolling window of the last N tool calls as JSON.
  * Tier-0 rule-based check runs every turn (free).
  * Tier-1 LLM judge is optional and rate-limited via config.
  * Fallback: strict heuristic + envelope hard backstop.
  * Nudge at first stuck sign → redirect message.
  * Abort proposal after nudge if still stuck → manual user confirm required.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select as sa_select

from cptr.models.te import LoopEnvelope
from cptr.utils.db import get_session_factory

from .loopguard.envelope import EnvelopeTracker
from .loopguard.rules import (
    assess_abort as _assess_abort,
    gate_for_judge,
    nudge_text as _nudge_text,
)
from .loopguard.state import SpiralState, canon_tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config keys (read from config.toml / Admin Settings)
# ---------------------------------------------------------------------------
CONFIG_ENABLED = "te.loopguard.enabled"
CONFIG_MAX_ENVELOPE_SIZE = "te.loopguard.max_envelope_size"
CONFIG_NUDGE_THRESHOLD = "te.loopguard.nudge_threshold"
CONFIG_LLM_JUDGE_ENABLED = "te.loopguard.llm_judge_enabled"
CONFIG_SPIRAL_LEVEL = "te.loopguard.spiral_level"  # conservative | default | aggressive

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG = {
    CONFIG_ENABLED: True,
    CONFIG_MAX_ENVELOPE_SIZE: 50,          # max tool calls kept in envelope
    CONFIG_NUDGE_THRESHOLD: 3,             # nudges before proposing abort
    CONFIG_LLM_JUDGE_ENABLED: False,       # LLM judge off by default
    CONFIG_SPIRAL_LEVEL: "default",        # aggressiveness preset
}


# ---------------------------------------------------------------------------
# Call record stored inside the envelope
# ---------------------------------------------------------------------------
@dataclass
class _CallRecord:
    """One completed tool call for envelope tracking."""
    tool_name: str
    args: dict[str, Any]
    result_preview: str  # truncated summary of result
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "args": self.args,
            "result_preview": self.result_preview[:200],  # safety cap
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> _CallRecord:
        return cls(
            tool_name=d["tool_name"],
            args=d["args"],
            result_preview=d["result_preview"],
            timestamp=float(d["timestamp"]),
        )


# ---------------------------------------------------------------------------
# Envelope – rolling window of recent tool calls (JSON serialised)
# ---------------------------------------------------------------------------
class Envelope:
    """Rolling window of the last N tool calls.

    Stored as JSON in ``LoopEnvelope.resolved_turns`` (reused column for
    the envelope payload).
    """

    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.calls: list[_CallRecord] = []

    def add(self, tool_name: str, args: dict, result_preview: str) -> None:
        self.calls.append(_CallRecord(
            tool_name=tool_name,
            args=args,
            result_preview=result_preview,
            timestamp=time.time(),
        ))
        # Keep only the last N calls
        if len(self.calls) > self.max_size:
            self.calls = self.calls[-self.max_size:]

    @property
    def size(self) -> int:
        return len(self.calls)

    def to_json(self) -> str:
        return json.dumps([c.to_dict() for c in self.calls])

    @classmethod
    def from_json(cls, raw: str | None, max_size: int = 50) -> Envelope:
        inst = cls(max_size=max_size)
        if raw:
            try:
                items = json.loads(raw)
                for item in items:
                    inst.calls.append(_CallRecord.from_dict(item))
            except (json.JSONDecodeError, KeyError):
                pass
        return inst

    def detect_repeats(self) -> int:
        """Count tool calls that are identical to the immediately previous one."""
        repeats = 0
        for i in range(1, len(self.calls)):
            prev = self.calls[i - 1]
            curr = self.calls[i]
            if (prev.tool_name == curr.tool_name
                    and prev.args == curr.args):
                repeats += 1
        return repeats

    def detect_error_streak(self) -> int:
        """Count consecutive calls with error-like result preview."""
        streak = 0
        for call in reversed(self.calls):
            if "error" in call.result_preview.lower() or \
               "traceback" in call.result_preview.lower() or \
               "failed" in call.result_preview.lower():
                streak += 1
            else:
                break
        return streak


# ---------------------------------------------------------------------------
# LoopGuard – per-chat controller with DB persistence
# ---------------------------------------------------------------------------
class LoopGuard:
    """Turn-level loop guard backed by the LoopEnvelope DB table.

    Each turn (tool call completion) is folded via ``fold_call()``. After each
    fold, state is persisted to the database. The guard can then be queried
    for abort decisions and nudge messages.
    """

    def __init__(
        self,
        chat_id: str,
        config_overrides: dict[str, Any] | None = None,
        llm_judge_callback=None,
    ):
        """
        Args:
            chat_id:              The chat to guard.
            config_overrides:     Dict of config keys → values (overrides defaults).
            llm_judge_callback:   Optional sync callable(state_digest) -> dict
                                  with keys {stuck: bool|None, confidence: float}.
        """
        self.chat_id = chat_id
        self.config = dict(_DEFAULT_CONFIG)
        if config_overrides:
            self.config.update(config_overrides)

        self.llm_judge_callback = llm_judge_callback

        # Core state – _nudge_count MUST be set before _load_from_db
        self._spiral = SpiralState()
        self._envelope = Envelope(
            max_size=self.config.get(CONFIG_MAX_ENVELOPE_SIZE, 50))
        self._tracker = EnvelopeTracker(level="default")
        self._nudge_count = 0

        # Load persisted state from DB
        self._load_from_db()

    # ---- Config helpers ---------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(self.config.get(CONFIG_ENABLED, True))

    @property
    def spiral_level(self) -> str:
        return self.config.get(CONFIG_SPIRAL_LEVEL, "default")

    @property
    def nudge_threshold(self) -> int:
        return self.config.get(CONFIG_NUDGE_THRESHOLD, 3)

    @property
    def llm_judge_enabled(self) -> bool:
        return bool(self.config.get(CONFIG_LLM_JUDGE_ENABLED, False))

    def thresholds(self):
        """Compute detector thresholds from level + tracker."""
        return self._tracker.thresholds()

    # ---- Tier-0 rule-based check (free, every turn) ----------------------

    @property
    def tier0_gate_open(self) -> bool:
        """Tier-0: cheap rule-based gate for the LLM judge.

        Returns True if the recent trace is worth a paid look.
        """
        return gate_for_judge(self._spiral, self.thresholds())

    # ---- fold_call – analyse each tool call and build envelope -----------

    def fold_call(
        self,
        name: str,
        args: dict[str, Any],
        result: str | None = "",
    ) -> dict:
        """Analyse one completed tool call, update state, persist to DB.

        Returns a dict with analysis results for the caller::

            { "tool_name": ..., "spiral_update": {...}, "tier0_gate": bool, ... }
        """
        if not self.enabled:
            return {"tool_name": name, "skipped": True}

        canon = canon_tool(name)
        result_preview = result[:200] if result else ""

        # Update SpiralState with this call
        failed = (
            "error" in result_preview.lower() or
            "traceback" in result_preview.lower() or
            "failed" in result_preview.lower()
        )
        self._spiral.update(canon, args, result, failed=failed)

        # Add to envelope
        self._envelope.add(canon, args, result_preview)

        # Persist state after every turn
        self._persist_to_db()

        # Return analysis snapshot
        return {
            "tool_name": canon,
            "spiral_turns": self._spiral.turns,
            "spiral_stagnation": round(self._spiral.stagnation, 3),
            "tier0_gate_open": self.tier0_gate_open,
            "envelope_size": self._envelope.size,
            "repeated_calls": self._envelope.detect_repeats(),
            "error_streak": self._envelope.detect_error_streak(),
        }

    # ---- assess_abort – evaluate whether to propose abort ----------------

    def assess_abort(self) -> tuple[bool, str]:
        """Evaluate whether an abort proposal is needed.

        Returns:
            (abort: bool, reason: str)
        """
        if not self.enabled:
            return False, "disabled"

        # Ensure state is persisted first
        self._persist_to_db()

        # Get the envelope size from DB as context for assess_abort
        db_env = self._load_from_db()
        envelope_size = db_env.envelope_size if db_env else 0

        # Build judge callback if enabled
        judge = None
        if self.llm_judge_enabled and self.llm_judge_callback:
            def _sync_judge(digest: str) -> dict | None:
                try:
                    result = self.llm_judge_callback(digest)
                    return result if isinstance(result, dict) else None
                except Exception as e:
                    logger.warning("LLM judge failed: %s", e)
                    return None
            judge = _sync_judge

        thr = self.thresholds()
        abort, reason = _assess_abort(
            self._spiral,
            envelope=envelope_size,
            judge=judge,
            thr=thr,
        )

        # Record the decision in DB
        if db_env:
            db_env.aborted = bool(db_env.aborted or abort)
            session = get_session_factory()
            session.add(db_env)
            session.commit()

        return abort, reason

    # ---- nudge_text – generate redirect message at first stuck sign -------

    def nudge_text(self) -> str | None:
        """Generate a nudge (redirect) message when stuck signs appear.

        Returns the nudge text or None if no nudge is warranted yet.
        Increments ``nudges_done`` in DB on success.
        """
        # Check if we should nudge based on spiral state signals
        if self._spiral.turns < 10:
            return None  # too early

        # Nudge at first sign of stagnation + repeated failures
        if (self._spiral.repeated_fail_sigs >= 1
                and self._spiral.stagnation > 0.15):
            msg = _nudge_text(self._spiral)
            self._increment_nudge()
            return msg

        # Also nudge on high error density even without exact repeat
        thr = self.thresholds()
        if (self._spiral.turns >= thr.get("gate_min_turns", 18)
                and self._spiral.error_outputs >= thr.get("gate_error_outputs", 8)):
            msg = _nudge_text(self._spiral)
            self._increment_nudge()
            return msg

        return None

    def _increment_nudge(self) -> None:
        """Increment nudge counter and persist."""
        self._nudge_count += 1
        try:
            session = get_session_factory()
            stmt = sa_select(LoopEnvelope).where(
                LoopEnvelope.chat_id == self.chat_id
            )
            result = session.execute(stmt)
            env = result.scalar_one_or_none()
            if env:
                env.nudges_done = self._nudge_count
                session.add(env)
                session.commit()
        except Exception as e:
            logger.warning("Failed to persist nudge count for %s: %s", self.chat_id, e)

    # ---- DB persistence --------------------------------------------------

    def _load_from_db(self) -> LoopEnvelope | None:
        """Load persisted state from the LoopEnvelope table."""
        try:
            session = get_session_factory()
            stmt = sa_select(LoopEnvelope).where(
                LoopEnvelope.chat_id == self.chat_id
            )
            result = session.execute(stmt)
            env = result.scalar_one_or_none()

            if env:
                # envelope_size column stores turn count
                self._spiral.turns = env.envelope_size
                # Restore nudges_done
                self._nudge_count = env.nudges_done or 0
                # Restore resolved turns from JSON
                resolved = env.resolved_turns or []
                if isinstance(resolved, list):
                    self._tracker.resolved_turns = [int(t) for t in resolved]
            else:
                self._nudge_count = 0

            return env
        except Exception as e:
            logger.warning("Failed to load LoopEnvelope for %s: %s", self.chat_id, e)
            self._nudge_count = 0
            return None

    def _persist_to_db(self) -> None:
        """Persist current state to the LoopEnvelope table."""
        try:
            session = get_session_factory()
            stmt = sa_select(LoopEnvelope).where(
                LoopEnvelope.chat_id == self.chat_id
            )
            result = session.execute(stmt)
            env = result.scalar_one_or_none()

            if env is None:
                env = LoopEnvelope(chat_id=self.chat_id)
                session.add(env)

            # Save state to the envelope columns
            env.envelope_size = self._spiral.turns
            env.nudges_done = self._nudge_count

            # Store resolved_turns as JSON array (learned turn counts)
            env.resolved_turns = list(self._tracker.resolved_turns[-500:])

            session.add(env)
            session.commit()
        except Exception as e:
            logger.warning("Failed to persist LoopEnvelope for %s: %s", self.chat_id, e)

    # ---- Public state queries --------------------------------------------

    @property
    def spiral_state(self) -> dict:
        """Current SpiralState snapshot."""
        return self._spiral.snapshot()

    @property
    def envelope_state(self) -> dict:
        """Current envelope summary."""
        return {
            "size": self._envelope.size,
            "max_size": self._envelope.max_size,
            "repeats": self._envelope.detect_repeats(),
            "error_streak": self._envelope.detect_error_streak(),
        }

    def get_state_json(self) -> dict:
        """Full state dump for debugging / admin UI."""
        return {
            "chat_id": self.chat_id,
            "enabled": self.enabled,
            "spiral": self._spiral.snapshot(),
            "envelope": self.envelope_state,
            "thresholds": {k: v for k, v in self.thresholds().items()},
            "tier0_gate_open": self.tier0_gate_open,
        }

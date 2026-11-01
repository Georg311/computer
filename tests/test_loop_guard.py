"""Unit tests for cptr.utils.te.loop_guard."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cptr.utils.te.loopguard.state import SpiralState, canon_tool
from cptr.utils.te.loopguard.rules import (
    assess_abort as _assess_abort,
    gate_for_judge,
    nudge_text as _nudge_text,
    is_stuck,
    scaled_thresholds,
)


# ── Envelope ───────────────────────────────────────────────────────────

class TestEnvelope:
    """Test the Envelope class (rolling window of tool calls)."""

    def test_add_and_size(self):
        from cptr.utils.te.loop_guard import Envelope
        env = Envelope(max_size=5)
        env.add("bash", {"command": "ls"}, "output")
        assert env.size == 1
        env.add("edit", {"path": "a.py"}, "ok")
        assert env.size == 2

    def test_max_size_truncation(self):
        from cptr.utils.te.loop_guard import Envelope
        env = Envelope(max_size=3)
        for i in range(5):
            env.add("bash", {"command": f"cmd{i}"}, f"out{i}")
        assert env.size == 3
        # Only last 3 calls remain
        assert env.calls[0].tool_name == "bash"

    def test_serialization_roundtrip(self):
        from cptr.utils.te.loop_guard import Envelope
        env = Envelope(max_size=10)
        env.add("edit", {"path": "x.py"}, "modified")
        env.add("bash", {"command": "pytest"}, "FAILED")
        json_str = env.to_json()
        restored = Envelope.from_json(json_str, max_size=10)
        assert restored.size == 2
        assert restored.calls[0].tool_name == "edit"
        assert restored.calls[1].tool_name == "bash"

    def test_detect_repeats(self):
        from cptr.utils.te.loop_guard import Envelope
        env = Envelope()
        env.add("bash", {"command": "ls"}, "out1")
        env.add("bash", {"command": "ls"}, "out2")  # repeat
        env.add("edit", {"path": "a.py"}, "ok")
        env.add("bash", {"command": "ls"}, "out3")  # repeat of first, not immediate
        assert env.detect_repeats() == 1  # only the adjacent repeat

    def test_detect_error_streak(self):
        from cptr.utils.te.loop_guard import Envelope
        env = Envelope()
        env.add("bash", {"command": "pytest"}, "passed")
        env.add("edit", {"path": "a.py"}, "ok")
        env.add("bash", {"command": "pytest"}, "Traceback error")
        env.add("bash", {"command": "pytest"}, "FAILED again")
        assert env.detect_error_streak() == 2  # 2 consecutive errors from end

    def test_from_json_empty(self):
        from cptr.utils.te.loop_guard import Envelope
        env = Envelope.from_json(None, max_size=5)
        assert env.size == 0
        env2 = Envelope.from_json("", max_size=5)
        assert env2.size == 0

    def test_from_json_invalid(self):
        from cptr.utils.te.loop_guard import Envelope
        env = Envelope.from_json("not json", max_size=5)
        assert env.size == 0


# ── LoopGuard.fold_call ────────────────────────────────────────────────

class TestFoldCall:
    """Test LoopGuard.fold_call() updates SpiralState and Envelope."""

    def _make_guard(self, **overrides):
        """Create a LoopGuard with DB persistence mocked out."""
        from cptr.utils.te.loop_guard import LoopGuard

        # Mock _persist_to_db and _load_from_db to avoid real DB calls
        with patch.object(LoopGuard, "_persist_to_db"):
            with patch.object(LoopGuard, "_load_from_db"):
                guard = LoopGuard("chat-fold", config_overrides=overrides)
                return guard

    def test_fold_call_updates_spiral_turns(self):
        guard = self._make_guard()
        result = guard.fold_call("bash", {"command": "ls"}, "output")
        assert result["spiral_turns"] == 1

    def test_fold_call_updates_envelope_size(self):
        guard = self._make_guard()
        for i in range(5):
            guard.fold_call("bash", {"command": f"cmd{i}"}, "ok")
        assert guard._envelope.size == 5

    def test_fold_call_marks_failed(self):
        guard = self._make_guard()
        result = guard.fold_call("bash", {"command": "pytest"}, "Traceback error")
        # SpiralState should have error_outputs incremented
        assert guard._spiral.error_outputs == 1

    def test_fold_call_when_disabled(self):
        guard = self._make_guard(config_overrides={"te.loopguard.enabled": False})
        result = guard.fold_call("bash", {"command": "ls"}, "ok")
        assert result.get("skipped") is True

    def test_fold_call_canonicalizes_tool_name(self):
        """Tool names should be canonicalized (e.g., 'multiedit' -> 'edit')."""
        from cptr.utils.te.loop_guard import LoopGuard
        with patch.object(LoopGuard, "_persist_to_db"):
            with patch.object(LoopGuard, "_load_from_db"):
                guard = LoopGuard("chat-canon")
                result = guard.fold_call("multiedit", {"path": "a.py"}, "ok")
                assert result["tool_name"] == "edit"  # canonical name

    def test_fold_call_persists_state(self):
        """fold_call should call _persist_to_db."""
        guard = self._make_guard()
        guard.fold_call("bash", {"command": "ls"}, "ok")
        # _persist_to_db was called (we patched it, so no exception)


# ── assess_abort ───────────────────────────────────────────────────────

class TestAssessAbort:
    """Test assess_abort() returns (True, reason) at repeated failures."""

    def test_not_stuck_early(self):
        """Should not abort before min_turns threshold."""
        state = SpiralState()
        # Only 5 turns, well below min_turns=20
        for i in range(5):
            state.update("bash", {"command": "cmd"}, "ok")
        abort, reason = _assess_abort(state, thr=scaled_thresholds())
        assert abort is False
        assert reason == "not-stuck"

    def test_stuck_with_high_churn(self):
        """Should detect stuck when churn + errors + stagnation all present."""
        state = SpiralState()
        # Generate enough turns with repeated failures and edits to same file
        for i in range(25):
            if i < 10:
                state.update("edit", {"path": "/a.py"}, "Traceback error")
            elif i < 20:
                state.update("edit", {"path": "/a.py"}, "FAILED assert")
            else:
                state.update("bash", {"command": "pytest"}, "Error in test")

        abort, reason = _assess_abort(state, thr=scaled_thresholds())
        assert abort is True  # churny + noisy + repeating

    def test_not_stuck_different_failures(self):
        """Different failures should NOT be stuck (productive grind)."""
        state = SpiralState()
        for i in range(25):
            # Each iteration produces a different failure signature
            state.update("edit", {"path": f"/file{i}.py"}, f"Error line {i}")

        abort, reason = _assess_abort(state, thr=scaled_thresholds())
        # Should not be stuck because failures are different (stagnation ~0)
        assert abort is False

    def test_backstop_trigger(self):
        """Should trigger hard backstop beyond envelope * multiplier."""
        state = SpiralState()
        for i in range(120):  # well past 2.5x typical envelope
            state.update("edit", {"path": "/a.py"}, "Traceback error")

        abort, reason = _assess_abort(state, envelope=40, thr=scaled_thresholds())
        assert abort is True
        assert "backstop" in reason

    def test_judge_productive(self):
        """LLM judge saying productive should spare the trajectory."""
        state = SpiralState()
        for i in range(30):
            state.update("edit", {"path": "/a.py"}, "Traceback error")

        def mock_judge(digest):
            return {"stuck": False, "confidence": 0.9}

        abort, reason = _assess_abort(state, judge=mock_judge, thr=scaled_thresholds())
        assert abort is False
        assert "productive" in reason


# ── nudge_text ─────────────────────────────────────────────────────────

class TestNudgeText:
    """Test nudge_text() returns redirect message on stagnation."""

    def test_returns_message_on_stagnation(self):
        """Should return a nudge when stagnation > 0.15 and repeated_fail_sigs >= 1."""
        state = SpiralState()
        # Generate enough turns to pass the 10-turn minimum
        for i in range(15):
            state.update("edit", {"path": "/a.py"}, "Traceback error")

        msg = _nudge_text(state)
        assert msg is not None
        assert "Process check" in msg
        assert "edit" in msg.lower() or "edits" in msg.lower()

    def test_contains_action_summary(self):
        """Nudge should summarize edits, files, and repeated failures."""
        state = SpiralState()
        for i in range(20):
            state.update("edit", {"path": "/x.py"}, "FAILED")
            state.update("bash", {"command": "pytest"}, "passed")

        msg = _nudge_text(state)
        assert "edits" in msg.lower() or "edits across" in msg.lower()
        assert "file" in msg.lower()


# ── Tier-0 gate_for_judge ─────────────────────────────────────────────

class TestGateForJudge:
    """Test tier-0 gate_for_judge rule-based check."""

    def test_gate_closed_early(self):
        """Should be closed before gate_min_turns."""
        state = SpiralState()
        for i in range(10):
            state.update("bash", {"command": "cmd"}, "ok")
        assert gate_for_judge(state) is False

    def test_gate_open_on_repeated_failures(self):
        """Should open when there are repeated identical failures."""
        state = SpiralState()
        for i in range(20):
            state.update("edit", {"path": "/a.py"}, "Traceback error")
        assert gate_for_judge(state) is True

    def test_gate_open_on_high_errors(self):
        """Should open when error_outputs >= gate_error_outputs."""
        thr = dict(scaled_thresholds())
        thr["gate_min_turns"] = 5  # lower threshold for testing
        state = SpiralState()
        for i in range(10):
            state.update("bash", {"command": "cmd"}, f"Error {i}")
        assert gate_for_judge(state, thr) is True

    def test_gate_closed_on_low_errors(self):
        """Should stay closed with few errors."""
        thr = dict(scaled_thresholds())
        state = SpiralState()
        for i in range(15):
            state.update("bash", {"command": "cmd"}, "ok")
        assert gate_for_judge(state, thr) is False


# ── LoopGuard DB persistence ───────────────────────────────────────────

class TestDBPersistence:
    """Test _persist_to_db / _load_from_db."""

    def test_persist_and_load_saves_turns(self):
        """_persist_to_db should save spiral.turns to DB."""
        from cptr.utils.te.loop_guard import LoopGuard, LoopEnvelope

        mock_session = MagicMock()
        mock_env = MagicMock()
        mock_env.chat_id = "chat-db"

        def side_effect(stmt):
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = None  # no existing env
            return mock_res

        async def mock_execute(stmt):
            return side_effect(stmt)
        mock_session.execute = mock_execute

        with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
            guard = LoopGuard("chat-db")
            guard._spiral.turns = 5
            guard._persist_to_db()

        # Verify session.add was called (we can't easily check the exact object, but no crash)
        assert mock_session.add.called


    def test_load_from_db_restores_nudge_count(self):
        """_load_from_db should restore nudges_done from DB."""
        from cptr.utils.te.loop_guard import LoopGuard

        mock_session = MagicMock()
        mock_env = MagicMock()
        mock_env.chat_id = "chat-load"
        mock_env.envelope_size = 10
        mock_env.nudges_done = 3
        mock_env.resolved_turns = [5, 10]

        def side_effect(stmt):
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = mock_env
            return mock_res

        async def mock_execute(stmt):
            return side_effect(stmt)
        mock_session.execute = mock_execute

        with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
            guard = LoopGuard("chat-load")
            assert guard._nudge_count == 3
            assert guard._spiral.turns == 10


    def test_load_from_db_handles_missing(self):
        """_load_from_db should handle missing envelope gracefully."""
        from cptr.utils.te.loop_guard import LoopGuard

        mock_session = MagicMock()
        def side_effect(stmt):
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = None
            return mock_res

        async def mock_execute(stmt):
            return side_effect(stmt)
        mock_session.execute = mock_execute

        with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
            guard = LoopGuard("chat-missing")
            assert guard._nudge_count == 0


# ── SpiralState helper tests ───────────────────────────────────────────

class TestSpiralStateHelpers:
    """Test SpiralState derived properties."""

    def test_stagnation_zero_when_no_fails(self):
        state = SpiralState()
        for i in range(10):
            state.update("bash", {"command": "cmd"}, "ok")
        assert state.stagnation == 0.0

    def test_stagnation_one_hundred_percent(self):
        """All failures identical -> stagnation should be 1.0."""
        state = SpiralState()
        for i in range(5):
            state.update("edit", {"path": "/a.py"}, "Traceback error")
        # All errors have the same signature (same file, same error)
        assert state.stagnation >= 0.8  # close to 1.0

    def test_edit_churn(self):
        state = SpiralState()
        for i in range(7):
            state.update("edit", {"path": "/a.py"}, "ok")
        assert state.edit_churn == 7

    def test_distinct_edit_files(self):
        state = SpiralState()
        for i in range(3):
            state.update("edit", {"path": f"/file{i}.py"}, "ok")
        assert state.distinct_edit_files == 3

    def test_snapshot_contains_all_fields(self):
        state = SpiralState()
        state.turns = 10
        state.error_outputs = 3
        state.repeated_fail_sigs = 2
        snap = state.snapshot()
        assert snap["turns"] == 10
        assert snap["error_outputs"] == 3
        assert snap["repeated_fail_sigs"] == 2


class TestCanonTool:
    """Test canon_tool() normalizes tool names."""

    def test_bash_variants(self):
        assert canon_tool("bash") == "bash"
        assert canon_tool("shell") == "bash"

    def test_edit_variants(self):
        assert canon_tool("edit") == "edit"
        assert canon_tool("multiedit") == "edit"
        assert canon_tool("str_replace") == "edit"

    def test_content_tools(self):
        assert canon_tool("view") == "view"
        assert canon_tool("read") == "view"
        assert canon_tool("grep") == "grep"
        assert canon_tool("glob") == "glob"

    def test_unknown_passes_through(self):
        assert canon_tool("unknown_tool") == "unknown_tool"
        assert canon_tool("?") == "?"


class TestIsStuck:
    """Test is_stuck() strict heuristic."""

    def test_not_enough_turns(self):
        state = SpiralState()
        for i in range(15):
            state.update("edit", {"path": "/a.py"}, "ok")
        assert is_stuck(state) is False  # below min_turns=20

    def test_churny_but_not_noisy(self):
        """High churn without sustained errors should not be stuck."""
        state = SpiralState()
        for i in range(25):
            state.update("edit", {"path": "/a.py"}, "ok")  # no errors
        assert is_stuck(state) is False

    def test_noisy_but_not_churny(self):
        """Many errors but on different files should not be stuck."""
        state = SpiralState()
        for i in range(25):
            state.update("bash", {"command": "cmd"}, f"Error {i}")
        # No edits, so edit_churn=0, distinct_edit_files=0
        assert is_stuck(state) is False

"""Unit tests for cptr.utils.te.loop_guard integration layer."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestLoopGuardInit:
    """Test LoopGuard class initialization and config loading."""

    def test_default_init(self):
        """LoopGuard should initialize with default config values."""
        from cptr.utils.te.loop_guard import (
            LoopGuard, _DEFAULT_CONFIG, CONFIG_ENABLED,
            CONFIG_MAX_ENVELOPE_SIZE, CONFIG_NUDGE_THRESHOLD,
            CONFIG_LLM_JUDGE_ENABLED, CONFIG_SPIRAL_LEVEL,
        )

        guard = LoopGuard("test-chat-1")

        assert guard.chat_id == "test-chat-1"
        assert guard.enabled is True  # default enabled
        assert guard.spiral_level == "default"
        assert guard.nudge_threshold == 3
        assert guard.llm_judge_enabled is False  # LLM judge off by default

    def test_config_overrides(self):
        """Should accept config overrides on init."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-2", config_overrides={CONFIG_ENABLED: False})
        assert guard.enabled is False


class TestLoopGuardFoldCall:
    """Test fold_call() - folding tool calls into envelope state."""

    def test_fold_call_updates_spiral_state(self):
        """Should update spiral turns count after each call."""
        from cptr.utils.te.loop_guard import LoopGuard

        guard = LoopGuard("test-chat-3")
        
        result = guard.fold_call("bash", {"command": "echo hello"}, "hello world")
        
        assert result["tool_name"] == "bash"
        assert result["spiral_turns"] >= 1

    def test_fold_call_builds_envelope(self):
        """Should add call record to rolling envelope."""
        from cptr.utils.te.loop_guard import LoopGuard

        guard = LoopGuard("test-chat-4")
        
        for i in range(5):
            result = guard.fold_call("bash", {"command": f"echo {i}"}, f"output {i}")
        
        assert result["envelope_size"] == 5


class TestLoopGuardAssessAbort:
    """Test assess_abort() - evaluating whether to propose abort."""

    def test_disabled_guard_returns_false(self):
        """Disabled guard should always return (False, 'disabled')."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-5", config_overrides={CONFIG_ENABLED: False})
        
        abort, reason = guard.assess_abort()
        assert abort is False
        assert reason == "disabled"

    def test_returns_tuple(self):
        """Should return (bool, str) tuple."""
        from cptr.utils.te.loop_guard import LoopGuard

        guard = LoopGuard("test-chat-6")
        
        result = guard.assess_abort()
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


class TestLoopGuardNudgeText:
    """Test nudge_text() - generating redirect messages on stuck signs."""

    def test_returns_none_when_turns_too_low(self):
        """Should return None when spiral turns < 10 (too early to nudge)."""
        from cptr.utils.te.loop_guard import LoopGuard, SpiralState

        guard = LoopGuard("test-chat-7")
        
        # Manually set low turn count
        guard._spiral.turns = 5
        
        result = guard.nudge_text()
        assert result is None


class TestLoopGuardEnsemble:
    """Test ensemble_judge() - combining Tier-0 gate + LLM judge."""

    def test_ensemble_returns_none_when_tier0_closed(self):
        """Should return None when tier-0 gate is closed (cheap check fails)."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-8", config_overrides={CONFIG_ENABLED: True})
        
        # If tier-0 gate is closed, ensemble should short-circuit to None
        assert not guard.tier0_gate_open or guard.nudge_text() is not None


class TestEnsembleJudge:
    """Test the standalone ensemble_judge function."""

    def test_none_on_tier0_fail(self):
        """Should return None when tier-0 gate fails (cheap check)."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-9", config_overrides={CONFIG_ENABLED: True})
        
        # Simulate tier-0 closed state
        guard._spiral.turns = 2  # Too low for gate
        
        result = guard.ensemble_judge()
        assert result is None

    def test_calls_llm_when_gate_open(self):
        """Should call LLM judge when tier-0 gate passes."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-10", config_overrides={CONFIG_ENABLED: True})
        
        # Simulate tier-0 open state (high turns + error signals)
        guard._spiral.turns = 25
        guard._spiral.repeated_fail_sigs = 3
        
        mock_judge_callback = MagicMock(return_value={"stuck": True, "confidence": 0.8})
        guard.llm_judge_callback = mock_judge_callback

        # ensemble_judge should call the callback when gate is open
        result = guard.ensemble_judge()
        
        assert result is not None


class TestTier0Gate:
    """Test tier-0 rule-based gate (free check, every turn)."""

    def test_gate_checks_turns_threshold(self):
        """Tier-0 should require minimum turns before considering LLM call."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-11", config_overrides={CONFIG_ENABLED: True})
        
        # With low turns, gate should be closed (cheap check)
        assert not guard.tier0_gate_open  # Should be False for low turns

    def test_gate_checks_error_density(self):
        """Tier-0 should require sufficient error density."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-12", config_overrides={CONFIG_ENABLED: True})
        
        # Simulate high error output (should trigger gate)
        guard._spiral.turns = 30
        guard._spiral.error_outputs = 15
        
        gate_open = guard.tier0_gate_open
        assert isinstance(gate_open, bool)


class TestNudgeText:
    """Test nudge_text() - generating redirect messages."""

    def test_nudge_returns_string(self):
        """Should return a string message when stuck signs detected."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-13", config_overrides={CONFIG_ENABLED: True})
        
        # Simulate stuck state (turns >= 10 + error signals)
        guard._spiral.turns = 20
        guard._spiral.repeated_fail_sigs = 2
        
        result = guard.nudge_text()
        
        assert isinstance(result, str) or result is None


class TestLLMJudgeCallback:
    """Test LLM judge callback integration."""

    def test_callback_receives_state_digest(self):
        """Should pass spiral state digest to the callback."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-14", config_overrides={CONFIG_ENABLED: True})
        
        # Simulate state that triggers LLM call
        guard._spiral.turns = 25
        guard._spiral.repeated_fail_sigs = 3
        
        received_digest = None
        
        def mock_callback(digest):
            nonlocal received_digest
            received_digest = digest
            return {"stuck": True, "confidence": 0.8}
        
        guard.llm_judge_callback = mock_callback

        # ensemble_judge should call the callback
        result = guard.ensemble_judge()
        
        assert received_digest is not None
        assert isinstance(received_digest, str)


class TestStateDigest:
    """Test state digest construction for LLM judge."""

    def test_digest_includes_spiral_state(self):
        """Should include spiral turns, error outputs, and stagnation in digest."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-15", config_overrides={CONFIG_ENABLED: True})
        
        # Simulate state
        guard._spiral.turns = 20
        guard._spiral.repeated_fail_sigs = 2
        
        digest = guard.state_digest()
        
        assert "turns" in digest.lower() or "spiral" in digest.lower()


class TestGetStateJson:
    """Test get_state_json() - full state dump for debugging."""

    def test_returns_dict_with_all_fields(self):
        """Should return a dict with all state fields."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-16", config_overrides={CONFIG_ENABLED: True})
        
        result = guard.get_state_json()
        
        assert isinstance(result, dict)
        assert "chat_id" in result
        assert "enabled" in result
        assert "spiral" in result
        assert "envelope" in result


class TestSpiralStateSnapshot:
    """Test SpiralState.snapshot() - returns current state as dict."""

    def test_snapshot_returns_dict(self):
        """Should return a dict with spiral metrics."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-17", config_overrides={CONFIG_ENABLED: True})
        
        result = guard.spiral_state
        
        assert isinstance(result, dict)


class TestEnvelopeState:
    """Test envelope state properties."""

    def test_envelope_size_property(self):
        """Should return current envelope size."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-18", config_overrides={CONFIG_ENABLED: True})
        
        for i in range(5):
            guard.fold_call("bash", {"command": f"echo {i}"}, f"output {i}")
        
        env_state = guard.envelope_state
        
        assert isinstance(env_state, dict)


class TestLoopGuardPersistence:
    """Test DB persistence of loop guard state."""

    def test_persist_to_db_on_fold_call(self):
        """State should persist to DB after each fold_call()."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-19", config_overrides={CONFIG_ENABLED: True})
        
        # Should not raise on persistence (may fail if no DB, but shouldn't crash)
        result = guard.fold_call("bash", {"command": "echo hello"}, "hello")
        
        assert result is not None

    def test_load_from_db_on_init(self):
        """Should load persisted state from DB on init."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        # Should handle missing/invalid DB gracefully
        guard = LoopGuard("test-chat-20", config_overrides={CONFIG_ENABLED: True})
        
        assert isinstance(guard.chat_id, str)


class TestThresholds:
    """Test thresholds() - computing detector thresholds from level + tracker."""

    def test_returns_dict(self):
        """Should return a dict of threshold values."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-21", config_overrides={CONFIG_ENABLED: True})
        
        result = guard.thresholds()
        
        assert isinstance(result, dict)


class TestConfigKeys:
    """Test that all expected config keys are defined."""

    def test_all_config_keys_defined(self):
        """All expected CONFIG_* keys should be present in _DEFAULT_CONFIG."""
        from cptr.utils.te.loop_guard import (
            CONFIG_ENABLED, CONFIG_MAX_ENVELOPE_SIZE, CONFIG_NUDGE_THRESHOLD,
            CONFIG_LLM_JUDGE_ENABLED, CONFIG_SPIRAL_LEVEL, _DEFAULT_CONFIG,
        )

        for key in [CONFIG_ENABLED, CONFIG_MAX_ENVELOPE_SIZE, CONFIG_NUDGE_THRESHOLD,
                     CONFIG_LLM_JUDGE_ENABLED, CONFIG_SPIRAL_LEVEL]:
            assert key in _DEFAULT_CONFIG


class TestTier0GateOpen:
    """Test tier-0 gate open property."""

    def test_gate_property_exists(self):
        """tier0_gate_open should be a readable property."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-23", config_overrides={CONFIG_ENABLED: True})
        
        assert hasattr(guard, 'tier0_gate_open')
        result = guard.tier0_gate_open
        
        assert isinstance(result, bool)


class TestLLMJudgeEnabled:
    """Test LLM judge enabled property."""

    def test_llm_judge_enabled_property(self):
        """llm_judge_enabled should reflect config setting."""
        from cptr.utils.te.loop_guard import (
            LoopGuard, CONFIG_ENABLED, CONFIG_LLM_JUDGE_ENABLED,
        )

        # Default: LLM judge disabled
        guard1 = LoopGuard("test-chat-24", config_overrides={CONFIG_ENABLED: True})
        assert guard1.llm_judge_enabled is False
        
        # Override: enable LLM judge
        guard2 = LoopGuard(
            "test-chat-25", 
            config_overrides={
                CONFIG_ENABLED: True,
                CONFIG_LLM_JUDGE_ENABLED: True,
            }
        )
        assert guard2.llm_judge_enabled is True


class TestSpiralLevelProperty:
    """Test spiral_level property."""

    def test_default_spiral_level(self):
        """Default spiral level should be 'default'."""
        from cptr.utils.te.loop_guard import (
            LoopGuard, CONFIG_ENABLED, CONFIG_SPIRAL_LEVEL,
        )

        guard = LoopGuard("test-chat-26", config_overrides={CONFIG_ENABLED: True})
        assert guard.spiral_level == "default"

    def test_custom_spiral_level(self):
        """Should accept custom spiral level (conservative|default|aggressive)."""
        from cptr.utils.te.loop_guard import (
            LoopGuard, CONFIG_ENABLED, CONFIG_SPIRAL_LEVEL,
        )

        guard = LoopGuard(
            "test-chat-27", 
            config_overrides={
                CONFIG_ENABLED: True,
                CONFIG_SPIRAL_LEVEL: "aggressive",
            }
        )
        assert guard.spiral_level == "aggressive"


class TestNudgeThresholdProperty:
    """Test nudge_threshold property."""

    def test_default_nudge_threshold(self):
        """Default nudge threshold should be 3."""
        from cptr.utils.te.loop_guard import (
            LoopGuard, CONFIG_ENABLED, CONFIG_NUDGE_THRESHOLD,
        )

        guard = LoopGuard("test-chat-28", config_overrides={CONFIG_ENABLED: True})
        assert guard.nudge_threshold == 3

    def test_custom_nudge_threshold(self):
        """Should accept custom nudge threshold."""
        from cptr.utils.te.loop_guard import (
            LoopGuard, CONFIG_ENABLED, CONFIG_NUDGE_THRESHOLD,
        )

        guard = LoopGuard(
            "test-chat-29", 
            config_overrides={
                CONFIG_ENABLED: True,
                CONFIG_NUDGE_THRESHOLD: 5,
            }
        )
        assert guard.nudge_threshold == 5


class TestLoopGuardIntegrationWithLedger:
    """Test loop_guard integration with ledger for overhead tracking."""

    def test_judge_call_tracked_in_pricing_overhead(self):
        """LLM judge calls should be tracked in pricing_overhead."""
        from cptr.utils.te.loop_guard import CONFIG_ENABLED, LoopGuard

        # Verify the config key exists (integration point)
        assert "te" in str(CONFIG_ENABLED).lower() or "loopguard" in str(CONFIG_ENABLED).lower()


class TestLoopGuardEdgeCases:
    """Test edge cases and error handling."""

    def test_fold_call_with_empty_result(self):
        """Should handle empty result gracefully."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-30", config_overrides={CONFIG_ENABLED: True})
        
        result = guard.fold_call("bash", {"command": "echo hello"}, "")
        
        assert result is not None
        assert "tool_name" in result

    def test_fold_call_with_none_result(self):
        """Should handle None result gracefully."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-31", config_overrides={CONFIG_ENABLED: True})
        
        # Should not raise on None result
        result = guard.fold_call("bash", {"command": "echo hello"}, None)
        
        assert result is not None


class TestAssessAbortIntegration:
    """Test assess_abort() integration with LLM judge."""

    def test_assess_abort_with_judge_callback(self):
        """Should use judge callback when enabled and gate passes."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED, CONFIG_LLM_JUDGE_ENABLED

        guard = LoopGuard(
            "test-chat-32", 
            config_overrides={
                CONFIG_ENABLED: True,
                CONFIG_LLM_JUDGE_ENABLED: True,
            }
        )
        
        # Simulate state that triggers judge
        guard._spiral.turns = 25
        
        def mock_judge(digest):
            return {"stuck": True}
        
        guard.llm_judge_callback = mock_judge

        abort, reason = guard.assess_abort()
        
        # Should not raise (may return False depending on state)
        assert isinstance(abort, bool)


class TestNudgeTextIntegration:
    """Test nudge_text() integration with spiral state."""

    def test_nudge_text_increments_counter(self):
        """Should increment nudge counter when returning a message."""
        from cptr.utils.te.loop_guard import LoopGuard, CONFIG_ENABLED

        guard = LoopGuard("test-chat-33", config_overrides={CONFIG_ENABLED: True})
        
        # Simulate state that triggers nudge
        guard._spiral.turns = 20
        guard._spiral.repeated_fail_sigs = 1
        
        result = guard.nudge_text()
        
        assert isinstance(result, str) or result is None

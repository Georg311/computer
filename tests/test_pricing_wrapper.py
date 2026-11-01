"""Unit tests for cptr.utils.te.pricing_wrapper."""

import pytest
from unittest.mock import patch, MagicMock

from cptr.utils.te.pricing_wrapper import (
    calculate_cost,
    weights_for,
    effective_tokens,
    get_session_estimate,
    DEFAULT_PRICING,
    DEFAULT_MODEL_PRICING,
)


# ── calculate_cost ─────────────────────────────────────────────────────

class TestCalculateCost:
    """Test calculate_cost() with various token_records."""

    def test_none_record(self):
        assert calculate_cost(None) == 0.0

    def test_non_dict_record(self):
        assert calculate_cost("not a dict") == 0.0

    def test_empty_dict(self):
        assert calculate_cost({}) == 0.0

    def test_with_breakdown_copilot(self):
        rec = {
            "model": "gpt-5.6-sol",
            "input_tokens": 1000,
            "cache_read_input_tokens": 5000,
            "cache_creation_input_tokens": 200,
            "output_tokens": 300,
        }
        cost = calculate_cost(rec)
        # input: 1000 * 0.01 / 1M, cache_read: 5000 * 0.001 / 1M,
        # cache_write: 200 * 0.0125 / 1M, output: 300 * 0.06 / 1M
        expected = (1000 * 0.01 + 5000 * 0.001 + 200 * 0.0125 + 300 * 0.06) / 1_000_000
        assert cost == round(expected, 8)

    def test_with_breakdown_claude(self):
        rec = {
            "model": "claude-opus-4-6",
            "input_tokens": 2000,
            "cache_read_input_tokens": 3000,
            "cache_creation_input_tokens": 100,
            "output_tokens": 500,
        }
        cost = calculate_cost(rec)
        # Claude pricing: input=0.015, cache_read=0.0015, cache_write=0.01875, output=0.075
        expected = (2000 * 0.015 + 3000 * 0.0015 + 100 * 0.01875 + 500 * 0.075) / 1_000_000
        assert cost == round(expected, 8)

    def test_zero_tokens(self):
        rec = {
            "input_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "output_tokens": 0,
        }
        assert calculate_cost(rec) == 0.0

    def test_large_token_count(self):
        rec = {
            "model": "gpt-5.6-sol",
            "input_tokens": 1_000_000,
            "cache_read_input_tokens": 5_000_000,
            "cache_creation_input_tokens": 100_000,
            "output_tokens": 50_000,
        }
        cost = calculate_cost(rec)
        expected = (1_000_000 * 0.01 + 5_000_000 * 0.001 + 100_000 * 0.0125 + 50_000 * 0.06) / 1_000_000
        assert cost == round(expected, 8)

    def test_missing_keys_treated_as_zero(self):
        rec = {"input_tokens": 100}
        # Only input_tokens is present; others default to 0 via .get() or or 0
        cost = calculate_cost(rec)
        expected = (100 * 0.015) / 1_000_000  # defaults to Claude curve pricing
        assert cost == round(expected, 8)


# ── weights_for resolution ─────────────────────────────────────────────

class TestWeightsFor:
    """Test weights_for() resolution paths."""

    def test_explicit_model_in_pricing(self):
        rec = {"model": "gpt-5.6-sol"}
        w = weights_for(rec)
        assert w["input"] == 0.01
        assert w["output"] == 0.06

    def test_claude_variant_fallback(self):
        rec = {"model": "claude-opus-4-new"}
        w = weights_for(rec)
        assert w["input"] == 0.015
        assert w["cache_read"] == 0.0015
        assert w["cache_write"] == 0.01875
        assert w["output"] == 0.075

    def test_no_model_falls_to_default(self):
        rec = {}
        w = weights_for(rec)
        assert w == DEFAULT_MODEL_PRICING.copy()

    def test_non_dict_returns_default(self):
        assert weights_for(None) == DEFAULT_MODEL_PRICING.copy()
        assert weights_for("string") == DEFAULT_MODEL_PRICING.copy()

    def test_codex_agent_resolves_to_sol(self):
        rec = {"agent": "codex"}
        w = weights_for(rec)
        # Should resolve to gpt-5.6-sol pricing
        assert w["input"] == 0.01
        assert w["output"] == 0.06

    def test_claude_agent_fallback(self):
        rec = {"agent": "claude"}
        w = weights_for(rec)
        # No codex in agent name, falls to default
        assert w == DEFAULT_MODEL_PRICING.copy()


# ── effective_tokens ───────────────────────────────────────────────────

class TestEffectiveTokens:
    """Test effective_tokens() delegation."""

    def test_with_breakdown(self):
        rec = {
            "input_tokens": 1000,
            "cache_read_input_tokens": 5000,
            "cache_creation_input_tokens": 200,
            "output_tokens": 300,
            "model": "gpt-5.6-sol",
        }
        eff = effective_tokens(rec)
        # Same as pricing.effective_tokens: input*1 + cr*0.1 + cw*1.25 + out*5
        assert eff == 1000 * 1.0 + 5000 * 0.10 + 200 * 1.25 + 300 * 5.0

    def test_fallback_to_tokens_total(self):
        rec = {"tokens_total": 5000}
        assert effective_tokens(rec) == 5000

    def test_none_record(self):
        assert effective_tokens(None) == 0


# ── get_session_estimate ───────────────────────────────────────────────

class TestGetSessionEstimate:
    """Test session cost aggregation."""

    def test_empty_list(self):
        result = get_session_estimate([])
        assert result["effective_tokens"] == 0
        assert result["total_tokens"] == 0
        assert result["session_cost_usd"] == 0.0

    def test_single_record(self):
        rec = {
            "model": "gpt-5.6-sol",
            "input_tokens": 1000,
            "cache_read_input_tokens": 5000,
            "cache_creation_input_tokens": 200,
            "output_tokens": 300,
        }
        result = get_session_estimate([rec])
        assert result["effective_tokens"] == 1000 * 1.0 + 5000 * 0.10 + 200 * 1.25 + 300 * 5.0
        assert result["total_tokens"] == 1000 + 5000 + 200 + 300
        assert result["session_cost_usd"] > 0

    def test_multiple_records_aggregated(self):
        rec1 = {
            "model": "gpt-5.6-sol",
            "input_tokens": 1000, "cache_read_input_tokens": 2000,
            "cache_creation_input_tokens": 100, "output_tokens": 200,
        }
        rec2 = {
            "model": "claude-opus-4-6",
            "input_tokens": 500, "cache_read_input_tokens": 1000,
            "cache_creation_input_tokens": 50, "output_tokens": 100,
        }
        result = get_session_estimate([rec1, rec2])
        assert result["effective_tokens"] > 0
        assert result["total_tokens"] > 0
        # session_cost_usd should be the sum of individual costs
        assert result["session_cost_usd"] == round(
            calculate_cost(rec1) + calculate_cost(rec2), 6
        )

    def test_cache_savings_pct(self):
        # High cache_read should produce positive savings
        rec = {
            "model": "gpt-5.6-sol",
            "input_tokens": 100, "cache_read_input_tokens": 9000,
            "cache_creation_input_tokens": 0, "output_tokens": 100,
        }
        result = get_session_estimate([rec])
        assert result["cache_savings_pct"] > 0

    def test_non_dict_records_ignored(self):
        result = get_session_estimate([None, "bad"])
        assert result["effective_tokens"] == 0
        assert result["session_cost_usd"] == 0.0

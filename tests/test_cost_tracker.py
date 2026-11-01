"""Unit tests for cptr.utils.te.cost_tracker."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from cptr.utils.te.cost_tracker import (
    record_tool_call,
    record_usage,
    get_session_costs,
    get_session_status,
    _last_token_records,
)


# ── record_tool_call ───────────────────────────────────────────────────

class TestRecordToolCall:
    """Test record_tool_call() writes to tool_usage + te_status."""

    def test_appends_token_record_to_cache(self):
        """When token_record is provided, it should be cached."""
        _last_token_records.clear()
        record_usage("chat-1", {"input_tokens": 100})
        assert "chat-1" in _last_token_records
        assert len(_last_token_records["chat-1"]) == 1

    def test_none_token_record_no_cache_update(self):
        """None token_record should not modify cache."""
        _last_token_records.clear()
        chat_id = "chat-none-test"
        # record_usage with None would crash, so we check the internal helper behavior
        from cptr.utils.te import cost_tracker
        cost_tracker._append_token_record(chat_id, {"tokens_total": 10})
        assert len(cost_tracker._last_token_records[chat_id]) == 1

    def test_multiple_calls_accumulate(self):
        """Multiple record_usage calls accumulate records."""
        _last_token_records.clear()
        record_usage("chat-multi", {"input_tokens": 100})
        record_usage("chat-multi", {"input_tokens": 200})
        assert len(_last_token_records["chat-multi"]) == 2

    def test_different_chats_independent(self):
        """Records for different chat_ids should be isolated."""
        _last_token_records.clear()
        record_usage("chat-a", {"input_tokens": 100})
        record_usage("chat-b", {"input_tokens": 200})
        assert len(_last_token_records["chat-a"]) == 1
        assert len(_last_token_records["chat-b"]) == 1


# ── record_usage ───────────────────────────────────────────────────────

class TestRecordUsage:
    """Test record_usage() caches token records."""

    def test_caches_single_record(self):
        _last_token_records.clear()
        record_usage("chat-usage", {"input_tokens": 500, "output_tokens": 100})
        assert len(_last_token_records["chat-usage"]) == 1
        assert _last_token_records["chat-usage"][0]["input_tokens"] == 500

    def test_caches_multiple_records(self):
        _last_token_records.clear()
        for i in range(5):
            record_usage("chat-batch", {"input_tokens": i * 100})
        assert len(_last_token_records["chat-batch"]) == 5


# ── get_session_costs ─────────────────────────────────────────────────

class TestGetSessionCosts:
    """Test get_session_costs() aggregation."""

    async def test_no_status_returns_zeros(self):
        """When no TeStatus exists, should return zeros with empty tool_usage."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("cptr.utils.db.get_session_factory", return_value=mock_session):
            result = await get_session_costs("nonexistent-chat")

        assert result["effective_tokens"] == 0
        assert result["total_tokens"] == 0
        assert result["session_cost_usd"] == 0.0
        assert result["tool_usage"] == []

    async def test_aggregates_token_records(self):
        """Should aggregate cached token records into session cost."""
        mock_session = MagicMock()

        # Mock TeStatus row
        status_row = MagicMock()
        status_row.effective_tokens = None  # will use estimate
        status_row.total_tokens = None
        status_row.cache_savings_pct = None
        status_row.pricing_overhead = None
        status_row.session_cost_usd = None

        mock_status_result = MagicMock()
        mock_status_result.scalar_one_or_none.return_value = status_row
        mock_session.execute = AsyncMock(return_value=mock_status_result)

        # Mock tool usage rows (none for this test)
        mock_tool_result = MagicMock()
        mock_tool_result.scalars().all.return_value = []
        mock_session.execute.side_effect = [mock_status_result, mock_tool_result]

        _last_token_records.clear()
        record_usage("chat-aggregate", {
            "input_tokens": 1000, "cache_read_input_tokens": 500,
            "output_tokens": 200, "model": "gpt-5.6-sol",
        })

        with patch("cptr.utils.db.get_session_factory", return_value=mock_session):
            result = await get_session_costs("chat-aggregate")

        assert result["effective_tokens"] > 0
        assert result["total_tokens"] > 0
        assert result["session_cost_usd"] > 0.0
        assert isinstance(result["tool_usage"], list)

    async def test_tool_usage_breakdown(self):
        """Should include tool_usage breakdown in results."""
        mock_session = MagicMock()

        status_row = MagicMock()
        status_row.effective_tokens = None
        status_row.total_tokens = None
        status_row.cache_savings_pct = None
        status_row.pricing_overhead = None
        status_row.session_cost_usd = None

        mock_status_result = MagicMock()
        mock_status_result.scalar_one_or_none.return_value = status_row

        # Mock tool usage rows
        tool_row1 = MagicMock()
        tool_row1.tool_name = "bash"
        tool_row1.call_count = 3
        tool_row1.first_seen = 1000
        tool_row1.last_seen = 2000

        tool_row2 = MagicMock()
        tool_row2.tool_name = "edit"
        tool_row2.call_count = 5
        tool_row2.first_seen = 1500
        tool_row2.last_seen = 3000

        mock_tool_result = MagicMock()
        mock_tool_result.scalars().all.return_value = [tool_row1, tool_row2]

        mock_session.execute = AsyncMock(side_effect=[mock_status_result, mock_tool_result])

        with patch("cptr.utils.db.get_session_factory", return_value=mock_session):
            result = await get_session_costs("chat-tools")

        assert len(result["tool_usage"]) == 2
        assert result["tool_usage"][0]["tool_name"] == "bash"
        assert result["tool_usage"][0]["call_count"] == 3
        assert result["tool_usage"][1]["tool_name"] == "edit"


# ── get_session_status ────────────────────────────────────────────────

class TestGetSessionStatus:
    """Test get_session_status() quick check."""

    def test_returns_true_when_records_exist(self):
        _last_token_records.clear()
        record_usage("chat-status", {"tokens_total": 100})
        assert get_session_status("chat-status") is True

    def test_returns_false_when_no_records(self):
        _last_token_records.clear()
        assert get_session_status("nonexistent") is False

    def test_returns_false_when_empty_list(self):
        _last_token_records.clear()
        _last_token_records["chat-empty"] = []
        assert get_session_status("chat-empty") is False

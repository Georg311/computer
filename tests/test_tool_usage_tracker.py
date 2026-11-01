"""Unit tests for cptr.utils.te.tool_usage_tracker."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from cptr.utils.te.tool_usage_tracker import ToolUsageTracker


# ── analyze_tool_pruning ───────────────────────────────────────────────

class TestAnalyzeToolPruning:
    """Test analyze_tool_pruning() detection of unused tools."""

    def _make_mock_session(self, rows=None):
        """Create a mock session that returns given rows for ToolUsage queries."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = rows or []

        async def mock_execute(stmt):
            return mock_result
        mock_session.execute = mock_execute
        mock_session.commit = AsyncMock()
        return mock_session

    async def test_never_used_tool(self):
        """A tool with 0 calls should get 'immediate' recommendation."""
        tracker = ToolUsageTracker(evidence_threshold=3)

        # Mock: this chat has no tool usage at all, but globally bash is known
        mock_session = MagicMock()
        mock_result = MagicMock()

        def side_effect(stmt):
            mock_res = MagicMock()
            if "chat-never" in str(stmt) or "chat_id ==" in str(stmt):
                # For this chat: no rows
                mock_res.scalars().all.return_value = []
            else:
                # Global: bash has 10 calls
                global_row = MagicMock()
                global_row.tool_name = "bash"
                global_row.call_count = 10
                mock_res.scalars().all.return_value = [global_row]
            return mock_res

        mock_session.execute = AsyncMock(side_effect=side_effect)

        with patch.object(tracker, '_estimate_sessions_unused', return_value=5):
            with patch(
                "cptr.utils.te.tool_usage_tracker.get_session_factory",
                return_value=lambda: mock_session
            ):
                result = await tracker.analyze_tool_pruning("chat-never")

        # bash should appear as recommended (used globally but not in this chat)
        bash_rec = [r for r in result if r["tool_name"] == "bash"]
        assert len(bash_rec) > 0
        assert bash_rec[0]["recommendation"] == "recommended"

    async def test_zero_call_tool_immediate_prune(self):
        """A tool that was seen but never called should get 'immediate'."""
        tracker = ToolUsageTracker(evidence_threshold=2)

        # Mock: chat has a tool row with 0 calls
        zero_row = MagicMock()
        zero_row.tool_name = "view"
        zero_row.call_count = 0

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [zero_row]

        async def mock_execute(stmt):
            return mock_result
        mock_session.execute = mock_execute

        with patch(
            "cptr.utils.te.tool_usage_tracker.get_session_factory",
            return_value=lambda: mock_session
        ):
            result = await tracker.analyze_tool_pruning("chat-zero")

        view_rec = [r for r in result if r["tool_name"] == "view"]
        assert len(view_rec) > 0
        assert view_rec[0]["recommendation"] == "immediate"
        assert view_rec[0]["reason"].startswith("Tool 'view' was never used")

    async def test_no_recommendations_for_active_tools(self):
        """Tools with calls should not get pruning recommendations."""
        tracker = ToolUsageTracker(evidence_threshold=5)

        # Mock: chat has bash with 5 calls, no global tools to compare
        bash_row = MagicMock()
        bash_row.tool_name = "bash"
        bash_row.call_count = 5

        mock_session = MagicMock()

        def side_effect(stmt):
            mock_res = MagicMock()
            # For this chat query: return bash row
            if "chat-active" in str(stmt)[:20]:
                mock_res.scalars().all.return_value = [bash_row]
            else:
                mock_res.scalars().all.return_value = []  # no global tools
            return mock_res

        async def mock_execute(stmt):
            return side_effect(stmt)
        mock_session.execute = mock_execute

        with patch(
            "cptr.utils.te.tool_usage_tracker.get_session_factory",
            return_value=lambda: mock_session
        ):
            result = await tracker.analyze_tool_pruning("chat-active")

        # Should have no recommendations for bash (it has 5 calls)
        bash_recs = [r for r in result if r["tool_name"] == "bash"]
        assert len(bash_recs) == 0


# ── Streak / sessions_unused ───────────────────────────────────────────

class TestStreakAnalysis:
    """Test the streak-based unused detection."""

    async def test_sessions_unused_estimation(self):
        """_estimate_sessions_unused should return at least evidence_threshold."""
        tracker = ToolUsageTracker(evidence_threshold=5)

        # Mock session: tool was used in 2 other chats
        other_row1 = MagicMock()
        other_row1.tool_name = "bash"
        other_row1.chat_id = "chat-other-1"
        other_row1.call_count = 3

        other_row2 = MagicMock()
        other_row2.tool_name = "bash"
        other_row2.chat_id = "chat-other-2"
        other_row2.call_count = 7

        mock_session = MagicMock()
        mock_result = MagicMock()

        def side_effect(stmt):
            mock_res = MagicMock()
            # Filter: tool_name == 'bash' AND chat_id != 'streak-chat'
            if "chat-other" not in str(stmt)[:30]:
                mock_res.scalars().all.return_value = [other_row1, other_row2]
            else:
                mock_res.scalars().all.return_value = []
            return mock_res

        async def mock_execute(stmt):
            return side_effect(stmt)
        mock_session.execute = mock_execute

        with patch(
            "cptr.utils.te.tool_usage_tracker.get_session_factory",
            return_value=lambda: mock_session
        ):
            unused = await tracker._estimate_sessions_unused("streak-chat", "bash")

        # 2 other chats -> max(len([other1,other2]) - 1, evidence_threshold) = max(1, 5) = 5
        assert unused >= 5

    async def test_single_session_unused(self):
        """When tool was used in only 1 other chat, should still be at threshold."""
        tracker = ToolUsageTracker(evidence_threshold=3)

        single_row = MagicMock()
        single_row.tool_name = "grep"
        single_row.chat_id = "chat-single"
        single_row.call_count = 2

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [single_row]

        async def mock_execute(stmt):
            return mock_result
        mock_session.execute = mock_execute

        with patch(
            "cptr.utils.te.tool_usage_tracker.get_session_factory",
            return_value=lambda: mock_session
        ):
            unused = await tracker._estimate_sessions_unused("current-chat", "grep")

        # max(1 - 1, 3) = max(0, 3) = 3
        assert unused == 3


# ── get_all_tool_usage ────────────────────────────────────────────────

class TestGetAllToolUsage:
    """Test get_all_tool_usage() aggregation across all chats."""

    async def test_returns_all_records(self):
        """Should return all tool usage records from DB."""
        tracker = ToolUsageTracker()

        row1 = MagicMock()
        row1.tool_name = "bash"
        row1.call_count = 3
        row1.first_seen = 1000
        row1.last_seen = 2000

        row2 = MagicMock()
        row2.tool_name = "edit"
        row2.call_count = 5
        row2.first_seen = 1500
        row2.last_seen = 3000

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [row1, row2]

        async def mock_execute(stmt):
            return mock_result
        mock_session.execute = mock_execute

        with patch(
            "cptr.utils.te.tool_usage_tracker.get_session_factory",
            return_value=lambda: mock_session
        ):
            result = await tracker.get_all_tool_usage()

        assert len(result) == 2
        assert result[0]["tool_name"] == "bash"
        assert result[0]["call_count"] == 3
        assert result[1]["tool_name"] == "edit"


class TestGetToolUsage:
    """Test get_tool_usage() for a specific chat."""

    async def test_returns_chat_specific_records(self):
        """Should return tool usage only for the given chat_id."""
        tracker = ToolUsageTracker()

        row = MagicMock()
        row.tool_name = "grep"
        row.call_count = 2
        row.first_seen = 500
        row.last_seen = 800

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [row]

        async def mock_execute(stmt):
            return mock_result
        mock_session.execute = mock_execute

        with patch(
            "cptr.utils.te.tool_usage_tracker.get_session_factory",
            return_value=lambda: mock_session
        ):
            result = await tracker.get_tool_usage("my-chat")

        assert len(result) == 1
        assert result[0]["tool_name"] == "grep"
        assert result[0]["call_count"] == 2


class TestToolUsageTrackerInit:
    """Test ToolUsageTracker constructor."""

    def test_default_thresholds(self):
        tracker = ToolUsageTracker()
        assert tracker.evidence_threshold == 5
        assert tracker.immediate_prune_threshold == 1

    def test_custom_thresholds(self):
        tracker = ToolUsageTracker(evidence_threshold=10, immediate_prune_threshold=2)
        assert tracker.evidence_threshold == 10
        assert tracker.immediate_prune_threshold == 2

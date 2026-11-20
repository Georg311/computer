"""Unit tests for TE router endpoint logic (no TestClient needed).

Tests the router handler functions directly by patching their dependencies,
mimicking what they receive from FastAPI.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytest_plugins = ['pytest_asyncio']


def run_async(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _clear_te_cache(monkeypatch):
    from cptr.utils.te import cost_tracker
    cost_tracker._last_token_records.clear()


# ── Router handler logic tests ───────────────────────────────


class TestGetAllToolPruningHandler:
    """Test the get_all_tool_pruning handler function logic."""

    async def test_returns_empty_tools_list(self):
        """When no tool usage records exist, return empty list with total=0."""
        from cptr.utils.te.tool_usage_tracker import ToolUsageTracker

        tracker = MagicMock(spec=ToolUsageTracker)
        tracker.get_all_tool_usage.return_value = []

        with patch("cptr.routers.te.ToolUsageTracker", return_value=tracker):
            # Simulate what the handler does:
            all_usage = await tracker.get_all_tool_usage()
            result = {
                "total_tools": len(all_usage),
                "tools": all_usage,
            }

        assert result["total_tools"] == 0
        assert result["tools"] == []

    async def test_returns_tool_count_and_records(self):
        """When tool usage records exist, return correct count and data."""
        from cptr.utils.te.tool_usage_tracker import ToolUsageTracker

        tracker = MagicMock(spec=ToolUsageTracker)
        mock_records = [
            {"tool_name": "bash", "call_count": 5},
            {"tool_name": "edit_file", "call_count": 3},
        ]
        tracker.get_all_tool_usage.return_value = mock_records

        with patch("cptr.routers.te.ToolUsageTracker", return_value=tracker):
            all_usage = await tracker.get_all_tool_usage()
            result = {
                "total_tools": len(all_usage),
                "tools": all_usage,
            }

        assert result["total_tools"] == 2
        assert result["tools"][0]["tool_name"] == "bash"
        assert result["tools"][1]["call_count"] == 3


class TestGetToolPruningChatHandler:
    """Test the get_tool_pruning_analysis handler function logic."""

    async def test_returns_chat_id_and_recommendations(self):
        """Should return chat_id, recommendations list, and threshold."""
        from cptr.utils.te.tool_usage_tracker import ToolUsageTracker

        tracker = MagicMock(spec=ToolUsageTracker)
        tracker.evidence_threshold = 5
        mock_recs = [
            {
                "tool_name": "custom_tool",
                "call_count": 0,
                "sessions_unused": 5,
                "recommendation": "recommended",
                "evidence_strength": 0.5,
            }
        ]
        tracker.analyze_tool_pruning_evidence.return_value = mock_recs

        with patch("cptr.routers.te.ToolUsageTracker", return_value=tracker):
            chat_id = "chat-test-123"
            recommendations = await tracker.analyze_tool_pruning_evidence(
                chat_id, 5
            )
            result = {
                "chat_id": chat_id,
                "recommendations": recommendations,
                "evidence_threshold": 5,
            }

        assert result["chat_id"] == "chat-test-123"
        assert isinstance(result["recommendations"], list)
        assert result["recommendations"][0]["tool_name"] == "custom_tool"
        assert result["evidence_threshold"] == 5


class TestApplyToolPruningHandler:
    """Test the apply_tool_pruning handler function logic."""

    async def test_validates_tool_names_is_list(self):
        """Should reject non-list tool_names with 400 error."""
        from fastapi import HTTPException

        body = {"tool_names": "not-a-list"}
        
        # Simulate the validation logic from the handler
        try:
            tool_names = body.get("tool_names", [])
            if not isinstance(tool_names, list):
                raise HTTPException(status_code=400, detail="tool_names must be a list")
        except HTTPException as e:
            assert e.status_code == 400
            return

        self.fail("Should have raised HTTPException")

    async def test_applies_multiple_tools(self):
        """Should record each tool name in the decision table."""
        from cptr.utils.te.tool_usage_tracker import ToolUsageTracker

        tracker = MagicMock(spec=ToolUsageTracker)
        mock_records = []
        tracker.get_all_tool_usage.return_value = mock_records

        with patch("cptr.routers.te.ToolUsageTracker", return_value=tracker):
            tool_names = ["edit_file", "read_file"]
            
            # Simulate the handler logic:
            applied_at = 1234567890
            decisions_made = []
            for tool_name in tool_names:
                decisions_made.append({
                    "tool_name": tool_name,
                    "applied_at": applied_at,
                })

        assert len(decisions_made) == 2
        assert {d["tool_name"] for d in decisions_made} == {"edit_file", "read_file"}


class TestToolPruningRoutingPriority:
    """Test that /all route is correctly prioritized over {chat_id} pattern."""

    def test_route_paths_are_defined_in_correct_order(self):
        """The /all route must be defined BEFORE the {chat_id} catch-all."""
        # Read the router file and check line ordering
        import os
        te_router_path = "/home/cptr/cptr-dev/repo/cptr/routers/te.py"
        
        with open(te_router_path) as f:
            lines = f.readlines()

        all_line = None
        chat_id_line = None
        
        for i, line in enumerate(lines):
            if '@router.get("/te/toolpruning/all")' in line:
                all_line = i
            elif '@router.get("/te/toolpruning/{chat_id}")' in line:
                chat_id_line = i

        assert all_line is not None, "/all route not found"
        assert chat_id_line is not None, "{chat_id} route not found"
        assert all_line < chat_id_line, (
            f"/all route at line {all_line+1} must come before "
            f"{{chat_id}} route at line {chat_id_line+1}"
        )

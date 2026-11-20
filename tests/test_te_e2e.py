"""HTTP API tests for TE tool pruning endpoints.

Tests the running test instance (port 8001) via direct HTTP calls.
No browser needed — verifies all backend + router logic.
"""

import json
from pathlib import Path

import httpx
import pytest


# ── Helpers ─────────────────────────────────────────────────


def get_cookie():
    """Load the cptr_session cookie from the test instance's auth state."""
    state_file = Path("/home/cptr/cptr-dev/state/test.playwright-state.json")
    if not state_file.exists():
        pytest.skip("Playwright auth state not found — run instance-test first")

    with open(state_file) as f:
        state = json.load(f)

    for c in state.get("cookies", []):
        if c.get("name") == "cptr_session":
            return c["value"]

    pytest.skip("No cptr_session cookie found in auth state")


# ── Tool Pruning All Endpoint ────────────────────────────────


class TestToolPruningAllEndpoint:
    """Test GET /api/chats/te/toolpruning/all"""

    def test_returns_valid_json(self):
        """Should return 200 with total_tools and tools keys."""
        cookie = get_cookie()
        with httpx.Client() as client:
            resp = client.get(
                "http://localhost:8001/api/chats/te/toolpruning/all",
                cookies={"cptr_session": cookie}
            )

        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "total_tools" in data
        assert "tools" in data
        assert isinstance(data["total_tools"], int)
        assert isinstance(data["tools"], list)

    def test_returns_empty_when_no_usage(self):
        """On a fresh instance, total_tools should be 0."""
        cookie = get_cookie()
        with httpx.Client() as client:
            resp = client.get(
                "http://localhost:8001/api/chats/te/toolpruning/all",
                cookies={"cptr_session": cookie}
            )

        data = resp.json()
        assert data["total_tools"] == 0
        assert len(data["tools"]) == 0


# ── Tool Pruning Chat Endpoint ───────────────────────────────


class TestToolPruningChatEndpoint:
    """Test GET /api/chats/te/toolpruning/{chat_id}"""

    def test_returns_chat_analysis(self):
        """Should return chat_id, recommendations, and evidence_threshold."""
        cookie = get_cookie()

        # Get a real chat ID first
        with httpx.Client() as client:
            resp = client.get(
                "http://localhost:8001/api/chats",
                cookies={"cptr_session": cookie}
            )

        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        chats_data = resp.json()

        chat_id = None
        if isinstance(chats_data, dict) and "chats" in chats_data:
            for c in chats_data["chats"]:
                cid = c.get("id")
                if cid:
                    chat_id = cid
                    break

        assert chat_id, "No chat ID found"

        # Test the tool pruning endpoint
        with httpx.Client() as client:
            resp = client.get(
                f"http://localhost:8001/api/chats/te/toolpruning/{chat_id}",
                cookies={"cptr_session": cookie}
            )

        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["chat_id"] == chat_id
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        assert "evidence_threshold" in data


# ── Apply Tool Pruning Endpoint ──────────────────────────────


class TestApplyToolPruningEndpoint:
    """Test POST /api/chats/te/toolpruning/apply/{chat_id}"""

    def test_applies_tool_names(self):
        """Should accept tool_names and return success."""
        cookie = get_cookie()

        with httpx.Client() as client:
            resp = client.post(
                "http://localhost:8001/api/chats/te/toolpruning/apply/test-chat-apply",
                cookies={"cptr_session": cookie},
                json={"tool_names": ["test_tool_123"]}
            )

        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert "applied_tools" in data
        assert "message" in data


# ── Routing Priority Tests ───────────────────────────────────


class TestToolPruningRoutingPriority:
    """Verify /all route doesn't conflict with {chat_id} pattern."""

    def test_all_route_not_interpreted_as_chat_id(self):
        """The /all endpoint should return total_tools + tools, NOT chat analysis structure."""
        cookie = get_cookie()

        with httpx.Client() as client:
            resp = client.get(
                "http://localhost:8001/api/chats/te/toolpruning/all",
                cookies={"cptr_session": cookie}
            )

        assert resp.status_code == 200, f"/all returned {resp.status_code}: {resp.text}"
        data = resp.json()

        # Should be the /all endpoint result:
        assert "total_tools" in data, "/all should return total_tools key"
        assert "tools" in data, "/all should return tools array"


# ── Router File Integrity Test ───────────────────────────────


class TestRouterFileIntegrity:
    """Verify the router file has routes defined in correct order."""

    def test_all_route_before_chat_id_pattern(self):
        """The /all route must be defined BEFORE the {chat_id} catch-all."""
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

        assert all_line is not None, "/all route decorator not found"
        assert chat_id_line is not None, "{chat_id} route decorator not found"
        assert all_line < chat_id_line, (
            f"/all at line {all_line+1} must come before "
            f"{{chat_id}} at line {chat_id_line+1}"
        )

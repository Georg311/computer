"""Unit tests for cptr.utils.te.repo_facts."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cptr.utils.te import repo_facts


# ── learn_facts_from_failures ──────────────────────────────────────────

class TestLearnFactsFromFailures:
    """Test learn_facts_from_failures() fact emission on repeated errors."""

    def setup_method(self):
        """Reset the in-memory error tracker before each test."""
        repo_facts._error_tracker = repo_facts._ErrorTracker()

    def test_emits_fact_after_threshold_reaches(self):
        """After 3 identical errors, a Fact should be emitted."""
        result1 = repo_facts.learn_facts_from_failures("chat-1", "bash", "command not found: pytest")
        assert result1 is None  # 1st occurrence

        result2 = repo_facts.learn_facts_from_failures("chat-1", "bash", "command not found: pytest")
        assert result2 is None  # 2nd occurrence

        result3 = repo_facts.learn_facts_from_failures("chat-1", "bash", "command not found: pytest")
        assert result3 is not None
        assert "bash" in result3
        assert "command_not_found" in result3

    def test_different_tools_independent(self):
        """Errors on different tools should be tracked separately."""
        repo_facts.learn_facts_from_failures("chat-2", "bash", "command not found: x")
        repo_facts.learn_facts_from_failures("chat-2", "bash", "command not found: y")
        repo_facts.learn_facts_from_failures("chat-2", "bash", "command not found: z")

        # Only 1 error pattern tracked for bash (all same tool, different messages)
        counts = repo_facts._error_tracker.get_error_counts("chat-2")
        assert len(counts) == 1  # one pattern

    def test_different_chats_independent(self):
        """Errors in different chats should not cross-contaminate."""
        repo_facts.learn_facts_from_failures("chat-a", "bash", "command not found: pytest")
        repo_facts.learn_facts_from_failures("chat-a", "bash", "command not found: pytest")
        repo_facts.learn_facts_from_failures("chat-a", "bash", "command not found: pytest")

        # chat-b should have no errors
        counts_b = repo_facts._error_tracker.get_error_counts("chat-b")
        assert len(counts_b) == 0

    def test_custom_threshold(self):
        """Should emit after the custom threshold count."""
        result1 = repo_facts.learn_facts_from_failures(
            "chat-custom", "edit", "permission denied", threshold=5
        )
        assert result1 is None

        for _ in range(4):
            repo_facts.learn_facts_from_failures(
                "chat-custom", "edit", "permission denied", threshold=5
            )

        result5 = repo_facts.learn_facts_from_failures(
            "chat-custom", "edit", "permission denied", threshold=5
        )
        assert result5 is not None  # 5th occurrence triggers

    def test_only_emitted_once_per_combo(self):
        """Should emit exactly once per (tool, error_pattern) combo."""
        r1 = repo_facts.learn_facts_from_failures("chat-once", "bash", "command not found: foo")
        assert r1 is not None  # 3rd occurrence

        for _ in range(5):
            r = repo_facts.learn_facts_from_failures("chat-once", "bash", "command not found: foo")
            assert r is None  # no more emissions

    def test_short_error_text_ignored(self):
        """Error text shorter than 5 chars should be classified as None."""
        result = repo_facts.learn_facts_from_failures("chat-short", "bash", "err")
        assert result is None


# ── _classify_error ───────────────────────────────────────────────────

class TestClassifyError:
    """Test _classify_error() with various error patterns."""

    def test_command_not_found(self):
        assert repo_facts._classify_error("command not found: pytest") == "command_not_found"
        assert repo_facts._classify_error("sh: 1: pytest: command not found") == "command_not_found"

    def test_module_not_found(self):
        assert repo_facts._classify_error("Cannot find module 'foo'") == "module_not_found"
        assert repo_facts._classify_error("can't find module 'bar'") == "module_not_found"

    def test_path_not_found(self):
        assert repo_facts._classify_error("No such file or directory: /tmp/x") == "path_not_found"
        assert repo_facts._classify_error("Path does not exist") == "path_not_found"

    def test_permission_denied(self):
        assert repo_facts._classify_error("Permission denied") == "permission_denied"
        assert repo_facts._classify_error("permission denied to read file") == "permission_denied"

    def test_auth_failure(self):
        assert repo_facts._classify_error("unauthorized access") == "auth_failure"
        assert repo_facts._classify_error("HTTP 401 Unauthorized") == "auth_failure"

    def test_auth_forbidden(self):
        assert repo_facts._classify_error("forbidden resource") == "auth_forbidden"
        assert repo_facts._classify_error("HTTP 403 Forbidden") == "auth_forbidden"

    def test_env_var_missing(self):
        assert repo_facts._classify_error("Environment variable DB_HOST not set") == "env_var_missing"

    def test_operation_timeout(self):
        result = repo_facts._classify_error("Connection timeout 30s")
        assert result == "operation_timeout"

    def test_connection_refused(self):
        assert repo_facts._classify_error("connection refused") == "connection_refused"

    def test_generic_error(self):
        assert repo_facts._classify_error("general error in processing") == "generic_error"
        assert repo_facts._classify_error("failure during execution") == "generic_error"
        assert repo_facts._classify_error("an exception occurred") == "generic_error"

    def test_short_text_returns_none(self):
        assert repo_facts._classify_error("err") is None
        assert repo_facts._classify_error("") is None

    def test_non_string_returns_none(self):
        assert repo_facts._classify_error(123) is None
        assert repo_facts._classify_error(None) is None

    def test_priority_ordering(self):
        """Higher priority patterns should win over generic ones."""
        # "command not found" matches both command_not_found (priority 0) and generic_error (priority 9)
        result = repo_facts._classify_error("command not found: pytest")
        assert result == "command_not_found"


# ── get_injected_facts ────────────────────────────────────────────────

class TestGetInjectedFacts:
    """Test get_injected_facts() reads and deduplicates."""

    async def test_returns_empty_when_no_facts(self):
        """When no facts exist, should return empty list."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = []

        async def mock_execute(stmt):
            return mock_result
        mock_session.execute = mock_execute

        with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
            result = await repo_facts.get_injected_facts("chat-empty")

        assert result == []

    async def test_deduplicates_by_text(self):
        """Facts with same text from both tables should be deduplicated."""
        mock_session = MagicMock()

        # Create mock rows for microskills_facts (newer table, takes precedence)
        mf_row = MagicMock()
        mf_row.id = "mf-1"
        mf_row.fact_text = "Tool 'bash' failed because 'command_not_found'"
        mf_row.confirmation_count = 2
        mf_row.active = True

        # Same fact text in repo_facts (legacy)
        rf_row = MagicMock()
        rf_row.id = "rf-1"
        rf_row.fact_text = "Tool 'bash' failed because 'command_not_found'"
        rf_row.confirmation_count = 3
        rf_row.active = True

        def side_effect(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt)
            if "microskills_facts" in stmt_str:
                mock_res.scalars().all.return_value = [mf_row]
            else:
                mock_res.scalars().all.return_value = [rf_row]
            return mock_res

        async def mock_execute(stmt):
            return side_effect(stmt)
        mock_session.execute = mock_execute

        with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
            result = await repo_facts.get_injected_facts("chat-dedup")

        # Should only have 1 fact (deduplicated)
        assert len(result) == 1
        assert result[0]["text"] == "Tool 'bash' failed because 'command_not_found'"

    async def test_limits_to_max_facts(self):
        """Should return at most MAX_FACTS_PER_CHAT facts."""
        mock_session = MagicMock()

        # Create more than MAX_FACTS_PER_CHAT facts
        from cptr.utils.te.repo_facts import MAX_FACTS_PER_CHAT
        for i in range(MAX_FACTS_PER_CHAT + 3):
            row = MagicMock()
            row.id = f"fact-{i}"
            row.fact_text = f"Fact {i}"
            row.confirmation_count = 0
            row.active = True

        def side_effect(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt)
            if "microskills_facts" in stmt_str:
                mock_res.scalars().all.return_value = [row] * (MAX_FACTS_PER_CHAT + 3)
            else:
                mock_res.scalars().all.return_value = []
            return mock_res

        async def mock_execute(stmt):
            return side_effect(stmt)
        mock_session.execute = mock_execute

        with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
            result = await repo_facts.get_injected_facts("chat-limit")

        assert len(result) <= MAX_FACTS_PER_CHAT


# ── record_fact_fire ──────────────────────────────────────────────────

class TestRecordFactFire:
    """Test record_fact_fire() updates fire_status."""

    async def test_updates_fire_status(self):
        """Should increment fire_status and confirmation_count."""
        mock_session = MagicMock()

        # Mock existing fact row
        existing_row = MagicMock()
        existing_row.fire_status = 0
        existing_row.confirmation_count = 0
        existing_row.id = "fact-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_row

        async def mock_execute(stmt):
            return mock_result
        mock_session.execute = mock_execute

        with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
            await repo_facts.record_fact_fire("chat-fire", "fact-123")

        # Verify fire_status was incremented
        assert existing_row.fire_status == 1
        assert existing_row.confirmation_count == 1


# ── reset_error_tracker ───────────────────────────────────────────────

class TestResetErrorTracker:
    """Test reset_error_tracker() clears state."""

    def setup_method(self):
        repo_facts._error_tracker = repo_facts._ErrorTracker()

    def test_clears_all_tracked_errors(self):
        """Should remove all error counts for the chat."""
        # Record some errors first
        repo_facts.learn_facts_from_failures("chat-reset", "bash", "command not found: x")
        repo_facts.learn_facts_from_failures("chat-reset", "bash", "command not found: y")
        repo_facts.learn_facts_from_failures("chat-reset", "edit", "permission denied")

        # Verify counts exist
        counts = repo_facts._error_tracker.get_error_counts("chat-reset")
        assert len(counts) > 0

        # Reset
        repo_facts.reset_error_tracker("chat-reset")

        # Verify cleared
        counts_after = repo_facts._error_tracker.get_error_counts("chat-reset")
        assert len(counts_after) == 0

    def test_reset_nonexistent_chat_is_safe(self):
        """Resetting a chat with no errors should not raise."""
        repo_facts.reset_error_tracker("chat-nonexistent")
        # Should not raise any exception
        counts = repo_facts._error_tracker.get_error_counts("chat-nonexistent")
        assert len(counts) == 0

    def test_reset_isolate_other_chats(self):
        """Resetting one chat should not affect another."""
        repo_facts.learn_facts_from_failures("chat-a", "bash", "command not found: x")
        repo_facts.learn_facts_from_failures("chat-b", "edit", "permission denied")

        repo_facts.reset_error_tracker("chat-a")

        # chat-a should be cleared
        assert len(repo_facts._error_tracker.get_error_counts("chat-a")) == 0
        # chat-b should still have errors
        counts_b = repo_facts._error_tracker.get_error_counts("chat-b")
        assert len(counts_b) > 0

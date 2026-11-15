"""Unit tests for search_files improvements.

Tests cover:
1. Single file path support (path can be a file, not just directory)
2. Context lines (context_before, context_after parameters)
3. Output modes (mode: "content" | "files_with_matches" | "count")
4. Pagination (head_limit, offset)
5. Backward compatibility with existing parameters
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytest_plugins = ["pytest_asyncio"]


def run_async(coro):
    """Run an async coroutine in a fresh event loop."""
    return asyncio.run(coro)


# ── Mock subprocess for _search_rg tests ──────────────────────────────────


class MockSubprocessProc:
    """Mock subprocess process with proper async behavior."""

    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self.stdout = MockStreamReader(stdout)
        self.stderr = MockStreamReader(stderr)
        self.returncode = returncode
        self.pid = 12345

    async def communicate(self):
        return (self.stdout._buf, self.stderr._buf)

    async def wait(self):
        return self.returncode


class MockStreamReader:
    """Mock stream reader."""

    def __init__(self, data):
        self._buf = data

    def read(self, n=-1):
        return self._buf[:n] if n > 0 else self._buf


# ── Test: _search_rg Helper ───────────────────────────────────────────────


class TestSearchRgHelper:
    """Test the _search_rg helper function directly."""

    async def test_context_lines_add_c_flag(self):
        """_search_rg should add -C flag when context is set."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        captured_args = []

        async def mock_exec(*args, **kwargs):
            # *args receives each element separately due to *args unpacking in _search_rg
            captured_args.extend(args)
            return MockSubprocessProc(b"", b"", 1)

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/test"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=2,
                context_after=3,
                mode="content",
                head_limit=0,
                offset=0,
            )

        # Verify -C flag was added with max(2, 3) = 3
        assert "-C" in captured_args
        c_idx = captured_args.index("-C")
        assert captured_args[c_idx + 1] == "3"

    async def test_context_zero_no_c_flag(self):
        """No -C flag when context_before and context_after are both 0."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        captured_args = []

        async def mock_exec(*args, **kwargs):
            captured_args.extend(args)
            return MockSubprocessProc(b"", b"", 1)

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/test"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=0,
                offset=0,
            )

        assert "-C" not in captured_args

    async def test_mode_count_adds_count_flag(self):
        """mode='count' should add --count flag."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        captured_args = []

        async def mock_exec(*args, **kwargs):
            captured_args.extend(args)
            return MockSubprocessProc(b"", b"", 1)

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/test"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="count",
                head_limit=0,
                offset=0,
            )

        assert "--count" in captured_args

    async def test_mode_content_no_count_flag(self):
        """mode='content' should NOT add --count flag."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        captured_args = []

        async def mock_exec(*args, **kwargs):
            captured_args.extend(args)
            return MockSubprocessProc(b"", b"", 1)

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/test"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=0,
                offset=0,
            )

        assert "--count" not in captured_args

    async def test_is_file_skips_env_globs(self):
        """is_file=True should skip .env glob filters."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        captured_args = []

        async def mock_exec(*args, **kwargs):
            captured_args.extend(args)
            return MockSubprocessProc(b"", b"", 1)

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/test.py"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=True,  # Single file mode
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=0,
                offset=0,
            )

        assert "!.env" not in captured_args
        assert "!.env.*" not in captured_args

    async def test_is_file_false_includes_env_globs(self):
        """is_file=False should include .env glob filters."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        captured_args = []

        async def mock_exec(*args, **kwargs):
            captured_args.extend(args)
            return MockSubprocessProc(b"", b"", 1)

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/repo"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,  # Directory mode
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=0,
                offset=0,
            )

        assert "!.env" in captured_args
        assert "!.env.*" in captured_args


# ── Test: _search_rg Output Formatting ────────────────────────────────────


class TestSearchRgOutputFormatting:
    """Test _search_rg output formatting with simulated rg output."""

    async def test_count_mode_single_file(self):
        """mode='count' with is_file=True should return 'filename: count'."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        # Simulate rg --count output for a single file
        mock_proc = MockSubprocessProc(b"5\n", b"", 0)

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/test.py"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=True,
                context_before=0,
                context_after=0,
                mode="count",
                head_limit=0,
                offset=0,
            )

            assert result == "test.py: 5"

    async def test_count_mode_single_file_no_matches(self):
        """mode='count' with is_file=True and no matches should return 'No matches found.'."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        # No output for no matches (returncode 1)
        mock_proc = MockSubprocessProc(b"", b"", 1)

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="nonexistent_xyz",
                full=Path("/home/cptr/test.py"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=True,
                context_before=0,
                context_after=0,
                mode="count",
                head_limit=0,
                offset=0,
            )

            assert result == "No matches found."

    async def test_count_mode_directory(self):
        """mode='count' with is_file=False should return 'filepath: count' per file."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        # Simulate rg --count output for a directory with multiple files
        mock_proc = MockSubprocessProc(b"repo/file1.py: 3\nrepo/file2.py: 7\n", b"", 0)

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/repo"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="count",
                head_limit=0,
                offset=0,
            )

            assert "repo/file1.py" in result
            assert "repo/file2.py" in result

    async def test_head_limit_applied(self):
        """head_limit should limit the number of results."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        # Simulate 10 matches
        lines = "\n".join([f"repo/file.py:{i}: match{i}" for i in range(1, 11)])
        mock_proc = MockSubprocessProc(f"{lines}\n".encode(), b"", 0)

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/repo"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=5,
                offset=0,
            )

            # Should only have 5 lines (head_limit applied to ALL results)
            result_lines = result.strip().split("\n")
            assert len(result_lines) == 5

    async def test_offset_applied(self):
        """offset should skip the first N results."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        # Simulate 5 matches
        lines = "\n".join([f"repo/file.py:{i}: match{i}" for i in range(1, 6)])
        mock_proc = MockSubprocessProc(f"{lines}\n".encode(), b"", 0)

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/repo"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=0,
                offset=2,
            )

            # Should skip first 2, return last 3
            result_lines = result.strip().split("\n")
            assert len(result_lines) == 3
            assert "match3" in result
            assert "match1" not in result

    async def test_offset_with_large_result_set(self):
        """offset should work on ALL results, not just first 200."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        # Simulate 500 matches (well above old 200 limit)
        lines = "\n".join([f"repo/file.py:{i}: match{i}" for i in range(1, 501)])
        mock_proc = MockSubprocessProc(f"{lines}\n".encode(), b"", 0)

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="test",
                full=Path("/home/cptr/repo"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=10,
                offset=490,  # Skip first 490, get last 10
            )

            # Should return matches 491-500 (10 items)
            result_lines = result.strip().split("\n")
            assert len(result_lines) == 10
            assert "match491" in result
            assert "match500" in result
            assert "match1" not in result

    async def test_no_matches_returns_message(self):
        """Should return 'No matches found.' when rg returns exit code 1."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        mock_proc = MockSubprocessProc(b"", b"", 1)  # No matches

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="nonexistent_pattern_xyz",
                full=Path("/home/cptr/repo"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="content",
                head_limit=0,
                offset=0,
            )

            assert result == "No matches found."


# ── Test: Backward Compatibility ──────────────────────────────────────────


class TestBackwardCompatibility:
    """Test that existing calls without new parameters still work."""

    async def test_default_parameters(self):
        """All new parameters should have sensible defaults."""
        from cptr.utils.tools import _search_rg, search_files

        # Verify _search_rg signature has defaults
        import inspect
        sig = inspect.signature(_search_rg)
        assert sig.parameters["is_file"].default is False
        assert sig.parameters["context_before"].default == 0
        assert sig.parameters["context_after"].default == 0
        assert sig.parameters["mode"].default == "content"
        assert sig.parameters["head_limit"].default == 0
        assert sig.parameters["offset"].default == 0

        # Verify search_files signature has defaults
        sig2 = inspect.signature(search_files)
        assert sig2.parameters["context_before"].default == 0
        assert sig2.parameters["context_after"].default == 0
        assert sig2.parameters["mode"].default == "content"
        assert sig2.parameters["head_limit"].default == 200  # Safety default to prevent memory issues
        assert sig2.parameters["offset"].default == 0


# ── Test: No Matches ──────────────────────────────────────────────────────


class TestNoMatches:
    """Test behavior when no matches are found."""

    async def test_no_matches_count_mode(self):
        """mode='count' should return 'No matches found.' when no matches."""
        from cptr.utils.tools import _search_rg

        mock_identity = MagicMock()
        mock_identity.is_pam = False

        mock_proc = MockSubprocessProc(b"", b"", 1)  # No matches

        async def mock_exec(*args, **kwargs):
            return mock_proc

        with patch("asyncio.create_subprocess_exec", mock_exec):
            result = await _search_rg(
                query="nonexistent_xyz",
                full=Path("/home/cptr/repo"),
                is_regex=False,
                case_insensitive=False,
                include="",
                filenames_only=False,
                filepaths_only=False,
                identity=mock_identity,
                is_file=False,
                context_before=0,
                context_after=0,
                mode="count",
                head_limit=0,
                offset=0,
            )

            assert result == "No matches found."

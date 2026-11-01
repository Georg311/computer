"""Shared pytest fixtures for TE module tests.

pytest-asyncio configuration: all async tests use asyncio mode 'auto'
so they can be plain async def functions.
"""
import asyncio

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# DB session mocking helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_te_cache(monkeypatch):
    """Clear the in-memory token records cache between tests."""
    from cptr.utils.te import cost_tracker
    cost_tracker._last_token_records.clear()


# ---------------------------------------------------------------------------
# Async test runner (pytest-asyncio compatible, but we use asyncio.run manually)
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run an async coroutine in a fresh event loop."""
    return asyncio.run(coro)


@pytest.fixture
def mock_session():
    """Create a MagicMock that behaves like an async DB session."""
    sess = MagicMock()
    sess.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    sess.get = AsyncMock(return_value=None)
    sess.add = MagicMock()
    sess.commit = AsyncMock()
    return sess


@pytest.fixture
def mock_get_session(mock_session):
    """Patch cptr.utils.db.get_session_factory to return our mock session."""
    with patch("cptr.utils.db.get_session_factory", return_value=lambda: mock_session):
        yield mock_session


# ---------------------------------------------------------------------------
# SpiralState / Envelope helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def spiral_state():
    """Fresh SpiralState for loop_guard tests."""
    from cptr.utils.te.loopguard.state import SpiralState
    st = SpiralState()
    return st


@pytest.fixture
def envelope():
    """Fresh Envelope for loop_guard tests."""
    from cptr.utils.te.loop_guard import Envelope
    env = Envelope(max_size=50)
    return env

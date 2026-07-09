"""Per-chat browser session manager.

Maintains one CDPClient per chat so the AI can do multi-step browser flows
(navigate -> snapshot -> click -> type -> snapshot) without losing state.
Sessions auto-close after an idle timeout.
"""

from __future__ import annotations

import asyncio
import logging
import time

from cptr.utils.browser.cdp import CDPClient

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES = 10


class BrowserSessionManager:
    """One browser session per chat, with idle timeout cleanup."""

    def __init__(self) -> None:
        self._sessions: dict[str, CDPClient] = {}
        self._last_used: dict[str, float] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._timeout_minutes = DEFAULT_TIMEOUT_MINUTES

    def set_timeout(self, minutes: int) -> None:
        self._timeout_minutes = max(1, minutes)

    async def get_or_create(self, chat_id: str, cdp_url: str) -> CDPClient:
        """Get an existing session for this chat, or create a new one."""
        if chat_id in self._sessions:
            client = self._sessions[chat_id]
            if not client.is_closed():
                self._last_used[chat_id] = time.monotonic()
                return client
            # Session was closed externally, remove it
            del self._sessions[chat_id]
            self._last_used.pop(chat_id, None)

        # Create new session
        client = await CDPClient.connect(cdp_url)
        self._sessions[chat_id] = client
        self._last_used[chat_id] = time.monotonic()

        # Start cleanup loop if not running
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Browser session created for chat %s", chat_id[:8])
        return client

    async def close(self, chat_id: str) -> None:
        """Close and remove a specific chat's session."""
        client = self._sessions.pop(chat_id, None)
        self._last_used.pop(chat_id, None)
        if client:
            await client.close()
            logger.info("Browser session closed for chat %s", chat_id[:8])

    async def close_all(self) -> None:
        """Close all sessions. Called on app shutdown."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        for chat_id in list(self._sessions):
            await self.close(chat_id)

    async def _cleanup_loop(self) -> None:
        """Periodically close idle sessions."""
        while self._sessions:
            await asyncio.sleep(60)  # Check every minute
            now = time.monotonic()
            timeout_seconds = self._timeout_minutes * 60
            expired = [
                cid
                for cid, last in self._last_used.items()
                if now - last > timeout_seconds
            ]
            for chat_id in expired:
                logger.info("Browser session timed out for chat %s", chat_id[:8])
                await self.close(chat_id)


# Singleton instance
session_manager = BrowserSessionManager()

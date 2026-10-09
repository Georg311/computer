"""Workspace Watch: detect external file changes in a workspace.

Watches active workspace roots for filesystem changes made by processes
outside of cptr (builds, other agents, git pulls on another device) and
reports them as debounced batches:

  - Badge: per-workspace change counts served with the workspace list and
    pushed to connected clients via socket.
  - Agent injection: a short note appended to the system prompt of the next
    agent turn in that workspace (no hard interrupt, no auto-rerun).

Platform support:
  - Linux/macOS/Windows: Uses watchdog for cross-platform stability.

Self-write suppression: cptr's own file writes (file tools, file browser)
are registered via ``mark_self_write``; events for those paths within a short
window are not reported as external changes. Shell commands run in the
workspace are *not* suppressed — their writes are treated as external by
design (safer than hiding real concurrent changes).

Standard library + watchdog.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)

# Directories that never count as workspace changes.
EXCLUDED_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__"})
# Max individual paths kept per workspace batch (overflow becomes "+N weitere").
MAX_EVENT_PATHS = 100
# Debounce window for batching events into one summary.
DEBOUNCE_SECONDS = 1.0
# Self-written paths are suppressed for this many seconds.
SELF_WRITE_SUPPRESS_SECONDS = 5.0


@dataclass
class PendingChanges:
    """Aggregated external changes for one workspace since last flush."""

    paths: list[str] = field(default_factory=list)
    overflow: int = 0
    updated_at: float = 0.0

    @property
    def count(self) -> int:
        return len(self.paths) + self.overflow

    def add(self, rel_path: str) -> None:
        if rel_path in self.paths:
            return
        if len(self.paths) < MAX_EVENT_PATHS:
            self.paths.append(rel_path)
        else:
            self.overflow += 1


def _rel_workspace_path(workspace: str, path: str) -> str | None:
    """Return the workspace-relative path for an absolute path, or None."""
    try:
        # Ensure both are resolved to avoid mismatching paths like /tmp/foo vs /tmp/foo/
        ws_path = Path(workspace).resolve()
        target_path = Path(path).resolve()
        return str(target_path.relative_to(ws_path))
    except ValueError:
        return None


def _is_excluded_rel_path(rel_path: str) -> bool:
    parts = rel_path.split("/")
    return any(part in EXCLUDED_DIRS for part in parts)


# ── Self-write suppression registry (global, keyed by abs path) ─

_self_write_lock = threading.Lock()
# abs path → expiry timestamp
_self_writes: dict[str, float] = {}


def mark_self_write(path: str) -> None:
    """Record a cptr-initiated write so the watcher ignores its events."""
    try:
        abs_path = str(Path(path).resolve())
    except (OSError, RuntimeError):
        return
    with _self_write_lock:
        writes = {p: exp for p, exp in _self_writes.items() if exp > time.time()}
        writes[abs_path] = time.time() + SELF_WRITE_SUPPRESS_SECONDS
        _self_writes.clear()
        _self_writes.update(writes)


def _is_self_write(abs_path: str) -> bool:
    with _self_write_lock:
        return _self_writes.get(abs_path, 0.0) > time.time()


# ── Per-workspace pending state (badge counts + injection note) ─

_registry_lock = threading.RLock()
_pending: dict[str, PendingChanges] = {}


def get_pending(workspace: str) -> PendingChanges | None:
    """Non-destructive snapshot of the pending changes for a workspace."""
    resolved = str(Path(workspace).resolve())
    with _registry_lock:
        pending = _pending.get(resolved)
        if pending is None:
            return None
        return PendingChanges(
            paths=list(pending.paths), overflow=pending.overflow, updated_at=pending.updated_at
        )


def pop_pending_note(workspace: str) -> str | None:
    """Pop the aggregated note for a workspace (consumed by one agent turn)."""
    resolved = str(Path(workspace).resolve())
    with _registry_lock:
        pending = _pending.pop(resolved, None)
    if not pending or pending.count == 0:
        return None
    shown = pending.paths[:20]
    extra = pending.count - len(shown)
    listing = ", ".join(f"`{p}`" for p in shown)
    more = f", … +{extra} weitere Änderungen" if extra > 0 else ""
    return (
        "[Workspace Watch] Since your last turn, files in this workspace were "
        f"changed by an external process: {listing}{more}. Consider re-reading "
        "affected files before relying on their previous contents."
    )


# ── Watchdog implementation ──────────────────────────────────────

class WorkspaceWatchEventHandler(FileSystemEventHandler):
    """Event handler that pushes changes to the manager."""

    def __init__(self, workspace: str, manager: 'WorkspaceWatchManager'):
        self.workspace = str(Path(workspace).resolve())
        self.manager = manager

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        abs_path = str(Path(event.src_path).resolve())
        logger.debug("[workspace-watch] watchdog event: %s on %s", type(event).__name__, abs_path)

        if _is_self_write(abs_path):
            logger.debug("[workspace-watch] suppressed (self-write): %s", abs_path)
            return

        rel = _rel_workspace_path(self.workspace, abs_path)
        if rel is None:
            logger.debug("[workspace-watch] ignored (not in workspace): %s vs %s", abs_path, self.workspace)
            return

        if _is_excluded_rel_path(rel):
            logger.debug("[workspace-watch] ignored (excluded): %s", rel)
            return

        logger.info("[workspace-watch] accepted: %s (%s)", rel, type(event).__name__)
        self.manager._add_event_to_pending(self.workspace, rel)


class WorkspaceWatchManager:
    """One watcher per workspace, debounced batch flush to an emit callback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._observers: dict[str, Observer] = {}
        self._task: asyncio.Task | None = None
        self._emit_callback = None

    def set_emit_callback(self, callback) -> None:
        """Set the async callback invoked with (workspace, PendingChanges)"""
        self._emit_callback = callback

    def _add_event_to_pending(self, workspace: str, rel_path: str) -> None:
        """Thread-safe addition of a change to the registry."""
        resolved_ws = str(Path(workspace).resolve())
        with _registry_lock:
            pending = _pending.setdefault(resolved_ws, PendingChanges())
            pending.add(rel_path)
            pending.updated_at = time.time()
            logger.debug("[workspace-watch] Registry Update | Key: %s | Added: %s | Total Count: %d", 
                         resolved_ws, rel_path, pending.count)

    def start_watch(self, workspace: str) -> bool:
        """Start watching a workspace root using watchdog."""
        resolved = str(Path(workspace).resolve())
        with self._lock:
            if resolved in self._observers:
                return True
            if not Path(resolved).is_dir():
                logger.info("[workspace-watch] skipping non-existent workspace %s", resolved)
                return False

            try:
                observer = Observer()
                handler = WorkspaceWatchEventHandler(resolved, self)
                observer.schedule(handler, resolved, recursive=True)
                observer.start()
                self._observers[resolved] = observer
                logger.info("[workspace-watch] watching workspace %s", resolved)
                return True
            except Exception as exc:
                logger.warning("[workspace-watch] failed to start for %s: %s", resolved, exc)
                return False

    def stop_watch(self, workspace: str) -> None:
        """Stop an individual workspace watch."""
        resolved = str(Path(workspace).resolve())
        with self._lock:
            observer = self._observers.pop(resolved, None)
            if observer:
                observer.stop()
                observer.join()
            with _registry_lock:
                _pending.pop(resolved, None)

    def watched_workspaces(self) -> list[str]:
        """Return currently active watched workspaces."""
        with self._lock:
            return list(self._observers.keys())

    async def run_loop(self) -> None:
        """Poll all watchers; flush debounced batches to the emit callback."""
        last_emitted_at: dict[str, float] = {}

        while True:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            try:
                active_workspaces = self.watched_workspaces()
                for workspace in active_workspaces:
                    snapshot = None
                    with _registry_lock:
                        pending = _pending.get(workspace)
                        if pending and pending.count > 0:
                            # We take a snapshot of the data to release the lock quickly.
                            snapshot = PendingChanges(
                                paths=list(pending.paths),
                                overflow=pending.overflow,
                                updated_at=pending.updated_at
                            )

                    if snapshot:
                        now = time.time()
                        last_emit = last_emitted_at.get(workspace, 0)

                        # Only emit if we haven't emitted too recently (debounce)
                        if (now - last_emit) >= DEBOUNCE_SECONDS:
                            logger.debug("[workspace-watch] Attempting to emit for %s", workspace)
                            if self._emit_callback:
                                try:
                                    await self._emit_callback(workspace, snapshot)
                                    last_emitted_at[workspace] = now
                                    logger.info("[workspace-watch] Callback successful for %s", workspace)
                                except Exception as exc:
                                    logger.exception("[workspace-watch] emit callback failed: %s", exc)
                            else:
                                logger.warning("[workspace-watch] No callback set for %s", workspace)
                    else:
                        # Optional: log that no changes were found for an active workspace to debug idle loops
                        # logger.debug("[workspace-watch] No pending changes for %s", workspace)
                        pass

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("[workspace-watch] loop error: %s", exc)

    def start(self) -> None:
        """Start the background poll loop (call from the app lifespan)."""
        if self._task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self.run_loop())
        except RuntimeError:
            return

    async def stop_all(self) -> None:
        """Stop all watchers and the manager task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        with self._lock:
            for workspace, observer in self._observers.items():
                observer.stop()
                observer.join()
            self._observers.clear()

        with _registry_lock:
            _pending.clear()

    async def stop_all_workspace_watches(self) -> None:
        """Public async stop all."""
        await self.stop_all()


manager = WorkspaceWatchManager()


async def start_workspace_watch(workspace: str) -> bool:
    """Start watching a workspace (idempotent). Returns True if active."""
    return manager.start_watch(workspace)


def stop_workspace_watch(workspace: str) -> None:
    """Stop watching a workspace."""
    manager.stop_watch(workspace)


async def stop_all_workspace_watches() -> None:
    """Stop all active workspace watches."""
    await manager.stop_all()

"""Workspace Watch: detect external file changes in a workspace.

Watches active workspace roots for filesystem changes made by processes
outside of cptr (builds, other agents, git pulls on another device) and
reports them as debounced batches:

  - Badge: per-workspace change counts served with the workspace list and
    pushed to connected clients via socket.
  - Agent injection: a short note appended to the system prompt of the next
    agent turn in that workspace (no hard interrupt, no auto-rerun).

Platform support:
  - Linux: inotify via ctypes/struct on top of os.inotify_* (stdlib only),
    recursive watch per top-level directory with excluded subtrees skipped.
  - macOS: fsevents is not implemented in v1 — start_watch raises a clear error.
  - Windows: Phase 2.

Self-write suppression: cptr's own file writes (file tools, file browser)
are registered via ``mark_self_write``; events for those paths within a short
window are not reported as external changes. Shell commands run in the
workspace are *not* suppressed — their writes are treated as external by
design (safer than hiding real concurrent changes).

Standard library only.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import select
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Directories that never count as workspace changes.
EXCLUDED_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__"})

# Max individual paths kept per workspace batch (overflow becomes "+N weitere").
MAX_EVENT_PATHS = 100
# Debounce window for batching events into one summary.
DEBOUNCE_SECONDS = 1.0
# Self-written paths are suppressed for this many seconds.
SELF_WRITE_SUPPRESS_SECONDS = 5.0

_LINUX_IN_CREATE = 0x00000010
_LINUX_IN_MODIFY = 0x00000008
_LINUX_IN_MOVED_FROM = 0x00000040
_LINUX_IN_MOVED_TO = 0x00000080
_LINUX_IN_DELETE = 0x00000200


class WorkspaceWatchUnsupportedError(RuntimeError):
    """Raised when the platform does not support workspace watching."""


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
        if rel_path not in self.paths and len(self.paths) < MAX_EVENT_PATHS:
            self.paths.append(rel_path)
        else:
            self.overflow += 1


def _rel_workspace_path(workspace: str, path: str) -> str | None:
    """Return the workspace-relative path for an absolute path, or None."""
    try:
        return str(Path(path).resolve().relative_to(Path(workspace)))
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

_registry_lock = threading.Lock()
_pending: dict[str, PendingChanges] = {}


def get_pending(workspace: str) -> PendingChanges | None:
    """Non-destructive snapshot of the pending changes for a workspace."""
    with _registry_lock:
        pending = _pending.get(str(Path(workspace).resolve()))
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


# ── Linux inotify backend ──────────────────────────────────────

_INOTIFY_HEADER = struct.Struct("<iIII")  # wd, mask, cookie, len; then raw name bytes


class _Inotify:
    """Minimal recursive inotify wrapper built on os.inotify_* + select."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.fd = os.inotify_init()
        self.watches: dict[int, str] = {}  # wd → dir path (absolute)
        self._add_dir(workspace)

    def _add_dir(self, path: Path) -> None:
        try:
            wd = os.inotify_add_watch(
                self.fd, str(path), _LINUX_IN_CREATE | _LINUX_IN_MODIFY | _LINUX_IN_DELETE
            )
            self.watches[wd] = str(path)
        except OSError:
            pass

    def scan_top_level(self) -> None:
        try:
            entries = sorted(self.workspace.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink() or not entry.is_dir():
                continue
            if entry.name in EXCLUDED_DIRS:
                continue
            self._add_dir(entry)

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass

    def read_events(self, timeout: float = 0.25) -> list[tuple[int, str]]:
        """Return (wd, filename) pairs; blocks up to timeout seconds."""
        events: list[tuple[int, str]] = []
        try:
            ready = select.select([self.fd], [], [], timeout)
            if not ready[0]:
                return events
            data = os.read(self.fd, 65536)
        except OSError:
            return events
        offset = 0
        while offset + _INOTIFY_HEADER.size <= len(data):
            wd, _mask, _cookie, name_len = _INOTIFY_HEADER.unpack_from(data, offset)
            if not name_len:
                offset += _INOTIFY_HEADER.size
                continue
            name = data[offset + _INOTIFY_HEADER.size : offset + _INOTIFY_HEADER.size + name_len]
            try:
                events.append((wd, name.decode("utf-8", "replace")))
            except Exception:
                pass
            offset += _INOTIFY_HEADER.size + name_len
        return events


class _LinuxWatcher:
    def __init__(self, workspace: str):
        self.workspace = Path(workspace).resolve()
        self.inotify = _Inotify(self.workspace)
        self.inotify.scan_top_level()

    def poll(self, timeout: float = 0.25) -> list[str]:
        """Return workspace-relative paths that changed since last poll."""
        changed: set[str] = set()
        for wd, name in self.inotify.read_events(timeout):
            dir_path = self.inotify.watches.get(wd)
            if not dir_path:
                continue
            abs_path = str(Path(dir_path) / name)
            rel = _rel_workspace_path(str(self.workspace), abs_path)
            if rel is None or _is_excluded_rel_path(rel):
                continue
            if _is_self_write(abs_path):
                continue
            changed.add(rel)
        return sorted(changed)

    def close(self) -> None:
        self.inotify.close()


# ── macOS stub (Phase 2: fsevents) ─────────────────────────────


class _UnsupportedWatcher:
    def __init__(self, workspace: str):
        raise WorkspaceWatchUnsupportedError(
            "Workspace Watch is not supported on this platform. "
            "v1 supports Linux (inotify); macOS fsevents support is planned for a later phase."
        )


# ── Per-workspace watcher + manager ────────────────────────────

class _WorkspaceWatcher:
    def __init__(self, workspace: str):
        self.workspace = str(Path(workspace).resolve())
        self.watcher = None

    def start(self) -> None:
        if platform.system() == "Linux":
            self.watcher = _LinuxWatcher(self.workspace)
        else:
            self.watcher = _UnsupportedWatcher(self.workspace)

    def stop(self) -> None:
        if self.watcher is not None:
            try:
                self.watcher.close()
            except Exception:
                pass
            self.watcher = None

    def poll_once(self) -> list[str]:
        return self.watcher.poll() if self.watcher else []


class WorkspaceWatchManager:
    """One watcher per workspace, debounced batch flush to an emit callback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._watchers: dict[str, _WorkspaceWatcher] = {}
        self._task: asyncio.Task | None = None
        self._emit_callback = None  # async (workspace, PendingChanges) → None

    def set_emit_callback(self, callback) -> None:
        """Set the async callback invoked with (workspace, PendingChanges)."""
        self._emit_callback = callback

    def start_watch(self, workspace: str) -> bool:
        """Start watching a workspace root. Returns True if active."""
        resolved = str(Path(workspace).resolve())
        with self._lock:
            if resolved in self._watchers:
                return True
            if not Path(resolved).is_dir():
                logger.info("[workspace-watch] skipping non-existent workspace %s", resolved)
                return False
            try:
                watcher = _WorkspaceWatcher(resolved)
                watcher.start()
            except WorkspaceWatchUnsupportedError as exc:
                logger.info("[workspace-watch] %s", exc)
                return False
            except OSError as exc:
                logger.warning("[workspace-watch] failed to start for %s: %s", resolved, exc)
                return False
            self._watchers[resolved] = watcher
        logger.info("[workspace-watch] watching workspace %s", resolved)
        return True

    def stop_watch(self, workspace: str) -> None:
        resolved = str(Path(workspace).resolve())
        with self._lock:
            watcher = self._watchers.pop(resolved, None)
        if watcher is not None:
            watcher.stop()
            with _registry_lock:
                _pending.pop(resolved, None)

    def watched_workspaces(self) -> list[str]:
        with self._lock:
            return list(self._watchers.keys())

    async def run_loop(self) -> None:
        """Poll all watchers; flush debounced batches to the emit callback."""
        while True:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            try:
                for workspace in self.watched_workspaces():
                    watcher = self._watchers.get(workspace)
                    if not watcher:
                        continue
                    changed = await asyncio.to_thread(watcher.poll_once)
                    if not changed:
                        continue
                    with _registry_lock:
                        pending = _pending.setdefault(workspace, PendingChanges())
                        for rel in changed:
                            pending.add(rel)
                        pending.updated_at = time.time()
                    snapshot = get_pending(workspace)
                    if self._emit_callback is not None and snapshot:
                        try:
                            await self._emit_callback(workspace, snapshot)
                        except Exception:
                            logger.exception("[workspace-watch] emit callback failed")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[workspace-watch] loop error")

    def start(self) -> None:
        """Start the background poll loop (call from the app lifespan)."""
        if self._task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._task = loop.create_task(self.run_loop())

    async def stop_all(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task
            self._task = None
        for workspace in list(self.watched_workspaces()):
            self.stop_watch(workspace)


manager = WorkspaceWatchManager()


async def start_workspace_watch(workspace: str) -> bool:
    """Start watching a workspace (idempotent). Returns True if active."""
    return manager.start_watch(workspace)


def stop_workspace_watch(workspace: str) -> None:
    manager.stop_watch(workspace)


async def stop_all_workspace_watches() -> None:
    await manager.stop_all()

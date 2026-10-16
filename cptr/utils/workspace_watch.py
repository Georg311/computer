"""Directory Watcher: detect external file changes in arbitrary directories.

Supports two modes:
  - Notification Mode (Passive): Notifies the agent of changes via a system message note.
  - Trigger Mode (Active): Triggers a new agent turn when a file matching a specified pattern is modified/created.

Safeguards against infinite loops via cooldown/downgrade mechanism and self-write suppression.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import re
import select
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Configuration
MAX_EVENT_PATHS = 100
DEBOUNCE_SECONDS = 1.0
SELF_WRITE_SUPPRESS_SECONDS = 5.0
TRIGGER_COOLDOWN_SECONDS = 300.0  # 5 minutes

# Linux inotify constants
_LINUX_IN_CREATE = 0x00000010
_LINUX_IN_MODIFY = 0x00000008
_LINUX_IN_DELETE = 0x00000200
_LINUX_IN_MOVED_FROM = 0x00000040
_LINUX_IN_MOVED_TO = 0x00000080
_INOTIFY_HEADER = struct.Struct("<iIII")  # wd, mask, cookie, len


@dataclass
class WatchEvent:
    """An event representing a file change."""
    abs_path: str
    rel_path: str


@dataclass
class PendingChanges:
    """Aggregated changes for a directory."""
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


# ── Self-write suppression ─────────────────────────────────────

_self_write_lock = threading.Lock()
_self_writes: dict[str, float] = {}


def mark_self_write(path: str) -> None:
    """Record a cptr-initiated write so the watcher ignores its events."""
    try:
        abs_path = str(Path(path).resolve())
    except (OSError, RuntimeError):
        return
    with _self_write_lock:
        now = time.time()
        # Clean up expired writes
        expired = [p for p, exp in _self_writes.items() if exp <= now]
        for p in expired:
            del _self_writes[p]
        _self_writes[abs_path] = now + SELF_WRITE_SUPPRESS_SECONDS


def _is_self_write(abs_path: str) -> bool:
    with _self_write_lock:
        return _self_writes.get(abs_path, 0.0) > time.time()


# ── Linux inotify backend ─────────────────────────────────────

class WatcherError(RuntimeError):
    """Raised when the platform does not support watching."""


# ── inotify_ctypes: fallback when os.inotify_* is unavailable ──

_inotify_ctypes = None
_global_inotify_fd = None
_global_inotify_lock = threading.Lock()
_global_watches: dict[int, str] = {}  # wd → dir path (absolute), shared by all instances


def _init_inotify_ctypes() -> None:
    """Initialize ctypes-based inotify if os.inotify_* is unavailable."""
    global _inotify_ctypes
    if hasattr(os, "inotify_init") and hasattr(os, "inotify_add_watch"):
        return  # native functions available
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        inotify_init = libc.inotify_init
        inotify_init.restype = ctypes.c_int
        inotify_add_watch = libc.inotify_add_watch
        inotify_add_watch.restype = ctypes.c_int
        inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        inotify_rm_watch = libc.inotify_rm_watch
        inotify_rm_watch.restype = ctypes.c_int
        inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
        _inotify_ctypes = {
            "init": inotify_init,
            "add_watch": inotify_add_watch,
            "rm_watch": inotify_rm_watch,
        }
    except Exception as e:
        logger.warning("[directory-watch] ctypes inotify fallback failed: %s", e)


def _get_global_inotify_fd() -> int:
    """Get or create the global inotify fd (singleton)."""
    global _global_inotify_fd
    if hasattr(os, "inotify_init"):
        return os.inotify_init()
    if _global_inotify_fd is not None:
        return _global_inotify_fd
    if _inotify_ctypes is None:
        _init_inotify_ctypes()
    if _inotify_ctypes and _inotify_ctypes["init"]:
        with _global_inotify_lock:
            if _global_inotify_fd is None:
                fd = _inotify_ctypes["init"]()
                if fd == -1:
                    import ctypes
                    errno = ctypes.get_errno()
                    raise OSError(errno, os.strerror(errno))
                _global_inotify_fd = fd
        return _global_inotify_fd
    return -1


def _inotify_add_watch(fd: int, path: str, mask: int) -> int:
    """Call inotify_add_watch, using ctypes fallback if needed."""
    if hasattr(os, "inotify_add_watch"):
        return os.inotify_add_watch(fd, path, mask)
    if _inotify_ctypes and _inotify_ctypes["add_watch"]:
        import ctypes
        return _inotify_ctypes["add_watch"](fd, ctypes.c_char_p(path.encode("utf-8")), mask)
    return -1


def _inotify_rm_watch(fd: int, wd: int) -> int:
    """Call inotify_rm_watch, using ctypes fallback if needed."""
    if hasattr(os, "inotify_rm_watch"):
        return os.inotify_rm_watch(fd, wd)
    if _inotify_ctypes and _inotify_ctypes["rm_watch"]:
        return _inotify_ctypes["rm_watch"](fd, wd)
    return -1


class _LinuxInotify:
    """Minimal recursive inotify wrapper.
    
    IMPORTANT: When using ctypes fallback, all instances share ONE global inotify fd
    and ONE global watches dict. This means poll() will return events from ALL
    watched directories, not just this instance's root.
    """

    def __init__(self, root: Path):
        self.root = root
        self.fd = _get_global_inotify_fd()
        self.watches: dict[int, str] = _global_watches  # Share global watches dict
        self._add_dir(root)

    def _add_dir(self, path: Path) -> None:
        try:
            wd = _inotify_add_watch(
                self.fd, str(path), 
                _LINUX_IN_CREATE | _LINUX_IN_MODIFY | _LINUX_IN_DELETE | 
                _LINUX_IN_MOVED_FROM | _LINUX_IN_MOVED_TO
            )
            _global_watches[wd] = str(path)
        except OSError:
            pass

    def scan_recursive(self) -> None:
        """Recursively add all directories to inotify watches."""
        try:
            for entry in self.root.rglob("*"):
                if entry.is_dir() and not entry.name.startswith("."):
                    self._add_dir(entry)
        except Exception:
            pass

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass

    def poll(self, timeout: float) -> list[WatchEvent]:
        """Return WatchEvent instances.
        
        NOTE: When using global inotify, this will consume ALL events from the fd,
        not just events for this instance's root. Events for other roots are also
        returned (the caller must filter by self.root).
        """
        events: list[WatchEvent] = []
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
            if name_len == 0:
                offset += _INOTIFY_HEADER.size
                continue
            name_raw = data[offset + _INOTIFY_HEADER.size : offset + _INOTIFY_HEADER.size + name_len]
            name = name_raw.decode("utf-8", "replace").strip("\x00")
            dir_path = _global_watches.get(wd)
            if dir_path:
                abs_path = os.path.join(dir_path, name)
                # Only return events for this instance's root
                if abs_path.startswith(str(self.root)):
                    rel_path = os.path.relpath(abs_path, self.root)
                    events.append(WatchEvent(abs_path=abs_path, rel_path=rel_path))
            offset += _INOTIFY_HEADER.size + name_len
        return events


# ── Per-directory watcher ───────────────────────────────────────

class _DirectoryWatcher:
    def __init__(self, abs_path: str, trigger_pattern: str | None = None):
        self.abs_path = abs_path
        self.root = Path(abs_path)
        self.trigger_pattern = re.compile(trigger_pattern) if trigger_pattern else None
        self.backend = None
        
        if platform.system() == "Linux":
            self.backend = _LinuxInotify(self.root)
            self.backend.scan_recursive()
        else:
            raise WatcherError(f"Platform {platform.system()} is not supported.")

    def poll(self) -> list[WatchEvent]:
        if not self.backend:
            return []
        
        events = []
        for event in self.backend.poll(0.1):
            events.append(event)
        return events

    def close(self) -> None:
        if self.backend:
            self.backend.close()


# ── Directory Watch Manager ───────────────────────────────────

class DirectoryWatchManager:
    """Manages multiple directory watchers and orchestrates events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._watchers: dict[str, _DirectoryWatcher] = {}  # abs_path -> watcher
        self._watcher_meta: dict[str, dict[str, str]] = {}  # abs_path -> meta (chat_id, user_id, workspace)
        self._task: asyncio.Task | None = None
        self._emit_callback: Callable[[str, PendingChanges, bool], Coroutine] = None
        
        # Cooldown tracking: (abs_path, pattern_str) -> last_trigger_timestamp
        self._last_triggers: dict[tuple[str, str | None], float] = {}
        
        # Pending state: abs_path -> PendingChanges
        self._pending: dict[str, PendingChanges] = {}

    def set_emit_callback(self, callback: Callable[[str, PendingChanges, bool, dict], Coroutine]) -> None:
        self._emit_callback = callback

    def watch(self, path: str, chat_id: str, user_id: str, workspace: str, trigger_on: str | None = None) -> str:
        """Start watching a directory. Returns status message."""
        abs_path = str(Path(path).resolve())
        with self._lock:
            if abs_path in self._watchers:
                return f"Already watching {abs_path}"

            try:
                watcher = _DirectoryWatcher(abs_path, trigger_on)
                self._watchers[abs_path] = watcher
                self._watcher_meta[abs_path] = {
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "workspace": workspace
                }
                return f"Started watching {abs_path} (Trigger on: {trigger_on or 'None'})"
            except Exception as e:
                return f"Failed to watch {abs_path}: {e}"

    def stop(self, path: str) -> None:
        abs_path = str(Path(path).resolve())
        with self._lock:
            watcher = self._watchers.pop(abs_path, None)
            if watcher:
                watcher.close()
            self._watcher_meta.pop(abs_path, None)
            self._pending.pop(abs_path, None)

    def get_pending(self, path: str) -> PendingChanges | None:
        abs_path = str(Path(path).resolve())
        with self._lock:
            return self._pending.get(abs_path)

    async def run_loop(self) -> None:
        """Main background loop."""
        while True:
            try:
                await asyncio.sleep(DEBOUNCE_SECONDS)
                await self._poll_and_flush()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[directory-watch] loop error")

    async def _poll_and_flush(self) -> None:
        now = time.time()
        
        # 1. Central poll: read events from global inotify fd once
        #    This avoids the race where watcher1.poll() consumes all events
        #    before watcher2.poll() can read anything.
        all_events: list[tuple[str, WatchEvent]] = [] # (abs_path, event)
        
        # Check if we're using the global inotify (ctypes fallback)
        using_global_inotify = not hasattr(os, "inotify_init") or _global_inotify_fd is not None
        
        if using_global_inotify and _global_inotify_fd is not None:
            # Central poll: read ALL events from global fd once
            global_events: list[WatchEvent] = []
            try:
                ready = select.select([_global_inotify_fd], [], [], DEBOUNCE_SECONDS)
                if ready[0]:
                    data = os.read(_global_inotify_fd, 65536)
                    offset = 0
                    while offset + _INOTIFY_HEADER.size <= len(data):
                        wd, _mask, _cookie, name_len = _INOTIFY_HEADER.unpack_from(data, offset)
                        if name_len == 0:
                            offset += _INOTIFY_HEADER.size
                            continue
                        name_raw = data[offset + _INOTIFY_HEADER.size : offset + _INOTIFY_HEADER.size + name_len]
                        name = name_raw.decode("utf-8", "replace").strip("\x00")
                        dir_path = _global_watches.get(wd)
                        if dir_path:
                            abs_path = os.path.join(dir_path, name)
                            global_events.append(WatchEvent(abs_path=abs_path, rel_path=name))
                        offset += _INOTIFY_HEADER.size + name_len
            except OSError:
                pass
            
            # Distribute events to each watcher based on its root
            with self._lock:
                for abs_path, watcher in self._watchers.items():
                    for event in global_events:
                        # Only include events for this watcher's root
                        if event.abs_path.startswith(str(watcher.root)):
                            all_events.append((abs_path, event))
        else:
            # Native inotify: each watcher has its own fd
            with self._lock:
                for abs_path, watcher in self._watchers.items():
                    for event in watcher.poll():
                        all_events.append((abs_path, event))

        if not all_events:
            return

        # 2. Process events and update pending changes / trigger
        for abs_path, event in all_events:
            # Skip if self-write
            if _is_self_write(event.abs_path):
                continue

            # Update pending changes
            with self._lock:
                pending = self._pending.setdefault(abs_path, PendingChanges())
                pending.add(event.rel_path)
                pending.updated_at = now

            # Check if it's a trigger
            watcher = self._watchers.get(abs_path)
            if not watcher or not watcher.trigger_pattern:
                continue
            
            if watcher.trigger_pattern.search(event.rel_path):
                # Check cooldown
                pattern_str = watcher.trigger_pattern.pattern
                trigger_key = (abs_path, pattern_str)
                last_trigger = self._last_triggers.get(trigger_key, 0.0)
                
                if now - last_trigger < TRIGGER_COOLDOWN_SECONDS:
                    # Within cooldown -> passive notification (already updated pending)
                    continue
                else:
                    # Outside cooldown -> TRIGGER
                    self._last_triggers[trigger_key] = now
                    # Triggering an active turn
                    with self._lock:
                        snapshot = PendingChanges(
                            paths=list(pending.paths),
                            overflow=pending.overflow,
                            updated_at=pending.updated_at
                        )
                    
                    meta = self._watcher_meta.get(abs_path)
                    if meta:
                        asyncio.create_task(self._trigger_active_turn(
                            abs_path, pattern_str, snapshot, meta
                        ))

    async def _trigger_active_turn(self, abs_path: str, pattern_str: str, snapshot: PendingChanges, meta: dict) -> None:
        """Injects a trigger message into the chat queue."""
        if not self._emit_callback:
            return
        try:
            # We pass the context required by inject_queued_message
            await self._emit_callback(
                abs_path, 
                snapshot, 
                True, 
                {
                    "chat_id": meta["chat_id"],
                    "user_id": meta["user_id"],
                    "workspace": meta["workspace"]
                }
            )
        except Exception:
            logger.exception("[directory-watch] trigger emit failed")

    async def stop_all(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task
            self._task = None
        
        with self._lock:
            for watcher in self._watchers.values():
                watcher.close()
            self._watchers.clear()
            self._watcher_meta.clear()
            self._pending.clear()


manager = DirectoryWatchManager()


async def start_directory_watch(path: str, chat_id: str, user_id: str, workspace: str, trigger_on: str | None = None) -> bool:
    """Start watching a directory (idempotent)."""
    result = manager.watch(path, chat_id, user_id, workspace, trigger_on)
    return result.startswith("Started")

def stop_directory_watch(path: str) -> None:
    manager.stop(path)

async def stop_all_directory_watches() -> None:
    await manager.stop_all()

def get_pending_changes(path: str) -> PendingChanges | None:
    return manager.get_pending(path)

"""Cross-platform PTY terminal session manager.

Uses stdlib pty/os.fork on Unix (zero dependencies).
Uses pywinpty on Windows (optional dependency, installed only on Windows).
"""

from __future__ import annotations

import os
import platform
import shlex
import struct
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

SCROLLBACK_SIZE = 64 * 1024  # 64 KB
IS_WINDOWS = platform.system() == "Windows"


@dataclass
class TerminalSession:
    """Platform-agnostic terminal session with scrollback buffer."""

    session_id: str
    cwd: str
    rows: int = 24
    cols: int = 80
    _scrollback: bytearray = field(default_factory=bytearray, repr=False)

    # Platform handles
    _fd: int = -1  # Unix: master pty fd
    _pid: int = -1  # Unix: child pid
    _process: object = None  # Windows: winpty PtyProcess

    def write(self, data: bytes) -> None:
        if IS_WINDOWS:
            data = data.decode("utf-8", errors="replace")
            self._process.write(data)  # type: ignore
        else:
            os.write(self._fd, data)

    def read(self, size: int = 4096) -> bytes:
        try:
            if IS_WINDOWS:
                data = self._process.read(size)  # type: ignore
                if isinstance(data, str):
                    data = data.encode("utf-8", errors="replace")
            else:
                data = os.read(self._fd, size)
        except (BlockingIOError, OSError):
            return b""
        if data:
            self._scrollback.extend(data)
            # Trim at 2x cap to amortize the cost. This halves the number of
            # 64 KB memcpy operations during high-throughput output.
            if len(self._scrollback) > SCROLLBACK_SIZE * 2:
                self._scrollback = self._scrollback[-SCROLLBACK_SIZE:]
        return data

    def get_scrollback(self) -> bytes:
        return bytes(self._scrollback)

    def resize(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        if IS_WINDOWS:
            try:
                self._process.set_size(cols, rows)  # type: ignore
            except Exception:
                pass
        else:
            import fcntl
            import termios

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._fd, termios.TIOCSWINSZ, winsize)

    def is_alive(self) -> bool:
        if IS_WINDOWS:
            return self._process.isalive()  # type: ignore
        try:
            pid, _ = os.waitpid(self._pid, os.WNOHANG)
            return pid == 0
        except ChildProcessError:
            return False

    def close(self) -> None:
        if IS_WINDOWS:
            try:
                self._process.close()  # type: ignore
            except Exception:
                pass
        else:
            import signal

            try:
                os.kill(self._pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                os.close(self._fd)
            except OSError:
                pass


def _create_unix(
    session_id: str, shell: str, work_dir: str, env: dict, rows: int, cols: int
) -> TerminalSession:
    """Create a terminal session on Unix using stdlib pty."""
    import fcntl
    import pty
    import tempfile
    import termios

    master_fd, slave_fd = pty.openpty()

    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    shell_name = os.path.basename(shell)
    shell_args = [shell]
    home = os.path.expanduser("~")

    # Create a temp init script that sources the user's real config then cd's.
    # This guarantees cwd is set AFTER all init files run. No timing hacks.
    if shell_name in ("zsh",):
        # For zsh: use ZDOTDIR to inject our .zshrc
        zdotdir = tempfile.mkdtemp(prefix="cptr_zsh_")
        init_content = (
            f'ZDOTDIR="{home}"\n'
            f'[[ -f "{home}/.zshenv" ]] && source "{home}/.zshenv"\n'
            f'[[ -f "{home}/.zprofile" ]] && source "{home}/.zprofile"\n'
            f'[[ -f "{home}/.zshrc" ]] && source "{home}/.zshrc"\n'
            f"cd {shlex.quote(work_dir)}\n"
        )
        with open(os.path.join(zdotdir, ".zshrc"), "w") as f:
            f.write(init_content)
        # Also create .zshenv to prevent system zshenv from interfering
        with open(os.path.join(zdotdir, ".zshenv"), "w") as f:
            f.write("")
        env["ZDOTDIR"] = zdotdir
        shell_args = [shell, "-i"]
    elif shell_name in ("bash",):
        # For bash: use --rcfile
        tmpf = tempfile.NamedTemporaryFile(
            mode="w", prefix="cptr_bash_", suffix=".sh", delete=False
        )
        tmpf.write(
            f'[[ -f "{home}/.bashrc" ]] && source "{home}/.bashrc"\ncd {shlex.quote(work_dir)}\n'
        )
        tmpf.close()
        shell_args = [shell, "--rcfile", tmpf.name, "-i"]
    else:
        # Generic POSIX: use ENV variable
        tmpf = tempfile.NamedTemporaryFile(mode="w", prefix="cptr_sh_", suffix=".sh", delete=False)
        tmpf.write(f'[ -f "$HOME/.profile" ] && . "$HOME/.profile"\ncd {shlex.quote(work_dir)}\n')
        tmpf.close()
        env["ENV"] = tmpf.name
        shell_args = [shell, "-i"]

    child_pid = os.fork()
    if child_pid == 0:
        # Child process
        os.close(master_fd)
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)

        os.chdir(work_dir)
        os.execvpe(shell, shell_args, env)
    else:
        # Parent process
        os.close(slave_fd)
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        return TerminalSession(
            session_id=session_id,
            cwd=work_dir,
            rows=rows,
            cols=cols,
            _fd=master_fd,
            _pid=child_pid,
        )


def _create_windows(
    session_id: str, shell: str, work_dir: str, env: dict, rows: int, cols: int
) -> TerminalSession:
    """Create a terminal session on Windows using pywinpty."""
    from winpty import PtyProcess  # type: ignore

    proc = PtyProcess.spawn(
        [shell],
        cwd=work_dir,
        env=env,
        dimensions=(rows, cols),
    )

    return TerminalSession(
        session_id=session_id,
        cwd=work_dir,
        rows=rows,
        cols=cols,
        _process=proc,
    )


class SessionManager:
    """Registry of active terminal sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, TerminalSession] = {}

    def create(self, rows: int = 24, cols: int = 80, cwd: Optional[str] = None) -> TerminalSession:
        session_id = uuid.uuid4().hex[:12]
        work_dir = cwd or os.path.expanduser("~")

        if IS_WINDOWS:
            shell = os.environ.get("COMSPEC", "cmd.exe")
        else:
            shell = os.environ.get("SHELL", "/bin/sh")

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["COLUMNS"] = str(cols)
        env["LINES"] = str(rows)
        env["PWD"] = work_dir

        if IS_WINDOWS:
            session = _create_windows(session_id, shell, work_dir, env, rows, cols)
        else:
            session = _create_unix(session_id, shell, work_dir, env, rows, cols)

        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[TerminalSession]:
        session = self._sessions.get(session_id)
        if session and not session.is_alive():
            session.close()
            del self._sessions[session_id]
            return None
        return session

    def list_sessions(self) -> List[dict]:
        result = []
        dead = []
        for sid, session in self._sessions.items():
            if session.is_alive():
                result.append({"session_id": sid, "cwd": session.cwd})
            else:
                dead.append(sid)
        for sid in dead:
            self._sessions[sid].close()
            del self._sessions[sid]
        return result

    def close(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            session.close()
            return True
        return False

    def close_all(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()


manager = SessionManager()

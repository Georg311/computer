"""Workspace filesystem helpers."""

from __future__ import annotations

from pathlib import Path

from cptr import env
from cptr.utils.config import load_config


def auto_gitignore_cptr_enabled() -> bool:
    if env.WORKSPACE_AUTO_GITIGNORE_DOT_CPTR_ENV is not None:
        return env.WORKSPACE_AUTO_GITIGNORE_DOT_CPTR

    config = load_config()
    value = None
    workspace = config.get("workspace", {})
    if isinstance(workspace, dict):
        value = workspace.get("auto_gitignore_dot_cptr")
    app_config = config.get("app_config", {})
    if isinstance(app_config, dict):
        value = app_config.get("workspace.auto_gitignore_dot_cptr", value)
    return _bool_config(value, default=True)


def ensure_cptr_gitignored(workspace: str | Path) -> None:
    """If workspace is a git repo, ensure .cptr is listed in .gitignore."""
    if not auto_gitignore_cptr_enabled():
        return

    ws = Path(workspace)
    if not (ws / ".git").exists():
        return

    gitignore = ws / ".gitignore"
    entry = ".cptr"

    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == entry or stripped == entry + "/":
                return
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"{entry}\n"
        gitignore.write_text(content, encoding="utf-8")
    else:
        gitignore.write_text(f"{entry}\n", encoding="utf-8")


def _bool_config(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default

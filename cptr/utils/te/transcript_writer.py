"""TranscriptWriter – JSONL transcript dumper for cptr SSE execution.

Writes Claude-compatible JSONL entries during chat_task execution so the
Distiller can build digests and run proposer ticks.

Each tool call + output pair becomes two adjacent JSON lines:
  {"type":"assistant","message":{"content":[{"type":"tool_use",...}]}}
  {"type":"user","message":{"content":[{"type":"tool_result",...}]}}
"""

import json
import logging
import os
from pathlib import Path as _Path
from typing import Any

logger = logging.getLogger(__name__)


class TranscriptWriter:
    """Append-only JSONL transcript writer for Distiller digest construction.

    Usage::

        tw = TranscriptWriter(chat_id, workspace="/home/user/repo")
        # During tool execution:
        tw.record_tool_use(call_id="tc_01", name="bash", input={"command": "ls"})
        tw.record_tool_result(call_id="tc_01", output="file1\\nfile2")
        # On task completion:
        transcript_path = tw.finish(resolved=True)  → "/home/user/.cptr/transcripts/..."

    The produced JSONL file is compatible with distiller.load_calls().
    """

    def __init__(self, chat_id: str, workspace: str = "") -> None:
        self.chat_id = chat_id
        self.workspace = workspace or ""
        self._call_index: dict[str, int] = {}  # call_id → index in entries
        self._entries: list[dict] = []  # raw JSONL lines as dicts

    # ── Recording phase ───────────────────────────────────────────────

    def record_tool_use(
        self,
        call_id: str,
        name: str,
        input: dict[str, Any],
    ) -> None:
        """Record a tool_use block (assistant side)."""
        entry = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": name,
                        "input": input,
                    }
                ]
            },
        }
        self._entries.append(entry)
        self._call_index[call_id] = len(self._entries) - 1

    def record_tool_result(
        self,
        call_id: str,
        output: Any,
    ) -> None:
        """Record a tool_result block (user side)."""
        txt = output if isinstance(output, str) else json.dumps(output or "")
        entry = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": txt,
                    }
                ]
            },
        }
        self._entries.append(entry)

    def record_user_message(self, text: str) -> None:
        """Record a user message (optional — for context)."""
        entry = {
            "type": "user",
            "message": {"content": [{"type": "text", "text": text}]},
        }
        self._entries.append(entry)

    # ── Finish phase ─────────────────────────────────────────────────

    def finish(self, resolved: bool = True) -> str | None:
        """Write JSONL transcript to disk and return the file path.

        Returns ``None`` if writing fails (graceful degradation).
        """
        try:
            # Ensure transcript directory exists
            cptr_dir = _Path.home() / ".cptr"
            transcripts_dir = cptr_dir / "transcripts"
            transcripts_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{self.chat_id}.jsonl"
            filepath = str(transcripts_dir / filename)

            with open(filepath, "w", encoding="utf-8") as fh:
                for entry in self._entries:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

            logger.debug(
                "[transcript] wrote %d entries to %s (resolved=%s)",
                len(self._entries),
                filepath,
                resolved,
            )
            return filepath

        except OSError as e:
            logger.warning("[transcript] write failed: %s", str(e))
            return None

    def reset(self) -> None:
        """Clear all recorded entries for the next task."""
        self._entries.clear()
        self._call_index.clear()


# ── Digest builder helper ────────────────────────────────────────────

def build_cptr_digest(
    workspace: str,
    transcript_path: str | None,
    chat_id: str,
) -> dict | None:
    """Build a Distiller-compatible digest from a cptr transcript.

    Delegates to distiller.build_digest() which parses the JSONL and
    extracts commands, edited files, test invocations, etc.

    Returns ``None`` if no valid digest can be constructed.
    """
    if not workspace or not transcript_path:
        return None

    from .microskills.distiller import build_digest as _build_digest

    try:
        return _build_digest(workspace, transcript_path, chat_id)
    except Exception as e:
        logger.debug("[digest] build failed for %s: %s", transcript_path, str(e))
        return None


# ── Window manager ───────────────────────────────────────────────────

class DigestWindow:
    """Rolling window of digests per chat — max 8 (WINDOW constant).

    The proposer reads this window to generate new facts.
    """

    def __init__(self, max_size: int = 8) -> None:
        self.max_size = max_size
        self._digests: list[dict] = []

    def add(self, digest: dict | None) -> None:
        """Append a single task digest; evict oldest if over capacity."""
        if digest is not None:
            self._digests.append(digest)
            while len(self._digests) > self.max_size:
                self._digests.pop(0)

    def get_all(self) -> list[dict]:
        """Return all digests currently in the window."""
        return list(self._digests)

    def size(self) -> int:
        return len(self._digests)

    def clear(self) -> None:
        self._digests.clear()


# ── LLM Runner for proposer ticks ───────────────────────────────────

def _build_openai_runner(api_key: str, base_url: str = "https://api.openai.com/v1") -> Any:
    """Build an OpenAI-compatible runner callable for the Distiller proposer.

    Returns a ``(prompt, model) → (raw_response, effective_tokens)`` pair.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    def runner(prompt: str, model: str) -> tuple[str, float | None]:
        try:
            resp = client.chat.completions.create(
                model=model or "gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            text = resp.choices[0].message.content or ""
            tokens = float(resp.usage.total_tokens) if resp.usage else 0.0
            return text, tokens
        except Exception as e:
            logger.warning("[llm_runner] OpenAI call failed: %s", str(e))
            return "", 0.0

    return runner


def _build_anthropic_runner(api_key: str) -> Any:
    """Build an Anthropic-compatible runner callable for the Distiller proposer."""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    def runner(prompt: str, model: str) -> tuple[str, float | None]:
        try:
            resp = client.messages.create(
                model=model or "claude-3-opus-20240229",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.3,
            )
            text = resp.content[0].text if resp.content else ""
            tokens = float(resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0.0
            return text, tokens
        except Exception as e:
            logger.warning("[llm_runner] Anthropic call failed: %s", str(e))
            return "", 0.0

    return runner


def build_proposer_runner() -> Any | None:
    """Try to construct a paid LLM runner from environment config.

    Falls back to ``None`` if no API keys are available.
    """
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("[llm_runner] No OPENAI/ANTHROPIC_API_KEY found — proposer disabled")
        return None

    provider = "openai" if os.environ.get("OPENAI_API_KEY") else "anthropic"
    base_url = os.environ.get(f"{provider.upper()}_BASE_URL", "")

    try:
        if provider == "openai":
            return _build_openai_runner(api_key, base_url or "https://api.openai.com/v1")
        else:
            return _build_anthropic_runner(api_key)
    except ImportError as e:
        logger.warning("[llm_runner] %s client not installed: %s", provider, str(e))
        return None

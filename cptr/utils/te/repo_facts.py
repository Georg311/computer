"""Micro-skills: rule-based fact learning and injection for cptr.

Rule-based Fact Learning (envfacts profile):

- Tracks tool-call errors per chat session.
- When the same error pattern repeats ≥3 times in one chat, a Fact is emitted.
- Facts are stored in the `repo_facts` table (via RepoFacts model).
- `get_injected_facts(chat_id)` returns formatted facts for system-prompt injection.

Injection profiles (from InjectionConfig.profile):
  * "envfacts"          — rule-based only, no paid LLM calls.
  * "distiller"         — LLM-proposed facts (not implemented here).
  * "envfacts+distiller" — both layers combined.

Integration points:
  - Called from chat_task.py after each tool execution (error → learn_facts_from_failures).
  - Called from chat_task.py before building the system prompt (get_injected_facts).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

MAX_FACTS_PER_CHAT = 5
MAX_FACT_TOKENS = 200  # ~4 chars per token

# Minimum repeat count for a fact to be emitted (default: 3)
DEFAULT_REPEAT_THRESHOLD = 3

# Fact format template
FACT_TEMPLATE = "Tool '{tool_name}' fehlgeschlagen wegen '{error_pattern}'"


# ── Error pattern registry ──────────────────────────────────────────

# Maps error substrings / regex patterns to a human-readable error_pattern label.
# Higher priority (larger index) wins when multiple patterns match.
_ERROR_PATTERNS: list[tuple[str | re.Pattern[str], str]] = [
    # High-severity: command / binary missing
    (re.compile(r"command not found(?::\s*\S+)?$", re.IGNORECASE), "command_not_found"),
    (re.compile(r"(?:[Cc]annot|can['\s]t)\s+find\s+module", re.IGNORECASE), "module_not_found"),
    (re.compile(r"[Ii]nternalError.*command not found", re.IGNORECASE), "internal_command_missing"),

    # Medium-severity: path / file issues
    (re.compile(r"[Nn]o such file or directory", re.IGNORECASE), "path_not_found"),
    (re.compile(r"[Pp]ath does not exist", re.IGNORECASE), "path_not_found"),
    (re.compile(r"[Ee][Nn][Oo][Ee][Nt]", re.IGNORECASE), "file_unavailable"),

    # Medium-severity: permission / auth
    (re.compile(r"[Pp]ermission denied", re.IGNORECASE), "permission_denied"),
    (re.compile(r"unauthorized|401", re.IGNORECASE), "auth_failure"),
    (re.compile(r"forbidden|403", re.IGNORECASE), "auth_forbidden"),

    # Low-severity: environment / config
    (re.compile(r"[Ee]nvironment variable.*not set", re.IGNORECASE), "env_var_missing"),
    (re.compile(r"[Tt]imeout[^\w]*(\d+)", re.IGNORECASE), "operation_timeout"),
    (re.compile(r"connection refused", re.IGNORECASE), "connection_refused"),

    # Generic fallback
    (re.compile(r"\b(error|failure|exception)\b", re.IGNORECASE), "generic_error"),
]


def _classify_error(error_text: str) -> Optional[str]:
    """Classify an error message into a normalized error_pattern label.

    Returns the best-matching pattern label, or None if nothing matches.
    """
    if not isinstance(error_text, str) or len(error_text) < 5:
        return None

    best_match: Optional[str] = None
    best_priority = -1

    for pattern, label in _ERROR_PATTERNS:
        if isinstance(pattern, str):
            matched = pattern.lower() in error_text.lower()
        else:
            matched = bool(pattern.search(error_text))

        if matched:
            # We assign priority by index order (later entries = higher priority)
            idx = _ERROR_PATTERNS.index((pattern, label))
            if idx > best_priority:
                best_priority = idx
                best_match = label

    return best_match


# ── Error tracker per chat ──────────────────────────────────────────

class _ErrorTracker:
    """Tracks repeated tool errors per chat and emits facts when threshold is reached.

    In-memory cache only — persistence happens via RepoFacts.save().
    """

    def __init__(self) -> None:
        # chat_id -> { error_pattern -> { tool_name -> count } }
        self._counts: dict[str, dict[str, dict[str, int]]] = {}
        # chat_id -> { error_pattern -> { tool_name -> first_seen_ms } }
        self._first_seen: dict[str, dict[str, dict[str, int]]] = {}

    def record_error(
        self,
        chat_id: str,
        tool_name: str,
        error_text: str,
        threshold: int = DEFAULT_REPEAT_THRESHOLD,
    ) -> Optional[str]:
        """Record a tool-call error and return a Fact text if threshold is reached.

        Args:
            chat_id: The session to track errors for.
            tool_name: Name of the failed tool (e.g. "bash", "file_edit").
            error_text: Raw error message from the tool output.
            threshold: Number of repeats before emitting a Fact (default 3).

        Returns:
            The formatted Fact string, or None if threshold not yet reached.
        """
        error_pattern = _classify_error(error_text)
        if error_pattern is None:
            return None

        # Ensure nested dicts exist
        chat_errors = self._counts.setdefault(chat_id, {})
        tool_counts = chat_errors.setdefault(error_pattern, {})

        count = tool_counts.get(tool_name, 0) + 1
        tool_counts[tool_name] = count

        if count == 1:
            self._first_seen.setdefault(chat_id, {}).setdefault(
                error_pattern, {}
            )[tool_name] = _now_ms()

        # Emit fact when threshold is reached (only once per unique combo)
        if count >= threshold and tool_counts.get(f"__emitted_{error_pattern}_{tool_name}") != 1:
            tool_counts[f"__emitted_{error_pattern}_{tool_name}"] = 1

            # Build the fact text
            fact_text = FACT_TEMPLATE.format(
                tool_name=tool_name,
                error_pattern=error_pattern,
            )
            logger.info(
                "[te] Fact emitted: %s (threshold=%d, pattern=%s)",
                fact_text,
                threshold,
                error_pattern,
            )
            return fact_text

        if count > 1 and count < threshold:
            logger.debug(
                "[te] Error repeat %d/%d for '%s'/%s",
                count,
                threshold,
                chat_id,
                error_pattern,
            )

        return None

    def get_error_counts(self, chat_id: str) -> dict[str, dict[str, int]]:
        """Return the current error counts for a chat (for debugging)."""
        return {
            ep: {k: v for k, v in tc.items() if not k.startswith("__")}
            for ep, tc in self._counts.get(chat_id, {}).items()
        }

    def reset_chat(self, chat_id: str) -> None:
        """Clear all tracked errors for a chat (e.g. at session start)."""
        self._counts.pop(chat_id, None)
        self._first_seen.pop(chat_id, None)


# ── Global instance ─────────────────────────────────────────────────

_error_tracker = _ErrorTracker()


# ── Public API ──────────────────────────────────────────────────────


def learn_facts_from_failures(
    chat_id: str,
    tool_name: str,
    error_text: str,
    threshold: int = DEFAULT_REPEAT_THRESHOLD,
) -> Optional[str]:
    """Recognize facts from repeated errors in a chat session.

    When the same error pattern repeats ≥threshold times for the same tool
    in the same chat, a Fact is emitted as a string and stored in memory.
    The Fact must later be persisted via RepoFacts.save().

    Args:
        chat_id: The chat session identifier.
        tool_name: Name of the failed tool (e.g. "bash").
        error_text: Raw error message from the tool output.
        threshold: Repeat count before emitting (default 3).

    Returns:
        The formatted Fact string, or None if threshold not yet reached.
    """
    return _error_tracker.record_error(chat_id, tool_name, error_text, threshold)


def get_injected_facts(chat_id: str) -> list[dict]:
    """Return active facts for a chat, formatted for system-prompt injection.

    Reads from both repo_facts (legacy) and microskills_facts tables,
    deduplicates by fact_text, and returns up to MAX_FACTS_PER_CHAT facts
    sorted by severity (high first).
    Each fact dict has keys: 'text', 'category', 'severity'.
    """
    from cptr.models import MicroskillsFact, RepoFacts

    async def _fetch():
        session = __import__("cptr.utils.db", fromlist=["get_session_factory"]).get_session_factory()()
        sa_select = __import__("sqlalchemy", fromlist=["select"]).select

        # Read from both tables
        stmt_rf = sa_select(RepoFacts).where(
            RepoFacts.chat_id == chat_id,
            RepoFacts.active is True,
        ).order_by(RepoFacts.confirmation_count.desc())
        result_rf = await session.execute(stmt_rf)
        rows_rf = list(result_rf.scalars().all())

        stmt_mf = sa_select(MicroskillsFact).where(
            MicroskillsFact.chat_id == chat_id,
            MicroskillsFact.active is True,
        ).order_by(MicroskillsFact.confirmation_count.desc())
        result_mf = await session.execute(stmt_mf)
        rows_mf = list(result_mf.scalars().all())

        # Deduplicate by fact_text (microskills_facts takes precedence)
        seen_texts = set()
        facts = []

        # First add from microskills_facts (newer table)
        for r in rows_mf:
            if r.fact_text not in seen_texts:
                severity = "high" if (r.confirmation_count or 0) >= 2 else "medium"
                facts.append({
                    "id": str(r.id),
                    "text": r.fact_text,
                    "category": "envfacts",
                    "severity": severity,
                    "fire_count": 1 if r.fire_status else 0,
                })
                seen_texts.add(r.fact_text)

        # Then add from repo_facts (legacy table) for any not already seen
        for r in rows_rf:
            if r.fact_text not in seen_texts:
                severity = "high" if (r.confirmation_count or 0) >= 2 else "medium"
                facts.append({
                    "id": str(r.id),
                    "text": r.fact_text,
                    "category": "envfacts",
                    "severity": severity,
                    "fire_count": r.fire_status or 0,
                })
                seen_texts.add(r.fact_text)

        return facts[:MAX_FACTS_PER_CHAT]

    # Run synchronously via asyncio
    try:
        import asyncio

        try:
            asyncio.get_running_loop()
            future = asyncio.ensure_future(_fetch())
            return asyncio.wait_for(future, timeout=2.0)
        except RuntimeError:
            pass

        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(_fetch())
    except Exception as exc:
        logger.warning("[te] get_injected_facts failed for %s: %s", chat_id, exc, exc_info=True)
        return []


async def record_fact_fire(chat_id: str, fact_id: str) -> None:
    """Record that a fact was successfully used (fired) in a chat."""
    from cptr.models import RepoFacts

    session = __import__("cptr.utils.db", fromlist=["get_session_factory"]).get_session_factory()()
    stmt = (
        __import__("sqlalchemy", fromlist=["select"])
        .select(RepoFacts)
        .where(RepoFacts.id == fact_id)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row:
        row.fire_status = (row.fire_status or 0) + 1
        row.confirmation_count = (row.confirmation_count or 0) + 1
        await session.commit()


def persist_facts_from_tracker(chat_id: str, repo_hash: str = None) -> None:
    """Persist all newly learned facts from the in-memory tracker to DB.

    Writes to both `repo_facts` (legacy) and `microskills_facts` tables.
    Facts are upserted — existing rows get their repo_hash updated if new one provided.
    """
    from cptr.models import MicroskillsFact, RepoFacts

    async def _save():
        session = __import__("cptr.utils.db", fromlist=["get_session_factory"]).get_session_factory()()
        sa_select = __import__("sqlalchemy", fromlist=["select"]).select

        # Get all learned facts from the in-memory tracker
        facts_data = _error_tracker._counts.get(chat_id, {})
        seen_facts = set()

        for error_pattern, tool_counts in facts_data.items():
            for tool_name, count in tool_counts.items():
                if tool_name.startswith("__"):
                    continue
                # Only persist facts that were emitted (threshold reached)
                emitted_key = f"__emitted_{error_pattern}_{tool_name}"
                if tool_counts.get(emitted_key) != 1:
                    continue

                fact_text = FACT_TEMPLATE.format(tool_name=tool_name, error_pattern=error_pattern)

                # Skip if already processed in this call
                if fact_text in seen_facts:
                    continue
                seen_facts.add(fact_text)

                # Check and upsert in repo_facts (legacy table)
                existing_rf = await session.execute(
                    sa_select(RepoFacts).where(
                        (RepoFacts.chat_id == chat_id) & (RepoFacts.fact_text == fact_text),
                    )
                )
                rf_row = existing_rf.scalar_one_or_none()

                if rf_row is None:
                    session.add(RepoFacts(
                        chat_id=chat_id,
                        repo_hash=repo_hash,
                        fact_text=fact_text,
                        fire_status=0,
                        confirmation_count=0,
                        active=True,
                    ))
                else:
                    rf_row.repo_hash = repo_hash or rf_row.repo_hash
                    rf_row.active = True

                # Check and upsert in microskills_facts (new table)
                existing_mf = await session.execute(
                    sa_select(MicroskillsFact).where(
                        (MicroskillsFact.chat_id == chat_id) &
                        (MicroskillsFact.fact_text == fact_text),
                    )
                )
                mf_row = existing_mf.scalar_one_or_none()

                if mf_row is None:
                    session.add(MicroskillsFact(
                        chat_id=chat_id,
                        repo_hash=repo_hash,
                        fact_text=fact_text,
                        fire_status=False,
                        confirmation_count=0,
                        active=True,
                    ))
                else:
                    mf_row.repo_hash = repo_hash or mf_row.repo_hash
                    mf_row.active = True

        await session.commit()

    try:
        import asyncio

        try:
            asyncio.get_running_loop()
            asyncio.ensure_future(_save())
        except RuntimeError:
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(_save())
    except Exception as exc:
        logger.warning("[te] persist_facts_from_tracker failed for %s: %s", chat_id, exc, exc_info=True)


def reset_error_tracker(chat_id: str) -> None:
    """Reset the in-memory error tracker for a chat (call at session start)."""
    _error_tracker.reset_chat(chat_id)


# ── Helpers ─────────────────────────────────────────────────────────

def _now_ms() -> int:
    import time
    return int(time.time() * 1000)

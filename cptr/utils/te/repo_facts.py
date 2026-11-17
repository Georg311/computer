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

# ── Lifecycle constants ──────────────────────────────────────────────
K_PROMOTE = 3        # confirmations to promote CANDIDATE → ACTIVE (different files required)
GAMMA = 0.8          # recency decay per task-ago
LAMBDA_VAL = 5.0     # contradiction weight (asymmetry: fail toward retirement)
SCORE_FLOOR = 0.0    # retire ACTIVE when recency score < floor
HARD_KILL = True     # high-stakes fact: single clean contradiction retires now
FIRE_GATE = 0.40     # inject only if firing rate >= 40%
FIRE_MIN_N = 4       # measured over at least this many exercised tasks


# ── Fact lifecycle states ───────────────────────────────────────────

class _FactState:
    """Represents a single fact with full lifecycle scoring.

    States: CANDIDATE → ACTIVE (after K_PROMOTE confirmations on different files)
            → RETIRED (when score < SCORE_FLOOR or HARD_KILL contradiction)
    """

    def __init__(self, chat_id: str, error_pattern: str, tool_name: str, fact_text: str) -> None:
        self.chat_id = chat_id
        self.error_pattern = error_pattern
        self.tool_name = tool_name
        self.fact_text = fact_text
        self.state = "CANDIDATE"  # CANDIDATE | ACTIVE | RETIRED

        # Counters
        self.confirmations: int = 0          # total confirmations
        self.contradictions: int = 0         # total contradictions
        self.fires: int = 0                  # times fact was successfully used
        self.exercises: int = 0              # total tasks that could have fired this fact

        # Track files where confirmations happened (drift-aware promotion)
        self.confirmation_files: set[str] = set()

        # First seen timestamp for recency scoring
        self.first_seen_ms: int = _now_ms()

    @property
    def firing_rate(self) -> float:
        """Return the fact's firing rate (fires / exercises)."""
        if self.exercises == 0:
            return 0.0
        return self.fires / self.exercises

    @property
    def recency_score(self) -> float:
        """Calculate recency score with exponential decay."""
        elapsed = _now_ms() - self.first_seen_ms
        # Convert ms to "task-ago" units (rough estimate: 1 task ≈ 500ms)
        task_ago = max(0, elapsed / 500.0)
        return GAMMA ** task_ago

    def score(self, now: int = None) -> float:
        """Calculate the current lifecycle score."""
        if self.state == "RETIRED":
            return 0.0
        # Base score from confirmations minus contradiction penalty
        base = min(self.confirmations, K_PROMOTE)
        penalty = self.contradictions * LAMBDA_VAL
        recency = self.recency_score
        score = (base - penalty) * recency
        return max(0.0, score)

    def injectable(self) -> bool:
        """Check if this fact should be injected into the prompt."""
        if self.state not in ("CANDIDATE", "ACTIVE"):
            return False
        # FIRE_GATE check: only inject if firing rate >= threshold and enough data
        if self.exercises < FIRE_MIN_N:
            return self.firing_rate >= FIRE_GATE or self.confirmations > 0
        return self.firing_rate >= FIRE_GATE

    def update(
        self,
        chat_id: str,
        tool_name: str,
        error_pattern: str,
        fact_text: str,
        files: list[str] = None,
    ) -> Optional[str]:
        """Update fact state based on new evidence.

        Returns the updated fact text if a lifecycle transition occurred, else None.
        """
        self.chat_id = chat_id
        self.tool_name = tool_name
        self.error_pattern = error_pattern
        self.fact_text = fact_text

    def confirm(self, file: str = None) -> bool:
        """Record a confirmation (fact was useful)."""
        self.confirmations += 1
        if file:
            self.confirmation_files.add(file)
        # Check promotion CANDIDATE → ACTIVE
        if (self.state == "CANDIDATE" and
                self.confirmations >= K_PROMOTE and
                len(self.confirmation_files) >= 2):
            self.state = "ACTIVE"
            return True
        return False

    def contradict(self) -> bool:
        """Record a contradiction (fact was wrong)."""
        self.contradictions += 1
        # HARD_KILL: single clean contradiction retires immediately
        if HARD_KILL and self.contradictions >= 1:
            self.state = "RETIRED"
            return True
        # Graceful retirement: score drops below floor
        if self.score() < SCORE_FLOOR:
            self.state = "RETIRED"
            return True
        return False

    def fire(self) -> None:
        """Record that this fact was successfully used."""
        self.fires += 1

    def exercise(self) -> None:
        """Record that a task occurred (potential to use this fact)."""
        self.exercises += 1


def _get_fact_key(chat_id: str, error_pattern: str) -> str:
    """Generate unique key for a fact."""
    return f"{chat_id}:{error_pattern}"


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
        # chat_id -> { key -> _FactState }
        self._fact_states: dict[str, dict[str, "_FactState"]] = {}

    def _get_fact_state(self, chat_id: str, error_pattern: str, tool_name: str) -> "_FactState":
        """Get or create a FactState for the given chat/error/tool combination."""
        key = f"{error_pattern}:{tool_name}"
        by_key = self._fact_states.setdefault(chat_id, {})
        if key not in by_key:
            fact_text = FACT_TEMPLATE.format(tool_name=tool_name, error_pattern=error_pattern)
            by_key[key] = _FactState(chat_id, error_pattern, tool_name, fact_text)
        return by_key[key]

    def confirm_fact(self, chat_id: str, error_pattern: str, file: str = None) -> bool:
        """Confirm a fact (it was useful). Returns True if promoted CANDIDATE→ACTIVE."""
        any_promoted = False
        for key, state in self._fact_states.get(chat_id, {}).items():
            if state.error_pattern == error_pattern:
                promoted = state.confirm(file=file or "unknown")
                if promoted:
                    logger.info("[te] Fact PROMOTED to ACTIVE: %s", state.fact_text)
                    any_promoted = True
        return any_promoted

    def contradict_fact(self, chat_id: str, error_pattern: str) -> bool:
        """Contradict a fact (it was wrong). Returns True if retired."""
        # Gather all matching states for this error pattern across tools
        any_retired = False
        for key, state in self._fact_states.get(chat_id, {}).items():
            if state.error_pattern == error_pattern:
                retired = state.contradict()
                if retired:
                    logger.info("[te] Fact RETIRED: %s", state.fact_text)
                    any_retired = True
        return any_retired

    def record_fire(self, chat_id: str, error_pattern: str) -> None:
        """Record that a fact was successfully used."""
        for key, state in self._fact_states.get(chat_id, {}).items():
            if state.error_pattern == error_pattern:
                state.fire()

    def get_lifecycle_status(self, chat_id: str) -> dict[str, str]:
        """Return lifecycle status of all facts for a chat (for API)."""
        result = {}
        if chat_id in self._fact_states:
            for key, state in self._fact_states[chat_id].items():
                parts = key.split(":")
                ep = parts[-1] if len(parts) > 1 else key
                result[ep] = state.state
        return result

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

        # Update lifecycle state for this fact
        fact_state = self._get_fact_state(chat_id, error_pattern, tool_name)
        fact_state.update(chat_id=chat_id, tool_name=tool_name, error_pattern=error_pattern, fact_text="")

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

        # Read from both tables — filter active + firing gate + not retired
        stmt_rf = sa_select(RepoFacts).where(
            RepoFacts.chat_id == chat_id,
            RepoFacts.active is True,
            RepoFacts.fire_rate >= FIRE_GATE,
            RepoFacts.lifecycle_state != "RETIRED",
        ).order_by(RepoFacts.confirmation_count.desc())

        stmt_mf = sa_select(MicroskillsFact).where(
            MicroskillsFact.chat_id == chat_id,
            MicroskillsFact.active is True,
            MicroskillsFact.fire_rate >= FIRE_GATE,
        ).order_by(MicroskillsFact.confirmation_count.desc())
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

                # ── Lifecycle confirm: track confirmation, check promotion ──
                state = _error_tracker._get_fact_state(chat_id, error_pattern, tool_name)
                promoted = state.confirm(file=repo_hash or "unknown")
                if promoted:
                    logger.info("[te] Fact PROMOTED to ACTIVE: %s", fact_text)

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

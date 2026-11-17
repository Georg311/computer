"""Tool usage tracker for cptr token economizer.

Tracks tool call counts per chat and across sessions to detect unused tools.
Generates pruning recommendations based on streak analysis.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import insert, select

from cptr.models.te import ToolUsage as TeToolUsage
from cptr.utils.db import get_session_factory

log = logging.getLogger(__name__)


class ToolUsageTracker:
    """Tracks tool usage per chat and across sessions for pruning recommendations."""

    def __init__(
        self,
        evidence_threshold: int = 5,
        immediate_prune_threshold: int = 1,
    ):
        """
        Args:
            evidence_threshold: Number of consecutive unused chats before recommending prune.
            immediate_prune_threshold: If tool was never used (0 calls), recommend immediately.
        """
        self.evidence_threshold = evidence_threshold
        self.immediate_prune_threshold = immediate_prune_threshold

    async def record_tool_call(self, chat_id: str, tool_name: str) -> None:
        """Record a single tool call for a chat."""
        async with get_session_factory()() as session:
            # Upsert the ToolUsage record
            result = await session.execute(
                select(TeToolUsage).where(
                    TeToolUsage.chat_id == chat_id,
                    TeToolUsage.tool_name == tool_name,
                )
            )
            existing = result.scalar_one_or_none()

            now_ms: int = self._now_ms()

            if existing is None:
                # First time seeing this tool in this chat
                await session.execute(
                    insert(TeToolUsage).values(
                        id=self._uuid(),
                        chat_id=chat_id,
                        tool_name=tool_name,
                        call_count=1,
                        first_seen=now_ms,
                        last_seen=now_ms,
                    )
                )
            else:
                existing.call_count = (existing.call_count or 0) + 1
                existing.last_seen = now_ms

            await session.commit()

    async def get_tool_usage(self, chat_id: str) -> List[dict]:
        """Get all tool usage for a specific chat."""
        async with get_session_factory()() as session:
            result = await session.execute(
                select(TeToolUsage).where(TeToolUsage.chat_id == chat_id)
            )
            rows = result.scalars().all()

        return [
            {
                "tool_name": r.tool_name,
                "call_count": r.call_count or 0,
                "first_seen": r.first_seen or 0,
                "last_seen": r.last_seen or 0,
            }
            for r in rows
        ]

    async def get_all_tool_usage(self) -> List[dict]:
        """Get all tool usage records across all chats."""
        async with get_session_factory()() as session:
            result = await session.execute(select(TeToolUsage))
            rows = result.scalars().all()

        return [
            {
                "tool_name": r.tool_name,
                "call_count": r.call_count or 0,
                "first_seen": r.first_seen or 0,
                "last_seen": r.last_seen or 0,
            }
            for r in rows
        ]

    async def analyze_tool_pruning(self, chat_id: str) -> List[dict]:
        """Analyze tool usage and generate pruning recommendations.

        Returns list of dicts with:
          - tool_name: name of the tool
          - call_count: total calls in this chat
          - sessions_unused: number of consecutive chats where tool was not used (estimated)
          - recommendation: "immediate" | "recommended" | None
          - reason: explanation string
        """
        # Get all known tools from usage records for this chat
        async with get_session_factory()() as session:
            result = await session.execute(
                select(TeToolUsage).where(TeToolUsage.chat_id == chat_id)
            )
            rows = result.scalars().all()

        tool_records = {r.tool_name: (r.call_count or 0) for r in rows}

        # Get all unique tools ever used across ALL chats to understand the catalog
        all_result = await session.execute(select(TeToolUsage))
        all_rows = all_result.scalars().all()
        global_tools = {r.tool_name: (r.call_count or 0) for r in all_rows}

        recommendations = []

        # Check each tool used in this chat
        for tool_name, call_count in tool_records.items():
            if call_count == 0:
                recommendations.append({
                    "tool_name": tool_name,
                    "call_count": 0,
                    "sessions_unused": self.evidence_threshold,
                    "recommendation": "immediate",
                    "reason": f"Tool '{tool_name}' was never used in this chat.",
                })

        # Check tools that have been used globally but not in this chat
        for tool_name, global_count in global_tools.items():
            if tool_name not in tool_records and global_count > 0:
                sessions_unused = await self._estimate_sessions_unused(chat_id, tool_name)
                recommendations.append({
                    "tool_name": tool_name,
                    "call_count": 0,
                    "sessions_unused": sessions_unused,
                    "recommendation": "recommended",
                    "reason": f"Tool '{tool_name}' has {global_count} calls across other chats but not in this one.",
                })

        # Filter out protected tools — they never get pruned recommendations
        from cptr.utils.te.toolprune.tools import PROTECTED_TOOLS
        filtered = [r for r in recommendations if r["tool_name"] not in PROTECTED_TOOLS]

        return filtered  # Return filtered list (PROTECTED_TOOLS removed)

    async def analyze_tool_pruning_evidence(self, chat_id: str, evidence_threshold: int = 5) -> List[dict]:
        """Evidence-gated tool pruning analysis.

        Mirrors TE's toolprune/stage.py build_tools() logic adapted for cptr:
          - Tracks tools loaded but unused across N consecutive sessions
          - Returns recommendations with evidence strength, not just counts
        
        Config Pattern: Liest evidence_threshold aus config.toml via load_config()!
        
        Args:
            chat_id: The current chat to analyze.
            evidence_threshold: Minimum consecutive unused chats before recommending prune.

        Returns list of dicts with:
          - tool_name: name of the tool
          - call_count: total calls in this chat
          - sessions_unused: number of consecutive chats where tool was not used
          - recommendation: "immediate" | "recommended" | "none"
          - reason: explanation string
          - evidence_strength: float 0.0–1.0 (higher = more confident)
        """
        from cptr.utils.te.toolprune.tools import PROTECTED_TOOLS
        
        # Config Pattern: Lese threshold aus config.toml!
        # [te_toolpruning]
        #   evidence_threshold = 5    # consecutive unused sessions before pruning (default: 5)
        #   check_interval = 20       # run analysis every N turns in chat loop (default: 20)
        try:
            from cptr.utils.db import load_config
            config = load_config()
            section = config.get("te_toolpruning", {})
            if not isinstance(section, dict):
                section = {}
            evidence_threshold = section.get("evidence_threshold", evidence_threshold)
        except Exception:
            pass  # Use default threshold if config unavailable

        # Get all known tools from usage records for this chat
        async with get_session_factory()() as session:
            result = await session.execute(
                select(TeToolUsage).where(TeToolUsage.chat_id == chat_id)
            )
            rows = result.scalars().all()

        tool_records = {r.tool_name: (r.call_count or 0) for r in rows}

        # Get all unique tools ever used across ALL chats to understand the catalog
        all_result = await session.execute(select(TeToolUsage))
        all_rows = all_result.scalars().all()
        global_tools = {r.tool_name: (r.call_count or 0) for r in all_rows}

        recommendations = []

        # Check each tool used in this chat — if never called, recommend with evidence
        for tool_name, call_count in tool_records.items():
            if tool_name in PROTECTED_TOOLS:
                continue  # Never prune protected tools
            
            if call_count == 0:
                sessions_unused = await self._estimate_sessions_unused(chat_id, tool_name)
                evidence_strength = min(1.0, sessions_unused / (evidence_threshold * 2))

                recommendations.append({
                    "tool_name": tool_name,
                    "call_count": 0,
                    "sessions_unused": sessions_unused,
                    "recommendation": "recommended" if evidence_strength >= 0.5 else "none",
                    "reason": f"Tool '{tool_name}' has {sessions_unused} consecutive unused sessions (threshold: {evidence_threshold}).",
                    "evidence_strength": round(evidence_strength, 2),
                })

        # Check tools that have been used globally but not in this chat
        for tool_name, global_count in global_tools.items():
            if tool_name in PROTECTED_TOOLS:
                continue  # Never prune protected tools
            
            if tool_name not in tool_records and global_count > 0:
                sessions_unused = await self._estimate_sessions_unused(chat_id, tool_name)
                evidence_strength = min(1.0, sessions_unused / (evidence_threshold * 2))

                recommendations.append({
                    "tool_name": tool_name,
                    "call_count": 0,
                    "sessions_unused": sessions_unused,
                    "recommendation": "recommended" if evidence_strength >= 0.5 else "none",
                    "reason": f"Tool '{tool_name}' has {global_count} calls across other chats but not in this one.",
                    "evidence_strength": round(evidence_strength, 2),
                })

        return recommendations

    async def _estimate_sessions_unused(self, chat_id: str, tool_name: str) -> int:
        """Estimate how many sessions a tool has been unused.

        Counts **consecutive** sessions (most recent first) where this tool was NOT used.
        Stops at the first session where it WAS used — that is not counted as "unused".
        Mirrors TE's `tool_unused_streaks` logic from toolprune/stage.py.
        """
        # Get all chats for this tool, ordered by most recent last_seen
        async with get_session_factory()() as session:
            result = await session.execute(
                select(TeToolUsage).where(
                    TeToolUsage.tool_name == tool_name
                ).order_by(TeToolUsage.last_seen.desc())
            )
            rows = result.scalars().all()

        # Count consecutive unused sessions (most recent first)
        streak = 0
        for row in rows:
            if row.chat_id == chat_id:
                continue  # skip the current chat
            if row.call_count and row.call_count > 0:
                break  # hit a used session — stop counting
            streak += 1

        return streak

    def _now_ms(self) -> int:
        """Return current time in milliseconds."""
        import time
        return int(time.time() * 1000)

    @staticmethod
    def _uuid() -> str:
        import uuid
        return str(uuid.uuid4())


async def analyze_tool_pruning(chat_id: str, evidence_threshold: int = 5) -> List[dict]:
    """Convenience function to analyze tool pruning for a chat."""
    tracker = ToolUsageTracker(evidence_threshold=evidence_threshold)
    return await tracker.analyze_tool_pruning(chat_id)


async def record_tool_call(chat_id: str, tool_name: str) -> None:
    """Convenience function to record a tool call."""
    tracker = ToolUsageTracker()
    await tracker.record_tool_call(chat_id, tool_name)

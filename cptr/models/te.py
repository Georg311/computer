"""TokenEconomizer database models (reference implementation).

These tables store per-chat TE state, tool usage stats, micro-skill facts,
and loop guard envelopes. All use the chat_id as the primary partition key.
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Boolean, Column, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from cptr.models.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TeStatus(Base):
    """Session-level token & cost accounting for one chat.

    Updated after each assistant turn (tool calls + LLM response).
    """

    __tablename__ = "te_status"

    id = Column(Text, primary_key=True, default=_uuid)
    chat_id = Column(
        Text,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    effective_tokens = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)
    cache_savings_pct = Column(Integer, default=0)  # percentage (0-100)
    pricing_overhead = Column(BigInteger, default=0)  # extra tokens from mechanisms
    session_cost_usd = Column(Float, default=0.0)  # total USD cost for the session

    # ── Class methods ────────────────────────────────────────

    @staticmethod
    async def get_by_chat(chat_id: str) -> TeStatus | None:
        from cptr.utils.db import get_session_factory

        session = get_session_factory()
        return await session.get(cls, chat_id)

    @classmethod
    async def ensure(cls, chat_id: str):
        """Create or return existing TeStatus for *chat_id*."""
        from cptr.utils.db import get_session_factory

        session = get_session_factory()
        instance = await session.get(cls, chat_id)
        if instance is None:
            instance = cls(chat_id=chat_id)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
        return instance


class ToolUsage(Base):
    """Per-chat tool call counts for pruning heuristics."""

    __tablename__ = "tool_usage"

    id = Column(Text, primary_key=True, default=_uuid)
    chat_id = Column(
        Text,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(Text, nullable=False)
    call_count = Column(Integer, default=0)
    first_seen = Column(BigInteger, default=0)
    last_seen = Column(BigInteger, default=0)

    __table_args__ = (
        # Unique per (chat_id, tool_name)
        {},
    )


class RepoFacts(Base):
    """Learned operating facts for micro-skills injection."""

    __tablename__ = "repo_facts"

    id = Column(Text, primary_key=True, default=_uuid)
    chat_id = Column(
        Text,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repo_hash = Column(Text, nullable=True)  # git rev-parse HEAD
    fact_text = Column(Text, nullable=False)
    fire_status = Column(Integer, default=0)  # 0=pending, >0=fire count
    confirmation_count = Column(Integer, default=0)
    active = Column(Boolean, default=True)

    @staticmethod
    async def get_active(chat_id: str) -> list["RepoFacts"]:
        from cptr.utils.db import get_session_factory
        from sqlalchemy import select as sa_select

        session = get_session_factory()
        stmt = sa_select(RepoFacts).where(
            RepoFacts.chat_id == chat_id,
            RepoFacts.active is True,
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


class LoopEnvelope(Base):
    """Loop guard state: envelope size, nudges, abort tracking."""

    __tablename__ = "loop_envelope"

    id = Column(Text, primary_key=True, default=_uuid)
    chat_id = Column(
        Text,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    envelope_size = Column(Integer, default=0)  # typical resolved-task length
    nudges_done = Column(Integer, default=0)
    aborted = Column(Boolean, default=False)
    resolved_turns = Column(JSON, nullable=True)  # JSON array of turn counts


class ToolPruneDecision(Base):
    """Per-chat record of tool pruning decisions (applied deny-list)."""

    __tablename__ = "tool_prune_decision"

    id = Column(Text, primary_key=True, default=_uuid)
    chat_id = Column(
        Text,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(Text, nullable=False)
    applied_at = Column(BigInteger, default=0)

    __table_args__ = (
        # Unique per (chat_id, tool_name) - one decision per tool per chat
        {},
    )


class MicroskillsFact(Base):
    """Rule-based learned facts for micro-skills injection (envfacts profile).

    Each row stores a short operating fact discovered from recurring tool-call errors.
    fire_status is a boolean flag indicating whether the LLM has successfully used this fact.
    """

    __tablename__ = "microskills_facts"

    id = Column(Text, primary_key=True, default=_uuid)
    chat_id = Column(
        Text,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repo_hash = Column(Text, nullable=True)  # git rev-parse HEAD
    fact_text = Column(Text, nullable=False)
    fire_status = Column(Boolean, default=False)  # True when LLM successfully used this fact
    confirmation_count = Column(Integer, default=0)
    active = Column(Boolean, default=True)

    @staticmethod
    async def get_active(chat_id: str) -> list["MicroskillsFact"]:
        from cptr.utils.db import get_session_factory
        from sqlalchemy import select as sa_select

        session = get_session_factory()
        stmt = sa_select(MicroskillsFact).where(
            MicroskillsFact.chat_id == chat_id,
            MicroskillsFact.active is True,
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

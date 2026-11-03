"""TokenEconomizer router: per-chat token & cost status API."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from cptr.models.te import LoopEnvelope, RepoFacts, TeStatus, ToolUsage, ToolPruneDecision
from cptr.models.chats import ChatMessage
from cptr.routers.chat import _get_user, COOKIE_NAME
from cptr.utils.db import get_session_factory
from cptr.utils.config import now_ms, load_config, save_config, invalidate_config_cache
from cptr.utils.te.pricing_wrapper import get_session_estimate
from cptr.utils.te.tool_usage_tracker import ToolUsageTracker, analyze_tool_pruning

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chats", tags=["token-economizer"])


class TeToolUsageItem(BaseModel):
    tool_name: str
    call_count: int
    first_seen: Optional[int] = None
    last_seen: Optional[int] = None


class TeStatusResponse(BaseModel):
    effective_tokens: int
    total_tokens: int
    cache_savings_pct: int
    pricing_overhead: int
    session_cost_usd: float
    tool_usage: List[TeToolUsageItem]


@router.get("/te/status", response_model=TeStatusResponse)
async def get_te_status(request: Request, chat_id: str = Query(...)):
    """Return token & cost status for a single chat.

    DB Primary: reads TeStatus from the database (fast, uses live tracking).
    Message-Fallback: if no TeStatus row exists, computes estimates from
    ChatMessage.usage records.
    Fresh input tokens: effective_tokens = sum(input_tokens - cache_read)
    per turn — shows real uncached prompt size, not weighted cost.
    """
    _get_user(request)

    async with get_session_factory()() as session:
        # ── DB Primary: read TeStatus ────────────────────────────
        status = (await session.execute(
            select(TeStatus).where(TeStatus.chat_id == chat_id)
        )).scalar_one_or_none()

        if status and (status.effective_tokens or 0) > 0:
            # DB has live tracking data — use it directly
            tools_result = await session.execute(
                select(ToolUsage).where(ToolUsage.chat_id == chat_id)
            )
            tools_rows = tools_result.scalars().all()

            tool_usage = [
                TeToolUsageItem(
                    tool_name=t.tool_name,
                    call_count=t.call_count,
                    first_seen=t.first_seen,
                    last_seen=t.last_seen,
                )
                for t in tools_rows
            ]

            return TeStatusResponse(
                effective_tokens=int(status.effective_tokens or 0),
                total_tokens=int(status.total_tokens or 0),
                cache_savings_pct=int(status.cache_savings_pct or 0),
                pricing_overhead=int(status.pricing_overhead or 0),
                session_cost_usd=float(status.session_cost_usd or 0.0),
                tool_usage=tool_usage,
            )

        # ── Message-Fallback: compute from ChatMessage.usage ─────
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id)
        )
        messages = result.scalars().all()

        token_records = []
        for msg in messages:
            usage = getattr(msg, "usage", None) if hasattr(msg, "usage") else None
            if isinstance(usage, dict):
                record = dict(usage)
                model = getattr(msg, "model", None)
                if model:
                    record["model"] = model
                token_records.append(record)

        # Compute fresh input tokens (not weighted cost)
        total_fresh_input = 0
        total_output = 0
        total_cache_read = 0
        for rec in token_records:
            if not isinstance(rec, dict):
                continue
            input_tok = rec.get("input_tokens") or 0
            cache_read = rec.get("cache_read_input_tokens") or 0
            # Also check cptr's legacy layout
            details = rec.get("input_tokens_details")
            if isinstance(details, dict):
                cache_read = max(cache_read, int(details.get("cached_tokens") or 0))
            output_tok = rec.get("output_tokens") or 0
            total_fresh_input += max(0, input_tok - cache_read)
            total_output += output_tok
            total_cache_read += cache_read

        total_raw = sum(rec.get("input_tokens", 0) + rec.get("cache_read_input_tokens", 0) + rec.get("output_tokens", 0) for rec in token_records if isinstance(rec, dict))

        # Compute session cost from usage records (weighted)
        estimate = get_session_estimate(token_records)

        # Fetch tool usage for this chat
        tools_result = await session.execute(
            select(ToolUsage).where(ToolUsage.chat_id == chat_id)
        )
        tools_rows = tools_result.scalars().all()

        # Fallback: if no tool_usage rows, try to extract from ChatMessage.usage
        if not tools_rows:
            try:
                from cptr.models import ChatMessage
                result = await session.execute(select(ChatMessage).where(ChatMessage.chat_id == chat_id))
                messages = result.scalars().all()
                tool_counts = {}
                for msg in messages:
                    usage = getattr(msg, "usage", None) if hasattr(msg, "usage") else None
                    if isinstance(usage, dict):
                        tool_calls = usage.get("tool_calls", [])
                        if isinstance(tool_calls, list):
                            for tc in tool_calls:
                                if isinstance(tc, dict):
                                    tool_name = tc.get("function", {}).get("name", "unknown")
                                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                # Build tool_usage from extracted data
                now_ms = now_ms()
                tool_usage = [
                    TeToolUsageItem(
                        tool_name=tool_name,
                        call_count=count,
                        first_seen=now_ms,
                        last_seen=now_ms,
                    )
                    for tool_name, count in tool_counts.items()
                ]
            except Exception:
                tool_usage = []

        # Cache savings: % of input_tokens that were served from cache
        total_input = sum((rec.get("input_tokens") or 0) for rec in token_records if isinstance(rec, dict))
        if total_input > 0:
            savings_pct = round(100 * total_cache_read / total_input, 2)
            savings_pct = max(0, min(100, savings_pct))
        else:
            savings_pct = 0

        pricing_overhead = int(max(0, total_raw - total_fresh_input))

        return TeStatusResponse(
            effective_tokens=total_fresh_input,
            total_tokens=total_raw,
            cache_savings_pct=int(savings_pct),
            pricing_overhead=pricing_overhead,
            session_cost_usd=float(estimate.get("session_cost_usd", 0.0)),
            tool_usage=tool_usage,
        )


# ── Optional: RepoFacts & LoopEnvelope endpoints (future phases) ──

@router.get("/te/repo-facts/{chat_id}")
async def get_repo_facts(request: Request, chat_id: str):
    """Return active repo facts for a chat."""
    _get_user(request)

    async with get_session_factory()() as session:
        result = await session.execute(
            select(RepoFacts).where(
                RepoFacts.chat_id == chat_id,
                RepoFacts.active is True,
            )
        )
        facts = result.scalars().all()

    return [
        {
            "id": f.id,
            "fact_text": f.fact_text,
            "fire_status": f.fire_status or 0,
            "confirmation_count": f.confirmation_count or 0,
        }
        for f in facts
    ]


@router.get("/te/loop-envelope/{chat_id}")
async def get_loop_envelope(request: Request, chat_id: str):
    """Return the loop guard envelope for a chat."""
    _get_user(request)

    async with get_session_factory()() as session:
        result = await session.execute(
            select(LoopEnvelope).where(LoopEnvelope.chat_id == chat_id)
        )
        env = result.scalar_one_or_none()

    if not env:
        return {"envelope_size": 0, "nudges_done": 0, "aborted": False}

    return {
        "envelope_size": env.envelope_size or 0,
        "nudges_done": env.nudges_done or 0,
        "aborted": env.aborted or False,
    }


# ── Tool Pruning endpoints ──────────────────────────────────

@router.get("/te/toolpruning/{chat_id}")
async def get_tool_pruning_analysis(request: Request, chat_id: str):
    """Analyze tool usage and return pruning recommendations for a chat."""
    _get_user(request)

    tracker = ToolUsageTracker()
    recommendations = await tracker.analyze_tool_pruning(chat_id)

    return {
        "chat_id": chat_id,
        "recommendations": recommendations,
        "evidence_threshold": tracker.evidence_threshold,
    }


@router.post("/te/toolpruning/apply/{chat_id}")
async def apply_tool_pruning(request: Request, chat_id: str):
    """Apply tool pruning decisions for a chat.

    POST body should contain {tool_names: ["edit", "read_file"]}.
    Records each tool in tool_prune_decision table so the chat_task
    can respect the deny-list on subsequent turns.
    """
    _get_user(request)

    from fastapi import Body, HTTPException
    from sqlalchemy import insert, select as sa_select

    body = await request.json()
    tool_names: list[str] = body.get("tool_names", [])

    if not isinstance(tool_names, list):
        raise HTTPException(status_code=400, detail="tool_names must be a list")

    applied_at = now_ms()

    async with get_session_factory()() as session:
        for tool_name in tool_names:
            # Upsert: insert or update existing decision
            result = await session.execute(
                sa_select(ToolPruneDecision).where(
                    (ToolPruneDecision.chat_id == chat_id) &
                    (ToolPruneDecision.tool_name == tool_name),
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                await session.execute(
                    insert(ToolPruneDecision).values(
                        chat_id=chat_id,
                        tool_name=tool_name,
                        applied_at=applied_at,
                    )
                )
            else:
                existing.applied_at = applied_at

        await session.commit()

    return {
        "ok": True,
        "chat_id": chat_id,
        "message": f"Tool pruning applied for {len(tool_names)} tool(s)",
        "applied_tools": tool_names,
    }


@router.get("/te/toolpruning/all")
async def get_all_tool_pruning(request: Request):
    """Get tool usage across all chats for global analysis."""
    _get_user(request)

    tracker = ToolUsageTracker()
    all_usage = await tracker.get_all_tool_usage()

    return {
        "total_tools": len(all_usage),
        "tools": all_usage,
    }


# ── TE Config endpoints ─────────────────────────────────────


class TeConfigUpdateRequest(BaseModel):
    section: str
    values: dict


@router.get("/te/config")
async def get_te_config(request: Request):
    """Return current TE configuration from all sources.

    Reads te_pricing, te_loopguard, te_microskills, and te_toolpruning
    sections from config.toml.
    """
    _get_user(request)

    config = load_config()

    pricing = config.get("te_pricing", {})
    if not isinstance(pricing, dict):
        pricing = {}

    loopguard = config.get("te_loopguard", {})
    if not isinstance(loopguard, dict):
        loopguard = {}

    microskills = config.get("te_microskills", {})
    if not isinstance(microskills, dict):
        microskills = {}

    toolpruning = config.get("te_toolpruning", {})
    if not isinstance(toolpruning, dict):
        toolpruning = {}

    return {
        "pricing": pricing,
        "loopguard": loopguard,
        "microskills": microskills,
        "toolpruning": toolpruning,
    }


@router.post("/te/config/update")
async def update_te_config(request: Request):
    """Update a TE config section in config.toml.

    POST body: { "section": "loopguard"|"microskills"|"toolpruning", "values": { key: value, ... } }
    """
    _get_user(request)

    body = await request.json()
    section = body.get("section", "")
    values = body.get("values", {})

    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="values must be a dict")

    valid_sections = ("loopguard", "microskills", "toolpruning")
    if section not in valid_sections:
        raise HTTPException(status_code=400, detail=f"section must be one of {valid_sections}")

    config = load_config()
    current_section = config.get(section, {})
    if not isinstance(current_section, dict):
        current_section = {}

    updated_keys: list[str] = []
    for key, value in values.items():
        current_section[key] = value
        updated_keys.append(key)

    config[section] = current_section
    save_config(config)
    invalidate_config_cache()

    return {
        "ok": True,
        "section": section,
        "updated_keys": updated_keys,
    }

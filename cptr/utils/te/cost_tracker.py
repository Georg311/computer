"""TokenEconomizer cost tracker — per-session accounting in SQLite.

Hooks into chat_task.py to record token usage and tool calls after every
model response, keeping te_status and tool_usage tables up to date.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Cache the last seen token records per chat_id so we can associate them with tools later.
_last_token_records: dict[str, list[dict]] = {}


def record_tool_call(chat_id: str, tool_name: str, token_record: dict | None) -> None:
    """Record a single tool call and its associated token usage.

    Called after each tool execution completes in chat_task.py.
    Writes to both `tool_usage` (per-tool counts) and `te_status` (session totals).

    Args:
        chat_id: The chat session identifier.
        tool_name: Name of the executed tool (e.g., "bash", "edit").
        token_record: Token usage dict from the model response that contained this call.
                      May be None if no usage data was available for this turn.
    """
    from cptr.models import TeStatus, ToolUsage

    # Update te_status with any new token records
    if token_record is not None:
        _append_token_record(chat_id, token_record)

    async def _update():
        from cptr.utils.db import get_session_factory

        # 1. Upsert tool_usage entry
        async with get_session_factory()() as session:
            existing = await session.execute(
                __import__("sqlalchemy", fromlist=["select"]).select(ToolUsage).where(
                    (ToolUsage.chat_id == chat_id) & (ToolUsage.tool_name == tool_name),
                )
            )
            entry = existing.scalar_one_or_none()

            now_ms = _now_ms()
            if entry is None:
                entry = ToolUsage(chat_id=chat_id, tool_name=tool_name, first_seen=now_ms)
                session.add(entry)
                await session.flush()
            entry.call_count += 1
            entry.last_seen = now_ms
            await session.commit()

        # 2. Ensure te_status exists and update it with latest token records
        status = await TeStatus.get_by_chat(chat_id)
        if status is None:
            status = await TeStatus.ensure(chat_id)

        # Compute fresh input tokens + session cost from in-memory records
        total_fresh_input = 0
        total_raw = 0
        total_cache_read = 0
        total_input = 0
        for rec in records:
            if not isinstance(rec, dict):
                continue
            input_tok = rec.get("input_tokens") or 0
            cache_read = rec.get("cache_read_input_tokens") or 0
            # Also check cptr's legacy layout (input_tokens_details.cached_tokens)
            details = rec.get("input_tokens_details")
            if isinstance(details, dict):
                cache_read = max(cache_read, int(details.get("cached_tokens") or 0))
            output_tok = rec.get("output_tokens") or 0
            total_fresh_input += max(0, input_tok - cache_read)
            total_raw += input_tok + cache_read + output_tok
            total_cache_read += cache_read
            total_input += input_tok

        # Cache savings: % of input_tokens served from cache
        if total_input > 0:
            savings_pct = round(100 * total_cache_read / total_input, 2)
            savings_pct = max(0, min(100, savings_pct))
        else:
            savings_pct = 0

        # Session cost (weighted, for billing accuracy)
        est = _estimate(records)
        session_cost_usd = float(est.get("session_cost_usd", 0.0))

        status.effective_tokens = total_fresh_input
        status.total_tokens = total_raw
        status.cache_savings_pct = int(savings_pct)
        status.pricing_overhead = int(max(0, total_raw - total_fresh_input))
        status.session_cost_usd = session_cost_usd

        # Save updated te_status
        async with get_session_factory()() as sess:
            sess.add(status)
            await sess.commit()

    # Run synchronously via asyncio to avoid blocking the main loop
    try:
        import asyncio

        existing_loop = None
        try:
            existing_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if existing_loop:
            asyncio.ensure_future(_update())
        else:
            import nest_asyncio

            nest_asyncio.apply()
            asyncio.run(_update())
    except Exception as exc:
        logger.warning("[te] cost_tracker.record_tool_call failed: %s", exc, exc_info=True)


def record_usage(chat_id: str, token_record: dict) -> None:
    """Record a model usage event (input/output tokens).

    Called when an API response completes — captures the full token breakdown.
    """
    _append_token_record(chat_id, token_record)


async def get_session_costs(chat_id: str) -> dict:
    """Retrieve aggregated session costs for a chat.

    Returns dict with effective_tokens, total_tokens, cache_savings_pct,
    pricing_overhead, session_cost_usd, and tool_usage breakdown.
    """
    from cptr.models import TeStatus, ToolUsage
    from sqlalchemy import select as sa_select

    async def _fetch():
        from cptr.utils.db import get_session_factory

        async with get_session_factory()() as session:
            # Get te_status
            status_row = await session.execute(sa_select(TeStatus).where(TeStatus.chat_id == chat_id))
            status = status_row.scalar_one_or_none()

            if not status:
                return {
                    "effective_tokens": 0,
                    "total_tokens": 0,
                    "cache_savings_pct": 0,
                    "pricing_overhead": 0,
                    "session_cost_usd": 0.0,
                    "tool_usage": [],
                }

            # Get tool usage breakdown
            tools = await session.execute(
                sa_select(ToolUsage).where(ToolUsage.chat_id == chat_id)
            )
            tool_rows = list(tools.scalars().all())

        from cptr.utils.te.pricing_wrapper import calculate_cost, get_session_estimate

        # Calculate total cost from cached records
        records = _last_token_records.get(chat_id, [])
        estimate = get_session_estimate(records)

        # Build tool usage with per-tool cost estimates
        tool_usage = []
        for t in tool_rows:
            tool_usage.append({
                "tool_name": t.tool_name,
                "call_count": t.call_count or 0,
                "first_seen": t.first_seen or 0,
                "last_seen": t.last_seen or 0,
            })

        return {
            "effective_tokens": status.effective_tokens or estimate["effective_tokens"],
            "total_tokens": status.total_tokens or estimate["total_tokens"],
            "cache_savings_pct": status.cache_savings_pct or estimate["cache_savings_pct"],
            "pricing_overhead": status.pricing_overhead or estimate["pricing_overhead"],
            "session_cost_usd": estimate["session_cost_usd"],
            "tool_usage": tool_usage,
        }

    return await _fetch()


def get_session_status(chat_id: str) -> dict | None:
    """Quick check if TE tracking exists for a chat."""
    return chat_id in _last_token_records and bool(_last_token_records[chat_id])


# ── Internal helpers ─────────────────────────────────────────

def _append_token_record(chat_id: str, record: dict) -> None:
    """Append a token record to the per-chat cache."""
    _last_token_records.setdefault(chat_id, []).append(record)


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)

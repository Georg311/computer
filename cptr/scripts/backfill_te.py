"""Backfill TE tables from existing chat_messages.usage records."""

from sqlalchemy import select, text


async def backfill():
    from cptr.models.chats import ChatMessage
    from cptr.models.te import TeStatus, ToolUsage
    from cptr.utils.db import get_session_factory
    from cptr.utils.te.pricing_wrapper import get_session_estimate

    async with get_session_factory()() as session:
        # Get all messages with usage data
        result = await session.execute(select(ChatMessage))
        messages = result.scalars().all()

        # Collect per-chat usage records and tool names
        chat_data: dict[str, list[dict]] = {}
        for msg in messages:
            usage = getattr(msg, "usage", None) if hasattr(msg, "usage") else None
            if isinstance(usage, dict) and (usage.get("input_tokens") or 0) > 0:
                chat_data.setdefault(msg.chat_id, []).append(dict(usage))

            # Extract tool names from output items
            output = getattr(msg, "output", None)
            if isinstance(output, list):
                for item in output:
                    if isinstance(item, dict) and item.get("type") == "function_call":
                        tool_name = item.get("name")
                        if tool_name:
                            # Upsert tool_usage
                            existing = await session.execute(
                                select(ToolUsage).where(
                                    (ToolUsage.chat_id == msg.chat_id) &
                                    (ToolUsage.tool_name == tool_name),
                                )
                            )
                            entry = existing.scalar_one_or_none()
                            if entry is None:
                                entry = ToolUsage(
                                    chat_id=msg.chat_id,
                                    tool_name=tool_name,
                                    call_count=1,
                                    first_seen=int(msg.created_at) if hasattr(msg, "created_at") else 0,
                                    last_seen=int(msg.created_at) if hasattr(msg, "created_at") else 0,
                                )
                                session.add(entry)
                            else:
                                entry.call_count += 1
                                entry.last_seen = int(msg.created_at) if hasattr(msg, "created_at") else 0

        await session.commit()

        # Now compute te_status per chat — fresh input tokens (not weighted cost)
        for chat_id, records in chat_data.items():
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
            est = get_session_estimate(records)
            session_cost_usd = float(est.get("session_cost_usd", 0.0))

            status = await TeStatus.get_by_chat(chat_id)
            if status is None:
                status = await TeStatus.ensure(chat_id)
            status.effective_tokens = total_fresh_input
            status.total_tokens = total_raw
            status.cache_savings_pct = int(savings_pct)
            status.pricing_overhead = int(max(0, total_raw - total_fresh_input))
            status.session_cost_usd = session_cost_usd

            session.add(status)

        await session.commit()

    # Print summary
    async with get_session_factory()() as session:
        tool_count = len((await session.execute(select(ToolUsage))).scalars().all())
        status_count = len((await session.execute(select(TeStatus))).scalars().all())
        print(f"Backfill complete: {tool_count} tool_usage rows, {status_count} te_status rows")


if __name__ == "__main__":
    import asyncio
    asyncio.run(backfill())

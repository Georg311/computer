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

        # Now compute te_status per chat
        for chat_id, records in chat_data.items():
            est = get_session_estimate(records)
            status = await TeStatus.get_by_chat(chat_id)
            if status is None:
                status = await TeStatus.ensure(chat_id)
            status.effective_tokens = int(est["effective_tokens"])
            status.total_tokens = int(est["total_tokens"])
            status.cache_savings_pct = int(est["cache_savings_pct"]) if est.get("cache_savings_pct") else 0
            status.pricing_overhead = int(max(0, est["total_tokens"] - est["effective_tokens"]))
            status.session_cost_usd = float(est.get("session_cost_usd", 0.0))

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

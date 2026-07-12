"""Durable one-shot timers backed by dormant internal child chats."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime

from cptr.env import TIMER_POLL_INTERVAL

logger = logging.getLogger(__name__)

_RELATIVE_TIME = re.compile(
    r"^(?:\+|in\s+)?(\d+)\s*(s|sec(?:onds?)?|m|min(?:utes?)?|h|hours?|d|days?)$"
)
_RFC3339_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_TIME_UNITS_NS = {
    "s": 1_000_000_000,
    "m": 60 * 1_000_000_000,
    "h": 60 * 60 * 1_000_000_000,
    "d": 24 * 60 * 60 * 1_000_000_000,
}
_manager_lock = asyncio.Lock()


def parse_timer_at(value: str) -> int:
    """Normalize a relative offset or timezone-aware RFC 3339 timestamp."""
    raw = value.strip()
    now = time.time_ns()
    relative = _RELATIVE_TIME.fullmatch(raw.lower())
    if relative:
        count = int(relative.group(1))
        if count <= 0:
            raise ValueError("at must be in the future.")
        return now + count * _TIME_UNITS_NS[relative.group(2)[0]]

    if not _RFC3339_TIME.fullmatch(raw):
        raise ValueError(
            "at must be a relative time such as 10s or in 10 seconds, "
            "or an RFC 3339 timestamp with a timezone."
        )
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "at must be a relative time such as 10s or in 10 seconds, "
            "or an RFC 3339 timestamp with a timezone."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("absolute at values must include an explicit timezone.")

    due_at = int(parsed.timestamp() * 1_000_000_000)
    if due_at <= now:
        raise ValueError("at must be in the future.")
    return due_at


async def cancel_timers_for_event(event) -> None:
    """Cancel matching dormant children after a committed parent-chat event."""
    subject = event.subject or {}
    if subject.get("type") != "chat" or not subject.get("id"):
        return

    from cptr.models import Chat
    from cptr.utils.config import now_ms

    async with _manager_lock:
        timers = await Chat.get_pending_timers(str(subject["id"]))
        for timer in timers:
            meta = dict(timer.meta or {})
            if event.event not in (meta.get("cancel_on") or []):
                continue
            meta.update(
                {
                    "timer_status": "cancelled",
                    "timer_cancelled_at": time.time_ns(),
                    "timer_cancelled_by": event.event,
                }
            )
            await Chat.update_meta(timer.id, meta, now_ms())


def _pack_parent_context(parent, messages, checkpoint_id: str | None) -> str:
    """Build a small launch-time view of the parent without changing its history."""
    message_by_id = {message.id: message for message in messages}
    branch = []
    current = message_by_id.get(parent.current_message_id)
    while current:
        branch.append(current)
        current = message_by_id.get(current.parent_id)
    branch.reverse()

    checkpoint_index = next(
        (index for index, message in enumerate(branch) if message.id == checkpoint_id), -1
    )
    changes = branch[checkpoint_index + 1 :] if checkpoint_index >= 0 else branch[-12:]
    changes = changes[-12:]

    parts = []
    summary = next(
        (message.chat_summary for message in reversed(branch) if message.chat_summary), None
    )
    if summary:
        parts.append(f"## Parent summary\n{summary[-4_000:]}")
    if changes:
        lines = []
        remaining = 6_000
        for message in changes:
            content = (message.content or "").strip()
            if not content:
                continue
            content = content[: min(len(content), remaining)]
            lines.append(f"{message.role}: {content}")
            remaining -= len(content)
            if remaining <= 0:
                break
        if lines:
            parts.append("## Changes since timer was set\n" + "\n\n".join(lines))
    return "\n\n".join(parts)


async def _set_timer_status(chat_id: str, status: str, **fields) -> None:
    from cptr.models import Chat
    from cptr.utils.config import now_ms

    chat = await Chat.get_by_id(chat_id)
    if not chat:
        return
    meta = dict(chat.meta or {})
    meta["timer_status"] = status
    meta.update(fields)
    await Chat.update_meta(chat_id, meta, now_ms())


async def set_timer_completion(record: dict, status: str, error: str | None) -> None:
    """Persist completion before the normal async-subagent result reaches the parent."""
    timer_chat_id = record.get("timer_chat_id")
    if not timer_chat_id:
        return
    final_status = "completed" if status == "completed" else "error"
    await _set_timer_status(
        timer_chat_id,
        final_status,
        timer_completed_at=time.time_ns(),
        timer_error=error,
    )


async def _launch_timer(timer, app) -> None:
    from cptr.models import Chat, ChatMessage
    from cptr.utils.async_subagents import (
        attach_subagent_chat,
        reserve_async_subagent,
        start_async_subagent,
    )
    from cptr.utils.chat_export import export_chat_to_file
    from cptr.utils.config import now_ms
    from cptr.utils.model_targets import ApiModelTarget, resolve_model_target
    from cptr.utils.tools import _get_subagent_config, _run_existing_subagent_chat

    async with _manager_lock:
        timer = await Chat.get_by_id(timer.id)
        if not timer:
            return
        meta = dict(timer.meta or {})
        if meta.get("timer_status") != "pending" or int(meta.get("timer_at") or 0) > time.time_ns():
            return

        parent = await Chat.get_by_id(meta.get("parent_chat_id", ""))
        if not parent:
            await _set_timer_status(timer.id, "error", timer_error="parent chat no longer exists")
            return

        config = await _get_subagent_config()
        if not config["background_enabled"]:
            return

        try:
            target = await resolve_model_target(meta["timer_model_id"], app.state)
        except Exception as exc:  # model configuration can change while a timer waits
            await _set_timer_status(timer.id, "error", timer_error=f"model unavailable: {exc}")
            return
        if not isinstance(target, ApiModelTarget):
            await _set_timer_status(
                timer.id, "error", timer_error="background timers require an API model"
            )
            return

        task_message = await ChatMessage.get_by_id(timer.current_message_id)
        if not task_message:
            await _set_timer_status(timer.id, "error", timer_error="timer task message is missing")
            return

        reserve = await reserve_async_subagent(
            config["max_async"],
            task=task_message.content,
            context="",
            workspace=meta.get("workspace", ""),
            user_id=timer.user_id,
            parent_chat_id=parent.id,
            parent_message_id=meta.get("timer_parent_message_id"),
            connection=target.connection,
            model=target.runtime_model,
            model_id=target.full_model_id,
            timer_chat_id=timer.id,
        )
        if reserve.get("status") == "rejected":
            return

        parent_messages = await ChatMessage.get_all_by_chat(parent.id)
        parent_context = _pack_parent_context(
            parent, parent_messages, meta.get("timer_parent_message_id")
        )
        content = task_message.content
        if parent_context:
            content = f"{content}\n\n## Parent context at launch\n{parent_context}"
        await ChatMessage.update(task_message.id, content=content)

        assistant_msg = await ChatMessage.create(
            chat_id=timer.id,
            role="assistant",
            content="",
            parent_id=task_message.id,
            model=target.full_model_id,
            done=False,
            created_at=now_ms(),
        )
        meta.update(
            {
                "timer_status": "running",
                "timer_started_at": time.time_ns(),
                "timer_assistant_message_id": assistant_msg.id,
                "delegation_id": reserve["delegation_id"],
            }
        )
        await Chat.update_meta(timer.id, meta, now_ms())
        await Chat.update_current_message(timer.id, assistant_msg.id, now_ms())
        await export_chat_to_file(timer.id)
        await attach_subagent_chat(
            reserve["delegation_id"],
            subagent_chat_id=timer.id,
            subagent_message_id=assistant_msg.id,
        )

        async def runner() -> str:
            return await _run_existing_subagent_chat(
                assistant_msg_id=assistant_msg.id,
                chat_id=timer.id,
                workspace=meta.get("workspace", ""),
                connection=target.connection,
                model=target.runtime_model,
                user_id=timer.user_id,
                config=config,
            )

        await start_async_subagent(reserve["delegation_id"], runner)


async def timer_worker_loop(app) -> None:
    """Poll durable pending timers; a capacity miss simply waits for the next pass."""
    from cptr.models import Chat

    logger.info("Timer worker started (poll interval: %ds)", TIMER_POLL_INTERVAL)
    while True:
        try:
            due = await Chat.get_due_timers(time.time_ns())
            for timer in due:
                await _launch_timer(timer, app)
        except Exception:
            logger.exception("Timer worker error")
        await asyncio.sleep(TIMER_POLL_INTERVAL)


async def recover_timers() -> None:
    """Do not replay work that was already launched before a process restart."""
    from cptr.models import Chat, ChatMessage
    from cptr.utils.config import now_ms

    for timer in await Chat.get_timers("pending"):
        current = await ChatMessage.get_by_id(timer.current_message_id)
        if current and current.role == "assistant":
            await ChatMessage.delete(current.id)
            await Chat.update_current_message(timer.id, current.parent_id, now_ms())

    for timer in await Chat.get_timers("running"):
        await _set_timer_status(
            timer.id,
            "error",
            timer_completed_at=time.time_ns(),
            timer_error="interrupted by restart",
        )

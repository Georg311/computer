"""Context usage helpers for chat compaction."""

from __future__ import annotations

from cptr.env import (
    CHAT_COMPACT_TOKEN_THRESHOLD,
    CHAT_COMPACT_MODE,
    CHAT_COMPACT_PERCENT_THRESHOLD,
    CHAT_COMPACT_KEEP_RECENT_TOKENS,
)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: len/4 for Latin text."""
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Total estimated tokens for a message list."""
    total = 0
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    total += estimate_tokens(block.get("text", ""))
                elif block.get("type") in ("image", "image_url"):
                    total += 1000  # rough estimate for images
        else:
            total += estimate_tokens(content)
        # Tool call arguments
        for tc in m.get("tool_calls", []):
            total += estimate_tokens(tc.get("function", {}).get("arguments", ""))
        total += 4  # per-message overhead (role, separators)
    return total


def should_compact(
    messages: list[dict],
    system_prompt: str,
    last_usage: dict | None = None,
    new_messages_since: int = 0,
    threshold: int | None = None,
) -> bool:
    """True when estimated tokens exceed the compact token threshold.

    Supports two modes:
      - "classic"  : absolute token threshold (existing behaviour)
      - "rolling"  : percentage of model context window + verbatim tail keep
    """
    resolved_threshold = threshold or _get_threshold()
    compact_mode = _get_compact_mode()

    if compact_mode == "rolling":
        return should_compact_rolling(
            messages, system_prompt, last_usage, new_messages_since, resolved_threshold
        )

    # Classic mode (existing behaviour)
    last_usage = normalize_usage(last_usage)
    if last_usage and last_usage.get("input_tokens"):
        base = last_usage["input_tokens"] + last_usage.get("output_tokens", 0)
        if new_messages_since > 0:
            new_msgs = messages[-new_messages_since:]
            base += estimate_messages_tokens(new_msgs)
        return base > resolved_threshold

    total = estimate_tokens(system_prompt) + estimate_messages_tokens(messages)
    return total > resolved_threshold


def should_compact_rolling(
    messages: list[dict],
    system_prompt: str,
    last_usage: dict | None = None,
    new_messages_since: int = 0,
    threshold: int | None = None,
) -> bool:
    """Rolling compaction: compact when usage exceeds percentage of context window."""
    percent_threshold = _get_percent_threshold() if threshold is None else min(95, max(10, threshold))
    context_window = _get_context_window()

    last_usage = normalize_usage(last_usage)
    if last_usage and last_usage.get("input_tokens"):
        base = last_usage["input_tokens"] + last_usage.get("output_tokens", 0)
        if new_messages_since > 0:
            new_msgs = messages[-new_messages_since:]
            base += estimate_messages_tokens(new_msgs)
        return (base * 100.0 / context_window) >= percent_threshold

    total = estimate_tokens(system_prompt) + estimate_messages_tokens(messages)
    return (total * 100.0 / context_window) >= percent_threshold


def _get_compact_mode() -> str:
    """Read compact mode from config, fall back to env var."""
    try:
        from cptr.utils.config import load_config

        config = load_config()
        val = config.get("app_config", {}).get("chat.compact_mode")
        if val and val in ("classic", "rolling"):
            return val
        val = config.get("chat", {}).get("compact_mode")
        if val and val in ("classic", "rolling"):
            return val
    except Exception:
        pass
    return CHAT_COMPACT_MODE


def _get_context_window() -> int:
    """Return the default context window size (200_000 tokens)."""
    try:
        from cptr.models import Config

        chat_models_config = Config.get_sync("chat.models") or {}
    except Exception:
        return 200_000

    for key, val in chat_models_config.items():
        if isinstance(val, dict) and "params" in val:
            cw = _parse_positive_int(val["params"].get("context_window"))
            if cw and cw > 0:
                return cw
    return 200_000


def _get_percent_threshold() -> int:
    """Read percent threshold from config, fall back to env var."""
    try:
        from cptr.utils.config import load_config

        config = load_config()
        val = config.get("app_config", {}).get("chat.compact_percent_threshold")
        if val is not None:
            return min(95, max(10, int(val)))
        val = config.get("chat", {}).get("compact_percent_threshold")
        if val is not None:
            return min(95, max(10, int(val)))
    except Exception:
        pass
    return CHAT_COMPACT_PERCENT_THRESHOLD


def _tail_keep_tokens() -> int:
    """Read verbatim tail keep from config, fall back to env var."""
    try:
        from cptr.utils.config import load_config

        config = load_config()
        val = config.get("app_config", {}).get("chat.compact_keep_recent_tokens")
        if val is not None:
            return int(val)
        val = config.get("chat", {}).get("compact_keep_recent_tokens")
        if val is not None:
            return int(val)
    except Exception:
        pass
    return CHAT_COMPACT_KEEP_RECENT_TOKENS


def _find_tail_start(messages: list[dict], target_tokens: int) -> int:
    """Find index where the last N tokens start (from end).

    Returns an index such that messages[idx:] has approximately *target_tokens*.
    If tail is larger than target, returns len(messages) — nothing to keep.
    """
    if not messages or target_tokens <= 0:
        return 0

    estimated = 0
    for i in range(len(messages) - 1, -1, -1):
        msg_tokens = estimate_messages_tokens([messages[i]])
        estimated += msg_tokens
        if estimated >= target_tokens:
            return max(i + 1, 2)  # keep at least 2 messages
    return len(messages)


def build_context_usage(tokens: int, *, threshold: int | None = None) -> dict:
    """Return context fullness stats for estimated token counts."""
    resolved_threshold = threshold or _get_threshold()
    percent = round((tokens / resolved_threshold) * 100) if resolved_threshold > 0 else 0
    return {
        "tokens": tokens,
        "estimated_tokens": tokens,
        "threshold": resolved_threshold,
        "percent": max(0, percent),
    }


def normalize_usage(usage: dict | None) -> dict | None:
    """Return provider usage with cptr's canonical token field names."""
    if not usage:
        return None
    normalized = dict(usage)
    input_tokens = _parse_nonnegative_int(
        normalized.get("input_tokens", normalized.get("prompt_tokens"))
    )
    output_tokens = _parse_nonnegative_int(
        normalized.get("output_tokens", normalized.get("completion_tokens"))
    )
    total_tokens = _parse_nonnegative_int(normalized.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    normalized["input_tokens"] = input_tokens
    normalized["output_tokens"] = output_tokens
    normalized["total_tokens"] = total_tokens
    return normalized


def usage_context_tokens(usage: dict | None) -> int:
    """Best available context token count from normalized or provider usage."""
    usage = normalize_usage(usage)
    if not usage:
        return 0
    if usage.get("input_tokens"):
        return usage["input_tokens"] + usage.get("output_tokens", 0)
    return usage.get("total_tokens", 0)


def estimate_context_usage(
    messages: list[dict], system_prompt: str, *, threshold: int | None = None
) -> dict:
    """Return context fullness stats using the same estimate as compaction."""
    resolved_threshold = threshold or _get_threshold()
    estimated_tokens = estimate_tokens(system_prompt) + estimate_messages_tokens(messages)
    return build_context_usage(estimated_tokens, threshold=resolved_threshold)


def _parse_positive_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_nonnegative_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def resolve_compact_token_threshold(
    model: str | None = None,
    *,
    chat_models_config: dict | None = None,
    global_threshold: int | None = None,
) -> int:
    """Return the effective compaction threshold for a model.

    Model-level values override the global default.
    """
    default_threshold = global_threshold or _get_threshold()
    model_threshold = None

    if chat_models_config:
        candidate_keys = []
        if model:
            candidate_keys.append(model)
            if "/" in model:
                candidate_keys.append(model.split("/", 1)[1])
        candidate_keys.append("*")

        for key in candidate_keys:
            params = chat_models_config.get(key, {}).get("params", {})
            model_threshold = _parse_positive_int(params.get("compact_token_threshold"))
            if model_threshold:
                break

    return model_threshold or default_threshold


async def load_compact_token_threshold(model: str | None = None) -> int:
    """Load the effective compaction threshold from persisted model config."""
    try:
        from cptr.models import Config

        chat_models_config = await Config.get("chat.models") or {}
    except Exception:
        chat_models_config = {}
    return resolve_compact_token_threshold(model, chat_models_config=chat_models_config)


def _get_threshold() -> int:
    """Read threshold: app_config (admin UI) > config.toml [chat] > env var/default."""
    try:
        from cptr.utils.config import load_config

        config = load_config()
        # Admin UI saves to [app_config] with dotted keys
        val = config.get("app_config", {}).get("chat.compact_token_threshold")
        if val is not None:
            return int(val)
        # Manual config.toml [chat] section
        val = config.get("chat", {}).get("compact_token_threshold")
        if val is not None:
            return int(val)
    except Exception:
        pass
    return CHAT_COMPACT_TOKEN_THRESHOLD

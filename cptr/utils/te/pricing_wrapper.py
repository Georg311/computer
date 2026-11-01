"""TokenEconomizer pricing wrapper — absolute Dollar costs per model call.

Wraps TE's cache-aware effective_tokens() with real-world provider prices so
every LLM cost can be reported in USD. Prices are configurable via config.toml
[te_pricing] and can be overridden through the Admin Settings API (T5.3).
"""

from __future__ import annotations

# Default per-1M-token prices in USD (input / cache_read / cache_write / output)
# These mirror pricing.MODEL_WEIGHTS ratios but as absolute dollar amounts.
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # --- OpenAI ----------------------------------------------------------
    "gpt-5.6-sol":     {"input": 0.01,   "cache_read": 0.001,  "cache_write": 0.0125,  "output": 0.06},
    "gpt-5.3-codex":   {"input": 0.015,  "cache_read": 0.00146, "cache_write": 0.0,    "output": 0.12},
    "gpt-5.6-luna":    {"input": 0.01,   "cache_read": 0.001,  "cache_write": 0.0125,  "output": 0.06},
    "gpt-5.6-terra":   {"input": 0.01,   "cache_read": 0.001,  "cache_write": 0.01248, "output": 0.06},
    "gpt-5-mini":      {"input": 0.01,   "cache_read": 0.0008,  "cache_write": 0.0,     "output": 0.08},
    "gpt-5.4":         {"input": 0.01,   "cache_read": 0.001,  "cache_write": 0.0,      "output": 0.06},
    "gpt-5.4-mini":    {"input": 0.01,   "cache_read": 0.00093,"cache_write": 0.0,      "output": 0.06},
    "gpt-5.5":         {"input": 0.01,   "cache_read": 0.001,  "cache_write": 0.0,      "output": 0.06},
    "gpt-5":           {"input": 0.0125, "cache_read": 0.00125,"cache_write": 0.0125,   "output": 0.10},
    "gpt-5.1":         {"input": 0.0125, "cache_read": 0.00125,"cache_write": 0.0125,   "output": 0.10},
    "gpt-5-codex":     {"input": 0.0125, "cache_read": 0.00125,"cache_write": 0.0125,   "output": 0.10},
    "gpt-5.1-codex":   {"input": 0.0125, "cache_read": 0.00125,"cache_write": 0.0125,   "output": 0.10},
    "gpt-5.1-codex-max":{"input": 0.0125,"cache_read": 0.00125,"cache_write": 0.0125,   "output": 0.10},
    "gpt-5.2-codex":   {"input": 0.0125, "cache_read": 0.00125,"cache_write": 0.0125,   "output": 0.10},
    # --- Anthropic -------------------------------------------------------
    "claude-haiku-4-5": {"input": 0.0013, "cache_read": 0.00013,"cache_write": 0.001625,"output": 0.005},
    "claude-opus-4-6":  {"input": 0.015,  "cache_read": 0.0015, "cache_write": 0.01875, "output": 0.075},
    "claude-opus-4-7":  {"input": 0.015,  "cache_read": 0.0015, "cache_write": 0.01875, "output": 0.075},
    "claude-opus-4-8":  {"input": 0.015,  "cache_read": 0.0015, "cache_write": 0.01875, "output": 0.075},
    "claude-opus-5":    {"input": 0.015,  "cache_read": 0.0015, "cache_write": 0.01875, "output": 0.075},
    "claude-sonnet-4-5":{"input": 0.003,  "cache_read": 0.0003, "cache_write": 0.00375, "output": 0.015},
    "claude-sonnet-4-6":{"input": 0.003,  "cache_read": 0.0003, "cache_write": 0.00375, "output": 0.015},
    "claude-sonnet-5":  {"input": 0.003,  "cache_read": 0.0003, "cache_write": 0.00375, "output": 0.015},
    # --- Google ----------------------------------------------------------
    "gemini-2.5-pro":   {"input": 0.0035, "cache_read": 0.00034,"cache_write": 0.0,      "output": 0.025},
    "gemini-3-flash-preview":{"input": 0.000163,"cache_read": 0.000016,"cache_write": 0.0,"output": 0.001},
    "gemini-3.1-pro-preview":{"input": 0.0035, "cache_read": 0.00035,"cache_write": 0.0,"output": 0.021},
    "gemini-3.5-flash": {"input": 0.000163,"cache_read": 0.000016,"cache_write": 0.0,   "output": 0.001},
    "gemini-3.6-flash": {"input": 0.000163,"cache_read": 0.000016,"cache_write": 0.0,   "output": 0.001},
}

# Default model when no specific model id is available (maps to Claude curve)
DEFAULT_MODEL_PRICING = {
    "input": 0.015, "cache_read": 0.0015, "cache_write": 0.01875, "output": 0.075,
}


def _resolve_model(rec: dict | None) -> str | None:
    """Resolve the billed model id from a token record."""
    if not isinstance(rec, dict):
        return None
    m = rec.get("model")
    if m and isinstance(m, str):
        # Strip provider prefix (e.g. "anthropic/claude-opus-4" -> "claude-opus-4")
        return m.rsplit("/", 1)[-1]
    # Fallback defaults
    agent = rec.get("agent", "")
    if isinstance(agent, str) and "codex" in agent.lower():
        return "gpt-5.6-sol"
    return None


def _get_pricing_table() -> dict[str, dict[str, float]]:
    """Load pricing from config.toml [te_pricing] or use defaults."""
    try:
        from cptr.utils.config import load_config

        config = load_config()
        custom = config.get("te_pricing", {})
        if isinstance(custom, dict) and custom:
            return custom  # Admin override present
    except Exception:
        pass
    return DEFAULT_PRICING


def weights_for(rec: dict | None) -> dict[str, float]:
    """Get per-model pricing for a token record.

    Resolution order:
      1. Explicit model id in record → custom pricing if available
      2. Model in default table → use defaults
      3. Claude variant → Claude curve
      4. Fallback → default pricing
    """
    model = _resolve_model(rec)
    pricing_table = _get_pricing_table()

    if model:
        key = model.lower()
        if key in pricing_table:
            return pricing_table[key]
        # Check Claude variants
        if "claude" in key:
            return {
                "input": 0.015, "cache_read": 0.0015,
                "cache_write": 0.01875, "output": 0.075,
            }

    # Fallback to defaults or custom pricing (use first entry as curve)
    if DEFAULT_MODEL_PRICING:
        return DEFAULT_MODEL_PRICING.copy()
    return {"input": 0.015, "cache_read": 0.0015, "cache_write": 0.01875, "output": 0.075}


def effective_tokens(rec: dict | None) -> int:
    """Cache-aware effective cost of one task, in fresh-input-token equivalents.

    Falls back to total_tokens at full weight when no breakdown is present.
    """
    from cptr.utils.te.pricing import effective_tokens as _te_effective

    if isinstance(rec, dict):
        # Use TE's cache-aware calculation
        return _te_effective(rec)

    tt = rec.get("tokens_total") if isinstance(rec, dict) else None
    return int(tt or 0)


def calculate_cost(token_record: dict | None) -> float:
    """Calculate the dollar cost of a single model call.

    Uses cache-aware effective tokens weighted by per-model pricing.
    Returns cost in USD (floating point, typically very small amounts).
    """
    if not isinstance(token_record, dict):
        return 0.0

    eff = effective_tokens(token_record)
    w = weights_for(token_record)

    # Calculate individual components
    input_cost = (token_record.get("input_tokens") or 0) * w["input"] / 1_000_000
    cache_read_cost = (token_record.get("cache_read_input_tokens") or 0) * w["cache_read"] / 1_000_000
    cache_write_cost = (token_record.get("cache_creation_input_tokens") or 0) * w["cache_write"] / 1_000_000
    output_cost = (token_record.get("output_tokens") or 0) * w["output"] / 1_000_000

    total = input_cost + cache_read_cost + cache_write_cost + output_cost
    return round(total, 8)  # Round to 8 decimal places for cents-level precision


def get_session_estimate(token_records: list[dict]) -> dict:
    """Aggregate cost estimates for a session (list of token records).

    Returns dict with: effective_tokens, total_tokens, cache_savings_pct,
                      pricing_overhead, session_cost_usd.
    """
    if not token_records:
        return {
            "effective_tokens": 0,
            "total_tokens": 0,
            "cache_savings_pct": 0,
            "pricing_overhead": 0,
            "session_cost_usd": 0.0,
        }

    total_eff = 0
    total_raw = 0
    total_cost = 0.0

    for rec in token_records:
        eff = effective_tokens(rec) if isinstance(rec, dict) else 0
        raw = rec.get("total_tokens", 0) if isinstance(rec, dict) else 0
        cost = calculate_cost(rec) if isinstance(rec, dict) else 0.0

        total_eff += int(eff)
        total_raw += int(raw or eff)  # fallback to eff when no breakdown
        total_cost += cost

    savings_pct = round(100 * (1 - total_eff / total_raw), 2) if total_raw > 0 else 0

    return {
        "effective_tokens": total_eff,
        "total_tokens": total_raw,
        "cache_savings_pct": savings_pct,
        "pricing_overhead": max(0, total_raw - total_eff),
        "session_cost_usd": round(total_cost, 6),
    }

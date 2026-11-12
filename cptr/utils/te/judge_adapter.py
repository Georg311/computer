"""LLM Judge adapter for LoopGuard – Tier-1 trace analysis.

Provides an LLM-based stuckness detector that receives a spiral-state digest
and returns {stuck: bool, confidence: float}. The judge is called only when
the Tier-0 gate passes (cheap rule check), so paid calls are rare.

Integration with loop_guard.py:
  * LoopGuard has llm_judge_callback parameter
  * This module provides the concrete implementation
"""
from __future__ import annotations

import logging
import json
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Judge prompt templates
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM_PROMPT = (
    "You are a trace-judge for an AI coding agent. Given a summary of recent "
    "tool calls and their outcomes, determine whether the agent is stuck in a "
    "failure loop.\n\n"
    "Return ONLY a JSON object with:\n"
    '  "stuck": true|false      — is the agent failing to make progress?\n'
    '  "confidence": 0.0-1.0     — how sure are you?\n'
    '\nConsider these signals:\n'
    '- Repeated identical tool calls with same arguments\n'
    '- High error rate (traceback, failed, error in outputs)\n'
    '- No productive progress over multiple turns\n'
    '- Spiral pattern: same mistake repeated without adaptation'
)

_JUDGE_USER_TEMPLATE = """Agent trace summary for chat {chat_id}:

Spiral state:
  - Total turns: {turns}
  - Error outputs: {error_outputs}
  - Repeated failure signals: {repeated_fail_sigs}
  - Stagnation score: {stagnation:.3f}
  - Spiral level: {spiral_level}

Recent tool calls (last {n_recent}):
{recent_calls}

Decision: Is the agent stuck? Return JSON.
"""


# ---------------------------------------------------------------------------
# State digest builder – creates a compact string from spiral state
# ---------------------------------------------------------------------------

def build_state_digest(spiral_snapshot: dict, envelope_summary: dict) -> str:
    """Build a token-cheap digest of the current spiral + envelope state.
    
    This is what gets passed to the LLM judge callback.
    
    Args:
        spiral_snapshot: Dict from LoopGuard.spiral_state
        envelope_summary: Dict from LoopGuard.envelope_state
        
    Returns:
        Formatted string digest for LLM consumption.
    """
    recent_calls = ""
    if "recent_calls" in spiral_snapshot:
        calls = spiral_snapshot["recent_calls"][:5]  # Limit to last 5
        recent_calls = "\n".join(f"- {c}" for c in calls)
    
    tmpl = _JUDGE_USER_TEMPLATE.format(
        chat_id=spiral_snapshot.get("chat_id", "unknown"),
        turns=spiral_snapshot.get("turns", 0),
        error_outputs=spiral_snapshot.get("error_outputs", 0),
        repeated_fail_sigs=spiral_snapshot.get("repeated_fail_sigs", 0),
        stagnation=spiral_snapshot.get("stagnation", 0.0),
        spiral_level=spiral_snapshot.get("level", "default"),
        n_recent=min(envelope_summary.get("size", 0), 5),
        recent_calls=recent_calls,
    )
    
    return tmpl


# ---------------------------------------------------------------------------
# LLM Judge callback implementation
# ---------------------------------------------------------------------------

def make_judge_callback(
    runner: Any = None,
    model: str = "agent",
) -> callable:
    """Create a judge callback compatible with LoopGuard.llm_judge_callback.
    
    The returned function has signature: (digest_string) -> {stuck: bool, confidence: float}
    
    Args:
        runner: Optional LLM runner callable(prompt, model) -> (response, eff_tokens)
        model: Model identifier for the call
        
    Returns:
        Callable suitable as LoopGuard.llm_judge_callback.
    """
    
    def _callback(digest: str) -> dict | None:
        """Judge callback: analyze digest and return stuckness assessment."""
        
        # Build full prompt with system + user message
        prompt = f"{_JUDGE_SYSTEM_PROMPT}\n\n---\n\n{digest}"
        
        try:
            # Call the LLM runner (if available)
            if runner is not None:
                raw_response, eff_tokens = runner(prompt, model)
                
                # Parse JSON from response
                result = _parse_judge_response(raw_response)
                
                if result and "stuck" in result:
                    logger.debug(
                        "[te] Judge: stuck=%s, confidence=%.2f",
                        result["stuck"],
                        result.get("confidence", 0.5),
                    )
                    return result
            
            # Fallback: heuristic judge when no LLM runner available
            return _heuristic_judge(digest)
            
        except Exception as e:
            logger.warning("[te] Judge callback failed: %s", e, exc_info=True)
            return None
    
    return _callback


def _parse_judge_response(raw: str) -> dict | None:
    """Parse JSON from LLM judge response."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None
    
    try:
        obj = json.loads(m.group(0))
        
        # Validate structure
        assert isinstance(obj.get("stuck"), bool), "stuck must be boolean"
        confidence = obj.get("confidence", 0.5)
        assert 0.0 <= confidence <= 1.0, "confidence must be 0-1"
        
        return {
            "stuck": bool(obj["stuck"]),
            "confidence": float(confidence),
        }
    except (json.JSONDecodeError, AssertionError, KeyError) as e:
        logger.warning("[te] Failed to parse judge response: %s", e)
        return None


def _heuristic_judge(digest: str) -> dict | None:
    """Fallback heuristic judge when LLM runner is unavailable.
    
    Analyzes the digest string for obvious stuck patterns without calling an LLM.
    """
    # Extract key metrics from digest (simple parsing)
    turns = 0
    error_outputs = 0
    
    for line in digest.split("\n"):
        if "turns:" in line.lower():
            m = re.search(r"(\d+)", line)
            if m:
                turns = int(m.group(1))
        if "error outputs:" in line.lower() or "error_outputs:" in line.lower():
            m = re.search(r"(\d+)", line)
            if m:
                error_outputs = int(m.group(1))
    
    # Heuristic rules
    stuck = False
    confidence = 0.5
    
    if turns >= 20 and error_outputs >= 8:
        stuck = True
        confidence = 0.7
    elif turns >= 30 and error_outputs >= 15:
        stuck = True
        confidence = 0.85
    
    return {"stuck": stuck, "confidence": confidence}


# ---------------------------------------------------------------------------
# ensemble_judge – Tier-0 gate + Tier-1 LLM judge integration
# ---------------------------------------------------------------------------

def ensemble_judge(
    tier0_gate_open: bool,
    spiral_snapshot: dict,
    envelope_summary: dict,
    llm_callback=None,
) -> dict | None:
    """Combined judge decision: Tier-0 gate + optional Tier-1 LLM call.
    
    Returns None when cheap check fails (no paid call).
    Returns {stuck, confidence} when LLM judge runs or heuristic fallback fires.
    
    Args:
        tier0_gate_open: Result of LoopGuard.tier0_gate_open
        spiral_snapshot: Current SpiralState snapshot
        envelope_summary: Current Envelope summary
        llm_callback: Optional callable(digest) -> {stuck, confidence}
        
    Returns:
        Dict with 'stuck' and 'confidence', or None if tier-0 closed.
    """
    
    # Tier-0 gate is the cheap check – short-circuit when closed
    if not tier0_gate_open:
        logger.debug("[te] ensemble_judge: tier-0 gate closed, skipping paid call")
        return None
    
    # Build digest for LLM judge
    digest = build_state_digest(spiral_snapshot, envelope_summary)
    
    # Call LLM judge (if available) or use heuristic fallback
    if llm_callback is not None:
        try:
            result = llm_callback(digest)
            if result and "stuck" in result:
                return result
        except Exception as e:
            logger.warning("[te] ensemble_judge LLM call failed, falling back to heuristic")
    
    # Fallback: heuristic judge
    logger.debug("[te] ensemble_judge: using heuristic fallback")
    return _heuristic_judge(digest)

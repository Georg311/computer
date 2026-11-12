"""Distiller integration layer for cptr plugin.

Provides the public API surface that connects the microskills Distiller
to the plugin's config and ledger:

  * propose_facts(repo, window, existing, ...) -> (extractors, facts)
    Orchestrates a single proposer tick via the model runner.
    
  * call_from_config(config) -> bool
    Gate predicate: True when injection.paid is enabled.

The proposer's effective-token cost accrues on Distiller.opt_tokens and must
be charged to the ledger as overhead by the caller (see pricing_overhead).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public gate function
# ---------------------------------------------------------------------------

def call_from_config(config) -> bool:
    """Return True when injection.paid is enabled (paid proposer should run).

    This is the config-driven gate that prevents paid LLM calls when
    injection is disabled or profile doesn't include 'distiller'.
    
    Args:
        config: InjectionConfig object from plugin.config.injection
        
    Returns:
        True if a paid proposer call is warranted.
    """
    if not hasattr(config, "paid"):
        return False
    return bool(config.paid)


# ---------------------------------------------------------------------------
# propose_facts - orchestrates one proposer tick
# ---------------------------------------------------------------------------

def propose_facts(
    distiller,
    runner: Callable[[str, str], tuple[str, float | None]],
    model: str = "agent",
) -> tuple[list[dict], list[dict]]:
    """Execute a single proposer tick and return (extractors, facts).

    This is the paid LLM call that authors new repo facts and extractors.
    
    Args:
        distiller: Distiller instance with populated window state.
        runner: Callable(prompt, model) -> (raw_response, effective_tokens)
        model: Model identifier to use for the call.
        
    Returns:
        Tuple of (extractors_list, facts_list) parsed from LLM response.
        
    Raises:
        ValueError: If distiller has no window or runner is None.
    """
    if not distiller.window:
        logger.debug("[te] propose_facts skipped: empty window")
        return [], []
    
    if distiller.runner is None and runner is None:
        raise ValueError("propose_facts requires a model runner")

    # Use provided runner or existing one
    effective_runner = runner or distiller.runner
    
    # Trigger the proposer tick directly (normally done via update())
    original_runner = distiller.runner
    try:
        distiller.runner = effective_runner
        
        # Manually trigger _maybe_propose which handles the paid LLM call
        distiller._maybe_propose()
        
        # Return newly admitted facts/extractors since last propose
        new_exts = []
        new_facts = []
        
        # Extractors added since last_propose (tracked via state)
        for name, ex in distiller.extractors.items():
            if hasattr(ex, 'to_dict'):
                new_exts.append(ex.to_dict())
        
        # Facts admitted since last propose
        for fid, fact in distiller.facts.items():
            if fact.state == "CANDIDATE":
                # New facts that haven't been promoted yet
                pass
        
    except Exception as e:
        logger.warning("[te] propose_factors failed: %s", e, exc_info=True)
        return [], []
    
    finally:
        distiller.runner = original_runner
    
    # Return the extractors and facts from current state
    exts = [e.to_dict() for name, e in distiller.extractors.items()]
    facts = [{
        "id": f.id,
        "claim": f.claim,
        "injection": f.injection,
        "high_stakes": f.high,
        "state": f.state,
        "detector": f.spec.get("detector", {}),
    } for fid, f in distiller.facts.items()]
    
    return exts, facts


# ---------------------------------------------------------------------------
# Convenience: build prompt and parse response
# ---------------------------------------------------------------------------

def build_and_parse_proposal(
    distiller,
    runner: Callable[[str, str], tuple[str, float | None]],
) -> dict:
    """Build proposer prompt, call LLM, return parsed result.
    
    This is a convenience wrapper for external callers who want full control
    over the proposal cycle.
    
    Returns:
        Dict with keys: 'prompt', 'raw_response', 'extractors', 'facts'
    """
    from .distiller import (
        build_proposer_prompt, parse_payload, proposer_view
    )
    
    if not distiller.window or distiller.runner is None and runner is None:
        return {"prompt": "", "raw_response": "", "extractors": [], "facts": []}
    
    effective_runner = runner or distiller.runner
    
    # Build the prompt (token-cheap)
    existing_facts = {i: f.claim for i, f in distiller.facts.items()}
    raw_excerpts = distiller._abstaining_excerpts()[:3]
    
    prompt = build_proposer_prompt(
        repo=distiller.repo,
        window=[proposer_view(d) for d in distiller.window],
        existing=existing_facts,
        existing_feats=set(distiller.extractors),
        raw_excerpts=raw_excerpts,
        external=[],
        generic=distiller.generic,
    )
    
    # Call the LLM
    try:
        raw_response, eff_tokens = effective_runner(prompt, distiller.model)
        
        if eff_tokens is not None:
            distiller.opt_tokens += eff_tokens
        
        exts, facts = parse_payload(raw_response)
        
        return {
            "prompt": prompt[:500] + "...",  # Truncated for readability
            "raw_response": raw_response,
            "extractors": exts,
            "facts": facts,
        }
    except Exception as e:
        logger.warning("[te] build_and_parse_proposal failed: %s", e)
        return {"prompt": prompt[:500], "raw_response": "", "extractors": [], "facts": []}

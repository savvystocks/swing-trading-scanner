"""School addendum Section 1 - GATE-MODE decision chain (DORMANT).

`school_mode` is a tunable with three values, default "off":
  off        - the frozen V10 engine decides alone. This module is never consulted. Orders are
               byte-identical to pre-school behavior (proven by v12_school_mot). THE DEFAULT.
  gatekeeper - the engine proposes; a candidate is purchased only if the school chain passes.
  sourcing   - the school also takes engine-SKIPPED candidates. HARD-BLOCKED until the fill ledger
               has measured real costs across the spread spectrum (a LIVE_GATE constant).

The chain (gatekeeper), in order, is pure and fail-CLOSED:
  1. engine already filtered this candidate in
  2. Student+Council blended probability clears THIS CONTRACT'S OWN break-even bar
  3. member disagreement is inside the band
  4. Treasurer size (fixed 1 until the Treasurer is separately promoted)
  5. drawdown ratchet
  6. macro brake has the final word
  7. -> order, with a broker-side ratchet stop attached
A MISSING FEATURE is not a veto (it flows through the model's NaN path upstream). A FAILED COMPONENT
(no calibrated probability, no quote, brake cannot evaluate, latency budget exceeded) is an absolute
VETO. Every veto is recorded by cause.

This file holds the LOGIC and the mode flag only. It is inert unless school_mode != "off", and the
live model-scoring wiring is the documented next step in LIVE_GATE.md - not enabled here.
"""
import os

VALID_MODES = ("off", "gatekeeper", "sourcing")


def school_mode(params=None):
    """Resolve the mode: env override, else params, else off. Any unknown value degrades to off."""
    m = os.environ.get("SCHOOL_MODE")
    if m is None and params is not None:
        m = params.get("school_mode")
    m = (m or "off").lower()
    return m if m in VALID_MODES else "off"


def is_dormant(params=None):
    return school_mode(params) == "off"


def decide(ctx):
    """The gatekeeper chain as a pure function. ctx keys:
        blend            calibrated Student+Council blended win-probability (None = component failure)
        disagree         member-probability std (None = component failure)
        contract_bar     this contract's own break-even
        disagree_max     the band ceiling
        macro_state      "CLEAR" | "BRAKE" | None (None = brake could not evaluate = component failure)
        drawdown         current fraction from high-water (>= halt => size 0 => veto)
        halt_drawdown    the halt line
        backstop_ready   bool - is a broker-side ratchet stop attachable (fleet backstop enabled)
    Returns {'decision','reason','size'}. size is fixed 1 (Treasurer dormant)."""
    # FAILED COMPONENT -> absolute veto (fail-closed)
    if ctx.get("blend") is None or ctx.get("disagree") is None:
        return {"decision": "VETO", "reason": "component_failure_no_probability", "size": 0}
    if ctx.get("macro_state") is None:
        return {"decision": "VETO", "reason": "component_failure_macro_unevaluable", "size": 0}
    if not ctx.get("backstop_ready", False):
        return {"decision": "VETO", "reason": "backstop_not_ready", "size": 0}
    # macro brake has the final word
    if ctx.get("macro_state") == "BRAKE":
        return {"decision": "VETO", "reason": "macro_brake", "size": 0}
    # drawdown ratchet at/through the halt
    if ctx.get("drawdown", 0.0) >= ctx.get("halt_drawdown", 0.30):
        return {"decision": "VETO", "reason": "drawdown_halt", "size": 0}
    # edge vs the contract's own bar
    if ctx["blend"] < ctx.get("contract_bar", 0.5944):
        return {"decision": "VETO", "reason": "below_contract_bar", "size": 0}
    # disagreement band
    if ctx["disagree"] > ctx.get("disagree_max", 0.18):
        return {"decision": "VETO", "reason": "members_disagree", "size": 0}
    return {"decision": "TAKE", "reason": "all_gates_passed", "size": 1}   # fixed 1 until Treasurer promoted


def gate_engine_candidate(params, candidate, scorer=None):
    """Engine-side hook. When dormant (the default) returns None and the engine proceeds untouched -
    this is the byte-identity guarantee the MOT asserts. When armed, it would run `scorer` (the live
    Student+Council) and apply decide(). scorer is injected so this module never imports sklearn."""
    if is_dormant(params):
        return None                                   # DORMANT: engine decides alone, nothing changes
    if scorer is None:
        return {"decision": "VETO", "reason": "component_failure_no_scorer", "size": 0}
    try:
        ctx = scorer(candidate)
    except Exception:
        return {"decision": "VETO", "reason": "component_failure_scorer_raised", "size": 0}
    return decide(ctx)

from datetime import datetime

from src.catalyst import regime_compass
from src.catalyst import sourcing_gates
from src.catalyst import strategy_vault
from src.catalyst import probe_ladder
from src.catalyst import paper_pipeline


def _gate_from_bias(bias):
    return {"SHORT": "SHORT", "LONG": "LONG"}.get((bias or "").upper(), "FLAT")


def screen(candidate, regime_state=None, vault_state=None, open_positions=None,
           returns_lookup=None, sector_map=None, combo=None, ladder_state=None, apply_blackout=True):
    if regime_state is None:
        regime_state = regime_compass.evaluate()
    bias = regime_state.get("bias")

    screen_res = sourcing_gates.evaluate_candidate(
        candidate, bias, open_positions, returns_lookup, sector_map)

    vstate = dict(vault_state or {})
    vstate["gate"] = _gate_from_bias(bias)
    route = strategy_vault.route(vstate)

    if ladder_state is None:
        ladder_state = probe_ladder.evaluate()

    sourcing_ok = screen_res["five_gates"]["passed"] and screen_res["sector_guard"]["passed"]
    earnings_setup = candidate.get("earnings_setup") or {}
    es = earnings_setup.get("setup")
    structure = route["structure"]
    if not sourcing_ok:
        decision, reasons = "REJECT", screen_res["reject_reasons"]
    elif es:
        decision, reasons = "TRADE", [earnings_setup.get("reason", es)]
        structure = earnings_setup.get("structure", structure)
    elif screen_res["positioning"]["passed"]:
        if route["tradeable"]:
            decision, reasons = "TRADE", [route["rationale"]]
        else:
            decision, reasons = "REJECT", [route["rationale"]]
    else:
        if route["tradeable"]:
            decision = "REROUTE"
            reasons = ["directional gate not met -> " + route["alert"]]
        else:
            decision = "REJECT"
            reasons = screen_res["positioning"]["reasons"] + [route["rationale"]]

    defined_ok = True
    if combo is not None:
        cd = combo.as_dict() if hasattr(combo, "as_dict") else combo
        defined_ok = bool(cd.get("defined_risk"))
        if not defined_ok:
            decision = "REJECT"
            reasons = list(reasons) + ["structure is not defined-risk"]

    blackout = {"blackout": False, "reasons": [], "checked": False}
    if apply_blackout:
        from src.catalyst import scan_safeguards
        blackout = scan_safeguards.event_blackout(candidate)
        if blackout["blackout"] and decision in ("TRADE", "REROUTE"):
            decision = "REJECT"
            reasons = list(reasons) + ["event blackout: " + ", ".join(blackout["reasons"])]

    if decision in ("TRADE", "REROUTE") and combo is None:
        decision = "REJECT"
        reasons = list(reasons) + ["no structurable combo (chain unavailable) - cannot verify defined risk"]

    return {
        "ticker": candidate.get("ticker"),
        "side": candidate.get("side"),
        "decision": decision,
        "structure": structure,
        "structure_family": route["family"],
        "route_alert": route["alert"],
        "earnings_setup": es,
        "size_multiplier": screen_res["sector_guard"].get("size_multiplier", 1.0),
        "regime": regime_state.get("regime"),
        "bias": bias,
        "size_pct": ladder_state["size_pct"],
        "ladder_rung": ladder_state["rung"],
        "active_tranche_gbp": ladder_state["ratchet"]["active_tranche_gbp"],
        "screen": screen_res,
        "defined_risk_ok": defined_ok,
        "blackout": blackout,
        "reasons": reasons,
    }


def _alert_from(candidate, combo_dict, decision):
    structure = combo_dict.get("structure") or ""
    if structure.endswith("backspread") or structure == "calendar_spread":
        family = "debit"
    else:
        family = "credit" if (combo_dict.get("net_credit") or 0) > 0 else "debit"
    if family == "credit":
        entry = combo_dict.get("net_credit")
    else:
        entry = combo_dict.get("net_debit") or combo_dict.get("net_credit") or combo_dict.get("max_loss_per_spread")
    return {
        "ticker": candidate.get("ticker"),
        "side": candidate.get("side"),
        "structure": combo_dict.get("structure") or decision["structure"],
        "family": family,
        "direction": combo_dict.get("direction"),
        "legs": combo_dict.get("legs"),
        "expiration": combo_dict.get("expiration"),
        "dte": (combo_dict.get("legs") or [{}])[0].get("dte"),
        "entry_premium": entry,
        "net_debit": combo_dict.get("net_debit"),
        "net_credit": combo_dict.get("net_credit"),
        "max_loss_per_spread": combo_dict.get("max_loss_per_spread"),
        "defined_risk": combo_dict.get("defined_risk"),
        "entry_spot": candidate.get("spot"),
        "regime": decision["regime"],
        "size_pct": decision["size_pct"],
        "gates": {"rung": decision["ladder_rung"], "structure": decision["structure"],
                  "confirmations": decision["screen"]["positioning"]["confirmations"]},
        "atr_trail_pct": candidate.get("atr_trail_pct"),
        "metadata": {
            "entry_hour_utc": datetime.utcnow().hour,
            "iv_rank": candidate.get("ivr"),
            "iv_pct": candidate.get("iv_pct"),
            "vix": candidate.get("vix"),
            "dte": (combo_dict.get("legs") or [{}])[0].get("dte"),
            "regime": decision.get("regime"),
            "structure": decision.get("structure"),
            "side": candidate.get("side"),
            "negative_gamma": candidate.get("negative_gamma"),
            "near_darkpool_node": candidate.get("near_darkpool_node"),
        },
    }


def process(candidate, combo=None, regime_state=None, vault_state=None, open_positions=None,
            returns_lookup=None, sector_map=None, ladder_state=None,
            apply_blackout=True, apply_cooldown=True):
    decision = screen(candidate, regime_state, vault_state, open_positions,
                      returns_lookup, sector_map, combo, ladder_state, apply_blackout)
    decision["logged"] = None
    decision["alerted"] = False
    decision["suppressed"] = False

    if decision["decision"] not in ("TRADE", "REROUTE"):
        return decision

    ticker = candidate.get("ticker")
    if apply_cooldown:
        from src.catalyst import scan_safeguards
        if scan_safeguards.already_alerted(ticker):
            decision["suppressed"] = True
            decision["reasons"] = list(decision["reasons"]) + ["cooldown: already alerted today"]
            return decision

    if combo is not None:
        cd = combo.as_dict() if hasattr(combo, "as_dict") else combo
        _positions, msg = paper_pipeline.log_alert(_alert_from(candidate, cd, decision))
        decision["logged"] = msg

    if apply_cooldown:
        from src.catalyst import scan_safeguards
        scan_safeguards.mark_alerted(ticker)
    decision["alerted"] = True
    return decision

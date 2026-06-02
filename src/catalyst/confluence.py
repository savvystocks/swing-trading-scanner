"""Confluence Detector - the keystone module.

Counts how many INDEPENDENT signals fire on each pick. The whole point of the
17 conviction inputs is that they say DIFFERENT THINGS. When 4-5 of them all
point the same way on a name, that's the high-conviction setup that compounds
the account.

Edge math (from academic + practitioner research):
  2 signals = ~52% win rate (barely profitable after costs)
  3 signals = ~58% win rate (small edge)
  4 signals = ~62-65% win rate (sweet spot)
  5+ signals = ~68-75% win rate (unicorn - take max size)

Confluence-driven sizing baked into position_size_for_pick():
  3 signals -> 20% of account
  4 signals -> 25% (standard)
  5+ signals -> 33% (max position)

The signals counted here are INDEPENDENT (not correlated):
  CATALYST:    catalyst_window 5-21d, activist_13d, earnings_history_bullish
  TECHNICAL:   vcp_setup PRIME/SETUP, mtf_trend aligned, quiet_rs leading,
               stage2 confirmed, pocket_pivot
  OPTIONS:     iv_window cheap, iv_window bull-pricing, uw_flow stacked,
               gex_favorable, dark_pool_accumulation
  SMART MONEY: insider_cluster CEO/CFO, insider_routine, edgar_buyback,
               edgar_guidance_raise
"""

from datetime import datetime


CATALYST_SIGNALS = ("catalyst_window", "activist_13d", "earnings_history_bullish", "index_rebalance")
TECHNICAL_SIGNALS = ("vcp_setup", "mtf_trend", "quiet_rs", "stage2", "pocket_pivot")
OPTIONS_SIGNALS = ("iv_window", "uw_flow", "gex_favorable", "dark_pool")
SMART_MONEY_SIGNALS = ("insider_cluster", "edgar_buyback", "edgar_guidance_raise")
POSITIONING_SIGNALS = ("cot_extreme", "dealer_gex_regime", "pb_flow_aligned")


def _check_catalyst_window(pick):
    fc = pick.get("_forward_catalyst") or {}
    days = fc.get("days_until")
    if days is None:
        return None
    if 5 <= days <= 21:
        return {"fires": True, "label": f"{fc.get('type', 'event').upper()} in {days}d", "score": fc.get("window_score", 80)}
    return {"fires": False, "label": None, "score": fc.get("window_score", 50)}


def _check_activist_13d(pick):
    a13d = pick.get("_activist_13d") or {}
    if a13d.get("fires"):
        return {"fires": True, "label": f"ACTIVIST: {a13d.get('name', 'unknown')}", "score": 95}
    return None


def _check_earnings_history_bullish(pick):
    eh = pick.get("_earnings_history") or {}
    if not eh:
        return None
    win_rate = eh.get("post_earnings_win_rate")
    avg_move = eh.get("avg_move_pct")
    if win_rate is None or avg_move is None:
        return None
    if win_rate >= 0.75 and avg_move >= 5:
        return {"fires": True, "label": f"history: {int(win_rate*100)}% win at avg +{avg_move:.1f}%", "score": 85}
    return {"fires": False, "label": None, "score": 50}


def _check_vcp_setup(pick):
    vcp = pick.get("_vcp_setup") or {}
    verdict = vcp.get("verdict")
    if verdict == "PRIME_BREAKOUT":
        return {"fires": True, "label": "PRIME BREAKOUT", "score": 90}
    if verdict == "BREAKOUT_SETUP":
        return {"fires": True, "label": "BREAKOUT SETUP", "score": 75}
    return {"fires": False, "label": None, "score": vcp.get("vcp_score", 50)}


def _check_mtf_trend(pick):
    mtf = pick.get("_mtf_trend") or {}
    if mtf.get("aligned_up"):
        return {"fires": True, "label": "trend aligned D+W+M", "score": 85}
    if mtf.get("aligned_down"):
        return {"fires": False, "label": None, "score": 25}
    return {"fires": False, "label": None, "score": 50}


def _check_quiet_rs(pick):
    """Already inside vcp_setup but call it out as independent signal too if quietly outperforming."""
    vcp = pick.get("_vcp_setup") or {}
    factors = vcp.get("factors") or {}
    qrs = factors.get("quiet_rs") or {}
    if qrs.get("pass") is True:
        return {"fires": True, "label": qrs.get("verdict", "quiet RS"), "score": 80}
    return None


def _check_stage2(pick):
    s2 = pick.get("_stage2_zone") or {}
    zone = s2.get("zone")
    if zone in ("PRIME_ENTRY", "EARLY", "STAGE_2_CONFIRMED"):
        return {"fires": True, "label": "Stage 2 trend", "score": 80}
    return None


def _check_pocket_pivot(pick):
    pp = pick.get("_pocket_pivot") or {}
    if pp.get("fires"):
        return {"fires": True, "label": pp.get("label", "pocket pivot"), "score": 75}
    return None


def _check_index_rebalance(pick):
    ir = pick.get("_index_rebalance") or []
    if isinstance(ir, list) and ir:
        match = ir[0]
        if match.get("days_until") is not None and match["days_until"] <= 30:
            return {"fires": True, "label": match.get("label", "index rebalance"), "score": 85}
    return None


def _check_cot_extreme(pick):
    cot = pick.get("_cot_positioning") or {}
    regime = cot.get("regime")
    if regime in ("CROWDED_SHORT",):
        return {"fires": True, "label": cot.get("label", "COT crowded short = long edge"), "score": 85}
    if regime in ("MODERATELY_SHORT",):
        return {"fires": True, "label": cot.get("label", "COT lean short = long edge"), "score": 65}
    if regime in ("CROWDED_LONG",):
        return {"fires": False, "label": cot.get("label"), "score": 25}
    return None


def _check_dealer_gex_regime(pick):
    gex = pick.get("_dealer_gex") or pick.get("_if_gex") or {}
    regime = gex.get("regime")
    if regime in ("NEGATIVE_AMP", "AMPLIFICATION"):
        return {"fires": True, "label": "negative GEX (amplification regime)", "score": 80}
    if regime in ("POSITIVE_PIN", "PINNING"):
        return {"fires": False, "label": "positive GEX (pinning regime)", "score": 40}
    return None


def _check_pb_flow_aligned(pick):
    pb = pick.get("_pb_flow") or {}
    if pb.get("aligned"):
        return {"fires": True, "label": pb.get("label", "PB flow aligned with thesis"), "score": 80}
    return None


def _check_squeeze_loaded(pick):
    sq = pick.get("_squeeze_setup") or {}
    if sq.get("fires"):
        return {"fires": True, "label": sq.get("label", "squeeze setup"), "score": sq.get("score", 75)}
    return None


def _check_analyst_revisions_positive(pick):
    ar = pick.get("_analyst_revisions") or {}
    if ar.get("verdict") == "POSITIVE_REVISIONS":
        return {"fires": True, "label": ar.get("label", "positive analyst revisions"), "score": 75}
    return None


def _check_auction_levels(pick):
    al = pick.get("_auction_levels") or {}
    position = al.get("position")
    if position == "ABOVE_VALUE":
        return {"fires": True, "label": f"auction: above value (POC ${al.get('poc')})", "score": 75}
    return None


def _check_macro_risk_on(pick):
    mp = pick.get("_macro_positioning") or {}
    if mp.get("regime") == "RISK_ON":
        return {"fires": True, "label": "macro regime: risk-on", "score": 70}
    if mp.get("regime") == "RISK_OFF_PRESSURE":
        return {"fires": False, "label": "macro regime: risk-off pressure", "score": 25}
    return None


def _check_iv_window(pick):
    ivw = pick.get("_iv_window") or {}
    verdict = ivw.get("verdict")
    if verdict == "IV_CHEAP_WINDOW":
        return {"fires": True, "label": "IV cheap pre-earnings", "score": 85}
    if verdict == "IV_TRAP":
        return {"fires": False, "label": None, "score": 25}
    return None


def _check_uw_flow(pick):
    flow = pick.get("_if_flow") or pick.get("_uw_flow") or []
    if isinstance(flow, list) and len(flow) >= 3:
        bullish = sum(1 for f in flow if (f.get("sentiment") or "").lower() == "bullish")
        if bullish >= 3:
            return {"fires": True, "label": f"{bullish} bullish sweeps", "score": 80}
    return None


def _check_gex_favorable(pick):
    gex = pick.get("_if_gex") or {}
    regime = gex.get("regime")
    if regime == "NEGATIVE_AMP":
        return {"fires": True, "label": "negative GEX (amplification)", "score": 75}
    return None


def _check_dark_pool(pick):
    dp = pick.get("_if_dark_pool") or pick.get("_uw_dark_pool") or []
    if isinstance(dp, list) and len(dp) >= 2:
        total_value = sum((p.get("value_usd") or 0) for p in dp)
        if total_value >= 5_000_000:
            return {"fires": True, "label": f"dark pool ${total_value/1e6:.1f}M", "score": 75}
    return None


def _check_insider_cluster(pick):
    insider = pick.get("insider_depth") or pick.get("_openinsider") or pick.get("_if_insider_cluster") or {}
    buyer_count = insider.get("buyer_count") or insider.get("buyers_count") or 0
    total_value = insider.get("total_value_usd") or 0
    ceo_or_cfo = insider.get("ceo_or_cfo_bought") or insider.get("ceo_or_cfo") or False
    if (buyer_count >= 3 and total_value >= 200_000) or (ceo_or_cfo and total_value >= 100_000):
        boost = 90 if ceo_or_cfo else 80
        label = f"insider cluster ({buyer_count} buyers, ${int(total_value/1000)}k{' CEO/CFO' if ceo_or_cfo else ''})"
        return {"fires": True, "label": label, "score": boost}
    return None


def _check_edgar_buyback(pick):
    bb = pick.get("_edgar_buyback") or {}
    if bb.get("verdict") == "BUYBACK_ANNOUNCED":
        return {"fires": True, "label": "buyback announced", "score": 75}
    return None


def _check_edgar_guidance(pick):
    gr = pick.get("_edgar_guidance_raise") or {}
    if gr.get("verdict") == "GUIDANCE_RAISED":
        return {"fires": True, "label": "guidance raised", "score": 80}
    return None


SIGNAL_CHECKERS = [
    ("catalyst_window", _check_catalyst_window, "CATALYST"),
    ("activist_13d", _check_activist_13d, "CATALYST"),
    ("earnings_history_bullish", _check_earnings_history_bullish, "CATALYST"),
    ("index_rebalance", _check_index_rebalance, "CATALYST"),
    ("vcp_setup", _check_vcp_setup, "TECHNICAL"),
    ("mtf_trend", _check_mtf_trend, "TECHNICAL"),
    ("quiet_rs", _check_quiet_rs, "TECHNICAL"),
    ("stage2", _check_stage2, "TECHNICAL"),
    ("pocket_pivot", _check_pocket_pivot, "TECHNICAL"),
    ("iv_window", _check_iv_window, "OPTIONS"),
    ("uw_flow", _check_uw_flow, "OPTIONS"),
    ("gex_favorable", _check_gex_favorable, "OPTIONS"),
    ("dark_pool", _check_dark_pool, "OPTIONS"),
    ("insider_cluster", _check_insider_cluster, "SMART_MONEY"),
    ("edgar_buyback", _check_edgar_buyback, "SMART_MONEY"),
    ("edgar_guidance_raise", _check_edgar_guidance, "SMART_MONEY"),
    ("cot_extreme", _check_cot_extreme, "POSITIONING"),
    ("dealer_gex_regime", _check_dealer_gex_regime, "POSITIONING"),
    ("pb_flow_aligned", _check_pb_flow_aligned, "POSITIONING"),
    ("squeeze_loaded", _check_squeeze_loaded, "POSITIONING"),
    ("macro_regime", _check_macro_risk_on, "POSITIONING"),
    ("analyst_revisions_positive", _check_analyst_revisions_positive, "SMART_MONEY"),
    ("auction_above_value", _check_auction_levels, "TECHNICAL"),
]


def compute_confluence(pick):
    """Returns dict with confluence_count, signals_firing list, confluence_score, sizing_tier."""
    firing = []
    by_category = {"CATALYST": 0, "TECHNICAL": 0, "OPTIONS": 0, "SMART_MONEY": 0, "POSITIONING": 0}
    for key, checker, category in SIGNAL_CHECKERS:
        try:
            res = checker(pick)
        except Exception:
            res = None
        if res is None:
            continue
        if res.get("fires"):
            firing.append({
                "signal": key,
                "category": category,
                "label": res.get("label"),
                "score": res.get("score", 70),
            })
            by_category[category] = by_category.get(category, 0) + 1

    confluence_count = len(firing)
    category_breadth = sum(1 for v in by_category.values() if v > 0)

    if confluence_count >= 5 and category_breadth >= 3:
        sizing_tier = "ELITE"
        confluence_score = 90
        sizing_pct = 33
    elif confluence_count >= 4 and category_breadth >= 2:
        sizing_tier = "STRONG"
        confluence_score = 80
        sizing_pct = 25
    elif confluence_count >= 3:
        sizing_tier = "MODERATE"
        confluence_score = 65
        sizing_pct = 20
    elif confluence_count >= 2:
        sizing_tier = "WEAK"
        confluence_score = 50
        sizing_pct = 0
    else:
        sizing_tier = "NONE"
        confluence_score = 35
        sizing_pct = 0

    return {
        "confluence_count": confluence_count,
        "category_breadth": category_breadth,
        "category_counts": by_category,
        "signals_firing": firing,
        "confluence_score": confluence_score,
        "sizing_tier": sizing_tier,
        "recommended_size_pct": sizing_pct,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }


def apply_confluence(picks, verbose=False):
    if not picks:
        return picks
    by_tier = {"ELITE": 0, "STRONG": 0, "MODERATE": 0, "WEAK": 0, "NONE": 0}
    for p in picks:
        try:
            res = compute_confluence(p)
            p["_confluence"] = res
            by_tier[res["sizing_tier"]] = by_tier.get(res["sizing_tier"], 0) + 1
        except Exception:
            continue
    if verbose:
        print(f"  confluence: ELITE={by_tier['ELITE']} STRONG={by_tier['STRONG']} MODERATE={by_tier['MODERATE']} WEAK={by_tier['WEAK']} NONE={by_tier['NONE']}")
    return picks

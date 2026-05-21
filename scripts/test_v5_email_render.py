import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.unified_email import render_unified_email
from src.catalyst.overall_score import compute_overall_score


def make_pick(
    ticker,
    name,
    sector,
    price,
    move_pct,
    catalysts,
    cat_score,
    survival_score,
    survival_verdict,
    earnings_quality_rating,
    bull_conf,
    bear_conv,
    bull_thesis,
    killer_thesis,
    is_trap,
    iv_pct,
    live_option=None,
    tier="A+",
    bracket="MICRO",
):
    pick = {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "live_spot": price,
        "price": price,
        "today_pct_change": move_pct,
        "bracket": bracket,
        "_aa_tier": tier,
        "_stacked_score": cat_score,
        "_category_count": len([c for c in catalysts if c.get("key")]),
        "catalysts": catalysts,
        "_survival_score": {
            "score": survival_score,
            "verdict": survival_verdict,
            "verdict_class": "survival-go" if survival_score >= 65 else "survival-reduce" if survival_score >= 50 else "survival-avoid",
            "action": "Full size allowed" if survival_score >= 65 else "Reduce size 50%" if survival_score >= 50 else "Avoid",
            "size_multiplier": 1.0 if survival_score >= 65 else 0.5,
            "kill_risks": [
                "Calendar: FOMC in 3d",
                "Vol regime: VIX 22.3 (normal)",
            ] if survival_score < 70 else [],
        },
        "_earnings_quality": {
            "rating": earnings_quality_rating,
            "earnings_quality_score": {"HIGH": 85, "MED": 65, "LOW": 45, "RED_FLAG": 20}.get(earnings_quality_rating, 60),
            "flags": [],
        },
        "iv_percentile_analysis": {
            "iv_percentile": iv_pct,
        },
        "unified_forensic": {
            "verdict": "BUY" if bull_conf >= 65 else "HOLD" if bull_conf >= 50 else "SKIP",
            "confidence_pct": bull_conf,
            "bull_thesis": bull_thesis,
        },
        "haiku_synthesis": {
            "verdict": "BUY" if bull_conf >= 65 else "HOLD" if bull_conf >= 50 else "SKIP",
            "confidence_pct": bull_conf,
            "bull_thesis": bull_thesis,
        },
        "bear_verification": {
            "bear_verdict": "TRAP" if is_trap else "OK",
            "bear_conviction_pct": bear_conv,
            "killer_thesis": killer_thesis,
            "is_this_trade_a_trap": is_trap,
        },
    }

    if live_option:
        pick["_live_option"] = live_option

    pick["_overall_score"] = compute_overall_score(pick)
    return pick


alms_option = {
    "strike": 25,
    "exp": "2026-06-19",
    "delta": 0.32,
    "iv_pct": 78.5,
    "mid": 0.85,
    "bid": 0.75,
    "ask": 0.95,
    "spread_pct": 23.5,
    "gamma": 0.04,
    "theta": -0.02,
    "vega": 0.05,
    "_fit": "acceptable",
}

usas_option = {
    "strike": 4,
    "exp": "2026-06-19",
    "delta": 0.42,
    "iv_pct": 95,
    "mid": 0.45,
    "bid": 0.40,
    "ask": 0.50,
    "spread_pct": 22,
    "gamma": 0.18,
    "theta": -0.012,
    "vega": 0.008,
    "_fit": "ideal",
}

nvax_option = {
    "strike": 9,
    "exp": "2026-07-17",
    "delta": 0.35,
    "iv_pct": 88,
    "mid": 0.62,
    "bid": 0.55,
    "ask": 0.68,
    "spread_pct": 21,
    "gamma": 0.10,
    "theta": -0.015,
    "vega": 0.018,
    "_fit": "ideal",
}

picks = [
    make_pick(
        "ALMS", "Alumis Inc",
        "Biotechnology",
        22.84, 4.3,
        [
            {"key": "clinical_milestone", "label": "Clinical trial data coming"},
            {"key": "earnings_lead_up_10_15d", "label": "Earnings in 10-15 days"},
            {"key": "cohort_biotech_binary", "label": "Biotech binary"},
            {"key": "insider_cluster", "label": "Insider buying cluster"},
        ],
        cat_score=235,
        survival_score=58,
        survival_verdict="REDUCE",
        earnings_quality_rating="MED",
        bull_conf=72,
        bear_conv=28,
        bull_thesis="Phase 2 PsO data due in 10 days. Beat Phase 1 endpoints by wide margin. Insider cluster + Lazar Capital stake = institutional conviction.",
        killer_thesis="Binary clinical event. If trial misses primary endpoint, stock could drop 40-60%. Cash runway tight.",
        is_trap=False,
        iv_pct=78,
        live_option=alms_option,
        tier="A+",
        bracket="MICRO",
    ),
    make_pick(
        "USAS", "Americas Gold and Silver",
        "Materials",
        3.95, 1.8,
        [
            {"key": "post_earnings_drift", "label": "Post-earnings drift"},
            {"key": "ratings_upgrade", "label": "Rating upgrade"},
            {"key": "contract_win", "label": "Contract win"},
        ],
        cat_score=185,
        survival_score=72,
        survival_verdict="GO",
        earnings_quality_rating="LOW",
        bull_conf=66,
        bear_conv=22,
        bull_thesis="Beat last earnings and stock has held the gains. Silver tailwind + Mexico mine restart on track. Sector rotation into precious metals continues.",
        killer_thesis="Small float means high volatility on any bad news. Mine permit risk in Mexico.",
        is_trap=False,
        iv_pct=58,
        live_option=usas_option,
        tier="A",
        bracket="MICRO",
    ),
    make_pick(
        "NVAX", "Novavax",
        "Biotechnology",
        9.12, -2.1,
        [
            {"key": "earnings_imminent_5_9d", "label": "Earnings 5-9 days"},
            {"key": "fda_event", "label": "FDA filing"},
            {"key": "strategic_partnership", "label": "Strategic partnership"},
        ],
        cat_score=210,
        survival_score=51,
        survival_verdict="REDUCE",
        earnings_quality_rating="LOW",
        bull_conf=58,
        bear_conv=35,
        bull_thesis="Earnings next week + flu/COVID combo vaccine FDA readout expected. Sanofi partnership milestones could be triggered.",
        killer_thesis="Cash burn continues, dilution risk on any FDA setback. Crowded short trade.",
        is_trap=False,
        iv_pct=72,
        live_option=nvax_option,
        tier="A",
        bracket="MICRO",
    ),
]

aa_results = {"A++": [], "A+": [picks[0]], "A": [picks[1], picks[2]]}
aa_picks = []
aa_rejections = [
    {"ticker": "KURA", "reason": "extension RED - 30d +38%"},
    {"ticker": "SAVA", "reason": "landmine - going concern language"},
    {"ticker": "BNGO", "reason": "IV percentile 96 - premium overpriced"},
]

scan = {
    "scan_date": "2026-05-16",
    "win_rate_stats": {"win_rate_pct": 58, "n": 17},
    "portfolio_summary": {"n_open": 1, "max_concurrent": 4},
}

html = render_unified_email(
    scan=scan,
    aa_results=aa_results,
    aa_picks=aa_picks,
    aa_rejections=aa_rejections,
    regime_info={"regime": "NORMAL", "position_multiplier": 1.0},
)

out_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "results", "V5_EMAIL_REFINED.html",
)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Rendered to: {out_path}")
print(f"Picks rendered: {len(picks)}")
for p in picks:
    o = p["_overall_score"]
    print(f"  {p['ticker']}: Overall {o['score']}/100 ({o['verdict']}) - {o['probability_of_profit_pct']}% PoP")

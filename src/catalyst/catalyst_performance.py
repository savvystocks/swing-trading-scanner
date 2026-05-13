import os
import json
import pathlib
from datetime import datetime, timedelta
from collections import defaultdict


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
PERFORMANCE_PATH = PROJECT_ROOT / "data" / "catalyst" / "catalyst_performance.json"
V4_PICKS_PATH = PROJECT_ROOT / "data" / "paper_trades" / "v4_picks.json"
SCORING_PATH = PROJECT_ROOT / "src" / "catalyst" / "scoring.py"


PRIOR_HIT_RATE = 0.50
PRIOR_AVG_GAIN = 5.0
PRIOR_WEIGHT_SAMPLES = 10
LOOKBACK_DAYS_DEFAULT = 90


def _load_perf():
    if not PERFORMANCE_PATH.exists():
        return {"catalyst_stats": {}, "last_updated": None, "version": 1}
    try:
        with open(PERFORMANCE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"catalyst_stats": {}, "last_updated": None, "version": 1}


def _save_perf(data):
    PERFORMANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.utcnow().isoformat()
    with open(PERFORMANCE_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _load_v4_picks():
    if not V4_PICKS_PATH.exists():
        return []
    try:
        with open(V4_PICKS_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def measure_catalyst_performance(lookback_days=LOOKBACK_DAYS_DEFAULT, verbose=False):
    picks = _load_v4_picks()
    if not picks:
        if verbose:
            print(f"  catalyst_performance: no v4 picks logged yet")
        return None

    cutoff = (datetime.utcnow().date() - timedelta(days=lookback_days)).isoformat()
    measured = [p for p in picks if p.get("scan_date", "") >= cutoff and (p.get("outcomes") or {}).get("measured_at")]
    if verbose:
        print(f"  catalyst_performance: {len(measured)}/{len(picks)} picks measured within {lookback_days}d")

    stats = defaultdict(lambda: {"n": 0, "wins": 0, "losses": 0, "stops": 0, "best_pcts": [], "drawdowns": [], "sample_tickers": []})

    for pick in measured:
        outcomes = pick.get("outcomes") or {}
        best_pct = outcomes.get("best_pct") or 0
        drawdown = outcomes.get("max_drawdown_pct") or 0
        hit_t1 = outcomes.get("hit_t1_pct50", False)
        hit_stop = outcomes.get("hit_stop_neg40", False)
        catalysts = pick.get("catalysts") or []
        ticker = pick.get("ticker", "?")

        for c in catalysts:
            if not isinstance(c, dict):
                continue
            key = c.get("key")
            if not key:
                continue
            s = stats[key]
            s["n"] += 1
            if hit_t1:
                s["wins"] += 1
            elif hit_stop:
                s["stops"] += 1
            else:
                s["losses"] += 1
            s["best_pcts"].append(best_pct)
            s["drawdowns"].append(drawdown)
            if len(s["sample_tickers"]) < 5:
                s["sample_tickers"].append(f"{ticker}@{pick.get('scan_date')}")

    summary = {}
    for key, s in stats.items():
        if s["n"] == 0:
            continue
        avg_best = sum(s["best_pcts"]) / len(s["best_pcts"]) if s["best_pcts"] else 0
        avg_drawdown = sum(s["drawdowns"]) / len(s["drawdowns"]) if s["drawdowns"] else 0
        raw_hit_rate = s["wins"] / s["n"]
        n_observed = s["n"]
        bayes_hit_rate = (
            (PRIOR_HIT_RATE * PRIOR_WEIGHT_SAMPLES + raw_hit_rate * n_observed)
            / (PRIOR_WEIGHT_SAMPLES + n_observed)
        )
        bayes_avg_gain = (
            (PRIOR_AVG_GAIN * PRIOR_WEIGHT_SAMPLES + avg_best * n_observed)
            / (PRIOR_WEIGHT_SAMPLES + n_observed)
        )
        edge_score = bayes_avg_gain * bayes_hit_rate
        summary[key] = {
            "n_picks": n_observed,
            "raw_hit_rate_pct": round(raw_hit_rate * 100, 1),
            "bayes_hit_rate_pct": round(bayes_hit_rate * 100, 1),
            "wins_t1": s["wins"],
            "stops": s["stops"],
            "raw_avg_best_pct": round(avg_best, 1),
            "bayes_avg_best_pct": round(bayes_avg_gain, 1),
            "raw_avg_drawdown_pct": round(avg_drawdown, 1),
            "edge_score": round(edge_score, 2),
            "sample_tickers": s["sample_tickers"],
        }

    summary_sorted = dict(sorted(summary.items(), key=lambda kv: kv[1]["edge_score"], reverse=True))

    perf_data = {
        "catalyst_stats": summary_sorted,
        "last_updated": datetime.utcnow().isoformat(),
        "version": 1,
        "lookback_days": lookback_days,
        "total_picks_measured": len(measured),
    }
    _save_perf(perf_data)
    if verbose:
        print(f"  catalyst_performance: updated stats for {len(summary)} catalyst types")
        print(f"  Top 5 by edge_score:")
        for key, stat in list(summary_sorted.items())[:5]:
            print(f"    {key:35s} edge={stat['edge_score']:6.2f} hit_rate={stat['bayes_hit_rate_pct']}% avg_gain={stat['bayes_avg_best_pct']}% n={stat['n_picks']}")
        print(f"  Bottom 5 by edge_score:")
        for key, stat in list(summary_sorted.items())[-5:]:
            print(f"    {key:35s} edge={stat['edge_score']:6.2f} hit_rate={stat['bayes_hit_rate_pct']}% avg_gain={stat['bayes_avg_best_pct']}% n={stat['n_picks']}")
    return perf_data


def suggest_weight_adjustments(verbose=False):
    perf = _load_perf()
    stats = perf.get("catalyst_stats") or {}
    if not stats:
        return None

    suggestions = {}
    sample_size_threshold = 5
    for key, stat in stats.items():
        if stat["n_picks"] < sample_size_threshold:
            continue
        edge = stat["edge_score"]
        if edge > 30:
            adjustment = "+0.5 pt (strong winner)"
            multiplier = 1.15
        elif edge > 15:
            adjustment = "+0.25 pt (above average)"
            multiplier = 1.07
        elif edge < 5:
            adjustment = "-0.5 pt (consistent loser)"
            multiplier = 0.85
        elif edge < 10:
            adjustment = "-0.25 pt (below average)"
            multiplier = 0.93
        else:
            adjustment = "no change (baseline)"
            multiplier = 1.0
        suggestions[key] = {
            "current_edge": edge,
            "n_picks": stat["n_picks"],
            "suggested_adjustment": adjustment,
            "multiplier": multiplier,
        }
    if verbose:
        print(f"\n  Weight adjustment suggestions (need >={sample_size_threshold} samples):")
        for key, s in suggestions.items():
            if s["multiplier"] != 1.0:
                print(f"    {key:35s} {s['suggested_adjustment']:35s} mult={s['multiplier']:.2f} (n={s['n_picks']})")
    return suggestions


def get_catalyst_edge(catalyst_key):
    perf = _load_perf()
    stats = perf.get("catalyst_stats") or {}
    return stats.get(catalyst_key)


def annotate_picks_with_performance(picks, verbose=False):
    perf = _load_perf()
    stats = perf.get("catalyst_stats") or {}
    if not stats:
        return
    enriched = 0
    for pick in picks or []:
        cats = pick.get("catalysts") or []
        cat_edges = []
        for c in cats:
            if not isinstance(c, dict):
                continue
            key = c.get("key")
            if not key or key not in stats:
                continue
            stat = stats[key]
            cat_edges.append({
                "key": key,
                "edge_score": stat.get("edge_score", 0),
                "hit_rate_pct": stat.get("bayes_hit_rate_pct", 50),
                "avg_gain_pct": stat.get("bayes_avg_best_pct", 5),
                "n_picks": stat.get("n_picks", 0),
            })
        if cat_edges:
            pick["_catalyst_performance"] = cat_edges
            enriched += 1
    if verbose and enriched:
        print(f"  catalyst_performance: annotated {enriched} picks with historical edge data")

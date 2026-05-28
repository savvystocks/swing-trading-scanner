"""Compute conviction trend for each pick: today's score vs prior scan.

Reads the most recent prior scan JSON, indexes its conviction scores by
ticker, then attaches a `_conviction_trend` block to each pick in today's
scan with prior score, delta, and a label (UP / FLAT / DOWN / NEW).
"""

import os
import glob
import json
import pathlib
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "results"


def _winning_score(pick):
    d = pick.get("_direction") or {}
    ws = d.get("winning_score")
    if ws is not None:
        return ws
    c = (pick.get("_conviction") or {}).get("score") or 0
    b = (pick.get("_bear_conviction") or {}).get("score") or 0
    return max(c, b)


def _find_prior_scan(today_str, max_lookback_days=7):
    files = sorted(glob.glob(str(RESULTS_DIR / "catalyst_*.json")), reverse=True)
    files = [f for f in files if "_email" not in os.path.basename(f) and "_intraweek" not in os.path.basename(f)]
    try:
        today = datetime.strptime(today_str, "%Y-%m-%d").date()
    except Exception:
        return None
    for f in files:
        base = os.path.basename(f)
        try:
            d_str = base.replace("catalyst_", "").replace(".json", "")
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if d >= today:
            continue
        if (today - d).days > max_lookback_days:
            return None
        return f
    return None


def _index_picks(scan):
    out = {}
    aa = scan.get("aa_results") or {}
    for tier, picks in aa.items():
        for p in picks or []:
            t = p.get("ticker")
            if not t:
                continue
            out[t] = {
                "tier": tier,
                "winning_score": _winning_score(p),
                "side": (p.get("_direction") or {}).get("side") or "CALL",
                "call_conviction": (p.get("_conviction") or {}).get("score") or 0,
                "bear_conviction": (p.get("_bear_conviction") or {}).get("score") or 0,
            }
    return out


def apply_trends(scan, verbose=False):
    today = scan.get("scan_date")
    if not today:
        return scan
    prior_path = _find_prior_scan(today)
    if not prior_path:
        if verbose:
            print(f"  conviction_trend: no prior scan within lookback - all picks will be NEW")
        prior_by_ticker = {}
    else:
        try:
            with open(prior_path, "r", encoding="utf-8") as f:
                prior_scan = json.load(f)
            prior_by_ticker = _index_picks(prior_scan)
            if verbose:
                print(f"  conviction_trend: prior scan {os.path.basename(prior_path)} indexed ({len(prior_by_ticker)} picks)")
        except Exception as e:
            if verbose:
                print(f"  conviction_trend: failed to load prior scan: {type(e).__name__}: {e}")
            prior_by_ticker = {}

    aa = scan.get("aa_results") or {}
    annotated = 0
    for tier, picks in aa.items():
        for p in picks or []:
            ticker = p.get("ticker")
            if not ticker:
                continue
            today_score = _winning_score(p)
            today_side = (p.get("_direction") or {}).get("side") or "CALL"
            prior = prior_by_ticker.get(ticker)
            if not prior:
                p["_conviction_trend"] = {
                    "label": "NEW",
                    "prior_score": None,
                    "prior_side": None,
                    "delta": None,
                    "side_changed": False,
                }
            else:
                delta = round(today_score - prior["winning_score"], 1)
                side_changed = prior["side"] != today_side
                if side_changed:
                    label = "FLIP"
                elif delta >= 5:
                    label = "UP"
                elif delta <= -5:
                    label = "DOWN"
                else:
                    label = "FLAT"
                p["_conviction_trend"] = {
                    "label": label,
                    "prior_score": prior["winning_score"],
                    "prior_side": prior["side"],
                    "delta": delta,
                    "side_changed": side_changed,
                }
            annotated += 1
    if verbose:
        print(f"  conviction_trend: annotated {annotated} picks")
    return scan

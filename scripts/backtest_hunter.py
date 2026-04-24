import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.options_hunter import SECTOR_TILT_KEYWORDS, _detect_sector_tilt, _compute_eta, _extension_adjustment


def _pass(v):
    return v in ("PASS", "PASS_BONUS")


def score_from_snapshot(w):
    mcap_b = (w.get("fundamentals") or {}).get("market_cap_b") or 0
    if mcap_b < 2.0:
        return {"qualified": False, "score": 0, "disqualified": f"mcap {mcap_b:.1f}B"}

    p = w.get("pillars_pre") or {}
    if p.get("p1_trend") == "FAIL":
        return {"qualified": False, "score": 0, "disqualified": "p1 fail"}

    score = 0
    reasons = []
    if _pass(p.get("p1_trend")):
        score += 10
    if _pass(p.get("p2_vol")):
        score += 10
        reasons.append("P2")
    if _pass(p.get("p3_canslim")):
        score += 5
    if _pass(p.get("p4_rs")):
        score += 10
    if _pass(p.get("p6_erm")):
        score += 20
        reasons.append("P6")
    if _pass(p.get("p7_squeeze")):
        score += 20
        reasons.append("P7")

    lb = w.get("lane_b_count_pre") or 0
    score += min(20, lb * 4)
    if lb >= 2:
        reasons.append(f"{lb}xLB")

    ne = w.get("near_earnings")
    earnings_days = None
    earnings_bucket = "none"
    if ne:
        earnings_days = ne.get("days_from_entry")
        try:
            d = int(earnings_days) if earnings_days is not None else None
        except (TypeError, ValueError):
            d = None
        if d is not None and 11 <= d <= 21:
            score += 15
            earnings_bucket = "sweet"
            reasons.append(f"earn {d}d")
        elif d is not None and abs(d) <= 30:
            score += 5
            earnings_bucket = "near"

    snap = w.get("pre_move_snapshot") or {}
    pct_from_high = snap.get("pct_from_52w_high")
    if pct_from_high is not None and pct_from_high >= -25:
        score += 10
        reasons.append("near 52wH")

    tilt = _detect_sector_tilt(w.get("sector"), w.get("industry"))
    if tilt:
        score += 5
        reasons.append(f"tilt:{tilt}")

    pct_200 = snap.get("pct_above_200d")
    if pct_200 is not None and pct_200 < 0:
        score -= 15
        reasons.append("below 200d")
    atr_pct = snap.get("atr_pct")
    if atr_pct is not None and atr_pct > 10:
        score -= 10
        reasons.append(f"ATR{atr_pct:.0f}%")

    pct_above_50d = snap.get("pct_above_50d")
    ext_adj = _extension_adjustment(pct_above_50d, None)
    if ext_adj["delta"] != 0:
        score += ext_adj["delta"]
        if ext_adj["label"]:
            reasons.append(ext_adj["label"])

    score = max(0, min(100, score))

    p2_mock = {"squeeze_percentile": None, "upper_band_break": False, "recent_squeeze_last_10d": False}
    eta_days, eta_label = _compute_eta(p2_mock, earnings_days, earnings_bucket, lb)

    return {
        "qualified": score >= 45,
        "score": int(round(score)),
        "reasons": reasons,
        "eta_days": eta_days,
        "eta_label": eta_label,
    }


def main():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "results", "50pct_movers_analyzed.json",
    )
    with open(path) as f:
        winners = json.load(f)
    print(f"Total analyzed winners: {len(winners)}")

    catchable = []
    for w in winners:
        p = w.get("pillars_pre") or {}
        g = w.get("gates_pre") or {}
        mcap = (w.get("fundamentals") or {}).get("market_cap_b") or 0
        if (
            _pass(p.get("p1_trend"))
            and _pass(p.get("p4_rs"))
            and _pass(g.get("g6_liq"))
            and mcap >= 2.0
        ):
            catchable.append(w)
    print(f"Catchable subset (P1+P4+G6+mcap>=$2B pre-move): {len(catchable)}")

    all_scored = [(w, score_from_snapshot(w)) for w in winners]
    catch_scored = [(w, score_from_snapshot(w)) for w in catchable]

    flagged = [ws for ws in catch_scored if ws[1]["qualified"]]
    print(f"\n=== HUNTER BACKTEST ===")
    print(f"Catchable winners flagged by hunter (score>=45): {len(flagged)}/{len(catchable)} ({len(flagged)*100/max(1,len(catchable)):.0f}%)")

    all_flagged = [ws for ws in all_scored if ws[1]["qualified"]]
    print(f"All winners flagged by hunter (score>=45):       {len(all_flagged)}/{len(winners)} ({len(all_flagged)*100/len(winners):.0f}%)")

    scores = sorted([s["score"] for _, s in catch_scored if s["score"] > 0], reverse=True)
    if scores:
        print(f"\nCatchable score distribution:")
        print(f"  max={max(scores)} median={scores[len(scores)//2]} min={min(scores)}")
        print(f"  >=70: {sum(1 for s in scores if s>=70)}")
        print(f"  60-69: {sum(1 for s in scores if 60<=s<70)}")
        print(f"  45-59: {sum(1 for s in scores if 45<=s<60)}")
        print(f"  <45:   {sum(1 for s in scores if s<45)}")

    print(f"\n=== TOP 25 CATCHABLE WINNERS BY HUNTER SCORE ===")
    catch_sorted = sorted(catch_scored, key=lambda ws: ws[1]["score"], reverse=True)
    print(f"{'TICKER':10s} {'SCORE':>5s} {'MOVE%':>6s} {'DAYS':>4s} {'MCAP':>6s} {'ETA':22s} {'REASONS':40s}")
    for w, s in catch_sorted[:25]:
        reasons_s = "; ".join(s.get("reasons", []))[:40]
        print(f"{w['ticker']:10s} {s['score']:>5d} {w['move_pct']:>5.1f}% {w['days_to_peak']:>4d} "
              f"{(w.get('fundamentals') or {}).get('market_cap_b',0):>5.1f}B "
              f"{(s.get('eta_label') or '')[:22]:22s} {reasons_s:40s}")

    print(f"\n=== CATCHABLE WINNERS MISSED BY HUNTER (score<45) ===")
    missed = [ws for ws in catch_scored if not ws[1]["qualified"]]
    if not missed:
        print("  None — 100% flag rate")
    else:
        print(f"{'TICKER':10s} {'SCORE':>5s} {'MOVE%':>6s} {'REASONS':50s}")
        for w, s in sorted(missed, key=lambda x: x[1]["score"]):
            print(f"{w['ticker']:10s} {s['score']:>5d} {w['move_pct']:>5.1f}% {('; '.join(s.get('reasons',[])))[:50]:50s}")

    print(f"\n=== ETA ACCURACY (catchable + flagged only) ===")
    within_bucket = {"fast<=10": 0, "mid 11-20": 0, "slow 21+": 0}
    actual_bucket = {"fast<=10": 0, "mid 11-20": 0, "slow 21+": 0}
    for w, s in flagged:
        eta = s.get("eta_days") or 99
        actual = w["days_to_peak"]
        def bucket(d):
            if d <= 10: return "fast<=10"
            if d <= 20: return "mid 11-20"
            return "slow 21+"
        within_bucket[bucket(eta)] += 1
        actual_bucket[bucket(actual)] += 1
    print(f"  Predicted bucket distribution: {within_bucket}")
    print(f"  Actual days-to-peak dist:      {actual_bucket}")


if __name__ == "__main__":
    main()

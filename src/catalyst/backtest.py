"""Backtest harness: validate signal weights against measured forward returns.

Reads conviction_journal.jsonl, isolates picks with measured outcomes, then:

1. Per-component edge: for each conviction component, bucket picks by
   component score (low/mid/high), measure forward returns in each bucket.
   If high-score buckets don't out-perform low-score buckets, that
   component carries no edge and its weight should drop.

2. Weight sweep: iterate alternative weight schemes (deltas around the
   current weights), recompute composite conviction, sort, measure top-N
   forward returns. Returns the weight scheme with the highest top-N
   average return.

3. Cross-validation: walk-forward by week to avoid look-ahead bias.

The system needs ~30 measured trading days (~150 entries) before weight
sweeps produce statistically meaningful suggestions. Until then this
module prints diagnostic stats and confidence intervals.
"""

import json
import pathlib
import itertools
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
JOURNAL_PATH = PROJECT_ROOT / "data" / "paper_trades" / "conviction_journal.jsonl"


CURRENT_WEIGHTS = {
    "llm_and_overall": 0.25,
    "insider": 0.13,
    "pead": 0.12,
    "buyback_guidance": 0.10,
    "options_flow": 0.08,
    "stage2": 0.08,
    "analyst": 0.06,
    "whisper": 0.06,
    "whalewisdom": 0.06,
    "trends": 0.06,
}

MIN_PICKS_FOR_SWEEP = 100
COMPONENT_LOW_HIGH_THRESHOLD = (40, 70)


def _load_journal():
    if not JOURNAL_PATH.exists():
        return []
    rows = []
    with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _measured_only(rows):
    out = []
    for r in rows:
        o = r.get("outcomes") or {}
        if o.get("ret_5d_pct") is None and o.get("best_pct") is None:
            continue
        out.append(r)
    return out


def _normalized_return(r, is_put):
    o = r.get("outcomes") or {}
    val = o.get("ret_5d_pct") if o.get("ret_5d_pct") is not None else o.get("best_pct")
    if val is None:
        return None
    return -val if is_put else val


def per_component_edge(rows):
    """For each component score band, what was the average forward return?

    If high-score picks (component >= 70) outperform low-score (<= 40),
    the component carries edge. If they don't, the component contributes
    noise.
    """
    measured = _measured_only(rows)
    if not measured:
        return None

    component_keys = list(CURRENT_WEIGHTS.keys())
    out = {}

    for ck in component_keys:
        low_rets = []
        mid_rets = []
        high_rets = []
        for r in measured:
            comps = (r.get("components") or {}).get("conviction_components") or {}
            score = comps.get(ck)
            if score is None:
                continue
            is_put = r.get("side") == "PUT"
            ret = _normalized_return(r, is_put)
            if ret is None:
                continue
            if score <= COMPONENT_LOW_HIGH_THRESHOLD[0]:
                low_rets.append(ret)
            elif score >= COMPONENT_LOW_HIGH_THRESHOLD[1]:
                high_rets.append(ret)
            else:
                mid_rets.append(ret)

        def _mean(xs):
            return sum(xs) / len(xs) if xs else None

        low_avg = _mean(low_rets)
        high_avg = _mean(high_rets)
        edge = (high_avg - low_avg) if (low_avg is not None and high_avg is not None) else None
        out[ck] = {
            "low_n": len(low_rets),
            "low_avg_pct": round(low_avg, 2) if low_avg is not None else None,
            "mid_n": len(mid_rets),
            "mid_avg_pct": round(_mean(mid_rets), 2) if mid_rets else None,
            "high_n": len(high_rets),
            "high_avg_pct": round(high_avg, 2) if high_avg is not None else None,
            "edge_pts": round(edge, 2) if edge is not None else None,
            "current_weight": CURRENT_WEIGHTS[ck],
        }
    return out


def _recompute_score(comps, weights):
    return sum((comps.get(k) or 50) * w for k, w in weights.items())


def weight_sweep(rows, top_n=10, deltas=(-0.05, 0, 0.05), max_combos=400):
    measured = _measured_only(rows)
    if len(measured) < MIN_PICKS_FOR_SWEEP:
        return {
            "status": "INSUFFICIENT_DATA",
            "n_measured": len(measured),
            "min_required": MIN_PICKS_FOR_SWEEP,
            "message": f"Need {MIN_PICKS_FOR_SWEEP - len(measured)} more measured picks before weight sweep is meaningful.",
        }

    component_keys = list(CURRENT_WEIGHTS.keys())
    candidate_weights = []
    for combo in itertools.product(deltas, repeat=len(component_keys)):
        w = {k: max(0.01, CURRENT_WEIGHTS[k] + d) for k, d in zip(component_keys, combo)}
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}
        candidate_weights.append(w)
        if len(candidate_weights) >= max_combos:
            break

    results = []
    by_date = {}
    for r in measured:
        by_date.setdefault(r.get("scan_date"), []).append(r)

    baseline_top_avg = None
    for w in [CURRENT_WEIGHTS] + candidate_weights:
        per_date_top_returns = []
        for d, picks in by_date.items():
            scored = []
            for p in picks:
                comps = (p.get("components") or {}).get("conviction_components") or {}
                if not comps:
                    continue
                is_put = p.get("side") == "PUT"
                ret = _normalized_return(p, is_put)
                if ret is None:
                    continue
                score = _recompute_score(comps, w)
                scored.append((score, ret))
            if not scored:
                continue
            scored.sort(key=lambda x: -x[0])
            top = [r for _, r in scored[:top_n]]
            if top:
                per_date_top_returns.append(sum(top) / len(top))
        if not per_date_top_returns:
            continue
        avg = sum(per_date_top_returns) / len(per_date_top_returns)
        if baseline_top_avg is None:
            baseline_top_avg = avg
        results.append({"weights": w, "avg_top_ret": round(avg, 3), "n_days": len(per_date_top_returns)})

    results.sort(key=lambda x: -x["avg_top_ret"])
    best = results[0] if results else None
    delta_vs_baseline = round(best["avg_top_ret"] - baseline_top_avg, 3) if (best and baseline_top_avg is not None) else None

    if best:
        weight_changes = {}
        for k in component_keys:
            old = CURRENT_WEIGHTS[k]
            new = best["weights"][k]
            weight_changes[k] = {
                "from": round(old, 3),
                "to": round(new, 3),
                "delta": round(new - old, 3),
            }

    return {
        "status": "OK",
        "n_measured": len(measured),
        "n_days": len(by_date),
        "baseline_avg_top_ret": round(baseline_top_avg, 3) if baseline_top_avg is not None else None,
        "best_avg_top_ret": best["avg_top_ret"] if best else None,
        "delta_vs_baseline": delta_vs_baseline,
        "best_weights": best["weights"] if best else None,
        "weight_changes": weight_changes if best else None,
        "top_5_results": results[:5],
    }


def walk_forward_validation(rows, train_days=14, test_days=7):
    measured = _measured_only(rows)
    if len(measured) < 50:
        return {"status": "INSUFFICIENT_DATA", "n_measured": len(measured)}

    dates = sorted({r["scan_date"] for r in measured})
    if len(dates) < (train_days + test_days):
        return {"status": "INSUFFICIENT_DATE_RANGE", "n_unique_dates": len(dates), "required": train_days + test_days}

    folds = []
    for i in range(0, len(dates) - train_days - test_days + 1, test_days):
        train_dates = set(dates[i:i + train_days])
        test_dates = set(dates[i + train_days:i + train_days + test_days])
        train_rows = [r for r in measured if r["scan_date"] in train_dates]
        test_rows = [r for r in measured if r["scan_date"] in test_dates]
        if len(train_rows) < 20 or len(test_rows) < 10:
            continue
        train_sweep = weight_sweep(train_rows, top_n=10)
        if train_sweep.get("status") != "OK" or not train_sweep.get("best_weights"):
            continue
        best_w = train_sweep["best_weights"]
        test_returns = []
        by_test_date = {}
        for r in test_rows:
            by_test_date.setdefault(r["scan_date"], []).append(r)
        for d, picks in by_test_date.items():
            scored = []
            for p in picks:
                comps = (p.get("components") or {}).get("conviction_components") or {}
                is_put = p.get("side") == "PUT"
                ret = _normalized_return(p, is_put)
                if ret is None:
                    continue
                score = _recompute_score(comps, best_w)
                scored.append((score, ret))
            scored.sort(key=lambda x: -x[0])
            top = [r for _, r in scored[:10]]
            if top:
                test_returns.append(sum(top) / len(top))
        if test_returns:
            folds.append({
                "train_dates": sorted(train_dates),
                "test_dates": sorted(test_dates),
                "train_best_ret": train_sweep["best_avg_top_ret"],
                "test_ret": round(sum(test_returns) / len(test_returns), 3),
            })

    if not folds:
        return {"status": "NO_FOLDS_PRODUCED", "n_dates": len(dates)}

    avg_test = sum(f["test_ret"] for f in folds) / len(folds)
    return {
        "status": "OK",
        "n_folds": len(folds),
        "avg_test_ret": round(avg_test, 3),
        "fold_details": folds,
    }


def report():
    rows = _load_journal()
    measured = _measured_only(rows)
    print("=" * 70)
    print("BACKTEST HARNESS REPORT")
    print("=" * 70)
    print(f"Total journal rows: {len(rows)}")
    print(f"Measured rows: {len(measured)}")
    print()

    print("PER-COMPONENT EDGE (avg forward return by component score band):")
    print("-" * 70)
    edge = per_component_edge(rows)
    if edge:
        print(f"{'Component':<22} {'Weight':>7} {'Low':>10} {'Mid':>10} {'High':>10} {'Edge':>8}")
        for ck, v in sorted(edge.items(), key=lambda x: -(x[1].get("edge_pts") or -999)):
            edge_str = f"{v['edge_pts']:+.2f}pt" if v["edge_pts"] is not None else "n/a"
            low_str = f"{v['low_avg_pct']:+.2f}% (n={v['low_n']})" if v["low_avg_pct"] is not None else "n/a"
            mid_str = f"{v['mid_avg_pct']:+.2f}% (n={v['mid_n']})" if v["mid_avg_pct"] is not None else "n/a"
            high_str = f"{v['high_avg_pct']:+.2f}% (n={v['high_n']})" if v["high_avg_pct"] is not None else "n/a"
            print(f"  {ck:<20} {v['current_weight']:>6.2f} {low_str:>10} {mid_str:>10} {high_str:>10} {edge_str:>8}")
    print()

    print("WEIGHT SWEEP:")
    print("-" * 70)
    sweep = weight_sweep(rows, top_n=10)
    print(f"  Status: {sweep['status']}")
    if sweep["status"] == "OK":
        print(f"  Baseline (current weights) avg top-10 return: {sweep['baseline_avg_top_ret']:+.2f}%")
        print(f"  Best alternative weights avg top-10 return:   {sweep['best_avg_top_ret']:+.2f}%")
        print(f"  Edge over baseline: {sweep['delta_vs_baseline']:+.2f}%")
        if sweep.get("weight_changes"):
            print()
            print("  Suggested weight changes (>=0.02 abs delta):")
            for ck, ch in sweep["weight_changes"].items():
                if abs(ch["delta"]) >= 0.02:
                    print(f"    {ck:<22} {ch['from']:.2f} -> {ch['to']:.2f}  ({ch['delta']:+.2f})")
    else:
        print(f"  {sweep.get('message', '')}")
    print()

    print("WALK-FORWARD VALIDATION:")
    print("-" * 70)
    wf = walk_forward_validation(rows)
    print(f"  Status: {wf['status']}")
    if wf["status"] == "OK":
        print(f"  Folds: {wf['n_folds']}")
        print(f"  Avg out-of-sample top-10 return: {wf['avg_test_ret']:+.2f}%")
    else:
        print(f"  Need more dates / picks before walk-forward is meaningful.")


if __name__ == "__main__":
    report()

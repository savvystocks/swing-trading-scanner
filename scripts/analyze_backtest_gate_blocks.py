import os
import sys
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.alpaca_ohlcv import get_daily_bars_eodhd_format


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAPPERS_PATH = os.path.join(PROJECT_ROOT, "data", "results", "backtest_gappers_30d.json")
OUT_PATH = os.path.join(PROJECT_ROOT, "data", "results", "backtest_gate_blocks.json")


EXTENSION_THRESHOLDS = {
    "ret_5d": {"yellow": 5, "red": 12},
    "ret_30d": {"yellow": 15, "red": 25},
    "ret_90d": {"yellow": 40, "red": 75},
}


def compute_returns_pre_gap(bars, gap_date_str):
    gap_date = datetime.strptime(gap_date_str, "%Y-%m-%d").date()
    bars_before = []
    for b in bars:
        try:
            bd = datetime.strptime(b["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if bd < gap_date:
            bars_before.append(b)
    if len(bars_before) < 5:
        return None

    last_close = bars_before[-1]["close"]
    rets = {}
    for n_days, key in [(5, "ret_5d"), (15, "ret_15d"), (30, "ret_30d"), (60, "ret_60d")]:
        if len(bars_before) > n_days:
            ref = bars_before[-n_days - 1]["close"]
            if ref > 0:
                rets[key] = round((last_close - ref) / ref * 100, 1)
    rets["last_close_before_gap"] = last_close
    rets["bars_count"] = len(bars_before)
    return rets


def extension_status(rets):
    if not rets:
        return {"red": 0, "yellow": 0, "tier_cap": "A++"}
    red = 0
    yellow = 0
    flags = []
    for key in ("ret_5d", "ret_30d"):
        v = rets.get(key)
        if v is None:
            continue
        t = EXTENSION_THRESHOLDS[key]
        if v >= t["red"]:
            red += 1
            flags.append(f"{key}={v}%[RED]")
        elif v >= t["yellow"]:
            yellow += 1
            flags.append(f"{key}={v}%[yel]")
    if red >= 2:
        cap = "REJECT"
    elif red >= 1:
        cap = "A"
    elif yellow >= 3:
        cap = "A"
    elif yellow >= 2:
        cap = "A+"
    else:
        cap = "A++"
    return {"red": red, "yellow": yellow, "tier_cap": cap, "flags": flags}


def main():
    with open(GAPPERS_PATH) as f:
        data = json.load(f)
    gappers = data.get("gappers") or []
    print(f"Loaded {len(gappers)} gapper events\n")

    # Group by ticker (one ticker may have multiple gap days; keep largest)
    by_ticker = {}
    for g in gappers:
        t = g["ticker"]
        if t not in by_ticker or g["high_pct"] > by_ticker[t]["high_pct"]:
            by_ticker[t] = g
    unique_tickers = list(by_ticker.values())
    print(f"Unique tickers: {len(unique_tickers)} (deduplicated to single largest gap per ticker)\n")

    # For each gapper, fetch its prior 60-day OHLCV to compute pre-gap returns
    print(f"Analyzing pre-gap extension for {len(unique_tickers)} unique gappers...\n")

    enriched = []
    start = time.time()
    for i, g in enumerate(unique_tickers):
        if i > 0 and i % 100 == 0:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(unique_tickers)}]  rate={rate:.1f}/s")

        ticker = g["ticker"]
        gap_date = g["date"]
        gap_dt = datetime.strptime(gap_date, "%Y-%m-%d").date()
        from_d = (gap_dt - timedelta(days=120)).strftime("%Y-%m-%d")
        to_d = gap_date

        try:
            bars = get_daily_bars_eodhd_format(ticker, from_date=from_d, to_date=to_d)
            rets = compute_returns_pre_gap(bars, gap_date) if bars else None
            ext = extension_status(rets) if rets else None
            enriched.append({
                **g,
                "pre_gap_rets": rets,
                "extension": ext,
            })
        except Exception as e:
            enriched.append({**g, "error": str(e)[:80]})

    elapsed = time.time() - start
    print(f"\nAnalysis took {elapsed:.0f}s\n")

    # ==================================================================
    # Tabulate
    # ==================================================================
    print("=" * 70)
    print("GATE BLOCK ANALYSIS")
    print("=" * 70)

    # Extension filter blocks
    ext_caps = Counter(e.get("extension", {}).get("tier_cap") for e in enriched if e.get("extension"))
    print("\nExtension filter tier cap distribution (BEFORE the gap):")
    for cap in ("A++", "A+", "A", "REJECT"):
        n = ext_caps.get(cap, 0)
        pct = n / len(enriched) * 100 if enriched else 0
        print(f"  {cap:8s}: {n:5d}  ({pct:5.1f}%)")
    reject_count = ext_caps.get("REJECT", 0)
    a_count = ext_caps.get("A", 0)
    aplus_count = ext_caps.get("A+", 0)
    aplusplus_count = ext_caps.get("A++", 0)
    print(f"\n  --> REJECTED by extension alone: {reject_count} ({reject_count/len(enriched)*100:.1f}% of all gappers)")
    print(f"  --> Capped at A (not A++): {a_count + reject_count} ({(a_count+reject_count)/len(enriched)*100:.1f}%)")

    # Sector breakdown
    print("\nSector distribution of gappers:")
    sec_counts = Counter(g["sector"] for g in enriched)
    for sec, n in sec_counts.most_common(15):
        pct = n / len(enriched) * 100
        print(f"  {sec[:25]:25s}: {n:5d}  ({pct:5.1f}%)")

    # Index distribution (proxy for mcap bracket)
    print("\nIndex distribution (proxy for cap):")
    idx_counts = Counter(g["index"] for g in enriched)
    for idx, n in idx_counts.most_common():
        pct = n / len(enriched) * 100
        print(f"  {idx[:25]:25s}: {n:5d}  ({pct:5.1f}%)")

    # Day-of-week clustering
    print("\nDay-of-week of gaps:")
    dow_counts = Counter()
    for g in enriched:
        try:
            d = datetime.strptime(g["date"], "%Y-%m-%d").date()
            dow_counts[d.strftime("%A")] += 1
        except Exception:
            pass
    for dow in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        n = dow_counts.get(dow, 0)
        print(f"  {dow:10s}: {n}")

    # Magnitude tiers
    print("\nGap magnitude tiers:")
    mag_buckets = {
        "10-15%": [g for g in enriched if 10 <= g["high_pct"] < 15],
        "15-25%": [g for g in enriched if 15 <= g["high_pct"] < 25],
        "25-50%": [g for g in enriched if 25 <= g["high_pct"] < 50],
        "50%+":   [g for g in enriched if g["high_pct"] >= 50],
    }
    for bucket, items in mag_buckets.items():
        rej = sum(1 for it in items if (it.get("extension") or {}).get("tier_cap") == "REJECT")
        print(f"  {bucket}: {len(items)} gappers, {rej} ({rej/len(items)*100 if items else 0:.1f}%) would be REJECTED by extension")

    # Save full enriched data
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({
            "analysis_date": datetime.utcnow().isoformat(),
            "total_gapper_events": len(gappers),
            "unique_tickers": len(unique_tickers),
            "enriched": enriched,
            "extension_cap_distribution": dict(ext_caps),
            "sector_distribution": dict(sec_counts),
            "index_distribution": dict(idx_counts),
        }, f, indent=2, default=str)
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()

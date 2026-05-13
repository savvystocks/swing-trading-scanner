import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKTEST_PATH = os.path.join(PROJECT_ROOT, "data", "results", "backtest_gate_blocks.json")
COHORTS_PATH = os.path.join(PROJECT_ROOT, "data", "catalyst", "cohorts.json")

GAP_THRESHOLD_PCT = 25.0
MAX_COHORT_SIZE = 60


def main():
    if not os.path.exists(BACKTEST_PATH):
        print(f"Backtest file missing: {BACKTEST_PATH}")
        print("Run scripts/backtest_gappers_30d.py first")
        sys.exit(1)

    with open(BACKTEST_PATH) as f:
        data = json.load(f)
    enriched = data.get("enriched") or []

    sorted_gaps = sorted(enriched, key=lambda e: e.get("high_pct") or 0, reverse=True)
    seen = set()
    top_tickers = []
    for g in sorted_gaps:
        t = g.get("ticker")
        if not t or t in seen:
            continue
        if (g.get("high_pct") or 0) >= GAP_THRESHOLD_PCT:
            top_tickers.append(t)
            seen.add(t)
        if len(top_tickers) >= MAX_COHORT_SIZE:
            break

    with open(COHORTS_PATH) as f:
        cohorts = json.load(f)
    if "recent_gappers_30d" not in cohorts:
        print("recent_gappers_30d cohort not found in cohorts.json")
        sys.exit(1)

    old_count = len(cohorts["recent_gappers_30d"]["tickers"])
    cohorts["recent_gappers_30d"]["tickers"] = top_tickers
    new_count = len(top_tickers)

    with open(COHORTS_PATH, "w") as f:
        json.dump(cohorts, f, indent=2)

    print(f"recent_gappers_30d: {old_count} -> {new_count} tickers")
    print(f"Saved to {COHORTS_PATH}")


if __name__ == "__main__":
    main()

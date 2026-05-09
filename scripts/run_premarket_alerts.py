import os
import sys
import json
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.premarket_tracker import detect_premarket_spikes
from src.telegram import send_alert


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "data", "results")
COHORTS_PATH = os.path.join(PROJECT_ROOT, "data", "catalyst", "cohorts.json")


def load_latest_scan():
    pattern = os.path.join(RESULTS_DIR, "catalyst_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    files = [f for f in files if "_email" not in os.path.basename(f) and "_morning" not in os.path.basename(f)]
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


def build_watchlist_with_prev_close(scan, cohorts):
    candidates = scan.get("all_scored", []) if scan else []
    watchlist = []
    prev_close_lookup = {}

    cohort_tickers = set()
    for cohort_name in ("high_momentum_runners",):
        cohort_tickers.update(cohorts.get(cohort_name, {}).get("tickers", []))

    seen = set()

    for s in candidates[:120]:
        ticker = s.get("ticker")
        price = s.get("price")
        if not ticker or not price or ticker in seen:
            continue
        seen.add(ticker)
        watchlist.append({"ticker": ticker})
        prev_close_lookup[ticker.replace(".US", "")] = price

    by_ticker = {s.get("ticker"): s for s in candidates}
    for tk in cohort_tickers:
        if tk in seen:
            continue
        s = by_ticker.get(tk)
        if not s or not s.get("price"):
            continue
        seen.add(tk)
        watchlist.append({"ticker": tk})
        prev_close_lookup[tk.replace(".US", "")] = s.get("price")

    return watchlist, prev_close_lookup


def main():
    scan = load_latest_scan()
    if not scan:
        print("No scan available — skipping pre-market alerts")
        return

    try:
        with open(COHORTS_PATH) as f:
            cohorts = json.load(f)
    except Exception:
        cohorts = {}

    watchlist, prev_close_lookup = build_watchlist_with_prev_close(scan, cohorts)
    print(f"Pre-market scan: {len(watchlist)} tickers, {len(prev_close_lookup)} with prev close")

    spikes, err = detect_premarket_spikes(watchlist, prev_close_lookup, min_spike_pct=3.0)
    if err:
        print(f"  premarket detection error: {err}")
        return

    print(f"  detected {len(spikes)} pre-market spikes")
    if not spikes:
        return

    msg_lines = ["PRE-MARKET ALERTS:"]
    for spike in spikes[:15]:
        arrow = "+" if spike["direction"] == "UP" else ""
        msg_lines.append(
            f"{spike['ticker']}: {arrow}{spike['change_pct']:.1f}% "
            f"(${spike['premarket_price']:.2f} vs ${spike['prev_close']:.2f} close)"
        )
    msg = "\n".join(msg_lines)
    print(msg)
    send_alert(msg)


if __name__ == "__main__":
    main()

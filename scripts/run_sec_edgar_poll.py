import os
import sys
import json
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.sec_edgar_rss import poll_and_alert
from src.telegram import send_alert


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "data", "results")
COHORTS_PATH = os.path.join(PROJECT_ROOT, "data", "catalyst", "cohorts.json")


def build_watchlist():
    tickers = set()

    try:
        with open(COHORTS_PATH) as f:
            cohorts = json.load(f)
        for cohort_name, cohort_data in cohorts.items():
            if cohort_name in ("high_momentum_runners", "lazar_plays", "biotech_binary", "prediction_markets", "crypto_treasury"):
                tickers.update(cohort_data.get("tickers", []))
    except Exception as e:
        print(f"  cohort load failed: {e}")

    pattern = os.path.join(RESULTS_DIR, "catalyst_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    files = [f for f in files if "_email" not in os.path.basename(f) and "_morning" not in os.path.basename(f)]
    if files:
        try:
            with open(files[0]) as f:
                scan = json.load(f)
            candidates = scan.get("candidates", [])
            for c in candidates[:50]:
                tk = c.get("ticker")
                if tk:
                    tickers.add(tk)
        except Exception as e:
            print(f"  scan load failed: {e}")

    return list(tickers)


def main():
    watchlist = build_watchlist()
    print(f"SEC EDGAR poll: watching {len(watchlist)} tickers")

    def telegram_callback(msg):
        send_alert(msg)

    new_filings, sent = poll_and_alert(
        watchlist_tickers=watchlist,
        telegram_callback=telegram_callback,
        verbose=True,
    )
    print(f"Done: {len(new_filings)} new filings, {sent} alerts sent")


if __name__ == "__main__":
    main()

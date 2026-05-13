import os
import sys
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.alpaca_ohlcv import get_daily_bars_eodhd_format


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIVERSE_PATH = os.path.join(PROJECT_ROOT, "data", "universe", "universe.json")
OUT_PATH = os.path.join(PROJECT_ROOT, "data", "results", "backtest_gappers_30d.json")

GAP_THRESHOLD_PCT = 10.0
LOOKBACK_DAYS = 35


def find_gappers(bars, gap_pct):
    if not bars or len(bars) < 2:
        return []
    gaps = []
    for i in range(1, len(bars)):
        prev_close = bars[i - 1].get("close") or 0
        cur_close = bars[i].get("close") or 0
        cur_high = bars[i].get("high") or 0
        if prev_close <= 0:
            continue
        close_pct = (cur_close - prev_close) / prev_close * 100
        high_pct = (cur_high - prev_close) / prev_close * 100
        if close_pct >= gap_pct or high_pct >= gap_pct:
            gaps.append({
                "date": bars[i]["date"],
                "prev_close": prev_close,
                "open": bars[i].get("open"),
                "high": bars[i].get("high"),
                "close": cur_close,
                "close_pct": round(close_pct, 2),
                "high_pct": round(high_pct, 2),
                "volume": bars[i].get("volume"),
            })
    return gaps


def main():
    with open(UNIVERSE_PATH) as f:
        universe = json.load(f)

    us_tickers = [t for t in universe if t["ticker"].endswith(".US")]
    print(f"=== Backtest: 30-day gappers in {len(us_tickers)} US tickers ===\n")

    today = datetime.utcnow().date()
    from_date = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    print(f"Date range: {from_date} to {to_date}")
    print(f"Gap threshold: >={GAP_THRESHOLD_PCT}% intraday or close")
    print()

    gappers = []
    errors = 0
    start = time.time()

    for i, row in enumerate(us_tickers):
        if i > 0 and i % 200 == 0:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            est_remain = (len(us_tickers) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(us_tickers)}]  {len(gappers)} gappers found  rate={rate:.1f}/s  est_remain={est_remain:.0f}s")

        ticker_full = row["ticker"]
        ticker_short = ticker_full[:-3]
        try:
            bars = get_daily_bars_eodhd_format(ticker_short, from_date=from_date, to_date=to_date)
            if not bars:
                continue
            gaps = find_gappers(bars, GAP_THRESHOLD_PCT)
            if gaps:
                for g in gaps:
                    gappers.append({
                        "ticker": ticker_short,
                        "eodhd_ticker": ticker_full,
                        "name": row.get("name", ""),
                        "sector": row.get("sector", ""),
                        "index": row.get("index", ""),
                        **g,
                    })
        except Exception as e:
            errors += 1
            if errors < 5:
                print(f"  error on {ticker_short}: {type(e).__name__}: {str(e)[:60]}")

    elapsed = time.time() - start
    gappers.sort(key=lambda g: g.get("high_pct") or 0, reverse=True)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({
            "scan_date": today.isoformat(),
            "from_date": from_date,
            "to_date": to_date,
            "universe_size": len(us_tickers),
            "gappers_count": len(gappers),
            "gap_threshold_pct": GAP_THRESHOLD_PCT,
            "elapsed_seconds": round(elapsed, 1),
            "errors": errors,
            "gappers": gappers,
        }, f, indent=2, default=str)

    print(f"\n=== Done ===")
    print(f"Total elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"Universe scanned: {len(us_tickers)}")
    print(f"Errors: {errors}")
    print(f"Gappers found: {len(gappers)}")
    print(f"Output: {OUT_PATH}")
    print()
    print("Top 30 biggest moves (by intraday high vs prev close):")
    for g in gappers[:30]:
        print(f"  {g['date']}  {g['ticker']:6s}  high {g['high_pct']:+6.1f}%  close {g['close_pct']:+6.1f}%  {g['sector'][:18]:18s}  {g['name'][:30]}")


if __name__ == "__main__":
    main()

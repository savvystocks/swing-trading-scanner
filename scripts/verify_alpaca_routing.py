import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eodhd import EODHDClient


def main():
    print("=== Alpaca-OHLCV routing verification ===\n")

    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        print("FAIL: ALPACA_API_KEY or ALPACA_SECRET_KEY missing from env")
        sys.exit(1)
    if not os.environ.get("EODHD_API_KEY"):
        print("FAIL: EODHD_API_KEY missing from env")
        sys.exit(1)

    print(f"EODHD key: {os.environ['EODHD_API_KEY'][:8]}...{os.environ['EODHD_API_KEY'][-4:]}")
    print(f"Alpaca key: {os.environ['ALPACA_API_KEY'][:8]}...{os.environ['ALPACA_API_KEY'][-4:]}\n")

    client = EODHDClient()
    calls_before = client.calls_made

    print("Test 1: US tickers should route to Alpaca (no EODHD calls)")
    print("---")
    for tkr in ["AAPL.US", "NVDA.US", "MRVL.US", "SPY.US", "ALAB.US", "CRDO.US"]:
        bars = client.ohlcv(tkr, from_date="2026-05-01", to_date="2026-05-13")
        n = len(bars) if bars else 0
        last = bars[-1] if bars else None
        if last:
            print(f"  {tkr:10s} {n} bars   last close ${last['close']:.2f}   vol {last['volume']:,}")
        else:
            print(f"  {tkr:10s} FAIL (no data)")
    eodhd_calls_us = client.calls_made - calls_before
    print(f"  EODHD calls made: {eodhd_calls_us}  (expect 0 for all-Alpaca routing)")
    print()

    print("Test 2: Non-US tickers should fall back to EODHD")
    print("---")
    calls_before = client.calls_made
    for tkr in ["SHEL.LSE", "VUKE.LSE", "VIX.INDX"]:
        try:
            bars = client.ohlcv(tkr, from_date="2026-05-01", to_date="2026-05-13")
            n = len(bars) if bars else 0
            last = bars[-1] if bars else None
            if last:
                print(f"  {tkr:12s} {n} bars   last close {last['close']:.2f}")
            else:
                print(f"  {tkr:12s} FAIL (no data)")
        except Exception as e:
            print(f"  {tkr:12s} FAIL: {type(e).__name__}: {str(e)[:60]}")
    eodhd_calls_nonus = client.calls_made - calls_before
    print(f"  EODHD calls made: {eodhd_calls_nonus}  (expect 3+ for non-US fallback)")
    print()

    print("Test 3: Volume scaling sanity check")
    print("---")
    bars = client.ohlcv("AAPL.US", from_date="2026-05-12", to_date="2026-05-13")
    if bars and len(bars) > 0:
        last = bars[-1]
        vol = last["volume"]
        print(f"  AAPL.US vol (Alpaca, scaled 33x): {vol:,}")
        print(f"  Expected range: 40,000,000 - 80,000,000 (typical AAPL consolidated)")
        if 30_000_000 <= vol <= 100_000_000:
            print(f"  OK: scaled volume in plausible range")
        else:
            print(f"  WARN: volume {vol:,} outside expected range")
    print()

    print("=== Summary ===")
    print(f"Total EODHD calls during this test: {client.calls_made}")
    print(f"Quota impact: {client.calls_made}/100,000 monthly = {client.calls_made/100_000*100:.2f}%")
    if eodhd_calls_us == 0:
        print("OK: US tickers routed entirely through Alpaca (zero EODHD calls)")
    else:
        print(f"WARN: {eodhd_calls_us} EODHD calls leaked through for US tickers (Alpaca fallback triggered?)")


if __name__ == "__main__":
    main()

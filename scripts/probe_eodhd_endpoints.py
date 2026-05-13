import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.eodhd import EODHDClient

c = EODHDClient()
print(f"API key: {c.api_key[:10]}...{c.api_key[-4:]}")
print()

tests = [
    ("OHLCV (LSE, EODHD-only path)", lambda: c.ohlcv("VUKE.LSE", from_date="2026-05-01", to_date="2026-05-13")),
    ("Fundamentals (AAPL)", lambda: c.fundamentals("AAPL.US")),
    ("Earnings calendar", lambda: c.earnings_calendar("2026-05-12", "2026-05-14")),
    ("Economic events", lambda: c.economic_events("2026-05-12", "2026-05-14")),
    ("Insider transactions (AAPL)", lambda: c.insider_transactions("AAPL.US", limit=5)),
    ("News (AAPL)", lambda: c.news("AAPL.US", limit=2)),
    ("Exchange symbols", lambda: c.exchange_tickers("US")),
]

for name, fn in tests:
    try:
        result = fn()
        if result is None:
            status = "OK (returned None)"
        elif isinstance(result, list):
            status = f"OK (list, {len(result)} items)"
        elif isinstance(result, dict):
            status = f"OK (dict, {len(result)} keys)"
        else:
            status = f"OK ({type(result).__name__})"
        print(f"  {name:40} {status}")
    except Exception as e:
        msg = str(e)[:100]
        print(f"  {name:40} FAIL: {msg}")

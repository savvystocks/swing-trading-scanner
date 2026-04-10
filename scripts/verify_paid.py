import os
import json
import pathlib
import requests

API = os.environ["EODHD_API_KEY"]
BASE = "https://eodhd.com/api"
DUMP = pathlib.Path(__file__).parent / "verification_dumps"
DUMP.mkdir(exist_ok=True)

session = requests.Session()
results = []

def call(label, path, params=None, dump_name=None):
    p = {"api_token": API, "fmt": "json"}
    if params:
        p.update(params)
    try:
        r = session.get(f"{BASE}{path}", params=p, timeout=30)
        if r.status_code != 200:
            results.append((label, "FAIL", f"HTTP {r.status_code}: {r.text[:200]}", None))
            return None
        data = r.json()
        if dump_name:
            (DUMP / dump_name).write_text(json.dumps(data, indent=2, default=str))
        results.append((label, "PASS", describe(data), data))
        return data
    except Exception as e:
        results.append((label, "ERROR", str(e)[:200], None))
        return None

def describe(data):
    if isinstance(data, list):
        return f"list[{len(data)}]"
    if isinstance(data, dict):
        return f"dict, {len(data)} top-level keys: {list(data.keys())[:8]}"
    return str(data)[:100]

print("=" * 80)
print("EODHD PAID-TIER VERIFICATION SWEEP")
print("=" * 80)
print()

call("US OHLCV (AAPL 30d)", "/eod/AAPL.US", {"from": "2026-03-10"})
call("US Fundamentals (AAPL)", "/fundamentals/AAPL.US", None, "aapl_fundamentals.json")
call("US Fundamentals (GME - high SI test)", "/fundamentals/GME.US", None, "gme_fundamentals.json")
call("US Fundamentals (STRL - mid-cap test)", "/fundamentals/STRL.US", None, "strl_fundamentals.json")
call("LSE OHLCV (SHEL 30d)", "/eod/SHEL.LSE", {"from": "2026-03-10"})
call("LSE Fundamentals (SHEL - FTSE 100)", "/fundamentals/SHEL.LSE", None, "shel_fundamentals.json")
call("LSE Fundamentals (ULVR - FTSE 100)", "/fundamentals/ULVR.LSE", None, "ulvr_fundamentals.json")
call("LSE Fundamentals (AAL - FTSE 100)", "/fundamentals/AAL.LSE", None, "aal_fundamentals.json")
call("LSE Fundamentals (RMV - FTSE 250)", "/fundamentals/RMV.LSE", None, "rmv_fundamentals.json")
call("Insider Transactions (AAPL)", "/insider-transactions", {"code": "AAPL.US", "limit": 10}, "insider_aapl.json")
call("Options Chain (AAPL)", "/options/AAPL.US", {"from": "2026-04-10", "to": "2026-04-30"}, "options_aapl.json")
call("Earnings Calendar (next 10d)", "/calendar/earnings", {"from": "2026-04-10", "to": "2026-04-20"}, "earnings_calendar.json")
call("Economic Events (next 30d)", "/economic-events", {"from": "2026-04-10", "to": "2026-05-10", "limit": 30}, "econ_events.json")
call("News (AAPL)", "/news", {"s": "AAPL.US", "limit": 5}, "news_aapl.json")
call("Exchange Tickers (LSE)", "/exchange-symbol-list/LSE", None)
call("Exchange Tickers (US)", "/exchange-symbol-list/US", None)

print()
for label, status, summary, _ in results:
    flag = "OK  " if status == "PASS" else "FAIL"
    print(f"[{flag}] {label}")
    print(f"       {summary[:250]}")
passed = sum(1 for _, s, _, _ in results if s == "PASS")
print()
print("=" * 80)
print(f"RESULT: {passed}/{len(results)} passed")
print("=" * 80)

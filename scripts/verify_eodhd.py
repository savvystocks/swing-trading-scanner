import os
import json
import sys
import requests

API = os.environ["EODHD_API_KEY"]
BASE = "https://eodhd.com/api"
session = requests.Session()

results = []

def call(label, path, params=None, expected_fields=None):
    p = {"api_token": API, "fmt": "json"}
    if params:
        p.update(params)
    try:
        r = session.get(f"{BASE}{path}", params=p, timeout=30)
        status = r.status_code
        if status != 200:
            results.append((label, "FAIL", f"HTTP {status}: {r.text[:200]}"))
            return None
        data = r.json()
        summary = summarize(data, expected_fields)
        results.append((label, "PASS", summary))
        return data
    except Exception as e:
        results.append((label, "ERROR", str(e)[:200]))
        return None

def summarize(data, expected_fields):
    if isinstance(data, list):
        if not data:
            return "empty list"
        first = data[0]
        return f"list[{len(data)}], sample keys: {list(first.keys())[:8] if isinstance(first, dict) else first}"
    if isinstance(data, dict):
        found = {}
        if expected_fields:
            for f in expected_fields:
                parts = f.split(".")
                node = data
                ok = True
                for part in parts:
                    if isinstance(node, dict) and part in node:
                        node = node[part]
                    else:
                        ok = False
                        break
                found[f] = "present" if ok else "MISSING"
        return f"dict, top keys: {list(data.keys())[:8]}, fields: {found}"
    return str(data)[:200]

print("=" * 70)
print("EODHD 10-CALL VERIFICATION")
print("=" * 70)

call("1. US OHLCV (AAPL)", "/eod/AAPL.US", {"from": "2026-03-01"})
call("2. US fundamentals (AAPL)", "/fundamentals/AAPL.US", None, [
    "General.Code", "Highlights.EPSEstimateNextQuarter",
    "Earnings.Trend", "Earnings.History",
    "SharesStats.SharesShort", "SharesStats.ShortRatio",
    "AnalystRatings",
])
call("3. US insider transactions (AAPL)", "/insider-transactions", {"code": "AAPL.US", "limit": 5})
call("4. US options chain (AAPL)", "/options/AAPL.US", {"from": "2026-04-01", "to": "2026-04-15"})
call("5. LSE OHLCV (SHEL)", "/eod/SHEL.LSE", {"from": "2026-03-01"})
call("6. LSE fundamentals (SHEL)", "/fundamentals/SHEL.LSE", None, [
    "General.Code", "Highlights.EPSEstimateNextQuarter",
    "Earnings.Trend", "SharesStats.SharesShort",
    "AnalystRatings",
])
call("7. LSE fundamentals (ULVR)", "/fundamentals/ULVR.LSE", None, [
    "General.Code", "Highlights.EPSEstimateNextQuarter",
    "Earnings.Trend",
])
call("8. Economic events calendar", "/economic-events", {"from": "2026-04-10", "to": "2026-05-10", "limit": 20})
call("9. Earnings calendar", "/calendar/earnings", {"from": "2026-04-10", "to": "2026-04-20"})
call("10. Exchanges list", "/exchanges-list/", None)

print()
for label, status, summary in results:
    flag = "OK  " if status == "PASS" else "FAIL"
    print(f"[{flag}] {label}")
    print(f"       {summary[:300]}")
    print()

passed = sum(1 for _, s, _ in results if s == "PASS")
print("=" * 70)
print(f"RESULT: {passed}/{len(results)} passed")

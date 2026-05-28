"""Show this week's pick performance + ETOR specific live update."""
import os
import sys
import json
import glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta


c = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])


def get_live(tickers):
    try:
        q = c.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=list(tickers)))
        out = {}
        for t, info in q.items():
            bid = float(info.bid_price) if info.bid_price else 0
            ask = float(info.ask_price) if info.ask_price else 0
            mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else (bid or ask)
            out[t] = mid
        return out
    except Exception as e:
        print(f"  Live quote fetch failed: {e}")
        return {}


def get_close_on(ticker, target_date):
    """Get the close price on a specific date (uses ±3 day window)."""
    try:
        start = (target_date - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
        end = (target_date + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59Z")
        bars = c.get_stock_bars(StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start, end=end))
        if ticker not in bars.data:
            return None
        for b in bars.data[ticker]:
            if b.timestamp.date() == target_date:
                return float(b.close)
        if bars.data[ticker]:
            return float(bars.data[ticker][-1].close)
        return None
    except Exception:
        return None


print("=" * 80)
print("WEEKLY PERFORMANCE UPDATE (Mon 26 May - Thu 28 May 2026)")
print("=" * 80)

# Load Friday's picks (the ones that would have driven Monday's email)
scans = sorted(glob.glob("data/results/catalyst_2026-05-2[2-7].json"))
print(f"\nScan files this week: {len(scans)}")
for s in scans:
    print(f"  - {os.path.basename(s)}")

# === ETOR SPECIFIC ===
print()
print("=" * 80)
print("ETOR SPECIFIC (the trade you took)")
print("=" * 80)

# Find ETOR in each scan
etor_history = []
for scan_file in scans:
    with open(scan_file, encoding="utf-8") as f:
        scan = json.load(f)
    for tier in ("A++", "A+", "A"):
        for p in scan.get("aa_results", {}).get(tier, []):
            if p.get("ticker") == "ETOR":
                o = (p.get("_overall_score") or {}).get("score")
                conv = (p.get("_conviction") or {}).get("score")
                h = p.get("haiku_synthesis") or {}
                etor_history.append({
                    "date": os.path.basename(scan_file).replace("catalyst_", "").replace(".json", ""),
                    "price": p.get("price"),
                    "overall": o,
                    "conviction": conv,
                    "llm_verdict": h.get("verdict"),
                    "llm_conf": h.get("confidence_pct"),
                    "ret_5d": p.get("ret_5d"),
                })
                break

print(f"\nETOR appearance in scans this week:")
print(f"{'Date':<12} {'Price':>8} {'Overall':>8} {'Conv':>5} {'LLM':<6} {'Conf':>5} {'5d ret':>7}")
print("-" * 60)
for h in etor_history:
    price_s = f"${h['price']:>6.2f}" if h.get('price') is not None else "n/a    "
    ov = h.get('overall')
    cv = h.get('conviction')
    rd = h.get('ret_5d')
    print(f"{h['date']:<12} {price_s:>9} {ov if ov is not None else '-':>8} {cv if cv is not None else '-':>5} {(h.get('llm_verdict') or '--'):<6} {h.get('llm_conf') or 0:>4}% {(rd if rd is not None else 0):>6.1f}%")

# Live ETOR
live = get_live(["ETOR"])
if "ETOR" in live:
    etor_live = live["ETOR"]
    fri_close = etor_history[0]["price"] if etor_history else None
    print(f"\nETOR LIVE: ${etor_live:.2f}")
    if fri_close:
        change = (etor_live - fri_close) / fri_close * 100
        print(f"vs Friday 23 May scan close (${fri_close}): {change:+.2f}%")

# === FULL TAKE LIST PERFORMANCE ===
print()
print("=" * 80)
print("ALL TAKE/WATCH PICKS FROM FRIDAY 23 MAY SCAN vs current price")
print("=" * 80)

with open("data/results/catalyst_2026-05-23.json", encoding="utf-8") as f:
    friday_scan = json.load(f)

picks = []
for tier in ("A++", "A+", "A"):
    for p in friday_scan.get("aa_results", {}).get(tier, []):
        conv = (p.get("_conviction") or {}).get("score") or 0
        if conv >= 55:
            picks.append({
                "ticker": p.get("ticker"),
                "scan_price": p.get("price"),
                "conviction": conv,
            })

picks.sort(key=lambda x: -x["conviction"])
top10 = picks[:10]
tickers = [p["ticker"] for p in top10 if p["ticker"] and "." not in p["ticker"]]
live_prices = get_live(tickers)

print(f"\n{'Ticker':<7} {'Fri close':>10} {'Live now':>10} {'Change':>8} {'Conv':>5}")
print("-" * 50)
total_change = 0
n = 0
for p in top10:
    if p["ticker"] not in live_prices:
        continue
    live_p = live_prices[p["ticker"]]
    change = (live_p - p["scan_price"]) / p["scan_price"] * 100
    arrow = "↑" if change >= 0 else "↓"
    print(f"{p['ticker']:<7} ${p['scan_price']:>8.2f} ${live_p:>8.2f} {arrow}{abs(change):>6.2f}% {p['conviction']:>4.0f}")
    total_change += change
    n += 1
if n > 0:
    print("-" * 50)
    print(f"AVG change of top {n} picks: {total_change/n:+.2f}%")

# === Today's TAKE picks for context ===
print()
print("=" * 80)
print("THURSDAY 28 MAY (today's) TOP PICKS BY CONVICTION")
print("=" * 80)

with open("data/results/catalyst_2026-05-28.json", encoding="utf-8") as f:
    today_scan = json.load(f)

today_picks = []
for tier in ("A++", "A+", "A", "MACRO_PUT"):
    for p in today_scan.get("aa_results", {}).get(tier, []):
        conv = (p.get("_conviction") or {}).get("score") or 0
        bear = (p.get("_bear_conviction") or {}).get("score") or 0
        d = p.get("_direction") or {}
        today_picks.append({
            "ticker": p.get("ticker"),
            "tier": p.get("_aa_tier"),
            "price": p.get("price"),
            "conv": conv,
            "bear": bear,
            "side": d.get("side") or "CALL",
            "winner": d.get("winning_score") or max(conv, bear),
        })

today_picks.sort(key=lambda x: -x["winner"])
print(f"\nMacro regime today: {today_scan.get('macro', {}).get('macro_regime', {}).get('regime', '?')} ({today_scan.get('macro', {}).get('macro_regime', {}).get('score', '?')}/100)")
print()
print(f"{'Ticker':<8} {'Side':<8} {'Conv':>5} {'Bear':>5} {'Win':>5} {'Tier':<10}")
print("-" * 55)
for p in today_picks[:10]:
    print(f"{p['ticker']:<8} {p['side']:<8} {p['conv']:>5} {p['bear']:>5} {p['winner']:>5} {p['tier']:<10}")

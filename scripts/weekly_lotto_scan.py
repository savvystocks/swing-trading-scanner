import os
import subprocess
import sys
import json
from datetime import datetime, timedelta
import pandas as pd

def load(n):
    r = subprocess.run(
        ["powershell", "-Command", f'[Environment]::GetEnvironmentVariable("{n}","User")'],
        capture_output=True, text=True,
    )
    return (r.stdout or "").strip()

for k in ("EODHD_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
    if not os.environ.get(k):
        v = load(k)
        if v:
            os.environ[k] = v

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eodhd import EODHDClient
from src.indicators import compute_all
from src.pillars import (
    pillar_1_trend_following, pillar_4_statarb, gate_3_rvol, gate_6_liquidity,
)
from src.alpaca_options import get_options_chain, get_live_price
from src.iv_metrics import vol_rank

client = EODHDClient()

today = datetime.now()
week_end = today + timedelta(days=7)
print(f"Scanning earnings calendar {today:%Y-%m-%d} -> {week_end:%Y-%m-%d}")

cal = client.earnings_calendar(today.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
earnings = cal.get("earnings", []) if isinstance(cal, dict) else []
print(f"Total earnings events this week: {len(earnings)}")

us_earnings = [e for e in earnings if e.get("code","").endswith(".US")]
print(f"US earnings: {len(us_earnings)}")

universe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "universe", "universe.json")
with open(universe_path) as f:
    universe = json.load(f)
universe_codes = {t["ticker"] for t in universe}

in_universe = [e for e in us_earnings if e.get("code") in universe_codes]
print(f"In our universe: {len(in_universe)}")

def fetch_df(t):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")
    raw = client.ohlcv(t, from_date=start, to_date=end)
    if not raw:
        return None
    df = pd.DataFrame(raw)
    if df.empty: return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

df_spy = fetch_df("SPY.US")
spy_ind = compute_all(df_spy)

candidates = []
for i, e in enumerate(in_universe):
    tkr = e["code"]
    try:
        df = fetch_df(tkr)
        if df is None or len(df) < 200: continue
        ind = compute_all(df)
        last = ind.iloc[-1]

        p1 = pillar_1_trend_following(ind)
        if p1["verdict"] == "FAIL": continue
        p4 = pillar_4_statarb(ind, spy_ind)
        if p4["verdict"] == "FAIL": continue

        fund = client.fundamentals(tkr)
        g6 = gate_6_liquidity(fund, ind)
        mcap = g6.get("market_cap") or 0
        if g6["verdict"] == "FAIL": continue

        g3 = gate_3_rvol(ind)
        rvol = g3.get("rvol") or 0

        report_date = e.get("report_date")
        est = e.get("estimate")

        candidates.append({
            "ticker": tkr,
            "name": (e.get("name") or "")[:25],
            "report_date": report_date,
            "before_after": e.get("before_after_market"),
            "eps_est": est,
            "price": float(last["close"]),
            "mcap_b": round(mcap/1e9, 2),
            "rvol": round(rvol, 2),
            "pct_above_50": round((last["close"]/last["sma_50"]-1)*100, 1) if last["sma_50"] else None,
            "pct_above_200": round((last["close"]/last["sma_200"]-1)*100, 1) if last["sma_200"] else None,
            "atr_pct": round(last["atr_14"]/last["close"]*100, 1),
        })
    except Exception as ex:
        continue

candidates.sort(key=lambda c: (c["pct_above_50"] or 0, c["rvol"]), reverse=True)

print(f"\n=== EARNINGS-THIS-WEEK CANDIDATES (Tier 1 momentum + liquidity filter) ===")
print(f"Found {len(candidates)} candidates\n")
print(f"{'TICKER':10s} {'REPORT':11s} {'B/A':4s} {'NAME':25s} {'PRICE':>7s} {'MCAP':>6s} {'%50':>6s} {'%200':>6s} {'ATR%':>5s} {'RVOL':>5s}")
for c in candidates[:15]:
    print(f"{c['ticker']:10s} {c['report_date'] or '?':11s} {(c['before_after'] or '?'):4s} {c['name']:25s} ${c['price']:>6.2f} {c['mcap_b']:>5.1f}B {(c['pct_above_50'] or 0):>+5.1f}% {(c['pct_above_200'] or 0):>+5.1f}% {c['atr_pct']:>4.1f}% {c['rvol']:>4.2f}x")

print(f"\n=== TOP 3 WEEKLY OPTIONS (lotto: ATM/near-ATM calls) ===")
for c in candidates[:3]:
    tkr = c["ticker"]
    underlying = tkr.replace(".US","")
    live = get_live_price(underlying) or c["price"]
    print(f"\n-- {tkr} ({c['name']}) reports {c['report_date']} {c['before_after'] or ''} --")
    print(f"   Live: ${live:.2f} | ATR: {c['atr_pct']}% | %above 50d: {c['pct_above_50']}%")
    contract = get_options_chain(underlying, 'call', live)
    if contract:
        print(f"   Call ${contract['strike']:.0f} exp {contract['expiration']} ({contract['dte']}d) delta {contract['delta']}")
        print(f"     IV {contract.get('impliedVol',0)*100:.0f}%  mid ${contract['mid']:.2f}  spread {contract['spread_pct']}%")
        cost = contract['mid']*100
        breakeven = contract['strike'] + contract['mid']
        print(f"     Cost ${cost:.0f}/contract  breakeven ${breakeven:.2f} ({(breakeven/live-1)*100:+.1f}% move)")

with open("data/results/weekly_lotto.json","w") as f:
    json.dump(candidates, f, indent=2)

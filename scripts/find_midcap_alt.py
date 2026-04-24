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
    pillar_1_trend_following, pillar_2_volatility_breakout, pillar_3_can_slim,
    pillar_4_statarb, pillar_5_global_macro, pillar_6_erm,
    pillar_7_short_squeeze, gate_3_rvol, gate_4_catalyst, gate_6_liquidity, gate_7_earnings_blackout,
)
from src.alpaca_options import get_options_chain, get_live_price, get_iv_skew_and_uoa
from src.lane_b import run_all_lane_b, lane_b_signal_count
from src.iv_metrics import vol_rank, options_interpretation

client = EODHDClient()

universe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "universe", "universe.json")
with open(universe_path) as f:
    universe = json.load(f)

MID_CAP_LOW = 2_000_000_000
MID_CAP_HIGH = 10_000_000_000

sp400 = [t for t in universe if t.get("index") == "SP400"]
print(f"Testing {len(sp400)} S&P 400 MidCap tickers...")

def fetch_df(t):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")
    raw = client.ohlcv(t, from_date=start, to_date=end)
    if not raw:
        return None
    df = pd.DataFrame(raw)
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

df_spy = fetch_df("SPY.US")
spy_ind = compute_all(df_spy)
vix_df = fetch_df("VIX.INDX")

candidates = []
for i, t in enumerate(sp400):
    tkr = t["ticker"]
    try:
        df = fetch_df(tkr)
        if df is None or len(df) < 200:
            continue
        ind = compute_all(df)
        last = ind.iloc[-1]

        p1 = pillar_1_trend_following(ind)
        if p1["verdict"] == "FAIL":
            continue

        p4 = pillar_4_statarb(ind, spy_ind)
        if p4["verdict"] == "FAIL":
            continue

        fund = client.fundamentals(tkr)
        g6 = gate_6_liquidity(fund, ind)
        mcap = g6.get("market_cap") or 0
        if mcap < MID_CAP_LOW or mcap > MID_CAP_HIGH:
            continue
        if g6["verdict"] == "FAIL":
            continue

        g7 = gate_7_earnings_blackout(fund, ind)
        if g7["verdict"] == "FAIL":
            continue
        g4 = gate_4_catalyst(fund, [])
        if g4["verdict"] == "FAIL":
            continue

        p3 = pillar_3_can_slim(fund)
        p2 = pillar_2_volatility_breakout(ind)
        p5 = pillar_5_global_macro(vix_df) if vix_df is not None else {"verdict":"PASS"}
        p6 = pillar_6_erm(fund, True)
        insider = client.insider_transactions(tkr, limit=50) or []
        p7 = pillar_7_short_squeeze(fund, ind, insider, True)

        passes = sum(1 for p in [p1,p2,p3,p4,p5,p6,p7] if p["verdict"] in ("PASS","PASS_BONUS"))

        lb = run_all_lane_b(ind, fund, insider)
        lb_count = lane_b_signal_count(lb)

        candidates.append({
            "ticker": tkr,
            "name": t.get("name","")[:28],
            "sector": t.get("sector",""),
            "price": float(last["close"]),
            "mcap_b": round(mcap/1e9, 2),
            "pillars_passed": passes,
            "p3": p3["verdict"],
            "lane_b_count": lb_count,
            "pct_above_50": round((last["close"]/last["sma_50"]-1)*100, 1) if last["sma_50"] else None,
            "pct_above_200": round((last["close"]/last["sma_200"]-1)*100, 1) if last["sma_200"] else None,
            "rvol": round((gate_3_rvol(ind).get("rvol") or 0), 2),
            "next_earn_days": g7.get("days_until"),
        })
        if (i+1) % 25 == 0:
            print(f"  scanned {i+1}/{len(sp400)}, {len(candidates)} candidates so far")
    except Exception as e:
        continue

candidates.sort(key=lambda c: (c["pillars_passed"], c["lane_b_count"], -c["pct_above_50"] if c["pct_above_50"] else 0), reverse=True)

print(f"\n\n=== TOP 20 MID-CAP CANDIDATES ===")
print(f"{'TICKER':12s} {'NAME':28s} {'SECTOR':16s} {'PRICE':>7s} {'MCAP':>6s} {'P/7':>4s} {'LB':>3s} {'%50':>6s} {'%200':>6s} {'RVOL':>5s} {'EARN':>5s}")
for c in candidates[:20]:
    print(f"{c['ticker']:12s} {c['name']:28s} {c['sector'][:16]:16s} ${c['price']:>6.2f} {c['mcap_b']:>5.1f}B {c['pillars_passed']:>4d} {c['lane_b_count']:>3d} {(c['pct_above_50'] or 0):>+5.1f}% {(c['pct_above_200'] or 0):>+5.1f}% {c['rvol']:>4.2f}x {(c['next_earn_days'] or -1):>4d}d")

with open("data/results/midcap_scan.json", "w") as f:
    json.dump(candidates, f, indent=2)
print(f"\nSaved {len(candidates)} candidates to data/results/midcap_scan.json")

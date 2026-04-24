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
    pillar_4_statarb, pillar_6_erm, gate_3_rvol, gate_6_liquidity,
)
from src.alpaca_options import get_options_chain, get_live_price
from src.lane_b import run_all_lane_b, lane_b_signal_count
from src.iv_metrics import vol_rank

client = EODHDClient()

today = datetime.now()
window_start = today + timedelta(days=8)
window_end = today + timedelta(days=16)
print(f"Earnings window: {window_start:%Y-%m-%d} -> {window_end:%Y-%m-%d} (8-16 days, sweet spot)")

cal = client.earnings_calendar(window_start.strftime("%Y-%m-%d"), window_end.strftime("%Y-%m-%d"))
earnings = cal.get("earnings", []) if isinstance(cal, dict) else []
us_earnings = [e for e in earnings if e.get("code","").endswith(".US")]

universe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "universe", "universe.json")
with open(universe_path) as f:
    universe = json.load(f)
u_codes = {t["ticker"] for t in universe}
u_by = {t["ticker"]: t for t in universe}

in_u = [e for e in us_earnings if e.get("code") in u_codes]
print(f"US earnings in universe, 8-16 day window: {len(in_u)}")

def fetch_df(t):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")
    raw = client.ohlcv(t, from_date=start, to_date=end)
    if not raw: return None
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

df_spy = fetch_df("SPY.US")
spy_ind = compute_all(df_spy)

candidates = []
for i, e in enumerate(in_u):
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
        if g6["verdict"] == "FAIL": continue
        mcap = g6.get("market_cap") or 0
        if mcap < 1_000_000_000: continue

        p2 = pillar_2_volatility_breakout(ind)
        p3 = pillar_3_can_slim(fund)
        p6 = pillar_6_erm(fund, True)
        insider = client.insider_transactions(tkr, limit=50) or []
        lb = run_all_lane_b(ind, fund, insider)
        lb_count = lane_b_signal_count(lb)

        pillars = [p1,p2,p3,p4,p6]
        pillars_pass = sum(1 for p in pillars if p["verdict"] in ("PASS","PASS_BONUS"))

        close = float(last["close"])
        atr_pct = float(last["atr_14"])/close*100
        pct_50 = (close/last["sma_50"]-1)*100 if last["sma_50"] else 0
        pct_200 = (close/last["sma_200"]-1)*100 if last["sma_200"] else 0
        rs = (close/last["sma_50"]-1) - (spy_ind.iloc[-1]["close"]/spy_ind.iloc[-1]["sma_50"]-1)

        candidates.append({
            "ticker": tkr,
            "name": u_by.get(tkr,{}).get("name","")[:25],
            "sector": u_by.get(tkr,{}).get("sector",""),
            "report_date": e.get("report_date"),
            "before_after": e.get("before_after_market"),
            "price": close,
            "mcap_b": round(mcap/1e9, 2),
            "atr_pct": round(atr_pct, 1),
            "pct_50": round(pct_50, 1),
            "pct_200": round(pct_200, 1),
            "rs_vs_spy": round(rs*100, 1),
            "pillars_5": pillars_pass,
            "lb_count": lb_count,
            "p3_pass": p3["verdict"] in ("PASS","PASS_BONUS"),
        })
        if (i+1) % 25 == 0:
            print(f"  scanned {i+1}/{len(in_u)}, {len(candidates)} candidates")
    except Exception as ex:
        continue

def setup_score(c):
    s = 0
    s += c["pillars_5"] * 20
    s += c["lb_count"] * 10
    pct = c["pct_50"]
    if 5 <= pct <= 25:
        s += pct
    elif pct > 25:
        s += max(0, 25 - (pct - 25) * 1.5)
    s += c["rs_vs_spy"] * 0.3
    if c["p3_pass"]: s += 15
    if c["atr_pct"] > 8: s -= 15
    return s

candidates = [c for c in candidates if c["pct_50"] <= 40]

for c in candidates:
    c["setup_score"] = round(setup_score(c), 1)

candidates.sort(key=lambda c: c["setup_score"], reverse=True)

print(f"\n=== TOP 15 SETUPS (reports 8-16 days out) ===")
print(f"{'TICKER':10s} {'REPORT':11s} {'NAME':25s} {'SECTOR':14s} {'PRICE':>7s} {'MCAP':>6s} {'P/5':>4s} {'LB':>3s} {'%50':>6s} {'RS':>5s} {'ATR':>5s} {'SCORE':>6s}")
for c in candidates[:15]:
    print(f"{c['ticker']:10s} {c['report_date'] or '?':11s} {c['name']:25s} {c['sector'][:14]:14s} ${c['price']:>6.2f} {c['mcap_b']:>5.1f}B {c['pillars_5']:>4d} {c['lb_count']:>3d} {c['pct_50']:>+5.1f}% {c['rs_vs_spy']:>+4.1f} {c['atr_pct']:>4.1f}% {c['setup_score']:>6.1f}")

print(f"\n=== OPTIONS CHAIN + PROJECTED ROI FOR TOP 5 ===")
print("(Strategy: buy call today, exit day before earnings — capture IV ramp + momentum, skip IV crush)\n")

results = []
for c in candidates[:5]:
    tkr = c["ticker"]
    underlying = tkr.replace(".US","")
    live = get_live_price(underlying) or c["price"]
    print(f"\n-- {tkr} ({c['name']}) reports {c['report_date']} {c['before_after'] or ''} --")
    print(f"   Live: ${live:.2f}  ATR: {c['atr_pct']}%  %>50d: {c['pct_50']}%  Setup score: {c['setup_score']}")

    contract = get_options_chain(underlying, 'call', live)
    if not contract:
        print(f"   no contract passing filters")
        continue

    strike = contract['strike']
    prem = contract['mid']
    exp = contract['expiration']
    dte = contract['dte']
    iv_now = contract.get('impliedVol',0)*100
    delta = contract['delta']
    cost = prem*100

    move_5 = live * 1.05
    move_8 = live * 1.08
    move_10 = live * 1.10

    iv_ramp_mult = 1.25
    days_held = 8
    time_decay_frac = 1 - (days_held / dte) * 0.4

    def proj(new_price):
        intrinsic = max(0, new_price - strike)
        time_remaining = max(0, prem - max(0, live - strike)) * time_decay_frac * iv_ramp_mult
        val = intrinsic + time_remaining
        roi = (val - prem) / prem * 100
        return val, roi

    v5, r5 = proj(move_5)
    v8, r8 = proj(move_8)
    v10, r10 = proj(move_10)

    print(f"   Call ${strike:.0f} exp {exp} ({dte}d) delta {delta}  IV {iv_now:.0f}%  mid ${prem:.2f}  spread {contract['spread_pct']}%  cost ${cost:.0f}")
    print(f"   Projected option value if exited day-before-earnings with IV ramp +25%:")
    print(f"     +5% move ({live*1.05:>7.2f}): ${v5:.2f} ROI {r5:+.0f}%")
    print(f"     +8% move ({live*1.08:>7.2f}): ${v8:.2f} ROI {r8:+.0f}%")
    print(f"     +10% move ({live*1.10:>7.2f}): ${v10:.2f} ROI {r10:+.0f}%")

    results.append({**c, "contract": contract, "live": live,
                    "roi_at_5pct": round(r5,0), "roi_at_8pct": round(r8,0), "roi_at_10pct": round(r10,0)})

with open("data/results/asymmetric_trade_scan.json","w") as f:
    json.dump({"candidates": candidates[:30], "top_with_options": results}, f, indent=2, default=str)
print(f"\nSaved scan to data/results/asymmetric_trade_scan.json")

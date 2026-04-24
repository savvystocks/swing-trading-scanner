import os
import subprocess
import sys
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict
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
    pillar_4_statarb, pillar_6_erm, pillar_7_short_squeeze, gate_3_rvol,
    gate_6_liquidity,
)
from src.lane_b import run_all_lane_b, lane_b_signal_count

client = EODHDClient()

with open("data/results/50pct_movers_raw.json") as f:
    winners_raw = json.load(f)

winners = [w for w in winners_raw if 50 <= w["move_pct"] <= 300]
print(f"Raw winners: {len(winners_raw)}")
print(f"After filtering split artifacts (keep 50%-300%): {len(winners)}")

def fetch_df(t, start_date=None, end_date=None):
    end = end_date or datetime.now().strftime("%Y-%m-%d")
    start = start_date or (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    raw = client.ohlcv(t, from_date=start, to_date=end)
    if not raw: return None
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

df_spy_full = fetch_df("SPY.US")

analyzed = []
for i, w in enumerate(winners):
    tkr = w["ticker"]
    entry_date = pd.to_datetime(w["entry_date"])
    snapshot_date = entry_date - timedelta(days=7)
    try:
        df_full = fetch_df(tkr)
        if df_full is None or len(df_full) < 200:
            continue

        df_pre = df_full[df_full.index <= snapshot_date]
        if len(df_pre) < 200:
            df_pre = df_full[df_full.index <= entry_date]
            if len(df_pre) < 200:
                continue

        df_spy_pre = df_spy_full[df_spy_full.index <= snapshot_date]
        if len(df_spy_pre) < 200:
            df_spy_pre = df_spy_full[df_spy_full.index <= entry_date]

        ind_pre = compute_all(df_pre)
        spy_ind_pre = compute_all(df_spy_pre)
        last_pre = ind_pre.iloc[-1]

        fund = client.fundamentals(tkr) or {}
        hl = fund.get("Highlights",{}) or {}
        tech = fund.get("Technicals",{}) or {}
        shares = fund.get("SharesStats",{}) or {}

        p1 = pillar_1_trend_following(ind_pre)
        p2 = pillar_2_volatility_breakout(ind_pre)
        p3 = pillar_3_can_slim(fund)
        p4 = pillar_4_statarb(ind_pre, spy_ind_pre)
        p6 = pillar_6_erm(fund, True)
        insider_raw = client.insider_transactions(tkr, limit=50) or []
        insider = []
        for ti in insider_raw:
            ti2 = dict(ti)
            dstr = ti2.get("transactionDate")
            if dstr:
                try:
                    ts = pd.to_datetime(dstr)
                    if getattr(ts, "tzinfo", None) is not None:
                        ts = ts.tz_localize(None)
                    ti2["transactionDate"] = ts.strftime("%Y-%m-%d")
                except Exception:
                    pass
            insider.append(ti2)
        p7 = pillar_7_short_squeeze(fund, ind_pre, insider, True)
        g3 = gate_3_rvol(ind_pre)
        g6 = gate_6_liquidity(fund, ind_pre)

        lb = run_all_lane_b(ind_pre, fund, insider)
        lb_count = lane_b_signal_count(lb)

        def _td(s):
            try:
                return pd.to_datetime(s).tz_localize(None) if pd.to_datetime(s).tzinfo else pd.to_datetime(s)
            except Exception:
                return None
        pre_insider = []
        for ti in insider:
            dstr = ti.get('transactionDate')
            if not dstr: continue
            td = _td(dstr)
            if td is None: continue
            diff = (snapshot_date - td).days
            if 0 <= diff <= 90:
                pre_insider.append(ti)
        pre_buys = [t for t in pre_insider if (t.get('transactionCode') or '').startswith('P')]
        pre_sells = [t for t in pre_insider if (t.get('transactionCode') or '').startswith('S')]

        earn_hist = fund.get("Earnings",{}).get("History",{}) or {}
        earn_dates = sorted(earn_hist.items(), reverse=True)
        near_earnings = None
        for d, v in earn_dates:
            rd = v.get("reportDate")
            if not rd: continue
            rd_dt = _td(rd)
            if rd_dt is None: continue
            diff = (rd_dt - entry_date).days
            if -10 <= diff <= 10:
                near_earnings = {"date": rd, "days_from_entry": diff, "actual": v.get("epsActual"), "estimate": v.get("epsEstimate"), "surprise_pct": v.get("surprisePercent")}
                break

        close_pre = float(last_pre["close"])
        sma_50 = last_pre.get("sma_50")
        sma_200 = last_pre.get("sma_200")
        atr_14 = last_pre.get("atr_14")
        rsi_14 = last_pre.get("rsi_14")

        hi_52 = float(df_pre["high"].tail(252).max()) if len(df_pre) >= 252 else None
        lo_52 = float(df_pre["low"].tail(252).min()) if len(df_pre) >= 252 else None

        try:
            news = client.news(tkr, limit=10) or []
        except Exception:
            news = []
        move_start = entry_date - timedelta(days=3)
        move_end = _td(w["peak_date"]) + timedelta(days=3) if _td(w["peak_date"]) is not None else entry_date + timedelta(days=40)
        news_during = []
        for n in news:
            nd = n.get("date")
            if not nd: continue
            nd_dt = _td(str(nd).split()[0] if " " in str(nd) else nd)
            if nd_dt is None: continue
            if move_start <= nd_dt <= move_end:
                news_during.append({"date": nd, "title": n.get("title","")[:100]})

        rec = {
            "ticker": tkr,
            "name": w["name"],
            "sector": w["sector"],
            "industry": w["industry"],
            "index": w["index"],
            "move_pct": w["move_pct"],
            "days_to_peak": w["days_to_peak"],
            "entry_date": w["entry_date"],
            "entry_price": w["entry_price"],
            "peak_price": w["peak_price"],
            "current_price": w["current_price"],
            "pre_move_snapshot": {
                "close": close_pre,
                "pct_above_50d": round((close_pre/sma_50-1)*100, 1) if sma_50 else None,
                "pct_above_200d": round((close_pre/sma_200-1)*100, 1) if sma_200 else None,
                "atr_pct": round(atr_14/close_pre*100, 1) if atr_14 else None,
                "rsi_14": round(rsi_14, 1) if rsi_14 else None,
                "pct_from_52w_high": round((close_pre/hi_52-1)*100, 1) if hi_52 else None,
                "pct_above_52w_low": round((close_pre/lo_52-1)*100, 1) if lo_52 else None,
            },
            "pillars_pre": {
                "p1_trend": p1["verdict"], "p1_summary": p1.get("summary",""),
                "p2_vol": p2["verdict"], "p2_summary": p2.get("summary",""),
                "p3_canslim": p3["verdict"], "p3_summary": p3.get("summary",""),
                "p4_rs": p4["verdict"], "p4_summary": p4.get("summary",""),
                "p6_erm": p6["verdict"], "p6_summary": p6.get("summary",""),
                "p7_squeeze": p7["verdict"], "p7_summary": p7.get("summary",""),
            },
            "gates_pre": {
                "g3_rvol": g3["verdict"], "g3_summary": g3.get("summary",""),
                "g6_liq": g6["verdict"], "g6_summary": g6.get("summary",""),
            },
            "lane_b_pre": {k: {"fired": v.get("fired", False), "summary": v.get("summary","")} for k,v in lb.items()},
            "lane_b_count_pre": lb_count,
            "insider_pre_90d": {"buys": len(pre_buys), "sells": len(pre_sells)},
            "near_earnings": near_earnings,
            "fundamentals": {
                "market_cap_b": round((hl.get("MarketCapitalization") or 0)/1e9, 2),
                "rev_qoq_yoy_pct": round((hl.get("QuarterlyRevenueGrowthYOY") or 0)*100, 1),
                "eps_qoq_yoy_pct": round((hl.get("QuarterlyEarningsGrowthYOY") or 0)*100, 1),
                "profit_margin_pct": round((hl.get("ProfitMargin") or 0)*100, 1),
                "short_pct_float": tech.get("ShortPercentFloat"),
                "shares_float": shares.get("SharesFloat"),
                "pct_insiders": shares.get("PercentInsiders"),
                "pct_institutions": shares.get("PercentInstitutions"),
                "forward_pe": hl.get("ForwardPE"),
                "peg": hl.get("PEGRatio"),
            },
            "news_during": news_during[:5],
        }
        analyzed.append(rec)
        if (i+1) % 20 == 0:
            print(f"  analyzed {i+1}/{len(winners)}")
    except Exception as ex:
        print(f"  err {tkr}: {type(ex).__name__}: {ex}")
        continue

with open("data/results/50pct_movers_analyzed.json","w") as f:
    json.dump(analyzed, f, indent=2, default=str)

print(f"\nAnalyzed {len(analyzed)} winners with full pre-move snapshots")

print("\n" + "="*70)
print("PATTERN ANALYSIS — what was common BEFORE the 50% moves")
print("="*70)

sector_counter = Counter(a["sector"] for a in analyzed if a["sector"])
print("\nSECTOR DISTRIBUTION:")
for s, c in sector_counter.most_common():
    print(f"  {s or '(none)':25s}  {c:3d}  ({c*100/len(analyzed):.1f}%)")

mcap_buckets = {"Nano (<300M)":0, "Micro ($300M-$2B)":0, "Small ($2B-$10B)":0, "Mid ($10B-$50B)":0, "Large (>$50B)":0}
for a in analyzed:
    mc = a["fundamentals"]["market_cap_b"]
    if mc < 0.3: mcap_buckets["Nano (<300M)"] += 1
    elif mc < 2: mcap_buckets["Micro ($300M-$2B)"] += 1
    elif mc < 10: mcap_buckets["Small ($2B-$10B)"] += 1
    elif mc < 50: mcap_buckets["Mid ($10B-$50B)"] += 1
    else: mcap_buckets["Large (>$50B)"] += 1
print("\nMARKET CAP DISTRIBUTION:")
for b, c in mcap_buckets.items():
    if c > 0:
        print(f"  {b:25s}  {c:3d}  ({c*100/len(analyzed):.1f}%)")

print("\nPILLAR PASS RATES (pre-move):")
for p, label in [("p1_trend","P1 Trend Template"),("p2_vol","P2 Vol Squeeze"),("p3_canslim","P3 CAN-SLIM"),("p4_rs","P4 RS vs SPY"),("p6_erm","P6 Earnings Revision"),("p7_squeeze","P7 Short Squeeze")]:
    passes = sum(1 for a in analyzed if a["pillars_pre"][p] in ("PASS","PASS_BONUS"))
    print(f"  {label:25s}  {passes:3d}/{len(analyzed)}  ({passes*100/len(analyzed):.1f}%)")

print("\nLANE B SIGNAL FIRE RATES (pre-move):")
lb_fires = defaultdict(int)
for a in analyzed:
    for k, v in a["lane_b_pre"].items():
        if v["fired"]:
            lb_fires[k] += 1
for k, c in sorted(lb_fires.items(), key=lambda x: -x[1]):
    print(f"  {k:25s}  {c:3d}  ({c*100/len(analyzed):.1f}%)")

lb_count_dist = Counter(a["lane_b_count_pre"] for a in analyzed)
print("\nLANE B SIGNAL COUNT DISTRIBUTION (pre-move):")
for n, c in sorted(lb_count_dist.items()):
    print(f"  {n} signals: {c} ({c*100/len(analyzed):.1f}%)")

earn_triggered = sum(1 for a in analyzed if a["near_earnings"])
print(f"\nEARNINGS-TRIGGERED MOVES (earnings within +/-10d of entry): {earn_triggered}/{len(analyzed)} ({earn_triggered*100/len(analyzed):.1f}%)")

print("\nPRE-MOVE TECHNICAL DISTRIBUTION:")
pct50s = [a["pre_move_snapshot"]["pct_above_50d"] for a in analyzed if a["pre_move_snapshot"]["pct_above_50d"] is not None]
pct200s = [a["pre_move_snapshot"]["pct_above_200d"] for a in analyzed if a["pre_move_snapshot"]["pct_above_200d"] is not None]
atrs = [a["pre_move_snapshot"]["atr_pct"] for a in analyzed if a["pre_move_snapshot"]["atr_pct"] is not None]
rsis = [a["pre_move_snapshot"]["rsi_14"] for a in analyzed if a["pre_move_snapshot"]["rsi_14"] is not None]
p52hs = [a["pre_move_snapshot"]["pct_from_52w_high"] for a in analyzed if a["pre_move_snapshot"]["pct_from_52w_high"] is not None]
def stat(name, values):
    if not values:
        print(f"  {name}: no data"); return
    s = pd.Series(values)
    print(f"  {name:25s}  median {s.median():+.1f}  mean {s.mean():+.1f}  25%/75% {s.quantile(0.25):+.1f}/{s.quantile(0.75):+.1f}")
stat("% above 50d MA", pct50s)
stat("% above 200d MA", pct200s)
stat("ATR% of price", atrs)
stat("RSI(14)", rsis)
stat("% from 52w high", p52hs)

short_floats = [float(a["fundamentals"]["short_pct_float"]) for a in analyzed if a["fundamentals"]["short_pct_float"] not in (None,"")]
print(f"\nSHORT INTEREST (where available, n={len(short_floats)}):")
if short_floats:
    s = pd.Series(short_floats)
    print(f"  median {s.median():.1f}%  >10%: {sum(1 for x in short_floats if x>10)}  >20%: {sum(1 for x in short_floats if x>20)}")

rev_growth = [a["fundamentals"]["rev_qoq_yoy_pct"] for a in analyzed if a["fundamentals"]["rev_qoq_yoy_pct"] is not None]
eps_growth = [a["fundamentals"]["eps_qoq_yoy_pct"] for a in analyzed if a["fundamentals"]["eps_qoq_yoy_pct"] is not None]
print("\nFUNDAMENTALS:")
if rev_growth: stat("Rev YoY %", rev_growth)
if eps_growth: stat("EPS YoY %", eps_growth)

insider_buyers = sum(1 for a in analyzed if a["insider_pre_90d"]["buys"] > 0)
insider_cluster = sum(1 for a in analyzed if a["insider_pre_90d"]["buys"] >= 3)
print(f"\nINSIDER ACTIVITY (90d pre-move):")
print(f"  Any buys: {insider_buyers}/{len(analyzed)} ({insider_buyers*100/len(analyzed):.1f}%)")
print(f"  Cluster (3+ buys): {insider_cluster}/{len(analyzed)} ({insider_cluster*100/len(analyzed):.1f}%)")

print("\nDONE. Full analyzed data in data/results/50pct_movers_analyzed.json")

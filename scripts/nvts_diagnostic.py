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
from src.lane_b import run_all_lane_b
from src.iv_metrics import vol_rank, options_interpretation

client = EODHDClient()
TICKER = "NVTS.US"

def fetch_df(t):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    raw = client.ohlcv(t, from_date=start, to_date=end)
    if not raw:
        return None
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

print("="*60)
print(f"NVTS FULL DIAGNOSTIC — {datetime.now():%Y-%m-%d %H:%M}")
print("="*60)

fund = client.fundamentals(TICKER)
df = fetch_df(TICKER)
df_spy = fetch_df("SPY.US")
df_ind = compute_all(df)
df_spy_ind = compute_all(df_spy)

last = df_ind.iloc[-1]
close = last["close"]
print(f"\nPRICE: ${close:.2f}")
print(f"52w high: ${df['high'].rolling(252).max().iloc[-1]:.2f} / low: ${df['low'].rolling(252).min().iloc[-1]:.2f}")
print(f"14d ATR: ${last['atr_14']:.2f} ({last['atr_14']/close*100:.1f}% of price)")
print(f"50d MA: ${last['sma_50']:.2f}  ({(close/last['sma_50']-1)*100:+.1f}% from price)")
print(f"200d MA: ${last['sma_200']:.2f}  ({(close/last['sma_200']-1)*100:+.1f}% from price)")

hl = fund.get("Highlights", {})
tech = fund.get("Technicals", {})
shares = fund.get("SharesStats", {})

print("\n--- SHORT SQUEEZE DATA ---")
print(f"Short % of float: {tech.get('ShortPercentFloat')}")
print(f"Shares short: {shares.get('SharesShort')}")
print(f"Shares short prior month: {shares.get('SharesShortPriorMonth')}")
print(f"Short ratio (days to cover): {shares.get('ShortRatio')}")
print(f"Float: {shares.get('PercentInsiders')}% insiders, {shares.get('PercentInstitutions')}% instit")
print(f"Float shares: {shares.get('SharesFloat')}")

print("\n--- PILLARS ---")
p1 = pillar_1_trend_following(df_ind)
print(f"P1 Trend: {p1['verdict']} — {p1.get('summary','')}")
p2 = pillar_2_volatility_breakout(df_ind)
print(f"P2 Vol: {p2['verdict']} — {p2.get('summary','')}")
p3 = pillar_3_can_slim(fund)
print(f"P3 CAN-SLIM: {p3['verdict']} — {p3.get('summary','')}")
p4 = pillar_4_statarb(df_ind, df_spy_ind)
print(f"P4 RS: {p4['verdict']} — {p4.get('summary','')}")
try:
    vix_df = fetch_df('VIX.INDX')
    p5 = pillar_5_global_macro(vix_df)
    print(f"P5 Macro: {p5['verdict']} — {p5.get('summary','')}")
except Exception as e:
    print(f"P5 Macro: fetch error {e}")
p6 = pillar_6_erm(fund, True)
print(f"P6 ERM: {p6['verdict']} — {p6.get('summary','')}")
insider_txns_early = client.insider_transactions(TICKER, limit=50) or []
p7 = pillar_7_short_squeeze(fund, df_ind, insider_txns_early, True)
print(f"P7 Short Squeeze: {p7['verdict']} — {p7.get('summary','')}")

print("\n--- GATES ---")
g3 = gate_3_rvol(df_ind)
print(f"G3 RVOL: {g3['verdict']} — RVOL {g3.get('rvol', 0):.2f}x")
g4 = gate_4_catalyst(fund, [])
print(f"G4 Catalyst: {g4['verdict']} — Tier {g4.get('tier','?')}")
g6 = gate_6_liquidity(fund, df_ind)
print(f"G6 Liquidity: {g6['verdict']} — mcap ${(g6.get('market_cap') or 0)/1e9:.2f}B, $vol ${g6.get('dollar_volume_20d', 0)/1e6:.2f}M")
g7 = gate_7_earnings_blackout(fund, df_ind)
print(f"G7 Earnings: {g7['verdict']} — {g7.get('next_earnings','?')} ({g7.get('days_until','?')} days)")

insider = client.insider_transactions(TICKER, limit=50) or []
print(f"\nINSIDER TXNS (last 50): {len(insider)}")
recent = [i for i in insider if i.get('transactionDate') and (datetime.now() - datetime.strptime(i['transactionDate'], '%Y-%m-%d')).days <= 90]
buys = [i for i in recent if (i.get('transactionCode') or '').startswith('P')]
sells = [i for i in recent if (i.get('transactionCode') or '').startswith('S')]
print(f"  Last 90d: {len(buys)} buys / {len(sells)} sells")

lane_b = run_all_lane_b(df_ind, fund, insider)
print(f"\n--- LANE B SIGNALS ---")
for k, v in lane_b.items():
    fired = v.get('fired', False)
    print(f"  {k}: {'FIRED' if fired else 'no'}", v.get('summary', '') if fired else '')

print("\n--- OPTIONS ---")
live = get_live_price('NVTS') or close
print(f"Alpaca live: ${live:.2f}")
vr = vol_rank(df_ind)
print(f"Realized vol rank: {vr.get('vol_rank_pct')}% ({options_interpretation(vr.get('vol_rank_pct'))})")
print(f"  current rv: {vr.get('current_realized_vol')}%, 52w range: {vr.get('52w_low_vol')}%-{vr.get('52w_high_vol')}%")
skew = get_iv_skew_and_uoa('NVTS', live)
if skew:
    print(f"IV skew: call {skew['avg_call_iv_pct']}%, put {skew['avg_put_iv_pct']}%, skew {skew['skew_pct']} ({skew['skew_bias']})")
contract = get_options_chain('NVTS', 'call', live)
if contract:
    print(f"Best call: ${contract['strike']:.0f} exp {contract['expiration']} ({contract['dte']}d)")
    print(f"  Delta {contract['delta']}, IV {contract.get('impliedVol',0)*100:.1f}%, mid ${contract['mid']:.2f}, spread {contract['spread_pct']}%")

import os
import subprocess
import sys
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
from src.indicators import compute_all, to_dataframe
from src.pillars import (
    pillar_1_trend_following, pillar_2_volatility_breakout, pillar_3_can_slim,
    pillar_4_statarb, pillar_5_global_macro, pillar_6_erm, pillar_7_short_squeeze,
    gate_3_rvol, gate_4_catalyst, gate_6_liquidity, gate_7_earnings_blackout,
)
from src.lane_b import run_all_lane_b
from src.scoring import score_candidate, build_trade_ticket
from src.options_hunter import options_hunter_score

client = EODHDClient()

TICKER = "CMI.US"
end = datetime.now().strftime("%Y-%m-%d")
start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")

print(f"Fetching {TICKER}...")
raw = client.ohlcv(TICKER, from_date=start, to_date=end)
df = to_dataframe(raw)
ind = compute_all(df)

spy_raw = client.ohlcv("SPY.US", from_date=start, to_date=end)
spy_ind = compute_all(to_dataframe(spy_raw))

vix_raw = client.ohlcv("VIX.INDX", from_date=start, to_date=end)
vix_df = to_dataframe(vix_raw) if vix_raw else None
vix_p = pillar_5_global_macro(vix_df)

fund = client.fundamentals(TICKER)

p1 = pillar_1_trend_following(ind)
p2 = pillar_2_volatility_breakout(ind)
p3 = pillar_3_can_slim(fund)
p4 = pillar_4_statarb(ind, spy_ind)
p6 = pillar_6_erm(fund, True)
insider = client.insider_transactions(TICKER, limit=20)
p7 = pillar_7_short_squeeze(fund, ind, insider, True)

g3 = gate_3_rvol(ind)
news = client.news(TICKER, limit=20)
g4 = gate_4_catalyst(fund, news)
g6 = gate_6_liquidity(fund, ind)
g7 = gate_7_earnings_blackout(fund, ind)

pillars = {"pillar_1": p1, "pillar_2": p2, "pillar_3": p3, "pillar_4": p4,
           "pillar_5": vix_p, "pillar_6": p6, "pillar_7": p7}
gates = {"gate_3": g3, "gate_4": g4, "gate_6": g6, "gate_7": g7,
         "gate_5_modifier": {"direction": "neutral"}}

tier_info = score_candidate(pillars, gates, True)
general = fund.get("General", {})
price = float(ind["close"].iloc[-1])
ticket = build_trade_ticket(
    TICKER, general.get("Name", ""), price, tier_info, pillars, gates,
    vix_p.get("regime", "unknown"),
    sector=general.get("Sector", ""), industry=general.get("Industry", ""),
)

lane_b = run_all_lane_b(ind, fund, insider)
ticket["lane_b"] = lane_b

hunter = options_hunter_score(ticket, pillars, gates, ind, fund)

print(f"\n{'='*60}\nCMI — Current Hunter Scorecard\n{'='*60}")
print(f"Price: ${price:.2f}   Mcap: ${(g6.get('market_cap') or 0)/1e9:.1f}B   Sector: {general.get('Sector')}")
print(f"Tier: T{tier_info['tier']}  ({tier_info['pillars_passed']}/{tier_info['applicable_pillars']} pillars)")
print(f"\nPillars:")
print(f"  P1 Trend:       {p1['verdict']:14s}  ({p1['trend_template_passed']}/7 template, stage {p1['stage']})")
print(f"  P2 Vol Sq:      {p2['verdict']:14s}  squeeze pct {p2.get('squeeze_percentile', 0):.0f}")
print(f"  P3 CAN-SLIM:    {p3['verdict']:14s}")
print(f"  P4 RS vs SPY:   {p4['verdict']:14s}  RS {p4.get('rs_score', 0):+.2f}%")
print(f"  P6 Revisions:   {p6['verdict']:14s}  beats={p6.get('consecutive_beats',0)}, up30d={p6.get('eps_up_30d',0)}")
print(f"  P7 Short Sq:    {p7['verdict']:14s}  SI {p7.get('short_percent_float', 0):.1f}%")
print(f"\nGates:")
print(f"  G3 RVOL:        {g3['verdict']}   rvol {g3.get('rvol') or 0:.2f}x")
print(f"  G4 Catalyst:    {g4['verdict']}   tier {g4.get('tier')}")
print(f"  G6 Liquidity:   {g6['verdict']}   mcap ${(g6.get('market_cap') or 0)/1e9:.1f}B")
print(f"  G7 Earnings:    {g7['verdict']}   next {g7.get('next_earnings')} ({g7.get('days_until')} days)")

print(f"\nLane B signals:")
for key in ("pocket_pivot", "base_quality", "insider_cluster", "revenue_acceleration", "earnings_turn"):
    s = lane_b.get(key, {})
    print(f"  {key:22s}: {'FIRED' if s.get('fired') else '----'}   {s.get('summary','')[:60]}")

print(f"\n{'='*60}\nHUNTER VERDICT\n{'='*60}")
print(f"Score:       {hunter['score']}/100")
print(f"Qualified:   {hunter['qualified']} (threshold: 45)")
print(f"Move ETA:    {hunter['eta_label']}")
print(f"Reasons:     {'; '.join(hunter.get('reasons', []))}")
print(f"Earnings in: {hunter.get('earnings_days')} days")
print(f"Pct from 52wH: {hunter.get('pct_from_high')}%")
print(f"Sector tilt: {hunter.get('sector_tilt')}")
print(f"Lane B count: {hunter.get('lane_b_count')}")
if hunter.get('disqualified_reason'):
    print(f"Disqualified: {hunter['disqualified_reason']}")

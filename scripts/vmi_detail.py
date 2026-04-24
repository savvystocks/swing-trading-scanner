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
from src.indicators import compute_all
from src.pillars import (
    pillar_1_trend_following, pillar_2_volatility_breakout, pillar_3_can_slim,
    pillar_4_statarb, pillar_5_global_macro, pillar_6_erm,
    pillar_7_short_squeeze, gate_3_rvol, gate_4_catalyst, gate_6_liquidity, gate_7_earnings_blackout,
)
from src.alpaca_options import get_options_chain, get_live_price, get_iv_skew_and_uoa
from src.lane_b import run_all_lane_b
from src.iv_metrics import vol_rank, options_interpretation
from src.options_suggest import suggest_options_trade

client = EODHDClient()

for TICKER in ("VMI.US", "HXL.US"):
    underlying = TICKER.replace(".US","")
    print("="*60)
    print(f"{TICKER}")
    print("="*60)
    fund = client.fundamentals(TICKER)
    gen = fund.get("General", {})
    hl = fund.get("Highlights", {})
    tech = fund.get("Technicals", {})

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    raw = client.ohlcv(TICKER, from_date=start, to_date=end)
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    ind = compute_all(df)
    last = ind.iloc[-1]

    print(f"Name: {gen.get('Name')}")
    print(f"Sector: {gen.get('Sector')} / {gen.get('Industry')}")
    print(f"Description: {(gen.get('Description') or '')[:300]}")
    print()
    print(f"Price: ${last['close']:.2f}")
    print(f"52w range: ${df['low'].rolling(252).min().iloc[-1]:.2f} - ${df['high'].rolling(252).max().iloc[-1]:.2f}")
    print(f"14d ATR: ${last['atr_14']:.2f} ({last['atr_14']/last['close']*100:.1f}%)")
    print(f"50d MA: ${last['sma_50']:.2f} ({(last['close']/last['sma_50']-1)*100:+.1f}% above)")
    print(f"200d MA: ${last['sma_200']:.2f} ({(last['close']/last['sma_200']-1)*100:+.1f}% above)")
    print(f"RSI(14): {last['rsi_14']:.1f}")
    print(f"Beta: {tech.get('Beta')}")
    print()
    print("--- FUNDAMENTALS ---")
    print(f"Market cap: ${(hl.get('MarketCapitalization') or 0)/1e9:.2f}B")
    print(f"Rev ttm: ${(hl.get('RevenueTTM') or 0)/1e9:.2f}B")
    print(f"Rev QoQ YoY: {(hl.get('QuarterlyRevenueGrowthYOY') or 0)*100:+.1f}%")
    print(f"EPS ttm: ${hl.get('EarningsShare')}")
    print(f"Earnings QoQ YoY: {(hl.get('QuarterlyEarningsGrowthYOY') or 0)*100:+.1f}%")
    print(f"Profit margin: {(hl.get('ProfitMargin') or 0)*100:.1f}%")
    print(f"Gross margin: {(hl.get('GrossProfitTTM') or 0)/(hl.get('RevenueTTM') or 1)*100:.1f}%")
    print(f"P/E fwd: {hl.get('ForwardPE')}, PEG: {hl.get('PEGRatio')}")
    print(f"Div yield: {(hl.get('DividendYield') or 0)*100:.2f}%")
    print()
    print("--- EARNINGS HISTORY ---")
    earn = fund.get("Earnings",{}).get("History") or {}
    items = sorted(earn.items(), key=lambda kv: kv[0], reverse=True)[:4]
    for d, v in items:
        surprise = v.get('surprisePercent')
        print(f"  {d} (reported {v.get('reportDate')}): EPS {v.get('epsActual')} vs est {v.get('epsEstimate')} (surprise: {surprise}%)")
    print()
    print("--- SHARE STRUCTURE ---")
    ss = fund.get("SharesStats", {})
    print(f"Float: {ss.get('SharesFloat')}")
    print(f"% Insiders: {ss.get('PercentInsiders')}%")
    print(f"% Institutions: {ss.get('PercentInstitutions')}%")
    print(f"Short % Float: {tech.get('ShortPercentFloat')}")

    insider = client.insider_transactions(TICKER, limit=50) or []
    recent = [i for i in insider if i.get('transactionDate') and (datetime.now() - datetime.strptime(i['transactionDate'], '%Y-%m-%d')).days <= 90]
    buys = [i for i in recent if (i.get('transactionCode') or '').startswith('P')]
    sells = [i for i in recent if (i.get('transactionCode') or '').startswith('S')]
    print(f"Insider 90d: {len(buys)} buys / {len(sells)} sells")

    print("\n--- LANE B ---")
    lb = run_all_lane_b(ind, fund, insider)
    for k, v in lb.items():
        if v.get("fired"):
            print(f"  {k}: FIRED {v.get('summary', '')}")

    print("\n--- OPTIONS ---")
    live = get_live_price(underlying) or last['close']
    phase1 = last['close'] * 1.50
    opt = suggest_options_trade(TICKER, phase1_target=phase1, current_price=live, df_ind=ind)
    if opt:
        print(f"Live price: ${live:.2f}, Phase 1 target: ${phase1:.2f}")
        print(f"Best contract: ${opt['strike']:.0f} Call exp {opt['expiration']} ({opt['dte']}d)")
        print(f"  Delta {opt['delta']}, IV {opt.get('iv_pct')}%, mid ${opt['premium_mid']:.2f}, spread {opt['spread_pct']}%")
        print(f"  Cost: ${opt['cost_per_contract']}, Breakeven: ${opt['breakeven']} ({opt['breakeven_pct_move']}% move)")
        print(f"  Projected ROI at Phase 1: {opt['projected_roi_pct']}% (${opt['profit_per_contract_at_target']:.0f}/contract)")
        print(f"  Vol rank: {opt['vol_rank']['vol_rank_pct']}% ({opt['vol_interpretation']})")
        if opt.get('iv_skew'):
            print(f"  Skew: {opt['iv_skew'].get('skew_pct')} ({opt['iv_skew'].get('skew_bias')})")
    print()

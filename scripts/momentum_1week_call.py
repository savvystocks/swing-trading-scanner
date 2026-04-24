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
from src.alpaca_options import get_options_chain, get_live_price
from src.iv_metrics import vol_rank

client = EODHDClient()

TICKERS = ["ADI.US", "CASY.US", "APH.US"]

def fetch_df(t):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")
    raw = client.ohlcv(t, from_date=start, to_date=end)
    if not raw: return None
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

for tkr in TICKERS:
    underlying = tkr.replace(".US","")
    print(f"\n{'='*60}\n{tkr}\n{'='*60}")
    df = fetch_df(tkr)
    ind = compute_all(df)
    last = ind.iloc[-1]
    close = last["close"]
    atr = last["atr_14"]
    atr_pct = atr/close*100

    live = get_live_price(underlying) or close
    print(f"Live: ${live:.2f}  ATR14: ${atr:.2f} ({atr_pct:.1f}%)")
    print(f"50d: ${last['sma_50']:.2f} (+{(close/last['sma_50']-1)*100:.1f}%)  200d: ${last['sma_200']:.2f} (+{(close/last['sma_200']-1)*100:.1f}%)")

    vr = vol_rank(ind)
    print(f"Realized vol rank: {vr.get('vol_rank_pct')}% (current {vr.get('current_realized_vol')}%)")

    one_week_move = atr * 3
    target_7d = close + one_week_move
    print(f"Realistic 7-day upside (3xATR): ${target_7d:.2f} ({(target_7d/close-1)*100:+.1f}%)")

    contract = get_options_chain(underlying, 'call', live)
    if not contract:
        print("  no contract")
        continue
    strike = contract['strike']
    prem = contract['mid']
    exp = contract['expiration']
    dte = contract['dte']
    iv = contract.get('impliedVol',0)*100
    delta = contract['delta']
    cost = prem*100
    breakeven = strike + prem

    intrinsic_at_target = max(0, target_7d - strike)
    theta_decay = dte * (prem * 0.03)
    time_remaining_value = (dte - 7) / dte * prem * 0.5 if dte > 7 else 0
    projected_value = intrinsic_at_target + time_remaining_value
    roi_at_target = (projected_value - prem) / prem * 100

    print(f"Best call: ${strike:.0f} exp {exp} ({dte}d) delta {delta}")
    print(f"  IV {iv:.0f}%  mid ${prem:.2f}  spread {contract['spread_pct']}%")
    print(f"  Cost ${cost:.0f}/contract  breakeven ${breakeven:.2f} ({(breakeven/live-1)*100:+.1f}% move)")
    print(f"  If stock hits ${target_7d:.2f} in 7 days (3xATR move):")
    print(f"    Option value ~${projected_value:.2f}  ROI ~{roi_at_target:+.0f}%")

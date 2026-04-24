import os
import subprocess
import sys

def load_user_env(name):
    r = subprocess.run(
        ["powershell", "-Command", f'[Environment]::GetEnvironmentVariable("{name}","User")'],
        capture_output=True, text=True,
    )
    return (r.stdout or "").strip()

for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "EODHD_API_KEY"):
    if not os.environ.get(k):
        v = load_user_env(k)
        if v:
            os.environ[k] = v

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timedelta
from src.eodhd import EODHDClient
from src.indicators import compute_all as add_indicators
from src.options_suggest import suggest_options_trade

_client = EODHDClient()

def get_ohlcv(ticker):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")
    raw = _client.ohlcv(ticker, from_date=start, to_date=end)
    if not raw:
        return None
    df = pd.DataFrame(raw)
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

BUDGET = 1000

plans = [
    {"ticker": "ADTN.US", "entry": 17.50, "stop": 15.40, "phase1": 26.25, "runner": 31.50},
    {"ticker": "DGII.US", "entry": 55.80, "stop": 49.10, "phase1": 83.70, "runner": 100.44},
]

results = []
for p in plans:
    print(f"\n=== {p['ticker']} ===")
    try:
        df = get_ohlcv(p["ticker"])
        df_ind = add_indicators(df) if df is not None and len(df) > 0 else None
    except Exception as e:
        print(f"  OHLCV fetch failed: {e}")
        df_ind = None

    opt = suggest_options_trade(p["ticker"], phase1_target=p["phase1"], current_price=p["entry"], df_ind=df_ind)
    if not opt:
        print("  No option contract returned.")
        continue

    cost_per = opt["cost_per_contract"]
    max_contracts = int(BUDGET // cost_per) if cost_per > 0 else 0
    total_cost = max_contracts * cost_per
    remaining = BUDGET - total_cost
    total_profit_at_target = max_contracts * opt["profit_per_contract_at_target"]
    roi_on_budget = (total_profit_at_target / BUDGET * 100) if BUDGET > 0 else 0

    results.append({
        "ticker": p["ticker"],
        "strike": opt["strike"],
        "expiration": opt["expiration"],
        "dte": opt["dte"],
        "delta": opt["delta"],
        "iv_pct": opt["iv_pct"],
        "mid": opt["premium_mid"],
        "bid": opt["bid"],
        "ask": opt["ask"],
        "spread_pct": opt["spread_pct"],
        "breakeven": opt["breakeven"],
        "breakeven_pct": opt["breakeven_pct_move"],
        "cost_per": cost_per,
        "max_contracts": max_contracts,
        "total_cost": round(total_cost, 2),
        "remaining": round(remaining, 2),
        "projected_value_at_target": opt["projected_value_at_target"],
        "projected_roi_pct": opt["projected_roi_pct"],
        "profit_per_contract_at_target": opt["profit_per_contract_at_target"],
        "total_profit_at_target": round(total_profit_at_target, 2),
        "roi_on_budget_pct": round(roi_on_budget, 0),
        "vol_rank": opt.get("vol_rank"),
        "vol_interpretation": opt.get("vol_interpretation"),
        "iv_skew": opt.get("iv_skew"),
    })

print("\n\n=== SUMMARY ===")
for r in results:
    print(f"\n{r['ticker']}")
    for k, v in r.items():
        if k == "ticker":
            continue
        print(f"  {k}: {v}")

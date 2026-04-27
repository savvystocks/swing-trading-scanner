import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

def load(n):
    if os.environ.get(n): return os.environ[n]
    r = subprocess.run(["powershell","-Command",f'[Environment]::GetEnvironmentVariable("{n}","User")'], capture_output=True, text=True)
    return (r.stdout or "").strip()

for k in ("EODHD_API_KEY","ALPACA_API_KEY","ALPACA_SECRET_KEY"):
    v = load(k)
    if v: os.environ[k]=v

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.eodhd import EODHDClient
from src.indicators import to_dataframe, compute_all
from datetime import datetime, timedelta
import pandas as pd

client = EODHDClient()
def get_fundamentals(t): return client.fundamentals(t)
def get_eod_history(t, days=250):
    to_d = datetime.now().strftime("%Y-%m-%d")
    from_d = (datetime.now() - timedelta(days=int(days*1.6))).strftime("%Y-%m-%d")
    raw = client.ohlcv(t, from_date=from_d, to_date=to_d)
    df = to_dataframe(raw)
    return df.tail(days) if df is not None and len(df) > days else df
def compute_indicators(df): return compute_all(df)

TICKER = "PUMP.US"
print(f"=== {TICKER} ===\n")

fund = get_fundamentals(TICKER)
g = (fund.get("General") or {})
h = (fund.get("Highlights") or {})
v = (fund.get("Valuation") or {})
ts = (fund.get("Technicals") or {})
shr = (fund.get("SharesStats") or {})
sec = (fund.get("SectorWeights") or {})

print(f"Name        : {g.get('Name')}")
print(f"Sector      : {g.get('Sector')}")
print(f"Industry    : {g.get('Industry')}")
print(f"Country     : {g.get('CountryName')}")
print(f"Exchange    : {g.get('Exchange')}")
print(f"Market Cap  : ${(h.get('MarketCapitalization') or 0)/1e9:.2f}B")
print(f"Float       : {(shr.get('PercentInsiders') or 0):.1f}% insiders, {(shr.get('PercentInstitutions') or 0):.1f}% inst")
print(f"Shares Out  : {(shr.get('SharesOutstanding') or 0)/1e6:.1f}M")
print(f"Short Float : {(shr.get('ShortPercentFloat') or 0):.2f}%")
print()
print(f"P/E TTM     : {h.get('PERatio')}")
print(f"PEG         : {h.get('PEGRatio')}")
print(f"EPS TTM     : ${h.get('EarningsShare')}")
print(f"Revenue TTM : ${(h.get('RevenueTTM') or 0)/1e9:.2f}B")
print(f"Gross Margin: {(h.get('GrossProfitMarginTTM') or 0)*100:.1f}%")
print(f"Op Margin   : {(h.get('OperatingMarginTTM') or 0)*100:.1f}%")
print(f"Profit Margin: {(h.get('ProfitMargin') or 0)*100:.1f}%")
print(f"ROE         : {(h.get('ReturnOnEquityTTM') or 0)*100:.1f}%")
print(f"Debt/Equity : {h.get('DebtToEquity')}")
print(f"Quarterly Rev Growth YoY: {(h.get('QuarterlyRevenueGrowthYOY') or 0)*100:.1f}%")
print(f"Quarterly Earn Growth YoY: {(h.get('QuarterlyEarningsGrowthYOY') or 0)*100:.1f}%")
print()
print(f"52w High    : ${ts.get('52WeekHigh')}")
print(f"52w Low     : ${ts.get('52WeekLow')}")
print(f"50d MA      : ${ts.get('50DayMA')}")
print(f"200d MA     : ${ts.get('200DayMA')}")
print(f"Beta        : {ts.get('Beta')}")
print()

earn = (fund.get("Earnings") or {})
hist = (earn.get("History") or {})
print("=== Recent Earnings ===")
items = sorted([(k,v) for k,v in hist.items()], reverse=True)[:6]
for k,v in items:
    rd = v.get("reportDate")
    eps_act = v.get("epsActual")
    eps_est = v.get("epsEstimate")
    surp = v.get("surprisePercent")
    print(f"  {rd}  EPS act={eps_act}  est={eps_est}  surprise={surp}%")
print()

trend = (earn.get("Trend") or {})
print("=== Earnings Trend (analyst revisions) ===")
items = sorted([(k,v) for k,v in trend.items()])[:4]
for k,v in items:
    print(f"  {k} (period end)")
    print(f"    EPS estimate: now={v.get('earningsEstimateAvg')}  7d ago={v.get('earningsEstimate7daysAgo','?')}  30d={v.get('earningsEstimate30daysAgo','?')}  60d={v.get('earningsEstimate60daysAgo','?')}")
    print(f"    Revisions up (last 30d): {v.get('epsRevisionsUpLast30days','?')}")
    print(f"    Revisions down (last 30d): {v.get('epsRevisionsDownLast30days','?')}")
print()

ar = (fund.get("AnalystRatings") or {})
print("=== Analyst Ratings ===")
print(f"  Rating: {ar.get('Rating')}")
print(f"  Target Price: ${ar.get('TargetPrice')}")
print(f"  Strong Buy: {ar.get('StrongBuy')}, Buy: {ar.get('Buy')}, Hold: {ar.get('Hold')}, Sell: {ar.get('Sell')}, Strong Sell: {ar.get('StrongSell')}")
print()

print("=== Loading 250d OHLCV ===")
hist_df = get_eod_history(TICKER, days=250)
if hist_df is None or len(hist_df) < 50:
    print("Insufficient history")
    sys.exit()
print(f"Loaded {len(hist_df)} bars, last close ${hist_df.iloc[-1]['close']:.2f} on {hist_df.index[-1].date()}")
print()

ind = compute_indicators(hist_df)
last = ind.iloc[-1]
print("=== Technicals (last bar) ===")
print(f"  Close       : ${float(last['close']):.2f}")
print(f"  SMA 20      : ${float(last.get('sma_20', float('nan'))):.2f}")
print(f"  SMA 50      : ${float(last.get('sma_50', float('nan'))):.2f}")
print(f"  SMA 150     : ${float(last.get('sma_150', float('nan'))):.2f}")
print(f"  SMA 200     : ${float(last.get('sma_200', float('nan'))):.2f}")
print(f"  RSI 14      : {float(last.get('rsi_14', float('nan'))):.1f}")
print(f"  ATR 14      : ${float(last.get('atr_14', float('nan'))):.2f} ({float(last.get('atr_14',0))/float(last['close'])*100:.1f}% of price)")
print(f"  BB Squeeze %: {last.get('bb_squeeze_pct')}")
print(f"  MACD        : {float(last.get('macd', 0)):.3f}  signal={float(last.get('macd_signal',0)):.3f}")
print()

# Returns over time
print("=== Returns ===")
close = ind['close']
for d, label in [(1,'1d'),(5,'5d'),(10,'10d'),(20,'20d'),(60,'60d'),(120,'120d')]:
    if len(close) > d:
        ret = (close.iloc[-1]/close.iloc[-1-d] - 1) * 100
        print(f"  {label:5s}: {ret:+.1f}%")
print()

# 52w high / low context
hh = float(close.max())
ll = float(close.min())
print(f"52w high (in window): ${hh:.2f}  ->  {(close.iloc[-1]/hh - 1)*100:+.1f}% from high")
print(f"52w low  (in window): ${ll:.2f}  ->  {(close.iloc[-1]/ll - 1)*100:+.1f}% from low")
print()

# Volatility forecast for projection
returns = close.pct_change().dropna()
realized_vol_20d = returns.tail(20).std() * (252**0.5) * 100
realized_vol_60d = returns.tail(60).std() * (252**0.5) * 100
atr_pct = float(last.get('atr_14',0))/float(last['close'])*100

print(f"=== Volatility profile ===")
print(f"  Realized vol 20d: {realized_vol_20d:.1f}% annualized")
print(f"  Realized vol 60d: {realized_vol_60d:.1f}% annualized")
print(f"  Daily ATR%      : {atr_pct:.2f}%")
print()

# Project where PUMP can realistically be at expiry (15 May 2026 = 17 calendar days from 28 Apr)
import math
spot = float(last['close'])
days_to_exp = 17  # 28 Apr to 15 May
trading_days = 12  # roughly
sigma_period = realized_vol_20d / 100 * math.sqrt(trading_days/252)

print(f"=== Projection to 15 May 2026 ({trading_days} trading days) ===")
print(f"  Period sigma (1 std): {sigma_period*100:.1f}% from current ${spot:.2f}")
for sd, label in [(-2,'-2sd'),(-1,'-1sd'),(0,'mean'),(1,'+1sd'),(2,'+2sd')]:
    target = spot * math.exp(sd * sigma_period)
    print(f"    {label}: ${target:.2f}")
print()

# Option payoff at each scenario for PUMP $15 May 15 CALL @ $2.29
strike = 15.0
entry = 2.29
contracts = 8
print(f"=== Option payoff scenarios at expiry (PUMP $15 CALL, entry $2.29 x 8) ===")
print(f"  PUMP at expiry    | Premium  | Per-contract P&L | Total P&L (8 ct)")
print(f"  ------------------|----------|------------------|------------------")
for sd, label in [(-2,'-2sd'),(-1,'-1sd'),(0,'mean'),(1,'+1sd'),(2,'+2sd')]:
    target = spot * math.exp(sd * sigma_period)
    intrinsic = max(0, target - strike)
    pnl_per = (intrinsic - entry)
    pnl_total = pnl_per * 100 * contracts
    pnl_pct = pnl_per/entry*100
    print(f"  {label:4s} ${target:>6.2f}     | ${intrinsic:>5.2f}   | {pnl_per:>+5.2f} ({pnl_pct:>+4.0f}%)   | ${pnl_total:>+8.0f}")

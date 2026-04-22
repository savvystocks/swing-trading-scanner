import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from src.eodhd import EODHDClient
from src.indicators import to_dataframe, compute_all

client = EODHDClient()
start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
ohlcv = client.ohlcv('KEYS.US', from_date=start)
df = to_dataframe(ohlcv)
ind = compute_all(df)

today_close = float(ind['close'].iloc[-1])
d90 = float(ind['close'].iloc[-63])
d60 = float(ind['close'].iloc[-42])
d30 = float(ind['close'].iloc[-21])
d180 = float(ind['close'].iloc[-126])

print('KEYS.US price ladder:')
print(f'  6 months ago: ${d180:.2f}')
print(f'  3 months ago: ${d90:.2f}  ->  today +{(today_close-d90)/d90*100:.1f}%')
print(f'  2 months ago: ${d60:.2f}  ->  today +{(today_close-d60)/d60*100:.1f}%')
print(f'  1 month ago:  ${d30:.2f}  ->  today +{(today_close-d30)/d30*100:.1f}%')
print(f'  Today:        ${today_close:.2f}')
print()

print('Breakout days (>=3% up with RVOL>=2x) in last 90d:')
for i in range(-90, -1):
    close = float(ind['close'].iloc[i])
    prev_close = float(ind['close'].iloc[i-1])
    ret = (close - prev_close) / prev_close * 100
    vol = float(ind['volume'].iloc[i])
    avg_vol = float(ind['avg_vol_20'].iloc[i]) if ind['avg_vol_20'].iloc[i] else 1
    rvol = vol / avg_vol if avg_vol else 0
    date = ind.index[i].strftime('%Y-%m-%d')
    sq_val = ind['bb_squeeze_pct'].iloc[i]
    sq = float(sq_val) if sq_val is not None and not (sq_val != sq_val) else -1
    if ret >= 3 and rvol >= 2:
        print(f'  {date}  close ${close:.2f}  +{ret:.1f}%  rvol {rvol:.1f}x  squeeze pct {sq:.0f}')
print()

print('Squeeze compression timeline:')
for offset, label in [(-126,'6mo ago'),(-90,'3mo ago'),(-63,'2mo ago'),(-42,'6wk ago'),(-21,'1mo ago'),(-1,'today')]:
    sq_val = ind['bb_squeeze_pct'].iloc[offset]
    sq = float(sq_val) if sq_val is not None and not (sq_val != sq_val) else -1
    print(f'  {label}: squeeze percentile {sq:.0f}')
print()

print('50dMA extension timeline:')
for offset, label in [(-126,'6mo ago'),(-90,'3mo ago'),(-63,'2mo ago'),(-42,'6wk ago'),(-21,'1mo ago'),(-1,'today')]:
    close = float(ind['close'].iloc[offset])
    sma_val = ind['sma_50'].iloc[offset]
    sma50 = float(sma_val) if sma_val is not None and not (sma_val != sma_val) else 0
    pct = (close - sma50) / sma50 * 100 if sma50 else 0
    print(f'  {label}: close ${close:.2f} vs 50d ${sma50:.2f}  ({pct:+.1f}% extended)')
print()

fundamentals = client.fundamentals('KEYS.US')
earn = fundamentals.get('Earnings', {}).get('History', {}) or {}
print('Earnings history (most recent 6):')
for d, row in sorted(earn.items(), reverse=True)[:6]:
    sp = row.get('surprisePercent')
    rd = row.get('reportDate')
    epsA = row.get('epsActual')
    epsE = row.get('epsEstimate')
    print(f'  FQ ending {d}  report {rd}  actual {epsA}  est {epsE}  surprise {sp}%')
print()

trend = fundamentals.get('Earnings', {}).get('Trend', {}) or {}
if trend:
    k0 = list(trend.keys())[0]
    t0 = trend[k0]
    print(f'Analyst trend for FQ {k0}:')
    print(f'  EPS estimate:           {t0.get("earningsEstimateAvg")}')
    print(f'  Revisions up 7d:        {t0.get("epsRevisionsUpLast7days")}')
    print(f'  Revisions up 30d:       {t0.get("epsRevisionsUpLast30days")}')
    print(f'  Revisions down 30d:     {t0.get("epsRevisionsDownLast30days")}')
print()

h = fundamentals.get('Highlights', {}) or {}
print('Current fundamentals snapshot:')
print(f'  Market cap:     {h.get("MarketCapitalization")}')
print(f'  EPS TTM:        {h.get("EarningsShare")}')
print(f'  P/E:            {h.get("PERatio")}')
print(f'  PEG:            {h.get("PEGRatio")}')
print(f'  Profit margin:  {h.get("ProfitMargin")}')
print(f'  ROE:            {h.get("ReturnOnEquityTTM")}')
print(f'  Q EPS growth YoY:  {h.get("QuarterlyEarningsGrowthYOY")}')
print(f'  Q Rev growth YoY:  {h.get("QuarterlyRevenueGrowthYOY")}')

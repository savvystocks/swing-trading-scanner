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

client = EODHDClient(cache_hours=0)

TICKER = "PUMP.US"
SYMBOL = "PUMP"

print("=" * 70)
print(f"  PUMP DECISION CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 70)

print("\n[1] LIVE PRICE (Alpaca)")
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
    sc = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    t = sc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=SYMBOL))
    q = sc.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=SYMBOL))
    last_trade = t[SYMBOL] if isinstance(t, dict) else t
    last_quote = q[SYMBOL] if isinstance(q, dict) else q
    print(f"  Last trade: ${float(last_trade.price):.2f} @ {last_trade.timestamp}")
    print(f"  Bid/Ask:    ${float(last_quote.bid_price):.2f} x ${float(last_quote.ask_price):.2f}")
    LIVE = float(last_trade.price)
except Exception as e:
    print(f"  Failed: {e}")
    LIVE = None

print("\n[2] LATEST OHLCV BARS (volume / accumulation pattern)")
to_d = datetime.now().strftime("%Y-%m-%d")
from_d = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
raw = client.ohlcv(TICKER, from_date=from_d, to_date=to_d)
df = to_dataframe(raw)
print(f"  Last 15 sessions:")
print(f"  {'Date':12s} {'Open':>7s} {'High':>7s} {'Low':>7s} {'Close':>7s} {'Volume':>11s} {'%chg':>7s}  {'avgV%':>6s}")
avg_vol = df['volume'].tail(40).mean()
acc_days = 0
dist_days = 0
for i in range(-15, 0):
    r = df.iloc[i]
    pct = (r['close']/df.iloc[i-1]['close'] - 1) * 100 if i > -len(df) else 0
    vol_pct = r['volume']/avg_vol*100
    label = ""
    if pct > 0.3 and vol_pct > 110:
        label = " ACC"
        acc_days += 1
    elif pct < -0.3 and vol_pct > 110:
        label = " DIST"
        dist_days += 1
    print(f"  {df.index[i].strftime('%Y-%m-%d')} {r['open']:>7.2f} {r['high']:>7.2f} {r['low']:>7.2f} {r['close']:>7.2f} {int(r['volume']):>11,d} {pct:>+6.1f}%  {vol_pct:>5.0f}%{label}")
print(f"\n  Last 15 sessions: {acc_days} accumulation days (up >0.3% on >110% avg vol)")
print(f"                    {dist_days} distribution days (down <-0.3% on >110% avg vol)")
print(f"  Net: {'INSTITUTIONAL ACCUMULATION' if acc_days > dist_days+1 else 'NEUTRAL/MIXED' if acc_days >= dist_days else 'DISTRIBUTION (warning)'}")

print("\n[3] INSIDER TRANSACTIONS (last 6 months)")
try:
    insider = client.insider_transactions(TICKER, limit=30)
    if insider:
        cutoff = datetime.now() - timedelta(days=180)
        recent = [t for t in insider if t.get('transactionDate') and datetime.strptime(t['transactionDate'], '%Y-%m-%d') >= cutoff]
        if not recent:
            print("  No insider transactions in last 6 months")
        else:
            buys = [t for t in recent if (t.get('transactionAcquiredDisposedCode') or '').upper() == 'A']
            sells = [t for t in recent if (t.get('transactionAcquiredDisposedCode') or '').upper() == 'D']
            buy_value = sum((t.get('transactionPrice') or 0) * (t.get('transactionAmount') or 0) for t in buys)
            sell_value = sum((t.get('transactionPrice') or 0) * (t.get('transactionAmount') or 0) for t in sells)
            print(f"  {len(buys)} buys (${buy_value:,.0f})  vs  {len(sells)} sells (${sell_value:,.0f})")
            print(f"  Recent transactions:")
            for t in recent[:10]:
                code = t.get('transactionAcquiredDisposedCode', '?')
                action = 'BUY' if code == 'A' else 'SELL' if code == 'D' else code
                print(f"    {t.get('transactionDate'):10s} {action:5s} {(t.get('ownerName') or '')[:30]:30s} {(t.get('transactionAmount') or 0):>10,d} sh @ ${(t.get('transactionPrice') or 0):.2f}")
    else:
        print("  No insider data returned")
except Exception as e:
    print(f"  Failed: {e}")

print("\n[4] EARNINGS CONTEXT")
fund = client.fundamentals(TICKER)
earn = (fund.get("Earnings") or {})
hist = (earn.get("History") or {})
upcoming = []
recent_reports = []
today = datetime.now().date()
for k, v in hist.items():
    rd = v.get('reportDate')
    if rd:
        try:
            rd_d = datetime.strptime(rd, '%Y-%m-%d').date()
            if rd_d > today:
                upcoming.append((rd_d, v))
            elif (today - rd_d).days <= 365:
                recent_reports.append((rd_d, v))
        except ValueError:
            pass
upcoming.sort()
recent_reports.sort(reverse=True)
if upcoming:
    print(f"  NEXT EARNINGS: {upcoming[0][0]} ({(upcoming[0][0]-today).days} days away)")
print(f"  Last 4 reports:")
for rd_d, v in recent_reports[:4]:
    eps_a = v.get('epsActual')
    eps_e = v.get('epsEstimate')
    surp = v.get('surprisePercent')
    beat = "BEAT" if eps_a and eps_e and float(eps_a) > float(eps_e) else "MISS"
    print(f"    {rd_d}  {beat}  EPS act={eps_a} est={eps_e} surprise={surp}%")

print("\n[5] EARNINGS REVISIONS (analyst sentiment)")
trend = (earn.get("Trend") or {})
fwd = []
for k, v in trend.items():
    try:
        period_end = datetime.strptime(k, '%Y-%m-%d').date()
        if period_end >= today - timedelta(days=180):
            fwd.append((period_end, v))
    except (ValueError, TypeError):
        pass
fwd.sort()
for pe, v in fwd[:4]:
    now_est = v.get('earningsEstimateAvg')
    e7 = v.get('earningsEstimate7daysAgo')
    e30 = v.get('earningsEstimate30daysAgo')
    e60 = v.get('earningsEstimate60daysAgo')
    revs_up = float(v.get('epsRevisionsUpLast30days') or 0)
    revs_dn = float(v.get('epsRevisionsDownLast30days') or 0)
    direction = "UP" if revs_up > revs_dn else "DOWN" if revs_dn > revs_up else "FLAT"
    print(f"  Period end {pe}: now est={now_est}  30d ago={e30}  60d ago={e60}")
    print(f"    Last 30d: {revs_up:.0f} up vs {revs_dn:.0f} down  -> {direction}")

print("\n[6] RECENT NEWS HEADLINES")
try:
    news = client.news(TICKER, limit=15)
    if news:
        for n in news[:10]:
            d = (n.get('date') or '')[:10]
            title = (n.get('title') or '')[:90]
            sent = n.get('sentiment') or {}
            polarity = sent.get('polarity', 0) if isinstance(sent, dict) else 0
            mark = "+" if polarity > 0.1 else "-" if polarity < -0.1 else "."
            print(f"  {d} [{mark}] {title}")
    else:
        print("  No news returned")
except Exception as e:
    print(f"  Failed: {e}")

if LIVE:
    print("\n[7] CURRENT POSITION P&L (with live price)")
    spot = LIVE
    strike = 15.0
    days_to_exp = (datetime(2026,5,15) - datetime.now()).days
    intrinsic = max(0, spot - strike)
    print(f"  PUMP live: ${spot:.2f}")
    print(f"  Days to expiry: {days_to_exp}")
    print(f"  Intrinsic: ${intrinsic:.2f}")
    print(f"  Entry: $2.29 -> need premium > $2.29 to break even at expiry (PUMP > $17.29)")
    if intrinsic > 2.29:
        print(f"  AT EXPIRY (intrinsic only): per-contract +${intrinsic-2.29:.2f} = +{(intrinsic-2.29)/2.29*100:.0f}%, total 8ct = ${(intrinsic-2.29)*800:.0f}")
    else:
        print(f"  AT EXPIRY (intrinsic only): per-contract -${2.29-intrinsic:.2f} = -{(2.29-intrinsic)/2.29*100:.0f}%, total 8ct = -${(2.29-intrinsic)*800:.0f}")

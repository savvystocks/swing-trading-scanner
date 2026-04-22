import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from src.eodhd import EODHDClient
from src.indicators import to_dataframe, compute_all

client = EODHDClient()
start = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')

# Compare KEYS vs Test & Measurement peers vs broader semi space
tickers = {
    'KEYS.US': 'Keysight - test & measurement leader',
    'VIAV.US': 'Viavi Solutions - direct T&M competitor',
    'TER.US':  'Teradyne - chip testing (lower half of value chain)',
    'KLAC.US': 'KLA Corp - metrology / semi inspection',
    'AMAT.US': 'Applied Materials - broad semicap',
    'LRCX.US': 'Lam Research - semicap',
    'ASML.US': 'ASML - lithography',
    'NVDA.US': 'NVIDIA - customer',
    'SOX':     'SOX ETF stand-in? (skip)',
    'SPY.US':  'S&P 500 baseline',
}

print('3-month price performance peer comparison:')
print(f"{'Ticker':10s}  {'3mo ret':>9s}  {'Note':<40s}")
print('-'*70)
for t, note in tickers.items():
    if t == 'SOX':
        continue
    try:
        data = client.ohlcv(t, from_date=start)
        if not data or len(data) < 90:
            continue
        df = to_dataframe(data)
        if len(df) < 65:
            continue
        today = float(df['close'].iloc[-1])
        d90 = float(df['close'].iloc[-65])
        ret = (today - d90) / d90 * 100
        print(f"{t:10s}  {ret:+8.1f}%  {note}")
    except Exception as e:
        print(f"{t:10s}  ERROR    {e}")
print()

# KEYS fundamentals deep dive
fund = client.fundamentals('KEYS.US')
general = fund.get('General', {}) or {}
print(f"Company: {general.get('Name')}")
print(f"Sector: {general.get('Sector')} / Industry: {general.get('Industry')}")
print(f"Sector group: {general.get('GicSector')}")
desc = general.get('Description', '')
print(f"Business desc (first 500 chars): {desc[:500]}...")
print()

# Valuations
val = fund.get('Valuation', {}) or {}
print('Valuation metrics:')
print(f"  Forward P/E:        {val.get('ForwardPE')}")
print(f"  P/S TTM:            {val.get('PriceSalesTTM')}")
print(f"  EV/Revenue:         {val.get('EnterpriseValueRevenue')}")
print(f"  EV/EBITDA:          {val.get('EnterpriseValueEbitda')}")
print()

# Tech / growth
tech = fund.get('Technicals', {}) or {}
print('Technicals:')
print(f"  Beta:               {tech.get('Beta')}")
print(f"  52-Week High:       {tech.get('52WeekHigh')}")
print(f"  52-Week Low:        {tech.get('52WeekLow')}")
print(f"  50DayMA:            {tech.get('50DayMA')}")
print(f"  200DayMA:           {tech.get('200DayMA')}")
print()

# Growth trajectory
earn = fund.get('Earnings', {}) or {}
annual = earn.get('Annual', {}) or {}
print('Annual earnings trajectory:')
for k, v in sorted(annual.items(), reverse=True)[:5]:
    print(f"  FY {k}: EPS ${v.get('epsActual')}  est ${v.get('epsEstimate')}")
print()

# Revenue trend
fin = fund.get('Financials', {}) or {}
income = fin.get('Income_Statement', {}) or {}
quarterly = income.get('quarterly', {}) or {}
print('Quarterly revenue trend (last 8 quarters):')
for k, v in sorted(quarterly.items(), reverse=True)[:8]:
    rev = v.get('totalRevenue')
    ni = v.get('netIncome')
    op_inc = v.get('operatingIncome')
    if rev:
        rev_b = float(rev)/1e9
        ni_m = float(ni)/1e6 if ni else 0
        op_m = float(op_inc)/1e6 if op_inc else 0
        print(f"  FQ {k}: Rev ${rev_b:.2f}B  OpIncome ${op_m:.0f}M  NI ${ni_m:.0f}M")
print()

# Insider & institutional
shares = fund.get('SharesStats', {}) or {}
print('Share structure:')
print(f"  Market cap:         ${int(shares.get('SharesOutstanding', 0) * float(fund.get('Highlights',{}).get('EarningsShare') or 0)):,}")
print(f"  Shares outstanding: {shares.get('SharesOutstanding')}")
print(f"  Shares float:       {shares.get('SharesFloat')}")
print(f"  % held by insiders: {shares.get('PercentInsiders')}")
print(f"  % held by institutions: {shares.get('PercentInstitutions')}")
print(f"  Short % of float:   {shares.get('ShortPercentFloat')}")
print()

# News feed — what the narrative has been
news = client.news('KEYS.US', limit=30) or []
print(f'Recent news headlines ({len(news)} items):')
# Keywords to flag
kw_map = {
    'ai':          ['ai ', 'artificial intelligence', 'gpu', 'nvidia', 'silicon photonic'],
    'network':     ['5g', '6g', 'ethernet', '800g', 'optical', 'network'],
    'defense':     ['defense', 'aerospace', 'radar', 'satellite', 'military'],
    'auto':        ['automot', 'ev ', 'electric vehicle', 'autonomous'],
    'capex':       ['bookings', 'backlog', 'orders', 'capex'],
    'guidance':    ['guidance', 'outlook', 'raise', 'raised'],
    'analyst':     ['upgrade', 'target', 'buy rating', 'price target'],
    'product':     ['launch', 'new product', 'unveil'],
    'beat':        ['beat', 'exceed', 'top estimate'],
    'ma':          ['acquire', 'acquisition', 'merger'],
}
import re
hits = {k: 0 for k in kw_map}
for n in news[:30]:
    title = (n.get('title') or '').lower()
    content = (n.get('content') or '')[:400].lower()
    full = title + ' ' + content
    matched_cats = []
    for cat, kws in kw_map.items():
        for kw in kws:
            if kw in full:
                hits[cat] += 1
                matched_cats.append(cat)
                break
    tag = '[' + ','.join(sorted(set(matched_cats))) + ']' if matched_cats else ''
    date = n.get('date', '')[:10]
    print(f"  {date}  {title[:95]}  {tag}")
print()
print('News topic totals (of 30 headlines):')
for cat, count in sorted(hits.items(), key=lambda x: -x[1]):
    if count > 0:
        print(f"  {cat:12s} {count}")

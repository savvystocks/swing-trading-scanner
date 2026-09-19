#!/usr/bin/env python
"""FAMILY F - WILDCARD.  Pre-registered grid, executable prices only, permutation bar on the whole grid.
Runs end to end from /tmp/research/.  Writes F_wildcard_results.json (and intermediate F_wildcard_progress.json).

Sub-families (all defined-risk, one contract, settle at expiry close = intrinsic, entered at that day's CLOSE):
  A  ETF premium selling (TLT GLD SLV XLF XLE SMH + SPY QQQ IWM): put/call credit spreads + delta-neutral condors,
     short strike by delta (0.10/0.20/0.30), two widths, Monday->Friday, BEAR gate on.  Pooled variants.
  H  Stock pool (25 names) and ALL-34 pool short premium.
  B  Open-interest walls: short strike just beyond (or at) the largest-OI strike of the week's expiry.
  C  Put/call IV skew (iv@-0.25 put minus iv@+0.25 call) tercile signal -> credit spreads and debit spreads.
  D  Day-of-week entry (2nd/3rd/4th trading day -> Friday) and month-end weeks.
  E  Directional debit spreads with NO stop (long 0.50 / short 0.25), regime-conditioned.
  F  contracts volume/OI unusual-activity STAND-DOWN filter on the pooled base (paired vs base).
  G  SPY ATM IV (VIX proxy) filter combined with / instead of the BEAR gate (paired vs base).
"""
import sqlite3, json, math, os, sys, time
from collections import defaultdict
from datetime import date
import numpy as np

os.chdir('/tmp/research')
START, END, WARM = '2024-09-03', '2026-03-13', '2024-07-01'
NFLIP = 600
SEED = 20260918
MIN_N = 20   # tercile-signal configs cannot reach 30 periods in 77 weeks; 20 is the eligibility floor
T0 = time.time()

def log(*a):
    print(f'[{time.time()-T0:7.1f}s]', *a, flush=True)

closes = json.load(open('closes.json'))
regime = json.load(open('regime.json'))
cal = [d for d in sorted(closes['SPY']) if WARM <= d <= END]

def isoweek(d):
    y, m, dd = map(int, d.split('-'))
    return date(y, m, dd).isocalendar()[:2]

_weeks = defaultdict(list)
for d in cal:
    _weeks[isoweek(d)].append(d)
WEEKS = [w for w in sorted(_weeks) if _weeks[w][0] >= START and _weeks[w][-1] <= END]
WEEK_DAYS = {w: _weeks[w] for w in WEEKS}
WEEK_EXP = {w: _weeks[w][-1] for w in WEEKS}
WIDX = {w: i for i, w in enumerate(WEEKS)}
_allw = sorted(_weeks)
WEEK_EXP2 = {w: _weeks[_allw[_allw.index(w) + 1]][-1] for w in WEEKS if _allw.index(w) + 1 < len(_allw) and _weeks[_allw[_allw.index(w) + 1]][-1] <= END}
# month-end weeks: the week contains the last trading day of a calendar month
_last_of_month = set()
for i, d in enumerate(cal):
    if i + 1 == len(cal) or cal[i + 1][:7] != d[:7]:
        _last_of_month.add(d)
MONTHEND = {w: any(d in _last_of_month for d in WEEK_DAYS[w]) for w in WEEKS}
def quarter(d):
    return f'{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}'

ETF6 = ['TLT', 'GLD', 'SLV', 'XLF', 'XLE', 'SMH']
IDX3 = ['SPY', 'QQQ', 'IWM']
ETF9 = ETF6 + IDX3
ALL34 = sorted(set(['AAPL', 'AMD', 'AMZN', 'AVGO', 'BAC', 'COIN', 'COST', 'CRM', 'GLD', 'GOOGL', 'HD', 'IWM', 'JPM', 'LLY',
                    'META', 'MSFT', 'MSTR', 'MU', 'NFLX', 'NVDA', 'ORCL', 'PLTR', 'QQQ', 'SLV', 'SMH', 'SPY', 'TLT', 'TSLA',
                    'UNH', 'WMT', 'XLE', 'XLF', 'XOM']))
STK25 = [t for t in ALL34 if t not in ETF9]
GROUPS = {'ETF6': ETF6, 'ETF9': ETF9, 'STK25': STK25, 'ALL34': ALL34}
ETF_WIDTHS = {'TLT': (1, 2), 'GLD': (5, 10), 'SLV': (1, 2), 'XLF': (1, 2), 'XLE': (1, 2), 'SMH': (5, 10),
              'SPY': (5, 10), 'QQQ': (5, 10), 'IWM': (2, 5)}
def width_for(t, px, which):
    if t in ETF_WIDTHS:
        return ETF_WIDTHS[t][0 if which == 'small' else 1]
    # stocks: width by that day's (unadjusted) price
    if px < 60: return 1.0
    if px < 150: return 2.5
    if px < 400: return 5.0
    return 10.0

# ----------------------------------------------------------------------------------------------- CONFIG GRID
CONFIGS = []
def add(sub, name, tickers, struct, sel='delta', delta=None, width='small', pos=0, gate=True, signal=None, pooled=None, tenor=1):
    CONFIGS.append(dict(id=len(CONFIGS), sub=sub, name=name, tickers=list(tickers), struct=struct, sel=sel, delta=delta,
                        width=width, pos=pos, gate=gate, signal=signal, pooled=pooled, tenor=tenor))

def units_etf9(per_ticker=True, pools=('ETF6', 'ETF9')):
    u = [(t, [t], None) for t in ETF9] if per_ticker else []
    u += [(p, GROUPS[p], p) for p in pools]
    return u

# A: ETF/index short premium, delta-selected, Monday->Friday, BEAR gate on
for label, tl, pooled in units_etf9():
    for st in ('PCS', 'CCS', 'IC'):
        for dl in (0.10, 0.20, 0.30):
            for wd in ('small', 'large'):
                add('A', f'A_{label}_{st}_d{dl:.2f}_{wd}', tl, st, delta=dl, width=wd, pooled=pooled)
for st in ('PCS', 'CCS', 'IC'):
    for dl in (0.10, 0.20, 0.30):
        for wd in ('small', 'large'):
            add('A', f'A_ETF6nogate_{st}_d{dl:.2f}_{wd}', ETF6, st, delta=dl, width=wd, gate=False, pooled='ETF6')
# H: stock pool / all-34 pool short premium (gate only matters for index/ETF members; STK25 has none)
for p in ('STK25', 'ALL34'):
    for st in ('PCS', 'CCS', 'IC'):
        for dl in (0.10, 0.20, 0.30):
            add('H', f'H_{p}_{st}_d{dl:.2f}_small', GROUPS[p], st, delta=dl, width='small', gate=(p == 'ALL34'), pooled=p)
# B: OI walls
for label, tl, pooled in units_etf9(pools=('ETF6', 'ETF9', 'STK25', 'ALL34')):
    for sel in ('wall_beyond', 'wall_at'):
        for st in ('PCS', 'CCS', 'IC'):
            add('B', f'B_{label}_{st}_{sel}_small', tl, st, sel=sel, width='small', gate=(label != 'STK25'), pooled=pooled)
# C: IV skew signal
for label, tl, pooled in units_etf9():
    for st in ('PCS', 'CCS', 'CDS', 'PDS'):
        for sg in ('high', 'low'):
            add('C', f'C_{label}_{st}_skew{sg}', tl, st, delta=0.20, width='small', signal=('skew', sg), pooled=pooled,
                gate=st in ('PCS', 'CCS'))
# D: day-of-week entry and month-end
for label, tl, pooled in units_etf9():
    for pos in (1, 2, 3):
        for st in ('PCS', 'CCS', 'IC'):
            add('D', f'D_{label}_{st}_d0.20_small_pos{pos}', tl, st, delta=0.20, width='small', pos=pos, pooled=pooled)
for label, tl, pooled in units_etf9(per_ticker=False):
    for me in (True, False):
        for st in ('PCS', 'CCS', 'IC'):
            add('D', f'D_{label}_{st}_d0.20_small_monthend{me}', tl, st, delta=0.20, width='small',
                signal=('monthend', me), pooled=pooled)
# E: directional debit spreads, no stop, regime-conditioned
E_SIGS = [None, ('regime', 'BULL'), ('regime', 'BEAR'), ('sp', 'pos'), ('sp', 'neg')]
for label, tl, pooled in units_etf9(pools=('ETF6', 'ETF9', 'STK25', 'ALL34')):
    for st in ('CDS', 'PDS'):
        for sg in E_SIGS:
            add('E', f'E_{label}_{st}_{sg[0] + sg[1] if sg else "always"}', tl, st, gate=False, signal=sg, pooled=pooled)
# F: volume/OI unusual-activity stand-down (paired vs base A_ETF9_*_d0.20_small and H_ALL34_*_d0.20_small)
PAIRS = []
for base, tl, gate in (('ETF9', ETF9, True), ('ALL34', ALL34, True)):
    for st in ('PCS', 'CCS', 'IC'):
        for thr in (0.8, 0.9):
            add('F', f'F_{base}_{st}_d0.20_small_voloi>{thr}', tl, st, delta=0.20, width='small', gate=gate,
                signal=('voloi', thr), pooled=base)
            PAIRS.append((CONFIGS[-1]['name'], f'A_{base}_{st}_d0.20_small' if base == 'ETF9' else f'H_{base}_{st}_d0.20_small'))
# G: SPY ATM IV proxy (VIX proxy) with and instead of the BEAR gate
for st in ('PCS', 'CCS', 'IC'):
    for sg in ('high', 'low', 'abovemed'):
        add('G', f'G_ETF9_{st}_d0.20_small_spyiv{sg}', ETF9, st, delta=0.20, width='small', signal=('spyiv', sg), pooled='ETF9')
        PAIRS.append((CONFIGS[-1]['name'], f'A_ETF9_{st}_d0.20_small'))
    add('G', f'G_ETF9_{st}_d0.20_small_nogate_spyivlow', ETF9, st, delta=0.20, width='small', gate=False,
        signal=('spyiv', 'low'), pooled='ETF9')
    PAIRS.append((CONFIGS[-1]['name'], f'A_ETF9_{st}_d0.20_small'))
# T: two-week tenor (enter first day of every EVEN-indexed week, expire the following week's last trading day; no overlap)
for label, tl, pooled in units_etf9(per_ticker=False):
    for st in ('PCS', 'CCS', 'IC'):
        for dl in (0.10, 0.20):
            add('T', f'T_{label}_{st}_d{dl:.2f}_small_2wk', tl, st, delta=dl, width='small', pooled=pooled, tenor=2)
NAME2CFG = {c['name']: c for c in CONFIGS}
log(f'grid size {len(CONFIGS)}  weeks {len(WEEKS)}  {WEEKS[0]}..{WEEKS[-1]}')

# ----------------------------------------------------------------------------------------------- DATA
con = sqlite3.connect('file:search.db?mode=ro', uri=True)
con.execute('pragma busy_timeout=120000')

class Row:
    __slots__ = ('bid', 'ask', 'oi', 'vol', 'iv', 'delta')
    def __init__(self, bid, ask, oi, vol, iv, delta):
        self.bid, self.ask, self.oi, self.vol, self.iv, self.delta = bid, ask, oi, vol, iv, delta

FACTORS = {1, 2, 3, 4, 5, 10, 20}
def load_ticker(t):
    rows = con.execute('select day,exp,cp,k,vol,oi,bid,ask,iv,delta from o where t=? and day>=?', (t, WARM)).fetchall()
    snaps = {}          # day -> {exp: {'P': {k: Row}, 'C': {k: Row}}} for that ISO week's (and next week's) expiry only
    dayvol = defaultdict(float); dayoi = defaultdict(float)
    atm = {}            # day -> ((exp, |delta-0.5|), k): the delta-0.50 call of the SHORTEST expiry that day -> split factor
    for day, exp, cp, k, vol, oi, bid, ask, iv, delta in rows:
        dayvol[day] += vol or 0; dayoi[day] += oi or 0
        if cp == 'C' and delta is not None:
            key = (exp, abs(delta - 0.5))
            if day not in atm or key < atm[day][0]:
                atm[day] = (key, k)
        w = isoweek(day)
        if w in WEEK_EXP and (exp == WEEK_EXP[w] or exp == WEEK_EXP2.get(w)):
            snaps.setdefault(day, {}).setdefault(exp, {'P': {}, 'C': {}})[cp][k] = Row(bid or 0.0, ask or 0.0, oi or 0, vol or 0, iv, delta)
    # split factor per day: closes.json is split-adjusted for NFLX/XLE while strikes are not.  Raw factor = nearest of
    # FACTORS to (ATM strike / close); the day's factor is the MODE of raw factors over +-5 trading days so that a crash
    # day or an odd chain never rejects a settlement (an earlier version dropped SLV's 2026-W05 crash week this way).
    raw = {}
    for day, (key, k) in atm.items():
        px = closes.get(t, {}).get(day)
        if px is None:
            continue
        ratio = k / px[3]
        f = min(FACTORS, key=lambda x: abs(ratio - x))
        raw[day] = f if abs(ratio / f - 1) < 0.25 else None
    tdays = [d for d in cal if d in closes.get(t, {})]
    factor = {}
    for i, d in enumerate(tdays):
        win = [raw[x] for x in tdays[max(0, i - 5):i + 6] if raw.get(x) is not None]
        factor[d] = max(set(win), key=win.count) if win else None
    voloi = {d: (dayvol[d] / dayoi[d] if dayoi[d] > 0 else None) for d in dayvol}
    return snaps, factor, voloi

def settle_px(t, exp, factor):
    px = closes.get(t, {}).get(exp)
    f = factor.get(exp)
    if px is None or f is None:
        return None
    return px[3] * f

def spot_px(t, day, factor):
    px = closes.get(t, {}).get(day); f = factor.get(day)
    if px is None or f is None:
        return None
    return px[3] * f

# ----------------------------------------------------------------------------------------------- STRUCTURES
def by_delta(side, target, tol=0.05):
    best, bd = None, 9.9
    for k, r in side.items():
        if r.bid <= 0 or r.ask <= 0 or r.delta is None:
            continue
        dd = abs(abs(r.delta) - target)
        if dd < bd:
            bd, best = dd, k
    return best if bd <= tol else None

def iv_at_delta(side, target, tol=0.07):
    best, bd = None, 9.9
    for k, r in side.items():
        if r.iv is None or r.delta is None or r.bid <= 0:
            continue
        dd = abs(abs(r.delta) - target)
        if dd < bd:
            bd, best = dd, r.iv
    return best if bd <= tol else None

def wall_strike(side, cp, spot, mode):
    """largest-OI strike among OTM strikes of that side; 'wall_at' sells that strike, 'wall_beyond' the next OTM one."""
    otm = [(k, r) for k, r in side.items() if (k < spot if cp == 'P' else k > spot)]
    if not otm:
        return None
    kw = max(otm, key=lambda kr: kr[1].oi)[0]
    if mode == 'wall_at':
        return kw
    ks = sorted(k for k, r in otm if (k < kw if cp == 'P' else k > kw))
    if not ks:
        return None
    return ks[-1] if cp == 'P' else ks[0]

def intrinsic(cp, k, S):
    return max(0.0, k - S) if cp == 'P' else max(0.0, S - k)

def credit_spread(side, cp, ks, W, S):
    """short ks (fill at BID), long ks-W for puts / ks+W for calls (fill at ASK). Returns (pnl, maxloss) or ('drop', why)."""
    kl = ks - W if cp == 'P' else ks + W
    s, l = side.get(ks), side.get(kl)
    if s is None or l is None:
        cf = None
        if s is not None and s.bid > 0:
            alt = sorted(k for k, r in side.items() if (k < kl if cp == 'P' else k > kl) and r.ask > 0)
            if alt:
                ka = alt[-1] if cp == 'P' else alt[0]; la = side[ka]
                if s.bid - la.ask > 0:
                    cf = ((s.bid - la.ask) - (intrinsic(cp, ks, S) - intrinsic(cp, ka, S))) * 100
        return ('drop', 'longstrike_missing', cf)
    if s.bid <= 0 or l.ask <= 0:
        return ('drop', 'zero_quote')
    cr = s.bid - l.ask
    if cr <= 0:
        return ('drop', 'no_credit')
    LEGS.append(dict(cp=cp, short_k=ks, short_bid=s.bid, short_ask=s.ask, short_delta=s.delta, long_k=kl, long_bid=l.bid, long_ask=l.ask, credit=round(cr, 3)))
    pnl = (cr - (intrinsic(cp, ks, S) - intrinsic(cp, kl, S))) * 100
    return (pnl, W * 100 - cr * 100)

def debit_spread(side, cp, kl, ks, S):
    """long kl (fill at ASK), short ks (fill at BID)."""
    l, s = side.get(kl), side.get(ks)
    if l is None or s is None:
        return ('drop', 'strike_missing')
    if l.ask <= 0 or s.bid <= 0:
        return ('drop', 'zero_quote')
    db = l.ask - s.bid
    if db <= 0:
        return ('drop', 'no_debit')
    LEGS.append(dict(cp=cp, long_k=kl, long_ask=l.ask, short_k=ks, short_bid=s.bid, debit=round(db, 3)))
    pnl = ((intrinsic(cp, kl, S) - intrinsic(cp, ks, S)) - db) * 100
    return (pnl, db * 100)

LEGS = []
def structure(cfg, t, snap, S, spot):
    LEGS.clear()
    st = cfg['struct']
    if st in ('PCS', 'CCS', 'IC'):
        out = []
        for cp in (('P',) if st == 'PCS' else ('C',) if st == 'CCS' else ('P', 'C')):
            side = snap[cp]
            W = width_for(t, spot, cfg['width'])
            if cfg['sel'] == 'delta':
                ks = by_delta(side, cfg['delta'])
                if ks is None:
                    return ('drop', 'short_delta_missing')
            else:
                ks = wall_strike(side, cp, spot, cfg['sel'])
                if ks is None:
                    return ('drop', 'wall_missing')
            r = credit_spread(side, cp, ks, W, S)
            if r[0] == 'drop':
                return r
            out.append(r)
        if st == 'IC':
            pnl = out[0][0] + out[1][0]
            Wd = width_for(t, spot, cfg['width']) * 100
            credit = sum(Wd - ml for _, ml in out)      # back out total credit; only one side can finish ITM
            return (pnl, Wd - credit)
        return out[0]
    if st in ('CDS', 'PDS'):
        cp = 'C' if st == 'CDS' else 'P'
        side = snap[cp]
        kl = by_delta(side, 0.50); ks = by_delta(side, 0.25)
        if kl is None or ks is None:
            return ('drop', 'debit_delta_missing')
        if (cp == 'C' and not kl < ks) or (cp == 'P' and not kl > ks):
            return ('drop', 'debit_order')
        return debit_spread(side, cp, kl, ks, S)
    raise ValueError(st)

# ----------------------------------------------------------------------------------------------- SIGNALS
SPYIV = {}       # day -> SPY ATM iv (call delta ~0.5, week expiry)
def trailing_rank(series_days, values, day, lookback=60, minn=30):
    """values: dict day->float over trading days. Returns percentile rank (0..1) of value[day] within the prior `lookback` days."""
    i = series_days.index(day)
    prior = [values[d] for d in series_days[max(0, i - lookback):i] if values.get(d) is not None]
    v = values.get(day)
    if v is None or len(prior) < minn:
        return None
    return sum(1 for p in prior if p <= v) / len(prior)

def signal_ok(sig, t, day, w, sigs):
    kind, arg = sig
    if kind == 'monthend':
        return MONTHEND[w] == arg
    if kind == 'regime':
        r = regime.get(day)
        if r is None: return None
        return r['regime'] == arg
    if kind == 'sp':
        r = regime.get(day)
        if r is None: return None
        return (r['sp'] > 0) if arg == 'pos' else (r['sp'] < 0)
    if kind == 'skew':
        rk = sigs['skew_rank'].get(day)
        if rk is None: return None
        return rk >= 2 / 3 if arg == 'high' else rk <= 1 / 3
    if kind == 'voloi':
        rk = sigs['voloi_rank'].get(day)
        if rk is None: return None
        return rk <= arg           # stand down when ratio is in the top (1-arg) of its trailing history
    if kind == 'spyiv':
        rk = sigs['spyiv_rank'].get(day)
        if rk is None: return None
        if arg == 'high': return rk >= 2 / 3
        if arg == 'low': return rk <= 1 / 3
        return rk >= 0.5
    raise ValueError(kind)

# ----------------------------------------------------------------------------------------------- RUN
RES = defaultdict(dict)          # cfg id -> {(t, w): pnl}
MAXLOSS = defaultdict(float)
SKIPS = defaultdict(int)         # signal / gate stand-downs (not periods)
DROPS = defaultdict(lambda: defaultdict(int))
TRADES = defaultdict(int)
STANDCF = defaultdict(list)    # counterfactual P&L of gate/signal stand-down weeks (diagnostic)
DROPCF = defaultdict(list)     # counterfactual P&L of longstrike_missing weeks using the nearest wider long strike (diagnostic)
DETAIL_NAMES = set(os.environ.get('DETAIL', '').split(',')) - {''}
DETAIL = defaultdict(list)
def drop(cfg, why, t, w):
    DROPS[cfg['id']][why] += 1
    if cfg['name'] in DETAIL_NAMES:
        DETAIL[cfg['name']].append(dict(t=t, week=f'{w[0]}-W{w[1]:02d}', dropped=why))
cfg_by_ticker = defaultdict(list)
for c in CONFIGS:
    for t in c['tickers']:
        cfg_by_ticker[t].append(c)

order = ['SPY'] + [t for t in ALL34 if t != 'SPY']      # SPY first: its ATM iv feeds sub-family G
if os.environ.get('TICKERS'):
    order = ['SPY'] + [t for t in os.environ['TICKERS'].split(',') if t != 'SPY']
spyiv_rank = {}
for t in order:
    snaps, factor, voloi = load_ticker(t)
    days = [d for d in cal if d in snaps and WEEK_EXP[isoweek(d)] in snaps[d]]
    skew = {}
    for d in days:
        sn = snaps[d][WEEK_EXP[isoweek(d)]]
        pi = iv_at_delta(sn['P'], 0.25); ci = iv_at_delta(sn['C'], 0.25)
        skew[d] = (pi - ci) if (pi is not None and ci is not None) else None
    sigs = {'skew_rank': {d: trailing_rank(days, skew, d) for d in days},
            'voloi_rank': {d: trailing_rank(cal, voloi, d) for d in days}}
    if t == 'SPY':
        for d in days:
            SPYIV[d] = iv_at_delta(snaps[d][WEEK_EXP[isoweek(d)]]['C'], 0.50, tol=0.10)
        spyiv_rank = {d: trailing_rank(days, SPYIV, d) for d in days}
    sigs['spyiv_rank'] = spyiv_rank
    nf = sum(1 for d in days if factor.get(d) not in (1, None))
    for w in WEEKS:
        S1 = settle_px(t, WEEK_EXP[w], factor)
        S2 = settle_px(t, WEEK_EXP2[w], factor) if w in WEEK_EXP2 else None
        for cfg in cfg_by_ticker[t]:
            wd = WEEK_DAYS[w]
            if cfg['tenor'] == 2:
                if WIDX[w] % 2 == 1:
                    continue
                if w not in WEEK_EXP2:
                    drop(cfg, 'no_next_week', t, w); continue
                exp, S = WEEK_EXP2[w], S2
            else:
                exp, S = WEEK_EXP[w], S1
            if cfg['pos'] >= len(wd):
                drop(cfg, 'no_such_day', t, w); continue
            d = wd[cfg['pos']]
            snap = snaps.get(d, {}).get(exp)
            if snap is None:
                drop(cfg, 'no_chain', t, w); continue
            skipped = False
            if cfg['gate'] and regime.get(d, {}).get('regime') == 'BEAR':
                SKIPS[cfg['id']] += 1; skipped = True
            if not skipped and cfg['signal'] is not None:
                ok = signal_ok(cfg['signal'], t, d, w, sigs)
                if ok is None:
                    drop(cfg, 'no_signal', t, w); continue
                if not ok:
                    SKIPS[cfg['id']] += 1; skipped = True
            if S is None:
                drop(cfg, 'no_settle', t, w); continue
            spot = spot_px(t, d, factor)
            if spot is None:
                drop(cfg, 'no_spot', t, w); continue
            r = structure(cfg, t, snap, S, spot)
            if r[0] == 'drop':
                if skipped:
                    continue
                if len(r) > 2 and r[2] is not None:
                    DROPCF[cfg['id']].append(r[2])
                drop(cfg, r[1], t, w); continue
            pnl, ml = r
            if cfg['name'] in DETAIL_NAMES:
                DETAIL[cfg['name']].append(dict(t=t, week=f'{w[0]}-W{w[1]:02d}', entry=d, exp=exp, spot=round(spot, 2),
                    settle=round(S, 2), pnl=round(pnl, 2), maxloss=round(ml, 2), gated=skipped,
                    regime=regime.get(d, {}).get('regime'), reg=regime.get(d, {}).get('reg'), legs=list(LEGS)))
            if skipped:
                STANDCF[cfg['id']].append(pnl)
                continue
            if ml > 1000.0 + 1e-9:
                drop(cfg, 'maxloss>1000', t, w); continue
            RES[cfg['id']][(t, w)] = pnl
            MAXLOSS[cfg['id']] = max(MAXLOSS[cfg['id']], ml)
            TRADES[cfg['id']] += 1
    log(f'{t}: days {len(days)} split-factor days {nf}  voloi ok {sum(1 for d in days if sigs["voloi_rank"][d] is not None)}')
    del snaps

# ----------------------------------------------------------------------------------------------- METRICS
TW = [(t, w) for t in ALL34 for w in WEEKS]
TWIDX = {tw: i for i, tw in enumerate(TW)}
C = len(CONFIGS)
M_week = np.full((C, len(WEEKS)), np.nan)
M_tw = np.full((C, len(TW)), np.nan)
for cid, d in RES.items():
    for (t, w), p in d.items():
        i = WIDX[w]
        M_week[cid, i] = (0.0 if np.isnan(M_week[cid, i]) else M_week[cid, i]) + p
        M_tw[cid, TWIDX[(t, w)]] = p

def tstat_rows(M):
    n = np.sum(~np.isnan(M), axis=1)
    mean = np.nanmean(M, axis=1)
    sd = np.nanstd(M, axis=1, ddof=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        t = mean / (sd / np.sqrt(n))
    return t, n, mean

def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 2 or np.std(x, ddof=1) == 0:
        return 0.0
    return float(np.mean(x) / (np.std(x, ddof=1) / math.sqrt(len(x))))

def metrics(cid):
    row = M_week[cid]; mask = ~np.isnan(row)
    wk = [(WEEKS[i], row[i]) for i in np.where(mask)[0]]
    x = np.array([p for _, p in wk])
    tw = M_tw[cid][~np.isnan(M_tw[cid])]
    m = {'n_periods': int(len(x)), 'n_ticker_weeks': int(len(tw)), 'total': float(x.sum()) if len(x) else 0.0}
    if len(x) < 2:
        m.update(per_period=0.0, t_week=0.0, t_tw=0.0, t_min=0.0, halves=[0, 0], quarters={}, q_pos='0/0',
                 worst_period=0.0, max_dd=0.0, max_loss_per_contract=MAXLOSS[cid], loo_t=0.0, loo_total=0.0,
                 stand_downs=SKIPS[cid], drops=dict(DROPS[cid]))
        return m
    m['per_period'] = float(x.mean()); m['per_ticker_week'] = float(tw.mean())
    m['t_week'] = tstat(x); m['t_tw'] = tstat(tw); m['t_min'] = min(m['t_week'], m['t_tw'])
    h = len(x) // 2
    m['halves'] = [float(x[:h].sum()), float(x[h:].sum())]
    q = defaultdict(float)
    for (w, p) in wk:
        q[quarter(WEEK_DAYS[w][0])] += p
    m['quarters'] = {k: round(v, 1) for k, v in sorted(q.items())}
    m['q_pos'] = f'{sum(1 for v in q.values() if v > 0)}/{len(q)}'
    m['worst_period'] = float(x.min())
    cum = np.cumsum(x); m['max_dd'] = float((np.maximum.accumulate(cum) - cum).max())
    m['max_loss_per_contract'] = float(MAXLOSS[cid])
    xl = np.delete(x, int(np.argmax(x)))
    m['loo_t'] = tstat(xl); m['loo_total'] = float(xl.sum())
    m['win_rate'] = float((tw > 0).mean())
    m['stand_downs'] = int(SKIPS[cid]); m['drops'] = {k: int(v) for k, v in DROPS[cid].items()}
    sc, dc = STANDCF[cid], DROPCF[cid]
    m['standdown_counterfactual'] = {'n': len(sc), 'total': float(sum(sc)), 'worst': float(min(sc)) if sc else 0.0}
    m['dropped_week_counterfactual'] = {'n': len(dc), 'total': float(sum(dc)), 'worst': float(min(dc)) if dc else 0.0}
    m['all_weather_total'] = float(x.sum() + sum(sc) + sum(dc))
    # mechanical tail flag: a short-premium series whose worst traded period never approached its max loss
    m['tail_flag'] = bool(m['win_rate'] >= 0.95 and m['worst_period'] > -0.25 * m['max_loss_per_contract']
                          and m['max_loss_per_contract'] > 0)
    return m

log('computing metrics')
MET = {c['id']: metrics(c['id']) for c in CONFIGS}
t_week_all, n_week_all, _ = tstat_rows(M_week)
elig = np.array([MET[i]['n_periods'] >= MIN_N for i in range(C)])
log(f'eligible configs (n>={MIN_N}): {elig.sum()} of {C}')

# ----------------------------------------------------------------------------------------------- PERMUTATION BAR
rng = np.random.default_rng(SEED)
def perm_bar(M, elig_mask, nflip=NFLIP):
    Me = M[elig_mask]
    if Me.shape[0] == 0:
        return float('nan'), float('nan')
    maxes = np.empty(nflip)
    for i in range(nflip):
        F = rng.choice([-1.0, 1.0], size=M.shape[1])
        t, n, _ = tstat_rows(Me * F)
        t = np.where(n >= 2, t, 0.0)
        maxes[i] = np.nanmax(np.abs(t)) if t.size else np.nan
    return float(np.percentile(maxes, 95)), float(np.percentile(maxes, 50))

def perm_bar_sub(M, mask):
    if mask.sum() == 0:
        return None
    return perm_bar(M, mask)[0]

log('permutation: week clustering')
bar_week, med_week = perm_bar(M_week, elig)
log(f'  bar_week (95th pct of max|t| over {elig.sum()} configs, {NFLIP} flips) = {bar_week:.3f}   median max = {med_week:.3f}')
log('permutation: ticker-week clustering')
bar_tw, med_tw = perm_bar(M_tw, elig)
log(f'  bar_tw = {bar_tw:.3f}   median max = {med_tw:.3f}')
SUBBARS = {}
for sub in sorted(set(c['sub'] for c in CONFIGS)):
    mask = elig & np.array([c['sub'] == sub for c in CONFIGS])
    SUBBARS[sub] = {'n_configs': int(mask.sum()), 'bar_week': perm_bar_sub(M_week, mask), 'bar_tw': perm_bar_sub(M_tw, mask)}
    log(f'  sub {sub}: {SUBBARS[sub]}')

# ----------------------------------------------------------------------------------------------- PAIRED (F, G vs base)
log('paired differences')
PAIRED = []
P_rows = []
for fname, bname in PAIRS:
    f, b = NAME2CFG[fname]['id'], NAME2CFG[bname]['id']
    base = RES[b]; filt = RES[f]
    diff = {}
    for tw_, p in base.items():
        diff[tw_] = filt.get(tw_, 0.0) - p            # skipped periods = flat
    dw = defaultdict(float)
    for (t, w), p in diff.items():
        dw[w] += p
    xs = np.array([dw[w] for w in WEEKS if w in dw])
    row = np.full(len(WEEKS), np.nan)
    for w, v in dw.items():
        row[WIDX[w]] = v
    P_rows.append(row)
    PAIRED.append({'filtered': fname, 'base': bname, 'n_periods': int(len(xs)), 'diff_total': float(xs.sum()),
                   'diff_per_period': float(xs.mean()) if len(xs) else 0.0, 'diff_t_week': tstat(xs),
                   'filtered_total': MET[f]['total'], 'base_total': MET[b]['total'],
                   'filtered_t_min': MET[f]['t_min'], 'base_t_min': MET[b]['t_min'],
                   'filtered_stand_downs': MET[f]['stand_downs']})
P = np.array(P_rows)
bar_paired = perm_bar(P, np.ones(len(P_rows), bool))[0] if len(P_rows) else None
log(f'  paired bar (week clustering, {len(P_rows)} pairs) = {bar_paired}')

# ----------------------------------------------------------------------------------------------- VERDICTS
def verdict(cid):
    m = MET[cid]
    if m['n_periods'] < MIN_N:
        return False, f'n={m["n_periods"]} < {MIN_N}'
    why = []
    if m['per_period'] <= 0: why.append('mean<=0')
    if not (m['t_week'] > bar_week): why.append(f't_week {m["t_week"]:.2f} <= bar {bar_week:.2f}')
    if not (m['t_tw'] > bar_tw): why.append(f't_tw {m["t_tw"]:.2f} <= bar {bar_tw:.2f}')
    if not (m['halves'][0] > 0 and m['halves'][1] > 0): why.append(f'halves {m["halves"]}')
    qp, qn = map(int, m['q_pos'].split('/'))
    need = 8 if qn >= 10 else 6 if qn >= 7 else qn - 1
    if qp < need: why.append(f'quarters {m["q_pos"]} < {need}')
    if not (m['loo_total'] > 0 and m['loo_t'] > 1.5): why.append(f'loo_t {m["loo_t"]:.2f}')
    if m['max_loss_per_contract'] > 1000: why.append('maxloss>1000')
    return (len(why) == 0), ('PASS' if not why else '; '.join(why))

out_c = []
for c in CONFIGS:
    ok, why = verdict(c['id'])
    spec = {k: c[k] for k in ('sub', 'tickers', 'struct', 'sel', 'delta', 'width', 'pos', 'gate', 'signal', 'pooled', 'tenor')}
    spec['entry'] = 'close of trading day index pos (0=first day) of ISO week; expiry = last trading day of that week (tenor 2: of the next week, entries on even-indexed weeks only); ' \
                    'fills: short@bid long@ask; settle at expiry close (split-factor corrected) intrinsic'
    spec['widths_$'] = ETF_WIDTHS if any(t in ETF_WIDTHS for t in c['tickers']) else 'stock rule: <60:1, <150:2.5, <400:5, else 10'
    spec['delta_tolerance'] = 0.05; spec['debit_legs'] = 'long |delta| 0.50, short |delta| 0.25'
    spec['signal_windows'] = 'skew/voloi/spyiv: trailing 60 trading days, >=30 required; terciles 1/3, 2/3'
    out_c.append({'name': c['name'], 'spec': spec, 'metrics': MET[c['id']], 'passes_search_bar': ok, 'why_or_why_not': why})

ranked = sorted(out_c, key=lambda r: -r['metrics']['t_min'])
log('TOP 25 by min(t_week, t_tw):')
for r in ranked[:25]:
    m = r['metrics']
    log(f"  {r['name']:<45} n={m['n_periods']:3d} tot={m['total']:9.0f} pp={m['per_period']:7.1f} tw={m['t_week']:5.2f} "
        f"ttw={m['t_tw']:5.2f} halves={[round(h) for h in m['halves']]} q={m['q_pos']} loo={m['loo_t']:5.2f} "
        f"wr={m.get('win_rate', 0):.2f} ml={m['max_loss_per_contract']:.0f} | {r['why_or_why_not']}")
log('PAIRED (filters vs base):')
for p in PAIRED:
    log(f"  {p['filtered']:<45} diff/period={p['diff_per_period']:7.1f} t={p['diff_t_week']:5.2f} (bar {bar_paired:.2f}) "
        f"base_total={p['base_total']:.0f} filt_total={p['filtered_total']:.0f} standdowns={p['filtered_stand_downs']}")

passes = [r for r in out_c if r['passes_search_bar']]
SUBDESC = {'A': 'ETF/index short premium by delta (PCS/CCS/IC, 0.10/0.20/0.30, two widths, BEAR gate)',
           'B': 'open-interest walls (short strike at / just beyond the largest-OI strike)',
           'C': 'put/call IV skew tercile signal (credit and debit spreads)',
           'D': 'day-of-week entry (2nd/3rd/4th day -> Friday) and month-end weeks',
           'E': 'directional debit spreads, no stop, regime/20d-conditioned',
           'F': 'volume/OI unusual-activity stand-down filter (paired vs base)',
           'G': 'SPY ATM-IV (VIX proxy) filter with / instead of the BEAR gate (paired vs base)',
           'H': 'single-stock (25) and all-34 pooled short premium',
           'T': 'two-week tenor ETF short premium (non-overlapping)'}
dead_ends = []
for sub in sorted(SUBDESC):
    cs = [r for r in out_c if r['spec']['sub'] == sub and r['metrics']['n_periods'] >= MIN_N]
    if not cs:
        continue
    best = max(cs, key=lambda r: r['metrics']['t_min']); bm = best['metrics']
    npos = sum(1 for r in cs if r['metrics']['per_period'] > 0)
    npass = sum(1 for r in cs if r['passes_search_bar'])
    ntail = sum(1 for r in cs if r['passes_search_bar'] and r['metrics']['tail_flag'])
    dead_ends.append(f"{sub} {SUBDESC[sub]}: {len(cs)} eligible configs, {npos} with positive mean, {npass} clear the bar "
                     f"({ntail} of those carry the tail-absent flag); best min-t {bm['t_min']:.2f} = {best['name']} "
                     f"(${bm['total']:.0f} over {bm['n_periods']} periods, win rate {bm['win_rate']:.2f}, worst period "
                     f"${bm['worst_period']:.0f}, max loss ${bm['max_loss_per_contract']:.0f}, stand-down counterfactual "
                     f"${bm['standdown_counterfactual']['total']:.0f}, dropped-week counterfactual ${bm['dropped_week_counterfactual']['total']:.0f}).")
for p_ in PAIRED:
    p_['clears_paired_bar'] = bool(p_['diff_t_week'] > bar_paired and p_['diff_per_period'] > 0)
notes = ('DATA: closes.json is split-adjusted for NFLX (10:1) and XLE (2:1) while option strikes are not; settlement here uses '
         'close x split factor (mode over +-5 days of the shortest-expiry delta-0.50 call strike / close). Any family settling '
         'NFLX or XLE from closes.json directly is wrong. '
         'TAIL FLAG: every config that clears the numeric bar is a 0.10-delta put credit spread with >=95% wins whose worst traded '
         'week never came near its max loss; their stand-down (BEAR-gated) and dropped-week counterfactuals are reported and are '
         'of the same size as, or larger than, the traded profit. The t-statistic of a binary-payoff series whose losing branch did '
         'not fire in-sample is not evidence of edge, and the sign-flip permutation bar cannot detect this because flips of a '
         'near-constant series produce ordinary |t|. '
         'DROPS: the top-500-by-volume cap removes far-OTM long legs most often on tickers with M/W/F expiries (SLV, GLD, TLT); '
         'the drop rule (never substitute) removed SLV 2026-W05 (-23.5% week) and SMH 2024-W31 (-8.4%, pre-period) from the '
         'put-spread series. dropped_week_counterfactual re-prices those weeks with the nearest wider long strike, diagnostic only. '
         'ELIGIBILITY: configs with fewer than 20 periods are ineligible and excluded from the permutation grid.')
result = {'family': 'F_wildcard', 'grid_size': len(CONFIGS), 'eligible_configs': int(elig.sum()),
          'weeks': len(WEEKS), 'search_period': [START, END], 'n_flips': NFLIP, 'seed': SEED,
          'permutation_bar': {'week': bar_week, 'ticker_week': bar_tw, 'median_max_week': med_week, 'median_max_tw': med_tw,
                              'by_subfamily': SUBBARS, 'paired': bar_paired},
          'n_pass': len(passes),
          'candidates': ranked,
          'paired': PAIRED,
          'dead_ends': dead_ends, 'notes': notes}
json.dump(result, open('F_wildcard_results.json', 'w'), indent=1, default=float)
if DETAIL:
    json.dump(DETAIL, open('F_wildcard_detail.json', 'w'), indent=1, default=float)
log(f'WROTE F_wildcard_results.json  passes={len(passes)}')

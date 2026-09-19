#!/usr/bin/env python
# FAMILY E - TIME STRUCTURE.  Reproducible: runs end to end from /tmp/research/.
# Reads ONLY search.db (table o), closes.json, regime.json.  Executable prices only (sell@bid, buy@ask).
import sqlite3, json, datetime as dt, math, collections, sys, time, os
import numpy as np

os.chdir('/tmp/research')
CLOSES = json.load(open('closes.json'))
REG = json.load(open('regime.json'))
START, END = '2024-07-22', '2026-03-13'     # continuous chain data AND regime coverage
NPERM, SEED = 500, 20260918
OUT = 'time_structure_results.json'
T0 = time.time()

def log(*a):
    print(f"[{time.time()-T0:7.1f}s]", *a, flush=True)

def d2(s): return dt.date.fromisoformat(s)
def s2(d): return d.isoformat()
def isoweek(s):
    y, w, _ = d2(s).isocalendar(); return f"{y}-W{w:02d}"
def quarter(s):
    d = d2(s); return f"{d.year}Q{(d.month-1)//3+1}"
def month(s): return s[:7]
def monday_of(s):
    d = d2(s); return d - dt.timedelta(d.weekday())
def third_friday(y, m):
    d = dt.date(y, m, 15)
    while d.weekday() != 4: d += dt.timedelta(1)
    return d
def close_of(t, day):
    b = CLOSES.get(t, {}).get(day); return b[3] if b else None     # [o,h,l,c,v] -> close
def is_bear(day):
    r = REG.get(day); return None if r is None else (r['regime'] == 'BEAR')
def intrinsic(cp, k, c): return max(k - c, 0.0) if cp == 'P' else max(c - k, 0.0)

# ---------------------------------------------------------------- data
class Chain:
    def __init__(self, t):
        self.t = t
        c = sqlite3.connect('file:search.db?mode=ro', uri=True); c.execute('pragma busy_timeout=120000')
        self.q = collections.defaultdict(dict)       # (day,exp,cp) -> {k:(bid,ask,delta)}
        days = set()
        for day, exp, cp, k, bid, ask, delta in c.execute(
                "select day,exp,cp,k,bid,ask,delta from o where t=? and day>=? and day<=?", (t, START, END)):
            self.q[(day, exp, cp)][k] = (bid, ask, delta); days.add(day)
        c.close()
        self.days = sorted(days)
        self.dayset = set(self.days)
        self.exps = collections.defaultdict(set)       # day -> set of exps listed that day
        for (day, exp, cp) in self.q: self.exps[day].add(exp)
        self.weeks = collections.defaultdict(list)     # isoweek -> trading days
        for d in self.days: self.weeks[isoweek(d)].append(d)
        log(f"{t}: {sum(len(v) for v in self.q.values()):,} quotes, {len(self.days)} days, {len(self.weeks)} weeks")
    def quote(self, day, exp, cp, k):
        return self.q.get((day, exp, cp), {}).get(k)
    def bid(self, day, exp, cp, k):        # SELL price
        r = self.quote(day, exp, cp, k); return r[0] if r and r[0] > 0 and r[1] >= r[0] else None
    def ask(self, day, exp, cp, k):        # BUY price
        r = self.quote(day, exp, cp, k); return r[1] if r and r[1] > 0 and r[1] >= r[0] else None
    def week_expiry(self, day, iso_monday):
        """the weekly expiry of the ISO week starting iso_monday, as listed on `day`: Friday, else Thursday."""
        for off in (4, 3):
            e = s2(iso_monday + dt.timedelta(off))
            if e in self.exps.get(day, ()): return e
        return None
    def delta_strike(self, day, exp, cp, target, grid=None, tol=0.05):
        ch = self.q.get((day, exp, cp), {})
        best, bd = None, 9
        for k, (b, a, dl) in ch.items():
            if grid and abs(k / grid - round(k / grid)) > 1e-9: continue
            if b <= 0 or a <= 0 or dl is None: continue
            d = abs(abs(dl) - target)
            if d < bd: best, bd = k, d
        return best if bd <= tol else None
    def next_days(self, day):
        i = self.days.index(day); return self.days[i+1:]

def rec(cfg, t, entry, exit_, pnl, maxloss, extra=None):
    r = dict(cfg=cfg, t=t, entry=entry, exit=exit_, wk=isoweek(entry), tw=f"{t}|{isoweek(entry)}",
             xm=month(exit_), q=quarter(entry), pnl=round(pnl, 2), maxloss=round(maxloss, 2))
    if extra: r.update(extra)
    return r

DROPS = collections.Counter()        # (cfg, reason) -> n
def drop(cfg, why): DROPS[(cfg, why)] += 1

# ---------------------------------------------------------------- sub-family 1: calendars / diagonals
def run_calendars(ch):
    t = ch.t; out = collections.defaultdict(list)
    for w, wdays in sorted(ch.weeks.items()):
        e = wdays[0]
        if e < START: continue
        spot = close_of(t, e)
        if spot is None: continue
        mon = monday_of(e)
        for cp in ('P', 'C'):
            for near_w in (0, 1):
                near = ch.week_expiry(e, mon + dt.timedelta(7 * near_w))
                for far_n in (2, 4, 6):
                    for srule in ('ATM5', 'D30', 'DIAG'):
                        if srule == 'DIAG' and far_n == 6: continue
                        cfg = f"CAL|{t}|{cp}|near{near_w}w|far+{far_n}w|{srule}"
                        if is_bear(e) is not False: drop(cfg, 'bear_gate' if is_bear(e) else 'no_regime'); continue
                        if near is None: drop(cfg, 'no_near_expiry'); continue
                        far = s2(d2(near) + dt.timedelta(7 * far_n))
                        if far not in ch.exps.get(e, ()): drop(cfg, 'far_expiry_not_listed'); continue
                        atm5 = round(spot / 5) * 5
                        if srule == 'ATM5': ks = kl = atm5
                        elif srule == 'D30':
                            ks = ch.delta_strike(e, near, cp, 0.30); kl = ks
                        else:
                            ks = ch.delta_strike(e, near, cp, 0.30); kl = atm5
                        if ks is None: drop(cfg, 'no_30d_strike'); continue
                        bn = ch.bid(e, near, cp, ks); af = ch.ask(e, far, cp, kl)
                        if bn is None or af is None: drop(cfg, 'strike_missing_entry'); continue
                        debit = af - bn
                        if debit <= 0: drop(cfg, 'nonpositive_debit'); continue
                        if near not in ch.dayset: drop(cfg, 'near_expiry_day_missing'); continue
                        c_e = close_of(t, near)
                        bf = ch.bid(near, far, cp, kl)
                        if c_e is None or bf is None: drop(cfg, 'far_leg_no_bid_at_exit'); continue
                        pnl = (-debit - intrinsic(cp, ks, c_e) + bf) * 100
                        ml = (debit + (max(0, ks - kl) if cp == 'P' else max(0, kl - ks))) * 100
                        out[cfg].append(rec(cfg, t, e, near, pnl, ml, dict(ks=ks, kl=kl, debit=round(debit, 2))))
    return out

# ---------------------------------------------------------------- sub-family 2: short-DTE put credit spreads
TENORS = {'MonWed': (0, 2), 'TueWed': (1, 1), 'WedFri': (2, 2), 'ThuFri': (3, 1), 'FriMon': (4, 3)}
WIDTHS = {'SPY': (5, 10), 'QQQ': (5, 10), 'IWM': (2, 5)}
def run_shortdte(ch):
    t = ch.t; out = collections.defaultdict(list)
    for e in ch.days:
        if e < START: continue
        wd = d2(e).weekday()
        for tenor, (ewd, off) in TENORS.items():
            if wd != ewd: continue
            exp = s2(d2(e) + dt.timedelta(off))
            for dl in (0.10, 0.20, 0.30):
                for width in WIDTHS[t]:
                    cfg = f"SDTE|{t}|{tenor}|d{int(dl*100)}|w{width}"
                    if is_bear(e) is not False: drop(cfg, 'bear_gate' if is_bear(e) else 'no_regime'); continue
                    if exp not in ch.exps.get(e, ()): drop(cfg, 'expiry_not_listed'); continue
                    if exp not in ch.dayset: drop(cfg, 'expiry_day_missing'); continue
                    ks = ch.delta_strike(e, exp, 'P', dl)
                    if ks is None: drop(cfg, 'no_delta_strike'); continue
                    kl = ks - width
                    bs = ch.bid(e, exp, 'P', ks); al = ch.ask(e, exp, 'P', kl)
                    if bs is None or al is None: drop(cfg, 'long_strike_missing'); continue
                    credit = bs - al
                    if credit <= 0: drop(cfg, 'nonpositive_credit'); continue
                    c_x = close_of(t, exp)
                    if c_x is None: drop(cfg, 'no_settle_close'); continue
                    pnl = (credit - intrinsic('P', ks, c_x) + intrinsic('P', kl, c_x)) * 100
                    out[cfg].append(rec(cfg, t, e, exp, pnl, (width - credit) * 100, dict(ks=ks, kl=kl, credit=round(credit, 2))))
    return out

# ---------------------------------------------------------------- sub-family 3: 30-45 DTE managed at 21 DTE
GRID = {'SPY': 5, 'QQQ': 5, 'IWM': 1}
def run_dte45(ch):
    t = ch.t; out = collections.defaultdict(list); paired = collections.defaultdict(list)
    for w, wdays in sorted(ch.weeks.items()):
        e = wdays[0]
        if e < START: continue
        ed = d2(e)
        cands = []
        for mo in range(0, 3):
            y, m = ed.year, ed.month + mo
            while m > 12: m -= 12; y += 1
            f = third_friday(y, m); dte = (f - ed).days
            if 28 <= dte <= 56: cands.append((abs(dte - 45), f))
        for dl in (0.16, 0.30):
            for width in WIDTHS[t]:
                base = f"DTE45|{t}|d{int(dl*100)}|w{width}"
                cfgs = {arm: f"{base}|{arm}" for arm in ('HOLD', 'M21', 'TP50')}
                def dropall(why):
                    for c in cfgs.values(): drop(c, why)
                if is_bear(e) is not False: dropall('bear_gate' if is_bear(e) else 'no_regime'); continue
                if not cands: dropall('no_monthly_in_window'); continue
                exp = s2(min(cands)[1])
                if exp not in ch.exps.get(e, ()): dropall('expiry_not_listed'); continue
                if exp > END or exp not in ch.dayset: dropall('expiry_beyond_data'); continue
                ks = ch.delta_strike(e, exp, 'P', dl, grid=GRID[t])
                if ks is None: dropall('no_delta_strike'); continue
                kl = ks - width
                bs = ch.bid(e, exp, 'P', ks); al = ch.ask(e, exp, 'P', kl)
                if bs is None or al is None: dropall('long_strike_missing'); continue
                credit = bs - al
                if credit <= 0: dropall('nonpositive_credit'); continue
                c_x = close_of(t, exp)
                if c_x is None: dropall('no_settle_close'); continue
                hold = (credit - intrinsic('P', ks, c_x) + intrinsic('P', kl, c_x)) * 100
                # path: daily closes after entry until the 21-DTE day
                m21_day = m21_cost = None; tp_day = tp_cost = None
                for d in ch.next_days(e):
                    if d > exp: break
                    dte = (d2(exp) - d2(d)).days
                    a_s = ch.ask(d, exp, 'P', ks); b_l = ch.bid(d, exp, 'P', kl)
                    cost = (a_s - b_l) if (a_s is not None and b_l is not None) else None
                    if tp_day is None and cost is not None and cost <= 0.5 * credit:
                        tp_day, tp_cost = d, cost
                    if dte <= 21:
                        if cost is None: break
                        m21_day, m21_cost = d, cost; break
                if m21_day is None: dropall('no_quote_on_21dte_day'); continue
                if tp_day is None: tp_day, tp_cost = m21_day, m21_cost
                m21 = (credit - m21_cost) * 100; tp = (credit - tp_cost) * 100
                ml = (width - credit) * 100
                out[cfgs['HOLD']].append(rec(cfgs['HOLD'], t, e, exp, hold, ml, dict(ks=ks, kl=kl, credit=round(credit, 2))))
                out[cfgs['M21']].append(rec(cfgs['M21'], t, e, m21_day, m21, ml, dict(ks=ks, kl=kl, credit=round(credit, 2))))
                out[cfgs['TP50']].append(rec(cfgs['TP50'], t, e, tp_day, tp, ml, dict(ks=ks, kl=kl, credit=round(credit, 2))))
                paired[f"PAIR|{base}|M21-HOLD"].append(rec(f"PAIR|{base}|M21-HOLD", t, e, exp, m21 - hold, ml))
                paired[f"PAIR|{base}|TP50-HOLD"].append(rec(f"PAIR|{base}|TP50-HOLD", t, e, exp, tp - hold, ml))
    return out, paired

# ---------------------------------------------------------------- sub-family 4: roll timing on the live weekly rule
ENTRIES = ('Mon0', 'Fri-1', 'Wed-1', 'Mon-1')
STRIKES = ((2, 4), (2, 3), (1, 2))
def run_roll(ch):
    t = ch.t; out = collections.defaultdict(list); paired = collections.defaultdict(list)
    weeks = sorted(ch.weeks)
    for i, w in enumerate(weeks):
        wdays = ch.weeks[w]; mon = monday_of(wdays[0])
        prev = ch.weeks.get(weeks[i-1]) if i > 0 else None
        entry_day = {'Mon0': wdays[0], 'Fri-1': prev[-1] if prev else None,
                     'Mon-1': prev[0] if prev else None,
                     'Wed-1': next((d for d in (prev or []) if d2(d).weekday() == 2), None)}
        for (so, lo) in STRIKES:
            res = {}
            for en in ENTRIES:
                cfg = f"ROLL|{t}|{en}|{so}/{lo}"
                e = entry_day[en]
                if e is None or e < START: drop(cfg, 'no_entry_day'); continue
                if is_bear(e) is not False: drop(cfg, 'bear_gate' if is_bear(e) else 'no_regime'); continue
                exp = ch.week_expiry(e, mon)
                if exp is None: drop(cfg, 'expiry_not_listed'); continue
                if exp not in ch.dayset: drop(cfg, 'expiry_day_missing'); continue
                spot = close_of(t, e)
                if spot is None: drop(cfg, 'no_spot'); continue
                ks, kl = round(spot * (1 - so / 100)), round(spot * (1 - lo / 100))
                bs = ch.bid(e, exp, 'P', ks); al = ch.ask(e, exp, 'P', kl)
                if bs is None or al is None: drop(cfg, 'strike_missing'); continue
                credit = bs - al
                if credit <= 0: drop(cfg, 'nonpositive_credit'); continue
                c_x = close_of(t, exp)
                if c_x is None: drop(cfg, 'no_settle_close'); continue
                pnl = (credit - intrinsic('P', ks, c_x) + intrinsic('P', kl, c_x)) * 100
                ml = (ks - kl - credit) * 100
                r = rec(cfg, t, e, exp, pnl, ml, dict(ks=ks, kl=kl, credit=round(credit, 2)))
                r['wk'] = w; r['tw'] = f"{t}|{w}"; r['q'] = quarter(exp)      # period = expiry week
                out[cfg].append(r); res[en] = (pnl, ml)
            if 'Mon0' in res:
                for en in ENTRIES[1:]:
                    if en in res:
                        pc = f"PAIR|ROLL|{t}|{en}-Mon0|{so}/{lo}"
                        r = rec(pc, t, wdays[0], wdays[-1], res[en][0] - res['Mon0'][0], max(res[en][1], res['Mon0'][1]))
                        r['wk'] = w; r['tw'] = f"{t}|{w}"; r['q'] = quarter(wdays[-1]); paired[pc].append(r)
    return out, paired

# ---------------------------------------------------------------- statistics
def ctstat(x, keys):
    idx = {k: i for i, k in enumerate(sorted(set(keys)))}; G = len(idx)
    if G < 2 or len(x) < 2: return float('nan')
    ci = np.array([idx[k] for k in keys])
    S = np.bincount(ci, weights=x - x.mean(), minlength=G)
    v = (S ** 2).sum() * G / (G - 1)
    return float(x.sum() / math.sqrt(v)) if v > 0 else float('nan')

def metrics(recs):
    recs = sorted(recs, key=lambda r: (r['entry'], r['t']))
    x = np.array([r['pnl'] for r in recs]); n = len(x)
    if n < 2: return dict(n=n, total=float(x.sum()) if n else 0.0)
    t_wk = ctstat(x, [r['wk'] for r in recs]); t_tw = ctstat(x, [r['tw'] for r in recs]); t_xm = ctstat(x, [r['xm'] for r in recs])
    vals = [v for v in (t_wk, t_tw, t_xm) if not math.isnan(v)]
    t_dec = min(vals) if vals else float('nan')
    h = n // 2; h1, h2 = float(x[:h].sum()), float(x[h:].sum())
    qs = collections.OrderedDict()
    for r in recs: qs[r['q']] = qs.get(r['q'], 0.0) + r['pnl']
    qpos = sum(1 for v in qs.values() if v > 0); Q = len(qs)
    qneed = Q - 1 if Q <= 7 else math.ceil(0.8 * Q)
    ib = int(np.argmax(x)); xl = np.delete(x, ib); kl = [r['wk'] for j, r in enumerate(recs) if j != ib]
    loo_t = ctstat(xl, kl); loo_mean = float(xl.mean())
    cum = np.cumsum(x); dd = float((np.maximum.accumulate(cum) - cum).max())
    wins = float((x > 0).mean())
    return dict(n=n, total=round(float(x.sum()), 2), per_period=round(float(x.mean()), 2), sd=round(float(x.std(ddof=1)), 2),
                win_rate=round(wins, 3), t_week=round(t_wk, 2), t_tickerweek=round(t_tw, 2), t_exitmonth=round(t_xm, 2),
                t_decision=round(t_dec, 2), half1=round(h1, 2), half2=round(h2, 2),
                quarters={k: round(v, 2) for k, v in qs.items()}, quarters_pos=f"{qpos}/{Q}", quarters_need=qneed,
                worst=round(float(x.min()), 2), best=round(float(x.max()), 2), max_drawdown=round(dd, 2),
                max_loss_per_contract=round(max(r['maxloss'] for r in recs), 2),
                loo_mean=round(loo_mean, 2), loo_t=round(loo_t, 2),
                weeks=len(set(r['wk'] for r in recs)), first=recs[0]['entry'], last=recs[-1]['entry'])

def perm_bar(configs, nperm=NPERM, seed=SEED):
    """95th pct of max |t_decision| across the grid under week-level sign flips (same flips for every config)."""
    allweeks = sorted({r['wk'] for recs in configs.values() for r in recs}); widx = {w: i for i, w in enumerate(allweeks)}
    rng = np.random.default_rng(seed); signs = rng.choice([-1.0, 1.0], size=(nperm, len(allweeks)))
    prepared = []
    for cfg, recs in configs.items():
        if len(recs) < 2: continue
        x = np.array([r['pnl'] for r in recs]); wi = np.array([widx[r['wk']] for r in recs])
        cl = []
        for key in ('wk', 'tw', 'xm'):
            ks = [r[key] for r in recs]; idx = {k: i for i, k in enumerate(sorted(set(ks)))}
            if len(idx) >= 2: cl.append((np.array([idx[k] for k in ks]), len(idx)))
        prepared.append((x, wi, cl))
    maxt = np.zeros(nperm)
    for p in range(nperm):
        best = 0.0
        for x, wi, cl in prepared:
            xs = x * signs[p, wi]; xc = xs - xs.mean(); tot = xs.sum(); tmin = None
            for ci, G in cl:
                S = np.bincount(ci, weights=xc, minlength=G); v = (S ** 2).sum() * G / (G - 1)
                if v > 0:
                    tv = tot / math.sqrt(v)
                    tmin = tv if tmin is None else min(tmin, tv)     # decision stat = min over clusterings
            if tmin is not None and abs(tmin) > best: best = abs(tmin)
        maxt[p] = best
    return float(np.percentile(maxt, 95)), float(np.median(maxt)), float(maxt.max())

def judge(m, bar):
    why = []
    if m.get('n', 0) < 2: return False, ['n<2']
    if not m['per_period'] > 0: why.append('mean<=0')
    if not (m['t_decision'] > bar): why.append(f"t_decision {m['t_decision']} <= bar {bar:.2f}")
    if not (m['half1'] > 0 and m['half2'] > 0): why.append(f"halves {m['half1']}/{m['half2']}")
    qp = int(m['quarters_pos'].split('/')[0])
    if qp < m['quarters_need']: why.append(f"quarters {m['quarters_pos']} need {m['quarters_need']}")
    if not (m['loo_mean'] > 0 and m['loo_t'] > 1.5): why.append(f"leave-one-out t {m['loo_t']}")
    if m['max_loss_per_contract'] > 1000: why.append(f"max loss ${m['max_loss_per_contract']} > $1000")
    return (len(why) == 0), why

def spec_of(cfg):
    p = cfg.split('|')
    base = dict(entry_price='close NBBO of entry day; sell legs at BID, buy legs at ASK', settlement='expiry-day close, intrinsic (cash)', regime_gate='skip entry if regime.json[entry_day].regime == BEAR', same_day_close='never', contracts=1)
    if p[0] == 'CAL':
        return dict(base, structure='calendar/diagonal', ticker=p[1], side=p[2], entry='first trading day of ISO week, at close',
                    near_expiry=f"weekly expiry of ISO week +{p[3][4]} (Fri, else Thu)", far_expiry=f"near expiry + {p[4][4]} weeks exactly (drop if not listed)",
                    strike=dict(ATM5='both legs at round(spot/5)*5', D30='both legs at the near-expiry strike with |delta| nearest 0.30 (within 0.05)', DIAG='short near leg at |delta|~0.30, long far leg at round(spot/5)*5')[p[5]],
                    exit='hold to near expiry: near leg settles at intrinsic, far leg SOLD at its BID that day (drop if no bid)', max_loss='debit + adverse strike gap')
    if p[0] == 'SDTE':
        ewd, off = TENORS[p[2]]
        return dict(base, structure='put credit spread', ticker=p[1], entry_weekday=['Mon','Tue','Wed','Thu','Fri'][ewd], expiry=f"entry + {off} calendar days (must be listed that day)",
                    short_strike=f"strike with |delta| nearest {int(p[3][1:])/100} (within 0.05)", long_strike=f"short - {p[4][1:] if p[1]!='POOL3' else 'narrow(SPY/QQQ $5, IWM $2) or wide(SPY/QQQ $10, IWM $5)'} (drop if missing)", exit='hold to expiry, cash settle at close')
    if p[0] == 'DTE45':
        return dict(base, structure='put credit spread 30-45 DTE', ticker=p[1], entry='first trading day of ISO week, at close', expiry='3rd-Friday monthly with DTE in [28,56] nearest 45',
                    short_strike=f"strike on the ${GRID[p[1]]} grid with |delta| nearest {int(p[2][1:])/100} (within 0.05)", long_strike=f"short - ${p[3][1:]}",
                    management=dict(HOLD='hold to expiry, settle intrinsic', M21='close at first daily close with DTE<=21: buy short at ASK, sell long at BID', TP50='close at first daily close (after entry day) where ASK(short)-BID(long) <= 50% of credit, else M21')[p[4]],
                    pairing_note='a week is dropped from ALL arms if the 21-DTE day lacks either quote')
    if p[0] == 'ROLL':
        ent = {'Mon0': 'first trading day of expiry ISO week (live base)', 'Fri-1': 'last trading day of the prior ISO week', 'Wed-1': 'Wednesday of the prior ISO week', 'Mon-1': 'first trading day of the prior ISO week'}
        return dict(base, structure='weekly put credit spread (live CREDIT_SPREAD_W rule)', ticker=p[1], entry=ent[p[2]],
                    expiry='weekly expiry of the ISO week (Fri, else Thu)', short_strike=f"round(spot*(1-{p[3].split('/')[0]}/100))", long_strike=f"round(spot*(1-{p[3].split('/')[1]}/100))", exit='hold to expiry, settle intrinsic', period='expiry week')
    if p[0] == 'PAIR':
        if p[1] == 'DTE45': arms = spec_of('|'.join(p[1:5] + ['HOLD']))
        else: arms = spec_of('|'.join(['ROLL', p[2], 'Mon0', p[4]]))
        return dict(paired_difference=cfg, note='per-period P&L of the variant minus the base on the SAME periods; judged against the paired permutation bar', base_arm=arms)
    return dict(raw=cfg)


# ---------------------------------------------------------------- adversarial verdicts (written after reading the per-trade records)
VERDICTS = {
 'SDTE|SPY|MonWed|d10|w10': (False, "REJECTED as a sample-selection artifact: 28 weeks, 100% wins, worst +$16, against $984 max loss. The $10-wide long strike is in the top-500 chain on only 28 of the 66 Mondays; the sibling SDTE|SPY|MonWed|d10|w5 has the IDENTICAL short leg on 50 weeks and contains the breach (2024-12-16, -$483 on a $0.17 credit) that the w10 subset dropped for a missing long strike. 0/28 breaches on a 10-delta strike is a 5% event even at the nominal 10% breach rate. The t of 16 measures the absence of the tail in the subset, not an edge."),
 'DTE45|QQQ|d30|w10|TP50': (False, "REJECTED under protocol rule 6: a 50%-take-profit is a management rule, so the decision statistic is the PAIRED difference against HOLD on the same 48 trades: -$58.58/trade, t -1.75, 1/7 quarters positive (PAIR|DTE45|QQQ|d30|w10|TP50-HOLD). The level t 5.68 is the truncation artifact of 2026-09-17 again: TP50 cuts the three -$800 March-2025 trades to +$119/+$108/-$277 and collapses the variance; HOLD itself is +$120/trade at t 1.93 (fails the bar). Same verdict for every DTE45 arm: all 24 paired M21-HOLD / TP50-HOLD differences are <= +$11.5 and 20 of 24 are negative."),
 'ROLL|QQQ|Wed-1|2/3': (False, "REJECTED: it modifies the live entry day, so rule 6 governs: PAIR|ROLL|QQQ|Wed-1-Mon0|2/3 is +$115/wk at t 2.78 against the paired bar 3.22 (n=22). The level t 5.3386 sits ON the level bar 5.34 (passes by <0.001), on 24 of 75 weeks (51 dropped because the 2%/3% strikes for next week's expiry are rarely in the Wednesday top-500 chain). The QQQ Mon0 2/3 base is -$22/wk t -1.28, so 'better than base' here means 'not as negative'."),
 'SDTE|IWM|FriMon|d10|w5': (True, "CLEARS the pre-registered bar (t 6.52 > 5.34, halves +276/+388, 7/7 quarters, LOO t 6.9, max loss $495) and has a documented mechanism (weekend variance overpricing: Jones & Shemesh 2018, option returns are negative over non-trading periods; in this data every one of 18 FriMon cells shows the same credit as ThuFri at the same delta but a breach rate 1/2 to 1/6 as high). RED FLAGS the verifier must weigh: (a) the t is a tail-absence statistic: 64 wins of $5-18 and ONE loss of -$79 in 65 weekends; mean $10.22 against $495 max loss means one full breach erases ~48 weekends; (b) on 2024-08-05 (the carry-unwind Monday, NOT gated: regime MILD) the short 202 strike survived by $0.35 (close 202.35, intraday low 196.82 = 2.6% through the strike) while the SPY and QQQ siblings that weekend took -$339/-$480; (c) the honest pooled estimate of the same weekend edge (SDTE|POOL3|FriMon|d10|narrow, 195 trades, 4 breaches) is +$8.13/trade at t 1.89, 5/7 quarters - far below the bar; (d) a 26-weekend holdout has no power against a 1-in-50 tail, so a holdout 'pass' would not be evidence the tail is priced; (e) IWM options are physically settled: a close between the strikes assigns 100 IWM shares (~$25k notional) to a $5k account. Expected income ~$430/contract/year (43 tradeable weekends x $10)."),
 'PAIR|ROLL|SPY|Fri-1-Mon0|2/3': (True, "CLEARS the paired bar by a thin margin (t 3.38 vs 3.22; +$33.56/wk on 48 shared weeks, 7/7 quarters, LOO t 3.69, worst week -$22). Mechanism is the same weekend premium plus strike placement: Friday entry collects $55 vs $46 average credit, and in weeks where Monday rallied then reversed the Monday-set strikes were breached while Friday's were not (2024-W51 +$303, 2025-W02 +$363 = 41% of the total; removing both leaves +$20.5/wk). CAVEATS: the same modification at the LIVE width 2/4 is +$3.42/wk t 0.10 (n=33) and at 1/2 is +$22.9 t 1.69; on QQQ 2/3 it is +$36.8 t 1.75 and on IWM 2/3 +$7.8 t 1.40 - positive in 8 of 9 ticker-x-width cells but clearing the bar in one. The Fri-1 2/3 LEVEL series (+$31.2/wk, t 2.57) does not clear the level bar 5.34 and the Mon0 2/3 base is +$18/wk t 1.50, so this is 'a better entry day for a rule that is itself unproven on executable prices'. Second half +$451/24wk vs first +$1,160/24wk. On XSP (live instrument, 1/10 size) the gain is ~$3.4/wk."),
}
DEAD_ENDS = [
 "CALENDARS / DIAGONALS (64 single-ticker + 32 pooled SPY+QQQ configs, gated): nothing clears. Best cells are tiny-n artifacts: CAL|SPY|P|near1w|far+4w|D30 n=6 t 4.03; CAL|QQQ|P|near0w|far+2w|D30 n=15 t 2.83. Every put-calendar cell with n>=20 is between -$76 and +$94/trade with t <= 2.41 (SPY P near0w far+4w ATM5: +$94 n=24 t 2.41, the best real one). Call calendars/diagonals are negative in most cells (SPY C near1w far+2w DIAG -$178/trade t -2.93). The data cannot support this sub-family: the top-500-by-volume cap leaves the far expiry with $5 strikes at best, so 30-60 of ~75 weeks per config are dropped for a missing strike at entry or a missing far-leg bid at exit. Even if a signal existed it would be unmeasurable here.",
 "SHORT-DTE PUT CREDIT SPREADS, mid-week tenors (Mon->Wed, Tue->Wed, Wed->Fri, Thu->Fri; 72 single + 24 pooled cells): Wed->Fri is NEGATIVE in all 18 cells (SPY -$10 to -$24/trade, QQQ -$9 to -$31, IWM -$6 to -$15; 1-3 of 7 quarters positive). Thu->Fri is ~zero (-$10 to +$12, |t| < 0.9): the breach rate at a 10-delta strike is 8.7-10.1%, i.e. the 1-DTE put is priced correctly. Mon->Wed and Tue->Wed are mildly positive (+$1 to +$40/trade, t 0.0-1.9) and clear nothing. Selling 1-2 DTE index put premium mid-week has no edge on executable prices.",
 "30-45 DTE PUT CREDIT SPREADS MANAGED AT 21 DTE or 50% PROFIT (36 arms, 24 paired differences on SPY/QQQ/IWM at 16 and 30 delta, $5/$10 or $2/$5 wide): the retail rule is a dead end on executable prices. Every paired M21-HOLD and TP50-HOLD difference is <= +$11.5/trade and 20 of 24 are negative (SPY d30 w10: M21 -$32.5 t -1.06, TP50 -$35.4; QQQ d30 w10: M21 -$58.2 t -1.99, TP50 -$58.6 t -1.75; IWM d30 w2: M21 -$13.3 t -1.64). Managing early pays the bid-ask twice and gives back the last 21 days of theta, which is where most of the credit is. HOLD itself does not clear either: SPY d30 w10 +$87/trade t 1.18 (halves +$235/+$4,397); QQQ d30 w10 +$120 t 1.93; all HOLD cells are 6/7 or fewer quarters and the March-2025 selloff costs three overlapping trades ~$800 each. 45-DTE credit is also badly served by this chain: 5-17 weeks per config dropped because the 21-DTE day lacks a quote on one leg.",
 "ROLL TIMING on the live weekly rule (36 level, 27 paired): Wed-1 (9 DTE) and Mon-1 (11 DTE) entries drop 45-67 of 75 weeks because the 2%/4% strikes for next week's Friday are seldom in the top-500 chain that early; their paired differences are noise (t -1.04 to +2.78, n 5-30). The 1/2 strike rule loses on every ticker at Mon0 (SPY -$29/wk t -1.55, QQQ -$28 t -1.09). At the live 2/4 width, SPY Mon0 is +$52/wk t 4.22 (6/7 quarters) but its max loss is $1,367 per SPY contract (over the cap; $137 on XSP) and t 4.22 < bar 5.34; QQQ Mon0 2/4 is -$5.45/wk. The Friday-entry direction is positive in 8 of 9 ticker x width cells but only SPY 2/3 clears (see candidates).",
 "POOLED 3-ticker weekend cells (the honest estimate of the Fri->Mon effect): d10 narrow +$8.13/trade t 1.89 (195 trades, 4 breaches, 5/7 quarters); d20 narrow +$19.3 t 2.53 (5/7); d20 wide +$27.1 t 2.52; d30 narrow +$24.0 t 2.18; d30 wide +$36.1 t 2.21; d10 wide +$10.3 t 1.55. Consistent sign, none within 2.8 t-units of the 288-config bar. The negative quarters are the ones holding the two non-gated gap Mondays: 2024-08-05 (carry unwind, IWM -3.2%, SPY/QQQ d10 spreads -$339/-$480) and 2025-01-27 (DeepSeek, QQQ d10 -$480).",
]
NOTES = ("Window 2024-07-22..2026-03-13 (the earliest day with continuous chain data AND regime coverage; the 2023 fragments in search.db have no regime and were not used). "
 "All configs sell index premium so the BEAR stand-down (regime.json, D-1) was applied to every entry; 9-11 entries per config were gated. "
 "Decision t = min over {entry-week, ticker-week, exit-month} cluster-robust t; the exit-month clustering is what stops the overlapping 45-DTE trades from counting the March-2025 drawdown three times. "
 "Permutation: 500 ISO-week sign flips shared across the grid, statistic = the same min-t; level bar 5.34 over 288 configs (median max|t| 3.34) - the bar is high because many cells have 90-100% win rates on tiny credits, which produce extreme t under flips too; paired bar 3.22 over 51 configs. "
 "Two numeric passes were rejected on protocol rule 6 (paired test for a modified rule) and one as a sample-selection artifact; the reasons and the sibling numbers are in each candidate. "
 "THE ONE STRUCTURAL FINDING: Friday-close to Monday-close index put spreads earn the same credit as Thursday-to-Friday at the same delta, but breach 1/2 to 1/6 as often (18 of 18 cells; e.g. SPY d10 w5 credit $16.6 vs $18.1, breach 3.1% vs 10.1%; QQQ d10 w5 $18.9 vs $19.3, 1.6% vs 8.7%; IWM d10 w5 $11.6 vs $12.6, 1.5% vs 8.7%). This is the published weekend-overpricing effect, and it is the only thing in this family with a mechanism. Its size after the tail is $8-36 per contract per weekend, and its risk is the Monday gap that a 20-month sample contains twice. "
 "A pre-registered follow-up on the six pooled weekend cells alone (bar ~2.5 for a 6-config grid) on data neither this study nor the verifier has used would be the honest next test; shrinking the grid after the fact to pass them is exactly what the protocol forbids and was not done. "
 "Commissions are not modelled (Alpaca options are commission-free; regulatory fees ~$0.05/contract). Physical settlement/assignment on IWM/SPY/QQQ is modelled as cash intrinsic at the close.")

def annotate(cands):
    for c in cands:
        v = VERDICTS.get(c['name'])
        if v:
            c['passes_search_bar'] = v[0]; c['verdict'] = v[1]

# ---------------------------------------------------------------- main
def main():
    level = {}; paired = {}
    for t in ('SPY', 'QQQ', 'IWM'):
        ch = Chain(t)
        if t in ('SPY', 'QQQ'):
            level.update(run_calendars(ch)); log(f"{t} calendars done")
        level.update(run_shortdte(ch)); log(f"{t} short-DTE done")
        a, b = run_dte45(ch); level.update(a); paired.update(b); log(f"{t} 45-DTE done")
        a, b = run_roll(ch); level.update(a); paired.update(b); log(f"{t} roll timing done")
        del ch
        for cfg in sorted(level):
            if f"|{t}|" in cfg:
                m = metrics(level[cfg]); dr = {k[1]: v for k, v in DROPS.items() if k[0] == cfg}
                log(f"  {cfg:42s} n={m.get('n',0):3d} $/p={m.get('per_period','-')} t={m.get('t_decision','-')} halves={m.get('half1','-')}/{m.get('half2','-')} q={m.get('quarters_pos','-')} maxloss={m.get('max_loss_per_contract','-')} drops={dr}")
    # pooled 3-ticker short-DTE configs (ticker-week clustering matters here)
    pooled = collections.defaultdict(list)
    for cfg, recs in list(level.items()):
        if cfg.startswith('SDTE|'):
            parts = cfg.split('|'); t = parts[1]; wtag = parts[4]
            wclass = ('narrow' if wtag == 'w2' else 'wide') if t == 'IWM' else ('narrow' if wtag == 'w5' else 'wide')
            pooled[f"SDTE|POOL3|{parts[2]}|{parts[3]}|{wclass}"] += recs
    level.update(pooled)
    cpool = collections.defaultdict(list)
    for cfg, recs in list(level.items()):
        if cfg.startswith('CAL|'):
            p = cfg.split('|'); cpool[f"CAL|POOL2|{p[2]}|{p[3]}|{p[4]}|{p[5]}"] += recs
    level.update(cpool)
    level = {k: v for k, v in level.items() if len(v) >= 2}; paired = {k: v for k, v in paired.items() if len(v) >= 2}
    log(f"grid: {len(level)} level configs, {len(paired)} paired configs; computing permutation bars ...")
    bar_l, med_l, max_l = perm_bar(level); log(f"LEVEL permutation bar (95th pct max|t| over {len(level)} configs, {NPERM} week-flips): {bar_l:.4f} (median {med_l:.2f}, max {max_l:.2f})")
    bar_p, med_p, max_p = perm_bar(paired); log(f"PAIRED permutation bar over {len(paired)} configs: {bar_p:.4f} (median {med_p:.2f}, max {max_p:.2f})")
    cands = []
    for grp, cfgs, bar in (('level', level, bar_l), ('paired', paired, bar_p)):
        for cfg, recs in sorted(cfgs.items()):
            m = metrics(recs); ok, why = judge(m, bar)
            drops = {k[1]: v for k, v in DROPS.items() if k[0] == cfg}
            cands.append(dict(name=cfg, group=grp, spec=spec_of(cfg), metrics=m, drops=drops,
                              passes_search_bar=ok, why_or_why_not=('PASSES search bar' if ok else '; '.join(why))))
    def sk(c):
        v = c['metrics'].get('t_decision'); return -(v if v == v else -99)
    cands.sort(key=sk)
    annotate(cands)
    res = dict(family='E - TIME STRUCTURE (calendars/diagonals, short-DTE overnight put credit spreads, 30-45 DTE managed at 21, roll timing)',
               data=dict(search_db_window=[START, END], executable='sell@bid buy@ask, settle at expiry close intrinsic', regime_gate='BEAR stand-down (regime.json, D-1) on every config: all sell index premium'),
               grid_size=len(level), paired_grid_size=len(paired), permutation_bar=round(bar_l, 3), paired_permutation_bar=round(bar_p, 3),
               permutation=dict(nperm=NPERM, seed=SEED, flips='ISO-week sign flips shared across the grid', statistic='min over {week, ticker-week, exit-month} cluster-robust t', median_max_t=round(med_l, 3), max_max_t=round(max_l, 3)),
               candidates=cands, dead_ends=DEAD_ENDS, notes=NOTES)
    json.dump(res, open(OUT, 'w'), indent=1)
    log(f"wrote {OUT}")
    passing = [c for c in cands if c['passes_search_bar']]
    log(f"PASSING: {len(passing)}")
    for c in passing: log("  PASS", c['name'], c['metrics'])
    log("top 25 by t_decision:")
    for c in cands[:25]:
        m = c['metrics']; log(f"  {c['name']:48s} n={m['n']} $/p={m['per_period']} t={m['t_decision']} h={m['half1']}/{m['half2']} q={m['quarters_pos']} loo={m['loo_t']} ml={m['max_loss_per_contract']} :: {c['why_or_why_not']}")

if __name__ == '__main__':
    main()

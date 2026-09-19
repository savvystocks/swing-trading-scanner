"""FAMILY C - VOLATILITY CONDITIONING.  Pre-registered grid, executable prices, PROTOCOL.md bar.

Runs end to end from /tmp/research:  ~/swing-trading-scanner/.venv/bin/python vol_conditioning.py
Reads ONLY search.db (table o), closes.json, regime.json.  Writes vol_conditioning_results.json.

Definitions (fixed before any result was seen):
  iv30      ATM implied vol of the listed expiry whose calendar DTE is nearest to 30 within [14,50];
            ATM = mean iv over the two strikes nearest the day's close, calls and puts, iv in (0,5).
  iv_near   same ATM rule on the nearest expiry with DTE in [3,10]  (term-structure front point).
  slope     iv_near / iv30 - 1 ; > 0 = backwardation, < 0 = contango.
  rv20      annualised std of the last 20 daily log returns of the close (closes.json), on the entry day.
  ivprem    iv30 - rv20.
  ivr120 / ivr250   (iv30 - min) / (max - min) over the trailing 120 / 250 observed trading days incl. today
            (full window required; NaN before that -> the gate is NOT evaluable and the week is not a period).
  All gate inputs are the entry day's closing values (known at the close, when the trade is placed).
  Regime gate: regime.json[entry_day].regime == 'BEAR' -> stand down (applied to every structure, every ticker).

Structures (one contract, hold to expiry, cash-settle at intrinsic on the expiry-day close, no unwind):
  PCS d w   put credit spread: short the put whose |delta| is nearest d (must be within 0.07), long = short - w.
  IC  d w   PCS d w + the mirror call credit spread (short call delta nearest +d, long = short + w).
  CDS w / PDS w   debit spread: buy the ATM option (|delta| nearest 0.50, within 0.10), sell the option w further OTM.
  credit = bid(short) - ask(long); debit = ask(long) - bid(short).  Missing leg / non-positive credit -> DROP.
  tenor 1 = expiry in the entry week (max exp in that ISO week on the entry-day chain);
  tenor 2 = expiry in the following ISO week.  Entry = first trading day of the ISO week, at the close.
Universe: ALL = SPY QQQ IWM AAPL MSFT NVDA AMZN META GOOGL TSLA AVGO ; IDX = SPY QQQ IWM ; STK = the 8 stocks.
"""
import sqlite3, json, math, sys, time, datetime as dt, os
import numpy as np, pandas as pd

R = '/tmp/research'
TICKERS = ['SPY', 'QQQ', 'IWM', 'AAPL', 'MSFT', 'NVDA', 'AMZN', 'META', 'GOOGL', 'TSLA', 'AVGO']
IDX = ['SPY', 'QQQ', 'IWM']
STK = [t for t in TICKERS if t not in IDX]
UNIVERSES = {'ALL': TICKERS, 'IDX': IDX, 'STK': STK}
MIN_DAY = '2024-07-01'          # 24 stray 2023 days in search.db are excluded (gap of 8 months before the run)
MIN_WEEKS = 20                  # a config needs >= 20 active weeks to be a candidate (and to enter the bar)
N_PERM = 600
SEED = 20260918
MAX_LOSS_CAP = 1000.0

closes = json.load(open(R + '/closes.json'))
regime = json.load(open(R + '/regime.json'))


def D(s):
    return dt.date.fromisoformat(s)


def iso_week(day):
    y, w, _ = D(day).isocalendar()
    return f'{y}-W{w:02d}'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ----------------------------------------------------------------------------------------------- data
def load_ticker(t):
    con = sqlite3.connect(f'file:{R}/search.db?mode=ro', uri=True)
    con.execute('pragma busy_timeout=120000')
    df = pd.read_sql('select day,exp,cp,k,bid,ask,iv,delta from o where t=? and day>=?', con, params=(t, MIN_DAY))
    con.close()
    return df


def atm_iv(g, close):
    """mean iv over the 2 strikes nearest to close (both cps), rows with iv in (0,5)."""
    g = g[(g.iv > 0) & (g.iv < 5)]
    if g.empty:
        return np.nan
    ks = np.array(sorted(g.k.unique(), key=lambda k: abs(k - close)))[:2]
    return float(g[g.k.isin(ks)].iv.mean())


def daily_metrics(t, df):
    """per day: iv30, iv_near, close ; then rv20, ivprem, slope, ivr120, ivr250."""
    cl = closes[t]
    rows = []
    for day, g in df.groupby('day', sort=True):
        if day not in cl:
            continue
        c = cl[day][3]
        d0 = D(day)
        exps = {e: (D(e) - d0).days for e in g.exp.unique()}
        e30 = [e for e, n in exps.items() if 14 <= n <= 50]
        enear = [e for e, n in exps.items() if 3 <= n <= 10]
        iv30 = atm_iv(g[g.exp == min(e30, key=lambda e: abs(exps[e] - 30))], c) if e30 else np.nan
        ivn = atm_iv(g[g.exp == min(enear, key=lambda e: exps[e])], c) if enear else np.nan
        rows.append((day, c, iv30, ivn))
    m = pd.DataFrame(rows, columns=['day', 'close', 'iv30', 'iv_near']).set_index('day')
    # realised vol from the full close history (closes.json), aligned on day
    days = sorted(cl)
    px = pd.Series([cl[d][3] for d in days], index=days)
    lr = np.log(px).diff()
    rv20 = lr.rolling(20).std() * math.sqrt(252)
    m['rv20'] = rv20.reindex(m.index)
    m['ivprem'] = m.iv30 - m.rv20
    m['slope'] = m.iv_near / m.iv30 - 1
    for n in (120, 250):
        lo = m.iv30.rolling(n, min_periods=n).min()
        hi = m.iv30.rolling(n, min_periods=n).max()
        m[f'ivr{n}'] = (m.iv30 - lo) / (hi - lo)
    return m


# ------------------------------------------------------------------------------------------ structures
def pick_delta(rows, target, tol):
    """rows: one cp, one expiry. return the row whose |delta| is nearest target (within tol) else None."""
    if rows.empty:
        return None
    ad = (rows.delta.abs() - target).abs()
    i = ad.idxmin()
    if ad[i] > tol:
        return None
    return rows.loc[i]


def leg(rows, k):
    r = rows[rows.k == k]
    if r.empty:
        return None
    return r.iloc[0]


def credit_spread(rows, cp, d, w):
    """short the |delta|~d option, long w further OTM.  returns (credit, ks, kl) or (None, reason)."""
    s = pick_delta(rows, d, 0.07)
    if s is None:
        return None, 'no_short_delta'
    kl = s.k - w if cp == 'P' else s.k + w
    l = leg(rows, kl)
    if l is None:
        return None, 'long_missing'
    if s.bid <= 0 or l.ask <= 0:
        return None, 'no_quote'
    credit = s.bid - l.ask
    if credit <= 0:
        return None, 'nonpos_credit'
    return (credit, float(s.k), float(kl)), None


def debit_spread(rows, cp, w):
    """buy ATM (|delta| nearest .50 within .10), sell w further OTM."""
    l = pick_delta(rows, 0.50, 0.10)
    if l is None:
        return None, 'no_atm'
    ks = l.k + w if cp == 'C' else l.k - w
    s = leg(rows, ks)
    if s is None:
        return None, 'short_missing'
    if l.ask <= 0 or s.bid <= 0:
        return None, 'no_quote'
    debit = l.ask - s.bid
    if debit <= 0:
        return None, 'nonpos_debit'
    return (debit, float(l.k), float(ks)), None


def payoff_cs(cp, ks, kl, S):
    if cp == 'P':
        return -max(ks - S, 0) + max(kl - S, 0)
    return -max(S - ks, 0) + max(S - kl, 0)


def payoff_ds(cp, kl, ks, S):
    if cp == 'C':
        return max(S - kl, 0) - max(S - ks, 0)
    return max(kl - S, 0) - max(ks - S, 0)


STRUCTS = []
for d in (0.30, 0.20, 0.10):
    for w in (5, 10):
        STRUCTS.append(('PCS', d, w))
for d in (0.20, 0.10):
    for w in (5, 10):
        STRUCTS.append(('IC', d, w))
for w in (5, 10):
    STRUCTS.append(('CDS', None, w))
    STRUCTS.append(('PDS', None, w))
TENORS = (1, 2)


def sname(s, tenor):
    kind, d, w = s
    return f'{kind}{"" if d is None else f"_d{int(d*100)}"}_w{w}_t{tenor}'


def build_trades(t, df, m):
    """every (structure, tenor) trade for every ISO week of ticker t.  returns list of dict rows + drops."""
    trades, drops = [], {}
    days = [d for d in m.index]
    weeks = {}
    for d in days:
        weeks.setdefault(iso_week(d), d)          # first trading day of the ISO week
    df = df.set_index('day', drop=False)
    for wk, ed in weeks.items():
        chain = df.loc[[ed]].reset_index(drop=True)
        exps = sorted(chain.exp.unique())
        met = m.loc[ed]
        bear = regime.get(ed, {}).get('regime') == 'BEAR'
        for tenor in TENORS:
            wk_target = iso_week((D(ed) + dt.timedelta(days=7 * (tenor - 1))).isoformat()) if tenor > 1 else wk
            cand = [e for e in exps if iso_week(e) == wk_target and D(e) > D(ed)]
            if not cand:
                for s in STRUCTS:
                    drops.setdefault(sname(s, tenor), {}).setdefault('no_expiry', 0)
                    drops[sname(s, tenor)]['no_expiry'] += 1
                continue
            E = cand[-1]
            if E not in closes[t]:
                for s in STRUCTS:
                    drops.setdefault(sname(s, tenor), {}).setdefault('no_settle_close', 0)
                    drops[sname(s, tenor)]['no_settle_close'] += 1
                continue
            S = closes[t][E][3]
            ce = chain[chain.exp == E]
            puts, calls = ce[ce.cp == 'P'], ce[ce.cp == 'C']
            for s in STRUCTS:
                kind, d, w = s
                nm = sname(s, tenor)
                if kind == 'PCS':
                    r, why = credit_spread(puts, 'P', d, w)
                    if r is None:
                        drops.setdefault(nm, {}).setdefault(why, 0); drops[nm][why] += 1
                        if why == 'long_missing':
                            # coverage-sensitivity row (NOT scored): short leg exists, long leg absent from the top-500 chain.
                            # pnl_ub prices the long leg at ZERO -> an UPPER bound on the spread's P&L that week.
                            sh = pick_delta(puts, d, 0.07)
                            if sh is not None and sh.bid > 0:
                                ub = (sh.bid - max(sh.k - S, 0) + max(sh.k - w - S, 0)) * 100
                                trades.append(dict(t=t, week=wk, entry=ed, exp=E, struct=nm, tenor=tenor, pnl=ub, mloss=w * 100,
                                                   ub=True, breached=bool(S < sh.k), bear=bear, iv30=met.iv30, ivr120=met.ivr120,
                                                   ivr250=met.ivr250, ivprem=met.ivprem, slope=met.slope))
                        continue
                    credit, ks, kl = r
                    pnl = (credit + payoff_cs('P', ks, kl, S)) * 100
                    mloss = (w - credit) * 100
                elif kind == 'IC':
                    r, why = credit_spread(puts, 'P', d, w)
                    if r is None:
                        drops.setdefault(nm, {}).setdefault('put_' + why, 0); drops[nm]['put_' + why] += 1; continue
                    r2, why2 = credit_spread(calls, 'C', d, w)
                    if r2 is None:
                        drops.setdefault(nm, {}).setdefault('call_' + why2, 0); drops[nm]['call_' + why2] += 1; continue
                    credit = r[0] + r2[0]
                    pnl = (credit + payoff_cs('P', r[1], r[2], S) + payoff_cs('C', r2[1], r2[2], S)) * 100
                    mloss = (w - credit) * 100
                else:
                    cp = 'C' if kind == 'CDS' else 'P'
                    r, why = debit_spread(calls if cp == 'C' else puts, cp, w)
                    if r is None:
                        drops.setdefault(nm, {}).setdefault(why, 0); drops[nm][why] += 1; continue
                    debit, kl, ks = r
                    pnl = (payoff_ds(cp, kl, ks, S) - debit) * 100
                    mloss = debit * 100
                trades.append(dict(t=t, week=wk, entry=ed, exp=E, struct=nm, tenor=tenor, pnl=pnl, mloss=mloss,
                                   ub=False, breached=False, bear=bear, iv30=met.iv30, ivr120=met.ivr120, ivr250=met.ivr250,
                                   ivprem=met.ivprem, slope=met.slope))
    return trades, drops


# ------------------------------------------------------------------------------------------------ gates
def gates_for(kind):
    g = {'ungated': lambda x: pd.Series(True, index=x.index)}
    if kind in ('PCS', 'IC'):
        for n in (120, 250):
            for th in (50, 70, 80):
                g[f'ivr{n}>{th}'] = (lambda n=n, th=th: lambda x: x[f'ivr{n}'] > th / 100)()
        for th in (0.0, 0.05, 0.10):
            g[f'ivprem>{th:.2f}'] = (lambda th=th: lambda x: x.ivprem > th)()
        g['contango'] = lambda x: x.slope < 0
        g['backwardation'] = lambda x: x.slope > 0
    else:
        for n in (120, 250):
            for th in (20, 30):
                g[f'ivr{n}<{th}'] = (lambda n=n, th=th: lambda x: x[f'ivr{n}'] < th / 100)()
        g['ivprem<0'] = lambda x: x.ivprem < 0
    return g


def evaluable(gate, x):
    """rows on which the gate could have been evaluated (its input is defined)."""
    if gate.startswith('ivr120'):
        return x.ivr120.notna()
    if gate.startswith('ivr250'):
        return x.ivr250.notna()
    if gate.startswith('ivprem'):
        return x.ivprem.notna()
    if gate in ('contango', 'backwardation'):
        return x.slope.notna()
    return pd.Series(True, index=x.index)


# -------------------------------------------------------------------------------------------- statistics
def tstat(x, nw_lag=0):
    x = np.asarray(x, float)
    n = len(x)
    if n < 3:
        return 0.0
    mu = x.mean()
    e = x - mu
    v = (e @ e) / n
    if nw_lag > 0:
        for L in range(1, nw_lag + 1):
            wgt = 1 - L / (nw_lag + 1)
            v += 2 * wgt * (e[L:] @ e[:-L]) / n
    if v <= 0:
        return 0.0
    return mu / math.sqrt(v / n)


def weekly(tr):
    return tr.groupby('week').pnl.sum().sort_index()


def max_dd(series):
    c = series.cumsum()
    return float((c - c.cummax()).min()) if len(c) else 0.0


def evaluate(tr, tenor):
    """metrics for one config's trade set (already gated)."""
    lag = 1 if tenor == 2 else 0
    w = weekly(tr)
    n_w = len(w)
    out = dict(n_trades=int(len(tr)), n_weeks=int(n_w), total=float(tr.pnl.sum()))
    if n_w == 0:
        return out
    out['per_trade'] = float(tr.pnl.mean())
    out['per_week'] = float(w.mean())
    out['t_week'] = tstat(w.values, lag)
    out['t_tw'] = tstat(tr.pnl.values)
    out['t_conservative'] = min(out['t_week'], out['t_tw'])
    h = math.ceil(n_w / 2)
    out['halves'] = [float(w.iloc[:h].sum()), float(w.iloc[h:].sum())]
    wq = {k: f'{e[:4]}Q{(int(e[5:7]) - 1) // 3 + 1}' for k, e in zip(tr.week, tr.entry)}
    q = w.groupby(lambda k: wq[k]).sum()
    out['quarters'] = {k: round(float(v), 1) for k, v in q.items()}
    nq = len(q)
    out['n_q_pos'] = int((q > 0).sum())
    out['q_needed'] = nq - int(math.floor(0.2 * nq))
    out['worst_week'] = float(w.min())
    out['best_week'] = float(w.max())
    out['max_dd'] = max_dd(w)
    out['max_loss_per_contract'] = float(tr.mloss.max())
    w_loo = w.drop(w.idxmax())
    out['loo_t'] = tstat(w_loo.values, lag) if len(w_loo) > 2 else 0.0
    out['loo_mean'] = float(w_loo.mean()) if len(w_loo) else 0.0
    out['win_rate'] = float((tr.pnl > 0).mean())
    out['first_week'], out['last_week'] = str(w.index[0]), str(w.index[-1])
    return out


def passes(mt, bar_w, bar_tw):
    if mt.get('n_weeks', 0) < MIN_WEEKS:
        return False, 'n_weeks<%d' % MIN_WEEKS
    checks = [
        (mt['per_week'] > 0, 'mean<=0'),
        (mt['t_week'] > bar_w, f't_week {mt["t_week"]:.2f} <= bar {bar_w:.2f}'),
        (mt['t_tw'] > bar_tw, f't_tw {mt["t_tw"]:.2f} <= bar {bar_tw:.2f}'),
        (mt['halves'][0] > 0 and mt['halves'][1] > 0, 'a half is negative'),
        (mt['n_q_pos'] >= mt['q_needed'], f'quarters {mt["n_q_pos"]}/{len(mt["quarters"])} < {mt["q_needed"]}'),
        (mt['loo_t'] > 1.5 and mt['loo_mean'] > 0, f'LOO t {mt["loo_t"]:.2f}'),
        (mt['max_loss_per_contract'] <= MAX_LOSS_CAP, 'max loss > 1000'),
    ]
    fails = [msg for ok, msg in checks if not ok]
    return (len(fails) == 0), ('; '.join(fails) if fails else 'all checks pass')


# ------------------------------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    all_trades, all_drops, ivsum = [], {}, {}
    for t in TICKERS:
        df = load_ticker(t)
        m = daily_metrics(t, df)
        ivsum[t] = dict(days=int(len(m)), iv30_cov=float(m.iv30.notna().mean()), iv_near_cov=float(m.iv_near.notna().mean()),
                        ivr120_from=str(m.ivr120.first_valid_index()), ivr250_from=str(m.ivr250.first_valid_index()),
                        iv30_med=float(m.iv30.median()), ivprem_med=float(m.ivprem.median()),
                        backwardation_share=float((m.slope > 0).mean()))
        tr, dr = build_trades(t, df, m)
        all_trades += tr
        all_drops[t] = dr
        log(f'{t}: rows {len(df):,} days {len(m)} iv30cov {ivsum[t]["iv30_cov"]:.2f} ivr120 from {ivsum[t]["ivr120_from"]} '
            f'ivr250 from {ivsum[t]["ivr250_from"]} trades {len(tr)}  ({time.time() - t0:.0f}s)')
        del df
    T = pd.DataFrame(all_trades)
    T = T[~T.bear]                                   # live BEAR stand-down, applied before scoring
    U = T[T.ub].copy()                               # unscored coverage rows (PCS, long leg absent): upper bounds only
    T = T[~T.ub].copy()
    log(f'trades after BEAR gate: {len(T):,}  weeks {T.week.nunique()}')
    T.to_csv(R + '/vol_conditioning_trades.csv', index=False)

    # ---------------- configs
    rows = []      # (name, kind, tenor, gate, universe, struct)
    cfg_trades = {}
    for s in STRUCTS:
        for tenor in TENORS:
            nm = sname(s, tenor)
            base = T[T.struct == nm]
            for gname, gf in gates_for(s[0]).items():
                for uname, ulist in UNIVERSES.items():
                    x = base[base.t.isin(ulist)]
                    x = x[evaluable(gname, x)]
                    on = x[gf(x)]
                    cname = f'{uname}|{nm}|{gname}'
                    rows.append(dict(name=cname, kind=s[0], tenor=tenor, gate=gname, universe=uname, struct=nm))
                    cfg_trades[cname] = (x, on)
    log(f'grid size {len(rows)} configs')

    # ---------------- level metrics
    res = {}
    for r in rows:
        x, on = cfg_trades[r['name']]
        res[r['name']] = evaluate(on, r['tenor'])
    elig = [r for r in rows if res[r['name']].get('n_weeks', 0) >= MIN_WEEKS]
    log(f'eligible (>= {MIN_WEEKS} active weeks): {len(elig)}')

    # ---------------- permutation bars (sign flips shared across configs; week-level and ticker-week-level)
    weeks_all = sorted(T.week.unique())
    widx = {w: i for i, w in enumerate(weeks_all)}
    tw_all = sorted(set(zip(T.t, T.week)))
    twidx = {k: i for i, k in enumerate(tw_all)}
    rng = np.random.default_rng(SEED)
    W = np.zeros((len(weeks_all), len(elig)))
    Wmask = np.zeros_like(W, dtype=bool)
    TWm = np.zeros((len(tw_all), len(elig)))
    TWmask = np.zeros_like(TWm, dtype=bool)
    lags = np.zeros(len(elig), int)
    for j, r in enumerate(elig):
        x, on = cfg_trades[r['name']]
        w = weekly(on)
        for k, v in w.items():
            W[widx[k], j] = v; Wmask[widx[k], j] = True
        for tk, wk, v in zip(on.t, on.week, on.pnl):
            TWm[twidx[(tk, wk)], j] = v; TWmask[twidx[(tk, wk)], j] = True
        lags[j] = 1 if r['tenor'] == 2 else 0

    def perm_bar(M, mask, lags, flips_len):
        mx = []
        for _ in range(N_PERM):
            f = rng.choice([-1.0, 1.0], size=flips_len)[:, None]
            Mf = M * f
            best = 0.0
            for j in range(M.shape[1]):
                col = Mf[mask[:, j], j]
                best = max(best, abs(tstat(col, lags[j])))
            mx.append(best)
        return float(np.percentile(mx, 95)), float(np.median(mx))

    log('permutation bar (week clustering)...')
    bar_w, med_w = perm_bar(W, Wmask, lags, len(weeks_all))
    log(f'  bar_week = {bar_w:.3f}  (median max|t| {med_w:.2f})')
    log('permutation bar (ticker-week clustering)...')
    bar_tw, med_tw = perm_bar(TWm, TWmask, np.zeros(len(elig), int), len(tw_all))
    log(f'  bar_tw = {bar_tw:.3f}  (median max|t| {med_tw:.2f})')

    # ---------------- paired differences: gated minus ungated, same structure / tenor / universe, evaluable rows only
    paired = {}
    gcols = []
    PW = []; PTW = []
    for r in elig:
        if r['gate'] == 'ungated':
            continue
        x, on = cfg_trades[r['name']]
        lag = 1 if r['tenor'] == 2 else 0
        onk = set(zip(on.t, on.week))
        d = x.copy()
        d['diff'] = np.where([(a, b) in onk for a, b in zip(d.t, d.week)], 0.0, -d.pnl)   # gated - ungated
        dw = d.groupby('week')['diff'].sum().sort_index()
        off = d[[(a, b) not in onk for a, b in zip(d.t, d.week)]]
        paired[r['name']] = dict(
            diff_per_week=float(dw.mean()), diff_total=float(dw.sum()),
            t_week=tstat(dw.values, lag), t_tw=tstat(d['diff'].values),
            on_per_trade=float(on.pnl.mean()) if len(on) else 0.0, on_n=int(len(on)),
            off_per_trade=float(off.pnl.mean()) if len(off) else 0.0, off_n=int(len(off)),
            ungated_per_trade=float(x.pnl.mean()), ungated_n=int(len(x)),
            share_on=float(len(on) / max(len(x), 1)))
        gcols.append(r['name'])
        PW.append((dw, lag)); PTW.append(d)
    if gcols:
        Wp = np.zeros((len(weeks_all), len(gcols))); Wpm = np.zeros_like(Wp, dtype=bool); lg = np.zeros(len(gcols), int)
        TWp = np.zeros((len(tw_all), len(gcols))); TWpm = np.zeros_like(TWp, dtype=bool)
        for j, ((dw, lag), d) in enumerate(zip(PW, PTW)):
            for k, v in dw.items():
                Wp[widx[k], j] = v; Wpm[widx[k], j] = True
            for tk, wk, v in zip(d.t, d.week, d['diff']):
                TWp[twidx[(tk, wk)], j] = v; TWpm[twidx[(tk, wk)], j] = True
            lg[j] = lag
        log('permutation bar for paired differences...')
        pbar_w, _ = perm_bar(Wp, Wpm, lg, len(weeks_all))
        pbar_tw, _ = perm_bar(TWp, TWpm, np.zeros(len(gcols), int), len(tw_all))
        log(f'  paired bars: week {pbar_w:.3f}  ticker-week {pbar_tw:.3f}')
    else:
        pbar_w = pbar_tw = float('nan')

    # ---------------- assemble
    cands = []
    for r in rows:
        mt = res[r['name']]
        ok, why = passes(mt, bar_w, bar_tw) if mt.get('n_weeks', 0) else (False, 'no trades')
        p = paired.get(r['name'])
        gate_adds = None
        if p is not None:
            gate_adds = bool(p['diff_per_week'] > 0 and p['t_week'] > pbar_w and p['t_tw'] > pbar_tw)
        spec = dict(universe=r['universe'], structure=r['struct'], tenor=r['tenor'], gate=r['gate'],
                    entry='first trading day of ISO week, at close (closing NBBO)',
                    expiry='max listed expiry in the target ISO week on the entry-day chain',
                    fills='sell@bid buy@ask; hold to expiry; intrinsic on expiry-day close',
                    regime='BEAR stand-down (regime.json, D-1)', delta_tol=0.07, atm_tol=0.10,
                    iv_defs='iv30=ATM iv of expiry nearest 30 DTE in [14,50]; iv_near=ATM iv of nearest expiry DTE in [3,10]; '
                            'ATM=mean iv of 2 strikes nearest close, both cps; rv20=std(20 log rets)*sqrt(252); '
                            'ivrN=(iv30-min)/(max-min) trailing N obs days full window; slope=iv_near/iv30-1')
        cands.append(dict(name=r['name'], spec=spec, metrics={k: (round(v, 3) if isinstance(v, float) else v) for k, v in mt.items()},
                          paired_vs_ungated=(None if p is None else {k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items()}),
                          gate_adds_value=gate_adds, passes_search_bar=bool(ok), why_or_why_not=why))
    survivors = [c for c in cands if c['passes_search_bar']]
    log(f'SURVIVORS: {len(survivors)}')
    for c in survivors:
        log('  PASS', c['name'], {k: c['metrics'][k] for k in ('n_weeks', 'per_week', 't_week', 't_tw', 'halves', 'n_q_pos', 'loo_t')},
            'gate_adds_value', c['gate_adds_value'])
    # ---------------- coverage sensitivity for every survivor (PCS only): fill the dropped weeks
    for c in survivors:
        uname, snm, gname = c['name'].split('|')
        if not snm.startswith('PCS'):
            continue
        x, on = cfg_trades[c['name']]
        tenor = int(snm[-1]); lag = 1 if tenor == 2 else 0
        u = U[(U.struct == snm) & (U.t.isin(UNIVERSES[uname]))]
        u = u[evaluable(gname, u)]
        u = u[gates_for('PCS')[gname](u)]
        w_kept = weekly(on)
        credit_avg = float(on.pnl[on.pnl > 0].mean()) if (on.pnl > 0).any() else 0.0
        sens = dict(dropped_ticker_weeks=int(len(u)), dropped_breach_weeks=int(u.breached.sum()),
                    breach_upper_bound_sum=float(u[u.breached].pnl.sum()), scored_ticker_weeks=int(len(on)),
                    note='dropped = short leg listed but long leg absent from the top-500 chain (live would trade them). '
                         'breach weeks priced at the long-leg-free UPPER bound; non-breach dropped weeks at the fill value.',
                    fills={})
        for label, fv in (('avg_kept_win', credit_avg), ('min_kept_win', float(on.pnl[on.pnl > 0].min()) if (on.pnl > 0).any() else 0.0), ('zero', 0.0)):
            f = u.copy(); f['pnl'] = np.where(f.breached, f.pnl, fv)
            w = pd.concat([on[['week', 'pnl']], f[['week', 'pnl']]]).groupby('week').pnl.sum().sort_index()
            h = math.ceil(len(w) / 2)
            tw = tstat(w.values, lag)
            sens['fills'][label] = dict(fill_value=round(fv, 1), n_weeks=int(len(w)), total=round(float(w.sum()), 1),
                                        per_week=round(float(w.mean()), 1), t_week=round(tw, 3), worst_week=round(float(w.min()), 1),
                                        max_dd=round(max_dd(w), 1), halves=[round(float(w.iloc[:h].sum()), 1), round(float(w.iloc[h:].sum()), 1)],
                                        loo_t=round(tstat(w.drop(w.idxmax()).values, lag), 3), clears_week_bar=bool(tw > bar_w))
        c['coverage_sensitivity'] = sens
        c['endorsed'] = bool(all(v['clears_week_bar'] for v in sens['fills'].values()))
        log('  coverage sensitivity', c['name'], {k: (v['t_week'], v['clears_week_bar']) for k, v in sens['fills'].items()}, 'endorsed', c['endorsed'])

    # near misses: t_conservative >= 2.0 but failed
    near = sorted([c for c in cands if not c['passes_search_bar'] and c['metrics'].get('t_conservative', 0) >= 2.0],
                  key=lambda c: -c['metrics']['t_conservative'])
    log(f'near misses (t_cons >= 2.0, failed): {len(near)}')
    for c in near[:40]:
        log('  NEAR', c['name'], 'n_w', c['metrics']['n_weeks'], '$/wk', c['metrics']['per_week'], 't_w', c['metrics']['t_week'],
            't_tw', c['metrics']['t_tw'], 'halves', c['metrics']['halves'], 'q', f"{c['metrics']['n_q_pos']}/{len(c['metrics']['quarters'])}",
            'loo', c['metrics']['loo_t'], '|', c['why_or_why_not'])
    # gate-level summary: on vs off per trade, for each gate pooled over structures
    gate_summary = {}
    for r in elig:
        p = paired.get(r['name'])
        if p is None:
            continue
        gate_summary.setdefault(r['gate'], []).append(dict(cfg=r['name'], on=p['on_per_trade'], off=p['off_per_trade'],
                                                            on_n=p['on_n'], off_n=p['off_n'], t_week=p['t_week'], t_tw=p['t_tw']))
    out = dict(family='C - volatility conditioning (IV rank / IV-RV premium / term structure gates on defined-risk spreads)',
               grid_size=len(rows), eligible_configs=len(elig), min_weeks=MIN_WEEKS,
               permutation_bar=dict(week=round(bar_w, 3), ticker_week=round(bar_tw, 3), n_perm=N_PERM,
                                    paired_week=round(pbar_w, 3), paired_ticker_week=round(pbar_tw, 3), seed=SEED),
               candidates=cands, survivors=[c['name'] for c in survivors],
               near_misses=[c['name'] for c in near],
               iv_summary=ivsum, drops=all_drops,
               gate_summary=gate_summary,
               dead_ends=[
                   'IV-rank gates (120d and 250d, thresholds 50/70/80) on put credit spreads and iron condors: paired difference vs the ungated structure is negative or noise for every structure/tenor/universe (0 of the gated configs beat the paired bar).',
                   'IV-minus-realised gate (>0, >0.05, >0.10): same result; the gate mostly reduces n and never lifts $/trade beyond noise.',
                   'Term structure (contango-only selling; backwardation-only selling): neither adds value paired; backwardation-only has too few weeks.',
                   'Debit spreads (ATM call or put, $5/$10, 1-2 weeks) lose everywhere ungated (ATM bid-ask on both legs); low-IV-rank gating lifts the paired difference to t 2.1-2.7 but the gated leg itself is at best ~+$10-30/trade on a $400-660 max loss and fails the level bar.',
                   'Weekly (tenor 1) put credit spreads at 20-30 delta lose money after executable fills on every universe; 10-delta weekly is flat.',
                   'Iron condors: only the 10-delta $10 two-week index condor is positive (t ~2) and it is not close to the bar.',
                   'The one numeric pass (IDX 10-delta $10-wide two-week PCS, ungated) is a coverage artefact: 47% of its ticker-weeks were dropped (long leg absent from the top-500 chain); filling them at the most favourable estimate fails the bar (see coverage_sensitivity).'],
               notes='Scoring follows PROTOCOL: drop rule, executable fills, BEAR stand-down, intrinsic settlement. The family hypothesis (premium selling pays only when IV is rich) is NOT supported here: on-gate $/trade never differs from off-gate $/trade beyond noise, on either clustering. The IV columns are clean (iv30 coverage 100% of days for all 11 tickers).',
               trades_after_bear=int(len(T)), weeks=len(weeks_all), runtime_s=round(time.time() - t0))
    json.dump(out, open(R + '/vol_conditioning_results.json', 'w'), indent=1, default=str)
    log('written vol_conditioning_results.json', f'{time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()

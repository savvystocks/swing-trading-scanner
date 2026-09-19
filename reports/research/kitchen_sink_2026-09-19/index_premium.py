#!/usr/bin/env python
"""FAMILY A - INDEX PREMIUM SELLING.  Pre-registered bar: /tmp/research/PROTOCOL.md.

Reads ONLY /tmp/research/search.db (table o), closes.json, regime.json.
Executable prices only: every SELL at bid, every BUY at ask, settlement = intrinsic at expiry close.
Runs end to end:  ~/swing-trading-scanner/.venv/bin/python /tmp/research/index_premium.py
Writes /tmp/research/index_premium_results.json (even if nothing passes).
"""
import sqlite3, json, datetime as dt, math, sys, time
import numpy as np
from collections import defaultdict, Counter

R = "/tmp/research"
TICKERS = ["SPY", "QQQ", "IWM", "TLT", "GLD"]          # DIA is not in search.db
START, END = "2024-07-23", "2026-03-13"                # contiguous chain coverage; 2023 stubs have no regime
NFLIPS, SEED, FLIP_CHUNK = 1000, 20260918, 100
MIN_N = 20
BASE_KEY = ("SPY", "PCS", ("pct", 2), ("pct", 2), "W0", 0)   # the live rule: sell 2% OTM put, buy 4% OTM put
CONDS = ["NONBEAR", "MILD", "BULL", "BEAR", "ALL", "NB_IVHIGH", "NB_IVLOW", "NB_UPWK", "NB_DNWK"]
GATE_OK = {"NONBEAR", "MILD", "BULL", "NB_IVHIGH", "NB_IVLOW", "NB_UPWK", "NB_DNWK"}
T0 = time.time()

def log(*a):
    print(f"[{time.time()-T0:7.1f}s]", *a, flush=True)

closes = json.load(open(f"{R}/closes.json"))
regime = json.load(open(f"{R}/regime.json"))

def d2(s): return dt.date.fromisoformat(s)
def isoweek(s):
    y, w, _ = d2(s).isocalendar(); return y * 100 + w
def quarter(s): return f"{s[:4]}Q{(int(s[5:7]) - 1) // 3 + 1}"

# ------------------------------------------------------------------ data
def load(t):
    c = sqlite3.connect(f"file:{R}/search.db?mode=ro", uri=True)
    c.execute("pragma busy_timeout=120000")
    chain = defaultdict(dict)
    for day, exp, cp, k, bid, ask, iv, delta in c.execute(
            "select day,exp,cp,k,bid,ask,iv,delta from o where t=? and day>=? and day<=?", (t, START, END)):
        chain[(day, exp, cp)][k] = (bid, ask, iv, delta)
    c.close()
    days = sorted(set(k[0] for k in chain))
    exps = defaultdict(set)
    for (day, exp, cp) in chain:
        exps[day].add(exp)
    return chain, days, exps

def atm_iv_flags(t, chain, days, exps):
    iv = {}
    for day in days:
        bar = closes[t].get(day)
        if not bar: continue
        spot = bar[3]
        cands = [e for e in exps[day] if 1 <= (d2(e) - d2(day)).days <= 14]
        if not cands: continue
        e = min(cands, key=lambda x: abs((d2(x) - d2(day)).days - 7))
        vals = []
        for cp in "PC":
            ks = chain.get((day, e, cp), {})
            if not ks: continue
            k = min(ks, key=lambda x: abs(x - spot))
            if abs(k - spot) <= 0.01 * spot and ks[k][2]:
                vals.append(ks[k][2])
        if vals: iv[day] = sum(vals) / len(vals)
    flag = {}
    ds = [d for d in days if d in iv]
    for i, d in enumerate(ds):
        prev = sorted(iv[x] for x in ds[max(0, i - 60):i])
        if len(prev) >= 30:
            med = prev[len(prev) // 2]
            flag[d] = "HIGH" if iv[d] > med else "LOW"
    return iv, flag

def pick_exp(entry, exps, tenor):
    ed = d2(entry)
    if tenor in ("W0", "W1"):
        fri = ed + dt.timedelta(days=4 - ed.weekday() + (7 if tenor == "W1" else 0))
        c = [e for e in exps if fri - dt.timedelta(days=1) <= d2(e) <= fri and d2(e) > ed and e <= END]
        return max(c) if c else None
    if tenor == "M":   # nearest monthly 30-45 DTE; one trade per cycle chosen later
        c = [e for e in exps if d2(e).weekday() == 4 and 15 <= d2(e).day <= 21
             and 30 <= (d2(e) - ed).days <= 45 and e <= END]
        return min(c, key=lambda e: abs((d2(e) - ed).days - 38)) if c else None
    raise ValueError(tenor)

def delta_strike(rows, target, spot, cp):
    best, bd = None, 9
    for k, (bid, ask, iv, delta) in rows.items():
        if bid <= 0 or delta is None: continue
        if (cp == "P" and k >= spot) or (cp == "C" and k <= spot): continue
        dd = abs(abs(delta) - target)
        if dd < bd: best, bd = k, dd
    return best if bd <= 0.04 else None

def leg(chain, entry, exp, cp, spot, smode, width, side_sign):
    """One vertical.  side_sign -1 for puts (strikes go down), +1 for calls.
    Returns a dict: why (None if tradeable), Ks, Kl, bs (short bid), ds (|delta| short), credit, width.
    When only the LONG strike is missing, the short-leg quote is still returned so the selection-bias
    diagnostic can price the short leg on dropped weeks."""
    rows = chain.get((entry, exp, cp))
    if not rows: return dict(why="no_chain")
    if smode[0] == "pct":
        Ks = float(round(spot * (1 + side_sign * smode[1] / 100)))
        Kl = (float(round(spot * (1 + side_sign * (smode[1] + width[1]) / 100))) if width[0] == "pct"
              else Ks + side_sign * width[1])
    else:
        Ks = delta_strike(rows, smode[1], spot, cp)
        if Ks is None: return dict(why="no_delta_strike")
        Kl = (float(round(Ks + side_sign * spot * width[1] / 100)) if width[0] == "pct"
              else Ks + side_sign * width[1])
    if Ks not in rows: return dict(why="strike_missing", Ks=Ks, Kl=Kl)
    bs, as_, _, ds = rows[Ks]
    if bs <= 0: return dict(why="zero_bid", Ks=Ks, Kl=Kl)
    out = dict(why=None, Ks=Ks, Kl=Kl, bs=bs, ds=abs(ds or 0.0))
    if Kl not in rows: out["why"] = "strike_missing"; return out
    if Ks == Kl: out["why"] = "degenerate"; return out
    bl, al, _, _ = rows[Kl]
    credit = bs - al
    if credit <= 0: out["why"] = "no_credit"; return out
    out.update(credit=credit, width=abs(Ks - Kl))
    return out

def settle(cp, Ks, Kl, S):
    if cp == "P": return -max(Ks - S, 0) + max(Kl - S, 0)
    return -max(S - Ks, 0) + max(S - Kl, 0)

# ------------------------------------------------------------------ grid
def structural_grid(t):
    g = []
    for struct in ("PCS", "CCS", "IC"):
        for s in (1, 2, 3, 4):
            for w in (1, 2, 4):
                for tenor in ("W0", "W1", "M"):
                    g.append((t, struct, ("pct", s), ("pct", w), tenor, 0))
    if t in ("SPY", "QQQ", "IWM"):
        for struct in ("PCS", "CCS", "IC"):
            for s in (1, 2, 3, 4):
                for w in (5, 7):
                    for tenor in ("W0", "W1", "M"):
                        g.append((t, struct, ("pct", s), ("usd", w), tenor, 0))
        for struct in ("PCS", "CCS"):
            for dl in (0.10, 0.16, 0.25):
                for w in (("pct", 1), ("pct", 2), ("usd", 7)):
                    for tenor in ("W0", "W1", "M"):
                        g.append((t, struct, ("delta", dl), w, tenor, 0))
    if t == "SPY":
        for struct in ("PCS", "CCS"):
            for s in (1, 2, 3):
                for w in (1, 2):
                    for tenor in ("W0", "W1"):
                        for idx in (1, 2, 3):
                            g.append((t, struct, ("pct", s), ("pct", w), tenor, idx))
    return g

def prior_week_returns(t):
    """ISO-week close-to-close return of the week BEFORE the entry week, from closes.json."""
    wk = defaultdict(list)
    for d in sorted(closes[t]): wk[isoweek(d)].append(d)
    ws = sorted(wk); last = {w: closes[t][wk[w][-1]][3] for w in ws}
    out = {}
    for i in range(2, len(ws)):
        out[ws[i]] = (last[ws[i - 1]] / last[ws[i - 2]] - 1) * 100
    return out

def build_trades(t, chain, days, exps, ivflag, grid, ivd=None):
    ivd = ivd or {}
    pw = prior_week_returns(t)
    weeks = defaultdict(list)
    for d in days: weeks[isoweek(d)].append(d)
    weeks = {w: sorted(v) for w, v in weeks.items()}
    trades = {g: [] for g in grid}
    drops = {g: Counter() for g in grid}
    dropped = {g: [] for g in grid}      # weeks dropped ONLY for a missing long strike, short leg priced
    # monthly cycle: one entry per monthly expiry = the earliest first-trading-day-of-week with 30<=DTE<=45
    monthly_entry = {}
    for w in sorted(weeks):
        entry = weeks[w][0]
        e = pick_exp(entry, exps[entry], "M")
        if e and e not in monthly_entry: monthly_entry[e] = entry
    monthly_entries = set(monthly_entry.values())
    for w in sorted(weeks):
        for g in grid:
            _, struct, smode, width, tenor, idx = g
            if idx >= len(weeks[w]): drops[g]["no_entry_day"] += 1; continue
            entry = weeks[w][idx]
            if tenor == "M" and entry not in monthly_entries: continue
            bar = closes[t].get(entry)
            if not bar: drops[g]["no_close"] += 1; continue
            spot = bar[3]
            reg = regime.get(entry)
            if not reg: drops[g]["no_regime"] += 1; continue
            exp = pick_exp(entry, exps[entry], tenor)
            if not exp: drops[g]["no_expiry"] += 1; continue
            sb = closes[t].get(exp)
            if not sb: drops[g]["no_settle_close"] += 1; continue
            S = sb[3]
            legs = []
            for cp, sign in (("P", -1), ("C", +1)):
                if (cp == "P" and struct == "CCS") or (cp == "C" and struct == "PCS"): continue
                legs.append((cp, leg(chain, entry, exp, cp, spot, smode, width, sign)))
            common = dict(t=t, entry=entry, exp=exp, spot=spot, wk=isoweek(exp), q=quarter(exp), reg=reg["regime"],
                          iv=ivflag.get(entry), atm_iv=ivd.get(entry), pw=pw.get(isoweek(entry)), wd=d2(entry).weekday())
            bad = [L for cp, L in legs if L["why"]]
            if bad:
                for L in bad: drops[g][L["why"]] += 1
                if all(L["why"] == "strike_missing" and "bs" in L for L in bad) and all("bs" in L for cp, L in legs):
                    slp = sum((L["bs"] - (max(L["Ks"] - S, 0) if cp == "P" else max(S - L["Ks"], 0))) for cp, L in legs)
                    breach = any((S < L["Ks"]) if cp == "P" else (S > L["Ks"]) for cp, L in legs)
                    dropped[g].append(dict(common, slp=round(slp * 100, 2), breach=breach))
                continue
            credit = sum(L["credit"] for cp, L in legs)
            pnl = credit + sum(settle(cp, L["Ks"], L["Kl"], S) for cp, L in legs)
            mx = max(L["width"] for cp, L in legs)
            slp = sum((L["bs"] - (max(L["Ks"] - S, 0) if cp == "P" else max(S - L["Ks"], 0))) for cp, L in legs)
            trades[g].append(dict(common, pnl=round(pnl * 100, 2), credit=round(credit * 100, 2),
                                  maxloss=round((mx - credit) * 100, 2), dl=round(sum(L["ds"] for cp, L in legs), 4),
                                  sl=round(sum(L["bs"] for cp, L in legs) * 100, 2), slp=round(slp * 100, 2)))
    return trades, drops, dropped

# ------------------------------------------------------------------ stats
def t_cluster(x, cl):
    n = len(x)
    if n < 2: return float("nan")
    m = x.mean()
    sums = defaultdict(float)
    for xi, c in zip(x, cl): sums[c] += xi - m
    G = len(sums)
    if G < 2: return float("nan")
    v = G / (G - 1) * sum(u * u for u in sums.values()) / n / n
    return float(m / math.sqrt(v)) if v > 0 else float("nan")

def cp_upper(x, n, conf=0.95):
    """Clopper-Pearson one-sided upper bound on a binomial proportion (x successes of n)."""
    if x >= n: return 1.0
    lo, hi = x / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        cdf = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(x + 1))
        if cdf > 1 - conf: lo = mid
        else: hi = mid
    return hi

def selection_diag(tr, dropped):
    """Short leg priced on kept vs dropped weeks; drop-corrected ESTIMATE of the spread on dropped weeks =
    short-leg P&L minus the average long-leg cost on kept weeks.  An estimate (uses substitution), used only
    as a stricter honesty check, never as a candidate metric."""
    if not tr: return None
    kept_slp = np.array([r["slp"] for r in tr]); long_cost = float(np.mean([r["sl"] - r["credit"] for r in tr]))
    out = dict(n_kept=len(tr), n_dropped=len(dropped), shortleg_mean_kept=round(float(kept_slp.mean()), 2),
               breach_rate_kept=round(float(np.mean([r["slp"] < r["sl"] for r in tr])), 3),
               atm_iv_kept=round(float(np.nanmean([r["atm_iv"] if r["atm_iv"] else np.nan for r in tr])), 4),
               long_cost_avg=round(long_cost, 2))
    if dropped:
        d_slp = np.array([r["slp"] for r in dropped])
        out.update(shortleg_mean_dropped=round(float(d_slp.mean()), 2),
                   breach_rate_dropped=round(float(np.mean([r["breach"] for r in dropped])), 3),
                   atm_iv_dropped=round(float(np.nanmean([r["atm_iv"] if r["atm_iv"] else np.nan for r in dropped])), 4))
        est = [dict(r, pnl=round(r["slp"] - long_cost, 2)) for r in dropped]
        allr = sorted(tr + est, key=lambda r: (r["exp"], r["t"], r["entry"]))
        x = np.array([r["pnl"] for r in allr]); wk = [r["wk"] for r in allr]; tw = [(r["t"], r["wk"]) for r in allr]
        tw_, w_ = t_cluster(x, tw), t_cluster(x, wk)
        out.update(drop_corrected_n=len(allr), drop_corrected_mean=round(float(x.mean()), 2),
                   drop_corrected_t=round(min(w_, tw_) if not (math.isnan(w_) or math.isnan(tw_)) else float("nan"), 3),
                   drop_corrected_losses=int((x < 0).sum()))
    else:
        out.update(drop_corrected_n=len(tr), drop_corrected_mean=round(float(np.mean([r["pnl"] for r in tr])), 2),
                   drop_corrected_t=None, drop_corrected_losses=int(sum(r["pnl"] < 0 for r in tr)))
    return out

def metrics(tr, dropped=None):
    tr = sorted(tr, key=lambda r: (r["exp"], r["t"], r["entry"]))
    n = len(tr)
    if n == 0: return dict(n=0)
    x = np.array([r["pnl"] for r in tr]); wk = [r["wk"] for r in tr]; tw = [(r["t"], r["wk"]) for r in tr]
    tw_t, w_t = t_cluster(x, tw), t_cluster(x, wk)
    tdec = w_t if abs(w_t) <= abs(tw_t) else tw_t
    if math.isnan(w_t) or math.isnan(tw_t): tdec = float("nan")
    h = n // 2
    qs = defaultdict(float)
    for r in tr: qs[r["q"]] += r["pnl"]
    qpos = sum(1 for v in qs.values() if v > 0)
    eq = peak = mdd = 0.0
    for r in tr:
        eq += r["pnl"]; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    ib = int(x.argmax())
    xl = np.delete(x, ib); wkl = wk[:ib] + wk[ib + 1:]; twl = tw[:ib] + tw[ib + 1:]
    loo_w, loo_tw = t_cluster(xl, wkl), t_cluster(xl, twl)
    loo = min(loo_w, loo_tw) if not (math.isnan(loo_w) or math.isnan(loo_tw)) else float("nan")
    spots = np.array([r["spot"] for r in tr]); sm = float(np.median(spots))
    losses = int((x < 0).sum()); wins_x = x[x > 0]; loss_x = x[x < 0]
    mean_win = float(wins_x.mean()) if len(wins_x) else 0.0
    mean_loss = float(loss_x.mean()) if len(loss_x) else 0.0
    maxloss = max(r["maxloss"] for r in tr)
    p_up = cp_upper(losses, n)
    ev_lb_real = (1 - p_up) * mean_win + p_up * (mean_loss if losses >= 3 else -maxloss)
    ev_lb_max = (1 - p_up) * mean_win - p_up * maxloss
    tail = dict(losses=losses, loss_rate=round(losses / n, 3), implied_loss_freq=round(float(np.mean([r["dl"] for r in tr])), 3),
                mean_win=round(mean_win, 2), mean_loss=round(mean_loss, 2), p_loss_upper95=round(p_up, 3),
                ev_lb_realised=round(ev_lb_real, 2), ev_lb_maxloss=round(ev_lb_max, 2))
    return dict(n=n, tail=tail, selection=selection_diag(tr, dropped or []), n_weeks=len(set(wk)), total=round(float(x.sum()), 2), mean=round(float(x.mean()), 2),
                t_week=round(w_t, 3), t_tickerweek=round(tw_t, 3), t_decision=round(tdec, 3),
                win_rate=round(float((x > 0).mean()), 3),
                halves=[round(float(x[:h].mean()), 2), round(float(x[h:].mean()), 2)],
                quarters={k: round(v, 0) for k, v in sorted(qs.items())}, quarters_pos=f"{qpos}/{len(qs)}",
                worst=round(float(x.min()), 2), max_drawdown=round(mdd, 2),
                max_loss=round(max(r["maxloss"] for r in tr), 2), mean_credit=round(float(np.mean([r["credit"] for r in tr])), 2),
                loo_t=round(loo, 3), loo_mean=round(float(xl.mean()), 2) if len(xl) else None,
                spot_split=[round(float(x[spots < sm].mean()), 2) if (spots < sm).any() else None,
                            round(float(x[spots >= sm].mean()), 2) if (spots >= sm).any() else None],
                first=tr[0]["entry"], last=tr[-1]["entry"])

def cond_filter(tr, cond):
    if cond == "NONBEAR": return [r for r in tr if r["reg"] != "BEAR"]
    if cond in ("MILD", "BULL", "BEAR"): return [r for r in tr if r["reg"] == cond]
    if cond == "ALL": return tr
    if cond == "NB_IVHIGH": return [r for r in tr if r["reg"] != "BEAR" and r["iv"] == "HIGH"]
    if cond == "NB_IVLOW": return [r for r in tr if r["reg"] != "BEAR" and r["iv"] == "LOW"]
    if cond == "NB_UPWK": return [r for r in tr if r["reg"] != "BEAR" and r["pw"] is not None and r["pw"] > 1.0]
    if cond == "NB_DNWK": return [r for r in tr if r["reg"] != "BEAR" and r["pw"] is not None and r["pw"] < -1.0]
    raise ValueError(cond)

def spec_of(g, cond):
    t, struct, smode, width, tenor, idx = g
    return dict(underlying=t, structure=struct,
                short_strike=("round(spot*(1-s/100)) puts / round(spot*(1+s/100)) calls, s=%d%%" % smode[1]
                              if smode[0] == "pct" else "chain strike with |delta| nearest %.2f (tolerance 0.04, else drop)" % smode[1]),
                long_strike=("round(spot*(1-(s+w)/100)) / round(spot*(1+(s+w)/100)), w=%d%%" % width[1] if (width[0] == "pct" and smode[0] == "pct")
                             else "round(short -/+ spot*w/100), w=%d%%" % width[1] if width[0] == "pct"
                             else "short -/+ $%d" % width[1]),
                tenor={"W0": "this ISO week's Friday expiry (Thursday if Friday holiday)",
                       "W1": "next ISO week's Friday expiry", "M": "nearest 3rd-Friday monthly 30-45 DTE, one trade per cycle, entered the earliest eligible week"}[tenor],
                entry="trading day #%d of the ISO week (0=first) at the CLOSE, legs filled short@bid long@ask" % idx,
                exit="hold to expiry, cash-settled at intrinsic on the expiry-day close (closes.json)",
                regime_condition=cond, regime_source="regime.json D-1 SPY vs 50d SMA; BEAR<-2%, BULL>+2%",
                iv_condition=("ATM iv (nearest-7DTE expiry, strike nearest spot, mean of P and C) vs trailing 60-day median, min 30 prior days"
                              if cond.startswith("NB_IV") else "none"),
                missing_strike="period DROPPED, never substituted", pooled=(t in ("ALL5", "EQ3")))

# ------------------------------------------------------------------ permutation machinery
def perm_bar(cfg_trades, nflips, seed, label):
    """cfg_trades: list of trade lists (one per config).  Sign flips per expiry ISO week, shared across
    the whole grid and all tickers.  Statistic = min(|t_week|,|t_tickerweek|) per config; bar = 95th pct
    of the grid max."""
    weeks = sorted({r["wk"] for tr in cfg_trades for r in tr})
    widx = {w: i for i, w in enumerate(weeks)}
    tws = sorted({(r["t"], r["wk"]) for tr in cfg_trades for r in tr})
    tidx = {c: i for i, c in enumerate(tws)}
    tw_week = np.array([widx[c[1]] for c in tws])
    C, W, TW = len(cfg_trades), len(weeks), len(tws)
    S_tw = np.zeros((C, TW)); N_tw = np.zeros((C, TW))
    for i, tr in enumerate(cfg_trades):
        for r in tr:
            j = tidx[(r["t"], r["wk"])]; S_tw[i, j] += r["pnl"]; N_tw[i, j] += 1
    A = np.zeros((TW, W)); A[np.arange(TW), tw_week] = 1
    S_w, N_w = S_tw @ A, N_tw @ A
    n = N_w.sum(1)
    G_w = (N_w > 0).sum(1); G_tw = (N_tw > 0).sum(1)
    valid = (n >= 2) & (G_w >= 2)
    def tstat(S, N, G, F):      # F: flips x cols (already mapped to cols)
        M = S @ F.T                              # C x nf
        Q = (S * N) @ F.T
        SS = (S * S).sum(1)[:, None]; NN = (N * N).sum(1)[:, None]
        nn = n[:, None]; mu = M / nn
        var = (G / np.maximum(G - 1, 1))[:, None] * (SS - 2 * mu * Q + mu * mu * NN) / nn / nn
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(var > 0, mu / np.sqrt(var), np.nan)
    rng = np.random.default_rng(seed)
    maxs = []
    done = 0
    while done < nflips:
        k = min(FLIP_CHUNK, nflips - done)
        F = rng.choice([-1.0, 1.0], size=(k, W))
        t_w = tstat(S_w, N_w, G_w, F)
        t_tw = tstat(S_tw, N_tw, G_tw, F[:, tw_week])
        st = np.minimum(np.abs(t_w), np.abs(t_tw))
        st[~valid] = np.nan
        maxs.extend(np.nanmax(st, axis=0).tolist())
        done += k
        log(f"perm {label}: {done}/{nflips}")
    maxs = np.array(maxs)
    return dict(bar95=round(float(np.percentile(maxs, 95)), 3), bar99=round(float(np.percentile(maxs, 99)), 3),
                median=round(float(np.median(maxs)), 3), n_configs=C, n_weeks=W, n_flips=nflips)

# ------------------------------------------------------------------ main
def main():
    all_trades, all_drops, all_dropped = {}, {}, {}
    for t in TICKERS:
        chain, days, exps = load(t)
        iv, flag = atm_iv_flags(t, chain, days, exps)
        grid = structural_grid(t)
        tr, dr, dd = build_trades(t, chain, days, exps, flag, grid, iv)
        all_trades.update(tr); all_drops.update(dr); all_dropped.update(dd)
        log(f"{t}: {len(days)} days, {len(grid)} structural configs, iv days {len(iv)}, flagged {len(flag)}; "
            f"sample n: {[len(tr[g]) for g in grid[:6]]}")
        del chain
    # pooled configs
    for pool, members in (("ALL5", TICKERS), ("EQ3", ["SPY", "QQQ", "IWM"])):
        for struct in ("PCS", "CCS", "IC"):
            for s in (1, 2, 3, 4):
                widths = [("pct", 1), ("pct", 2), ("pct", 4)] + ([("usd", 5), ("usd", 7)] if pool == "EQ3" else [])
                for w in widths:
                    for tenor in ("W0", "W1", "M"):
                        g = (pool, struct, ("pct", s), w, tenor, 0)
                        all_trades[g] = sum((all_trades[(m, struct, ("pct", s), w, tenor, 0)] for m in members), [])
                        all_drops[g] = sum((all_drops[(m, struct, ("pct", s), w, tenor, 0)] for m in members), Counter())
                        all_dropped[g] = sum((all_dropped[(m, struct, ("pct", s), w, tenor, 0)] for m in members), [])
    log(f"structural configs total: {len(all_trades)}")

    # baseline
    base = all_trades[BASE_KEY]
    base_nb = cond_filter(base, "NONBEAR")
    base_by_wk = {r["wk"]: r["pnl"] for r in base_nb}
    base_dd = all_dropped[BASE_KEY]
    bm = metrics(base_nb, cond_filter(base_dd, "NONBEAR"))
    log("BASELINE SPY 2%/4% W0 NONBEAR:", json.dumps(bm))
    bmon = metrics([r for r in base_nb if r["wd"] == 0], [r for r in cond_filter(base_dd, "NONBEAR") if r["wd"] == 0])
    log("BASELINE Monday-only entries:", json.dumps(bmon))
    log("BASELINE ALL regimes:", json.dumps(metrics(base, base_dd)))
    log("BASELINE drops:", dict(all_drops[BASE_KEY]))
    kept = {r["wk"] for r in base}
    wkret = defaultdict(list)
    for d in sorted(closes["SPY"]):
        if START <= d <= END: wkret[isoweek(d)].append(d)
    kv, dv = [], []
    for w, ds in wkret.items():
        rr = closes["SPY"][ds[-1]][3] / closes["SPY"][ds[0]][3] - 1
        (kv if w in kept else dv).append(rr * 100)
    base_diag = dict(kept_weeks=len(kv), dropped_weeks=len(dv),
                     kept_mean_weekly_ret_pct=round(float(np.mean(kv)), 3), dropped_mean_weekly_ret_pct=round(float(np.mean(dv)), 3) if dv else None,
                     kept_sd=round(float(np.std(kv)), 3), dropped_sd=round(float(np.std(dv)), 3) if dv else None,
                     kept_min=round(min(kv), 2), dropped_min=round(min(dv), 2) if dv else None)
    log("BASELINE kept-vs-dropped weeks (SPY first-day close to last-day close):", base_diag)

    # evaluate the grid
    rows, cfg_lists, names = [], [], []
    paired_lists, paired_names = [], []
    for g, tr in all_trades.items():
        for cond in CONDS:
            sub = cond_filter(tr, cond)
            name = f"{g[0]}|{g[1]}|{g[2][0]}{g[2][1]}|{g[3][0]}{g[3][1]}|{g[4]}|e{g[5]}|{cond}"
            m = metrics(sub, cond_filter(all_dropped[g], cond))
            row = dict(name=name, key=g, cond=cond, metrics=m, drops=dict(all_drops[g]))
            if g[0] == "SPY" and g[4] == "W0":
                common = [r for r in sub if r["wk"] in base_by_wk]
                if len(common) >= 2:
                    d = [dict(r, pnl=round(r["pnl"] - base_by_wk[r["wk"]], 2)) for r in common]
                    pm = metrics(d)
                    row["paired_vs_baseline"] = dict(n=pm["n"], mean_diff=pm["mean"], t_week=pm["t_week"],
                                                     t_decision=pm["t_decision"], halves=pm["halves"])
                    if len(d) >= MIN_N: paired_lists.append(d); paired_names.append(name)
            rows.append(row)
            cfg_lists.append(sub); names.append(name)
    log(f"grid evaluated: {len(rows)} configs")
    ok_rows = [r for r in rows if r["metrics"]["n"] >= MIN_N]
    def tkey(r):
        td = r["metrics"].get("t_decision", float("nan"))
        return -9.0 if (td is None or math.isnan(td)) else td
    top = sorted(ok_rows, key=lambda r: -tkey(r))[:25]
    for r in top:
        m = r["metrics"]
        log(f"TOP {r['name']:<45} n={m['n']:3d} mean={m['mean']:7.2f} t={m['t_decision']:.2f} halves={m['halves']} q={m['quarters_pos']} loo={m['loo_t']:.2f} maxloss={m['max_loss']:.0f}")

    # permutation bars
    elig = [i for i, r in enumerate(rows) if r["metrics"]["n"] >= MIN_N]
    log(f"eligible configs (n>={MIN_N}): {len(elig)} of {len(rows)}")
    bar = perm_bar([cfg_lists[i] for i in elig], NFLIPS, SEED, "eligible grid")
    log("PERMUTATION BAR (full grid):", bar)
    core_idx = [i for i in elig if rows[i]["key"][0] in TICKERS and rows[i]["key"][2][0] == "pct" and rows[i]["key"][3][0] == "pct"
                and rows[i]["key"][4] == "W0" and rows[i]["key"][5] == 0 and rows[i]["cond"] == "NONBEAR"]
    bar_core = perm_bar([cfg_lists[i] for i in core_idx], NFLIPS, SEED, "core sub-grid (informational)")
    log("PERMUTATION BAR (core 180-config sub-grid, informational only):", bar_core)
    pbar = perm_bar(paired_lists, NFLIPS, SEED, "paired") if paired_lists else None
    log("PAIRED BAR:", pbar)

    # decisions
    B = bar["bar95"]
    candidates, near = [], []
    for r in rows:
        m = r["metrics"]; g = r["key"]
        if m["n"] < MIN_N:
            r["passes_search_bar"] = False; r["why_or_why_not"] = f"n={m['n']} < {MIN_N} periods"; continue
        fails = []
        td = m["t_decision"]
        if not (m["mean"] > 0 and not math.isnan(td) and td > B): fails.append(f"t_decision {td} <= bar {B} or mean<=0")
        if not (m["halves"][0] > 0 and m["halves"][1] > 0): fails.append(f"halves {m['halves']}")
        qp, qn = map(int, m["quarters_pos"].split("/"))
        allowed = max(1, qn // 5)
        if qn < 5 or qp < qn - allowed: fails.append(f"quarters {m['quarters_pos']}")
        if not (m["loo_mean"] and m["loo_mean"] > 0 and not math.isnan(m["loo_t"]) and m["loo_t"] > 1.5): fails.append(f"leave-one-out t {m['loo_t']}")
        tl = m["tail"]
        if tl["losses"] < 3: fails.append(f"only {tl['losses']} losing periods observed in {m['n']}: the loss side is unmeasured (delta-implied loss freq {tl['implied_loss_freq']}, upper95 {tl['p_loss_upper95']})")
        if tl["ev_lb_realised"] <= 0: fails.append(f"EV with loss frequency at its 95% upper bound is {tl['ev_lb_realised']}/period")
        sel = m["selection"]
        if sel and sel.get("n_dropped", 0) > 0:
            dct = sel["drop_corrected_t"]
            if not (sel["drop_corrected_mean"] > 0 and dct is not None and not math.isnan(dct) and dct > 2.0):
                fails.append(f"selection bias: {sel['n_dropped']} weeks dropped for a missing long strike; short leg kept ${sel['shortleg_mean_kept']} vs dropped ${sel.get('shortleg_mean_dropped')}; drop-corrected estimate {sel['drop_corrected_mean']}/period t {dct}")
        if r["cond"] not in GATE_OK: fails.append(f"live BEAR stand-down gate not applied ({r['cond']})")
        if m["max_loss"] > 1000: fails.append(f"max loss ${m['max_loss']:.0f} > $1000 per contract (XSP at 1/10 would be ${m['max_loss']/10:.0f})")
        if g[0] == "SPY" and g[1] == "PCS" and g[4] == "W0" and "paired_vs_baseline" in r and pbar:
            p = r["paired_vs_baseline"]
            if not (p["mean_diff"] > 0 and p["t_decision"] > pbar["bar95"]):
                fails.append(f"paired vs live 2%/4%: diff {p['mean_diff']}/wk t {p['t_decision']} <= paired bar {pbar['bar95']}")
        r["passes_search_bar"] = not fails
        r["why_or_why_not"] = "PASSES every search-period check" if not fails else "; ".join(fails)
        if not fails: candidates.append(r)
        elif len(fails) == 1 or (not math.isnan(td) and td > B and m["mean"] > 0): near.append(r)
    near.sort(key=lambda r: -tkey(r))
    log(f"PASSING: {len(candidates)}   near-misses (fail exactly one item, or clear the bar but fail others): {len(near)}")
    for r in candidates + near[:40]:
        log(("PASS " if r["passes_search_bar"] else "NEAR ") + r["name"], json.dumps(r["metrics"]), r["why_or_why_not"])

    # dead ends: aggregate by dimension
    def agg(keyf):
        d = defaultdict(list)
        for r in ok_rows:
            d[keyf(r)].append(r["metrics"]["mean"])
        return {k: dict(n_configs=len(v), mean_of_means=round(float(np.mean(v)), 2),
                        share_positive=round(float(np.mean([x > 0 for x in v])), 2)) for k, v in sorted(d.items(), key=lambda kv: str(kv[0]))}
    summary = dict(by_underlying=agg(lambda r: r["key"][0]), by_structure=agg(lambda r: r["key"][1]),
                   by_tenor=agg(lambda r: r["key"][4]), by_condition=agg(lambda r: r["cond"]),
                   by_short=agg(lambda r: f"{r['key'][2][0]}{r['key'][2][1]}"), by_width=agg(lambda r: f"{r['key'][3][0]}{r['key'][3][1]}"),
                   by_entry_day=agg(lambda r: r["key"][5]),
                   by_structure_condition=agg(lambda r: f"{r['key'][1]}|{r['cond']}"),
                   by_underlying_structure=agg(lambda r: f"{r['key'][0]}|{r['key'][1]}"))
    log("SUMMARY:", json.dumps(summary, indent=1))

    # delta-based vs percent-OTM strike selection: P&L and credit by SPY spot tercile (NONBEAR, W0, first-day entry)
    delta_vs_pct = []
    for g, tr in all_trades.items():
        if g[0] == "SPY" and g[1] == "PCS" and g[4] == "W0" and g[5] == 0:
            v = cond_filter(tr, "NONBEAR")
            if len(v) < 20: continue
            sp = np.array([r["spot"] for r in v]); x = np.array([r["pnl"] for r in v]); cr = np.array([r["credit"] for r in v])
            q1, q2 = np.percentile(sp, [33, 67]); msk = [sp < q1, (sp >= q1) & (sp < q2), sp >= q2]
            delta_vs_pct.append(dict(short=f"{g[2][0]}{g[2][1]}", width=f"{g[3][0]}{g[3][1]}", n=len(v),
                                     pnl_by_spot_tercile=[round(float(x[k].mean()), 1) for k in msk],
                                     credit_by_spot_tercile=[round(float(cr[k].mean()), 1) for k in msk],
                                     losses_by_spot_tercile=[int((x[k] < 0).sum()) for k in msk],
                                     mean_short_delta=round(float(np.mean([r["dl"] for r in v])), 3)))
    log("DELTA vs PCT:", json.dumps(delta_vs_pct))

    def pack(r):
        return dict(name=r["name"], spec=spec_of(r["key"], r["cond"]), metrics=r["metrics"], drops=r["drops"],
                    paired_vs_baseline=r.get("paired_vs_baseline"), passes_search_bar=r["passes_search_bar"],
                    why_or_why_not=r["why_or_why_not"])
    out = dict(family="A - INDEX PREMIUM SELLING (put/call credit spreads, iron condors) on SPY QQQ IWM TLT GLD",
               protocol="/tmp/research/PROTOCOL.md", search_window=[START, END], grid_size=len(rows),
               structural_configs=len(all_trades), conditions=CONDS, min_periods=MIN_N,
               permutation_bar=bar["bar95"], permutation_detail=bar, permutation_core_subgrid_informational=bar_core,
               paired_bar=pbar, baseline=dict(spec=spec_of(BASE_KEY, "NONBEAR"), metrics=bm, monday_only=bmon,
                                              all_regimes=metrics(base), drops=dict(all_drops[BASE_KEY]), kept_vs_dropped=base_diag),
               candidates=[pack(r) for r in candidates] + [pack(r) for r in near],
               top25_by_t=[pack(r) for r in top], summary=summary, delta_vs_pct_spy_pcs_w0_nonbear=delta_vs_pct,
               grid=[dict(name=r["name"], n=r["metrics"]["n"], mean=r["metrics"].get("mean"), t=r["metrics"].get("t_decision"),
                          halves=r["metrics"].get("halves"), q=r["metrics"].get("quarters_pos"), loo=r["metrics"].get("loo_t"),
                          maxloss=r["metrics"].get("max_loss"), passes=r["passes_search_bar"],
                          losses=(r["metrics"].get("tail") or {}).get("losses"), ev_lb=(r["metrics"].get("tail") or {}).get("ev_lb_realised"),
                          n_dropped=(r["metrics"].get("selection") or {}).get("n_dropped"),
                          dc_mean=(r["metrics"].get("selection") or {}).get("drop_corrected_mean"),
                          dc_t=(r["metrics"].get("selection") or {}).get("drop_corrected_t"),
                          paired_t=(r.get("paired_vs_baseline") or {}).get("t_decision")) for r in rows],
               dead_ends=[], notes=[
                   "DIA is not in search.db; excluded.",
                   "Chain days used 2024-07-23..2026-03-13 (contiguous); 2023-10/11 stubs excluded (no regime.json coverage).",
                   "Trades whose expiry falls after 2026-03-13 are dropped so no holdout close is ever read.",
                   "Statistic for the bar and the decision: min(|t_week|,|t_ticker-week|) clustered by EXPIRY ISO week; sign flips per expiry week shared across the grid.",
                   "Monthly tenor: one trade per monthly cycle (no overlapping positions).",
                   "ADDED (stricter, disclosed): a candidate must show >=3 losing periods and positive EV when the loss frequency is set to its Clopper-Pearson 95% upper bound (ev_lb_realised). Zero-loss samples have an unmeasured tail and cannot pass.",
                   "Permutation bar computed on the ELIGIBLE grid (n>=20) - the only grid a candidate can be picked from.",
                   "ADDED (stricter, disclosed): SELECTION-BIAS check. search.db holds only the 500 busiest contracts per ticker-day, so a far-OTM long strike is present mainly on active, rich-premium weeks. For every config the SHORT leg is priced on the dropped weeks too (it exists there); a drop-corrected ESTIMATE (short-leg P&L minus the average long-leg cost on kept weeks) must stay positive with clustered t > 2.0. This estimate uses substitution and is a diagnostic only, never a candidate metric.",
                   "Conditions NB_UPWK / NB_DNWK = non-BEAR and the prior ISO week's underlying return > +1% / < -1% (closes.json).",
                   "Weekday variants e1..e3 = 2nd..4th trading day of the ISO week (SPY only).",
                   "Live 2%/4% baseline re-measured on bid/ask (short@bid, long@ask), intrinsic settlement; the fivek backtest used a single daily price."])
    json.dump(out, open(f"{R}/index_premium_results.json", "w"), indent=1, default=str)
    log("WROTE", f"{R}/index_premium_results.json")

if __name__ == "__main__":
    main()

#!/usr/bin/env python
# FAMILY B - single-name defined-risk premium selling (put / call credit spreads on mega-caps)
# with the daily flow aggregates in search.db used as an ENTRY FILTER.
# Pre-registered grid (fixed before the first run):
#   side   in {P (put credit spread), C (call credit spread)}
#   otm    in {0,1,2,3,5,8%}     short strike distance from entry close (0-2% added as an extension, see below)
#   wpct   in {2%, 5%}            intended width as % of price, capped at 10 points ($1,000 max loss)
#   tenor  in {1, 2, 4} weeks     expiry = Friday of ISO week (entry week + tenor - 1)
#   filter in {none, flow_with, avoid_opp, quiet, persist2}
#   -> 2*6*2*3*5 = 360 configurations.  Level bar = sign-flip weeks x1000, 95th pct of max |t| over 180.
#   Filter value = paired difference (filter on vs off, same base structure), own bar from within-week
#   label shuffles x1000, 95th pct of max |t_diff| over the 144 filter configs.
# Conventions (PROTOCOL.md): entry at the close of the first trading day of each ISO week using that
# day's closing NBBO (sell at bid, buy at ask); hold to expiry; cash-settle on the expiry close
# (closes.json); BEAR stand-down (regime.json) for put credit spreads; call credit spreads ungated
# (the live gate only covers premium selling with short-put exposure).  Missing intended strike =
# DROP the ticker-week.  Search window 2024-09-03 .. 2026-03-13; expiry must fall inside it.
import sqlite3, json, sys, time, math, datetime as dt, collections
import numpy as np, pandas as pd

R = "/tmp/research"
FAMILY = "B_single_name_premium_flow_filter"
UNIV = "AAPL MSFT NVDA AMZN META GOOGL TSLA AMD AVGO NFLX JPM XOM UNH LLY COST WMT HD BAC COIN PLTR MSTR MU CRM ORCL".split()
D0, D1 = "2024-09-03", "2026-03-13"
FLOW_D0 = "2024-07-01"            # extra days before D0 only feed the trailing flow ranks
OTMS = [0.00, 0.01, 0.02, 0.03, 0.05, 0.08]
# GRID EXTENSION (declared after run 1 of the 3/5/8% grid, before any near-the-money number was seen):
# run 1 showed every 3-8% OTM structure loses because the executable credit is only ~1-9% of width;
# 0/1/2% OTM is the remaining part of this family, added as a whole block. The permutation bar below
# is recomputed on the full 360-config grid, so the extension pays its own multiple-testing cost.
WIDTHS = [0.02, 0.05]
TENORS = [1, 2, 4]
SIDES = ["P", "C"]
FILTERS = ["none", "flow_with", "avoid_opp", "quiet", "persist2"]
LOOK, MINLOOK, HI, LO = 60, 20, 0.8, 0.2
MAXW = 10.0                        # points; width*100 <= $1,000
NPERM, SEED = 1000, 20260918
SPLITS = {"NFLX": ("2025-11-17", 10.0)}   # closes.json is split-adjusted; the chain before this day is raw

t0 = time.time()
def log(*a):
    print(f"[{time.time()-t0:7.1f}s]", *a, flush=True)

closes = json.load(open(f"{R}/closes.json"))
regime = json.load(open(f"{R}/regime.json"))
con = sqlite3.connect(f"file:{R}/search.db?mode=ro", uri=True)
con.execute("pragma busy_timeout=120000")

db_days = [r[0] for r in con.execute("select distinct day from o where t='SPY' and day between ? and ? order by day", (D0, D1))]
day_set = set(db_days)
def iso_week(d):
    y, w, _ = dt.date.fromisoformat(d).isocalendar(); return y * 100 + w
weeks = sorted(set(iso_week(d) for d in db_days))
week_idx = {w: i for i, w in enumerate(weeks)}
entry_days = []
seen = set()
for d in db_days:
    w = iso_week(d)
    if w not in seen:
        seen.add(w); entry_days.append(d)
def friday_of(d, plus_weeks):
    dd = dt.date.fromisoformat(d)
    fri = dd + dt.timedelta(days=(4 - dd.weekday())) + dt.timedelta(weeks=plus_weeks)
    return fri
log(f"trading days {len(db_days)}  weeks {len(weeks)}  entry days {len(entry_days)}")

def raw_close(t, d):
    b = closes.get(t, {}).get(d)
    if b is None: return None
    c = b[3]
    if t in SPLITS and d < SPLITS[t][0]: c *= SPLITS[t][1]
    return c

def trailing_rank(v, look=LOOK, minlook=MINLOOK):
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        lo = max(0, i - look); prev = v[lo:i]
        if len(prev) >= minlook: out[i] = (prev < v[i]).mean()
    return out

trades = []
drops = collections.Counter()
basis_flags = []
for t in UNIV:
    df = pd.read_sql("select day,exp,cp,k,vol,askv,bidv,prem,bid,ask,delta,iv from o where t=? and day>=? and day<=?",
                     con, params=(t, FLOW_D0, D1))
    # ---- flow features per day (all expiries, all strikes present) ----
    df["vol"] = df["vol"].fillna(0); df["prem"] = df["prem"].fillna(0)
    df["net"] = np.where(df["vol"] > 0, df["prem"] * (df["askv"].fillna(0) - df["bidv"].fillna(0)) / df["vol"].replace(0, np.nan), 0.0)
    fl = df.groupby(["day", "cp"]).agg(net=("net", "sum"), prem=("prem", "sum"), mx=("prem", "max")).unstack("cp").fillna(0)
    fl.columns = ["_".join(c) for c in fl.columns]
    fl = fl.sort_index()
    for c in ["net_C", "net_P", "prem_C", "prem_P"]:
        if c not in fl: fl[c] = 0.0
    fl["tot"] = fl["prem_C"] + fl["prem_P"]
    fl["r_call"] = trailing_rank(fl["net_C"].values)
    fl["r_put"] = trailing_rank(fl["net_P"].values)
    fl["r_tot"] = trailing_rank(fl["tot"].values)
    fl["r_call_prev"] = fl["r_call"].shift(1); fl["r_put_prev"] = fl["r_put"].shift(1)
    flow = fl.to_dict("index")
    # ---- chain lookup: (day, exp, cp) -> arrays ----
    ch = {}
    sub = df[df["day"] >= D0]
    for key, g in sub.groupby(["day", "exp", "cp"]):
        g = g.sort_values("k")
        ch[key] = (g["k"].values, g["bid"].values, g["ask"].values)
    # event flag: ATM IV of this expiry vs ATM IV of the first expiry >= 25 days later (term-structure inversion)
    ivr = {}
    iv_atm = {}
    for key, g in sub[(sub["iv"] > 0) & (sub["cp"] == "P")].groupby(["day", "exp"]):
        i = (g["delta"] + 0.5).abs().values.argmin()
        if abs(g["delta"].values[i] + 0.5) < 0.15: iv_atm[key] = g["iv"].values[i]
    by_day = collections.defaultdict(list)
    for (d, e), v in iv_atm.items(): by_day[d].append((e, v))
    for d, lst in by_day.items():
        lst.sort()
        for e, v in lst:
            far = [v2 for e2, v2 in lst if (dt.date.fromisoformat(e2) - dt.date.fromisoformat(e)).days >= 25]
            if far: ivr[(d, e)] = v / far[0]
    exps_by_day = collections.defaultdict(set)
    for (d, e, cp) in ch: exps_by_day[d].add(e)
    # basis sanity: ATM strike vs close
    for d in entry_days[::8]:
        S = raw_close(t, d)
        g = sub[(sub["day"] == d) & (sub["cp"] == "P") & (sub["exp"] > d)]
        if S and len(g):
            g2 = g[g["exp"] == g["exp"].min()]
            katm = g2.iloc[(g2["delta"] + 0.5).abs().argmin()]["k"]
            if abs(katm / S - 1) > 0.10: basis_flags.append((t, d, S, katm))
    ntr = 0
    for d in entry_days:
        S = raw_close(t, d)
        if S is None: drops[(t, "no_close_entry")] += 1; continue
        f = flow.get(d)
        reg = regime.get(d, {}).get("regime")
        if reg is None: drops[(t, "no_regime")] += 1; continue
        for tenor in TENORS:
            fri = friday_of(d, tenor - 1)
            cands = [e for e in exps_by_day.get(d, ()) if fri - dt.timedelta(days=3) <= dt.date.fromisoformat(e) <= fri and e > d]
            if not cands: drops[(t, f"no_expiry_T{tenor}")] += 1; continue
            exp = max(cands)
            if exp > D1: drops[(t, f"exp_beyond_window_T{tenor}")] += 1; continue
            C = raw_close(t, exp)
            if C is None: drops[(t, "no_close_expiry")] += 1; continue
            if t in SPLITS and d < SPLITS[t][0] <= exp: drops[(t, "straddles_split")] += 1; continue
            iv_ratio = ivr.get((d, exp), np.nan)
            # strike grid step near the money on this expiry (both cps)
            ks_all = np.unique(np.concatenate([ch[(d, exp, cp)][0] for cp in "PC" if (d, exp, cp) in ch]))
            near = ks_all[(ks_all > 0.85 * S) & (ks_all < 1.15 * S)]
            if len(near) < 3: drops[(t, f"thin_chain_T{tenor}")] += 1; continue
            step = collections.Counter(np.round(np.diff(near), 4)).most_common(1)[0][0]
            for side in SIDES:
                if side == "P" and reg == "BEAR": drops[(t, "bear_gate_P")] += 1; continue
                if (d, exp, side) not in ch: drops[(t, f"no_{side}_rows_T{tenor}")] += 1; continue
                ks, bids, asks = ch[(d, exp, side)]
                kpos = {k: i for i, k in enumerate(ks)}
                for otm in OTMS:
                    if side == "P":
                        target = S * (1 - otm); below = ks[ks <= target]
                        if len(below) == 0: drops[(t, "no_short_strike")] += 1; continue
                        Ks = below.max()
                    else:
                        target = S * (1 + otm); above = ks[ks >= target]
                        if len(above) == 0: drops[(t, "no_short_strike")] += 1; continue
                        Ks = above.min()
                    if abs(Ks - target) > max(step, 0.015 * S): drops[(t, "short_strike_too_far")] += 1; continue
                    for wp in WIDTHS:
                        wpts = max(step, math.floor(min(wp * S, MAXW) / step + 1e-9) * step)
                        Kl = round(Ks - wpts, 4) if side == "P" else round(Ks + wpts, 4)
                        if Kl not in kpos: drops[(t, "long_strike_missing")] += 1; continue
                        bs, al = bids[kpos[Ks]], asks[kpos[Kl]]; as_, bl = asks[kpos[Ks]], bids[kpos[Kl]]
                        if not (bs > 0 and asks[kpos[Ks]] > 0 and al >= 0): drops[(t, "no_quote")] += 1; continue
                        credit = bs - al
                        if credit <= 0: drops[(t, "nonpos_credit")] += 1; continue
                        if side == "P": payoff = max(Ks - C, 0) - max(Kl - C, 0)
                        else: payoff = max(C - Ks, 0) - max(C - Kl, 0)
                        pnl = (credit - payoff) * 100.0
                        trades.append(dict(t=t, day=d, exp=exp, week=week_idx[iso_week(d)], q=f"{d[:4]}Q{(int(d[5:7])-1)//3+1}",
                                           tenor=tenor, side=side, otm=otm, wpct=wp, wpts=wpts, Ks=Ks, Kl=Kl, S=S, C=C,
                                           credit=credit, pnl=pnl, maxloss=(wpts - credit) * 100.0, reg=reg,
                                           bs=bs, as_=as_, bl=bl, al=al, mid_credit=((bs + as_) / 2 - (bl + al) / 2),
                                           iv_ratio=iv_ratio,
                                           r_call=f["r_call"] if f else np.nan, r_put=f["r_put"] if f else np.nan,
                                           r_tot=f["r_tot"] if f else np.nan,
                                           r_call_prev=f["r_call_prev"] if f else np.nan, r_put_prev=f["r_put_prev"] if f else np.nan))
                        ntr += 1
    log(f"{t}: {ntr} trades; drops {sum(v for k, v in drops.items() if k[0]==t)}")
    del df, sub, ch

TR = pd.DataFrame(trades)
TR.to_csv(f"{R}/familyB_trades.csv", index=False)
log(f"total trades {len(TR)}; basis flags {len(basis_flags)}")
if basis_flags: log("BASIS FLAGS (ticker, day, close, atm strike):", basis_flags[:20])

# ---- filter indicators ----
def filt_mask(sub, side, name):
    if name == "none": return np.ones(len(sub), bool), np.ones(len(sub), bool)
    rc, rp, rt = sub["r_call"].values, sub["r_put"].values, sub["r_tot"].values
    rcp, rpp = sub["r_call_prev"].values, sub["r_put_prev"].values
    if name == "flow_with":
        v = rc if side == "P" else rp; return v >= HI, ~np.isnan(v)
    if name == "avoid_opp":
        v = rp if side == "P" else rc; return v < HI, ~np.isnan(v)
    if name == "quiet":
        return rt <= LO, ~np.isnan(rt)
    if name == "persist2":
        v, vp = (rc, rcp) if side == "P" else (rp, rpp); return (v >= HI) & (vp >= HI), ~np.isnan(v) & ~np.isnan(vp)

def t_mean_cluster(y, cl):
    n = len(y)
    if n < 3: return np.nan
    m = y.mean(); e = y - m
    s = np.bincount(cl, weights=e); K = (np.bincount(cl) > 0).sum()
    if K < 2: return np.nan
    V = (s ** 2).sum() / n ** 2 * K / (K - 1)
    return m / math.sqrt(V) if V > 0 else np.nan

def t_diff_cluster(y, x, cl):
    xt = x - x.mean(); sxx = (xt ** 2).sum()
    if sxx == 0: return np.nan, np.nan
    b = (xt * y).sum() / sxx
    e = y - y.mean() - b * xt
    s = np.bincount(cl, weights=xt * e); K = (np.bincount(cl) > 0).sum()
    V = (s ** 2).sum() / sxx ** 2 * K / (K - 1)
    return b, (b / math.sqrt(V) if V > 0 else np.nan)

NW = len(weeks)
def metrics(sub):
    y = sub["pnl"].values; wk = sub["week"].values; n = len(y)
    if n < 20: return dict(n=n)
    blk = wk // 4
    tw = t_mean_cluster(y, wk); ttw = y.mean() / (y.std(ddof=1) / math.sqrt(n)); tb = t_mean_cluster(y, blk)
    ws = pd.Series(y).groupby(wk).sum()
    mid = np.median(wk); h1, h2 = y[wk <= mid].sum(), y[wk > mid].sum()
    qs = pd.Series(y).groupby(sub["q"].values).sum()
    cum = ws.cumsum(); dd = (cum - cum.cummax()).min()
    best = ws.idxmax(); loo = t_mean_cluster(y[wk != best], wk[wk != best])
    return dict(n=n, weeks=int(ws.size), total=round(y.sum(), 2), per_trade=round(y.mean(), 2), per_week=round(ws.mean(), 2),
                win=round((y > 0).mean(), 3), t_week=round(tw, 2), t_tw=round(ttw, 2), t_block4=round(tb, 2),
                t_min=round(min(tw, ttw, tb), 2), h1=round(h1, 2), h2=round(h2, 2),
                quarters={k: round(v, 2) for k, v in qs.items()}, q_pos=int((qs > 0).sum()), q_n=int(qs.size),
                worst_week=round(ws.min(), 2), worst_trade=round(y.min(), 2), max_dd=round(dd, 2),
                max_loss=round(sub["maxloss"].max(), 2), median_credit=round(sub["credit"].median(), 3),
                median_width=round(sub["wpts"].median(), 2), loo_t=round(loo, 2), best_week_sum=round(ws.max(), 2),
                drops=None)

configs = []
for side in SIDES:
    for tenor in TENORS:
        for otm in OTMS:
            for wp in WIDTHS:
                base = TR[(TR.side == side) & (TR.tenor == tenor) & (TR.otm == otm) & (TR.wpct == wp)]
                for fn in FILTERS:
                    m, defined = filt_mask(base, side, fn)
                    sub = base[m & defined]
                    configs.append(dict(side=side, tenor=tenor, otm=otm, wpct=wp, filter=fn, sub=sub, base=base[defined], mask=m[defined]))
log(f"configs {len(configs)}")

# ---- level permutation bar: sign-flip weeks, recompute t_week / t_tw / t_block for all configs ----
rng = np.random.default_rng(SEED)
F = rng.choice([-1.0, 1.0], size=(NPERM, NW))
maxt_w = np.zeros(NPERM); maxt_tw = np.zeros(NPERM); maxt_b = np.zeros(NPERM)
for c in configs:
    sub = c["sub"]; y = sub["pnl"].values; wk = sub["week"].values; n = len(y)
    if n < 20: continue
    W = np.bincount(wk, weights=y, minlength=NW); Nk = np.bincount(wk, minlength=NW).astype(float); K = (Nk > 0).sum()
    M = (F @ W) / n
    S = F * W[None, :] - Nk[None, :] * M[:, None]
    V = (S ** 2).sum(1) / n ** 2 * K / (K - 1)
    tw = np.abs(M / np.sqrt(V)); maxt_w = np.maximum(maxt_w, tw)
    # trade-level (ticker-week) t under the same week flips
    sumsq = (y ** 2).sum()                       # flips do not change y^2
    Vtw = (sumsq / n - M ** 2) * n / (n - 1)     # sample variance of flipped y
    ttw = np.abs(M / np.sqrt(Vtw / n)); maxt_tw = np.maximum(maxt_tw, ttw)
    blk = wk // 4; NB = NW // 4 + 1
    Wb = np.zeros((NPERM, NB)); Nb = np.bincount(blk, minlength=NB).astype(float); Kb = (Nb > 0).sum()
    for b in range(NB):
        sel = np.arange(NW)[np.arange(NW) // 4 == b]
        Wb[:, b] = F[:, sel] @ W[sel]
    Sb = Wb - Nb[None, :] * M[:, None]
    Vb = (Sb ** 2).sum(1) / n ** 2 * Kb / (Kb - 1)
    tb = np.abs(M / np.sqrt(Vb)); maxt_b = np.maximum(maxt_b, tb)
bar_w, bar_tw, bar_b = [float(np.percentile(v, 95)) for v in (maxt_w, maxt_tw, maxt_b)]
BAR = max(bar_w, bar_b)   # the ticker-week bar is reported separately; decision uses each t against its own bar
log(f"LEVEL permutation bar (95th pct of max|t| over {len(configs)} configs, {NPERM} week sign-flips): "
    f"t_week {bar_w:.2f}  t_tw {bar_tw:.2f}  t_block4 {bar_b:.2f}  -> BAR {BAR:.2f}")

# ---- filter (paired) permutation bar: shuffle filter labels within week ----
maxt_d = np.zeros(NPERM)
base_groups = {}
for c in configs:
    if c["filter"] == "none": continue
    key = (c["side"], c["tenor"], c["otm"], c["wpct"])
    base_groups.setdefault(key, []).append(c)
for key, cs in base_groups.items():
    base = cs[0]["base"]
    for c in cs:
        b = c["base"]; y = b["pnl"].values; wk = b["week"].values; x = c["mask"].astype(float)
        if len(y) < 20 or x.sum() < 10 or (1 - x).sum() < 10: continue
        order = np.argsort(wk, kind="stable"); ys, wks, xs = y[order], wk[order], x[order]
        for p in range(NPERM):
            xp = xs[np.lexsort((rng.random(len(xs)), wks))]   # within-week shuffle of the filter labels
            _, td = t_diff_cluster(ys, xp, wks)
            if not np.isnan(td): maxt_d[p] = max(maxt_d[p], abs(td))
bar_d = float(np.percentile(maxt_d, 95))
log(f"FILTER paired bar (95th pct of max|t_diff| over filter configs, {NPERM} within-week label shuffles): {bar_d:.2f}")

# ---- score every config ----
results = []
for c in configs:
    m = metrics(c["sub"])
    name = f"{c['side']}CS_otm{int(c['otm']*100)}_w{int(c['wpct']*100)}_T{c['tenor']}w_{c['filter']}"
    spec = dict(structure="put_credit_spread" if c["side"] == "P" else "call_credit_spread",
                short_strike=f"{'highest' if c['side']=='P' else 'lowest'} chain strike {'<=' if c['side']=='P' else '>='} close*(1{'-' if c['side']=='P' else '+'}{c['otm']}); must be within max(strike step, 1.5% of price) of target else DROP",
                width=f"max(step, floor(min({c['wpct']}*close, {MAXW})/step)*step) points; long strike must exist in that day's chain else DROP",
                tenor_weeks=c["tenor"], expiry="latest expiry within 3 days on/before Friday of ISO week (entry week + tenor - 1)",
                entry="close of first trading day of ISO week; sell short leg at closing BID, buy long leg at closing ASK",
                exit="hold to expiry; cash-settle intrinsic on expiry-day close (closes.json)",
                regime_gate="skip entry when regime.json[entry_day].regime == BEAR" if c["side"] == "P" else "none",
                filter=c["filter"], filter_def={
                    "none": "no filter",
                    "flow_with": f"trailing-{LOOK}d rank (min {MINLOOK} prior days) of net ask-side {'CALL' if c['side']=='P' else 'PUT'} premium on entry day >= {HI}",
                    "avoid_opp": f"trailing-{LOOK}d rank of net ask-side {'PUT' if c['side']=='P' else 'CALL'} premium on entry day < {HI}",
                    "quiet": f"trailing-{LOOK}d rank of total premium traded on entry day <= {LO}",
                    "persist2": f"flow_with condition true on entry day AND the prior trading day"}[c["filter"]],
                flow_def="net ask-side premium = sum over the day's rows of prem*(askv-bidv)/vol; ranks computed per ticker against its own trailing window",
                universe=UNIV, window=[D0, D1], splits=SPLITS)
    lvl_pass = False; why = []
    if m.get("n", 0) >= 20:
        ok_t = m["t_week"] > bar_w and m["t_tw"] > bar_tw and m["t_block4"] > bar_b; ok_h = m["h1"] > 0 and m["h2"] > 0
        ok_q = m["q_pos"] >= (m["q_n"] - 1 if m["q_n"] <= 7 else round(0.8 * m["q_n"]))
        ok_loo = m["loo_t"] > 1.5 and m["per_trade"] > 0
        lvl_pass = ok_t and ok_h and ok_q and ok_loo and m["max_loss"] <= 1000
        why = [f"t_week {m['t_week']} vs {bar_w:.2f}, t_tw {m['t_tw']} vs {bar_tw:.2f}, t_block4 {m['t_block4']} vs {bar_b:.2f} {'OK' if ok_t else 'FAIL'}",
               f"halves {m['h1']}/{m['h2']} {'OK' if ok_h else 'FAIL'}",
               f"quarters {m['q_pos']}/{m['q_n']} {'OK' if ok_q else 'FAIL'}",
               f"LOO t {m['loo_t']} {'OK' if ok_loo else 'FAIL'}"]
    paired = None
    if c["filter"] != "none":
        b = c["base"]; y = b["pnl"].values; wk = b["week"].values; x = c["mask"].astype(float)
        if len(y) >= 20 and x.sum() >= 10 and (1 - x).sum() >= 10:
            bdiff, td = t_diff_cluster(y, x, wk)
            paired = dict(diff_per_trade=round(bdiff, 2), t_diff_week=round(td, 2), bar=round(bar_d, 2),
                          n_on=int(x.sum()), n_off=int((1 - x).sum()), mean_on=round(y[x == 1].mean(), 2), mean_off=round(y[x == 0].mean(), 2),
                          passes=bool(td > bar_d and bdiff > 0))
    results.append(dict(name=name, spec=spec, metrics=m, paired_vs_unfiltered=paired, passes_search_bar=bool(lvl_pass), why_or_why_not="; ".join(why)))

# drops summary
drop_summary = collections.Counter()
for (t, r), v in drops.items(): drop_summary[r] += v
for r in results: r["metrics"]["drops"] = None
# regime / ticker diagnostics for the unfiltered structures
diag = {}
for side in SIDES:
    s = TR[TR.side == side]
    diag[f"{side}_by_regime_per_trade"] = {k: [round(v.mean(), 2), int(len(v))] for k, v in s.groupby("reg")["pnl"]}
    diag[f"{side}_by_ticker_per_trade"] = {k: round(v.mean(), 2) for k, v in s.groupby("t")["pnl"]}
    diag[f"{side}_by_tenor_per_trade"] = {int(k): round(v.mean(), 2) for k, v in s.groupby("tenor")["pnl"]}
    diag[f"{side}_by_otm_per_trade"] = {float(k): round(v.mean(), 2) for k, v in s.groupby("otm")["pnl"]}

for side in SIDES:
    for tenor in TENORS:
        s = TR[(TR.side == side) & (TR.tenor == tenor) & (TR.otm == 0.05) & (TR.wpct == 0.05)]
        if len(s) == 0: continue
        ev = s["iv_ratio"] > 1.3
        diag[f"{side}_T{tenor}_otm5_w5_spread_cost"] = dict(
            n=int(len(s)), exec_credit=round(s["credit"].mean(), 3), mid_credit_DIAGNOSTIC_ONLY=round(s["mid_credit"].mean(), 3),
            exec_pnl_per_trade=round(s["pnl"].mean(), 2),
            mid_pnl_per_trade_DIAGNOSTIC_ONLY=round((s["pnl"] + (s["mid_credit"] - s["credit"]) * 100).mean(), 2),
            short_leg_rel_spread=round(((s["as_"] - s["bs"]) / ((s["as_"] + s["bs"]) / 2)).median(), 3),
            event_weeks_n=int(ev.sum()), event_weeks_pnl=round(s.loc[ev, "pnl"].mean(), 2) if ev.sum() else None,
            non_event_pnl=round(s.loc[~ev & s["iv_ratio"].notna(), "pnl"].mean(), 2), iv_ratio_missing=int(s["iv_ratio"].isna().sum()))
passing = [r for r in results if r["passes_search_bar"]]
paired_pass = [r for r in results if r["paired_vs_unfiltered"] and r["paired_vs_unfiltered"]["passes"]]
out = dict(family=FAMILY, grid_size=len(configs), permutation_bar=round(BAR, 3),
           permutation_bar_detail=dict(t_week=round(bar_w, 3), t_ticker_week=round(bar_tw, 3), t_block4=round(bar_b, 3), filter_paired=round(bar_d, 3), nperm=NPERM, seed=SEED),
           n_trades=int(len(TR)), drops=dict(drop_summary), basis_flags=basis_flags[:50],
           candidates=results, diagnostics=diag,
           dead_ends=[], notes="")
json.dump(out, open(f"{R}/familyB_results.json", "w"), indent=1, default=float)
log(f"wrote {R}/familyB_results.json  passing level bar: {len(passing)}  filters passing paired bar: {len(paired_pass)}")

# ---- print table ----
cols = ["name", "n", "per_trade", "per_week", "win", "t_week", "t_tw", "t_block4", "h1", "h2", "q_pos", "loo_t", "max_dd", "max_loss", "worst_trade"]
print("\n" + " ".join(f"{c:>9}" for c in cols))
for r in sorted(results, key=lambda r: -(r["metrics"].get("t_min") or -99)):
    m = r["metrics"]
    if m.get("n", 0) < 20: print(f"{r['name']:>40} n={m.get('n')}"); continue
    pv = r["paired_vs_unfiltered"]
    ps = f"  paired diff {pv['diff_per_trade']:>7} t {pv['t_diff_week']:>5} ({pv['n_on']}/{pv['n_off']})" if pv else ""
    print(f"{r['name']:>40} " + " ".join(f"{str(m[c]):>9}" for c in cols[1:]) + ("  PASS" if r["passes_search_bar"] else "") + ps)
print("\nDROPS:", dict(drop_summary))
print("DIAG:", json.dumps(diag, indent=0, default=float)[:3000])

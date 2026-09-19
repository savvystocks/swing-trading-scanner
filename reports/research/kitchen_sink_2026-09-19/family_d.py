#!/usr/bin/env python
# FAMILY D - price-triggered, defined-risk directional (bullish). Pre-registered protocol: /tmp/research/PROTOCOL.md
# Reads ONLY /tmp/research/search.db (table o), closes.json, regime.json. Executable prices only (buy@ask, sell@bid).
# Run: ~/swing-trading-scanner/.venv/bin/python /tmp/research/family_d.py [--tickers SPY,QQQ] [--nperm 1000]
import json, sqlite3, datetime as dt, math, os, pickle, sys, collections, time, argparse
import numpy as np

R = "/tmp/research"
ap = argparse.ArgumentParser()
ap.add_argument("--tickers", default="SPY,QQQ,IWM,AAPL,AMZN,GOOGL,META,MSFT,NVDA,TSLA,AVGO")
ap.add_argument("--nperm", type=int, default=1000)
ap.add_argument("--out", default=f"{R}/family_d_results.json")
ap.add_argument("--cache", default=f"{R}/family_d_cache")
args = ap.parse_args()
TICKERS = args.tickers.split(",")
START, END = "2024-09-03", "2026-03-13"      # search period; expiries and exits must also be <= END
MAXLOSS = 1000.0
STRIKE_TOL = 0.015                            # intended strike must be within 1.5% of spot*target, else DROP
WIDTH_PCT, WIDTH_CAP = 0.02, 10.0             # spread width target: 2% of spot, capped at $10 (keeps max loss <= $1000), rounded UP to the strike grid
MIN_N, MIN_WEEKS = 20, 10                     # a config with fewer trades / distinct entry weeks is reported but not scored (degenerate t)
def grid_step(t, spot):                       # the liquid strike grid we intend to trade; anything off it is not a substitute, it is a DROP
    if t in ("SPY", "QQQ"): return 5.0
    if t == "IWM": return 1.0
    return 5.0 if spot >= 250 else (2.5 if spot >= 150 else 1.0)
HALF_SPLIT = "2025-06-08"                     # calendar midpoint of search period
os.makedirs(args.cache, exist_ok=True)

closes = json.load(open(f"{R}/closes.json"))
regime = json.load(open(f"{R}/regime.json"))
def d2(s): return dt.date.fromisoformat(s)
def isoweek(s): y, w, _ = d2(s).isocalendar(); return f"{y}-W{w:02d}"
def quarter(s): return f"{s[:4]}Q{(int(s[5:7])-1)//3+1}"

# ---------------------------------------------------------------- indicators from closes.json
def indicators(t):
    days = sorted(closes[t]); n = len(days)
    o = np.array([closes[t][d][0] for d in days]); c = np.array([closes[t][d][3] for d in days])
    delta = np.diff(c, prepend=c[0]); gain = np.where(delta > 0, delta, 0.0); loss = np.where(delta < 0, -delta, 0.0)
    rsi = np.full(n, np.nan); ag = gain[1:15].mean(); al = loss[1:15].mean()
    for i in range(15, n):
        ag = (ag*13 + gain[i])/14; al = (al*13 + loss[i])/14
        rsi[i] = 100.0 if al == 0 else 100 - 100/(1 + ag/al)
    out = {}
    for i, d in enumerate(days):
        if i < 50 or i+1 >= n: continue
        sma20 = c[i-19:i+1].mean(); sma50 = c[i-49:i+1].mean()
        out[d] = dict(i=i, c=c[i], dd20=c[i]/c[i-19:i+1].max()-1, dd50=c[i]/c[i-49:i+1].max()-1,
                      ret1=c[i]/c[i-1]-1, ret2=c[i]/c[i-2]-1, ret5=c[i]/c[i-5]-1, gap=o[i]/c[i-1]-1,
                      rsi=rsi[i], dist20=c[i]/sma20-1, up=bool(c[i] > sma50), up20=bool(c[i] > sma20),
                      breakout=bool(c[i] >= c[i-20:i].max()), two_down=bool(c[i] < c[i-1] and c[i-1] < c[i-2]),
                      month_end=bool(days[i+1][:7] != d[:7]))
    return days, out

TRIGGERS = {
    "PB":   lambda x, rg: x["up"] and -0.08 <= x["dd20"] <= -0.03,          # pullback 3-8% off 20d high inside uptrend
    "DD2":  lambda x, rg: x["up"] and x["ret1"] <= -0.02,                    # -2% day in uptrend (mean reversion)
    "DD3":  lambda x, rg: x["up"] and x["ret1"] <= -0.03,                    # -3% day in uptrend
    "BO":   lambda x, rg: x["breakout"],                                     # close at/above prior 20d closing high
    "2DN":  lambda x, rg: x["up"] and x["two_down"],                         # two consecutive down closes in uptrend
    "ME":   lambda x, rg: x["month_end"],                                    # last trading day of the month
    "RSI":  lambda x, rg: x["rsi"] < 35,                                     # oversold oscillator (any trend)
    "GAPDN": lambda x, rg: x["up"] and x["gap"] <= -0.015,                   # gap-open down >=1.5% in uptrend (entered at that day's close)
    "R5":   lambda x, rg: x["up"] and x["ret5"] <= -0.04,                    # 5-day return <= -4% in uptrend
    "BO50": lambda x, rg: x["dd50"] >= 0.0,                                  # close at the 50d closing high
}
EXPRS = {"CDS": ("C", 1.00), "PCS98": ("P", 0.98), "PCS96": ("P", 0.96)}   # (cp, moneyness of the first leg)
TENORS = {"T7": 7, "T14": 14, "T21": 21}                                     # min calendar days to a Friday expiry
EXITS = {"T7": ["HOLD"], "T14": ["HOLD", "X5"], "T21": ["HOLD", "X5"]}      # HOLD = cash-settle on expiry close; X5 = unwind at close of 5th trading day
SHAPES = [(tn, ex) for tn in TENORS for ex in EXITS[tn]]                    # 5 tenor/exit shapes
GRID = [(tr, e, tn, ex) for tr in TRIGGERS for e in EXPRS for tn, ex in SHAPES]
print(f"grid size {len(GRID)}", flush=True)

def nearest(ks, x): return min(ks, key=lambda k: (abs(k-x), k))

# ---------------------------------------------------------------- per-ticker: chain in memory, every-day trade table
def load_ticker(t):
    cf = f"{args.cache}/{t}.pkl"
    if os.path.exists(cf): return pickle.load(open(cf, "rb"))
    t0 = time.time()
    db = sqlite3.connect(f"file:{R}/search.db?mode=ro", uri=True); db.execute("pragma busy_timeout=120000")
    listed = collections.defaultdict(set)
    for exp, cp, k in db.execute("select distinct exp, cp, k from o where t=?", (t,)): listed[(exp, cp)].add(k)
    ch = {}
    for day, exp, cp, k, bid, ask in db.execute(
            "select day, exp, cp, k, bid, ask from o where t=? and day>=? and julianday(exp)-julianday(day) between 0 and 31",
            (t, START)):
        ch.setdefault((day, exp, cp), {})[k] = (bid, ask)
    db.close()
    cal = sorted(closes[t]); calset = set(cal)
    exps = sorted({e for (e, cp) in listed})
    def eligible_exp(e):   # weekly expiries only: Fridays, or Thursday when that Friday is a market holiday
        w = d2(e).weekday()
        if w == 4: return True
        if w == 3: fri = (d2(e)+dt.timedelta(days=1)).isoformat(); return fri not in calset
        return False
    exps = [e for e in exps if eligible_exp(e) and e in calset and e <= END]
    days, ind = indicators(t)
    table = {}; drops = collections.Counter()
    for d in days:
        if d < START or d > END or d not in ind or d not in regime: continue
        rg = regime[d]["regime"]
        if rg == "BEAR": continue          # live gate (D-1 convention): no bullish entries with SPY >2% under its 50d
        x = ind[d]; spot = x["c"]; dd = d2(d)
        for tn, tmin in TENORS.items():
            exp = next((e for e in exps if (d2(e)-dd).days >= tmin), None)
            if exp is None: drops[(tn, "no_expiry")] += 1; continue
            for ename, (cp, m1) in EXPRS.items():
                ks = listed.get((exp, cp))
                if not ks: drops[(ename, tn, "no_chain")] += 1; continue
                g = grid_step(t, spot)
                k1 = round(spot*m1/g)*g
                if abs(k1 - spot*m1) > STRIKE_TOL*spot: drops[(ename, tn, "strike_far")] += 1; continue
                width = max(1, math.ceil(min(WIDTH_PCT*spot, WIDTH_CAP)/g - 1e-9))*g
                k2 = k1 + width if cp == "C" else k1 - width
                if k1 not in ks or k2 not in ks: drops[(ename, tn, "strike_not_listed")] += 1; continue
                q = ch.get((d, exp, cp))
                if not q or k1 not in q or k2 not in q: drops[(ename, tn, "strike_unquoted_entry")] += 1; continue
                b1, a1 = q[k1]; b2, a2 = q[k2]
                if a1 < b1 or a2 < b2 or a1 <= 0 or a2 <= 0: drops[(ename, tn, "bad_quote")] += 1; continue
                if cp == "C":     # buy k1 @ask, sell k2 @bid
                    if b2 <= 0: drops[(ename, tn, "short_leg_no_bid")] += 1; continue
                    entry = -(a1 - b2)
                    if entry >= 0: drops[(ename, tn, "bad_quote")] += 1; continue
                    maxloss = -entry*100
                else:             # sell k1 @bid, buy k2 @ask
                    if b1 <= 0: drops[(ename, tn, "short_leg_no_bid")] += 1; continue
                    entry = b1 - a2
                    if entry <= 0: drops[(ename, tn, "no_credit")] += 1; continue
                    maxloss = (width - entry)*100
                if maxloss > MAXLOSS: drops[(ename, tn, "maxloss_gt_1000")] += 1; continue
                S = closes[t][exp][3]
                val = min(max(S - k1, 0.0), width) if cp == "C" else -min(max(k1 - S, 0.0), width)
                base = dict(t=t, d=d, exp=exp, k1=k1, k2=k2, width=width, entry=entry, maxloss=maxloss, rg=rg, spot=spot)
                table[(d, ename, tn, "HOLD")] = dict(base, xd=exp, pnl=(entry + val)*100)
                if "X5" in EXITS[tn]:
                    xi = x["i"] + 5
                    if xi >= len(cal): drops[(ename, tn, "X5", "no_exit_day")] += 1; continue
                    xd = cal[xi]
                    if xd > END or xd >= exp: drops[(ename, tn, "X5", "exit_after_end")] += 1; continue
                    qx = ch.get((xd, exp, cp))
                    if not qx or k1 not in qx or k2 not in qx: drops[(ename, tn, "X5", "strike_unquoted_exit")] += 1; continue
                    xb1, xa1 = qx[k1]; xb2, xa2 = qx[k2]
                    if cp == "C":   # sell k1 @bid, buy k2 @ask
                        if xa2 <= 0 or xa1 < xb1 or xa2 < xb2: drops[(ename, tn, "X5", "bad_exit_quote")] += 1; continue
                        unwind = xb1 - xa2
                    else:           # buy k1 @ask, sell k2 @bid
                        if xa1 <= 0 or xa1 < xb1 or xa2 < xb2: drops[(ename, tn, "X5", "bad_exit_quote")] += 1; continue
                        unwind = -(xa1 - xb2)
                    table[(d, ename, tn, "X5")] = dict(base, xd=xd, pnl=(entry + unwind)*100)
    res = dict(table=table, ind=ind, drops=dict(drops), cal=cal)
    pickle.dump(res, open(cf, "wb"))
    print(f"  {t}: chain keys {len(ch):,}  eligible days {sum(1 for d in ind if START<=d<=END)}  table rows {len(table):,}  {time.time()-t0:.0f}s", flush=True)
    return res

# ---------------------------------------------------------------- statistics
def ct(x, cl):
    x = np.asarray(x, float); n = len(x)
    if n < 2: return 0.0
    xb = x.mean(); S = collections.defaultdict(float)
    for v, c in zip(x - xb, cl): S[c] += v
    se = math.sqrt(sum(v*v for v in S.values()))/n
    return float(xb/se) if se > 0 else 0.0

def maxdd(p):
    cum = np.cumsum(p); peak = np.maximum.accumulate(cum); return float((cum - peak).min()) if len(p) else 0.0

def summarize(tr, key):
    x = np.array([r[key] for r in tr]); days = [r["d"] for r in tr]
    wk = [isoweek(d) for d in days]; tw = [r["t"] + isoweek(d) for r, d in zip(tr, days)]
    n = len(x); out = dict(n=n, weeks=len(set(wk)), total=round(float(x.sum()), 2), mean=round(float(x.mean()), 2),
        t_day=round(ct(x, days), 2), t_week=round(ct(x, wk), 2), t_tw=round(ct(x, tw), 2))
    out["t_min"] = min(out["t_week"], out["t_tw"])
    h1 = x[[d < HALF_SPLIT for d in days]]; h2 = x[[d >= HALF_SPLIT for d in days]]
    out["halves"] = [round(float(h1.sum()), 2) if len(h1) else None, round(float(h2.sum()), 2) if len(h2) else None]
    qs = collections.defaultdict(float)
    for v, d in zip(x, days): qs[quarter(d)] += v
    out["quarters"] = {q: round(v, 2) for q, v in sorted(qs.items())}
    out["q_pos"] = sum(v > 0 for v in qs.values()); out["q_n"] = len(qs)
    out["worst"] = round(float(x.min()), 2) if n else None; out["best"] = round(float(x.max()), 2) if n else None
    out["win_rate"] = round(float((x > 0).mean()), 3) if n else None
    out["maxdd"] = round(maxdd(x), 2)
    if n > 2:
        ib = int(x.argmax()); keep = [i for i in range(n) if i != ib]
        out["loo_trade_t"] = round(min(ct(x[keep], [wk[i] for i in keep]), ct(x[keep], [tw[i] for i in keep])), 2)
        out["loo_trade_mean"] = round(float(x[keep].mean()), 2)
        bw = max(set(wk), key=lambda w: x[[k == w for k in wk]].sum()); keep = [i for i in range(n) if wk[i] != bw]
        out["loo_week_t"] = round(min(ct(x[keep], [wk[i] for i in keep]), ct(x[keep], [tw[i] for i in keep])), 2) if len(keep) > 2 else 0.0
        out["loo_week_mean"] = round(float(x[keep].mean()), 2) if keep else None
        tk = sorted({r["t"] for r in tr}); lot = []
        for t in tk:
            keep = [i for i in range(n) if tr[i]["t"] != t]
            if len(keep) > 2: lot.append((t, round(float(x[keep].mean()), 2), round(min(ct(x[keep], [wk[i] for i in keep]), ct(x[keep], [tw[i] for i in keep])), 2)))
        out["lo_ticker_min_t"] = round(min(v[2] for v in lot), 2) if lot else None
        out["by_ticker"] = {t: [int(sum(1 for r in tr if r["t"] == t)), round(float(x[[r["t"] == t for r in tr]].sum()), 2)] for t in tk}
    return out

# ---------------------------------------------------------------- build trade sets
data = {}
for t in TICKERS:
    print(f"loading {t}", flush=True); data[t] = load_ticker(t)

# regime-matched every-day baseline per (ticker, expression shape): mean pnl over ALL eligible non-BEAR days in that regime
baseline = {}
for t in TICKERS:
    acc = collections.defaultdict(list)
    for (d, e, tn, ex), r in data[t]["table"].items(): acc[(e, tn, ex, r["rg"])].append(r["pnl"])
    for k, v in acc.items(): baseline[(t,) + k] = (float(np.mean(v)), len(v))

trades = {}; cfg_drops = {}
for (tr, e, tn, ex) in GRID:
    rows = []; overlap = 0
    for t in TICKERS:
        tab = data[t]["table"]; ind = data[t]["ind"]; last_exit = ""
        for d in sorted(ind):
            if d < START or d > END or d not in regime or regime[d]["regime"] == "BEAR": continue
            if not TRIGGERS[tr](ind[d], regime[d]["regime"]): continue
            r = tab.get((d, e, tn, ex))
            if r is None: continue
            if d <= last_exit: overlap += 1; continue          # one open position per ticker per config
            last_exit = r["xd"]
            b = baseline[(t, e, tn, ex, r["rg"])][0]
            rows.append(dict(r, excess=r["pnl"] - b))
    trades[(tr, e, tn, ex)] = rows; cfg_drops[(tr, e, tn, ex)] = overlap

# ---------------------------------------------------------------- permutation bars (common cluster-level sign flips across the grid)
rng = np.random.default_rng(20260918)
def perm_bar(key, cluster_fn, min_n=MIN_N):
    clusters = sorted({cluster_fn(r) for rows in trades.values() for r in rows}); cid = {c: i for i, c in enumerate(clusters)}
    signs = rng.choice([-1.0, 1.0], size=(args.nperm, len(clusters)))
    mx = np.zeros(args.nperm)
    for cfg, rows in trades.items():
        if len(rows) < min_n or len({isoweek(r["d"]) for r in rows}) < MIN_WEEKS: continue
        x = np.array([r[key] for r in rows]); ids = np.array([cid[cluster_fn(r)] for r in rows])
        u, inv = np.unique(ids, return_inverse=True)
        S = np.zeros(len(u)); nc = np.zeros(len(u)); np.add.at(S, inv, x); np.add.at(nc, inv, 1)
        sg = signs[:, u]; tot = sg @ S; xbar = tot/len(x)
        M = sg*S[None, :] - nc[None, :]*xbar[:, None]; se = np.sqrt((M**2).sum(1))
        tt = np.where(se > 0, np.abs(tot)/np.maximum(se, 1e-12), 0.0); mx = np.maximum(mx, tt)
    return float(np.percentile(mx, 95)), float(np.percentile(mx, 99))

bars = {}
for key in ("pnl", "excess"):
    bars[key + "_week"] = perm_bar(key, lambda r: isoweek(r["d"]))
    bars[key + "_tw"] = perm_bar(key, lambda r: r["t"] + isoweek(r["d"]))
BAR = {k: max(bars[k + "_week"][0], bars[k + "_tw"][0]) for k in ("pnl", "excess")}
bars50 = {k + "_week_n50": perm_bar(k, lambda r: isoweek(r["d"]), 50) for k in ("pnl", "excess")}
print("context: bars over only the n>=50 configs:", bars50, flush=True)
print("permutation bars (95th pct of max|t| over grid; 99th):", bars, "-> decision bars", BAR, flush=True)

# ---------------------------------------------------------------- score the grid
def passes(m, mx):
    if m["n"] < MIN_N or m["weeks"] < MIN_WEEKS: return False, f"insufficient n ({m['n']} trades, {m['weeks']} weeks) - not scored"
    why = []
    if m["mean"] <= 0: why.append("mean<=0")
    if m["t_min"] <= BAR["pnl"]: why.append(f"t_min {m['t_min']} <= bar {BAR['pnl']:.2f}")
    if mx["mean"] <= 0 or mx["t_min"] <= BAR["excess"]: why.append(f"excess t_min {mx['t_min']} <= bar {BAR['excess']:.2f} (does not beat regime-matched random entry)")
    if None in m["halves"] or min(m["halves"]) <= 0: why.append(f"half negative {m['halves']}")
    need = 6 if m["q_n"] <= 7 else 8
    if m["q_pos"] < need: why.append(f"quarters {m['q_pos']}/{m['q_n']} positive (<{need})")
    if m.get("loo_trade_t", 0) <= 1.5 or m.get("loo_trade_mean", 0) <= 0: why.append(f"leave-best-trade-out t {m.get('loo_trade_t')}")
    if m.get("loo_week_t", 0) <= 1.5: why.append(f"leave-best-week-out t {m.get('loo_week_t')}")
    return (len(why) == 0), ("PASS" if not why else "; ".join(why))

TRIG_RULE = {"PB": "close>SMA50 and -8%<=close/max(close,20d)-1<=-3%", "DD2": "close>SMA50 and 1d return<=-2%",
             "DD3": "close>SMA50 and 1d return<=-3%", "BO": "close>=max(prior 20 closes)", "2DN": "close>SMA50 and two consecutive down closes",
             "ME": "last trading day of calendar month", "RSI": "Wilder RSI14<35", "GAPDN": "close>SMA50 and open/prev close-1<=-1.5%",
             "R5": "close>SMA50 and 5-day return<=-4%", "BO50": "close>=max(close,50d)"}
LEGS = {"CDS": "buy call at 1.00*spot rounded to the strike grid @ask, sell call one width higher @bid",
        "PCS98": "sell put at 0.98*spot rounded to the strike grid @bid, buy put one width lower @ask",
        "PCS96": "sell put at 0.96*spot rounded to the strike grid @bid, buy put one width lower @ask"}
GRID_RULE = "strike grid: SPY/QQQ $5; IWM $1; stocks $5 if spot>=250, $2.50 if 150<=spot<250, $1 below 150; width = ceil(min(2%*spot,$10)/grid)*grid; both legs must be listed for that expiry and quoted (top-500 rows) that day or the period is DROPPED"
results = []
for cfg, rows in trades.items():
    tr, e, tn, ex = cfg
    if len(rows) < 3:
        results.append(dict(name="_".join(cfg), spec=dict(trigger=tr, expression=e, tenor=tn, exit=ex), metrics=dict(n=len(rows)), passes_search_bar=False, why_or_why_not="n<3", max_loss_per_contract=None)); continue
    m = summarize(rows, "pnl"); mx = summarize(rows, "excess")
    ok, why = passes(m, mx)
    ml = max(r["maxloss"] for r in rows)
    results.append(dict(name="_".join(cfg),
        spec=dict(trigger=tr, trigger_rule=TRIG_RULE[tr], expression=e, legs=LEGS[e], strike_grid=GRID_RULE,
                  tenor=tn, tenor_rule=f"first Friday(or holiday-Thursday) expiry >= {TENORS[tn]} calendar days from entry, entry at that day's closing NBBO",
                  exit=ex, exit_rule="cash-settle intrinsic on expiry close" if ex == "HOLD" else "unwind at closing NBBO of 5th trading day after entry (sell@bid/buy@ask)",
                  gates="regime.json[entry day] != BEAR (D-1 SPY vs 50d SMA); one open position per ticker per config; expiry and exit <= 2026-03-13; max loss <= $1000; intended strike within 1.5% of spot else DROP",
                  universe=TICKERS, period=[START, END]),
        metrics=dict(raw=m, excess_vs_regime_matched_random_entry=mx, max_loss_per_contract=round(ml, 2), overlap_skips=cfg_drops[cfg]),
        passes_search_bar=ok, why_or_why_not=why, max_loss_per_contract=round(ml, 2)))

results.sort(key=lambda r: -(r["metrics"]["raw"]["t_min"] if "raw" in r["metrics"] else -99))
print("\nTOP 30 by min clustered t (raw pnl):")
print(f"{'config':28s} {'n':>5s} {'$/tr':>8s} {'total':>9s} {'t_wk':>6s} {'t_tw':>6s} {'xs$':>7s} {'xs_t':>6s} {'halves':>22s} {'q+':>5s} {'loo':>5s} {'wr':>5s} {'mdd':>8s}  verdict")
for r in results[:30]:
    m = r["metrics"].get("raw"); mx = r["metrics"].get("excess_vs_regime_matched_random_entry")
    if not m: continue
    print(f"{r['name']:28s} {m['n']:5d} {m['mean']:8.1f} {m['total']:9.0f} {m['t_week']:6.2f} {m['t_tw']:6.2f} {mx['mean']:7.1f} {mx['t_min']:6.2f} {str(m['halves']):>22s} {m['q_pos']}/{m['q_n']} {m.get('loo_trade_t',0):5.2f} {m['win_rate']:5.2f} {m['maxdd']:8.0f}  {r['why_or_why_not'][:70]}")

# ---------------------------------------------------------------- CDS vs PCS on the SAME trigger events (paired)
pairs = []
for tr in TRIGGERS:
    for tn, ex in SHAPES:
        a = {(r["t"], r["d"]): r["pnl"] for r in trades[(tr, "CDS", tn, ex)]}
        for pe in ("PCS98", "PCS96"):
            b = {(r["t"], r["d"]): r["pnl"] for r in trades[(tr, pe, tn, ex)]}
            ks = sorted(set(a) & set(b))
            if len(ks) < 5: continue
            diff = np.array([a[k] - b[k] for k in ks]); wk = [isoweek(k[1]) for k in ks]; tw = [k[0] + isoweek(k[1]) for k in ks]
            pairs.append(dict(trigger=tr, tenor=tn, exit=ex, vs=pe, n=len(ks), cds_mean=round(float(np.mean([a[k] for k in ks])), 2),
                              pcs_mean=round(float(np.mean([b[k] for k in ks])), 2), diff_mean=round(float(diff.mean()), 2),
                              diff_t_min=round(min(ct(diff, wk), ct(diff, tw)), 2)))
print("\nCDS minus PCS, paired on identical trigger events (positive = debit spread better):")
for p in sorted(pairs, key=lambda p: p["diff_t_min"]):
    print(f"  {p['trigger']:4s} {p['tenor']:4s} {p['exit']:4s} vs {p['vs']:6s} n={p['n']:4d} CDS {p['cds_mean']:7.1f} PCS {p['pcs_mean']:7.1f} diff {p['diff_mean']:7.1f} t {p['diff_t_min']:5.2f}")

# ---------------------------------------------------------------- every-day (unconditional) expression means, for context
uncond = {}
for e in EXPRS:
    for tn, ex in SHAPES:
        allx = [r["pnl"] for t in TICKERS for (d, ee, tt, xx), r in data[t]["table"].items() if ee == e and tt == tn and xx == ex]
        uncond[f"{e}_{tn}_{ex}"] = dict(n=len(allx), mean=round(float(np.mean(allx)), 2) if allx else None)
print("\nUnconditional (every eligible non-BEAR day, all tickers) mean $/contract:", uncond)

top_trades = {}
for r in results[:8]:
    cfg = tuple(r["name"].split("_"))
    top_trades[r["name"]] = [dict(t=x["t"], d=x["d"], exp=x["exp"], xd=x["xd"], k1=x["k1"], k2=x["k2"], entry=round(x["entry"], 2), pnl=round(x["pnl"], 2), rg=x["rg"]) for x in trades[cfg]]
drops_all = {t: {"|".join(map(str, k)): v for k, v in data[t]["drops"].items()} for t in TICKERS}
out = dict(family="D - price-triggered defined-risk directional (bullish): call debit spread vs put credit spread on price triggers",
           grid_size=len(GRID), permutation_bar=BAR["pnl"], permutation_bars_detail=bars, context_bars_n_ge_50=bars50, nperm=args.nperm, top_config_trades=top_trades, universe=TICKERS, period=[START, END],
           candidates=results, cds_vs_pcs_paired=pairs, unconditional=uncond, drops=drops_all,
           dead_ends=[
             "Call debit spreads (a): unconditionally negative on every tenor/exit (-$15 to -$77 per contract on all non-BEAR days); only 12 of 50 CDS configs have a positive mean, best clustered t 1.30 (GAPDN_CDS_T14_HOLD). Paying the ask and receiving the bid on two legs at the closing NBBO costs roughly 4-8% of the width per round trip and no price trigger recovers it.",
             "Early unwind at day 5 (X5): every put-credit-spread X5 shape is unconditionally negative (-$10 to -$29) because the spread is paid twice; only hold-to-expiry shapes are positive, and their positivity is the bull tape (regime-matched every-day mean +$14 to +$23), not the trigger.",
             "Breakout to 20d/50d high, month-end, two consecutive down days, 3-8% pullback: excess over regime-matched random entry is ~0 or negative (excess t between -1.05 and +1.32). Month-end PCS98_T14: +$5,684 first half, -$1,733 second half - a regime artifact, not a calendar effect.",
             "RSI14<35 oversold: negative on most shapes (CDS -$33 to -$228 per contract); oversold in this sample kept falling.",
             "CDS vs PCS on identical trigger events (paired, own clustered t): the put credit spread beats the call debit spread on 79 of 100 pairings, significantly on every X5 pairing (t down to -5.24); the only reverse case (PB_T7 +$28.5) is t 1.00.",
             "Closest things to a signal - DD3 (-3% day inside uptrend) and GAPDN (gap-down >=1.5% inside uptrend) with a 2-week 4%-OTM put credit spread: +$70-75 per contract, 85-88% win rate, 6-7 of 7 quarters positive, but raw min clustered t 2.20-2.28 vs bar 4.47, excess over random entry only +$44-46 with t 1.24-1.25, and TSLA+AVGO supply 24 of the 47 DD3 trades. Not a candidate."],
           notes="Zero survivors. Every SELL at bid and BUY at ask (closing NBBO), settlement at intrinsic on the expiry close, BEAR stand-down from regime.json applied to every entry (all structures, not only index premium), one open position per ticker per config, expiry and exit <= 2026-03-13, max loss <= $1,000 per contract enforced (drops counted). Drops: 6,009 of 37,917 entry opportunities had an intended grid strike unquoted that day (top-500 chain), 1,225 X5 exits unquoted, 264 no eligible expiry, 170 strike not listed, 125 no credit. The permutation bar (4.47 raw / 4.81 excess, 95th pct of max|t| over 150 configs, cluster-level sign flips) is high because cluster-robust t with 20-60 clusters has fat tails; even the old 2.90 bar or the n>=50-only bar (4.18/3.92) clears nothing: max raw min-t 2.20, max excess min-t 1.72. The sample is one bull tape (2024-09..2026-03, non-BEAR days only): unconditional put-credit-spread hold-to-expiry is +$14-23 per contract per entry, which is beta plus premium, and the triggers do not add to it.")
json.dump(out, open(args.out, "w"), indent=1, default=str)
print(f"\nwrote {args.out}; passes: {[r['name'] for r in results if r['passes_search_bar']]}")

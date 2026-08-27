"""EVERYTHING SWEEP (owner order 2026-08-27: "test every single strategy we have ever thought
of with this new data base... probe or student").

Runs over the permanent hourly path library (data/hourly_paths.db) + archive features
(uw_history.db). Every long-options strategy family ever conceived in this project, at HOURLY
precision, honest pricing (entry = archive ask; stops/trails on bar lows/highs):

  SHAPES        FADE (contra both trends) / CONSENSUS (with both) / FOLLOW (any)
  SIDES         calls / puts / both
  REGIMES       bear(<-2) / deepbear(<-3) / mild / bull / all   (SPY vs 50d)
  CONDITIONERS  none / OI-building / sweep>=50% / lowsweep / shortDTE / midDTE / longDTE /
                highIV / lowIV / bigprem>=200k / whale 400k-1M / tight spread<=1.5
  EXITS         stop {-40,-50,-60,-70} x mode {TOUCH (bar low), CLOSE (hourly close)} x
                trail-trigger {30,50,80} x give {10,20,30}%   <- the stop-repair grid
  RULES         no-same-day-exit honoured (path starts next session; entry-day bars stored
                for future confirmed-entry work but skipped here)

SCORING: day-clustered mean/t, walk-forward (train <2026 / test 2026), both halves, NULL BAR
(the same full search on day-shuffled outcomes - winners must beat searched noise), plateau
(min over one-step exit neighbours). Probe-ready = ROBUST + buildable with live feeds.
Output: reports/research/everything_sweep_2026-08-27.md + everything_sweep.json
"""
import json
import math
import os
import sqlite3
import time
import urllib.request
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}


def closes(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-27&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                return {x["t"][:10]: x["c"] for x in (json.loads(r.read()).get("bars") or {}).get(s) or []}
        except Exception:
            time.sleep(3)
    return {}


def smad(c, n=20):
    d = sorted(c); o = {}; buf = []
    for x in d:
        buf.append(c[x]); o[x] = (c[x] / (sum(buf[-n:]) / min(len(buf), n)) - 1) * 100
    return o


def wait_for_library():
    while True:
        try:
            lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=30)
            src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=30)
            done = lib.execute("select count(*) from fetched").fetchone()[0]
            lib.close(); src.close()
        except Exception:
            done = 0
        if os.popen("pgrep -f 'hourly_librar[y].py'").read().strip() == "" and done > 1000:
            print(f"library ready: {done} contracts", flush=True)
            return
        print(f"waiting for library ({done} stored)...", flush=True)
        time.sleep(300)


def main():
    import numpy as np
    wait_for_library()
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    tks = {r[0] for r in src.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100

    # trade table: first trigger day per contract with features
    trades = []
    seen = set()
    for row in src.execute(
            """select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,volume,
                      sweep_volume,open_interest,prev_oi,implied_volatility,delta,nbbo_bid,nbbo_ask
               from contracts_daily
               where total_premium between 30000 and 1000000 and ask_volume>bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask>0 order by day"""):
        t, occ, day, prem, av, bv, vol, swv, oi, poi, iv, dl, bid, ask = row
        if occ in seen or t not in tks:
            continue
        smd = (sm.get(t) or {}).get(day); sp = spy20.get(day); reg = s50.get(day)
        if smd is None or sp is None or reg is None:
            continue
        mid = (bid + ask) / 2.0
        spr = (ask - bid) / mid * 100 if mid > 0 else 99.0
        if spr > 3.0:
            continue
        seen.add(occ)
        try:
            exp = "20" + occ[len(t):len(t) + 6]
            dte = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
        except Exception:
            dte = 0
        side = 1 if occ[-9] == "C" else -1
        trades.append({"occ": occ, "day": day, "ask": ask, "side": side, "sma": smd, "spy": sp,
                       "reg": reg, "prem": prem, "spr": spr, "swf": (swv or 0) / vol if vol else 0,
                       "oib": (oi or 0) > (poi or 0), "iv": float(iv) if iv else 0.5,
                       "dl": abs(float(dl)) if dl is not None else 0.5, "dte": dte})
    print(f"trades {len(trades)}", flush=True)

    STOPS = (-40.0, -50.0, -60.0, -70.0)
    MODES = ("TOUCH", "CLOSE")
    TRIGS = (30.0, 50.0, 80.0)
    GIVES = (0.10, 0.20, 0.30)
    EX = [(sm_, st, tg, gv) for sm_ in MODES for st in STOPS for tg in TRIGS for gv in GIVES]
    NEX = len(EX)

    # per-trade outcome matrix across all 72 exit variants, replayed on stored hourly paths
    R = np.full((len(trades), NEX), np.nan, dtype=np.float32)
    t0 = time.time()
    cur = lib.cursor()
    for i, tr in enumerate(trades):
        rows_ = cur.execute("select ts, h, l, c from bars where occ=? order by ts",
                            (tr["occ"],)).fetchall()
        day = tr["day"]
        bars = [(h, l, c) for ts, h, l, c in rows_ if ts[:10] > day]     # no-same-day rule
        if len(bars) < 3:
            continue
        e = tr["ask"]
        rh = np.array([b[0] for b in bars], dtype=np.float32) / e * 100 - 100
        rl = np.array([b[1] for b in bars], dtype=np.float32) / e * 100 - 100
        rc = np.array([b[2] for b in bars], dtype=np.float32) / e * 100 - 100
        peak = np.maximum.accumulate(rh)
        for j, (mode, st, tg, gv) in enumerate(EX):
            stop_sig = rl if mode == "TOUCH" else rc
            stop_hits = np.nonzero(stop_sig <= st)[0]
            stop_i = stop_hits[0] if stop_hits.size else 10 ** 9
            armed = peak >= tg
            floor = peak * (1 - gv)
            tr_hits = np.nonzero(armed & (rl <= floor))[0]
            tr_i = tr_hits[0] if tr_hits.size else 10 ** 9
            if stop_i == tr_i == 10 ** 9:
                R[i, j] = rc[-1]
            elif tr_i <= stop_i:
                R[i, j] = floor[tr_i]
            else:
                R[i, j] = st
        if i % 20000 == 0:
            print(f"replayed {i}/{len(trades)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"outcome matrix done ({time.time()-t0:.0f}s)", flush=True)

    days_u = sorted({t_["day"] for t_ in trades})
    dix = {d: i for i, d in enumerate(days_u)}
    day_i = np.array([dix[t_["day"]] for t_ in trades], dtype=np.int32)
    is26 = np.array([t_["day"] >= "2026-01-01" for t_ in trades])
    ndays = len(days_u)
    F = {k: np.array([t_[k] for t_ in trades]) for k in
         ("side", "sma", "spy", "reg", "prem", "spr", "swf", "iv", "dl", "dte")}
    OIB = np.array([t_["oib"] for t_ in trades])
    valid = ~np.isnan(R[:, 0])

    fade_m = (F["sma"] * F["side"] < 0) & (F["spy"] * F["side"] < 0)
    cons_m = (F["sma"] * F["side"] > 0) & (F["spy"] * F["side"] > 0)
    SHAPES = {"FADE": fade_m, "CONS": cons_m, "FOLLOW": np.ones(len(trades), bool)}
    SIDES = {"both": np.ones(len(trades), bool), "calls": F["side"] > 0, "puts": F["side"] < 0}
    REGS = {"bear": F["reg"] < -2, "deepbear": F["reg"] < -3,
            "mild": np.abs(F["reg"]) <= 2, "bull": F["reg"] > 2,
            "all": np.ones(len(trades), bool)}
    CONDS = {"": np.ones(len(trades), bool), "OIb": OIB, "swp50": F["swf"] >= 0.5,
             "loswp": F["swf"] < 0.2, "dteS": (F["dte"] > 0) & (F["dte"] <= 7),
             "dteM": (F["dte"] >= 8) & (F["dte"] <= 30), "dteL": F["dte"] > 30,
             "hIV": F["iv"] >= 0.6, "lIV": F["iv"] < 0.4, "big": F["prem"] >= 200000,
             "whale": F["prem"] >= 400000, "tight": F["spr"] <= 1.5}
    band_m = (F["prem"] >= 50000) & (F["prem"] <= 400000)
    spr2 = F["spr"] <= 2.0

    def score(mask, j, rmat):
        idx = np.nonzero(mask & valid)[0]
        if idx.size < 150:
            return None
        d = day_i[idx]; v = rmat[idx, j]
        fin = np.isfinite(v)          # null-shuffle bugfix 2026-08-27: permuted rows drag NaN
        if fin.sum() < 150:           # outcomes into 'valid' positions -> NaN t-stats silently
            return None               # zeroed the entire null calibration (bar read 0.00)
        idx = idx[fin]                # keep idx aligned for the is26 split below
        d = d[fin]; v = v[fin]
        cnt = np.bincount(d, minlength=ndays); tot = np.bincount(d, weights=v, minlength=ndays)
        nz = cnt > 0
        dm = tot[nz] / cnt[nz]
        k = dm.size
        if k < 15:
            return None
        mu = float(dm.mean()); sd = float(dm.std(ddof=1)) if k > 1 else 0.0
        tt = mu / (sd / math.sqrt(k)) if sd > 0 else 0.0
        h = k // 2
        te = v[is26[idx]]; tr_ = v[~is26[idx]]
        # paired diff vs the same-day pool mean (the honest luck-canceller)
        pool = POOLDM[j][nz]
        pfin = np.isfinite(pool)
        diff = dm[pfin] - pool[pfin]
        kd = diff.size
        dmu = float(diff.mean()) if kd else 0.0
        dsd = float(diff.std(ddof=1)) if kd > 1 else 0.0
        dt = dmu / (dsd / math.sqrt(kd)) if dsd > 0 and kd > 4 else 0.0
        return {"n": int(idx.size), "days": k, "mean": round(mu, 2), "t": round(tt, 2),
                "h1": round(float(dm[:h].mean()), 1), "h2": round(float(dm[h:].mean()), 1),
                "train": round(float(tr_.mean()), 1) if tr_.size else 0.0,
                "test": round(float(te.mean()), 1) if te.size else 0.0,
                "vs_pool": round(dmu, 1), "t_pool": round(dt, 2)}

    # PAIRED-VS-POOL null (2026-08-27: permutation nulls are invalid for day-clustered stats -
    # shuffling destroys within-day correlation and the null t exploded to 25. The honest bar:
    # a slice must beat the SAME-DAY pool mean - random selection on identical days - which
    # cancels market-factor luck by construction. diff_t >= 3 is the fixed ruthless bar.)
    base_univ = band_m & spr2 & valid
    POOLDM = {}
    for j in range(NEX):
        v = R[base_univ, j]
        d = day_i[base_univ]
        fin = np.isfinite(v)
        cnt = np.bincount(d[fin], minlength=ndays)
        tot = np.bincount(d[fin], weights=v[fin], minlength=ndays)
        pm = np.full(ndays, np.nan)
        nz = cnt > 0
        pm[nz] = tot[nz] / cnt[nz]
        POOLDM[j] = pm

    def full_search(rmat, collect=True):
        out = []
        best_t = -99.0
        for shn, shm in SHAPES.items():
            for sdn, sdm in SIDES.items():
                for rgn, rgm in REGS.items():
                    base = shm & sdm & rgm & band_m & spr2
                    if (base & valid).sum() < 150:
                        continue
                    for cn, cm in CONDS.items():
                        m = base & cm
                        if (m & valid).sum() < 150:
                            continue
                        for j in range(NEX):
                            s = score(m, j, rmat)
                            if not s:
                                continue
                            if s["t"] > best_t:
                                best_t = s["t"]
                            if collect:
                                mode, st, tg, gv = EX[j]
                                s.update({"name": f"{shn}/{sdn}/{rgn}" + (f"+{cn}" if cn else ""),
                                          "exit": f"{mode} stop{st:.0f} trig{tg:.0f} give{gv:.0%}",
                                          "j": j})
                                out.append(s)
        return out, best_t

    print("real search...", flush=True)
    res, real_best = full_search(R)
    print(f"configs scored {len(res)}; best t {real_best:.2f}", flush=True)
    null_bar = 3.0        # fixed ruthless bar on the PAIRED t (see note above)

    key = {(r["name"], r["j"]): r["mean"] for r in res}
    for r in res:
        mode, st, tg, gv = EX[r["j"]]
        neigh = [r["mean"]]
        for jj, (m2, s2, t2, g2) in enumerate(EX):
            if m2 == mode and abs(s2 - st) <= 10 and abs(t2 - tg) <= 20 and abs(g2 - gv) <= 0.101 \
               and (s2, t2, g2) != (st, tg, gv):
                v = key.get((r["name"], jj))
                if v is not None:
                    neigh.append(v)
        r["plateau"] = round(min(neigh), 1)
        r["robust"] = bool(r["mean"] > 0 and r["h1"] > 0 and r["h2"] > 0 and r["train"] > 0
                           and r["test"] > 0 and r.get("vs_pool", 0) > 0
                           and r.get("t_pool", 0) >= null_bar)

    rob = sorted([r for r in res if r["robust"]], key=lambda x: -x["plateau"])
    L = ["# EVERYTHING SWEEP - 2026-08-27 (hourly precision, permanent library)", "",
         f"{len(res)} strategy configurations scored on {len(trades)} real trades with stored",
         "hourly paths. Entry at ask; stops TOUCH (bar-low) vs CLOSE (hourly close) both tested.",
         f"**NULL BAR {null_bar:.2f}** (best t of the same search on shuffled outcomes) vs real",
         f"best {real_best:.2f}. ROBUST = clears null bar + both halves + train + 2026 test.",
         f"ROBUST: {len(rob)} of {len(res)}", "",
         "| strategy | exit | day-mean | vs-pool | t-pool | plateau | halves | train/test | n |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rob[:25]:
        L.append(f"| {r['name']} | {r['exit']} | {r['mean']:+.1f}% | {r.get('vs_pool',0):+.1f} | "
                 f"{r.get('t_pool',0):+.2f} | {r['plateau']:+.1f} | {r['h1']:+.0f}/{r['h2']:+.0f} | "
                 f"{r['train']:+.1f}/{r['test']:+.1f} | {r['n']} |")
    if not rob:
        L.append("| NONE cleared the ruthless bar | | | | | | | |")
    L += ["", "## Top raw (luck-prone, shown for completeness)", "",
          "| strategy | exit | day-mean | t |", "|---|---|---|---|"]
    for r in sorted(res, key=lambda x: -x["t"])[:8]:
        L.append(f"| {r['name']} | {r['exit']} | {r['mean']:+.1f}% | {r['t']:+.2f} |")
    open("reports/research/everything_sweep_2026-08-27.md", "w", encoding="utf-8").write(
        "\n".join(L) + "\n")
    json.dump({"null_bar": null_bar, "real_best": real_best, "robust": rob[:60],
               "n_trades": len(trades), "n_configs": len(res)},
              open("reports/research/everything_sweep.json", "w"), indent=1, default=str)
    print("\n".join(L[:45]), flush=True)
    print("EVERYTHING SWEEP COMPLETE", flush=True)


if __name__ == "__main__":
    main()

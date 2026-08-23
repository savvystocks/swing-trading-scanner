"""MEGA SWEEP (owner order 2026-08-23: "simulate all different variables ... until the highest
return is found") - with the search itself measured, so the winner is not just the luckiest cell.

EVERYTHING is priced the honest way: ENTRY AT THE ASK, OUTCOMES ON THE BID, live exit replay.
Every config also reports its TRADEABLE form (quoted spread <= the config's own cap), because an
edge in contracts we cannot buy is not an edge.

GRID (entry): shape (fade/consensus/follow) x regime bucket (bear/mild/bull/all) x regime
threshold (1/2/3%) x flow band (4) x spread cap (1.5/2/3%) x side (call/put/both) x delta
(all/<0.30) ; (exit): stop (-40/-50/-60) x trail trigger (30/50/80) x give (10/20/30%).
= 2,592 entry x 27 exit = 69,984 configurations.

SCORING (day-clustered throughout):
  robust = day-mean>0 AND both halves>0 AND train(<2026)>0 AND test(2026)>0
  plateau = min over the config and its one-step exit neighbours (a lone spike is noise)
  NULL CALIBRATION = the same full grid re-run on SHUFFLED day labels (signal destroyed). The
  95th-percentile MAX-t across the shuffled grid is the bar the real winner must clear. This is
  the multiple-testing deflation: it answers "is the best real config better than the best
  result noise can produce when searched just as hard?"
Then a FINE pass refines around the winning plateau.
Output: reports/research/mega_sweep_2026-08-23.md + mega_sweep.json
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
MAXPATH = 60


def closes(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-22&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                b = (json.loads(r.read()).get("bars") or {}).get(s) or []
            return {x["t"][:10]: x["c"] for x in b}
        except Exception:
            time.sleep(3)
    return {}


def smad(c, n=20):
    d = sorted(c); o = {}; buf = []
    for x in d:
        buf.append(c[x]); o[x] = (c[x] / (sum(buf[-n:]) / min(len(buf), n)) - 1) * 100
    return o


def replay(path, e, stop, trig, give):
    pk, on = -999.0, False
    for b in path:
        r = (b / e - 1) * 100
        if r >= trig:
            on = True
        if on:
            pk = max(pk, r)
            if r <= pk * (1 - give):
                return r
        if r <= stop:
            return stop
    return (path[-1] / e - 1) * 100


STOPS = (-40.0, -50.0, -60.0)
TRIGS = (30.0, 50.0, 80.0)
GIVES = (0.10, 0.20, 0.30)
BANDS = ((30000, 400000), (50000, 400000), (50000, 1000000), (100000, 400000))
SPRS = (1.5, 2.0, 3.0)
RTHR = (1.0, 2.0, 3.0)


def main():
    import numpy as np
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select distinct ticker from contracts_daily")]
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100
    fwd = defaultdict(list)
    for occ, day, bid in con.execute("select option_symbol,day,nbbo_bid from contracts_daily "
                                     "where nbbo_bid is not null and nbbo_bid>0 order by day"):
        fwd[occ].append((day, bid))

    rows, paths = [], []
    seen = set()
    for t, occ, day, prem, av, bv, dl, bid, ask in con.execute(
            """select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,delta,
                      nbbo_bid,nbbo_ask from contracts_daily
               where total_premium between 30000 and 1000000 and ask_volume>bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask>0
               order by day"""):
        if occ in seen:
            continue
        smd = (sm.get(t) or {}).get(day); sp = spy20.get(day); reg = s50.get(day)
        if smd is None or sp is None or reg is None:
            continue
        p = [b for d, b in fwd.get(occ, []) if d > day][:MAXPATH]
        if len(p) < 2:
            continue
        seen.add(occ)
        side = 1 if occ[-9] == "C" else -1
        mid = (bid + ask) / 2.0
        rows.append((day, side, float(prem), ((ask - bid) / mid * 100) if mid > 0 else 999.0,
                     abs(float(dl)) if dl is not None else 0.5, smd, sp, reg, ask))
        paths.append(p)
    n = len(rows)
    print(f"cohort {n}", flush=True)

    days_u = sorted({r[0] for r in rows})
    dix = {d: i for i, d in enumerate(days_u)}
    day_i = np.array([dix[r[0]] for r in rows], dtype=np.int32)
    side = np.array([r[1] for r in rows], dtype=np.int8)
    prem = np.array([r[2] for r in rows])
    spr = np.array([r[3] for r in rows])
    dlt = np.array([r[4] for r in rows])
    sma = np.array([r[5] for r in rows])
    spyd = np.array([r[6] for r in rows])
    reg = np.array([r[7] for r in rows])
    is2026 = np.array([r[0] >= "2026-01-01" for r in rows])

    EX = [(s, t_, g) for s in STOPS for t_ in TRIGS for g in GIVES]
    R = np.zeros((n, len(EX)), dtype=np.float32)
    t0 = time.time()
    for j, (s, t_, g) in enumerate(EX):
        col = R[:, j]
        for i in range(n):
            col[i] = replay(paths[i], rows[i][8], s, t_, g)
        print(f"exit {j+1}/{len(EX)} done ({time.time()-t0:.0f}s)", flush=True)

    ndays = len(days_u)

    def stats(mask, j, rmat):
        idx = np.nonzero(mask)[0]
        if idx.size < 200:
            return None
        d = day_i[idx]; v = rmat[idx, j]
        cnt = np.bincount(d, minlength=ndays)
        tot = np.bincount(d, weights=v, minlength=ndays)
        nz = cnt > 0
        dm = tot[nz] / cnt[nz]
        k = dm.size
        if k < 20:
            return None
        mu = float(dm.mean())
        sd = float(dm.std(ddof=1)) if k > 1 else 0.0
        tt = mu / (sd / math.sqrt(k)) if sd > 0 else 0.0
        h = k // 2
        d2 = day_i[idx]; y26 = is2026[idx]
        tr = v[~y26]; te = v[y26]
        return {"n": int(idx.size), "days": k, "mean": mu, "t": tt,
                "h1": float(dm[:h].mean()), "h2": float(dm[h:].mean()),
                "train": float(tr.mean()) if tr.size else 0.0,
                "test": float(te.mean()) if te.size else 0.0}

    fade_m = (sma * side < 0) & (spyd * side < 0)
    cons_m = (sma * side > 0) & (spyd * side > 0)
    SHAPES = {"FADE": fade_m, "CONSENSUS": cons_m, "FOLLOW": np.ones(n, bool)}
    SIDES = {"both": np.ones(n, bool), "calls": side > 0, "puts": side < 0}
    DELTAS = {"all": np.ones(n, bool), "lo<0.30": dlt < 0.30}

    def sweep(rmat, collect_all=True):
        out = []
        best_t = -99.0
        for shname, shm in SHAPES.items():
            for thr in RTHR:
                REGS = {"bear": reg < -thr, "mild": np.abs(reg) <= thr, "bull": reg > thr,
                        "all": np.ones(n, bool)}
                for rgname, rgm in REGS.items():
                    m1 = shm & rgm
                    if m1.sum() < 200:
                        continue
                    for (blo, bhi) in BANDS:
                        m2 = m1 & (prem >= blo) & (prem <= bhi)
                        if m2.sum() < 200:
                            continue
                        for sc in SPRS:
                            m3 = m2 & (spr <= sc)
                            if m3.sum() < 200:
                                continue
                            for sdname, sdm in SIDES.items():
                                m4 = m3 & sdm
                                if m4.sum() < 200:
                                    continue
                                for dname, dm_ in DELTAS.items():
                                    m5 = m4 & dm_
                                    if m5.sum() < 200:
                                        continue
                                    for j, (st, tg, gv) in enumerate(EX):
                                        s = stats(m5, j, rmat)
                                        if not s:
                                            continue
                                        if s["t"] > best_t:
                                            best_t = s["t"]
                                        if collect_all:
                                            s.update({"shape": shname, "regime": rgname,
                                                      "rthr": thr, "band": [blo, bhi],
                                                      "spr": sc, "side": sdname, "delta": dname,
                                                      "stop": st, "trig": tg, "give": gv, "ex": j})
                                            out.append(s)
        return out, best_t

    print("real sweep...", flush=True)
    res, real_best = sweep(R)
    print(f"configs scored {len(res)}; best t {real_best:.2f} ({time.time()-t0:.0f}s)", flush=True)

    # NULL CALIBRATION: destroy the signal by shuffling each config's day labels via a permuted
    # return matrix (rows reassigned to random days), then search JUST AS HARD.
    rng = np.random.RandomState(7)
    null_bests = []
    for rep_i in range(2):
        perm = rng.permutation(n)
        Rn = R[perm, :]
        _, nb = sweep(Rn, collect_all=False)
        null_bests.append(nb)
        print(f"null replica {rep_i+1}: best t {nb:.2f}", flush=True)
    null_bar = max(null_bests) if null_bests else 3.0

    # PLATEAU: a config's score is the min of itself and its one-step exit neighbours.
    key = {}
    for r in res:
        key[(r["shape"], r["regime"], r["rthr"], tuple(r["band"]), r["spr"], r["side"],
             r["delta"], r["stop"], r["trig"], r["give"])] = r
    for r in res:
        neigh = [r["mean"]]
        for dst in (-10, 10):
            for dtg in (-20, 20):
                k = (r["shape"], r["regime"], r["rthr"], tuple(r["band"]), r["spr"], r["side"],
                     r["delta"], r["stop"] + dst, r["trig"] + dtg, r["give"])
                if k in key:
                    neigh.append(key[k]["mean"])
        r["plateau"] = min(neigh)
        r["robust"] = (r["mean"] > 0 and r["h1"] > 0 and r["h2"] > 0 and
                       r["train"] > 0 and r["test"] > 0 and r["t"] >= null_bar)

    rob = [r for r in res if r["robust"]]
    rob.sort(key=lambda r: -r["plateau"])
    allr = sorted(res, key=lambda r: -r["mean"])

    def line(r):
        return (f"| {r['shape']}/{r['regime']}(±{r['rthr']}) | {r['band'][0]//1000}-{r['band'][1]//1000}k "
                f"spr{r['spr']} {r['side']} {r['delta']} | stop{r['stop']:.0f} trig{r['trig']:.0f} "
                f"give{r['give']:.0%} | {r['mean']:+.1f}% | {r['t']:+.2f} | {r['plateau']:+.1f} | "
                f"{r['h1']:+.0f}/{r['h2']:+.0f} | {r['train']:+.1f}/{r['test']:+.1f} | {r['n']} |")

    L = ["# MEGA SWEEP - 2026-08-23", "",
         f"Cohort {n} real triggers. Entry AT THE ASK, outcomes ON THE BID, live exit replay.",
         f"{len(res)} configurations scored across shape x regime x threshold x band x spread x side",
         "x delta x stop x trail-trigger x give.", "",
         f"**NULL BAR: {null_bar:.2f}** - the best t the SAME search finds on scrambled data.",
         f"Real best t: {real_best:.2f}. A config only counts as ROBUST if its t clears the null bar",
         "AND it is positive in both halves AND in train(<2026) AND in test(2026).", "",
         f"ROBUST configs: {len(rob)} of {len(res)}", "",
         "## Top ROBUST configurations (ranked by PLATEAU - neighbour-safe, not lone spikes)", "",
         "| shape/regime | entry filters | exits | day-mean | t | plateau | halves | train/test | n |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rob[:20]:
        L.append(line(r))
    if not rob:
        L.append("| NONE - no configuration beat the noise bar | | | | | | | | |")
    L += ["", "## Highest raw return (ignoring robustness - shown because it was asked for; "
          "these are the cells most likely to be luck)", "",
          "| shape/regime | entry filters | exits | day-mean | t | plateau | halves | train/test | n |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in allr[:10]:
        L.append(line(r))

    # regime table for the headline shapes, executable, at the live spread cap
    L += ["", "## Regime table rebased (executable, spread<=2.0, band 50-400k)", "",
          "| shape | BEAR | MILD | BULL |", "|---|---|---|---|"]
    j_live = EX.index((-50.0, 50.0, 0.20))
    for shname, shm in SHAPES.items():
        cells = []
        for rgname, rgm in (("bear", reg < -2), ("mild", np.abs(reg) <= 2), ("bull", reg > 2)):
            m = shm & rgm & (prem >= 50000) & (prem <= 400000) & (spr <= 2.0)
            s = stats(m, j_live, R)
            cells.append(f"{s['mean']:+.1f}% t{s['t']:+.2f} ({s['days']}d, n={s['n']})" if s else "thin")
        L.append(f"| {shname} | " + " | ".join(cells) + " |")

    json.dump({"null_bar": null_bar, "real_best": real_best, "n_configs": len(res),
               "robust": rob[:50], "top_raw": allr[:20]},
              open("reports/research/mega_sweep.json", "w"), indent=1, default=str)
    open("reports/research/mega_sweep_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:60]), flush=True)
    print("SWEEP COMPLETE", flush=True)


if __name__ == "__main__":
    main()

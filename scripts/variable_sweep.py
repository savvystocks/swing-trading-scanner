"""FULL VARIABLE SWEEP (owner order 2026-08-21 22:57: every variable, every figure, every
strategy core - no assumptions; runs at every promotion to seed the challenger ring).

Grid over the REAL harvest cohort (bid-path replays, spread toll embedded):
  band_lo {20,30,50,80,100}k x band_hi {250,400,600,1000}k x spr_max {1,1.5,2,2.5,3}
  x spy_max {1.0,1.5,2.5,99} x stop {-30,-40,-50,-60} x trig {30,50,70} x give {.1,.2,.3}
  = 14,400 configs per core, cores = fade-shape and consensus-shape.
Scoring: day-clustered day-mean, halves, n; ranked by PLATEAU score = min(own day-mean,
mean of one-step neighbors) - an isolated spike is luck, a good neighborhood is structure.
HONESTY: 14,400 configs is deliberate mass mining - results seed CHALLENGERS ONLY (each
still walks the hardened virgin bars vs CHAMPION); nothing here touches the live spec.
--reseed: rewrite challengers.json with the top stable one-dial deviations from the
current champion. Output: reports/research/sweep_latest.json + SWEEP.md
"""
import itertools
import json
import os
import sqlite3
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
GRID = {"band_lo": [20000, 30000, 50000, 80000, 100000],
        "band_hi": [250000, 400000, 600000, 1000000],
        "spr_max": [1.0, 1.5, 2.0, 2.5, 3.0],
        "spy_max": [1.0, 1.5, 2.5, 99.0],
        "stop": [-30, -40, -50, -60],
        "trig": [30, 50, 70],
        "give": [0.10, 0.20, 0.30]}
EXITS = [(s, t, g) for s in GRID["stop"] for t in GRID["trig"] for g in GRID["give"]]


def replay(pts, e, stop, trig, give):
    peak, on = -999.0, False
    for _, b in pts:
        r = (b / e - 1) * 100
        if r >= trig:
            on = True
        if on:
            peak = max(peak, r)
            if r <= peak * (1 - give):
                return r
        if r <= stop:
            return stop
    return (pts[-1][1] / e - 1) * 100


def load_all(db="data/harvest.db"):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
    rows = con.execute(
        """select c.candidate_id, c.entry_ref, c.right, c.spread_pct, c.rule_score, c.features,
                  cast(c.signal_ts_utc/86400000 as int)
           from candidates c join labels l on l.candidate_id=c.candidate_id
           where l.outcome is not null and c.entry_ref > 0 and c.features != ''""").fetchall()
    meta = {}
    for cid, e, right, spr, score, fj, day in rows:
        try:
            f = json.loads(fj)
        except Exception:
            continue
        sma = (f.get("macro") or {}).get("distance_to_sma20_pct")
        spy = (f.get("regime_stack") or {}).get("market_spy_dist_pct")
        if not isinstance(sma, (int, float)) or not isinstance(spy, (int, float)):
            continue
        side = 1 if right == "call" else -1
        meta[cid] = {"e": e, "side": side, "sma": sma, "spy": spy,
                     "spr": spr or 99, "score": score or 0, "day": day}
    paths = defaultdict(list)
    for cid, ts, bid in con.execute(
            "select candidate_id, poll_ts_utc, bid from bid_path where bid is not null and stale is not 1"):
        if cid in meta:
            paths[cid].append((ts, bid))
    keep = {c: sorted(p) for c, p in paths.items() if len(p) >= 3}
    return {c: meta[c] for c in keep}, keep


def main(reseed=False):
    meta, paths = load_all()
    print(f"cohort: {len(meta)} candidates, {len({m['day'] for m in meta.values()})} days", flush=True)
    exit_cache = {}                                     # (cid, exitcombo) -> ret, computed once
    for c, m in meta.items():
        for ex in EXITS:
            exit_cache[(c, ex)] = replay(paths[c], m["e"], *ex)
    print(f"exit cache built: {len(exit_cache)} replays", flush=True)
    results = {}
    for core, shape in (("FADE", -1), ("CONSENSUS", 1)):
        cids_by_filter = {}
        for bl, bh, sp, sy in itertools.product(GRID["band_lo"], GRID["band_hi"],
                                                GRID["spr_max"], GRID["spy_max"]):
            key = (bl, bh, sp, sy)
            cids_by_filter[key] = [c for c, m in meta.items()
                                   if (m["sma"] * m["side"] * shape > 0 and m["spy"] * m["side"] * shape > 0
                                       and m["spr"] <= sp and bl <= m["score"] <= bh
                                       and abs(m["spy"]) < sy)]
        rows = []
        for fkey, cids in cids_by_filter.items():
            if len(cids) < 40:
                continue
            for ex in EXITS:
                per_day = defaultdict(list)
                for c in cids:
                    per_day[meta[c]["day"]].append(exit_cache[(c, ex)])
                dm = [sum(v) / len(v) for v in per_day.values()]
                if len(dm) < 8:
                    continue
                mu = sum(dm) / len(dm)
                h = len(dm) // 2
                rows.append({"cfg": fkey + ex, "n": len(cids), "days": len(dm),
                             "day_mean": round(mu, 2),
                             "h1": round(sum(dm[:h]) / max(h, 1), 1),
                             "h2": round(sum(dm[h:]) / max(len(dm) - h, 1), 1)})
        bymap = {r["cfg"]: r["day_mean"] for r in rows}
        names = ["band_lo", "band_hi", "spr_max", "spy_max", "stop", "trig", "give"]
        for r in rows:
            nb = []
            for i, pname in enumerate(names):
                vals = GRID[pname]
                idx = vals.index(r["cfg"][i])
                for j in (idx - 1, idx + 1):
                    if 0 <= j < len(vals):
                        k = list(r["cfg"]); k[i] = vals[j]
                        v = bymap.get(tuple(k))
                        if v is not None:
                            nb.append(v)
            r["plateau"] = round(min(r["day_mean"], sum(nb) / len(nb)), 2) if nb else r["day_mean"]
        rows.sort(key=lambda r: -r["plateau"])
        results[core] = rows[:40]
        print(f"{core}: {len(rows)} configs scored; top plateau {rows[0] if rows else None}", flush=True)
    os.makedirs("reports/research", exist_ok=True)
    json.dump(results, open("reports/research/sweep_latest.json", "w"), indent=1)
    L = ["# Full variable sweep - " + __import__("datetime").date.today().isoformat(),
         "", "14,400 configs/core on the real harvest cohort; ranked by PLATEAU (min of own",
         "day-mean and one-step-neighbor mean). Seeds challengers ONLY - virgin bars decide.", ""]
    for core in results:
        L.append(f"## {core} top 10 (band_lo, band_hi, spr, spy, stop, trig, give)")
        for r in results[core][:10]:
            L.append(f"- {r['cfg']} plateau {r['plateau']:+.2f} mean {r['day_mean']:+.2f} "
                     f"n={r['n']} days={r['days']} halves {r['h1']:+.1f}/{r['h2']:+.1f}")
        L.append("")
    open("reports/research/SWEEP.md", "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L), flush=True)

    if reseed and results.get("FADE"):
        spec = json.load(open("fade_book_spec.json"))
        e, x = spec.get("entry", {}), spec.get("exit", {})
        champ = (e.get("flow_min", 50000), e.get("flow_max", 400000), e.get("max_spread_pct", 2.0),
                 e.get("max_spy_dist_pct", 99.0), x.get("stop", -50), x.get("trail_activate", 50),
                 (x.get("trail_drawdown", 20) / 100.0 if x.get("trail_drawdown", 20) > 1
                  else x.get("trail_drawdown", 0.2)))
        names = ["band_lo", "band_hi", "spr_max", "spy_max", "stop", "trig", "give"]
        spec_keys = {"band_lo": "entry.flow_min", "band_hi": "entry.flow_max",
                     "spr_max": "entry.max_spread_pct", "spy_max": "entry.max_spy_dist_pct",
                     "stop": "exit.stop"}
        books, menu, used = {}, {}, set()
        for r in results["FADE"]:
            diff = [i for i in range(7) if r["cfg"][i] != champ[i]]
            if len(diff) != 1 or r["plateau"] <= 0:
                continue                       # one-dial deviations from champion only
            i = diff[0]
            pname, val = names[i], r["cfg"][i]
            if (pname, val) in used or len(used) >= 6:
                continue
            used.add((pname, val))
            nm = f"CH_{pname.upper()[:8]}_{str(val).replace('.', 'p').replace('-', 'm')}"
            if pname in ("band_lo", "band_hi", "spr_max", "spy_max"):
                books[nm] = {pname: val}
            else:
                books[nm] = {pname: val}
            if pname in spec_keys:
                menu[nm] = {spec_keys[pname]: val, "_vs": "CHAMPION"}
        if books:
            json.dump({"note": "ring SWEEP-seeded " + __import__("datetime").date.today().isoformat()
                               + " - top one-dial plateau deviations from champion",
                       "books": books, "menu": menu}, open("challengers.json", "w"), indent=1)
            print(f"reseeded challenger ring: {list(books)}", flush=True)


if __name__ == "__main__":
    main(reseed="--reseed" in sys.argv)

"""HARDENED-SCOREBOARD SIMULATION (owner order 2026-08-19 01:30: simulate before building).

Runs BOTH scoreboards over REAL corpus data (3,743 replayed candidates, 2024-09..2026-07):
  CURRENT : 10d window, mean>0, mean(diff vs comparator) > +2.0 raw pts, both halves > 0
  HARDENED: same window, mean>0, halves>0, t(diff) must beat the 95th percentile of what
            200 hash-seeded PLACEBO books (random picks from the same real days) achieve
Books tested: FADE_MILD (our best real-edge candidate, corpus t=2.26), CONS_TREND, WHALE,
and the 200 placebos themselves (the noise flow-through measurement).
Comparator: the all-candidate day-mean (EXEC_BASELINE analogue).
Output: pass rates per book per scoreboard = measured false-promotion and detection rates
on real market data, before a line of the new scoreboard is built.
"""
import json
import math
import os
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = json.load(open(os.path.join(REPO, "reports/research/historical_corpus_2026-08-13/rows.json")))


def replay(closes, e):
    peak, on = -999.0, False
    for b in closes:
        r = (b / e - 1) * 100
        if r >= 50:
            on = True
        if on:
            peak = max(peak, r)
            if r <= peak * 0.8:
                return r
        if r <= -50:
            return -50
    return (closes[-1] / e - 1) * 100


by_day = defaultdict(list)
for r in rows:
    ret = replay([c for _, c in r["path"]], r["e"])
    mild = abs(r["spy"]) < 1.5
    tags = ["ALL"]
    if r["shape"] == "fade" and mild and r["prem"] <= 400000:
        tags.append("FADE_MILD")
    if r["shape"] == "consensus" and not mild:
        tags.append("CONS_TREND")
    if r["shape"] == "fade" and mild and r["prem"] > 400000:
        tags.append("WHALE")
    by_day[r["day"]].append((ret, tags, r["occ"]))

days = sorted(by_day)
series = defaultdict(dict)
for d in days:
    pool = by_day[d]
    base = [x for x, _, _ in pool]
    series["COMPARATOR"][d] = sum(base) / len(base)
    for name in ("FADE_MILD", "CONS_TREND", "WHALE"):
        v = [x for x, t, _ in pool if name in t]
        if v:
            series[name][d] = sum(v) / len(v)
    for p in range(200):                       # placebo army: hash-picked from the same real days
        v = [x for x, _, o in pool if hash(f"{p}:{o}") % 5 == 0]
        if v:
            series[f"PL{p}"][d] = sum(v) / len(v)


def windows(book, n=10, step=5):
    bd = series[book]
    shared = [d for d in days if d in bd and d in series["COMPARATOR"]]
    for i in range(0, len(shared) - n + 1, step):
        w = shared[i:i + n]
        vals = [bd[d] for d in w]
        diffs = [bd[d] - series["COMPARATOR"][d] for d in w]
        yield vals, diffs


def cur_pass(vals, diffs):
    h = len(vals) // 2
    return (sum(vals) / len(vals) > 0 and sum(diffs) / len(diffs) > 2.0
            and sum(vals[:h]) / h > 0 and sum(vals[h:]) / (len(vals) - h) > 0)


def tstat(diffs):
    n = len(diffs)
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    return mu / (sd / math.sqrt(n)) if sd > 0 else 0.0


pl_ts = []
for p in range(200):
    for vals, diffs in windows(f"PL{p}"):
        pl_ts.append(tstat(diffs))
pl_ts.sort()
thr = pl_ts[int(len(pl_ts) * 0.95)] if pl_ts else 1.83
print(f"placebo army: {len(pl_ts)} windows, empirical 95th-pct t threshold = {thr:.2f}")


def hard_pass(vals, diffs):
    h = len(vals) // 2
    return (sum(vals) / len(vals) > 0 and tstat(diffs) >= thr
            and sum(vals[:h]) / h > 0 and sum(vals[h:]) / (len(vals) - h) > 0)


print(f"{'book':12s} {'windows':>7s} {'CURRENT pass':>13s} {'HARDENED pass':>14s}")
for name in ("FADE_MILD", "CONS_TREND", "WHALE"):
    ws = list(windows(name))
    if not ws:
        print(f"{name:12s} {'0':>7s}")
        continue
    c = sum(cur_pass(v, df) for v, df in ws)
    hd = sum(hard_pass(v, df) for v, df in ws)
    print(f"{name:12s} {len(ws):7d} {c:5d} ({c/len(ws)*100:4.0f}%) {hd:6d} ({hd/len(ws)*100:4.0f}%)")
pc = ph = pw = 0
for p in range(200):
    for v, df in windows(f"PL{p}"):
        pw += 1
        pc += cur_pass(v, df)
        ph += hard_pass(v, df)
print(f"{'PLACEBO x200':12s} {pw:7d} {pc:5d} ({pc/pw*100:4.1f}%) {ph:6d} ({ph/pw*100:4.1f}%)")
print(f"\nnoise flow-through: CURRENT {pc/pw*100:.1f}% vs HARDENED {ph/pw*100:.1f}% "
      f"| detection cost on FADE_MILD shown above")

"""STUDENT: TRAIN ON WHAT IT BUYS, AND SEARCH ITS EXIT (research, READ-ONLY).

Owner order 2026-09-16 01:42 BST. Two questions, one script, nothing written to the spec, the model
files or the court clock.

1. COHORT. STUDENT_A is trained AND calibrated on the ALL cohort - 70,976 rows, most of them
   contracts the $1,000 seat can never buy - and then executes only what fits the cap. The code
   already defines a CAP1000 cohort (entry $0.30-9.90). This rebuilds A's walk-forward stream both
   ways and compares them on the slice that actually trades.

2. EXIT. 37% of A's executed picks die at the -50% stop. The fine grid
   (reports/research/glide_fine_rows_v3.jsonl, 210 configs: 7 stops x 6 triggers x 5 givebacks) is
   joined to those picks by (occ, day). Searching 210 configs on ~68 trades is curve-fitting, so the
   headline result is WALK-FORWARD on the exit too: the config is chosen on the FIRST half of weeks
   and scored on the SECOND half it never saw. The in-sample best is printed only as a reference and
   is labelled as a search result.

Robustness on every cell, because this book's means are carried by a few trades: best-removed,
top-3-removed, median, stop-out rate, weekly t and both halves.
"""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.expanduser("~/swing-trading-scanner")
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import numpy as np
from src import student_features as sfx
import student_formula_sim as sf
from student_export import cohort_mask, ASOF, EXIT_IDX

os.environ["FEATURE_SET"] = "ASOF"
FINE = "reports/research/glide_fine_rows_v3.jsonl"
STOPS = [-45.0, -50.0, -55.0, -60.0, -65.0, -70.0, -75.0]
TRIGS = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0]
GIVES = [0.15, 0.20, 0.25, 0.30, 0.35]
GRID = [(s, t, g) for s in STOPS for t in TRIGS for g in GIVES]
BASE_IX = GRID.index((-50.0, 50.0, 0.20))


def wk(d):
    return date.fromisoformat(d).isocalendar()[:2]


def tstat(x):
    n = len(x)
    if n < 3:
        return 0.0
    m = sum(x) / n
    sd = (sum((v - m) ** 2 for v in x) / (n - 1)) ** 0.5
    return (m / (sd / math.sqrt(n))) if sd > 0 else 0.0


def describe(pct, weeks_usd, label):
    n = len(pct)
    if n < 5:
        return f"  {label:<34} thin ({n})"
    sp = sorted(pct)
    nobest = (sum(sp) - sp[-1]) / (n - 1)
    no3 = (sum(sp) - sum(sp[-3:])) / (n - 3) if n > 3 else float("nan")
    w = [weeks_usd[k] for k in sorted(weeks_usd)]
    h = len(w) // 2
    return (f"  {label:<34} n {n:>3}  mean {sum(pct)/n:+7.1f}%  best-removed {nobest:+7.1f}%  top3-removed {no3:+7.1f}%  "
            f"med {sp[n//2]:+6.1f}%  win {sum(1 for x in pct if x > 0)/n:.0%}  stops {sum(1 for x in pct if x <= -50)/n:.0%}  "
            f"wk$ {sum(w)/len(w):+7.0f} t {tstat(w):+5.2f}  halves {sum(w[:h])/max(1,h):+7.0f}/{sum(w[h:])/max(1,len(w)-h):+7.0f}")


def main():
    spec = json.load(open("fade_book_spec.json", encoding="utf-8"))
    stu = (spec.get("probe") or {}).get("student") or {}
    cfg = (stu.get("probes") or {}).get("STUDENT_A") or {}
    cap = float(cfg.get("exec_max_ask", stu.get("exec_max_ask", 10.0)))
    k_pw = int(cfg.get("k_per_week", 3))
    target = cfg.get("target", "EXPRET")
    ei = EXIT_IDX.get(cfg.get("exit_label", "BASE"), 0)
    rows = [json.loads(l) for l in open(ASOF, encoding="utf-8")]
    X = np.array([r["vec"] for r in rows], float)
    days = [r["day"] for r in rows]
    rets = np.array([r["rets"][ei] if r["rets"][ei] is not None else np.nan for r in rows])
    y_cls = (rets > 0).astype(int)
    y_big = (rets >= 30).astype(int)
    y_reg = np.clip(np.nan_to_num(rets, nan=0.0), -100, 300)

    def stream_and_pick(cohort):
        cm = cohort_mask(rows, cohort) & ~np.isnan(rets)
        oos = sf.fit_stream(X, y_cls, y_big, y_reg, days, target, cm)
        have = cm & ~np.isnan(oos)
        # thresholds calibrated exactly as student_export does: trailing 60 sessions of the OOS stream
        sub = sorted(set(np.array(days)[have]))[-60:]
        tail = have & np.isin(np.array(days), sub)
        weeks = max(1, len({wk(d) for d in np.array(days)[tail]}))
        per_week = tail.sum() / weeks
        q = 1.0 - min(0.5, (3 * 1.5) / per_week)
        bar = float(np.quantile(oos[tail], q))              # k3, the live bar
        idx = [i for i in np.argsort(np.array(days)) if have[i] and not np.isnan(oos[i]) and oos[i] >= bar]
        byd = defaultdict(list)
        for i in idx:
            byd[days[i]].append(i)
        out, cnt = [], defaultdict(int)
        for d in sorted(byd):
            for i in sorted(byd[d], key=lambda j: -oos[j]):
                if cnt[wk(d)] >= k_pw:
                    break
                cnt[wk(d)] += 1
                out.append(i)
        ex = [i for i in out if rows[i]["entry"] <= cap]
        return oos, have, bar, out, ex

    print("=== 1. COHORT: trained on ALL (live) vs trained on CAP1000 (what it buys) ===", flush=True)
    res = {}
    for cohort in ("ALL", "CAP1000"):
        print(f"  rebuilding the walk-forward stream on {cohort}...", flush=True)
        oos, have, bar, picks, ex = stream_and_pick(cohort)
        pct = [rows[i]["rets"][ei] or 0.0 for i in ex]
        wkusd = defaultdict(float)
        for i in ex:
            r = rows[i]
            p = r["rets"][ei] or 0.0
            wkusd[wk(r["day"])] += max(1, int(1000.0 // (r["entry"] * 100))) * p / 100.0 * r["entry"] * 100.0
        res[cohort] = (ex, pct, wkusd, bar, int(have.sum()))
        print(describe(pct, wkusd, f"{cohort} cohort, executed"))
        print(f"      bar {bar:.2f} | rows scored OOS {int(have.sum()):,} | picks {len(picks)} | executed {len(ex)}")

    print("\n=== 2. EXIT SEARCH on the live-cohort picks (210 configs, joined by occ+day) ===", flush=True)
    for cohort in ("ALL", "CAP1000"):
        ex, pct, wkusd, bar, _ = res[cohort]
        want = {(rows[i]["occ"], rows[i]["day"]): i for i in ex}
        fine = {}
        with open(FINE, encoding="utf-8") as f:
            for line in f:
                if '"occ"' not in line:
                    continue
                r = json.loads(line)
                key = (r.get("occ"), r.get("day"))
                if key in want:
                    fine[key] = r["rets"]
        print(f"\n  -- {cohort} cohort: {len(fine)} of {len(ex)} executed picks matched to the fine grid --")
        if len(fine) < 20:
            print("     too few matched to search"); continue
        matched = [(k, want[k]) for k in fine]
        wks = sorted({wk(rows[i]["day"]) for _, i in matched})
        cut = wks[len(wks) // 2]

        def cell(gix, subset):
            p, wu = [], defaultdict(float)
            for k, i in subset:
                v = fine[k][gix]
                if v is None:
                    continue
                r = rows[i]
                p.append(v)
                wu[wk(r["day"])] += max(1, int(1000.0 // (r["entry"] * 100))) * v / 100.0 * r["entry"] * 100.0
            return p, wu
        first = [(k, i) for k, i in matched if wk(rows[i]["day"]) < cut]
        second = [(k, i) for k, i in matched if wk(rows[i]["day"]) >= cut]
        p, wu = cell(BASE_IX, matched)
        print(describe(p, wu, f"BASE {GRID[BASE_IX]} (reference)"))
        best_in, best_ix = None, None
        for j in range(len(GRID)):
            pj, wj = cell(j, matched)
            if len(pj) < 20:
                continue
            m = sum(pj) / len(pj)
            if best_in is None or m > best_in:
                best_in, best_ix = m, j
        pj, wj = cell(best_ix, matched)
        print(describe(pj, wj, f"in-sample best {GRID[best_ix]}"))
        print("     ^ 1 of 210 configs chosen on the same rows it is scored on - a SEARCH RESULT, not evidence")
        bf, bfj = None, None
        for j in range(len(GRID)):
            pj, wj = cell(j, first)
            if len(pj) < 12:
                continue
            m = sum(pj) / len(pj)
            if bf is None or m > bf:
                bf, bfj = m, j
        if bfj is not None:
            pj, wj = cell(bfj, second)
            pb, wb = cell(BASE_IX, second)
            print(f"     WALK-FORWARD exit: chosen on the first half {GRID[bfj]} (first-half mean {bf:+.1f}%)")
            print(describe(pj, wj, "  -> second half, chosen exit"))
            print(describe(pb, wb, "  -> second half, BASE exit"))


if __name__ == "__main__":
    main()

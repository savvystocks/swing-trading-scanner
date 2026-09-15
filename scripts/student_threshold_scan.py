"""STUDENT THRESHOLD SCAN (research, READ-ONLY; owner order 2026-09-15 23:50 BST).

Answers one question with the seat's own walk-forward stream: what would picker A (and its
siblings) trade at its STRICT (k1), MIDDLE (k2) and LOOSE (k3) bar instead of the loose one it
runs today? Rebuilds the out-of-sample score stream exactly as scripts/student_export.py does
(quarterly refits, never in-sample), then applies each threshold as the LIVE seat does - score
at or above the bar, best first within a day, hard cap of k_per_week - and reports both the
threshold cohort and the executed slice (entry ask <= exec_max_ask, engine sizing).

Writes nothing: no spec, no model, no court clock. Report to stdout and a dated markdown file.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if os.path.basename(
    os.path.dirname(os.path.abspath(__file__))) == "scripts" else os.path.expanduser("~/swing-trading-scanner")
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import numpy as np
from src import student_features as sfx
import student_formula_sim as sf
from student_export import cohort_mask, executed_slice, ASOF, EXIT_IDX

os.environ["FEATURE_SET"] = "ASOF"
OUT = f"reports/research/student_thresholds_{date.today().isoformat()}.md"


def week_of(d):
    return date.fromisoformat(d).isocalendar()[:2]


def picks_at(scores, days, mask, thr, k_per_week):
    """The LIVE rule: a candidate is eligible at or above the bar; best score first within a day;
    at most k_per_week picks per ISO week. (student_export's pick_weekly recalibrates its own
    threshold from the trailing window - here the bar is fixed, which is what the seat does.)"""
    idx = [i for i in np.argsort(np.array(days)) if mask[i] and not np.isnan(scores[i]) and scores[i] >= thr]
    by_day = defaultdict(list)
    for i in idx:
        by_day[days[i]].append(i)
    out, wk = [], defaultdict(int)
    for d in sorted(by_day):
        for i in sorted(by_day[d], key=lambda j: -scores[j]):
            w = week_of(d)
            if wk[w] >= k_per_week:
                break
            wk[w] += 1
            out.append(i)
    return out


def cohort_stats(picks, rows, ei):
    if not picks:
        return {"trades": 0}
    pct, wkusd = [], defaultdict(float)
    for i in picks:
        r = rows[i]
        p = r["rets"][ei] if r["rets"][ei] is not None else 0.0
        pct.append(p)
        wkusd[week_of(r["day"])] += p          # equal-weight percent per pick, weekly sum
    w = np.array([wkusd[x] for x in sorted(wkusd)])
    t = float(w.mean() / (w.std(ddof=1) / len(w) ** 0.5)) if len(w) > 2 and w.std(ddof=1) > 0 else 0.0
    return {"trades": len(picks), "weeks": len(w), "per_trade": round(float(np.mean(pct)), 1),
            "win": round(float(np.mean(np.array(pct) > 0)), 3), "wk_t": round(t, 2),
            "pos_weeks": round(float(np.mean(w > 0)), 2)}


def main():
    spec = json.load(open("fade_book_spec.json", encoding="utf-8"))
    stu = (spec.get("probe") or {}).get("student") or {}
    probes = stu.get("probes") or {}
    rows = [json.loads(l) for l in open(ASOF, encoding="utf-8")]
    X = np.array([r["vec"] for r in rows], float)
    days = [r["day"] for r in rows]
    meta_days = np.array(days)
    only = sys.argv[1:] or [n for n, c in probes.items() if not c.get("pulled")]
    lines = [f"# Student threshold scan - {date.today().isoformat()}", "",
             "Read-only. The out-of-sample stream is rebuilt exactly as `scripts/student_export.py` builds it",
             "(quarterly walk-forward refits, never in-sample); each bar is then applied the way the LIVE seat",
             "applies it (score >= bar, best first within a day, hard cap k_per_week). The executed slice is the",
             "picks whose entry ask fits `exec_max_ask`, sized as the engine sizes them.", ""]
    for name in sorted(only):
        cfg = probes.get(name) or {}
        target = cfg.get("target", "PWIN")
        cohort = cfg.get("cohort", "AFFORD")
        thr_co = cfg.get("threshold_cohort") or cohort
        ei = EXIT_IDX.get(cfg.get("exit_label", "BASE"), 0)
        k_pw = int(cfg.get("k_per_week", 3))
        cap = float(cfg.get("exec_max_ask", stu.get("exec_max_ask", 10.0)))
        model_path = cfg.get("model")
        thr_live = {}
        if model_path and os.path.exists(model_path):
            thr_live = (json.load(open(model_path, encoding="utf-8")) or {}).get("thresholds") or {}
        if not thr_live:
            lines.append(f"## {name}: no model file ({model_path}) - skipped"); continue
        rets = np.array([r["rets"][ei] if r["rets"][ei] is not None else np.nan for r in rows])
        cm = cohort_mask(rows, cohort) & ~np.isnan(rets)
        y_cls = (rets > 0).astype(int)
        y_big = (rets >= 30).astype(int)
        y_reg = np.clip(np.nan_to_num(rets, nan=0.0), -100, 300)
        print(f"[{name}] rebuilding the walk-forward stream ({int(cm.sum())} cohort rows)...", flush=True)
        oos = sf.fit_stream(X, y_cls, y_big, y_reg, days, target, cm)
        have_t = cm & ~np.isnan(oos) & cohort_mask(rows, thr_co)
        lines += [f"## {name} (target {target}, cohort {cohort}, bar cohort {thr_co}, {k_pw}/week, cap ${cap:g})", "",
                  "| bar | score | picks | per trade | win | weekly t | positive weeks | executed | exec per trade | exec win | exec weekly t | exec $ |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k in ("k1", "k2", "k3"):
            if k not in thr_live:
                continue
            thr = float(thr_live[k])
            pk = picks_at(oos, days, have_t, thr, k_pw)
            c = cohort_stats(pk, rows, ei)
            e = executed_slice(pk, rows, ei, cap) if pk else {"trades": 0}
            tag = {"k1": "strict", "k2": "middle", "k3": "loose (LIVE)"}[k]
            lines.append(
                f"| {tag} | {thr:.2f} | {c.get('trades',0)} | {c.get('per_trade','n/a')}% | "
                f"{c.get('win','n/a')} | {c.get('wk_t','n/a')} | {c.get('pos_weeks','n/a')} | "
                f"{e.get('trades',0)} | {e.get('per_trade','n/a')}% | {e.get('win','n/a')} | "
                f"{e.get('wk_t','n/a')} | {e.get('total','n/a')} |")
        lines.append("")
        lines.append(f"Rows scored out of sample: {int((cm & ~np.isnan(oos)).sum())} of {int(cm.sum())} in the cohort; "
                     f"bar cohort rows {int(have_t.sum())}; corpus {ASOF}.")
        lines.append("")
    lines += ["## Reading this", "",
              "`per trade` is the mean percent return of a pick at the seat's exit configuration; `executed` is the",
              "subset the $1,000 slot can actually buy, in engine sizing, and `exec $` is their summed weekly dollars.",
              "A stricter bar should raise per-trade return and lower the count. If it does not, the bar is not the",
              "lever. Weekly t on a handful of weeks is not evidence of anything - read the counts first.", ""]
    os.makedirs("reports/research", exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwritten {OUT}")


if __name__ == "__main__":
    main()

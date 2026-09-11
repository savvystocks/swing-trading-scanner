"""BASIS DIFF - v1 vs v2 corpus (panel order 2026-09-09).

v1 entered at the CLOSE of the first hourly bar after the print (a trade price ~90 minutes
late), fed that same bar to the peak/trail loop (look-ahead), and filled exits at the exact
theoretical level. v2 enters at the NBBO ASK banked at the print, excludes the entry bar from
the peak loop, and haircuts every exit to the bid side.

This prints the same strategy cells on both bases, so the cost of the correction is a
published number rather than a guess. Acceptance rule from the panel: if the gap exceeds the
promotion floor (+3%/day), the v1 numbers were never a bar and every cell citing them is
superseded."""
import json
import os
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

EXITS = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
         (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]
BASE = EXITS.index((-50.0, 50.0, 0.20))
WIDE = EXITS.index((-70.0, 80.0, 0.30))

CELLS = {
    "POOL (every trigger)":  (lambda r: True, BASE),
    "FOLLOW_CALLS":          (lambda r: r["side"] == "C", BASE),
    "CONSENSUS_CALLS":       (lambda r: r["side"] == "C" and not (r["smd"] < 0 and r["sp"] < 0), BASE),
    "BULL_DIP":              (lambda r: r["reg"] > 2 and r["smd"] < 0 and r["side"] == "C", BASE),
    "DIP_CONF_MILD":         (lambda r: -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0
                                        and r["side"] == "C", BASE),
    "DIP_CONVEXITY (wide)":  (lambda r: r["reg"] < -2 and r["sp"] < 0 and r["side"] == "C", WIDE),
    "WINNER_PROFILE_X":      (lambda r: (r.get("prem") or 0) > 100000, BASE),
}


def load(path):
    rows = []
    if not os.path.exists(path):
        return rows
    for ln in open(path, encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    return rows


def daymean(rows, pred, gi):
    per = defaultdict(list)
    for r in rows:
        if not pred(r):
            continue
        v = r["rets"][gi]
        if v is not None:
            per[r["day"]].append(v)
    if not per:
        return None, 0, 0
    dm = {d: sum(v) / len(v) for d, v in per.items()}
    return sum(dm.values()) / len(dm), len(dm), sum(len(v) for v in per.values())


def main():
    v1 = load(os.environ.get("BASIS_OLD", "reports/research/probe_tuner_rows_v2.jsonl"))
    v2 = load(os.environ.get("BASIS_NEW", "reports/research/probe_tuner_rows_v3.jsonl"))
    L = [f"# CORPUS BASIS DIFF v1 -> v2 - {date.today().isoformat()}",
         "",
         f"v1 rows {len(v1)} (entry = trade-bar close ~90min post-print, look-ahead in the entry "
         f"bar, exits at the exact level)",
         f"v2 rows {len(v2)} (entry = NBBO ASK at the print, entry bar excluded from the peak "
         f"loop, exits haircut to the bid)",
         "",
         "| cell | v1 %/day | v2 %/day | DIFF | v1 days | v2 days | v1 n | v2 n |",
         "|---|---|---|---|---|---|---|---|"]
    worst = 0.0
    for name, (pred, gi) in CELLS.items():
        m1, d1, n1 = daymean(v1, pred, gi)
        m2, d2, n2 = daymean(v2, pred, gi)
        if m1 is None or m2 is None:
            L.append(f"| {name} | - | - | - | {d1} | {d2} | {n1} | {n2} |")
            continue
        diff = m2 - m1
        worst = min(worst, diff)
        L.append(f"| {name} | {m1:+.2f} | {m2:+.2f} | {diff:+.2f} | {d1} | {d2} | {n1} | {n2} |")
    L += ["", f"LARGEST DEGRADATION: {worst:+.2f} points/day.",
          "PANEL ACCEPTANCE RULE: a gap beyond the promotion floor (3.0 points/day) means the v1 "
          "numbers were never a bar - every published cell citing them is SUPERSEDED and no "
          "strategy may be promoted or seated on a v1 figure.",
          "",
          "Note the two bases also differ in population: v2 drops any contract with no executable "
          "ask banked at its print (never faked from the daily quote), and v2 was built after the "
          "bar-library top-up, so row counts are not directly comparable - the day-means are."]
    fn = f"reports/research/basis_diff_{os.environ.get('BASIS_TAG', 'v2_v3')}_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("BASIS DIFF COMPLETE", flush=True)


if __name__ == "__main__":
    main()

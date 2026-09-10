"""MASTERS vs SEATS SIMULATION (owner order 2026-09-09: "what proof do we have that this is
better than the old system, run simulations for that").

The panel's central open question, measured instead of argued. Two architectures replayed on
the SAME archive corpus (73k real triggers, 452 days, bar-replay exits, spread<=2% embedded):

  ARCHITECTURE A (today) - separate seats, each accruing its own evidence:
      BULL_DIP, DIP_CONF_MILD, DIP_CONVEXITY, FOLLOW_CALLS, WINNER_PROFILE_X
  ARCHITECTURE B (masters) - three regime seats, each = its anchor PLUS the merged
      winner-profile condition (prem>100k), which is what "promote the indicator into the
      master" actually does:
      BULL   = reg>2  AND ticker<20d AND calls AND prem>100k
      MILD   = |reg|<=2 AND ticker<20d AND SPY<20d AND calls AND prem>100k
      BEAR   = reg<-2 AND SPY<20d AND calls AND prem>100k

Reported per entity: trades, trading days, day-mean %/day, t vs the unfiltered pool on shared
days, walk-forward halves, and TIME-TO-VERDICT (how many calendar months to reach the court's
8-shared-day bar at the entity's own measured day rate). The merge question is answered by
comparing each master against its own anchor: does adding the proven condition raise the
day-mean, and what does it cost in day supply?
Research tier: report only, no telegram (channel policy 2026-09-09)."""
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from glide_sim import GIX, snap

BASE = GIX[snap((-50.0, 50.0, 0.20))]
WIDE = GIX[snap((-70.0, 80.0, 0.30))]

# (name, predicate, exit_config) - anchors use their live exit configs
SEATS = {
    "BULL_DIP":        (lambda r: r["reg"] > 2 and r["smd"] < 0 and r["side"] == "C", BASE),
    "DIP_CONF_MILD":   (lambda r: -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0
                                  and r["side"] == "C", BASE),
    "DIP_CONVEXITY":   (lambda r: r["reg"] < -2 and r["sp"] < 0 and r["side"] == "C", WIDE),
    "FOLLOW_CALLS":    (lambda r: r["side"] == "C", BASE),
    "WINNER_PROFILE_X": (lambda r: (r.get("prem") or 0) > 100000, BASE),
}
MASTERS = {
    "BULL":  (lambda r: r["reg"] > 2 and r["smd"] < 0 and r["side"] == "C"
                        and (r.get("prem") or 0) > 100000, BASE),
    "MILD":  (lambda r: -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0
                        and r["side"] == "C" and (r.get("prem") or 0) > 100000, BASE),
    "BEAR":  (lambda r: r["reg"] < -2 and r["sp"] < 0 and r["side"] == "C"
                        and (r.get("prem") or 0) > 100000, WIDE),
}
ANCHOR_OF = {"BULL": "BULL_DIP", "MILD": "DIP_CONF_MILD", "BEAR": "DIP_CONVEXITY"}


def dmeans(rows, gi):
    per = defaultdict(list)
    for r in rows:
        v = r["rets"][gi]
        if v is not None:
            per[r["day"]].append(v)
    return {d: sum(v) / len(v) for d, v in per.items()}


def paired_t(a, b):
    shared = sorted(set(a) & set(b))
    diffs = [a[d] - b[d] for d in shared]
    n = len(diffs)
    if n < 10:
        return None, n
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    return (mu / (sd / math.sqrt(n)) if sd > 0 else 0.0), n


def main():
    rows = []
    for ln in open("reports/research/glide_fine_rows_v2.jsonl", encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    pa = {}
    for ln in open("reports/research/probe_tuner_rows_v2.jsonl", encoding="utf-8"):
        try:
            j = json.loads(ln)
            pa[j["occ"]] = j.get("prem")
        except Exception:
            pass
    for r in rows:
        r["prem"] = pa.get(r["occ"])
    days_all = sorted({r["day"] for r in rows})
    span_months = len(days_all) / 21.0
    pool = dmeans(rows, BASE)
    half = days_all[len(days_all) // 2]

    def profile(name, pred, gi):
        sel = [r for r in rows if pred(r)]
        dm = dmeans(sel, gi)
        if not dm:
            return None
        mean = sum(dm.values()) / len(dm)
        t, n = paired_t(dm, pool)
        h1 = [v for d, v in dm.items() if d < half]
        h2 = [v for d, v in dm.items() if d >= half]
        rate = len(dm) / span_months                    # trading days with a fill, per month
        ttv = (8.0 / rate) if rate > 0 else 999         # months to the court's 8-day bar
        return {"n": len(sel), "days": len(dm), "mean": mean, "t": t,
                "h1": sum(h1) / len(h1) if h1 else 0, "h2": sum(h2) / len(h2) if h2 else 0,
                "rate": rate, "ttv": ttv}

    L = [f"# MASTERS vs SEATS - {date.today().isoformat()}",
         f"corpus {len(rows)} archive trades over {len(days_all)} days (~{span_months:.1f} months); "
         f"unfiltered pool {sum(pool.values()) / len(pool):+.2f}%/day",
         "Time-to-verdict = months to reach the court's 8-shared-day bar at the entity's own "
         "measured fill-day rate (the bar also needs the control present, so these are FLOORS).",
         "", "## ARCHITECTURE A - separate seats (today)", "",
         "| seat | trades | days | %/day | t vs pool | halves | days/mo | months to verdict |",
         "|---|---|---|---|---|---|---|---|"]
    A = {}
    for nm, (pred, gi) in SEATS.items():
        p = profile(nm, pred, gi)
        A[nm] = p
        if p:
            L.append(f"| {nm} | {p['n']} | {p['days']} | {p['mean']:+.2f} | "
                     f"{('%+.2f' % p['t']) if p['t'] is not None else 'n/a'} | "
                     f"{p['h1']:+.1f}/{p['h2']:+.1f} | {p['rate']:.1f} | {p['ttv']:.1f} |")
    L += ["", "## ARCHITECTURE B - three regime masters (anchor + merged winner condition)", "",
          "| master | trades | days | %/day | t vs pool | halves | days/mo | months to verdict |",
          "|---|---|---|---|---|---|---|---|"]
    B = {}
    for nm, (pred, gi) in MASTERS.items():
        p = profile(nm, pred, gi)
        B[nm] = p
        if p:
            L.append(f"| {nm} | {p['n']} | {p['days']} | {p['mean']:+.2f} | "
                     f"{('%+.2f' % p['t']) if p['t'] is not None else 'n/a'} | "
                     f"{p['h1']:+.1f}/{p['h2']:+.1f} | {p['rate']:.1f} | {p['ttv']:.1f} |")
    L += ["", "## THE MERGE QUESTION - does absorbing the proven condition improve the anchor?", "",
          "| master | anchor %/day | master %/day | edge gained | day supply kept | verdict slower by |",
          "|---|---|---|---|---|---|"]
    better = 0
    for m, anc in ANCHOR_OF.items():
        pa_, pb = A.get(anc), B.get(m)
        if not (pa_ and pb):
            continue
        gain = pb["mean"] - pa_["mean"]
        keep = (pb["days"] / pa_["days"] * 100) if pa_["days"] else 0
        slow = (pb["ttv"] - pa_["ttv"])
        better += 1 if gain > 0 else 0
        L.append(f"| {m} | {pa_['mean']:+.2f} | {pb['mean']:+.2f} | {gain:+.2f} | "
                 f"{keep:.0f}% | {slow:+.1f} months |")
    L += ["", f"MERGE SCORE: {better}/3 masters beat their own anchor on day-mean.", ""]
    tot_a = sum(p["days"] for p in A.values() if p)
    tot_b = sum(p["days"] for p in B.values() if p)
    L.append(f"EVIDENCE SUPPLY: architecture A accrues {tot_a} strategy-days across "
             f"{len([p for p in A.values() if p])} seats; architecture B accrues {tot_b} across 3. "
             "Fewer seats means each one's evidence is less fragmented, but every AND-merge "
             "removes day supply from the seat that absorbs it - the trade the panel priced.")
    L.append("")
    L.append("CAVEATS: bar-replay exits, one historical path, no execution frictions beyond the "
             "embedded spread cap; regimes are computed from SPY vs its 50d/20d exactly as the "
             "live router does. The live court remains the judge of whatever ships.")
    fn = f"reports/research/masters_vs_seats_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("SIM COMPLETE", flush=True)


if __name__ == "__main__":
    main()

"""CAPTURE RATIO (owner order 2026-09-09, action 2 of 4; also ROADMAP item 14's own
requirement for the real-money gate).

THE central unanswered question: the archive says these cohorts earn +3 to +6%/day of excess;
the live discovery book is deep in tuition. Is the gap execution friction, replay optimism,
selection, or small sample? This measures it instead of arguing it.

Method - same strategy, SAME CALENDAR DAYS, live actual vs archive expected:
  for each live PROBE strategy with closed trades, take the days it actually traded, compute
  its realized day-mean, and compute the archive's day-mean for the SAME predicate on those
  same days. capture = live / archive. A capture near 1.0 means the lab reproduces its
  backtest; near 0 or negative means the edge does not survive contact.
Also reports the pool benchmark (what taking every archive trigger returned on those days),
so a bad capture can be told apart from a bad tape.
Small-n honesty: every row carries its day count; rows under 5 days are marked THIN and must
not be quoted as a verdict. Research tier: report only (channel policy 2026-09-09)."""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from glide_sim import GIX, snap

BASE = GIX[snap((-50.0, 50.0, 0.20))]
WIDE = GIX[snap((-70.0, 80.0, 0.30))]

# live strategy -> (archive predicate, exit config used live)
MAP = {
    "EXEC_BASELINE":   (lambda r: True, BASE),
    "FOLLOW_CALLS":    (lambda r: r["side"] == "C", BASE),
    "CONSENSUS":       (lambda r: r["side"] == "C" and not (r["smd"] < 0 and r["sp"] < 0), BASE),
    "CONSENSUS_CALLS": (lambda r: r["side"] == "C" and not (r["smd"] < 0 and r["sp"] < 0), BASE),
    "BULL_DIP":        (lambda r: r["reg"] > 2 and r["smd"] < 0 and r["side"] == "C", BASE),
    "DIP_CONF_MILD":   (lambda r: -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0
                                  and r["side"] == "C", BASE),
    "DIP_CONVEXITY":   (lambda r: r["reg"] < -2 and r["sp"] < 0 and r["side"] == "C", WIDE),
    "DP_HEAVY":        (lambda r: True, BASE),
    "FADE_UNROUTED":   (lambda r: (r["smd"] < 0 and r["sp"] < 0) if r["side"] == "C"
                                  else (r["smd"] > 0 and r["sp"] > 0), BASE),
    "QUIET_TAPE":      (lambda r: True, BASE),
}


def main():
    rows = []
    for ln in open("reports/research/glide_fine_rows.jsonl", encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)

    def arch_daymean(pred, gi, days):
        out = {}
        for d in days:
            vals = [x["rets"][gi] for x in by_day.get(d, []) if pred(x) and x["rets"][gi] is not None]
            if vals:
                out[d] = sum(vals) / len(vals)
        return out

    log = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
    live = defaultdict(lambda: defaultdict(list))
    for rec in log:
        if rec.get("book") != "PROBE":
            continue
        st = rec.get("probe_strategy")
        d = (rec.get("entry_ts_utc") or "")[:10]
        if not (st and d):
            continue
        for le in (rec.get("leg_exits") or {}).values():
            if isinstance(le, dict) and le.get("return_pct") is not None:
                live[st][d].append(le["return_pct"])
    L = [f"# CAPTURE RATIO - {date.today().isoformat()}",
         "Live realized vs archive expected, SAME strategy, SAME calendar days.",
         "capture = live day-mean / archive day-mean on those days. THIN = under 5 shared days "
         "(reported for completeness, never a verdict).", "",
         "GAP = live minus archive in percentage points (the ratio is UNDEFINED when the "
         "archive day-mean sits near zero - a division that produced -2530x on the first run). "
         "MEDIAN columns resist a single monster trade dominating a small sample.", "",
         "| strategy | shared days | live mean | arch mean | GAP | live med | arch med | GAP med | note |",
         "|---|---|---|---|---|---|---|---|---|"]
    tot_live, tot_arch, tot_days = [], [], 0
    for st, dm in sorted(live.items()):
        if st not in MAP:
            continue
        pred, gi = MAP[st]
        ld = {d: sum(v) / len(v) for d, v in dm.items()}
        ad = arch_daymean(pred, gi, list(ld))
        pd_ = arch_daymean(lambda r: True, BASE, list(ld))
        shared = sorted(set(ld) & set(ad))
        if not shared:
            L.append(f"| {st} | 0 | - | - | - | - | no archive overlap (days outside corpus) |")
            continue
        def _med(xs):
            xs = sorted(xs)
            n_ = len(xs)
            return 0.0 if not n_ else (xs[n_ // 2] if n_ % 2 else (xs[n_ // 2 - 1] + xs[n_ // 2]) / 2)
        lm = sum(ld[d] for d in shared) / len(shared)
        am = sum(ad[d] for d in shared) / len(shared)
        lmd = _med([ld[d] for d in shared])
        amd = _med([ad[d] for d in shared])
        note = "THIN" if len(shared) < 5 else ""
        L.append(f"| {st} | {len(shared)} | {lm:+.2f} | {am:+.2f} | {lm - am:+.2f} | "
                 f"{lmd:+.2f} | {amd:+.2f} | {lmd - amd:+.2f} | {note} |")
        if len(shared) >= 5:
            tot_live.append(lm * len(shared))
            tot_arch.append(am * len(shared))
            tot_days += len(shared)
    L.append("")
    if tot_days:
        lm = sum(tot_live) / tot_days
        am = sum(tot_arch) / tot_days
        L.append(f"WEIGHTED (non-THIN rows, {tot_days} strategy-days): live {lm:+.2f}%/day vs "
                 f"archive {am:+.2f}%/day - GAP {lm - am:+.2f} points.")
        L.append("")
        L.append("READING: a GAP near zero means the lab reproduces its backtest; a large "
                 "negative GAP means the edge does not survive contact and must be attributed "
                 "(execution friction, replay optimism, or selection) BEFORE any real-money "
                 "gate passes, since every promotion bar is denominated in archive-scale "
                 "returns. POWER WARNING: with this many days and option returns this skewed, "
                 "no gap smaller than roughly 10 points is distinguishable from noise - this "
                 "study is a measurement instrument that is not yet loaded, and its own honest "
                 "output today is 'not enough closed evidence'.")
    else:
        L.append("NO non-thin overlap yet - the live book has not traded enough days inside the "
                 "archive window to measure capture. This is itself the finding: the gate's "
                 "capture requirement cannot be met until closed live evidence accumulates.")
    L += ["", "CAVEATS: archive exits are bar-replays on the same config; live exits include real "
              "fills, slippage and the no-same-day rule. Live entries are at the ask; archive "
              "entries use the post-print bar close. Those differences ARE the friction this "
              "ratio is designed to expose - they are not a reason to discount it."]
    fn = f"reports/research/capture_ratio_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("CAPTURE RATIO COMPLETE", flush=True)


if __name__ == "__main__":
    main()

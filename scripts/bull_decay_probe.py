"""BULL_DIP DECAY INVESTIGATION (owner order 2026-09-09, after the masters-vs-seats sim showed
BULL_DIP halves +17.9 then -4.6).

The question that matters: is the bull-dip edge DECAYING, or did the whole market's option
tape decay and BULL_DIP merely rode it? Method: quarter-by-quarter day-means for BULL_DIP,
its cousins, and the unfiltered pool on the same days, plus each quarter's EXCESS over the
pool (the only number that isolates strategy from tape). Also splits BULL_DIP by episode so a
single fat quarter cannot masquerade as an edge.
Research tier: report only (channel policy 2026-09-09)."""
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

ENTITIES = {
    "BULL_DIP":      (lambda r: r["reg"] > 2 and r["smd"] < 0 and r["side"] == "C", BASE),
    "BULL_ALLCALLS": (lambda r: r["reg"] > 2 and r["side"] == "C", BASE),
    "FOLLOW_CALLS":  (lambda r: r["side"] == "C", BASE),
    "MILD":          (lambda r: -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0
                                and r["side"] == "C", BASE),
    "BEAR":          (lambda r: r["reg"] < -2 and r["sp"] < 0 and r["side"] == "C", WIDE),
}


def dmeans(rows, gi):
    per = defaultdict(list)
    for r in rows:
        v = r["rets"][gi]
        if v is not None:
            per[r["day"]].append(v)
    return {d: sum(v) / len(v) for d, v in per.items()}


def q(d):
    y, m = int(d[:4]), int(d[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def main():
    rows = []
    for ln in open("reports/research/glide_fine_rows.jsonl", encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    pool = dmeans(rows, BASE)
    L = [f"# BULL_DIP DECAY - {date.today().isoformat()}",
         f"corpus {len(rows)} archive trades; POOL = every trigger (the tape itself).",
         "EXCESS = the entity's day-mean minus the pool's on the SAME days - the only column "
         "that separates strategy skill from market weather.", ""]
    for name, (pred, gi) in ENTITIES.items():
        sel = [r for r in rows if pred(r)]
        dm = dmeans(sel, gi)
        byq = defaultdict(list)
        exq = defaultdict(list)
        for d, v in dm.items():
            byq[q(d)].append(v)
            if d in pool:
                exq[q(d)].append(v - pool[d])
        L += [f"## {name} ({len(sel)} trades, {len(dm)} days)", "",
              "| quarter | days | %/day | pool %/day | EXCESS |", "|---|---|---|---|---|"]
        for qq in sorted(byq):
            pv = [pool[d] for d in dm if q(d) == qq and d in pool]
            ex = exq.get(qq) or [0]
            L.append(f"| {qq} | {len(byq[qq])} | {sum(byq[qq]) / len(byq[qq]):+.2f} | "
                     f"{(sum(pv) / len(pv)) if pv else 0:+.2f} | {sum(ex) / len(ex):+.2f} |")
        allex = [x for v in exq.values() for x in v]
        if len(allex) > 2:
            mu = sum(allex) / len(allex)
            sd = (sum((x - mu) ** 2 for x in allex) / (len(allex) - 1)) ** 0.5
            t = mu / (sd / math.sqrt(len(allex))) if sd > 0 else 0
            pos = sum(1 for qq in sorted(exq) if sum(exq[qq]) / len(exq[qq]) > 0)
            L += ["", f"lifetime EXCESS {mu:+.2f}%/day (t{t:+.2f}, {len(allex)}d); "
                      f"quarters with positive excess: {pos}/{len(exq)}", ""]
    fn = f"reports/research/bull_decay_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("DECAY PROBE COMPLETE", flush=True)


if __name__ == "__main__":
    main()

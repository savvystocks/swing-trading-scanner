"""BULL VARIANT HEAD-TO-HEAD (owner order 2026-09-09, action 4 of 4: "test bull-regime calls
without the dip filter").

The decay probe suggested BULL_DIP's defining filter SUBTRACTS value. "One number looks
bigger" is not proof, so this pairs the variants DAY BY DAY on their shared days and tests
the difference directly - the same paired-t the live court uses. Variants:
  BULL_DIP     reg>2, ticker<20d, calls        (the live seat today)
  BULL_CALLS   reg>2, calls                    (drop the dip filter)
  BULL_MOMO    reg>2, ticker>20d, calls        (the inverse: buy strength, not dips)
  BULL_CONF    reg>2, ticker<20d, SPY<20d, calls (dip WITH market confirmation - the MILD recipe)
Reported: each variant vs pool, and every pairwise difference vs BULL_DIP with a paired t.
A filter earns its place only if removing it makes things WORSE.
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
V = {
    "BULL_DIP":   lambda r: r["reg"] > 2 and r["smd"] < 0 and r["side"] == "C",
    "BULL_CALLS": lambda r: r["reg"] > 2 and r["side"] == "C",
    "BULL_MOMO":  lambda r: r["reg"] > 2 and r["smd"] > 0 and r["side"] == "C",
    "BULL_CONF":  lambda r: r["reg"] > 2 and r["smd"] < 0 and r["sp"] < 0 and r["side"] == "C",
}


def dmeans(rows):
    per = defaultdict(list)
    for r in rows:
        v = r["rets"][BASE]
        if v is not None:
            per[r["day"]].append(v)
    return {d: sum(v) / len(v) for d, v in per.items()}


def paired(a, b):
    shared = sorted(set(a) & set(b))
    diffs = [a[d] - b[d] for d in shared]
    n = len(diffs)
    if n < 10:
        return None, None, n
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    return mu, (mu / (sd / math.sqrt(n)) if sd > 0 else 0.0), n


def main():
    rows = []
    for ln in open("reports/research/glide_fine_rows.jsonl", encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    pool = dmeans(rows)
    dm = {k: dmeans([r for r in rows if p(r)]) for k, p in V.items()}
    nn = {k: len([r for r in rows if p(r)]) for k, p in V.items()}
    L = [f"# BULL VARIANT HEAD-TO-HEAD - {date.today().isoformat()}",
         f"corpus {len(rows)} archive trades; exit -50/+50/0.20; paired on shared days.", "",
         "| variant | trades | days | %/day | excess vs pool | t vs pool |",
         "|---|---|---|---|---|---|"]
    for k in V:
        d = dm[k]
        if not d:
            continue
        mu, t, n = paired(d, pool)
        L.append(f"| {k} | {nn[k]} | {len(d)} | {sum(d.values()) / len(d):+.2f} | "
                 f"{('%+.2f' % mu) if mu is not None else 'n/a'} | "
                 f"{('%+.2f' % t) if t is not None else 'n/a'} |")
    L += ["", "## Does the dip filter earn its place? (each variant MINUS BULL_DIP, paired)", "",
          "| variant vs BULL_DIP | shared days | mean diff | t | reading |", "|---|---|---|---|---|"]
    for k in V:
        if k == "BULL_DIP":
            continue
        mu, t, n = paired(dm[k], dm["BULL_DIP"])
        if mu is None:
            L.append(f"| {k} | {n} | - | - | too few shared days |")
            continue
        read = ("BEATS the live seat" if (t or 0) > 1.8 else
                "loses to the live seat" if (t or 0) < -1.8 else "indistinguishable")
        L.append(f"| {k} | {n} | {mu:+.2f} | {t:+.2f} | {read} |")
    L += ["", "DECISION RULE (pre-registered here, before reading): drop the dip filter only if "
              "BULL_CALLS beats BULL_DIP at t>=+1.8 paired. Anything less is 'indistinguishable' "
              "and the live seat stays as it is - a filter is not removed on a hunch, and an "
              "indistinguishable variant is not an improvement, it is a coin flip with extra steps.",
          "", "CAVEATS: bar-replay exits, one historical path, bull regimes only (~46% of days). "
              "BULL_DIP has ZERO live closed evidence, so nothing live is contradicted either way."]
    fn = f"reports/research/bull_variant_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("VARIANT TEST COMPLETE", flush=True)


if __name__ == "__main__":
    main()

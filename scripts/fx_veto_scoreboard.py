"""S26 shadow veto scoreboard (NORTH_STAR v1.10, the veto's scoreboard). Joins every S26 signal's model outcome (R from
reports/fx_alerts/s26_state.json: executable bid/ask prices, stop slippage, financing not included; a signal the rule
itself skipped counts as 0 R) to its shadow verdict and prints the raw and vetoed ledgers per mechanical signal, with
the chance that random vetoes of the same number do at least as well. A missing, late or failed verdict counts as
approved (fail open). Shadow on an unvalidated rule: not counted toward the 60 live signals, and no keep-or-stop
verdict is ever printed."""
import glob
import json
import os
import random
import sys
from itertools import combinations
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABEL = "S26 shadow - not counted toward the 60"


def load(state_path, veto_dir):
    with open(state_path) as f:
        trades = json.load(f)["trades"]
    verdicts = {}
    for p in glob.glob(os.path.join(veto_dir, "*.verdict.json")):
        with open(p) as f:
            verdicts[os.path.basename(p)[:-len(".verdict.json")]] = json.load(f)
    return trades, verdicts


def join(trades, verdicts):
    rows, pend = [], 0
    for tr in trades:
        if tr["status"] in ("pending", "open"):
            pend += 1
            continue
        v = verdicts.get(tr["id"]) or {}
        dec = v.get("decision") if v.get("decision") in ("approve", "veto") and v.get("before_order_time") else "no_verdict"
        rows.append({"id": tr["id"], "pair": tr["pair"], "dir": tr["dir"], "kind": tr.get("kind", ""),
                     "R": float(tr["R"]) if tr["status"] == "closed" else 0.0, "decision": dec,
                     "confidence": v.get("confidence") if dec != "no_verdict" else None})
    return rows, pend


def random_veto_p(rs, k, removed, draws=20_000, seed=26):
    n = len(rs)
    if k == 0 or k >= n:
        return None
    if comb(n, k) <= draws:
        sums = [sum(c) for c in combinations(rs, k)]
    else:
        rng = random.Random(seed)
        sums = [sum(rng.sample(rs, k)) for _ in range(draws)]
    return sum(1 for s in sums if s <= removed + 1e-9) / len(sums)


def summary(rows):
    n = len(rows)
    rs = [r["R"] for r in rows]
    raw = sum(rs)
    removed = sum(r["R"] for r in rows if r["decision"] == "veto")
    k = sum(1 for r in rows if r["decision"] == "veto")
    count = {d: sum(1 for r in rows if r["decision"] == d) for d in ("approve", "veto", "no_verdict")}
    return {"signals": n, "vetoes": k, "approve": count["approve"], "no_verdict": count["no_verdict"],
            "raw_total_R": raw, "raw_R_per_signal": raw / n if n else None,
            "vetoed_total_R": raw - removed, "vetoed_R_per_signal": (raw - removed) / n if n else None,
            "vetoed_signals_R": removed, "random_veto_p": random_veto_p(rs, k, removed)}


def report(rows, pend):
    m = summary(rows)
    out = [LABEL, f"graded signals: {m['signals']} (still pending or open: {pend})",
           f"verdicts: approve {m['approve']}, veto {m['vetoes']}, no verdict {m['no_verdict']} (no verdict counts as approved)"]
    if m["signals"]:
        out += [f"raw ledger: {m['signals']} signals, total {m['raw_total_R']:+.2f} R, {m['raw_R_per_signal']:+.3f} R per signal",
                f"vetoed ledger: {m['signals'] - m['vetoes']} traded, total {m['vetoed_total_R']:+.2f} R, "
                f"{m['vetoed_R_per_signal']:+.3f} R per mechanical signal",
                f"vetoed signals: {m['vetoes']}, total {m['vetoed_signals_R']:+.2f} R"]
        if m["random_veto_p"] is not None:
            out.append(f"random vetoes of the same number doing at least as well: {m['random_veto_p']:.3f}")
    out.append("verdict: none (shadow on an unvalidated rule; no verdict before 60 live signals of a validated rule)")
    for r in rows:
        c = "" if r["confidence"] is None else f" ({r['confidence']:.2f})"
        out.append(f"  {r['id']:<22} {'long' if r['dir'] == 1 else 'short':<5} {r['kind']:<10} {r['R']:+6.2f} R  "
                   f"{r['decision']}{c}")
    return "\n".join(out)


if __name__ == "__main__":
    state = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "reports", "fx_alerts", "s26_state.json")
    veto = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "reports", "fx_alerts", "veto")
    print(report(*join(*load(state, veto))))

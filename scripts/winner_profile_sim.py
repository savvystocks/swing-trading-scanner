"""WINNER PROFILE SIMULATION (owner order 2026-09-09: "do simulations to find the best
variables for this winning profile and then backtest it").

Cross-corpus exam: the profile was built on 25,597 harvest-labeled trades; this replays it
on the INDEPENDENT 73k-trigger archive corpus (2 years, different source, different labels -
bar-replay exits). Grid: flow-premium floor x front-IV ceiling. The corpus already embeds
the tight-spread leg (rows required spread<=2% at the day quote). Scoring: day-mean %/day
under the baseline exit (-50/+50/0.20), day-clustered t vs the UNFILTERED pool on shared
days (does the profile SELECT better days/trades than taking everything?), walk-forward
halves. Multiple testing: every cell reported, trial count stated. The live probe keeps its
frozen values unless the owner orders a retune from this evidence.
Research-tier: report only, no telegram (channel policy 2026-09-09)."""
import json
import math
import os
import sqlite3
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import sys
sys.path.insert(0, os.path.join(REPO, "scripts"))
from glide_sim import GRID, GIX, snap

BASE_EXIT = GIX[snap((-50.0, 50.0, 0.20))]
PREM_GRID = [50000, 73200, 100000, 150000, 250000]
IV_GRID = [40.0, 47.7, 55.0, None]


def dmeans(rows):
    per = defaultdict(list)
    for r in rows:
        v = r["rets"][BASE_EXIT]
        if v is not None:
            per[r["day"]].append(v)
    return {d: sum(v) / len(v) for d, v in per.items()}


def paired_t(a, b):
    shared = sorted(set(a) & set(b))
    diffs = [a[d] - b[d] for d in shared]
    n = len(diffs)
    if n < 15:
        return None, None, n
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    return mu, (mu / (sd / math.sqrt(n)) if sd > 0 else 0.0), n


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
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    con.execute("create temp table need(occ text, day text)")   # bounded join (OOM lesson
    con.executemany("insert into need values (?,?)",            # 2026-08-26): fetch ONLY the
                    [(r["occ"], r["day"]) for r in rows])       # corpus keys, never the 11.7M
    iv = {}
    for occ, day, v in con.execute(
            "select c.option_symbol, c.day, c.implied_volatility from contracts_daily c "
            "join need n on n.occ = c.option_symbol and n.day = c.day "
            "where c.implied_volatility is not null"):
        iv[(occ, day)] = v
    print(f"corpus {len(rows)} rows, iv keys {len(iv)}", flush=True)
    enriched = []
    for r in rows:
        p = pa.get(r["occ"])
        v = iv.get((r["occ"], r["day"]))
        if p is None:
            continue
        r["prem"] = p
        r["iv"] = (v * 100 if isinstance(v, (int, float)) and v < 5 else v)
        enriched.append(r)
    pool_dm = dmeans(enriched)
    pool_days = sorted(pool_dm)
    half = pool_days[len(pool_days) // 2]
    L = [f"# WINNER PROFILE SIMULATION - {date.today().isoformat()}",
         f"corpus {len(enriched)} archive trades, {len(pool_days)} days; baseline exit -50/+50/0.20; "
         f"spread<=2% embedded; {len(PREM_GRID) * len(IV_GRID)} cells (all reported - multiple-testing counted)",
         f"UNFILTERED POOL: {sum(pool_dm.values()) / len(pool_dm):+.2f}%/day",
         "", "| prem floor | iv ceil | n | days | %/day | vs pool t | 1st half | 2nd half |",
         "|---|---|---|---|---|---|---|---|"]
    best = None
    for pf in PREM_GRID:
        for ivc in IV_GRID:
            sel = [r for r in enriched if r["prem"] and r["prem"] > pf
                   and (ivc is None or (isinstance(r["iv"], (int, float)) and r["iv"] < ivc))]
            dm = dmeans(sel)
            if len(dm) < 30:
                continue
            mean = sum(dm.values()) / len(dm)
            mu, t, n = paired_t(dm, pool_dm)
            h1 = [v for d, v in dm.items() if d < half]
            h2 = [v for d, v in dm.items() if d >= half]
            m1 = sum(h1) / len(h1) if h1 else 0
            m2 = sum(h2) / len(h2) if h2 else 0
            tag = " <= FROZEN LIVE CELL" if (pf == 73200 and ivc == 47.7) else ""
            L.append(f"| {pf / 1000:.0f}k | {ivc if ivc else 'none'} | {len(sel)} | {len(dm)} | "
                     f"{mean:+.2f} | {('%+.2f' % t) if t is not None else 'n/a'} | {m1:+.2f} | {m2:+.2f} |{tag}")
            if t is not None and m1 > 0 and m2 > 0:
                score = mu if mu is not None else -99
                if best is None or score > best[0]:
                    best = (score, pf, ivc, mean, t, m1, m2)
    L.append("")
    if best:
        _, pf, ivc, mean, t, m1, m2 = best
        L.append(f"BEST ROBUST CELL (both halves positive, ranked by edge vs pool): prem>{pf / 1000:.0f}k, "
                 f"iv<{ivc if ivc else 'uncapped'} -> {mean:+.2f}%/day, vs-pool t{t:+.2f}, halves {m1:+.2f}/{m2:+.2f}")
    else:
        L.append("NO cell beats the pool robustly - selection adds nothing on the archive; keep the frozen cell as a pure control")
    L.append("Live probe stays FROZEN at 73.2k/47.7 unless the owner orders a retune from this table (20 trials counted).")
    fn = f"reports/research/winner_profile_sim_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("SIM COMPLETE", flush=True)


if __name__ == "__main__":
    main()

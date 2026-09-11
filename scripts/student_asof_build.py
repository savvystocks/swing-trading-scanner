"""AS-OF FEATURE BUILD for the student (2026-09-11). For every corpus v3 row, the 15-float
vector from src/student_features.vector built ONLY from what existed at the qualifying print:
the per-print stream up to that print, and the PRIOR day's contract fields (OI, IV, delta,
gamma). End-of-day totals never enter. Output: reports/research/student_asof_v3.jsonl
(untracked) with occ, day, side, reg, vec, rets."""
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
from src import student_features as sfx

SRC = "reports/research/probe_tuner_rows_v3.jsonl"
OUT = "reports/research/student_asof_v3.jsonl"


def main():
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
    keys = {(r["occ"], r["day"]) for r in rows}
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=120)
    con.execute("create temp table need(occ text, day text)")
    con.executemany("insert into need values (?,?)", list(keys))
    print(f"rows {len(rows)}; streaming prints ...", flush=True)
    prints = defaultdict(list)
    for occ, day, ts, px, size, prem, bid, ask, sh in con.execute(
            """select f.occ, f.day, f.executed_at, f.price, f.size, f.premium, f.nbbo_bid, f.nbbo_ask, f.side_hint
               from flow_prints f join need n on n.occ = f.occ and n.day = f.day
               order by f.occ, f.day, f.executed_at"""):
        prints[(occ, day)].append((ts, px, size, prem, bid, ask, sh))
    print(f"prints for {len(prints)} contract-days; prior-day fields ...", flush=True)
    # prior-day contract fields: point lookups on the primary key, the most recent row in the
    # 6 calendar days before D (the unindexed range join took >15 min and was killed)
    tick = {(r["occ"], r["day"]): r["t"] for r in rows}
    prev = {}
    q = "select open_interest, implied_volatility, delta, gamma from contracts_daily where day=? and ticker=? and option_symbol=?"
    for (occ, d) in keys:
        dd = date.fromisoformat(d)
        for back in range(1, 7):
            hit = con.execute(q, ((dd - timedelta(days=back)).isoformat(), tick[(occ, d)], occ)).fetchone()
            if hit:
                prev[(occ, d)] = hit
                break
    print(f"prior-day fields for {len(prev)} contract-days; writing ...", flush=True)
    n_ok = n_noq = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for r in rows:
            k = (r["occ"], r["day"])
            asof = sfx.asof_from_prints(prints.get(k, []))
            if asof is None:
                n_noq += 1
                continue
            oi, iv, de, ga = prev.get(k, (None, None, None, None))
            vec = sfx.vector(r["side"], r["occ"], r["day"], r["reg"], r["sp"], r["smd"], asof, oi, iv)
            out.write(json.dumps({"occ": r["occ"], "day": r["day"], "side": r["side"], "reg": r["reg"],
                                  "sp": r["sp"], "smd": r["smd"], "entry": r["entry"], "vec": vec,
                                  "rets": r["rets"]}) + "\n")
            n_ok += 1
    print(f"AS-OF BUILD COMPLETE: {n_ok} rows written, {n_noq} without a qualifying print", flush=True)


if __name__ == "__main__":
    main()

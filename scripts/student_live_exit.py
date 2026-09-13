"""STUDENT LIVE EXIT SEARCH (owner order 2026-09-13 22:45: "run the exit search on A's live
picks when it has fills").

Pre-registered before any fill exists:
  - runs weekly (Saturday 09:00 UTC cron) and does NOTHING until the picker has >= MIN_FILLS (20)
    CLOSED live records (book PROBE, probe_strategy = the picker; VOID and PENDING never count);
  - for each such record the live exit family (glide_sim.GRID: 210 stop x trigger x give-back
    configs) is replayed on the contract's HOURLY bars from the entry cycle onward
    (data/hourly_paths.db; a contract the library lacks is fetched once, in memory only), on the
    v3 basis: same-day bars after the entry timestamp with the entry bar dropped, entry = the
    record's entry_premium (the live ask the order was priced on), trail exits close-confirmed,
    gap-through stops, bid-side haircut from the record's live spread;
  - reported: BASE (-50/+50/0.20, the live rule), the eight tuner anchors, the grid's best on all
    picks (in-sample ceiling - 210 trials on the answer, never evidence), and a LEAVE-ONE-OUT
    best: each pick scored under the config that was best on the OTHER picks (the honest,
    implementable number). The replayed BASE is compared with the book's realized returns as a
    sanity check on the replay itself.
Research tier: report only, no telegram (channel policy: research verdicts go to reports and
briefs). Writes reports/research/student_live_exit_<date>.md. STUDENT_NAME / MIN_FILLS env.
"""
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

NAME = os.environ.get("STUDENT_NAME", "STUDENT_A")
MIN_FILLS = int(os.environ.get("MIN_FILLS", "20"))
BASE = (-50.0, 50.0, 0.20)
LIB = "data/hourly_paths.db"


def replay(today_after, nxt, e, stop, trig, give, sfr):
    """The tuner's replay_true, v3 branch (close-confirmed trail, gap-through stop, bid haircut)."""
    def _sell(rp):
        return ((1 + rp / 100.0) * (1 - sfr) - 1) * 100.0
    peak, on = -999.0, False
    for (h, l, c) in today_after:
        rh = (h / e - 1) * 100
        if rh >= trig:
            on = True
        peak = max(peak, rh)
    for (h, l, c) in nxt:
        rh = (h / e - 1) * 100; rl = (l / e - 1) * 100
        if rh >= trig:
            on = True
        if on:
            peak = max(peak, rh)
            fl = peak * (1 - give)
            if rl <= fl:
                rc = (c / e - 1) * 100
                return _sell(min(fl, rc))
        if rl <= stop:
            return _sell(min(stop, rl) if rl < stop else stop)
    return _sell((nxt[-1][2] / e - 1) * 100) if nxt else None


def bars_for(occ, day, lib):
    rows = lib.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,)).fetchall()
    if rows:
        return rows
    try:                                                  # the library lacks it: one fetch, in memory
        import hourly_library as hl
        end = (date.fromisoformat(day) + timedelta(days=70)).isoformat()
        got = hl.fetch_batch([occ], day, end).get(occ) or []
        return [(t, h, l, c) for (t, o, h, l, c) in sorted(got)]
    except Exception:
        return []


def main():
    from glide_sim import GRID, ANCHORS
    book = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
    recs = [r for r in book if r.get("book") == "PROBE" and r.get("probe_strategy") == NAME
            and r.get("status") == "CLOSED" and isinstance(r.get("legs"), dict)]
    if len(recs) < MIN_FILLS:
        print(f"{NAME} live exit search: {len(recs)} closed fill(s) / {MIN_FILLS} needed - waiting", flush=True)
        return
    lib = sqlite3.connect(f"file:{LIB}?mode=ro", uri=True, timeout=60)
    picks = []
    for r in recs:
        for ln, leg in r["legs"].items():
            occ, e = leg.get("occ_symbol"), leg.get("entry_premium")
            if not occ or not e or e <= 0:
                continue
            ts = str(r.get("entry_ts_utc") or "")
            day = ts[:10]
            sp = ((leg.get("execution_cost") or {}).get("bid_ask_spread_pct"))
            sfr = max(0.0, min(0.05, float(sp) / 100.0)) if isinstance(sp, (int, float)) else 0.02
            rows_ = bars_for(occ, day, lib)
            today_after = [(h, l, c) for t, h, l, c in rows_ if t[:10] == day and t[11:19] > ts[11:19]][1:]
            nxt = [(h, l, c) for t, h, l, c in rows_ if t[:10] > day]
            if len(nxt) < 1:
                continue
            realized = ((r.get("leg_exits") or {}).get(ln) or {}).get("return_pct")
            lots = int(leg.get("contracts") or 1)
            picks.append({"day": day, "occ": occ, "e": float(e), "lots": lots, "sf": sfr, "ta": today_after, "nx": nxt,
                          "realized": realized, "regime": r.get("regime")})
    if len(picks) < MIN_FILLS:
        print(f"{NAME} live exit search: only {len(picks)} of {len(recs)} closed fills have a bar path - waiting", flush=True)
        return
    n = len(picks)
    res = {}                                              # cfg -> list of (pct, usd) per pick
    for cfg in GRID:
        out = []
        for p in picks:
            rp = replay(p["ta"], p["nx"], p["e"], cfg[0], cfg[1], cfg[2], p["sf"])
            rp = 0.0 if rp is None else rp
            out.append((rp, p["lots"] * p["e"] * 100.0 * rp / 100.0))
        res[cfg] = out

    def summ(cfg):
        v = res[cfg]; pct = [x[0] for x in v]; usd = sum(x[1] for x in v)
        return (sum(pct) / n, sorted(pct)[n // 2], sum(1 for x in pct if x > 0) / n, usd)
    best = max(GRID, key=lambda c: sum(x[1] for x in res[c]))
    loo = []                                              # leave-one-out: honest implementable number
    for i in range(n):
        c_i = max(GRID, key=lambda c: sum(x[1] for j, x in enumerate(res[c]) if j != i))
        loo.append(res[c_i][i])
    loo_mean = sum(x[0] for x in loo) / n; loo_usd = sum(x[1] for x in loo)
    base_pct = [x[0] for x in res[BASE]]
    real = [(p["realized"], bp) for p, bp in zip(picks, base_pct) if isinstance(p["realized"], (int, float))]
    mad = (sum(abs(a - b) for a, b in real) / len(real)) if real else float("nan")
    L = [f"# {NAME} LIVE EXIT SEARCH - {date.today().isoformat()}", "",
         f"{n} closed live fills replayed on hourly bars (v3 basis, entry = the live ask the order was priced on, "
         f"bid haircut from each record's live spread). 210 exit configs (stop x trail trigger x give-back).", "",
         "| config | %/trade mean | median | win | total $ at live lots |", "|---|---|---|---|---|"]
    for label, cfg in [("BASE (live rule)", BASE)] + [(f"anchor {c}", c) for c in ANCHORS if c != BASE]:
        m, md, w, usd = summ(cfg)
        L.append(f"| {label} {cfg} | {m:+.1f} | {md:+.1f} | {w:.0%} | {usd:+.0f} |")
    m, md, w, usd = summ(best)
    L.append(f"| BEST IN-SAMPLE {best} (ceiling, 210 trials) | {m:+.1f} | {md:+.1f} | {w:.0%} | {usd:+.0f} |")
    L.append(f"| LEAVE-ONE-OUT best (honest) | {loo_mean:+.1f} | - | {sum(1 for x in loo if x[0] > 0) / n:.0%} | {loo_usd:+.0f} |")
    L += ["", f"sanity: replayed BASE vs the book's realized return, mean absolute gap {mad:.1f} points over {len(real)} fills "
              f"(large gaps mean the live fills differ from the replay's model - market sells, partial fills, stale bars).",
          "", "Verdict rule (pre-registered): the exit changes only if the LEAVE-ONE-OUT best beats BASE by more than the sanity "
              "gap AND the in-sample best is not a lone corner of the grid; even then it goes to the tuner's anchor set, not straight live."]
    out = f"reports/research/student_live_exit_{date.today().isoformat()}.md"
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print(f"written {out}", flush=True)


if __name__ == "__main__":
    main()

"""FADE v1.3 pre-registered verification (written 2026-08-05, BEFORE the virgin days existed).

Candidates (from fade_six_hole_mining_2026-08-05.md): depth<2% entry filter, maxhold 3d,
optional stop -40. Virgin window = trading days AFTER 2026-08-05 (the mining's registration
date). With ~3 virgin days by Sunday this is a SMOKE TEST, not proof - bars are pre-registered
accordingly:
  APPLY v1.3 iff on virgin days: (a) baseline day-mean > -5% (no collapse), AND
  (b) depth<2% cohort day-mean >= baseline day-mean - 2pts (no sign-flip vs baseline), AND
  (c) >= 20 virgin-cohort trades exist. Else HOLD and report.
Usage: python scripts/fade_v13_check.py <path-to-newest-harvest.db>
"""
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import date

REG_DAY = (date(2026, 8, 5) - date(1970, 1, 1)).days   # virgin = day > REG_DAY


def cohort(con, virgin_only=True):
    rows = con.execute(
        """select c.candidate_id, c.entry_ref, c.right, c.features, c.spread_pct, c.rule_score,
                  cast(c.signal_ts_utc/86400000 as int)
           from candidates c join labels l on l.candidate_id=c.candidate_id
           where l.outcome is not null and c.entry_ref>0 and c.features!=''""").fetchall()
    meta = {}
    for cid, eref, right, fj, spr, score, day in rows:
        if virgin_only and day <= REG_DAY:
            continue
        try:
            f = json.loads(fj)
        except Exception:
            continue
        sma = (f.get("macro") or {}).get("distance_to_sma20_pct")
        spy = (f.get("regime_stack") or {}).get("market_spy_dist_pct")
        side = 1 if right == "call" else -1
        if not isinstance(sma, (int, float)) or not isinstance(spy, (int, float)):
            continue
        if not (sma * side < 0 and spy * side < 0):
            continue
        if (spr or 99) > 2.0 or not score or not (50000 <= score <= 250000):
            continue
        meta[cid] = {"e": eref, "day": day, "depth": abs(sma), "right": right}
    return meta


def replay(pts, e, stop=-50, maxhold_d=None):
    t0 = pts[0][0]
    peak, on = -999.0, False
    for ts, b in pts:
        r = (b / e - 1) * 100
        if maxhold_d is not None and (ts - t0) / 86400000.0 > maxhold_d:
            return r
        if r >= 50:
            on = True
        if on:
            peak = max(peak, r)
            if r <= peak * 0.8:
                return r
        if stop is not None and r <= stop:
            return stop
    return (pts[-1][1] / e - 1) * 100


def day_mean(res, meta):
    days = defaultdict(list)
    for cid, r in res.items():
        days[meta[cid]["day"]].append(r)
    dm = [sum(v) / len(v) for v in days.values()]
    return (sum(dm) / len(dm) if dm else None), len(days)


def main(db):
    con = sqlite3.connect(db)
    meta = cohort(con)
    paths = defaultdict(list)
    for cid, ts, bid in con.execute(
            "select candidate_id, poll_ts_utc, bid from bid_path "
            "where bid is not null and stale is not 1"):
        if cid in meta:
            paths[cid].append((ts, bid))
    P = [c for c in meta if len(paths[c]) >= 3]
    for c in P:
        paths[c].sort()
    if len(P) < 20:
        print(f"VERDICT: HOLD - only {len(P)} virgin-cohort trades (< 20 floor); re-check next Sunday")
        return 1
    base = {c: replay(paths[c], meta[c]["e"]) for c in P}
    b_mu, b_days = day_mean(base, meta)
    Pd = [c for c in P if meta[c]["depth"] < 2.0]
    v13 = {c: replay(paths[c], meta[c]["e"], stop=-40, maxhold_d=3) for c in Pd}
    v_mu, v_days = day_mean(v13, meta)
    print(f"virgin window: {len(P)} trades / {b_days} days | baseline day-mean {b_mu:+.2f}%")
    print(f"v1.3 cohort (depth<2, stop-40, hold3d): {len(Pd)} trades | day-mean "
          f"{v_mu:+.2f}%" if v_mu is not None else "v1.3 cohort empty")
    ok = (b_mu is not None and b_mu > -5.0 and v_mu is not None and v_mu >= b_mu - 2.0)
    print(f"VERDICT: {'APPLY v1.3' if ok else 'HOLD - smoke test failed'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

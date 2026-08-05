"""FADE BOOK health instrument - the day-clustered t-statistic life bar.

Replays the locked fade spec (fade_book_spec.json: fade shape, spread<=2%, flow $50-250k,
no scale-out, trail 50/20, stop -50) over the snapshot's stored bid paths at executable prices,
and reports the numbers the Governor's ladder promotes/kills on: pooled mean, day-clustered
mean and t, split-half means, and the live-fill slice (book=FADE records) once fills exist.
Brain-side, read-only, fail-open: any error returns a NO-DATA block, never raises.
"""
import json
import math
import sqlite3
from collections import defaultdict


def _fade_cohort(con):
    rows = con.execute(
        """select c.candidate_id, c.entry_ref, c.right, c.features, c.spread_pct, c.rule_score,
                  cast(c.signal_ts_utc/86400000 as int)
           from candidates c join labels l on l.candidate_id=c.candidate_id
           where l.outcome is not null and c.entry_ref>0 and c.features!=''""").fetchall()
    meta = {}
    for cid, eref, right, fj, spr, score, day in rows:
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
        meta[cid] = {"e": eref, "day": day}
    return meta


def _replay(rets, trig=50, give=0.20, stop=-50):
    peak, on = -999.0, False
    for r in rets:
        if r >= trig:
            on = True
        if on:
            peak = max(peak, r)
            if r <= peak * (1 - give):
                return r
        if r <= stop:
            return stop
    return rets[-1]


def health(db_path):
    try:
        con = sqlite3.connect(db_path)
        meta = _fade_cohort(con)
        paths = defaultdict(list)
        for cid, ts, bid in con.execute(
                "select candidate_id, poll_ts_utc, bid from bid_path "
                "where bid is not null and stale is not 1"):
            if cid in meta:
                paths[cid].append((ts, bid))
        res = {}
        for cid, pts in paths.items():
            if len(pts) < 3:
                continue
            pts.sort()
            e = meta[cid]["e"]
            res[cid] = _replay([(b / e - 1) * 100 for _, b in pts])
        if len(res) < 30:
            return {"status": "UNDERPOWERED", "n": len(res)}
        days = defaultdict(list)
        for cid, r in res.items():
            days[meta[cid]["day"]].append(r)
        dm = sorted((d, sum(v) / len(v)) for d, v in days.items())
        means = [m for _, m in dm]
        mu = sum(means) / len(means)
        sd = math.sqrt(sum((x - mu) ** 2 for x in means) / max(len(means) - 1, 1))
        t = mu / (sd / math.sqrt(len(means))) if sd else 0.0
        pooled = sum(res.values()) / len(res)
        mid = len(dm) // 2
        early = [r for d, _ in dm[:mid] for r in days[d]]
        late = [r for d, _ in dm[mid:] for r in days[d]]
        return {"status": "OK", "n": len(res), "days": len(dm),
                "pooled_mean": round(pooled, 2), "day_mean": round(mu, 2),
                "day_t": round(t, 2),
                "early_mean": round(sum(early) / len(early), 2) if early else None,
                "late_mean": round(sum(late) / len(late), 2) if late else None}
    except Exception as e:
        return {"status": "NO-DATA", "error": str(e)[:120]}


def render(db_path):
    h = health(db_path)
    if h.get("status") != "OK":
        return f"- FADE book shadow health: {h.get('status')} (n={h.get('n', 0)})"
    return ("- FADE book shadow health (spec replay on stored paths, executable prices): "
            f"n={h['n']} across {h['days']} days | pooled {h['pooled_mean']:+.2f}%/trade | "
            f"day-clustered {h['day_mean']:+.2f}% (t={h['day_t']:.2f}) | "
            f"halves {h['early_mean']:+.2f}/{h['late_mean']:+.2f} | "
            "LADDER: t>1 @4wk holds, t>2 @10wk scales, sign-flip or capture<50% kills")

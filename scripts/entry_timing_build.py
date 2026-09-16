"""ENTRY TIMING STUDY (research, owner order 2026-09-16 00:48 BST).

The puzzle: cheap contracts are the BEST slice close-to-close and the WORST on the intraday
qualifying-print basis. Three things differ between those measurements, not one - entry timing,
population, and exit resolution - so this isolates them with a PAIRED design: the same contract,
the same day, priced three ways and measured two ways.

  entries   AT_PRINT    the ask at the qualifying print (what the engine does live, minutes later)
            AT_CLOSE    the ask at that day's close
            NEXT_CLOSE  the ask at the next day's close
  exits     DAILY       contracts_daily bids, checked once a day (the whole-market corpus's method)
            HOURLY      hourly bars, stop checked on the LOW, trail on the close (the honest method)

Population is held constant: every arm uses the same qualifying-print contract-days, so any
difference between arms is entry timing or exit resolution, never selection.

Pre-registered before running (reports/research/whole_market_2026-09-15.md section 6):
  - the comparison of interest is AT_PRINT vs AT_CLOSE under HOURLY exits, split by ask band;
  - a difference counts only if it holds in BOTH halves of the archive and reaches |t| >= 2 on the
    daily differences of the paired arms;
  - if the cheap-vs-expensive ordering flips only when the EXIT method changes, the flip was an
    artefact of daily-resolution stops and nothing changes.

Writes one jsonl. Touches no spec, no model, no engine.
"""
import json
import os
import random
import sqlite3
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.expanduser("~/swing-trading-scanner")
os.chdir(REPO)
UW, HB = "data/uw_history.db", "data/hourly_paths.db"
OUT = "reports/research/entry_timing_v1.jsonl"
QUAL_PREM = 50000.0               # the v3 qualifying threshold
ASK_LO, ASK_HI = 0.30, 60.0       # wide: the ask-band split is the point of the study
HORIZON = 21
STOP, TRIG, GIVE = -50.0, 50.0, 0.20
PER_DAY = 80
SEED = 11


def occ_expiry(occ, tk):
    core = occ[len(tk):] if occ.startswith(tk) else occ
    try:
        return f"20{core[:2]}-{core[2:4]}-{core[4:6]}", ("C" if core[6:7] == "C" else "P")
    except Exception:
        return None, None


def run_exit(entry, seq):
    """BASE -50/+50/0.20 over a sequence of (low_ret, close_ret) pairs already in percent.
    DAILY passes (close_ret, close_ret) - the whole-market corpus's method, which cannot see an
    intraday breach. HOURLY passes the true low. Returns (ret, steps, reason)."""
    peak = 0.0
    armed = False
    last = None
    for i, (lo, cl) in enumerate(seq, 1):
        if cl is None:
            continue
        last = cl
        if lo is not None and lo <= STOP:
            return STOP, i, "stop"
        peak = max(peak, cl)
        if peak >= TRIG:
            armed = True
        if armed and cl <= peak * (1.0 - GIVE):
            return cl, i, "trail"
    return (last, len(seq), "horizon") if last is not None else (None, 0, "no_data")


def main():
    random.seed(SEED)
    uw = sqlite3.connect(UW)
    uw.execute("pragma cache_size=-40000")
    print("pass 1: qualifying prints", flush=True)
    entries = defaultdict(list)                 # day -> [entry dict]
    cur = uw.execute("select occ, day, executed_at, premium, nbbo_ask, side_hint from flow_prints "
                     "order by day, occ, executed_at")
    key = None
    cum = ask_p = bid_p = 0.0
    for occ, day, ts, prem, ask, side in cur:
        if (occ, day) != key:
            key, cum, ask_p, bid_p = (occ, day), 0.0, 0.0, 0.0
        if cum >= QUAL_PREM:
            continue                            # already qualified this contract-day
        p = prem or 0.0
        cum += p
        if side == "ask":
            ask_p += p
        elif side == "bid":
            bid_p += p
        if cum >= QUAL_PREM and ask_p > bid_p and ask and ask > 0:
            entries[day].append({"occ": occ, "day": day, "print_ts": (ts or "")[:19], "at_print": round(ask, 2)})
    days = sorted(entries)
    print(f"  qualifying contract-days: {sum(len(v) for v in entries.values()):,} over {len(days)} sessions", flush=True)
    sampled = {}
    for d in days:
        pick = entries[d] if len(entries[d]) <= PER_DAY else random.sample(entries[d], PER_DAY)
        for e in pick:
            sampled[(e["occ"], e["day"])] = e
    print(f"  sampled {len(sampled):,}", flush=True)

    print("pass 2: daily closes and daily exit paths", flush=True)
    all_days = [r[0] for r in uw.execute("select distinct day from contracts_daily order by day")]
    by_occ_day = defaultdict(dict)               # occ -> {day: (bid, ask)}
    want = {k[0] for k in sampled}
    for i, d in enumerate(all_days):
        for occ, bid, ask in uw.execute(
                "select option_symbol, nbbo_bid, nbbo_ask from contracts_daily where day=?", (d,)):
            if occ in want:
                by_occ_day[occ][d] = (bid, ask)
        if i % 60 == 0:
            print(f"    {d} cached {sum(len(v) for v in by_occ_day.values()):,}", flush=True)
    dpos = {d: i for i, d in enumerate(all_days)}

    print("pass 3: hourly bars + assemble", flush=True)
    hb = sqlite3.connect(HB)
    out = open(OUT, "w", encoding="utf-8")
    out.write(json.dumps({"_meta": "entry timing v1", "qualifying_premium": QUAL_PREM,
                          "entries": ["at_print", "at_close", "next_close"], "exits": ["daily", "hourly"],
                          "rule": [STOP, TRIG, GIVE], "horizon_days": HORIZON, "per_day": PER_DAY,
                          "seed": SEED, "paired": "same contract-day in every arm"}) + "\n")
    n = 0
    for (occ, d), e in sorted(sampled.items(), key=lambda kv: kv[0][1]):
        ser = by_occ_day.get(occ) or {}
        if d not in dpos or d not in ser:
            continue
        i0 = dpos[d]
        fwd = [all_days[j] for j in range(i0 + 1, min(i0 + 1 + HORIZON + 1, len(all_days)))]
        e["at_close"] = round(ser[d][1], 2) if ser[d][1] else None
        nd = fwd[0] if fwd else None
        e["next_close"] = round(ser[nd][1], 2) if nd and nd in ser and ser[nd][1] else None
        exp, side = occ_expiry(occ, occ[:len(occ) - 15] if len(occ) > 15 else occ)
        e["side"] = side
        e["dte"] = (date.fromisoformat(exp) - date.fromisoformat(d)).days if exp else None
        bars = hb.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,)).fetchall()
        for arm, price, start_day, start_ts in (("at_print", e["at_print"], d, e["print_ts"]),
                                                ("at_close", e.get("at_close"), d, d + "T20:00:00"),
                                                ("next_close", e.get("next_close"), nd, (nd or "") + "T20:00:00")):
            if not price or price <= 0 or not start_day:
                e[arm + "_daily"] = e[arm + "_hourly"] = None
                continue
            j0 = dpos[start_day]
            dseq = []
            for j in range(j0 + 1, min(j0 + 1 + HORIZON, len(all_days))):
                b = (ser.get(all_days[j]) or (None, None))[0]
                r = (b / price - 1.0) * 100.0 if b and b > 0 else None
                dseq.append((r, r))                       # daily: no intraday low, the artefact under test
            rr, st, why = run_exit(price, dseq)
            e[arm + "_daily"] = None if rr is None else round(rr, 2)
            e[arm + "_daily_why"] = why
            hseq = []
            for ts, h, lo, c in bars:
                if ts[:19] <= start_ts:
                    continue
                if len(hseq) >= HORIZON * 8:
                    break
                hseq.append((((lo / price - 1.0) * 100.0) if lo and lo > 0 else None,
                             ((c / price - 1.0) * 100.0) if c and c > 0 else None))
            rr2, st2, why2 = run_exit(price, hseq)
            e[arm + "_hourly"] = None if rr2 is None else round(rr2, 2)
            e[arm + "_hourly_why"] = why2
        e.pop("print_ts", None)
        out.write(json.dumps(e) + "\n")
        n += 1
        if n % 2000 == 0:
            print(f"    assembled {n:,}", flush=True)
    out.close()
    print(f"DONE {n:,} paired rows -> {OUT}", flush=True)


if __name__ == "__main__":
    main()

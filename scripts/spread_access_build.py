"""VERTICAL DEBIT SPREAD: does it buy access to the band where the edge lives? (research, read-only)

Owner order 2026-09-16 01:54 BST. Every cell's edge sits above $16 a contract and a $1,000 slot
cannot buy one. A vertical debit spread buys the contract with the edge and sells a further strike
against it, so the NET debit can fit the slot while the position still tracks the underlying move.

PAIRED, one population: qualifying flow prints (cumulative premium >= $50k, ask-side), the same
universe as the entry-timing study. For each one, three arms on the same contract-day:

  SINGLE       buy the trigger contract outright                     (affordable only if ask <= budget)
  SPREAD       buy it, sell the FURTHEST same-expiry strike whose credit still brings the net debit
               under budget - the rule keeps the most upside subject to affording it
  SINGLE_CAP   the same trigger bought outright at a LARGER budget   (the $1,600 / $2,500 question)

Exits: BASE -50 / +50 / 0.20 applied to the POSITION's value each day - for the spread that is
(long bid - short ask), the price you could actually unwind at, never the mid.

HONESTY: close-to-close basis (both legs priced from contracts_daily NBBO at the day's close), the
same basis as whole_market_affordable_v1 and NOT comparable to a v3 cell. All three arms share it,
so the SPREAD-vs-SINGLE comparison is the result and the levels are not. Daily resolution. A spread
caps the upside by construction, and this book's mean is carried by its tail, so the number to watch
is not the mean alone but what happens to the trades that would have run.
"""
import json
import os
import random
import sqlite3
from collections import defaultdict
from datetime import date

REPO = os.path.expanduser("~/swing-trading-scanner")
os.chdir(REPO)
UW = "data/uw_history.db"
OUT = "reports/research/spread_access_v1.jsonl"
QUAL_PREM = 50000.0
BUDGETS = [1000.0, 1600.0, 2500.0]
HORIZON = 21
STOP, TRIG, GIVE = -50.0, 50.0, 0.20
PER_DAY = 40
SEED = 13


def parse_occ(occ):
    """(ticker, expiry_iso, side, strike) from an OCC symbol."""
    i = len(occ) - 15
    if i < 1:
        return None
    try:
        return (occ[:i], f"20{occ[i:i+2]}-{occ[i+2:i+4]}-{occ[i+4:i+6]}",
                occ[i+6], int(occ[i+7:]) / 1000.0)
    except Exception:
        return None


def run_exit(seq):
    peak = 0.0
    armed = False
    last = None
    for i, r in enumerate(seq, 1):
        if r is None:
            continue
        last = r
        if r <= STOP:
            return STOP, i, "stop"
        peak = max(peak, r)
        if peak >= TRIG:
            armed = True
        if armed and r <= peak * (1.0 - GIVE):
            return r, i, "trail"
    return (last, len(seq), "horizon") if last is not None else (None, 0, "no_data")


def main():
    random.seed(SEED)
    uw = sqlite3.connect(UW)
    uw.execute("pragma cache_size=-40000")
    print("pass 1: qualifying prints", flush=True)
    ent = defaultdict(list)
    key = None
    cum = ask_p = bid_p = 0.0
    for occ, day, ts, prem, ask, side in uw.execute(
            "select occ, day, executed_at, premium, nbbo_ask, side_hint from flow_prints order by day, occ, executed_at"):
        if (occ, day) != key:
            key, cum, ask_p, bid_p = (occ, day), 0.0, 0.0, 0.0
        if cum >= QUAL_PREM:
            continue
        p = prem or 0.0
        cum += p
        if side == "ask":
            ask_p += p
        elif side == "bid":
            bid_p += p
        if cum >= QUAL_PREM and ask_p > bid_p:
            ent[day].append(occ)
    days_all = [r[0] for r in uw.execute("select distinct day from contracts_daily order by day")]
    dpos = {d: i for i, d in enumerate(days_all)}
    sampled = {}
    for d, lst in ent.items():
        if d not in dpos:
            continue
        for occ in (random.sample(lst, PER_DAY) if len(lst) > PER_DAY else lst):
            sampled[(occ, d)] = True
    print(f"  qualifying {sum(len(v) for v in ent.values()):,}; sampled {len(sampled):,}", flush=True)

    out = open(OUT, "w", encoding="utf-8")
    out.write(json.dumps({"_meta": "spread access v1", "basis": "close_to_close",
                          "budgets": BUDGETS, "rule": [STOP, TRIG, GIVE], "horizon": HORIZON,
                          "short_leg": "furthest same-expiry strike whose credit brings the net debit under budget",
                          "unwind": "long bid minus short ask (executable, never mid)",
                          "warning": "not comparable to a v3 cell; spread-vs-single is the result"}) + "\n")
    pending = defaultdict(list)          # occ -> [(entry_row, leg) ...] awaiting forward prices
    need = defaultdict(dict)             # entry_id -> {occ: [prices]}
    live = {}
    n_done = 0
    for di, d in enumerate(days_all):
        rows = uw.execute("select option_symbol, nbbo_bid, nbbo_ask from contracts_daily where day=?", (d,)).fetchall()
        quote = {o: (b, a) for o, b, a in rows}
        # 1) advance open positions
        done = []
        for eid, e in list(live.items()):
            lb, la = quote.get(e["long"], (None, None))
            if e["short"]:
                sb, sa = quote.get(e["short"], (None, None))
                val = (lb - sa) if (lb is not None and sa is not None) else None
            else:
                val = lb
            e["path"].append(None if (val is None or e["debit"] <= 0) else (val / e["debit"] - 1.0) * 100.0)
            if len(e["path"]) >= HORIZON or e["expiry"] <= d:
                done.append(eid)
        for eid in done:
            e = live.pop(eid)
            r, steps, why = run_exit(e["path"])
            e.pop("path")
            e["ret"] = None if r is None else round(r, 2)
            e["held"] = steps
            e["why"] = why
            out.write(json.dumps(e) + "\n")
            n_done += 1
        # 2) new entries for this day
        todays = [occ for (occ, dd) in sampled if dd == d] if di < 0 else None
        for (occ, dd) in list(sampled.keys()):
            if dd != d:
                continue
            p = parse_occ(occ)
            if not p:
                continue
            tk, exp, side, strike = p
            lb, la = quote.get(occ, (None, None))
            if not la or la <= 0 or exp <= d:
                continue
            # chain: same ticker, same expiry, same side
            chain = []
            for o2, (b2, a2) in quote.items():
                if not o2.startswith(tk) or len(o2) != len(occ):
                    continue
                q = parse_occ(o2)
                if not q or q[1] != exp or q[2] != side:
                    continue
                if b2 and b2 > 0:
                    chain.append((q[3], b2))
            for budget in BUDGETS:
                base = {"day": d, "occ": occ, "t": tk, "side": side, "dte": (date.fromisoformat(exp) - date.fromisoformat(d)).days,
                        "long_ask": round(la, 2), "budget": budget, "expiry": exp}
                if la * 100 <= budget:                      # SINGLE affordable at this budget
                    e = dict(base); e["arm"] = "single"; e["debit"] = la; e["short"] = None
                    e["long"] = occ; e["path"] = []; e["width"] = None
                    live[f"{occ}|{d}|s{budget}"] = e
                # SPREAD: furthest strike whose credit brings the net debit under budget
                cands = [(k, b) for k, b in chain if (k > strike if side == "C" else k < strike)]
                cands.sort(key=lambda x: -abs(x[0] - strike))     # furthest first = most upside kept
                pick = None
                for k, b in cands:
                    if (la - b) > 0 and (la - b) * 100 <= budget:
                        pick = (k, b)
                        break
                if pick:
                    k, b = pick
                    e = dict(base); e["arm"] = "spread"; e["debit"] = round(la - b, 2)
                    e["short"] = (occ[:len(occ) - 8] + f"{int(k*1000):08d}")
                    e["long"] = occ; e["path"] = []; e["width"] = round(abs(k - strike), 2)
                    e["short_bid"] = round(b, 2)
                    live[f"{occ}|{d}|p{budget}"] = e
        if di % 60 == 0:
            print(f"    {d} live {len(live):,} written {n_done:,}", flush=True)
    for eid, e in live.items():
        if not e["path"]:
            continue
        r, steps, why = run_exit(e["path"])
        e.pop("path"); e["ret"] = None if r is None else round(r, 2); e["held"] = steps; e["why"] = why
        out.write(json.dumps(e) + "\n"); n_done += 1
    out.close()
    print(f"DONE {n_done:,} rows -> {OUT}", flush=True)


if __name__ == "__main__":
    main()

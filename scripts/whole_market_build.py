"""WHOLE-MARKET AFFORDABLE CORPUS (research, owner order 2026-09-15 23:50 BST).

The question: the live scan only surfaces names whose flow cleared $50,000 of premium, and the
evidence corpus was built from that same floor, so nothing we own can say whether contracts BELOW
it have edge. `data/uw_history.db:contracts_daily` does not have that floor - it is every contract
with volume, 61M contract-days over 509 sessions - so the answer is already on disk.

Builds one row per sampled affordable contract-day: entry at that day's NBBO ASK, forward path at
each later day's NBBO BID, and the seat's BASE exit (-50 stop / +50 trigger / 20% giveback) applied
at DAILY resolution.

HONESTY, stated here and in the report:
  - This is a CLOSE-TO-CLOSE basis. The v3 corpus enters at the ask of a qualifying intraday print;
    this enters at the day's closing ask. The two are NOT comparable and no number from here may be
    quoted against a v3 cell. Within this file every slice shares the basis, so RELATIVE questions
    (sub-50k vs 50k+, mid-cap vs mega-cap, premium rank) are answerable and absolute levels are not.
  - Daily resolution flatters stops: a stop breached intraday and recovered by the close is not seen.
  - Sampling is per day and stratified by the flow floor so both sides are measurable; the sample
    is recorded in the header row so nothing here can be mistaken for the whole market.
Writes ONE jsonl under reports/research/. Touches no spec, no model, no engine.
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
DB = "data/uw_history.db"
OUT = "reports/research/whole_market_affordable_v1.jsonl"
ASK_LO, ASK_HI = 0.30, 9.90
HORIZON = 21                      # trading days of forward path
PER_DAY = 240                     # sampled entries per day, per side of the flow floor
STOP, TRIG, GIVE = -50.0, 50.0, 0.20
SEED = 7


def occ_parts(occ, ticker):
    """(expiry_iso, side) from an OCC symbol; None on anything non-standard."""
    core = occ[len(ticker):] if occ.startswith(ticker) else occ
    if len(core) < 7:
        return None, None
    d, s = core[:6], core[6:7]
    try:
        return f"20{d[:2]}-{d[2:4]}-{d[4:6]}", ("C" if s == "C" else "P" if s == "P" else None)
    except Exception:
        return None, None


def base_exit(entry, path):
    """BASE exit at daily resolution. Returns (return_pct, days_held, reason)."""
    peak = 0.0
    armed = False
    for i, bid in enumerate(path, 1):
        if bid is None or bid <= 0:
            continue
        ret = (bid / entry - 1.0) * 100.0
        peak = max(peak, ret)
        if ret <= STOP:
            return STOP, i, "stop"
        if peak >= TRIG:
            armed = True
        if armed and ret <= peak * (1.0 - GIVE):
            return ret, i, "trail"
    for i in range(len(path) - 1, -1, -1):
        if path[i] is not None and path[i] > 0:
            return (path[i] / entry - 1.0) * 100.0, i + 1, "horizon"
    return -100.0, len(path), "no_bid"


def main():
    random.seed(SEED)
    con = sqlite3.connect(DB)
    con.execute("pragma cache_size=-40000")            # ~40MB, well inside the box's headroom
    days = [r[0] for r in con.execute("select distinct day from contracts_daily order by day")]
    print(f"{len(days)} sessions {days[0]}..{days[-1]}", flush=True)
    out = open(OUT, "w", encoding="utf-8")
    out.write(json.dumps({"_meta": "whole-market affordable corpus v1", "basis": "close_to_close",
                          "entry": "nbbo_ask at the day's close", "exit": "nbbo_bid, BASE -50/+50/0.20 at daily resolution",
                          "ask_band": [ASK_LO, ASK_HI], "horizon_days": HORIZON,
                          "sample_per_day_per_side": PER_DAY, "seed": SEED, "sessions": len(days),
                          "warning": "NOT comparable to probe_tuner_rows_v3 (intraday qualifying-print basis); "
                                     "relative comparisons within this file only"}) + "\n")
    pending = defaultdict(list)          # occ -> [entry dicts still collecting a path]
    n_entry = n_done = 0
    for di, d in enumerate(days):
        rows = con.execute(
            "select ticker, option_symbol, nbbo_bid, nbbo_ask, total_premium, volume, open_interest, "
            "implied_volatility, delta from contracts_daily where day=?", (d,)).fetchall()
        # 1) advance every open path with today's bid
        closed = []
        for tk, occ, bid, ask, prem, vol, oi, iv, dlt in rows:
            if occ in pending:
                for e in pending[occ]:
                    e["path"].append(bid)
        for occ in list(pending):
            keep = []
            for e in pending[occ]:
                if len(e["path"]) >= HORIZON or e["expiry"] <= d:
                    closed.append(e)
                else:
                    keep.append(e)
            if keep:
                pending[occ] = keep
            else:
                del pending[occ]
        for e in closed:
            ret, held, why = base_exit(e["entry"], e["path"])
            e.pop("path"); e.pop("expiry", None)
            e["ret"] = round(ret, 2)
            e["held_days"] = held
            e["exit_reason"] = why
            out.write(json.dumps(e) + "\n")
            n_done += 1
        # 2) today's entry candidates, sampled either side of the flow floor
        cand_lo, cand_hi = [], []
        prem_by_tk = defaultdict(float)
        for tk, occ, bid, ask, prem, vol, oi, iv, dlt in rows:
            if prem:
                prem_by_tk[tk] += prem
            if ask is None or bid is None or not (ASK_LO <= ask <= ASK_HI) or not vol or vol <= 0 or bid <= 0:
                continue
            (cand_lo if (prem or 0) < 50000 else cand_hi).append((tk, occ, ask, prem, vol, oi, iv, dlt))
        rank = {tk: i + 1 for i, tk in enumerate(sorted(prem_by_tk, key=lambda t: -prem_by_tk[t]))}
        for bucket in (cand_lo, cand_hi):
            for tk, occ, ask, prem, vol, oi, iv, dlt in (random.sample(bucket, PER_DAY) if len(bucket) > PER_DAY else bucket):
                exp, side = occ_parts(occ, tk)
                if not exp or not side:
                    continue
                dte = (date.fromisoformat(exp) - date.fromisoformat(d)).days
                if dte < 1 or dte > 120:
                    continue
                pending[occ].append({"day": d, "t": tk, "occ": occ, "entry": round(ask, 2), "side": side,
                                     "prem": round(prem or 0.0, 0), "vol": int(vol or 0), "oi": int(oi or 0),
                                     "iv": round(iv, 4) if iv is not None else None,
                                     "delta": round(dlt, 4) if dlt is not None else None,
                                     "dte": dte, "expiry": exp, "prem_rank": rank.get(tk), "path": []})
                n_entry += 1
        if di % 25 == 0:
            print(f"  {d}  entries {n_entry:,}  completed {n_done:,}  open {sum(len(v) for v in pending.values()):,}", flush=True)
    for occ in pending:                   # flush whatever is still open at the end of the archive
        for e in pending[occ]:
            if not e["path"]:
                continue
            ret, held, why = base_exit(e["entry"], e["path"])
            e.pop("path"); e.pop("expiry", None)
            e["ret"] = round(ret, 2); e["held_days"] = held; e["exit_reason"] = why
            out.write(json.dumps(e) + "\n"); n_done += 1
    out.close()
    print(f"DONE entries {n_entry:,} rows written {n_done:,} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()

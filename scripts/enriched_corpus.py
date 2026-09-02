"""ENRICHED SCENARIO CORPUS (owner order 2026-09-02 night). Adds feature BLOCKS to the tuner's
39.5k-trigger corpus, each with a declared INFORMATION TIME so the ablation is honest:

  IVX     prev-day (D-1) ticker/contract state: median ticker IV, contract delta/theta,
          prev_oi and OI change into the day - all knowable before entry.
  MICRO   strictly pre-print tape: prints on ANY of the ticker's contracts that day with
          executed_at < entry print ts (count, premium sum, ask-side share).
  PATH    strictly pre-print option bars of the trigger occ that day (count, range%, drift%).
  BREADTH corpus triggers earlier the same day (distinct tickers with print ts < this ts).
  VOL     underlying 20d realized vol from daily closes ENDING D-1.
  CANARY  the first post-entry hourly bar's return - DELIBERATE LEAK, detector only: the
          ablation harness must show a big AUC spike here or it cannot be trusted to reveal
          leaks elsewhere.

LEAKAGE RULE (pre-registered, 07-26 discipline): every comparison in code is strict `<` on
the print timestamp or uses day <= D-1 data. The BASE features (ask/prem from day-close
snapshots) carry the corpus's historical approximation - documented, shared by every prior
student - so block DELTAS on top of BASE are the clean measurements.
Output: reports/research/enriched_rows.jsonl (one line per trigger, blocks nested).
"""
import json
import math
import os
import sqlite3
import time
import urllib.request
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}
OUT = "reports/research/enriched_rows.jsonl"


def closes_series(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-31&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                return {x["t"][:10]: x["c"] for x in (json.loads(r.read()).get("bars") or {}).get(s) or []}
        except Exception:
            time.sleep(3)
    return {}


def main():
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    cur = lib.cursor()
    rows = []
    for line in open("reports/research/probe_tuner_rows.jsonl", encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    print(f"base corpus: {len(rows)} triggers", flush=True)

    prints_ix = defaultdict(list)              # ticker -> [(executed_at, premium, side_hint)]
    trig_ts = {}
    for occ, day, ts, prem, side in src.execute(
            "select occ, day, executed_at, premium, side_hint from flow_prints"):
        t = occ[:len(occ) - 15] if len(occ) > 15 else occ
        prints_ix[(t, day)].append((ts, prem or 0.0, side or ""))
    for k in prints_ix:
        prints_ix[k].sort()
    for occ, day, ts in src.execute("select occ, day, min(executed_at) from flow_prints group by occ, day"):
        trig_ts[(occ, day)] = ts
    print("prints indexed", flush=True)

    # OOM discipline (BREAKDOWNS 08-26, relearned tonight the hard way): the first version of
    # this pass held all 11.7M archive rows in dicts and the kernel killed it on the 2GB box.
    # Same single scan now, but ONLY rows the corpus needs are kept: IV as running sum/count
    # per (corpus ticker, day); prev-day contract state only for the 39.5k corpus occs.
    corpus_tks = {r["t"] for r in rows}
    corpus_occs = {r["occ"] for r in rows}
    iv_sum = defaultdict(float); iv_n = defaultdict(int)
    contract_prev = {}
    for t, occ, day, iv, dl, th, oi, poi in src.execute(
            "select ticker, option_symbol, day, implied_volatility, delta, theta, "
            "open_interest, prev_oi from contracts_daily"):
        if t in corpus_tks and iv:
            iv_sum[(t, day)] += iv; iv_n[(t, day)] += 1
        if occ in corpus_occs:
            contract_prev[(occ, day)] = (dl, th, oi, poi)
    day_sorted = defaultdict(list)
    for (t, day) in iv_n:
        day_sorted[t].append(day)
    for t in day_sorted:
        day_sorted[t].sort()
    print("iv indexed (bounded)", flush=True)

    tks = sorted({r["t"] for r in rows})
    rv20 = {}
    for t in tks:
        c = closes_series(t)
        ds = sorted(c)
        rets = {}
        for i in range(1, len(ds)):
            rets[ds[i]] = c[ds[i]] / c[ds[i - 1]] - 1
        rl = []
        for i, dd in enumerate(ds):
            win = [rets[x] for x in ds[max(0, i - 20):i] if x in rets]
            if len(win) >= 10:
                mu = sum(win) / len(win)
                rv20[(t, dd)] = (sum((x - mu) ** 2 for x in win) / (len(win) - 1)) ** 0.5 * 100
        # rv for day D looks up window ENDING D-1 by construction (slice excludes i)
    print("rv20 built", flush=True)

    trig_by_day = defaultdict(list)
    for r in rows:
        ts = trig_ts.get((r["occ"], r["day"]))
        if ts:
            trig_by_day[r["day"]].append((ts, r["t"]))
    for d in trig_by_day:
        trig_by_day[d].sort()

    out = open(OUT, "w", encoding="utf-8")
    n = 0
    for r in rows:
        occ, t, day = r["occ"], r["t"], r["day"]
        pts = trig_ts.get((occ, day))
        if not pts:
            continue
        blocks = {}
        pdays = [x for x in day_sorted.get(t, []) if x < day]
        pd = pdays[-1] if pdays else None
        med_iv = (iv_sum[(t, pd)] / iv_n[(t, pd)]) if pd and iv_n.get((t, pd)) else None
        cp = contract_prev.get((occ, pd)) if pd else None
        oi_now = contract_prev.get((occ, day))
        blocks["ivx"] = {"tkr_iv_prev": med_iv,
                         "delta_prev": cp[0] if cp else None,
                         "theta_prev": cp[1] if cp else None,
                         "prev_oi": oi_now[3] if oi_now else None,
                         "oi_chg": (oi_now[3] - cp[2]) if (oi_now and cp and oi_now[3] is not None
                                                           and cp[2] is not None) else None}
        earlier = [p for p in prints_ix.get((t, day), []) if p[0] < pts]
        ask_side = sum(1 for p in earlier if "ask" in p[2].lower()) if earlier else 0
        blocks["micro"] = {"n_prints_before": len(earlier),
                           "prem_before": round(sum(p[1] for p in earlier), 0),
                           "ask_share_before": round(ask_side / len(earlier), 3) if earlier else None}
        bars_pre = [(h, l, c_) for ts_, h, l, c_ in cur.execute(
            "select ts, h, l, c from bars where occ=? and ts like ? order by ts", (occ, day + "%"))
            if ts_[11:19] < pts[11:19]]
        if bars_pre:
            hi = max(b[0] for b in bars_pre); lo = min(b[1] for b in bars_pre)
            blocks["path"] = {"n_bars_pre": len(bars_pre),
                              "range_pre": round((hi - lo) / max(lo, .01) * 100, 1),
                              "drift_pre": round((bars_pre[-1][2] / max(bars_pre[0][2], .01) - 1) * 100, 1)}
        else:
            blocks["path"] = {"n_bars_pre": 0, "range_pre": None, "drift_pre": None}
        blocks["breadth"] = {"trigs_before": len({tk for ts_, tk in trig_by_day.get(day, [])
                                                  if ts_ < pts and tk != t})}
        blocks["vol"] = {"rv20": rv20.get((t, day))}
        bars_post = [c_ for ts_, h, l, c_ in cur.execute(
            "select ts, h, l, c from bars where occ=? and ts like ? order by ts", (occ, day + "%"))
            if ts_[11:19] > pts[11:19]]
        e = bars_post[0] if bars_post else None
        blocks["canary"] = {"post1": round((bars_post[1] / e - 1) * 100, 2)
                            if e and len(bars_post) > 1 and e > 0 else None}
        out.write(json.dumps({**{k: r[k] for k in ("occ", "t", "day", "prem", "ask", "side",
                                                   "smd", "reg", "sp", "rets")},
                              "blocks": blocks}) + "\n")
        n += 1
        if n % 4000 == 0:
            print(f"enriched {n}", flush=True)
    out.close()
    print(f"ENRICHED CORPUS COMPLETE: {n} rows -> {OUT}", flush=True)


if __name__ == "__main__":
    main()

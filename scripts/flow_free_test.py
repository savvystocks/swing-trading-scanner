"""FLOW-FREE TEST (owner order 2026-08-31: "run the flow-free test now and cancel UW if it
passes"). The $150/mo question: do the dip strategies need the PAID flow trigger, or does a
FREE price-only trigger match it?

Head-to-head per regime (bull / mild / bear), same 47 tickers, same hourly-path replays:
  FLOW      - the paid trigger: aggressive call buying (ask>bid volume, premium 50-400k) on a
              ticker trading below its 20d SMA. (What BULL_DIP/DIP_CONVEXITY use today.)
  FLOW-FREE - price-only: the ticker closed below its 20d SMA that day, full stop. One
              candidate per ticker-day: the most liquid call, 20-60 DTE, delta .35-.65,
              spread<=2. Zero UW inputs (selection uses only chain liquidity + price data
              Alpaca provides free).
Both replayed with live exits (50/50/20) and wide (-70/80/30), entry at ask, day-clustered.
PASS RULE (pre-registered): flow-free within 3 pts/day of flow - or better - in each regime
where the flow version is positive => the trigger does not need UW.
Output: reports/research/flow_free_2026-08-31.md
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


def smad(c, n=20):
    d = sorted(c); o = {}; buf = []
    for x in d:
        buf.append(c[x]); o[x] = (c[x] / (sum(buf[-n:]) / min(len(buf), n)) - 1) * 100
    return o


def dstat(rows):
    per = defaultdict(list)
    for d, r in rows:
        per[d].append(r)
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 6:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    return {"n": len(rows), "u": n, "mean": round(mu, 1), "t": round(t, 2),
            "h1": round(sum(m[:h]) / max(h, 1), 1), "h2": round(sum(m[h:]) / max(n - h, 1), 1)}


def hourly_outcome(bars, e, stop, trig, give):
    peak, on = -999.0, False
    for (h, l, c) in bars:
        rh = (h / e - 1) * 100; rl = (l / e - 1) * 100
        if rh >= trig:
            on = True
        if on:
            peak = max(peak, rh)
            fl = peak * (1 - give)
            if rl <= fl:
                return fl
        if rl <= stop:
            return stop
    return (bars[-1][2] / e - 1) * 100 if bars else None


def main():
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    cur = lib.cursor()
    tks = {r[0] for r in src.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    sm = {t: smad(closes_series(t)) for t in tks}
    spyc = closes_series("SPY")
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100

    def regname(day):
        r = s50.get(day)
        if r is None:
            return None
        return "bear" if r < -2 else ("bull" if r > 2 else "mild")

    def bars_after(occ, day):
        return [(h, l, c) for ts, h, l, c in
                cur.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,))
                if ts[:10] > day]

    flow = defaultdict(list)          # (regime, exit) -> [(day, ret)]
    seen = set()
    for t, occ, day, bid, ask in src.execute(
            """select ticker, option_symbol, day, nbbo_bid, nbbo_ask from contracts_daily
               where total_premium between 50000 and 400000 and ask_volume > bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
               order by day"""):
        if occ in seen or t not in tks or occ[-9] != "C":
            continue
        smd = (sm.get(t) or {}).get(day); rg = regname(day)
        if smd is None or rg is None or smd >= 0:
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0 or (ask - bid) / mid * 100 > 2.0:
            continue
        seen.add(occ)
        b = bars_after(occ, day)
        if len(b) < 3:
            continue
        for exn, (st, tg, gv) in (("live", (-50.0, 50.0, 0.20)), ("wide", (-70.0, 80.0, 0.30))):
            r = hourly_outcome(b, ask, st, tg, gv)
            if r is not None:
                flow[(rg, exn)].append((day, r))
    print("flow cohorts done", flush=True)

    # FLOW-FREE: one candidate per dip ticker-day, chosen by liquidity/structure ONLY
    free = defaultdict(list)
    pick = {}
    for t, occ, day, vol, bid, ask, dl in src.execute(
            """select ticker, option_symbol, day, volume, nbbo_bid, nbbo_ask, delta
               from contracts_daily
               where nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
                 and delta is not null order by day"""):
        if t not in tks or occ[-9] != "C":
            continue
        smd = (sm.get(t) or {}).get(day)
        if smd is None or smd >= 0:
            continue
        d_ = abs(float(dl))
        if not (0.35 <= d_ <= 0.65):
            continue
        try:
            exp = "20" + occ[len(t):len(t) + 6]
            dte = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
        except Exception:
            continue
        if not (20 <= dte <= 60):
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0 or (ask - bid) / mid * 100 > 2.0:
            continue
        k = (t, day)
        if k not in pick or (vol or 0) > pick[k][1]:
            pick[k] = (occ, vol or 0, ask)
    print(f"flow-free candidates: {len(pick)} ticker-days", flush=True)
    used = set()
    for (t, day), (occ, _, ask) in pick.items():
        if occ in used:
            continue
        used.add(occ)
        rg = regname(day)
        if rg is None:
            continue
        b = bars_after(occ, day)
        if len(b) < 3:
            continue
        for exn, (st, tg, gv) in (("live", (-50.0, 50.0, 0.20)), ("wide", (-70.0, 80.0, 0.30))):
            r = hourly_outcome(b, ask, st, tg, gv)
            if r is not None:
                free[(rg, exn)].append((day, r))

    L = ["# FLOW-FREE TEST - 2026-08-31 (the $150/month question)", "",
         "| regime/exit | FLOW (paid trigger) | FLOW-FREE (price only) | gap | verdict |",
         "|---|---|---|---|---|"]
    passes = 0; comparisons = 0
    for rg in ("bull", "mild", "bear"):
        for exn in ("live", "wide"):
            a = dstat(flow.get((rg, exn), []))
            b2 = dstat(free.get((rg, exn), []))
            av = f"{a['mean']:+.1f}/t{a['t']:+.1f} ({a['u']}d)" if a else "thin"
            bv = f"{b2['mean']:+.1f}/t{b2['t']:+.1f} ({b2['u']}d)" if b2 else "thin"
            verdict = "-"
            if a and b2 and a["mean"] > 0:
                comparisons += 1
                gap = b2["mean"] - a["mean"]
                verdict = "PASS" if gap >= -3.0 else "flow wins"
                if verdict == "PASS":
                    passes += 1
                L.append(f"| {rg}/{exn} | {av} | {bv} | {gap:+.1f} | {verdict} |")
            else:
                L.append(f"| {rg}/{exn} | {av} | {bv} | - | {verdict} |")
    L += ["", f"PASS RULE: flow-free within 3 pts/day (or better) wherever flow is positive.",
          f"RESULT: {passes}/{comparisons} comparisons PASS -> "
          + ("UW LIVE FEED NOT REQUIRED for the dip strategies - CANCEL SUPPORTED"
             if comparisons and passes == comparisons else
             "flow retains value in some regimes - see table before cancelling")]
    open("reports/research/flow_free_2026-08-31.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("FLOW-FREE TEST COMPLETE", flush=True)


if __name__ == "__main__":
    main()

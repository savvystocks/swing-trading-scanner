"""PRECISE REPLAY (owner order 2026-08-25: "isnt there anywhere with a full record, precise
per day... find and do that").

The answer: Alpaca's own historical OPTION BARS - per-hour traded prices for every contract
back to Feb 2024, free on our account. This re-runs the decisive verdicts at HOURLY resolution,
fixing the daily-close blind spots: stops that touched intraday (bar LOW), trail peaks between
closes (bar HIGH), whipsaws the daily replay muted.

Replay convention (matches live mechanics, conservative):
  entry  = the archive's closing ASK on trigger day (executable, same as before)
  path   = hourly bars of the SAME contract, from the next session onward
  stop   = fires if bar LOW <= stop level -> booked AT the stop level
  trail  = MFE tracked from bar HIGHs; exit when bar LOW crosses the trail floor -> booked at floor
  else   = final close
Cohorts re-verified: FADE live-config in bear (band 50-400k, spr<=2, stop-50/trig50/give20)
and the SWEEP_DEEPBEAR variant (50k-1M, delta<0.30, stop-60/trig80/give20, bear<-3).
Output: reports/research/precise_replay_2026-08-25.md - hourly verdict vs daily verdict = the
measured bias of every daily-resolution study to date.
"""
import json
import math
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}


def closes(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-25&limit=10000&adjustment=split&feed=iex")
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


def opt_bars(occ, start, end):
    """Hourly bars for one option contract. Returns [(t, o, h, l, c)] or []."""
    q = urllib.parse.urlencode({"symbols": occ, "timeframe": "1Hour", "start": start,
                                "end": end, "limit": 10000})
    u = f"https://data.alpaca.markets/v1beta1/options/bars?{q}"
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                bars = (json.loads(r.read()).get("bars") or {}).get(occ) or []
            return [(b["t"], b["o"], b["h"], b["l"], b["c"]) for b in bars]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20); continue
            return []
        except Exception:
            time.sleep(3)
    return []


def replay_hourly(bars, e, stop, trig, give):
    """OHLC-aware: stop on bar LOW touch (booked at stop); trail floor on LOW (booked at floor);
    MFE from HIGHs. Returns (ret_pct, exit_kind)."""
    peak = -999.0
    on = False
    for (_, o, h, l, c) in bars:
        rh = (h / e - 1) * 100
        rl = (l / e - 1) * 100
        rc = (c / e - 1) * 100
        if rh >= trig:
            on = True
        if on:
            peak = max(peak, rh)
            floor = peak * (1 - give)
            if rl <= floor:
                return floor, "TRAIL"
        if rl <= stop:
            return stop, "STOP"
    if bars:
        return (bars[-1][4] / e - 1) * 100, "END"
    return None, "NO_BARS"


def dstat(rows):
    per = defaultdict(list)
    for d, r in rows:
        per[d].append(r)
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 5:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    return {"n": len(rows), "days": n, "mean": round(mu, 1), "t": round(t, 2),
            "h1": round(sum(m[:h]) / max(h, 1), 1), "h2": round(sum(m[h:]) / max(n - h, 1), 1)}


def main():
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")]
    tkset = set(tks)
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100

    # daily-path map for the daily-resolution comparison
    fwd = defaultdict(list)
    for occ, day, bid in con.execute("select option_symbol, day, nbbo_bid from contracts_daily "
                                     "where nbbo_bid is not null and nbbo_bid>0 order by day"):
        fwd[occ].append((day, bid))

    def replay_daily(path, e, stop, trig, give):
        pk, on = -999.0, False
        for b in path:
            r = (b / e - 1) * 100
            if r >= trig:
                on = True
            if on:
                pk = max(pk, r)
                if r <= pk * (1 - give):
                    return r
            if r <= stop:
                return stop
        return (path[-1] / e - 1) * 100 if path else None

    cohorts = {
        "FADE_LIVE_bear": {"reg_lt": -2.0, "band": (50000, 400000), "spr": 2.0, "dmax": 1.01,
                           "stop": -50.0, "trig": 50.0, "give": 0.20},
        "SWEEP_DEEPBEAR": {"reg_lt": -3.0, "band": (50000, 1000000), "spr": 2.0, "dmax": 0.30,
                           "stop": -60.0, "trig": 80.0, "give": 0.20},
    }
    rows = con.execute(
        """select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,delta,
                  nbbo_bid,nbbo_ask from contracts_daily
           where total_premium between 50000 and 1000000 and ask_volume>bid_volume
             and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask>0
             and delta is not null order by day""").fetchall()
    out = {k: {"daily": [], "hourly": [], "kinds": defaultdict(int)} for k in cohorts}
    seen = {k: set() for k in cohorts}
    n_req = 0
    for t, occ, day, prem, av, bv, dl, bid, ask in rows:
        if t not in tkset:
            continue
        smd = (sm.get(t) or {}).get(day); sp = spy20.get(day); reg = s50.get(day)
        if smd is None or sp is None or reg is None:
            continue
        side = 1 if occ[-9] == "C" else -1
        if not (smd * side < 0 and sp * side < 0):
            continue
        mid = (bid + ask) / 2.0
        sprd = (ask - bid) / mid * 100 if mid > 0 else 99.0
        for ck, c in cohorts.items():
            if occ in seen[ck]:
                continue
            if reg >= c["reg_lt"] or not (c["band"][0] <= prem <= c["band"][1]):
                continue
            if sprd > c["spr"] or abs(float(dl)) >= c["dmax"]:
                continue
            dpath = [b for d, b in fwd.get(occ, []) if d > day][:60]
            if len(dpath) < 2:
                continue
            seen[ck].add(occ)
            rd = replay_daily(dpath, ask, c["stop"], c["trig"], c["give"])
            if rd is not None:
                out[ck]["daily"].append((day, rd))
            start = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
            end = min(date.fromisoformat(day) + timedelta(days=65), date(2026, 8, 24)).isoformat()
            hb = opt_bars(occ, start, end)
            n_req += 1
            if n_req % 25 == 0:
                print(f"{n_req} contracts pulled...", flush=True)
            time.sleep(0.31)                       # 200 req/min budget
            rh, kind = replay_hourly(hb, ask, c["stop"], c["trig"], c["give"])
            out[ck]["kinds"][kind] += 1
            if rh is not None:
                out[ck]["hourly"].append((day, rh))

    L = ["# PRECISE REPLAY - 2026-08-25 (hourly Alpaca bars vs daily archive closes)", "",
         "Same contracts, same entry (archive ask), same exit rules. HOURLY sees intraday stop",
         "touches (bar lows) and true trail peaks (bar highs) that daily closes cannot.", ""]
    for ck in cohorts:
        d0 = dstat(out[ck]["daily"]); h0 = dstat(out[ck]["hourly"])
        L.append(f"## {ck}")
        L.append(f"  daily-resolution : " + (f"{d0['mean']:+.1f}%/day t{d0['t']:+.2f} "
                 f"({d0['days']}d, n={d0['n']}, halves {d0['h1']:+.0f}/{d0['h2']:+.0f})" if d0 else "thin"))
        L.append(f"  HOURLY-precision : " + (f"{h0['mean']:+.1f}%/day t{h0['t']:+.2f} "
                 f"({h0['days']}d, n={h0['n']}, halves {h0['h1']:+.0f}/{h0['h2']:+.0f})" if h0 else "thin"))
        if d0 and h0:
            L.append(f"  BIAS of daily studies: {d0['mean'] - h0['mean']:+.1f} pts/day "
                     f"({'daily was OPTIMISTIC' if d0['mean'] > h0['mean'] else 'daily was CONSERVATIVE'})")
        L.append(f"  exit kinds (hourly): {dict(out[ck]['kinds'])}")
        L.append("")
    open("reports/research/precise_replay_2026-08-25.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("PRECISE REPLAY COMPLETE", flush=True)


if __name__ == "__main__":
    main()

"""WINNER STRESS TEST (2026-08-23): is the mega-sweep winner an edge, or a few violent days?

The sweep's winner - FADE / deep-bear(+-3%) / 50k-1M / spread<=3 / delta<0.30 / stop-60 /
trig80 / give20 - scored +67.8% day-mean (t+3.43) but with halves +11/+122. That split is the
signature of concentration. Day-clustering does NOT fix EPISODE clustering: 30-odd bear days
drawn from two or three corrections are not 30 independent observations.

Tests:
  1. Day count, and the per-day return ladder (is it carried by 1-3 days?)
  2. EPISODE grouping (contiguous bear runs, gaps > 5 trading days start a new episode) and
     the episode-clustered t - the honest unit of independence here
  3. JACKKNIFE: drop the best 1 / 2 / 3 days, and drop the best EPISODE entirely
  4. Live-comparable variant: the same config at the LIVE spread cap (<=2.0)
  5. The current live setting as a baseline for the same days
Output: reports/research/winner_stress_2026-08-23.md
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


def closes(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-22&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                b = (json.loads(r.read()).get("bars") or {}).get(s) or []
            return {x["t"][:10]: x["c"] for x in b}
        except Exception:
            time.sleep(3)
    return {}


def smad(c, n=20):
    d = sorted(c); o = {}; buf = []
    for x in d:
        buf.append(c[x]); o[x] = (c[x] / (sum(buf[-n:]) / min(len(buf), n)) - 1) * 100
    return o


def replay(path, e, stop, trig, give):
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
    return (path[-1] / e - 1) * 100


def tstat(v):
    n = len(v)
    if n < 3:
        return 0.0
    mu = sum(v) / n
    sd = (sum((x - mu) ** 2 for x in v) / (n - 1)) ** 0.5
    return mu / (sd / math.sqrt(n)) if sd > 0 else 0.0


def main():
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")]
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100
    fwd = defaultdict(list)
    for occ, day, bid in con.execute("select option_symbol,day,nbbo_bid from contracts_daily "
                                     "where nbbo_bid is not null and nbbo_bid>0 order by day"):
        fwd[occ].append((day, bid))
    tkset = set(tks)
    trades = []          # (day, ret, spread)
    seen = set()
    for t, occ, day, prem, av, bv, dl, bid, ask in con.execute(
            """select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,delta,
                      nbbo_bid,nbbo_ask from contracts_daily
               where total_premium between 50000 and 1000000 and ask_volume>bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask>0
                 and delta is not null order by day"""):
        if occ in seen or t not in tkset:
            continue
        smd = (sm.get(t) or {}).get(day); sp = spy20.get(day); reg = s50.get(day)
        if smd is None or sp is None or reg is None or reg >= -3.0:
            continue                                   # deep-bear regime only
        side = 1 if occ[-9] == "C" else -1
        if not (smd * side < 0 and sp * side < 0):
            continue                                   # fade shape
        if abs(float(dl)) >= 0.30:
            continue                                   # delta < 0.30
        mid = (bid + ask) / 2.0
        spr = ((ask - bid) / mid * 100) if mid > 0 else 999.0
        if spr > 3.0:
            continue
        p = [b for d, b in fwd.get(occ, []) if d > day][:60]
        if len(p) < 2:
            continue
        seen.add(occ)
        trades.append((day, replay(p, ask, -60.0, 80.0, 0.20), spr))
    per = defaultdict(list)
    for d, r, _ in trades:
        per[d].append(r)
    dm = sorted((d, sum(v) / len(v)) for d, v in per.items())
    days = [d for d, _ in dm]
    vals = [v for _, v in dm]

    # episodes: contiguous bear days, a gap of >5 calendar-days starts a new one
    eps, cur = [], [dm[0]] if dm else []
    for i in range(1, len(dm)):
        gap = (date.fromisoformat(dm[i][0]) - date.fromisoformat(dm[i - 1][0])).days
        if gap > 5:
            eps.append(cur); cur = []
        cur.append(dm[i])
    if cur:
        eps.append(cur)
    ep_means = [sum(v for _, v in e) / len(e) for e in eps]

    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    def drop_top(k):
        keep = [vals[i] for i in range(len(vals)) if i not in set(order[:k])]
        return (sum(keep) / len(keep), tstat(keep)) if keep else (0, 0)

    best_ep = max(range(len(eps)), key=lambda i: ep_means[i]) if eps else None
    wo_ep = [v for i, e in enumerate(eps) if i != best_ep for _, v in e]

    L = ["# Winner stress test - 2026-08-23", "",
         "Config: FADE / deep-bear (SPY < -3% vs 50d) / 50k-1M / spread<=3% / delta<0.30 /",
         "stop -60 / trail trigger 80 / give 20%. Entry at ask, outcomes on bid.", "",
         f"Trades: {len(trades)} across {len(days)} trading days, in {len(eps)} distinct episodes.",
         f"Day-clustered mean {sum(vals)/len(vals):+.1f}%  t {tstat(vals):+.2f}", "",
         "## The honest unit: EPISODES (bear days cluster into corrections; they are not independent)", "",
         f"Episode count: {len(eps)}   episode-mean {sum(ep_means)/len(ep_means):+.1f}%   "
         f"episode-clustered t {tstat(ep_means):+.2f}", ""]
    for i, e in enumerate(eps):
        L.append(f"  episode {i+1}: {e[0][0]} .. {e[-1][0]}  ({len(e)}d)  mean {ep_means[i]:+.1f}%")
    L += ["", "## Concentration - the day ladder (top 8 and bottom 5)", ""]
    for i in order[:8]:
        L.append(f"  {days[i]}  {vals[i]:+.1f}%")
    L.append("  ...")
    for i in order[-5:]:
        L.append(f"  {days[i]}  {vals[i]:+.1f}%")
    L += ["", "## Jackknife", "", "| removed | day-mean | t |", "|---|---|---|"]
    for k in (0, 1, 2, 3, 5):
        m, tt = drop_top(k)
        L.append(f"| top {k} day(s) | {m:+.1f}% | {tt:+.2f} |")
    if wo_ep:
        L.append(f"| the entire best EPISODE ({eps[best_ep][0][0]}..{eps[best_ep][-1][0]}) | "
                 f"{sum(wo_ep)/len(wo_ep):+.1f}% | {tstat(wo_ep):+.2f} |")
    # live spread cap variant
    per2 = defaultdict(list)
    for d, r, s in trades:
        if s <= 2.0:
            per2[d].append(r)
    v2 = [sum(v) / len(v) for _, v in sorted(per2.items())]
    L += ["", "## At the LIVE spread cap (<=2.0) instead of 3.0", "",
          f"days {len(v2)}, day-mean {(sum(v2)/len(v2)) if v2 else 0:+.1f}%, t {tstat(v2):+.2f}", "",
          "## Verdict", "",
          "If the episode-clustered t collapses below ~2, or dropping the best episode kills it,",
          "this is a handful of corrections - size it as a lottery, not an edge."]
    open("reports/research/winner_stress_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()

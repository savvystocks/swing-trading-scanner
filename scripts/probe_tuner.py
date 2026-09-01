"""PROBE TUNER v1 (owner order 2026-09-01: "simulate all different variables for all the
different probes... each strategy doesn't need the same structure... dynamic way for the best
result in each for both the buy and sell side... hover where it finds the sweet spot").

ONE pass over the archive: every qualifying contract-day (prem 50k-1M, aggressor, spr<=2,
print-covered) is replayed ONCE per exit config on its true-trigger hourly path. Then every
strategy x buy-variant x exit-config cell is a cheap in-memory filter. Day-clustered stats,
both-halves, episode-drop (best ISO week removed). Tunes on the ARCHIVE, never on thin live
fills - the live court (virgin days vs control) remains the only judge.

Buy variables: premium band, contract ask band, SPY-20d confirmation, regime, side.
Sell variables: stop x trail-trigger x giveback (8 pre-registered combos).
Output: reports/research/probe_tuner_<date>.md - per-strategy champion vs current config.
Application is MANUAL (Friday window; damped to adjacent cells; max one change per strategy
per 2 weeks). Resume-safe: checkpoints every 4000 contracts.
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
CKPT = "reports/research/probe_tuner_rows.jsonl"

EXITS = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
         (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]


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


def replay_true(bars_today_after, bars_next, e, stop, trig, give):
    peak = -999.0
    on = False
    for (h, l, c) in bars_today_after:
        rh = (h / e - 1) * 100
        if rh >= trig:
            on = True
        peak = max(peak, rh)
    for (h, l, c) in bars_next:
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
    return (bars_next[-1][2] / e - 1) * 100 if bars_next else None


def build_rows():
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    cur = lib.cursor()
    tks = {r[0] for r in src.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    sm = {t: smad(closes_series(t)) for t in tks}
    spyc = closes_series("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100
    prints = {}
    for occ, day, ts in src.execute("select occ, day, min(executed_at) from flow_prints group by occ, day"):
        prints[(occ, day)] = ts

    done = set()
    if os.path.exists(CKPT):
        for line in open(CKPT, encoding="utf-8"):
            try:
                done.add(json.loads(line)["occ"])
            except Exception:
                pass
        print(f"resume: {len(done)} contracts already scored", flush=True)
    out = open(CKPT, "a", encoding="utf-8")
    n = 0
    for t, occ, day, prem, bid, ask in src.execute(
            """select ticker, option_symbol, day, total_premium, nbbo_bid, nbbo_ask
               from contracts_daily
               where total_premium between 50000 and 1000000 and ask_volume > bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
               order by option_symbol"""):
        if occ in done or t not in tks:
            continue
        # done is marked only when a row is WRITTEN (first run marked it here, which discarded
        # any occ whose first-by-symbol day failed a gate - 13.5k rows instead of ~30k)
        smd = (sm.get(t) or {}).get(day); reg = s50.get(day); sp = spy20.get(day)
        if smd is None or reg is None or sp is None:
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0 or (ask - bid) / mid * 100 > 2.0:
            continue
        pts = prints.get((occ, day))
        if not pts:
            continue
        rows_ = cur.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,)).fetchall()
        today_after = [(h, l, c) for ts_, h, l, c in rows_
                       if ts_[:10] == day and ts_[11:19] > pts[11:19]]
        nxt = [(h, l, c) for ts_, h, l, c in rows_ if ts_[:10] > day]
        if len(nxt) < 3:
            continue
        e = today_after[0][2] if today_after else ask
        if e <= 0:
            continue
        done.add(occ)
        rets = []
        for (st, tg, gv) in EXITS:
            r = replay_true(today_after, nxt, e, st, tg, gv)
            rets.append(round(r, 2) if r is not None else None)
        out.write(json.dumps({"occ": occ, "t": t, "day": day, "prem": prem, "ask": ask,
                              "side": "C" if occ[-9] == "C" else "P", "smd": round(smd, 2),
                              "reg": round(reg, 2), "sp": round(sp, 2), "rets": rets}) + "\n")
        n += 1
        if n % 4000 == 0:
            out.flush()
            print(f"scored {n} new contracts", flush=True)
    out.close()
    print(f"row build complete: {n} new", flush=True)


STRATS = {
    "FOLLOW_CALLS": lambda r: r["side"] == "C",
    "CONSENSUS_CALLS": lambda r: r["side"] == "C" and not (r["smd"] < 0 and r["sp"] < 0),
    "BULL_DIP": lambda r: r["side"] == "C" and r["reg"] > 2 and r["smd"] < 0,
    "DIP_CONF_MILD": lambda r: r["side"] == "C" and -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0,
    "DIP_CONVEXITY": lambda r: r["side"] == "C" and r["reg"] < -2,
    "FADE_BEAR": lambda r: r["reg"] < -2 and ((r["smd"] < 0 and r["sp"] < 0) if r["side"] == "C"
                                              else (r["smd"] > 0 and r["sp"] > 0)),
}
BUY_VARIANTS = [
    ("base_cheap", lambda r: 50000 <= r["prem"] <= 400000 and 0.30 <= r["ask"] <= 4.0),
    ("pricey_4_9", lambda r: 50000 <= r["prem"] <= 400000 and 4.0 < r["ask"] <= 9.0),
    ("whale", lambda r: 400000 < r["prem"] <= 1000000),
    ("fullband", lambda r: True),
    ("tight_mid", lambda r: 50000 <= r["prem"] <= 250000 and 0.30 <= r["ask"] <= 4.0),
    ("spyconf", lambda r: 50000 <= r["prem"] <= 400000 and r["sp"] < 0),
]


def stats(rows_list, ei):
    per = defaultdict(list)
    for r in rows_list:
        if r["rets"][ei] is not None:
            per[r["day"]].append(r["rets"][ei])
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 15:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5
    tt = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    wk = defaultdict(list)
    for d, v in sorted(per.items()):
        iso = date.fromisoformat(d).isocalendar()
        wk[f"{iso[0]}-{iso[1]}"].append(sum(v) / len(v))
    wmeans = {k: sum(v) / len(v) for k, v in wk.items()}
    if len(wmeans) >= 3:
        best = max(wmeans, key=wmeans.get)
        rest = [x for k, v in wk.items() if k != best for x in v]
        edrop = round(sum(rest) / len(rest), 1) if rest else None
    else:
        edrop = None
    return {"n": sum(len(v) for v in per.values()), "u": n, "mean": round(mu, 1),
            "t": round(tt, 2), "h1": round(sum(m[:h]) / max(h, 1), 1),
            "h2": round(sum(m[h:]) / max(n - h, 1), 1), "edrop": edrop}


def report():
    rows = []
    for line in open(CKPT, encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    L = [f"# PROBE TUNER - {date.today().isoformat()} ({len(rows)} contract-days, 8 exits each)",
         "", "exit key: (stop/trigger/giveback). PASS needs: n>=150, both halves>0, episode-drop>0.", ""]
    for sname, sfil in STRATS.items():
        srows = [r for r in rows if sfil(r)]
        L.append(f"## {sname} ({len(srows)} qualifying trades)")
        L.append("| buy variant | exit | day-mean | t | days/n | halves | ep-drop | flags |")
        L.append("|---|---|---|---|---|---|---|---|")
        cells = []
        for vname, vfil in BUY_VARIANTS:
            vrows = [r for r in srows if vfil(r)]
            for ei, (st, tg, gv) in enumerate(EXITS):
                s = stats(vrows, ei)
                if not s:
                    continue
                ok = (s["n"] >= 150 and s["h1"] > 0 and s["h2"] > 0
                      and (s["edrop"] is None or s["edrop"] > 0))
                cells.append((s["t"], vname, (st, tg, gv), s, ok))
        cells.sort(key=lambda x: -x[0])
        for tt, vname, ex, s, ok in cells[:10]:
            L.append(f"| {vname} | {ex[0]:.0f}/{ex[1]:.0f}/{ex[2]:.2f} | {s['mean']:+.1f}% | "
                     f"{s['t']:+.2f} | {s['u']}/{s['n']} | {s['h1']:+.0f}/{s['h2']:+.0f} | "
                     f"{s['edrop'] if s['edrop'] is not None else '-'} | {'PASS' if ok else '-'} |")
        champ = next((c for c in cells if c[4]), None)
        if champ:
            L.append(f"CHAMPION: {champ[1]} exit {champ[2]} -> {champ[3]['mean']:+.1f}%/day "
                     f"t{champ[3]['t']:+.2f} (apply via Friday window, damped)")
        else:
            L.append("CHAMPION: none clears the bar - keep current config")
        L.append("")
    fn = f"reports/research/probe_tuner_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("PROBE TUNER COMPLETE", flush=True)


if __name__ == "__main__":
    build_rows()
    report()

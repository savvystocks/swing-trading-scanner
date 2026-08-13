"""HISTORICAL OPTION CORPUS (owner order 2026-08-13 01:40: build it now, report tonight).

Reconstructs a 2-year fade/consensus candidate corpus from FREE Alpaca historical option
bars (probed working back to >=Jun-2024). No UW flow history exists at our tier, so the
trigger is a stated PROXY: a contract-day whose premium turnover (volume x vwap x 100)
lands in the live band ($50-400k; whale 400k-1M). Honest deviations from live, all noted
in the report: proxy trigger (not real sweeps), signal known end-of-day -> entry next
session's first hour, hourly trade-price paths (not 10-min bid quotes), no spread screen ->
a 2% round-trip haircut variant is reported alongside raw.

Stage 1: discover active contracts per ticker-month via generated OCCs + 1Day bars.
Stage 2: screen contract-days into premium bands.
Stage 3: pull 1Hour paths for qualifiers (signal day + 12 trading days).
Stage 4: shape-tag (fade / consensus vs 20d SMA + SPY) and replay live exits + variants.
Checkpointed + resumable; rate-limit aware; fail-soft per batch.
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "reports", "research", "historical_corpus_2026-08-13")
os.makedirs(OUT, exist_ok=True)
CK = os.path.join(OUT, "checkpoint.json")
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}
TICKERS = ["SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL",
           "AMD", "SLV", "GLD", "TLT", "COIN", "PLTR", "NFLX", "MU", "INTC", "BA"]
START, END = date(2024, 9, 1), date(2026, 8, 1)


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20 * (i + 1))
                continue
            if e.code in (404, 422):
                return {}
            time.sleep(3)
        except Exception:
            time.sleep(3)
    return {}


def strike_step(px):
    return 0.5 if px < 25 else (1.0 if px < 100 else (5.0 if px < 500 else 10.0))


def occ(t, exp, cp, k):
    return f"{t}{exp.strftime('%y%m%d')}{cp}{int(round(k * 1000)):08d}"


def daily_closes():
    """Spot + sma20 per ticker per day from Alpaca stock bars (free, no yfinance rate pain)."""
    path = os.path.join(OUT, "equity.json")
    if os.path.exists(path):
        return json.load(open(path))
    out = {}
    for t in TICKERS:
        url = ("https://data.alpaca.markets/v2/stocks/bars?symbols=" + t +
               "&timeframe=1Day&start=2024-06-01&end=2026-08-12&limit=10000&adjustment=split&feed=iex")
        bars = (get(url).get("bars") or {}).get(t) or []
        ser = [(b["t"][:10], b["c"]) for b in bars]
        m = {}
        closes = []
        for d, c in ser:
            closes.append(c)
            sma = sum(closes[-20:]) / min(len(closes), 20)
            m[d] = {"c": c, "sma_dist": round((c / sma - 1) * 100, 3)}
        out[t] = m
        print(f"equity {t}: {len(m)} days", flush=True)
    json.dump(out, open(path, "w"))
    return out


def month_starts():
    d, out = START, []
    while d < END:
        out.append(d)
        d = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
    return out


def main():
    ck = json.load(open(CK)) if os.path.exists(CK) else {"done_months": [], "cands": []}
    eq = daily_closes()
    spy = eq["SPY"]
    for ms in month_starts():
        key = ms.isoformat()[:7]
        if key in ck["done_months"]:
            continue
        me = (ms.replace(day=1) + timedelta(days=32)).replace(day=1)
        for t in TICKERS:
            days = sorted(d for d in eq[t] if ms.isoformat() <= d < me.isoformat())
            if not days:
                continue
            spot = eq[t][days[0]]["c"]
            step = strike_step(spot)
            ks = [round(spot * (1 + p / 100) / step) * step for p in range(-8, 9)]
            ks = sorted({round(k, 1) for k in ks if k > 0})
            exps = []
            d = ms
            while d < me + timedelta(days=45):
                if d.weekday() == 4 and (d - ms).days >= 3:
                    exps.append(d)
                d += timedelta(days=1)
            occs = [occ(t, e, cp, k) for e in exps[:6] for cp in "CP" for k in ks]
            for i in range(0, len(occs), 90):
                syms = ",".join(occs[i:i + 90])
                url = ("https://data.alpaca.markets/v1beta1/options/bars?symbols=" + syms +
                       f"&timeframe=1Day&start={ms}&end={me}&limit=10000")
                bars = get(url).get("bars") or {}
                for sym, bl in bars.items():
                    for b in bl:
                        prem = (b.get("v") or 0) * (b.get("vw") or b.get("c") or 0) * 100
                        if 50000 <= prem <= 1000000:
                            dd = b["t"][:10]
                            sd = (eq[t].get(dd) or {}).get("sma_dist")
                            sp = (spy.get(dd) or {}).get("sma_dist")
                            if sd is None or sp is None:
                                continue
                            side = 1 if sym[len(t):][6] == "C" else -1
                            shape = ("fade" if (sd * side < 0 and sp * side < 0) else
                                     ("consensus" if (sd * side > 0 and sp * side > 0) else "mixed"))
                            ck["cands"].append({"occ": sym, "t": t, "day": dd, "prem": round(prem),
                                                "side": side, "sma": sd, "spy": sp, "shape": shape})
        ck["done_months"].append(key)
        json.dump(ck, open(CK, "w"))
        print(f"month {key}: cumulative candidates {len(ck['cands'])}", flush=True)
    print(f"DISCOVERY DONE: {len(ck['cands'])} candidate contract-days", flush=True)

    # Stage 3+4: paths for fade/consensus candidates (cap for tonight, deterministic sample)
    cands = [c for c in ck["cands"] if c["shape"] in ("fade", "consensus")]
    cands.sort(key=lambda c: (c["day"], c["occ"]))
    if len(cands) > 6000:
        stepn = len(cands) / 6000.0
        cands = [cands[int(i * stepn)] for i in range(6000)]
    allc = sorted(ck["cands"], key=lambda c: (c["day"], c["occ"]))   # owner ask 2026-08-13 02:02:
    if len(allc) > 4000:                                            # EXEC_BASELINE analogue - every
        stepn = len(allc) / 4000.0                                  # shape incl. mixed, evenly
        allc = [allc[int(i * stepn)] for i in range(4000)]          # sampled across the 2 years
    cands = cands + allc
    print(f"path stage: {len(cands)} candidates", flush=True)
    rows = json.load(open(os.path.join(OUT, "rows.json"))) if os.path.exists(os.path.join(OUT, "rows.json")) else []
    seen = {(r["occ"], r["day"]) for r in rows}
    batch = []
    for c in cands:
        if (c["occ"], c["day"]) in seen:
            continue
        batch.append(c)
    for i in range(0, len(batch), 40):
        grp = batch[i:i + 40]
        syms = ",".join(sorted({g["occ"] for g in grp}))
        d0 = min(g["day"] for g in grp)
        d1 = (date.fromisoformat(max(g["day"] for g in grp)) + timedelta(days=18)).isoformat()
        url = ("https://data.alpaca.markets/v1beta1/options/bars?symbols=" + syms +
               f"&timeframe=1Hour&start={d0}&end={d1}&limit=10000")
        bars = get(url).get("bars") or {}
        for g in grp:
            bl = [b for b in (bars.get(g["occ"]) or []) if b["t"][:10] > g["day"]]
            if len(bl) < 3:
                continue
            e = bl[0]["o"]
            if not e or e <= 0.02:
                continue
            path = [(b["t"], b["c"]) for b in bl]
            g2 = dict(g)
            g2["e"] = e
            g2["path"] = path[:90]
            rows.append(g2)
        if (i // 40) % 25 == 0:
            json.dump(rows, open(os.path.join(OUT, "rows.json"), "w"))
            print(f"paths {i}/{len(batch)} -> rows {len(rows)}", flush=True)
    json.dump(rows, open(os.path.join(OUT, "rows.json"), "w"))
    print(f"PATHS DONE: {len(rows)} replayable candidates", flush=True)


if __name__ == "__main__":
    main()

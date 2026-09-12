"""STUDENT SPREAD STUDY (owner order 2026-09-12: "research the spread variant first").

Question: does picker A's edge (EXPRET/ALL/BASE/k3 - the only student picker with holdout
evidence, +49.9%/trade on ~$15 contracts) survive being traded as a DEFINED-RISK CALL SPREAD
whose debit fits the $1,000 per-trade cap?

PRE-REGISTERED RULE (written before any second-leg price was seen):
  - picks: exactly A's walk-forward picks (search window and holdout), reproduced from the
    as-of corpus with the same stream, threshold calibration and weekly cap;
  - a pick whose long ask already fits the cap (<= $10.00) is bought outright, as the seat would;
  - otherwise the seat sells a further-out call on the SAME expiry: the FURTHEST listed strike
    whose net debit (long ask - short bid) still fits the cap. The short's bid is the close of
    the last hourly bar COMPLETED before the entry time (no look-ahead into the entry hour),
    haircut by the long's measured spread fraction; no completed bar that day -> the entry-hour
    bar's open; no bar at all -> that strike is not tradeable; no strike fits -> pick skipped;
  - lots = floor($1,000 / debit), at least 1, at most 10;
  - exit timing is the long leg's BASE rule (stop -50 / trail +50 / giveback 20%, close-
    confirmed), exactly as the corpus label; the spread is unwound at that bar: long at the
    corpus's haircut level, short bought back at that bar's close marked up by the same
    fraction; value clipped to [0, width]; if the short has no bar on the exit day, intrinsic
    value on the underlying's close that day;
  - ONE configuration; the holdout is touched once; nothing is chosen after seeing it.
  Sensitivity rows (NOT pre-registered, reported for shape only): the NEAREST fitting strike.
NO-ARBITRAGE GUARDS (added after the first pass showed stale short-leg prints: a 50-wide
deep-in-the-money spread "cost" $6): a candidate strike is rejected when its debit is below
90% of the spread's intrinsic value at the prior close (a stale print, not a price); a short
leg is bought back at no less than its intrinsic value on the exit day's close. These are
price-sanity bounds, not selection choices. Rows are also shown at ENGINE sizing (lots =
floor($1,000 / cost), no ten-lot cap) because that is what the seat actually does.
SECOND QUESTION (the owner's Thursday order, "trade A's affordable subset", tested cleanly):
A's own stream restricted to candidates whose ask fits the cap (0.30-9.90), three a week,
walk-forward, both windows, with a single-best-trade-removed sensitivity.

Basis caveats: bars are TRADE prices (close-price approximation), not quotes; both legs pay a
spread; mleg fills and early assignment are not modelled; strike lists come from Alpaca's
contract registry (inactive contracts for expired expiries).
"""
import json
import math
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.environ["FEATURE_SET"] = "ASOF"
import numpy as np
import student_formula_sim as sf

H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}
QUAL_PREM, CYCLE_DELAY_MIN = 50000.0, 10
STOP, TRIG, GIVE = -50.0, 50.0, 0.20
CAP = 10.0                      # $1,000 per trade, in per-share dollars
K_PER_WEEK = 3
OUT = f"reports/research/student_spread_{date.today().isoformat()}.md"
CACHE = "reports/research/student_spread_cache.json"


def get(u, tries=4):
    for att in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=45) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(10 * (att + 1)); continue
            return None
        except Exception:
            time.sleep(3)
    return None


def parse_occ(occ):
    m = re.match(r"^([A-Z]+)(\d{6})([CP])(\d{8})$", occ)
    return m.group(1), "20" + m.group(2)[:2] + "-" + m.group(2)[2:4] + "-" + m.group(2)[4:], m.group(3), int(m.group(4)) / 1000.0


_chain = {}


def chain_strikes(tk, exp, side):
    key = (tk, exp, side)
    if key in _chain:
        return _chain[key]
    out = []
    for st in ("inactive", "active"):
        q = urllib.parse.urlencode({"underlying_symbols": tk, "expiration_date": exp,
                                    "type": "call" if side == "C" else "put", "status": st, "limit": 500})
        j = get("https://paper-api.alpaca.markets/v2/options/contracts?" + q)
        for c in (j or {}).get("option_contracts") or []:
            out.append((float(c["strike_price"]), c["symbol"]))
        if out:
            break
        time.sleep(0.2)
    _chain[key] = sorted(set(out))
    return _chain[key]


def bars_for(symbols, start, end):
    out = defaultdict(list)
    for i in range(0, len(symbols), 50):
        token = None
        for _page in range(20):
            q = {"symbols": ",".join(symbols[i:i + 50]), "timeframe": "1Hour", "start": start, "end": end, "limit": 10000}
            if token:
                q["page_token"] = token
            j = get("https://data.alpaca.markets/v1beta1/options/bars?" + urllib.parse.urlencode(q))
            if not j:
                break
            for occ, bs in (j.get("bars") or {}).items():
                for b in bs:
                    out[occ].append((b["t"], b["o"], b["h"], b["l"], b["c"]))
            token = j.get("next_page_token")
            if not token:
                break
            time.sleep(0.3)
        time.sleep(0.25)
    for occ in out:
        out[occ].sort()
    return out


_closes = {}


def underlying_close(tk, day):
    if tk not in _closes:
        u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={tk}&timeframe=1Day&start=2024-05-01"
             f"&end={(date.today() - timedelta(days=1)).isoformat()}&limit=10000&adjustment=split&feed=iex")
        j = get(u) or {}
        _closes[tk] = {x["t"][:10]: x["c"] for x in (j.get("bars") or {}).get(tk) or []}
    c = _closes[tk]
    if day in c:
        return c[day]
    prior = [d for d in c if d <= day]
    return c[max(prior)] if prior else None


def qual_print(src, occ, day):
    c = 0.0
    for ts, prem, bid, ask in src.execute(
            "select executed_at, premium, nbbo_bid, nbbo_ask from flow_prints where occ=? and day=? order by executed_at",
            (occ, day)):
        c += float(prem or 0.0)
        if c >= QUAL_PREM:
            try:
                hh, mm = int(ts[11:13]), int(ts[14:16]) + CYCLE_DELAY_MIN
                hh += mm // 60; mm %= 60
                ts = ts[:11] + f"{hh:02d}:{mm:02d}" + ts[16:]
            except Exception:
                pass
            return ts, bid, ask
    return None


def replay_exit(today_after, nxt, e, sfr):
    """The tuner's replay_true (v3 branch) with the exit bar returned. Bars carry (ts,h,l,c)."""
    def _sell(rp):
        return ((1 + rp / 100.0) * (1 - sfr) - 1) * 100.0
    peak, on = -999.0, False
    for (_ts, h, l, c) in today_after:
        rh = (h / e - 1) * 100
        if rh >= TRIG:
            on = True
        peak = max(peak, rh)
    for (ts, h, l, c) in nxt:
        rh = (h / e - 1) * 100; rl = (l / e - 1) * 100
        if rh >= TRIG:
            on = True
        if on:
            peak = max(peak, rh)
            fl = peak * (1 - GIVE)
            if rl <= fl:
                rc = (c / e - 1) * 100
                return _sell(min(fl, rc)), ts, "trail"
        if rl <= STOP:
            return _sell(min(STOP, rl) if rl < STOP else STOP), ts, "stop"
    return (_sell((nxt[-1][3] / e - 1) * 100), nxt[-1][0], "time") if nxt else (None, None, None)


def stats(rows, label):
    """rows: (day, reg, pct, dollars). Real-dollar weekly t at integer lots."""
    if not rows:
        return None
    pct = np.array([r[2] for r in rows])
    wk = defaultdict(float)
    for d, reg, p, usd in rows:
        wk[sf.week_key(d)] += usd
    w = np.array([wk[x] for x in sorted(wk)])
    t = (w.mean() / (w.std(ddof=1) / math.sqrt(len(w)))) if len(w) > 2 and w.std(ddof=1) > 0 else 0.0
    cum = np.cumsum(w); dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0
    h = len(w) // 2
    regs = defaultdict(list)
    for d, reg, p, usd in rows:
        regs[sf.regime(reg)].append(p)
    rg = {k: (len(v), float(np.mean(v))) for k, v in regs.items()}
    allreg = all(rg.get(k, (0, 0))[0] >= 10 and rg.get(k, (0, 0))[1] > 0 for k in ("BULL", "MILD", "BEAR"))
    return {"label": label, "trades": len(rows), "weeks": len(w), "per_trade": float(pct.mean()),
            "win": float(np.mean(pct > 0)), "wk_mean": float(w.mean()), "wk_t": float(t),
            "pos_weeks": float(np.mean(w > 0)), "h1": float(w[:h].mean()) if h else 0.0,
            "h2": float(w[h:].mean()) if len(w) - h else 0.0, "maxdd": dd, "total": float(w.sum()),
            "regs": rg, "allreg": allreg}


HDR = ("| config | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean | all regimes |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def fmt(e):
    if not e:
        return "| (no trades) |"
    rg = " ".join(f"{k}:{v[0]}/{v[1]:+.0f}" for k, v in sorted(e["regs"].items()))
    return (f"| {e['label']} | {e['trades']} | {e['weeks']} | {e['per_trade']:+.1f} | {e['win']:.0%} | "
            f"{e['wk_mean']:+.0f} | {e['wk_t']:+.2f} | {e['pos_weeks']:.0%} | {e['h1']:+.0f}/{e['h2']:+.0f} | "
            f"{e['maxdd']:.0f} | {e['total']:+.0f} | {rg} | {'YES' if e['allreg'] else 'no'} |")


def price_pick(src, lib, m, cache):
    """One pick -> dict with the long replay and the spread pricing (both rules)."""
    day, side, reg, smd, sp, e, rets, occ = m
    key = f"{occ}|{day}"
    if key in cache:
        return cache[key]
    res = {"occ": occ, "day": day, "reg": reg, "e": e, "long_ret": rets[0], "status": "ok"}
    tk, exp, cp, K = parse_occ(occ)
    res.update({"tk": tk, "exp": exp, "K": K})
    pr = qual_print(src, occ, day)
    if not pr:
        res["status"] = "no_print"; cache[key] = res; return res
    pts, pbid, pask = pr
    sfr = max(0.0, min(0.05, (pask - pbid) / pask)) if pbid and pask and pask > 0 and pbid > 0 else 0.0
    res["sf"] = round(sfr, 4); res["pts"] = pts
    rows_ = lib.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,)).fetchall()
    today_after = [(ts_, h, l, c) for ts_, h, l, c in rows_ if ts_[:10] == day and ts_[11:19] > pts[11:19]]
    nxt = [(ts_, h, l, c) for ts_, h, l, c in rows_ if ts_[:10] > day]
    if len(nxt) < 3:
        res["status"] = "no_path"; cache[key] = res; return res
    r_long, exit_ts, kind = replay_exit(today_after[1:], nxt, e, sfr)
    res.update({"replay_ret": None if r_long is None else round(r_long, 2), "exit_ts": exit_ts, "exit_kind": kind})
    if r_long is None:
        res["status"] = "no_exit"; cache[key] = res; return res
    if e <= CAP:
        res["status"] = "affordable"; cache[key] = res; return res
    strikes = [(k2, sym) for k2, sym in chain_strikes(tk, exp, cp) if k2 > K and k2 <= K * 1.6]
    if not strikes:
        res["status"] = "no_chain"; cache[key] = res; return res
    syms = [s for _, s in strikes]
    exit_day = exit_ts[:10]
    bars = bars_for(syms, day, (date.fromisoformat(exit_day) + timedelta(days=1)).isoformat())
    s_prev = underlying_close(tk, (date.fromisoformat(day) - timedelta(days=1)).isoformat())
    s_exit_u = underlying_close(tk, exit_day)
    res["s_prev"] = s_prev; res["s_exit_u"] = s_exit_u
    stale = 0
    cands = []
    for k2, sym in strikes:
        bs = bars.get(sym) or []
        before = [b for b in bs if b[0][:10] == day and b[0][11:19] < pts[11:16] + ":00" and b[0][:13] != pts[:13]]
        px = None
        if before:
            px = before[-1][4]                       # last COMPLETED bar before the entry hour: close
        else:
            same = [b for b in bs if b[0][:13] == pts[:13]]
            if same:
                px = same[0][1]                      # entry-hour bar: its open
        if not px or px <= 0:
            continue
        credit = px * (1 - sfr)
        debit = e - credit
        width = k2 - K
        if credit <= 0 or debit <= 0 or debit > CAP:
            continue
        if s_prev is not None and debit < 0.9 * min(max(s_prev - K, 0.0), width):
            stale += 1                               # a debit below intrinsic is a stale print
            continue
        # exit side
        at_exit = [b for b in bs if b[0] == exit_ts]
        if at_exit:
            s_exit = at_exit[0][4] * (1 + sfr); how = "bar"
        else:
            same_day = [b for b in bs if b[0][:10] == exit_day and b[0] <= exit_ts]
            if same_day:
                s_exit = same_day[-1][4] * (1 + sfr); how = "bar_prior"
            else:
                s_exit = max(0.0, s_exit_u - k2) if s_exit_u is not None else None; how = "intrinsic"
        if s_exit is None:
            continue
        if s_exit_u is not None and s_exit < max(0.0, s_exit_u - k2):
            s_exit = max(0.0, s_exit_u - k2); how += "+intrinsic_floor"
        l_exit = e * (1 + r_long / 100.0)
        v = min(max(l_exit - s_exit, 0.0), width)
        lots = max(1, min(10, int(CAP // debit)))
        lots_eng = max(1, int(CAP // debit))
        cands.append({"k2": k2, "width": round(width, 2), "credit": round(credit, 3), "debit": round(debit, 3),
                      "lots": lots, "s_exit": round(s_exit, 3), "exit_how": how,
                      "pct": round((v - debit) / debit * 100.0, 2), "usd": round(lots * (v - debit) * 100.0, 2),
                      "usd_eng": round(lots_eng * (v - debit) * 100.0, 2)})
    res["stale_rejected"] = stale
    if not cands:
        res["status"] = "no_fit"; cache[key] = res; return res
    cands.sort(key=lambda c: c["k2"])
    res["furthest"] = cands[-1]
    res["nearest"] = cands[0]
    res["n_fit"] = len(cands)
    cache[key] = res
    return res


def main():
    X, meta = sf.load_asof()
    days = [m[0] for m in meta]
    search = np.array([d < sf.SEARCH_END for d in days]); hold = ~search
    rets0 = np.array([m[6][0] if m[6][0] is not None else np.nan for m in meta])
    ok = ~np.isnan(rets0)
    y_cls = (rets0 > 0).astype(int); y_big = (rets0 >= 30).astype(int)
    y_reg = np.clip(np.nan_to_num(rets0, nan=0.0), -100, 300)
    cm = sf.cohort_mask(meta, "ALL") & ok
    print("fitting A's stream (EXPRET/ALL, quarterly refits) ...", flush=True)
    stream = sf.fit_stream(X, y_cls, y_big, y_reg, days, "EXPRET", cm)
    sc = stream.copy(); sc[~search] = np.nan
    picks_s = sf.pick_weekly(sc, days, cm, K_PER_WEEK)
    sc = stream.copy(); sc[search] = np.nan
    picks_h = sf.pick_weekly(sc, days, cm, K_PER_WEEK)
    es = sf.evaluate(picks_s, meta, 0, "A LONG $1,000 notional (report basis) - search")
    eh = sf.evaluate(picks_h, meta, 0, "A LONG $1,000 notional (report basis) - HOLDOUT")
    print(f"reproduced: search {es['trades']} trades {es['per_trade']:+.1f}%/trade t {es['wk_t']:+.2f} | "
          f"holdout {eh['trades']} trades {eh['per_trade']:+.1f}%/trade t {eh['wk_t']:+.2f}", flush=True)
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    priced = {}
    allp = [("search", i) for i in picks_s] + [("holdout", i) for i in picks_h]
    for n, (win, i) in enumerate(allp):
        priced[i] = price_pick(src, lib, meta[i], cache)
        if n % 10 == 0:
            json.dump(cache, open(CACHE, "w", encoding="utf-8"))
            print(f"  priced {n + 1}/{len(allp)}", flush=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"))
    L = [f"# STUDENT SPREAD STUDY - {date.today().isoformat()}", "",
         "Picker A (EXPRET/ALL/BASE/k3) traded under the $1,000 cap as a defined-risk call spread: the FURTHEST "
         "listed strike on the same expiry whose net debit fits the cap (pre-registered; see the script header). "
         "Affordable picks (ask <= $10) are bought outright. Exit timing = the long leg's BASE rule. Real-dollar "
         "weekly t at integer lots.", ""]
    # SECOND QUESTION: A's stream restricted to cap-fitting candidates (0.30-9.90), 3/week
    cap_mask = cm & np.array([0.30 <= m[5] <= 9.90 for m in meta])
    sc = stream.copy(); sc[~search] = np.nan
    picks_cs = sf.pick_weekly(sc, days, cap_mask, K_PER_WEEK)
    sc = stream.copy(); sc[search] = np.nan
    picks_ch = sf.pick_weekly(sc, days, cap_mask, K_PER_WEEK)

    def eng_rows(picks):
        out = []
        for i in picks:
            m = meta[i]; e = m[5]; lr = (m[6][0] or 0.0)
            out.append((m[0], m[2], lr, max(1, int(CAP // e)) * lr / 100.0 * e * 100.0))
        return out

    def drop_best(rows):
        if len(rows) < 2:
            return rows
        b = max(range(len(rows)), key=lambda j: rows[j][3])
        return [r for j, r in enumerate(rows) if j != b]

    for win, picks, base_e, picks_cap in (("search", picks_s, es, picks_cs), ("HOLDOUT", picks_h, eh, picks_ch)):
        L += [f"## {win} window", "", HDR, fmt(base_e)]
        one = []; caprule = []; caprule_eng = []; capnear = []; spread_all = []; spread_near_all = []; aff_only = []
        counts = defaultdict(int); mism = 0; big_long = []; big_spread = []; stale_n = 0
        for i in picks:
            r = priced[i]; m = meta[i]; day, reg, e, lr = m[0], m[2], m[5], (m[6][0] or 0.0)
            counts[r["status"]] += 1
            stale_n += r.get("stale_rejected", 0)
            one.append((day, reg, lr, lr / 100.0 * e * 100.0))
            if r.get("replay_ret") is not None and abs(r["replay_ret"] - lr) > 0.05:
                mism += 1
            if r["status"] == "affordable":
                lots = max(1, min(10, int(CAP // e)))
                usd = lots * lr / 100.0 * e * 100.0
                usd_eng = max(1, int(CAP // e)) * lr / 100.0 * e * 100.0
                caprule.append((day, reg, lr, usd)); caprule_eng.append((day, reg, lr, usd_eng))
                capnear.append((day, reg, lr, usd)); aff_only.append((day, reg, lr, usd_eng))
            elif r["status"] == "ok":
                f, nr = r["furthest"], r["nearest"]
                caprule.append((day, reg, f["pct"], f["usd"])); caprule_eng.append((day, reg, f["pct"], f["usd_eng"]))
                capnear.append((day, reg, nr["pct"], nr["usd"]))
                spread_all.append((day, reg, f["pct"], f["usd"]))
                spread_near_all.append((day, reg, nr["pct"], nr["usd"]))
                if lr >= 100:
                    big_long.append(lr); big_spread.append(f["pct"])
        L.append(fmt(stats(one, "A LONG one contract at real cost (what a $1,600 seat does)")))
        L.append(fmt(stats(caprule, "CAP RULE: long if <= $10 else spread FURTHEST fit (pre-registered, <=10 lots)")))
        L.append(fmt(stats(caprule_eng, "  same, ENGINE sizing (lots = floor($1,000/cost))")))
        L.append(fmt(stats(drop_best(caprule_eng), "  same, engine sizing, single best trade removed")))
        L.append(fmt(stats(aff_only, "  affordable longs only (A's picks with ask <= $10), engine sizing")))
        L.append(fmt(stats(spread_all, "  spread legs only, FURTHEST fit")))
        L.append(fmt(stats(capnear, "  sensitivity: NEAREST fitting strike (not pre-registered)")))
        L.append(fmt(stats(spread_near_all, "  spread legs only, NEAREST fit")))
        cap_rows = eng_rows(picks_cap)
        L.append(fmt(stats(cap_rows, "A RESTRICTED to cap-fitting candidates (0.30-9.90), 3/week, engine sizing")))
        L.append(fmt(stats(drop_best(cap_rows), "  same, single best trade removed")))
        st = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        L += ["", f"pick outcomes: {st}; stale short-leg prints rejected: {stale_n}; replay mismatches vs corpus label: {mism}"]
        if big_long:
            L.append(f"capture on the long's big winners (>= +100%, n={len(big_long)}): long mean {np.mean(big_long):+.0f}% -> "
                     f"spread mean {np.mean(big_spread):+.0f}%")
        sp_pcts = [r[2] for r in spread_all]
        if sp_pcts:
            lo = [priced[i]["long_ret"] for i in picks if priced[i]["status"] == "ok"]
            L.append(f"same-trade comparison (spread-priced picks only, n={len(sp_pcts)}): long {np.mean(lo):+.1f}%/trade -> "
                     f"spread {np.mean(sp_pcts):+.1f}%/trade; median width {np.median([priced[i]['furthest']['width'] for i in picks if priced[i]['status']=='ok']):.1f}, "
                     f"median debit ${np.median([priced[i]['furthest']['debit'] for i in picks if priced[i]['status']=='ok'])*100:.0f}")
        L.append("")
    L += ["## Holdout picks, one per line", "",
          "| day | occ | ask | K | K2 | width | credit | debit | lots | long % | spread % | exit | short exit px |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i in picks_h:
        r = priced[i]
        if r["status"] == "ok":
            f = r["furthest"]
            L.append(f"| {r['day']} | {r['occ']} | {r['e']:.2f} | {r['K']} | {f['k2']} | {f['width']} | {f['credit']:.2f} | "
                     f"{f['debit']:.2f} | {f['lots']} | {r['long_ret']:+.1f} | {f['pct']:+.1f} | {r.get('exit_kind')} | {f['s_exit']:.2f} ({f['exit_how']}) |")
        else:
            L.append(f"| {r['day']} | {r['occ']} | {r['e']:.2f} | {r['K']} | - | - | - | - | - | {r['long_ret']:+.1f} | - | {r.get('exit_kind')} | {r['status']} |")
    L += ["", "## Six checks", "",
          "1. Edge: none new - the same picks; only the instrument changes.",
          "2. Fat tail: a spread caps the right tail that pays A's book; the 'big winners' line above measures how much is lost.",
          "3. Frictions: two legs, two spreads (haircut applied both ways); mleg fill quality and early assignment not modelled; bars are trade prices.",
          "4. Data honesty: one pre-registered rule, holdout touched once; the short strike is chosen on prices completed BEFORE the entry hour; the sensitivity row is labelled and not evidence.",
          "5. Dead weight: none added; the script is research-only.",
          "6. Unknowns: strike lists from Alpaca's registry; a strike with no bar before entry is treated as untradeable, which biases toward liquid strikes; intrinsic settlement when the short has no exit-day bar.",
          "7. Stale prints: trade bars on illiquid deep-in-the-money strikes lag the market; the intrinsic-value bounds above reject them at entry and floor them at exit. A live seat would see NBBO quotes instead; this study cannot.",
          "", "Verdict rule (written before running): the spread variant is worth a seat design only if the HOLDOUT cap-rule row keeps a positive weekly t, positive halves and a per-trade mean above the pool; otherwise the cap and the edge do not fit together and the two remaining options stand. The SEARCH-window row is reported for consistency: a rule that passes only on the holdout while losing on the window the picker was chosen on is fragile, whatever the holdout says."]
    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print(f"\nwritten {OUT}", flush=True)


if __name__ == "__main__":
    main()

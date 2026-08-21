"""SHADOW LAB (owner order 2026-08-10: "run hypotheticals and study them").

Seven hypothesis books replay each day's harvested fade-cohort candidates at executable prices.
None of them trades. Each is a pre-registered hypothesis with the same promotion machinery as
everything else: day-clustered evidence on virgin days, counted trials, Sunday review.

BOOKS:
  BASELINE   - the live spec (fade shape, band 50-250k, spread<=2)     [the yardstick]
  INVERSE    - consensus-following, same band/spread                    [CONTROL ARM: if this
               beats BASELINE, the fade direction is wrong; if both lose equally, the 'edge'
               is friction-illusion]
  PUTS_ONLY / CALLS_ONLY - the side split, live                         [in-sample: puts +14%]
  V13_DEPTH  - depth<2% filter (HELD by the 08-09 check; rehab watch)
  BAND_WIDE  - flow band 40-300k                                        [robustness variant]
  RED_DAY / GREEN_DAY tag - every book's P&L is also tagged by the day's SPY sign
               [regime conditioning: which days pay]
Output: one JSON line per day per book -> reports/shadow_lab/ledger.jsonl (committed).
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
OUT = os.path.join(REPO, "reports", "shadow_lab")
os.makedirs(OUT, exist_ok=True)


def replay(pts, e, stop=-50, trig=50, give=0.20):
    peak, on = -999.0, False
    for _, b in pts:
        r = (b / e - 1) * 100
        if r >= trig:
            on = True
        if on:
            peak = max(peak, r)
            if r <= peak * (1 - give):
                return r
        if r <= stop:
            return stop
    return (pts[-1][1] / e - 1) * 100


def run_day(db, day_iso):
    d0 = (date.fromisoformat(day_iso) - date(1970, 1, 1)).days
    lo, hi = d0 * 86400000, (d0 + 1) * 86400000
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
    rows = con.execute(
        """select c.candidate_id, c.entry_ref, c.right, c.spread_pct, c.rule_score, c.features,
                  c.strike, c.underlying_last
           from candidates c join labels l on l.candidate_id=c.candidate_id
           where c.signal_ts_utc >= ? and c.signal_ts_utc < ? and l.outcome is not null
             and c.entry_ref > 0 and c.features != ''""", (lo, hi)).fetchall()
    if not rows:
        print(f"{day_iso}: no labeled rows readable (poller lock?) - NOT writing a null line")
        return {"day": day_iso, "skipped": "empty-read"}
    meta = {}
    spy_signs = []
    for cid, e, right, spr, score, fj, _K, _S in rows:
        try:
            f = json.loads(fj)
        except Exception:
            continue
        sma = (f.get("macro") or {}).get("distance_to_sma20_pct")
        spy = (f.get("regime_stack") or {}).get("market_spy_dist_pct")
        if not isinstance(sma, (int, float)) or not isinstance(spy, (int, float)):
            continue
        side = 1 if right == "call" else -1
        spy_signs.append(spy)
        dp = (f.get("dark_pool") or {}).get("n_prints") or 0
        mny = ((_K / _S - 1) * 100 * (1 if right == "call" else -1)) if (_K and _S) else None
        hr = (f.get("macro_context") or {}).get("execution_hour")
        meta[cid] = {"e": e, "side": side, "sma": sma, "spy": spy, "spr": spr or 99,
                     "score": score or 0, "right": right, "dp": dp, "mny": mny, "hr": hr}
    paths = defaultdict(list)
    for cid, ts, bid in con.execute(
            "select candidate_id, poll_ts_utc, bid from bid_path where bid is not null and stale is not 1"):
        if cid in meta:
            paths[cid].append((ts, bid))
    res = {}
    for cid, pts in paths.items():
        if len(pts) >= 3:
            pts.sort()
            res[cid] = replay(pts, meta[cid]["e"])

    def sel(pred):
        vals = [res[c] for c in res if pred(meta[c])]
        return {"n": len(vals), "mean": round(sum(vals) / len(vals), 2) if vals else None}

    fade = lambda m: m["sma"] * m["side"] < 0 and m["spy"] * m["side"] < 0
    tight = lambda m: m["spr"] <= 2.0
    band = lambda m, lo=50000, hi=250000: lo <= m["score"] <= hi
    books = {
        "BASELINE": lambda m: fade(m) and tight(m) and band(m),
        "INVERSE_CONTROL": lambda m: m["sma"] * m["side"] > 0 and m["spy"] * m["side"] > 0 and tight(m) and band(m),
        "PUTS_ONLY": lambda m: fade(m) and tight(m) and band(m) and m["right"] == "put",
        "CALLS_ONLY": lambda m: fade(m) and tight(m) and band(m) and m["right"] == "call",
        "V13_DEPTH": lambda m: fade(m) and tight(m) and band(m) and abs(m["sma"]) < 2.0,
        "BAND_WIDE": lambda m: fade(m) and tight(m) and band(m, 40000, 300000),
        "SHAPE_NO_SPREAD": lambda m: fade(m) and band(m),
        # MILD hypothesis (registered 2026-08-10 after day-1 lab output: fade -16.3 vs control
        # -4.1 on a strong-green day; depth finding says shallow beats deep): fade only GENTLE
        # disagreement - both the ticker's and the market's displacement small.
        # OPT_WINNER (25,920-config joint sweep 2026-08-10: top worst-half stability +8.4/+11.0;
        # in-sample argmax - must earn promotion on virgin days like everything else)
        "OPT_WINNER": lambda m: fade(m) and m["spr"] <= 2.0 and band(m) and abs(m["spy"]) < 1.5 and abs(m["sma"]) < 3.0,
        "BAND_50_400": lambda m: fade(m) and tight(m) and band(m, 50000, 400000),
        # LIVE_SPEC (registered 2026-08-12): exact replica of the live book's gates - the honest
        # comparator for hypotheses that differ from it by exactly one key (router, band ceiling).
        "LIVE_SPEC": lambda m: fade(m) and tight(m) and band(m, 50000, 400000) and abs(m["spy"]) < 1.5,
        # TIME-OF-DAY buckets (registered 2026-08-12, owner: "what are we missing" - entry hour
        # was never tested; path signatures say the first 2h decide destiny, so WHEN we enter
        # may matter as much as what). LIVE_SPEC gates + UTC execution-hour windows.
        # SOFT_ROUTER (registered 2026-08-12: the router is binary at 1.5 - test the middle
        # rung. Owner: "what can we do to make the fade system better")
        "SOFT_ROUTER": lambda m: fade(m) and tight(m) and band(m, 50000, 400000) and abs(m["spy"]) < 2.5,
        # TREND_CONSENSUS (registered 2026-08-12): the trend-day counterpart candidate - flow
        # agreeing with both trends, ONLY on the days the fade router stands down. If this
        # earns, the router becomes a junction (mild->fade, trend->consensus), not a stop.
        "TREND_CONSENSUS": lambda m: (m["sma"] * m["side"] > 0 and m["spy"] * m["side"] > 0
                                      and tight(m) and band(m, 50000, 400000) and abs(m["spy"]) >= 1.5),
        "TOD_OPEN": lambda m: (fade(m) and tight(m) and band(m, 50000, 400000)
                               and abs(m["spy"]) < 1.5 and isinstance(m.get("hr"), (int, float)) and m["hr"] <= 14),
        "TOD_MID": lambda m: (fade(m) and tight(m) and band(m, 50000, 400000)
                              and abs(m["spy"]) < 1.5 and isinstance(m.get("hr"), (int, float)) and 15 <= m["hr"] <= 17),
        "TOD_LATE": lambda m: (fade(m) and tight(m) and band(m, 50000, 400000)
                               and abs(m["spy"]) < 1.5 and isinstance(m.get("hr"), (int, float)) and m["hr"] >= 18),
        # FADE_WHALE (registered 2026-08-12 after owner band question: stored-cohort replay put
        # fade-shaped 400k-1M at +3.37 day-mean vs -0.47 in-band, halves flipped - unproven)
        "FADE_WHALE": lambda m: fade(m) and tight(m) and 400000 < m["score"] <= 1000000,
        "SPR_25_MILD": lambda m: fade(m) and m["spr"] <= 2.5 and band(m, 50000, 400000) and abs(m["spy"]) < 1.5,
        # FADE_DP (registered 2026-08-11: dark-pool density was the pile's strongest measured
        # conditioner - 40.9% vs 19.3% win. Does it lift the fade cohort on virgin days?)
        # FADE_ATM (registered 2026-08-11 round-2 mine: ATM/ITM carries the cohort +4.5 stable
        # while OTM runs flat - matches Hu JFE 2014: informative flow is ATM/ITM, never lottery OTM)
        "FADE_ATM": lambda m: fade(m) and tight(m) and band(m, 50000, 400000) and m.get("mny") is not None and m["mny"] < 1.0,
        "FADE_DP": lambda m: fade(m) and tight(m) and band(m, 50000, 400000) and m["dp"] >= 150,
        "MILD_ONLY": lambda m: fade(m) and tight(m) and band(m) and abs(m["sma"]) < 2.0 and abs(m["spy"]) < 1.5,
        # PLACEBO arm (owner science-hardening 2026-08-18): picks pseudo-randomly by candidate-id
        # hash - NO market logic. If the promotion machinery ever passes THIS book, the lab is
        # hallucinating edges and every other verdict is suspect. Expected: ~0 mean forever.
        "PLACEBO_RANDOM": lambda m: (hash(str(m.get("e")) + str(m.get("score"))) % 7) == 0,
    }
    # EARLY_CUT book (path-signature rule mined 2026-08-11): baseline entries, but cut at
    # <= -15% once >= 2h held. Second replay pass with the cut.
    res_cut = {}
    for cid, pts in paths.items():
        if len(pts) < 3:
            continue
        e = meta[cid]["e"]; t0 = pts[0][0]; peak = -999.0; on = False; out_r = None
        for ts, b in pts:
            r = (b / e - 1) * 100
            if (ts - t0) >= 2 * 3600000 and r <= -15:
                out_r = r; break
            if r >= 50:
                on = True
            if on:
                peak = max(peak, r)
                if r <= peak * 0.8:
                    out_r = r; break
            if r <= -50:
                out_r = -50; break
        res_cut[cid] = out_r if out_r is not None else (pts[-1][1] / e - 1) * 100
    _bl = [res_cut[c] for c in res_cut if books["BASELINE"](meta[c])]
    day_spy = round(sum(spy_signs) / len(spy_signs), 3) if spy_signs else None
    out = {"day": day_iso, "computed_at": datetime.now(timezone.utc).isoformat()[:16],
           "spy_mean_dist": day_spy, "day_type": "RED" if (day_spy or 0) < 0 else "GREEN",
           "labeled": len(res)}
    for name, pred in books.items():
        out[name] = sel(pred)
    out["EARLY_CUT"] = {"n": len(_bl), "mean": round(sum(_bl) / len(_bl), 2) if _bl else None}
    # CHALLENGER PROTOCOL (owner design 2026-08-21): CHAMPION mirrors the LIVE spec nightly;
    # challengers (challengers.json) are one-dial neighbors replayed on the same cohort.
    try:
        _spec = json.load(open("fade_book_spec.json"))
        _e = _spec.get("entry") or {}
        _x = _spec.get("exit") or {}
        _td = _x.get("trail_drawdown", 20)
        _cp = {"band_lo": _e.get("flow_min", 50000), "band_hi": _e.get("flow_max", 400000),
               "spr_max": _e.get("max_spread_pct", 2.0), "spy_max": _e.get("max_spy_dist_pct", 99),
               "stop": _x.get("stop", -50), "trig": _x.get("trail_activate", 50),
               "give": _td / 100.0 if _td > 1 else _td}

        def _cfilter(p):
            return lambda m: (fade(m) and m["spr"] <= p.get("spr_max", _cp["spr_max"])
                              and p.get("band_lo", _cp["band_lo"]) <= m["score"] <= p.get("band_hi", _cp["band_hi"])
                              and abs(m["spy"]) < p.get("spy_max", _cp["spy_max"]))

        def _ceval(p):
            _f = _cfilter(p)
            _cids = [c for c in res if _f(meta[c])]
            _st = p.get("stop", _cp["stop"]); _tg = p.get("trig", _cp["trig"]); _gv = p.get("give", _cp["give"])
            if (_st, _tg, _gv) == (_cp["stop"], _cp["trig"], _cp["give"]):
                _vals = [res[c] for c in _cids]
            else:
                _vals = [replay(paths[c], meta[c]["e"], stop=_st, trig=_tg, give=_gv) for c in _cids]
            return {"n": len(_vals), "mean": round(sum(_vals) / len(_vals), 2) if _vals else None}

        out["CHAMPION"] = _ceval({})
        if os.path.exists("challengers.json"):
            for _nm, _p in (json.load(open("challengers.json")).get("books") or {}).items():
                out[_nm] = _ceval(_p)
    except Exception as _ce:
        print(f"challenger eval skipped: {type(_ce).__name__}")
    # PLACEBO ARMY (lab v2.1, owner order 2026-08-19 01:36): 200 hash-seeded random books from
    # the same day's real candidates - the empirical null the boundary judges every pass against.
    _army = []
    for _p in range(200):
        _v = [res[c] for c in res if hash(f"{_p}:{c}") % 5 == 0]
        _army.append(round(sum(_v) / len(_v), 2) if _v else None)
    out["PL"] = _army
    # EXIT VARIANTS (registered 2026-08-12, owner: exploration was entry-only). LIVE_SPEC
    # cohort, five alternative exit rules replayed on the same stored bid paths. EXIT_STOP40
    # maps to the live exit.stop key (auto-promotable); the others are measurement until one
    # earns a code session.
    _live_cids = [c for c in res if books["LIVE_SPEC"](meta[c])]

    def _trunc_tp(pts, e, cap=80):
        cut = []
        for ts, b in pts:
            cut.append((ts, b))
            if (b / e - 1) * 100 >= cap:
                break
        return cut

    def _trunc_time(pts, hours=48):
        t0 = pts[0][0]
        return [(ts, b) for ts, b in pts if (ts - t0) <= hours * 3600000] or pts[:1]

    _variants = {
        "EXIT_STOP40": lambda pts, e: replay(pts, e, stop=-40),
        "EXIT_TIGHT_TRAIL": lambda pts, e: replay(pts, e, give=0.10),
        "EXIT_TRAIL30": lambda pts, e: replay(pts, e, trig=30),
        "EXIT_TP80": lambda pts, e: replay(_trunc_tp(pts, e), e),
        "EXIT_TIME48": lambda pts, e: replay(_trunc_time(pts), e),
    }
    for _vn, _vf in _variants.items():
        _vals = [_vf(paths[c], meta[c]["e"]) for c in _live_cids if len(paths.get(c) or []) >= 3]
        out[_vn] = {"n": len(_vals), "mean": round(sum(_vals) / len(_vals), 2) if _vals else None}
    with open(os.path.join(OUT, "ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    return out


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "data/harvest.db"
    day = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()
    r = run_day(db, day)
    print(json.dumps(r, indent=1))

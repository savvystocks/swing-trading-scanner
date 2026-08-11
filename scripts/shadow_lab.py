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
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        """select c.candidate_id, c.entry_ref, c.right, c.spread_pct, c.rule_score, c.features,
                  c.strike, c.underlying_last
           from candidates c join labels l on l.candidate_id=c.candidate_id
           where c.signal_ts_utc >= ? and c.signal_ts_utc < ? and l.outcome is not null
             and c.entry_ref > 0 and c.features != ''""", (lo, hi)).fetchall()
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
        meta[cid] = {"e": e, "side": side, "sma": sma, "spy": spy, "spr": spr or 99,
                     "score": score or 0, "right": right, "dp": dp, "mny": mny}
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
    with open(os.path.join(OUT, "ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    return out


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "data/harvest.db"
    day = sys.argv[2] if len(sys.argv) > 2 else date.today().isoformat()
    r = run_day(db, day)
    print(json.dumps(r, indent=1))

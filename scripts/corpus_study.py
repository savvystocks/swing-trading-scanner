"""HISTORICAL CORPUS STRESS-TEST (companion to historical_corpus.py, 2026-08-13).

Replays the live exit rules (trail 50/20, stop -50) and the exit variants over every
reconstructed candidate, sliced by shape x regime x band x period. Day-clustered stats
everywhere. Reports RAW (trade-price paths) and HAIRCUT (2% round-trip cost) columns.
Output: reports/research/historical_corpus_2026-08-13/STRESS_TEST.md
"""
import json
import math
import os
from collections import defaultdict

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "reports", "research", "historical_corpus_2026-08-13")


def replay(closes, e, stop=-50, trig=50, give=0.20, cap=None, max_bars=None):
    peak, on = -999.0, False
    seq = closes[:max_bars] if max_bars else closes
    for b in seq:
        r = (b / e - 1) * 100
        if cap is not None and r >= cap:
            return r
        if r >= trig:
            on = True
        if on:
            peak = max(peak, r)
            if r <= peak * (1 - give):
                return r
        if r <= stop:
            return stop
    return (seq[-1] / e - 1) * 100


def stats(pts):
    per_day = defaultdict(list)
    for d, r in pts:
        per_day[d].append(r)
    dm = sorted((d, sum(v) / len(v)) for d, v in per_day.items())
    if not dm:
        return None
    means = [m for _, m in dm]
    n = len(means)
    mu = sum(means) / n
    sd = (sum((x - mu) ** 2 for x in means) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    e1 = sum(means[:h]) / max(h, 1)
    e2 = sum(means[h:]) / max(n - h, 1)
    return {"trades": len(pts), "days": n, "day_mean": round(mu, 2), "t": round(t, 2),
            "h1": round(e1, 1), "h2": round(e2, 1)}


def hc(r):
    return ((1 + r / 100) * 0.98 - 1) * 100


def line(name, pts):
    s = stats(pts)
    if not s:
        return f"| {name} | 0 | - | - | - | - |"
    sh = stats([(d, hc(r)) for d, r in pts])
    return (f"| {name} | {s['trades']}/{s['days']}d | {s['day_mean']:+.2f}% (t={s['t']}) "
            f"| {sh['day_mean']:+.2f}% | {s['h1']:+.1f} / {s['h2']:+.1f} |")


def spy_day_color():
    """GREEN/RED per day from SPY close-to-close (equity.json is written by the harvester)."""
    eq = json.load(open(os.path.join(OUT, "equity.json"), encoding="utf-8"))["SPY"]
    days = sorted(eq)
    out = {}
    for i in range(1, len(days)):
        out[days[i]] = "GREEN" if eq[days[i]]["c"] >= eq[days[i - 1]]["c"] else "RED"
    return out


def main():
    rows = json.load(open(os.path.join(OUT, "rows.json"), encoding="utf-8"))
    color = spy_day_color()
    for r in rows:
        r["ret"] = replay([c for _, c in r["path"]], r["e"])
        r["color"] = color.get(r["day"], "?")
    L = ["# Historical corpus stress-test - built overnight 2026-08-13",
         "",
         f"Corpus: {len(rows)} replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,",
         "free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover",
         "in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);",
         "trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.",
         "Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.",
         "",
         "| slice | n/days | day-mean raw | haircut | halves |",
         "|---|---|---|---|---|"]
    mild = lambda r: abs(r["spy"]) < 1.5
    band = lambda r: r["prem"] <= 400000
    whale = lambda r: r["prem"] > 400000
    fade = [r for r in rows if r["shape"] == "fade"]
    cons = [r for r in rows if r["shape"] == "consensus"]
    P = lambda rs: [(r["day"], r["ret"]) for r in rs]
    L.append(line("FADE mild in-band (live analogue)", P([r for r in fade if mild(r) and band(r)])))
    L.append(line("FADE mild whale 400k-1M", P([r for r in fade if mild(r) and whale(r)])))
    L.append(line("FADE trend days (router blocks)", P([r for r in fade if not mild(r)])))
    L.append(line("CONSENSUS trend days (leg candidate)", P([r for r in cons if not mild(r)])))
    L.append(line("CONSENSUS mild days", P([r for r in cons if mild(r)])))
    L.append("")
    L.append("## By period - FADE mild in-band vs CONSENSUS trend")
    L.append("| period | fade mild | consensus trend |")
    L.append("|---|---|---|")
    for lo, hi, tag in [("2024-09", "2025-03", "2024H2"), ("2025-03", "2025-09", "2025H1+"),
                        ("2025-09", "2026-03", "2025H2+"), ("2026-03", "2026-08", "2026")]:
        f = stats(P([r for r in fade if mild(r) and band(r) and lo <= r["day"] < hi]))
        c = stats(P([r for r in cons if not mild(r) and lo <= r["day"] < hi]))
        fs = f"{f['day_mean']:+.2f}% ({f['trades']}/{f['days']}d t={f['t']})" if f else "-"
        cs = f"{c['day_mean']:+.2f}% ({c['trades']}/{c['days']}d t={c['t']})" if c else "-"
        L.append(f"| {tag} | {fs} | {cs} |")
    L.append("")
    L.append("## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)")
    L.append("| slice | n/days | day-mean raw | haircut | halves |")
    L.append("|---|---|---|---|---|")
    allr = rows
    L.append(line("EXEC_BASELINE (any shape, any day)", P([r for r in allr if band(r)])))
    L.append(line("EXEC_BASELINE green days", P([r for r in allr if band(r) and r["color"] == "GREEN"])))
    L.append(line("EXEC_BASELINE red days", P([r for r in allr if band(r) and r["color"] == "RED"])))
    L.append(line("FADE mild GREEN days", P([r for r in fade if mild(r) and band(r) and r["color"] == "GREEN"])))
    L.append(line("FADE mild RED days", P([r for r in fade if mild(r) and band(r) and r["color"] == "RED"])))
    L.append(line("CONSENSUS trend GREEN (calls w/ uptrend)", P([r for r in cons if not mild(r) and r["color"] == "GREEN"])))
    L.append(line("CONSENSUS trend RED (puts w/ downtrend)", P([r for r in cons if not mild(r) and r["color"] == "RED"])))
    L.append(line("MIXED shape (neither fade nor consensus)", P([r for r in allr if r["shape"] == "mixed"])))
    L.append(line("CALLS only, green days", P([r for r in allr if r["side"] == 1 and r["color"] == "GREEN"])))
    L.append(line("PUTS only, red days", P([r for r in allr if r["side"] == -1 and r["color"] == "RED"])))
    L.append("")
    L.append("## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)")
    L.append("| mode | n/days | day-mean raw | haircut | halves |")
    L.append("|---|---|---|---|---|")
    es_pts, es_all = [], [r for r in fade if mild(r) and band(r)]
    for r in es_all:
        closes = [c for _, c in r["path"]]
        if len(closes) < 4:
            continue
        for j in (1, 2, 3):                       # confirmation window ~first 3 hourly bars
            rise = closes[j] / r["e"] - 1
            if 0.05 <= rise <= 0.15:
                e2 = closes[j]                    # enter at the confirmed price
                es_pts.append((r["day"], replay(closes[j + 1:] or closes[-1:], e2)))
                break
            if rise > 0.15:
                break
    L.append(line("immediate entry (live mode)", P(es_all)))
    L.append(line("confirmed entry (early-strength)", es_pts))
    L.append("")
    L.append("## Exit variants on FADE mild in-band (raw)")
    L.append("| exit rule | n/days | day-mean raw | haircut | halves |")
    L.append("|---|---|---|---|---|")
    base = [r for r in fade if mild(r) and band(r)]
    for name, kw in [("live trail50/20 stop-50", {}), ("stop -40", {"stop": -40}),
                     ("tight trail 10%", {"give": 0.10}), ("early trail trig30", {"trig": 30}),
                     ("take-profit +80", {"cap": 80}), ("time-stop ~3 sessions", {"max_bars": 21})]:
        pts = [(r["day"], replay([c for _, c in r["path"]], r["e"], **kw)) for r in base]
        L.append(line(name, pts))
    # CORPUS PRIORS (owner order 2026-08-13 02:12: "all of this data into the lab") - a
    # machine-readable 2y prior per Sunday-menu hypothesis. ADVISORY ONLY by design: the
    # boundary prints it beside each virgin verdict but never blocks on it - historical
    # concordance informs, virgin days decide. A new blocking gate would be the exact
    # over-engineering the throughput floor exists to prevent.
    pri = {}
    b_all = stats(P([r for r in allr if band(r)]))
    lv = stats(P(base))
    pri["_baseline_any_shape"] = b_all["day_mean"] if b_all else None
    pri["_live_spec_analogue"] = lv["day_mean"] if lv else None

    def put(k, pts):
        s = stats(pts)
        pri[k] = ({"day_mean": s["day_mean"], "t": s["t"], "n": s["trades"], "days": s["days"]}
                  if s else None)
    RP = lambda r, **kw: replay([c for _, c in r["path"]], r["e"], **kw)
    put("EXIT_STOP40", [(r["day"], RP(r, stop=-40)) for r in base])
    put("FADE_WHALE", P([r for r in fade if mild(r) and whale(r)]))
    put("BAND_50_400", P([r for r in fade if band(r)]))
    put("SOFT_ROUTER", P([r for r in fade if band(r) and abs(r["spy"]) < 2.5]))
    put("OPT_WINNER", [(r["day"], RP(r, stop=-40)) for r in fade
                       if mild(r) and abs(r["sma"]) < 3 and r["prem"] <= 250000])
    put("V13_DEPTH", P([r for r in fade if mild(r) and band(r) and abs(r["sma"]) < 2]))
    put("MILD_ONLY", P([r for r in fade if mild(r) and band(r) and abs(r["sma"]) < 2]))
    json.dump(pri, open(os.path.join(OUT, "corpus_priors.json"), "w"), indent=1)
    open(os.path.join(OUT, "STRESS_TEST.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

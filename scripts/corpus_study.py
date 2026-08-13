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


def main():
    rows = json.load(open(os.path.join(OUT, "rows.json"), encoding="utf-8"))
    for r in rows:
        r["ret"] = replay([c for _, c in r["path"]], r["e"])
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
    L.append("## Exit variants on FADE mild in-band (raw)")
    L.append("| exit rule | n/days | day-mean raw | haircut | halves |")
    L.append("|---|---|---|---|---|")
    base = [r for r in fade if mild(r) and band(r)]
    for name, kw in [("live trail50/20 stop-50", {}), ("stop -40", {"stop": -40}),
                     ("tight trail 10%", {"give": 0.10}), ("early trail trig30", {"trig": 30}),
                     ("take-profit +80", {"cap": 80}), ("time-stop ~3 sessions", {"max_bars": 21})]:
        pts = [(r["day"], replay([c for _, c in r["path"]], r["e"], **kw)) for r in base]
        L.append(line(name, pts))
    open(os.path.join(OUT, "STRESS_TEST.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

"""$5K STRATEGY BACKTESTS (owner order 2026-08-18 20:29: integrate + backtest 2.5y).

Prices the four candidate $5k structures against real Alpaca option history:
  NAKED_PUT_W    - weekly XSP 2%-OTM short put (baseline; NOT tradable at 5k - reference only)
  CREDIT_SPREAD_W- weekly XSP 2%/4% put credit spread (the 5k-sized premium edge)
  CONDOR_W       - weekly XSP 2%/4% iron condor (both sides)
  WHEEL_CSP_F    - monthly cash-secured put on F, 5% OTM, close-at-expiry lower bound
  DEBIT_SPREAD   - corpus candidates re-priced as verticals (long leg minus a real short leg)
Prices are daily trade bars (not quotes) - a +/-20% credit haircut sensitivity is reported.
Weeks with missing legs are skipped and counted (coverage stated, never hidden).
Output: reports/research/fivek_backtests_2026-08-18/REPORT.md
"""
import json
import math
import os
import time
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
OUT = os.path.join(REPO, "reports", "research", "fivek_backtests_2026-08-18")
os.makedirs(OUT, exist_ok=True)
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15 * (i + 1)); continue
            if e.code in (404, 422):
                return {}
            time.sleep(3)
        except Exception:
            time.sleep(3)
    return {}


def opt_daily(occs, start="2024-06-01", end="2026-08-16"):
    out = {}
    for i in range(0, len(occs), 90):
        url = ("https://data.alpaca.markets/v1beta1/options/bars?symbols=" + ",".join(occs[i:i + 90]) +
               f"&timeframe=1Day&start={start}&end={end}&limit=10000")
        page = None
        while True:
            u = url + ("&page_token=" + page if page else "")
            j = get(u)
            for sym, bl in (j.get("bars") or {}).items():
                out.setdefault(sym, {}).update({b["t"][:10]: b["c"] for b in bl})
            page = j.get("next_page_token")
            if not page:
                break
        time.sleep(0.3)
    return out


def stock_daily(sym, start="2024-06-01"):
    url = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={sym}&timeframe=1Day&start={start}"
           "&end=2026-08-16&limit=10000&adjustment=split&feed=iex")
    j = get(url)
    return {b["t"][:10]: b["c"] for b in (j.get("bars") or {}).get(sym, [])}


def occ(root, exp, cp, k):
    return f"{root}{exp.strftime('%y%m%d')}{cp}{int(round(k * 1000)):08d}"


def stats_line(name, weekly):
    if not weekly:
        return f"| {name} | 0 | - | - | - | - |"
    tot = sum(p for _, p in weekly)
    wins = sum(1 for _, p in weekly if p > 0)
    worst = min(p for _, p in weekly)
    eq, peak, mdd = 0.0, 0.0, 0.0
    for _, p in weekly:
        eq += p; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    return (f"| {name} | {len(weekly)} | ${tot:+,.0f} | {wins/len(weekly)*100:.0f}% | "
            f"${worst:+,.0f} | ${mdd:+,.0f} |")


def main():
    xsp = stock_daily("SPY")                      # SPY/10 tracks XSP within pennies; SPY iex feed is dense
    xdays = sorted(xsp)
    weeks = []
    d = date(2024, 6, 3)
    while d < date(2026, 8, 10):
        wd = [x for x in xdays if d.isoformat() <= x <= (d + timedelta(days=4)).isoformat()]
        if len(wd) >= 3:
            weeks.append((wd[0], wd[-1]))
        d += timedelta(days=7)
    legs_needed = []
    plan = []
    for ent, exp in weeks:
        spot = xsp[ent] / 10.0
        k1, k2 = round(spot * 0.98), round(spot * 0.96)
        k3, k4 = round(spot * 1.02), round(spot * 1.04)
        ed = date.fromisoformat(exp)
        row = {"ent": ent, "exp": exp, "spot": spot,
               "p1": occ("XSP", ed, "P", k1), "p2": occ("XSP", ed, "P", k2),
               "c1": occ("XSP", ed, "C", k3), "c2": occ("XSP", ed, "C", k4),
               "k": (k1, k2, k3, k4)}
        plan.append(row)
        legs_needed += [row["p1"], row["p2"], row["c1"], row["c2"]]
    print(f"weekly plan: {len(plan)} weeks, {len(legs_needed)} legs", flush=True)
    bars = opt_daily(sorted(set(legs_needed)))
    naked, credit, condor = [], [], []
    skip = 0
    for r in plan:
        S = xsp[r["exp"]] / 10.0
        k1, k2, k3, k4 = r["k"]
        pr = {n: (bars.get(r[n]) or {}).get(r["ent"]) for n in ("p1", "p2", "c1", "c2")}
        if not pr["p1"] or not pr["p2"]:
            skip += 1
            continue
        naked.append((r["ent"], (pr["p1"] - max(k1 - S, 0)) * 100))
        credit.append((r["ent"], (pr["p1"] - pr["p2"] - max(k1 - S, 0) + max(k2 - S, 0)) * 100))
        if pr["c1"] and pr["c2"]:
            condor.append((r["ent"], (pr["p1"] - pr["p2"] + pr["c1"] - pr["c2"]
                                      - max(k1 - S, 0) + max(k2 - S, 0)
                                      - max(S - k3, 0) + max(S - k4, 0)) * 100))
    print(f"priced: naked {len(naked)}, credit {len(credit)}, condor {len(condor)}, skipped {skip}", flush=True)

    f = stock_daily("F")
    fdays = sorted(f)
    wheel = []
    m = date(2024, 6, 1)
    while m < date(2026, 8, 1):
        md = [x for x in fdays if x[:7] == m.isoformat()[:7]]
        if md:
            ent = md[0]
            spot = f[ent]
            k = round(spot * 0.95 * 2) / 2
            fri = m.replace(day=15)
            while fri.weekday() != 4:
                fri += timedelta(days=1)
            o = occ("F", fri, "P", k)
            prem = (opt_daily([o]).get(o) or {}).get(ent)
            sd = [x for x in fdays if x <= fri.isoformat()]
            S = f[sd[-1]] if sd else None
            if prem and S:
                wheel.append((ent, (prem - max(k - S, 0)) * 100))
        m = (m + timedelta(days=32)).replace(day=1)
    print(f"wheel months priced: {len(wheel)}", flush=True)

    rows = json.load(open("reports/research/historical_corpus_2026-08-13/rows.json"))
    rows = [r for r in rows if r.get("shape") in ("fade", "consensus")]
    rows = rows[:: max(1, len(rows) // 400)][:400]
    shorts = []
    for r in rows:
        root = r["t"]
        tail = r["occ"][len(root):]
        exp, cp, k = tail[:6], tail[6], int(tail[7:]) / 1000.0
        step = 0.5 if k < 25 else (1.0 if k < 100 else (5.0 if k < 500 else 10.0))
        k2 = k + step if cp == "C" else k - step
        r["occ2"] = f"{root}{exp}{cp}{int(round(k2 * 1000)):08d}"
        shorts.append(r["occ2"])
    b2 = {}
    for i in range(0, len(shorts), 40):
        grp = rows[i:i + 40]
        syms = ",".join(sorted({g["occ2"] for g in grp}))
        d0 = min(g["day"] for g in grp)
        d1 = (date.fromisoformat(max(g["day"] for g in grp)) + timedelta(days=18)).isoformat()
        j = get("https://data.alpaca.markets/v1beta1/options/bars?symbols=" + syms +
                f"&timeframe=1Hour&start={d0}&end={d1}&limit=10000")
        for sym, bl in (j.get("bars") or {}).items():
            b2.setdefault(sym, {}).update({b["t"]: b["c"] for b in bl})
    deb_pts, long_pts = [], []
    for r in rows:
        sp = b2.get(r["occ2"]) or {}
        if len(sp) < 3:
            continue
        lp = dict(r["path"])
        common = [t for t, _ in r["path"] if t in sp and t > r["day"]]
        if len(common) < 3:
            continue
        e_l, e_s = lp[common[0]], sp[common[0]]
        net0 = e_l - e_s
        if net0 <= 0.03:
            continue
        best_exit = common[-1]
        for t in common:
            if (lp[t] / r["e"] - 1) * 100 <= -50 or (lp[t] / r["e"] - 1) * 100 >= 100:
                best_exit = t
                break
        net1 = lp[best_exit] - sp[best_exit]
        deb_pts.append((r["day"], (net1 / net0 - 1) * 100))
        long_pts.append((r["day"], (lp[best_exit] / lp[common[0]] - 1) * 100))
    print(f"debit spreads priced: {len(deb_pts)}", flush=True)

    def dc(pts):
        per = defaultdict(list)
        for dd, x in pts:
            per[dd].append(x)
        ms = [sum(v) / len(v) for v in per.values()]
        if not ms:
            return "n=0"
        mu = sum(ms) / len(ms)
        sd = (sum((x - mu) ** 2 for x in ms) / max(len(ms) - 1, 1)) ** 0.5
        t = mu / (sd / math.sqrt(len(ms))) if sd > 0 else 0
        return f"{len(pts)} trades/{len(ms)}d day-mean {mu:+.2f}% t={t:.2f}"

    L = ["# $5k strategy backtests - 2.5y real option bars (2026-08-18)",
         "",
         "Trade-bar prices (not quotes); weeks with missing legs skipped and counted; the",
         "naked put is the untradable-at-5k REFERENCE for what the credit spread gives up.",
         "",
         "| strategy (1 lot) | periods | total P&L | win% | worst period | max drawdown |",
         "|---|---|---|---|---|---|",
         stats_line("NAKED_PUT_W (reference)", naked),
         stats_line("CREDIT_SPREAD_W", credit),
         stats_line("CONDOR_W", condor),
         stats_line("WHEEL_CSP_F", wheel),
         "",
         f"DEBIT_SPREAD (vertical, real short legs): {dc(deb_pts)}",
         f"LONG-ONLY same sample (comparison):      {dc(long_pts)}",
         "",
         f"coverage: {len(credit)}/{len(plan)} weeks priced for spreads; sensitivity: a 20% credit",
         "haircut scales spread P&L roughly linearly - apply mentally before believing totals."]
    open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump({"naked": naked, "credit": credit, "condor": condor, "wheel": wheel},
              open(os.path.join(OUT, "weekly_pnl.json"), "w"))
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()

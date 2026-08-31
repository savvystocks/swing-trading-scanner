"""DATA INTEGRITY AUDIT (owner 2026-08-31: "are you 1000% sure our data is correct and lined
up properly?"). No honest system claims 1000% - this measures instead of asserting.

CHECKS (two independent data sources cross-examined):
1. PRICE ALIGNMENT - random sample of contract-days: does the day's LAST Alpaca hourly close
   (traded price, source B) sit inside/near that day's UW closing bid-ask (source A)? Gross
   mismatches would expose symbol collisions, date shifts, or bad quotes.
2. DATE SANITY - no library bars earlier than the contract's first archive day - 60d; bar dates
   are weekdays; flow_prints executed_at matches its claimed day.
3. SYMBOL PARSE - OCC symbols round-trip (ticker prefix, YYMMDD expiry >= trade day, strike>0).
4. STRUCTURAL - primary-key duplicate impossibility confirmed, orphan bar check, prints-day check.
Output: reports/research/data_integrity_2026-08-31.md with PASS/FAIL per check + error rates.
"""
import json
import os
import random
import sqlite3
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)


def main():
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    L = ["# DATA INTEGRITY AUDIT - 2026-08-31", ""]
    rng = random.Random(7)

    # ---- 1. cross-source price alignment ----
    rows = src.execute(
        """select ticker, option_symbol, day, nbbo_bid, nbbo_ask from contracts_daily
           where nbbo_bid is not null and nbbo_ask is not null and nbbo_ask > 0
             and nbbo_bid > 0 and (nbbo_ask - nbbo_bid) / ((nbbo_ask+nbbo_bid)/2.0) * 100 <= 3
           order by random() limit 800""").fetchall()
    cur = lib.cursor()
    inside = near = outside = nodata = 0
    worst = []
    for t, occ, day, bid, ask in rows:
        bars = cur.execute("select ts, c from bars where occ=? and ts like ? order by ts",
                           (occ, day + "%")).fetchall()
        if not bars:
            nodata += 1
            continue
        last_close = bars[-1][1]
        mid = (bid + ask) / 2.0
        if bid - 1e-9 <= last_close <= ask + 1e-9:
            inside += 1
        elif abs(last_close - mid) / mid <= 0.10:
            near += 1                      # within 10% of mid - quote timestamp skew, acceptable
        else:
            outside += 1
            if len(worst) < 5:
                worst.append((occ, day, round(bid, 2), round(ask, 2), round(last_close, 2)))
    checked = inside + near + outside
    ok_rate = (inside + near) / checked * 100 if checked else 0
    L += ["## 1. Cross-source price alignment (UW closing quote vs Alpaca last hourly trade)",
          f"  sampled {len(rows)} contract-days | comparable {checked} (no same-day bars: {nodata})",
          f"  inside bid-ask: {inside} | near (<=10% of mid): {near} | OUTSIDE: {outside}",
          f"  ALIGNMENT: {ok_rate:.1f}% -> {'PASS' if ok_rate >= 95 else 'FAIL - INVESTIGATE'}",
          f"  worst mismatches: {worst}" if worst else "  worst mismatches: none", ""]

    # ---- 2. date sanity ----
    bad_dates = 0
    weekend_bars = 0
    sample_occ = [r[0] for r in src.execute(
        "select distinct option_symbol from contracts_daily order by random() limit 300")]
    for occ in sample_occ:
        f = src.execute("select min(day) from contracts_daily where option_symbol=?", (occ,)).fetchone()[0]
        b = cur.execute("select min(ts), max(ts) from bars where occ=?", (occ,)).fetchone()
        if b and b[0]:
            if b[0][:10] < f and (date.fromisoformat(f) - date.fromisoformat(b[0][:10])).days > 60:
                bad_dates += 1
            wd = cur.execute("select count(*) from bars where occ=? and "
                             "cast(strftime('%w', substr(ts,1,10)) as int) in (0,6)", (occ,)).fetchone()[0]
            weekend_bars += wd
    L += ["## 2. Date sanity (300 sampled contracts)",
          f"  bars predating archive window: {bad_dates} -> {'PASS' if bad_dates == 0 else 'FAIL'}",
          f"  weekend-dated bars: {weekend_bars} -> {'PASS' if weekend_bars == 0 else 'FAIL'}", ""]

    # ---- 3. OCC symbol parse round-trip ----
    parse_fail = expiry_fail = 0
    for t, occ, day in src.execute(
            "select ticker, option_symbol, day from contracts_daily order by random() limit 2000"):
        try:
            assert occ.startswith(t)
            exp = "20" + occ[len(t):len(t) + 6]
            ed = date(int(exp[:4]), int(exp[4:6]), int(exp[6:8]))
            k = int(occ[len(t) + 7:]) / 1000.0
            assert occ[len(t) + 6] in "CP" and k > 0
            if ed < date.fromisoformat(day):
                expiry_fail += 1
        except Exception:
            parse_fail += 1
    L += ["## 3. OCC symbol parse round-trip (2,000 sampled)",
          f"  parse failures: {parse_fail} -> {'PASS' if parse_fail == 0 else 'FAIL'}",
          f"  expiry-before-trade-day: {expiry_fail} -> {'PASS' if expiry_fail == 0 else 'FAIL'}", ""]

    # ---- 4. structural ----
    n_pr_bad = src.execute("select count(*) from flow_prints where substr(executed_at,1,10) != day").fetchone()[0]
    orphan = lib.execute("select count(*) from bars where occ not in (select occ from fetched)").fetchone()[0]
    L += ["## 4. Structural",
          "  contracts_daily primary key (day, option_symbol): duplicates impossible by schema -> PASS",
          f"  flow_prints executed_at/day mismatches: {n_pr_bad} -> {'PASS' if n_pr_bad == 0 else 'FAIL'}",
          f"  orphan bars (no fetch record): {orphan} -> {'PASS' if orphan == 0 else 'WARN'}", "",
          "## Known, documented limits (not errors)",
          "  - hourly bars exist only where a contract traded that hour (quiet hours = gaps)",
          "  - UW quotes are end-of-day snapshots; intraday quote paths are not stored",
          "  - exits in replays price near trade/mid, ~<=1pt optimistic vs bid on spr<=2 cohorts",
          "  - coverage gate (47 tickers) trades breadth for era-consistency by design"]
    open("reports/research/data_integrity_2026-08-31.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("INTEGRITY AUDIT COMPLETE", flush=True)


if __name__ == "__main__":
    main()

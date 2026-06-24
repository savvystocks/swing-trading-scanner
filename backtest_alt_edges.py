"""V10 Research Sandbox - alt-edge expectancy backtester (STANDALONE).

Question: does adding the insider open-market-buy signal lift expectancy vs the
flow-survivor baseline, for a 3-5 day momentum trade?

Two data modes:
  MODE A (--funnel)  parse the live funnel_*.jsonl logs committed to main = the exact
                     universe the scanner saw. NOTE: funnel logging only began
                     2026-06-24, so the 5-day forward window has not elapsed for any
                     logged candidate yet -> 0 evaluable rows until logs accumulate.
  MODE B (default)   HISTORICAL RECONSTRUCTION over completed 5-day windows, so we can
                     produce a real expectancy table today. Baseline = a basket of
                     liquid optionable names at historical scan dates (a stand-in for
                     'flow survivors', since historical UW flow is not free to replay);
                     Overlay = the same rows filtered to names with an open-market
                     insider buy (Form 4 code P) filed within the prior 14 days. The
                     delta isolates the INSIDER edge.

Pricing: Alpaca daily bars (IEX). Insider: edgartools (Form 4 code P, >$25k).
Win = forward 5-day Max Run >= 15%. Realized return = close at 5th trading day
(simple time exit). Wired to nothing in the V9 engine.

Run:  ALPACA_PAPER_API_KEY=... ALPACA_PAPER_SECRET_KEY=... python backtest_alt_edges.py
"""

import os
import sys
import glob
import json
import math
import statistics
from datetime import datetime, timedelta, date

SEC_IDENTITY = "Savvas Georgiou savvastgeorgiou@gmail.com"
WIN_RUN_PCT = 15.0
FWD_WINDOW = 5
INSIDER_PRIOR_DAYS = 14


# ----------------------------------------------------------------------------
# MODE A - funnel log ingestion (the live universe; currently too young)
# ----------------------------------------------------------------------------
def load_funnel_candidates(log_dir="data/ambush_logs"):
    rows = []
    for path in sorted(glob.glob(os.path.join(log_dir, "funnel_*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            scan_date = (rec.get("ts") or "")[:10]
            for e in rec.get("enriched", []):
                rows.append({"ticker": e.get("ticker"), "scan_date": scan_date})
    # dedupe (ticker, scan_date)
    seen, out = set(), []
    for r in rows:
        k = (r["ticker"], r["scan_date"])
        if r["ticker"] and k not in seen:
            seen.add(k)
            out.append(r)
    return out


# ----------------------------------------------------------------------------
# Pricing - Alpaca daily bars
# ----------------------------------------------------------------------------
def alpaca_daily(ticker, start_iso, end_iso):
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed
    k = os.environ.get("ALPACA_PAPER_API_KEY") or os.environ.get("ALPACA_API_KEY")
    s = os.environ.get("ALPACA_PAPER_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")
    if not (k and s):
        return []
    cli = StockHistoricalDataClient(k, s)
    try:
        data = cli.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=ticker, timeframe=TimeFrame.Day,
            start=datetime.fromisoformat(start_iso), end=datetime.fromisoformat(end_iso),
            feed=DataFeed.IEX)).data.get(ticker, [])
    except Exception:
        return []
    return [{"date": b.timestamp.strftime("%Y-%m-%d"), "close": float(b.close), "high": float(b.high)}
            for b in data]


def forward_run(bars, scan_date, window=FWD_WINDOW):
    """Entry = first close on/after scan_date; max run + realized 5d-exit over next `window` bars."""
    idx = [i for i, b in enumerate(bars) if b["date"] >= scan_date]
    if not idx:
        return None
    e = idx[0]
    entry = bars[e]["close"]
    fwd = bars[e + 1:e + 1 + window]
    if not fwd or not entry:
        return None
    max_high = max(b["high"] for b in fwd)
    close_n = fwd[-1]["close"]
    return {"entry": round(entry, 2),
            "max_run": round((max_high / entry - 1) * 100, 1),
            "r_exit": round((close_n / entry - 1) * 100, 1)}


# ----------------------------------------------------------------------------
# Insider - all open-market P-buy filing dates (one edgartools pull per ticker)
# ----------------------------------------------------------------------------
def insider_buy_dates(ticker, since_iso, min_value=25000, max_filings=60):
    from edgar import Company, set_identity
    set_identity(SEC_IDENTITY)
    t = (ticker or "").upper().split(".")[0]
    try:
        fs = Company(t).get_filings(form="4", filing_date=f"{since_iso}:")
    except Exception:
        return []
    dates, n = [], 0
    for f in fs:
        if n >= max_filings:
            break
        n += 1
        try:
            df = f.obj().to_dataframe()
        except Exception:
            continue
        if df is None or getattr(df, "empty", True) or "Code" not in df.columns:
            continue
        for _, r in df[df["Code"] == "P"].iterrows():
            try:
                val = float(r.get("Value"))
                if math.isnan(val):
                    raise ValueError
            except (TypeError, ValueError):
                sh = float(r.get("Shares") or 0)
                pr = float(r.get("Price") or 0)
                val = sh * pr
            if val >= min_value:
                dates.append(str(r.get("Date"))[:10])
    return sorted(set(dates))


def _within_prior(scan_iso, buy_dates, days=INSIDER_PRIOR_DAYS):
    sd = date.fromisoformat(scan_iso)
    for b in buy_dates:
        try:
            delta = (sd - date.fromisoformat(b)).days
        except Exception:
            continue
        if 0 <= delta <= days:
            return b
    return None


# ----------------------------------------------------------------------------
# Expectancy
# ----------------------------------------------------------------------------
def expectancy(rows, label):
    n = len(rows)
    if n == 0:
        return {"label": label, "n": 0, "win_rate": 0, "avg_win": 0, "avg_loss": 0,
                "expectancy": 0, "avg_max_run": 0}
    wins = [r for r in rows if r["win"]]
    losses = [r for r in rows if not r["win"]]
    wr = len(wins) / n
    avg_win = statistics.mean([r["r_exit"] for r in wins]) if wins else 0.0
    avg_loss = statistics.mean([r["r_exit"] for r in losses]) if losses else 0.0
    E = wr * avg_win - (1 - wr) * abs(avg_loss)
    return {"label": label, "n": n, "win_rate": round(wr * 100, 1),
            "avg_win": round(avg_win, 1), "avg_loss": round(avg_loss, 1),
            "expectancy": round(E, 2),
            "avg_max_run": round(statistics.mean([r["max_run"] for r in rows]), 1)}


# ----------------------------------------------------------------------------
# Reconstruction universe (completed 5-day windows)
# ----------------------------------------------------------------------------
UNIVERSE = ["HOOD", "SOFI", "RIVN", "OXY", "NVDA", "AMD", "MU", "PLTR", "COIN", "MARA",
            "WEN", "SMCI", "F", "INTC", "BAC", "UBER", "KO", "JNJ", "VZ", "WMT"]
SCAN_DATES = ["2026-04-21", "2026-04-28", "2026-05-05", "2026-05-12",
              "2026-05-19", "2026-05-27", "2026-06-02", "2026-06-09", "2026-06-16"]


def run_reconstruction():
    earliest = min(SCAN_DATES)
    bars_start = (date.fromisoformat(earliest) - timedelta(days=10)).isoformat()
    insider_since = (date.fromisoformat(earliest) - timedelta(days=INSIDER_PRIOR_DAYS + 3)).isoformat()
    today = datetime.utcnow().date().isoformat()
    rows = []
    print(f"reconstructing {len(UNIVERSE)} tickers x {len(SCAN_DATES)} scan dates "
          f"({earliest} -> {SCAN_DATES[-1]})...")
    for t in UNIVERSE:
        bars = alpaca_daily(t, bars_start, today)
        buys = insider_buy_dates(t, insider_since, max_filings=30)
        hit = 0
        for sd in SCAN_DATES:
            fr = forward_run(bars, sd)
            if not fr:
                continue
            prior_buy = _within_prior(sd, buys)
            rows.append({"ticker": t, "scan_date": sd, "entry": fr["entry"],
                         "max_run": fr["max_run"], "r_exit": fr["r_exit"],
                         "win": fr["max_run"] >= WIN_RUN_PCT,
                         "insider": prior_buy is not None, "prior_buy_date": prior_buy})
            if prior_buy:
                hit += 1
        print(f"  {t:<6} bars={len(bars):>3} P-buy-dates={buys if buys else '-'} overlay_rows={hit}")
    return rows


def _print_expectancy(base, overlay):
    print("\n" + "=" * 78)
    print("EXPECTANCY COMPARISON  (win = fwd 5d Max Run >= 15%; realized = 5d-close exit)")
    print("=" * 78)
    hdr = f"{'strategy':<34}{'n':>4}{'win%':>7}{'avgWin%':>9}{'avgLoss%':>9}{'E(pts)':>8}{'avgMaxRun%':>12}"
    print(hdr); print("-" * len(hdr))
    for s in (base, overlay):
        print(f"{s['label']:<34}{s['n']:>4}{s['win_rate']:>7}{s['avg_win']:>9}{s['avg_loss']:>9}"
              f"{s['expectancy']:>8}{s['avg_max_run']:>12}")
    if base["expectancy"] or overlay["expectancy"]:
        lift = round(overlay["expectancy"] - base["expectancy"], 2)
        print(f"\nexpectancy lift from insider overlay: {lift:+.2f} pts "
              f"({'edge confirmed' if lift > 0 else 'no lift in this sample'})")


def main():
    print("=" * 78)
    print("V10 ALT-EDGE EXPECTANCY BACKTESTER")
    print("=" * 78)

    print("\n--- MODE A: live funnel logs ---")
    fc = load_funnel_candidates()
    today = datetime.utcnow().date()
    evaluable = [r for r in fc if r["scan_date"] and
                 (today - date.fromisoformat(r["scan_date"])).days >= FWD_WINDOW + 2]
    print(f"  funnel candidates found: {len(fc)} | with an elapsed 5d window: {len(evaluable)}")
    if not evaluable:
        print("  -> funnel logging began 2026-06-24; no candidate's forward window has closed yet.")
        print("  -> falling back to historical reconstruction for a real expectancy table.\n")

    print("--- MODE B: historical reconstruction ---")
    rows = run_reconstruction()
    valid = [r for r in rows if r["r_exit"] is not None]
    overlay_rows = [r for r in valid if r["insider"]]
    base = expectancy(valid, "BASELINE (flow-proxy universe)")
    over = expectancy(overlay_rows, "OVERLAY (+ insider P buy <=14d)")
    _print_expectancy(base, over)

    print("\n--- overlay rows (insider buy within prior 14d) ---")
    for r in sorted(overlay_rows, key=lambda x: (x["ticker"], x["scan_date"])):
        print(f"  {r['ticker']:<6} scan {r['scan_date']}  buy {r['prior_buy_date']}  "
              f"maxRun {r['max_run']:>6}%  exit5d {r['r_exit']:>6}%  {'WIN' if r['win'] else 'loss'}")


if __name__ == "__main__":
    main()

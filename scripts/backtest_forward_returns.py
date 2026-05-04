import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "results"


def load_alpaca():
    def get(n):
        if os.environ.get(n):
            return os.environ[n]
        r = subprocess.run(
            ["powershell", "-Command", f'[Environment]::GetEnvironmentVariable("{n}","User")'],
            capture_output=True, text=True
        )
        return (r.stdout or "").strip()
    for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        v = get(k)
        if v:
            os.environ[k] = v


def fetch_current_prices(tickers, verbose=True):
    if not os.environ.get("ALPACA_API_KEY"):
        if verbose:
            print("Alpaca key missing")
        return {}
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest
    sc = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    syms = list({t.replace(".US", "") for t in tickers if t.endswith(".US")})
    if not syms:
        return {}
    out = {}
    chunk = 100
    for i in range(0, len(syms), chunk):
        batch = syms[i:i+chunk]
        try:
            r = sc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=batch))
            if isinstance(r, dict):
                for sym, t in r.items():
                    try:
                        out[sym] = float(t.price)
                    except Exception:
                        pass
        except Exception as e:
            if verbose:
                print(f"  batch fetch failed: {e}")
    return out


def categorize_return(pct):
    if pct >= 50: return "+50_BLOWOUT"
    if pct >= 20: return "+20_BIG_WIN"
    if pct >= 10: return "+10_WIN"
    if pct >= 0: return "FLAT_GREEN"
    if pct >= -10: return "FLAT_RED"
    if pct >= -20: return "LOSER"
    return "BIG_LOSER"


def analyze_scan(scan_path, current_prices, verbose=True):
    with open(scan_path) as f:
        scan = json.load(f)
    scan_date = scan.get("scan_date", scan_path.stem.replace("scan_", ""))
    tickets = scan.get("tickets", [])

    days_elapsed = (datetime.now(timezone.utc).date() - datetime.strptime(scan_date, "%Y-%m-%d").date()).days
    if days_elapsed < 1:
        if verbose:
            print(f"  {scan_date}: too recent ({days_elapsed} days), skipping")
        return None

    hunter_q = [t for t in tickets if t.get("hunter") and t["hunter"].get("qualified")]
    tier4_plus = [t for t in tickets if t.get("tier") and t["tier"] >= 4]
    tier5 = [t for t in tickets if t.get("tier") == 5]
    all_us = [t for t in tickets if t.get("ticker", "").endswith(".US")]

    def compute_returns(group, label):
        rows = []
        for t in group:
            sym = t.get("ticker", "").replace(".US", "")
            entry = t.get("price")
            current = current_prices.get(sym)
            if not entry or not current:
                continue
            pct = (current / entry - 1) * 100
            rows.append({
                "ticker": t["ticker"],
                "name": (t.get("name") or "")[:25],
                "tier": t.get("tier"),
                "hunter_score": (t.get("hunter") or {}).get("score"),
                "entry": entry,
                "current": current,
                "ret_pct": pct,
                "category": categorize_return(pct),
            })
        return rows

    return {
        "scan_date": scan_date,
        "days_elapsed": days_elapsed,
        "all_us_count": len(all_us),
        "tier4_plus": compute_returns(tier4_plus, "Tier 4+"),
        "tier5": compute_returns(tier5, "Tier 5"),
        "hunter_qualified": compute_returns(hunter_q, "Hunter qualified"),
    }


def aggregate_stats(group_rows, label):
    if not group_rows:
        return {"label": label, "n": 0}
    rets = [r["ret_pct"] for r in group_rows]
    cats = [r["category"] for r in group_rows]
    n = len(rets)
    wins_20 = sum(1 for r in rets if r >= 20)
    wins_10 = sum(1 for r in rets if r >= 10)
    wins_any = sum(1 for r in rets if r > 0)
    losses_10 = sum(1 for r in rets if r <= -10)
    return {
        "label": label,
        "n": n,
        "mean_ret": sum(rets) / n,
        "median_ret": sorted(rets)[n // 2],
        "max_ret": max(rets),
        "min_ret": min(rets),
        "win_rate_any": wins_any / n * 100,
        "win_rate_10pct": wins_10 / n * 100,
        "win_rate_20pct": wins_20 / n * 100,
        "loss_rate_10pct": losses_10 / n * 100,
        "categories": {c: cats.count(c) for c in set(cats)},
    }


def print_stats(stats):
    print(f"\n{stats['label']} (n={stats['n']}):")
    if stats["n"] == 0:
        print("  no data")
        return
    print(f"  Mean return:   {stats['mean_ret']:+.2f}%")
    print(f"  Median:        {stats['median_ret']:+.2f}%")
    print(f"  Range:         {stats['min_ret']:+.1f}% to {stats['max_ret']:+.1f}%")
    print(f"  Win rate (any positive):  {stats['win_rate_any']:.1f}%")
    print(f"  Win rate (>=+10%):        {stats['win_rate_10pct']:.1f}%")
    print(f"  Win rate (>=+20%):        {stats['win_rate_20pct']:.1f}%")
    print(f"  Loss rate (<=-10%):       {stats['loss_rate_10pct']:.1f}%")
    print(f"  Outcome distribution: {stats['categories']}")


def main():
    load_alpaca()

    scan_files = sorted(RESULTS_DIR.glob("scan_*.json"))
    if not scan_files:
        print("No scan files found")
        return

    print(f"Found {len(scan_files)} scan files")
    for f in scan_files:
        print(f"  {f.stem}")

    print("\nFetching current prices for all tickers across scans...")
    all_tickers = set()
    for f in scan_files:
        with open(f) as fh:
            s = json.load(fh)
            for t in s.get("tickets", []):
                if t.get("ticker", "").endswith(".US"):
                    all_tickers.add(t["ticker"])
    print(f"Total unique US tickers across history: {len(all_tickers)}")

    prices = fetch_current_prices(all_tickers)
    print(f"Got current prices for {len(prices)}/{len(all_tickers)} tickers")

    aggregate = {"hunter_qualified": [], "tier5": [], "tier4_plus": []}

    for f in scan_files:
        result = analyze_scan(f, prices)
        if not result:
            continue
        print(f"\n{'='*80}")
        print(f"  Scan {result['scan_date']} ({result['days_elapsed']} days ago)")
        print(f"{'='*80}")
        for key in ("hunter_qualified", "tier5", "tier4_plus"):
            rows = result[key]
            if rows:
                aggregate[key].extend(rows)
                stats = aggregate_stats(rows, f"{key.replace('_',' ')} from {result['scan_date']}")
                print_stats(stats)
                top = sorted(rows, key=lambda r: -r["ret_pct"])[:5]
                bottom = sorted(rows, key=lambda r: r["ret_pct"])[:3]
                print(f"  Top 5 winners:")
                for r in top:
                    print(f"    {r['ticker']:10s} {r['ret_pct']:+6.1f}%  hunter={r['hunter_score']}  T{r['tier']}")
                print(f"  Worst 3 losers:")
                for r in bottom:
                    print(f"    {r['ticker']:10s} {r['ret_pct']:+6.1f}%  hunter={r['hunter_score']}  T{r['tier']}")

    print(f"\n\n{'='*80}")
    print(f"  AGGREGATE STATS ACROSS ALL SCANS")
    print(f"{'='*80}")
    for key in ("hunter_qualified", "tier5", "tier4_plus"):
        stats = aggregate_stats(aggregate[key], f"AGGREGATE {key}")
        print_stats(stats)


if __name__ == "__main__":
    main()

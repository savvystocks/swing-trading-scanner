import os
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eodhd import EODHDClient
from src.catalyst.factor_screener import compute_factor_matches


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIVERSE_PATH = os.path.join(PROJECT_ROOT, "data", "universe", "universe.json")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "data", "results")
MCAP_CACHE_PATH = os.path.join(PROJECT_ROOT, "data", "universe", "factor_universe_mcap_cache.json")

MCAP_MIN = 300_000_000
MCAP_MAX = 50_000_000_000


def load_mcap_cache():
    if not os.path.exists(MCAP_CACHE_PATH):
        return {}
    try:
        with open(MCAP_CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_mcap_cache(cache):
    os.makedirs(os.path.dirname(MCAP_CACHE_PATH), exist_ok=True)
    with open(MCAP_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def main():
    target_date = os.environ.get("CATALYST_DATE") or datetime.utcnow().date().strftime("%Y-%m-%d")
    limit_env = os.environ.get("FACTOR_UNIVERSE_LIMIT", "").strip()
    limit = int(limit_env) if limit_env.isdigit() else None

    print(f"=== Factor Universe Scan ({target_date}) ===")

    with open(UNIVERSE_PATH) as f:
        universe = json.load(f)
    if limit:
        universe = universe[:limit]
    print(f"Universe loaded: {len(universe)} tickers")

    client = EODHDClient()
    mcap_cache = load_mcap_cache()

    in_window = []
    too_big = 0
    too_small = 0
    no_data = 0
    errors = 0
    new_fetches = 0
    start = time.time()

    print(f"Step 1/2: filter universe to ${MCAP_MIN/1e6:.0f}M-${MCAP_MAX/1e9:.1f}B + fetch fundamentals")

    for i, row in enumerate(universe):
        if i > 0 and i % 200 == 0:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(universe)}] in_window={len(in_window)} small={too_small} big={too_big} no_data={no_data} err={errors} rate={rate:.1f}/s")

        ticker = row["ticker"]
        try:
            fund = client.fundamentals(ticker)
            if not fund:
                no_data += 1
                continue
            general = fund.get("General", {}) or {}
            highlights = fund.get("Highlights", {}) or {}
            try:
                mcap = float(highlights.get("MarketCapitalization") or 0)
            except (TypeError, ValueError):
                mcap = 0
            mcap_cache[ticker] = mcap
            new_fetches += 1
            if mcap < MCAP_MIN:
                too_small += 1
                continue
            if mcap > MCAP_MAX:
                too_big += 1
                continue

            in_window.append({
                "ticker": ticker.split(".")[0],
                "eodhd_ticker": ticker,
                "name": general.get("Name") or row.get("name"),
                "sector": general.get("Sector") or row.get("sector"),
                "industry": general.get("Industry", "") or "",
                "description": (general.get("Description", "") or "")[:600],
                "market_cap": mcap,
                "index": row.get("index"),
            })
        except Exception as e:
            errors += 1
            if errors < 3:
                print(f"  error on {ticker}: {type(e).__name__}: {str(e)[:80]}")

    save_mcap_cache(mcap_cache)
    print(f"  in window: {len(in_window)}  small={too_small} big={too_big} no_data={no_data} err={errors}")

    print(f"Step 2/2: run factor screener on {len(in_window)} small-mid caps")
    matches = []
    for s in in_window:
        result = compute_factor_matches(s)
        if result["theme_count"] >= 1 or result["factor_count"] >= 2:
            matches.append({
                **s,
                "factor_count": result["factor_count"],
                "theme_count": result["theme_count"],
                "event_count": result["event_count"],
                "matched_factors": result["matched_factors"],
                "factor_ids": result["factor_ids"],
            })

    matches.sort(key=lambda x: (x["theme_count"], x["factor_count"], x.get("market_cap") or 0), reverse=True)

    print(f"  matches: {len(matches)}")
    print(f"  top 15:")
    for m in matches[:15]:
        themes = [f["factor_name"] for f in m["matched_factors"] if f["type"] == "theme"]
        print(f"    {m['ticker']:6s} ${m['market_cap']/1e9:.2f}B  theme={m['theme_count']} factors={m['factor_count']}  {themes[:3]}")

    out = {
        "scan_date": target_date,
        "universe_size": len(universe),
        "in_window_size": len(in_window),
        "matches_count": len(matches),
        "matches": matches,
        "api_calls": client.calls_made,
        "elapsed_seconds": round(time.time() - start, 1),
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, f"factor_screen_{target_date}.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {out_path}")
    print(f"Total time: {time.time() - start:.0f}s, API calls: {client.calls_made}")


if __name__ == "__main__":
    main()

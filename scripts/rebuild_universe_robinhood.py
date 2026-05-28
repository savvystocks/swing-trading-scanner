"""Rebuild universe.json for Robinhood UK options reality.

Filters:
1. Drop FTSE 100 + FTSE 250 entirely (can't trade UK options on Robinhood UK)
2. Keep S&P 500 + S&P 400 + Russell 1000 entirely (large/mid cap, options-liquid)
3. Russell 2000: keep only names with market cap >= $1.5B AND ($1.5B is a proxy for
   sufficient options liquidity since we don't have OI data per ticker here.
   Better filter later via Barchart Premier once subscribed.)

Expected result: ~700-900 tickers (down from 3,284). Cuts EODHD spend ~75%.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


UNIVERSE_PATH = "data/universe/universe.json"
BACKUP_PATH = "data/universe/universe_full_3284.json.bak"


def main():
    with open(UNIVERSE_PATH, "r", encoding="utf-8") as f:
        universe = json.load(f)
    print(f"Input universe: {len(universe)} tickers")

    if not os.path.exists(BACKUP_PATH):
        with open(BACKUP_PATH, "w", encoding="utf-8") as f:
            json.dump(universe, f, indent=2)
        print(f"Backed up full universe to {BACKUP_PATH}")

    EXCLUDED_INDICES = {"FTSE100", "FTSE250"}
    KEEP_INDICES_FULL = {"SP500", "SP400", "RUSSELL1000"}

    filtered = []
    dropped_by_reason = {"ftse": 0, "russell2000_small": 0, "no_mcap": 0}

    for t in universe:
        idx = t.get("index", "")
        if idx in EXCLUDED_INDICES:
            dropped_by_reason["ftse"] += 1
            continue
        if idx in KEEP_INDICES_FULL:
            filtered.append(t)
            continue
        if idx == "RUSSELL2000":
            mcap = t.get("market_cap")
            if mcap is None:
                dropped_by_reason["no_mcap"] += 1
                continue
            try:
                if float(mcap) < 1_500_000_000:
                    dropped_by_reason["russell2000_small"] += 1
                    continue
            except (TypeError, ValueError):
                dropped_by_reason["no_mcap"] += 1
                continue
            filtered.append(t)
            continue
        filtered.append(t)

    print()
    print(f"Output universe: {len(filtered)} tickers (cut {len(universe) - len(filtered)})")
    print("Dropped by reason:")
    for k, v in dropped_by_reason.items():
        print(f"  {k}: {v}")

    print()
    from collections import Counter
    src = Counter(t.get("index") or "?" for t in filtered)
    for s, c in src.most_common():
        print(f"  {s}: {c}")

    if "--apply" in sys.argv:
        with open(UNIVERSE_PATH, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)
        print(f"\nWrote new universe to {UNIVERSE_PATH}")
    else:
        print("\n(Dry run - pass --apply to overwrite universe.json)")


if __name__ == "__main__":
    main()

"""Export current TAKE-grade picks as a TradingView-importable watchlist.

TradingView watchlist format: plain text, one ticker per line, with optional
section headers prefixed by ###. Save the output as a .txt file and import
via the TradingView watchlist menu.

Usage:
  python scripts/export_tradingview_watchlist.py
  python scripts/export_tradingview_watchlist.py > my_take_picks.txt
"""
import os
import sys
import json
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def find_latest_scan():
    files = sorted(glob.glob("data/results/catalyst_2026-*.json"), reverse=True)
    files = [f for f in files if "_intraweek" not in os.path.basename(f) and "_email" not in os.path.basename(f)]
    return files[0] if files else None


def main():
    path = os.environ.get("CATALYST_SCAN_JSON") or find_latest_scan()
    if not path:
        print("No scan JSON found in data/results", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        scan = json.load(f)

    aa = scan.get("aa_results") or {}
    take = []
    watch_borderline = []
    macro_puts = []
    open_journal_positions = []

    for tier in ("A++", "A+", "A"):
        for p in aa.get(tier, []) or []:
            action = (p.get("_action_signal") or {}).get("action")
            conv = (p.get("_conviction") or {}).get("score") or 0
            t = p.get("ticker")
            if not t:
                continue
            if action == "TAKE":
                take.append((t, conv, tier))
            elif conv >= 60:
                watch_borderline.append((t, conv, tier))

    for p in aa.get("MACRO_PUT", []) or []:
        t = p.get("ticker")
        score = (p.get("_bear_conviction") or {}).get("score") or 0
        if t:
            macro_puts.append((t, score))

    journal_path = "data/paper_trades/conviction_journal.jsonl"
    if os.path.exists(journal_path):
        with open(journal_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("status") == "OPEN":
                    open_journal_positions.append(row.get("ticker"))

    take.sort(key=lambda x: -x[1])
    watch_borderline.sort(key=lambda x: -x[1])

    print(f"### TAKE picks — scan {scan.get('scan_date', '?')}")
    for t, c, tier in take[:5]:
        print(t)
    print()

    if watch_borderline:
        print(f"### Borderline (60-69 conviction)")
        for t, c, tier in watch_borderline[:10]:
            print(t)
        print()

    if macro_puts:
        print(f"### Macro put candidates")
        for t, s in macro_puts:
            print(t)
        print()

    if open_journal_positions:
        seen = set()
        unique = [t for t in open_journal_positions if t not in seen and not seen.add(t)]
        print(f"### Open paper positions (drift watch)")
        for t in unique[:20]:
            print(t)


if __name__ == "__main__":
    main()

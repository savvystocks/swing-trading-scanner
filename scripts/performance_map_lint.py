"""PERFORMANCE MAP LINT (2026-09-13). The returns map may only quote numbers the ledger holds,
and the ledger may not be stale:
  - reports/performance/ledger.json exists and is at most MAX_AGE_DAYS old;
  - every [[KEY = value]] token in docs/performance_map/*.md resolves to a ledger key and its
    value equals the ledger's formatted value (the ledger's --update-map writes them, so a
    mismatch means someone edited a number by hand or the ledger moved without the map);
  - every ACTIVE strategy in the ledger has a map file; every map file carries its sections.
Exit 1 on any miss, naming it. MOT 6.19 runs it."""
import json
import os
import re
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
LEDGER = os.path.join(REPO, "reports", "performance", "ledger.json")
MAP = os.path.join(REPO, "docs", "performance_map")
MAX_AGE_DAYS = 10
SECTIONS = ["## What", "## Evidence cell", "## Numbers", "## Recompute", "## Healthy", "## Live", "## Checks", "## Traps"]
TOK = re.compile(r"\[\[([A-Za-z0-9_.]+) = ([^\]]*)\]\]")


def main():
    misses = []
    if not os.path.exists(LEDGER):
        print(f"performance map lint: FAIL\n  {LEDGER} missing - run scripts/returns_ledger.py")
        return 1
    led = json.load(open(LEDGER, encoding="utf-8"))
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(led["generated_at"])).days
        if age > MAX_AGE_DAYS:
            misses.append(f"ledger is {age} days old (limit {MAX_AGE_DAYS}) - run scripts/returns_ledger.py --update-map")
    except Exception:
        misses.append("ledger has no readable generated_at")
    from returns_ledger import fmt, lookup
    files = {n for n in os.listdir(MAP) if n.endswith(".md")} if os.path.isdir(MAP) else set()
    for s in led.get("active") or []:
        if f"{s}.md" not in files:
            misses.append(f"active strategy {s} has no docs/performance_map/{s}.md")
    n_tok = 0
    for name in sorted(files):
        txt = open(os.path.join(MAP, name), encoding="utf-8").read()
        if name != "README.md":
            for sec in SECTIONS:
                if sec not in txt:
                    misses.append(f"{name}: section '{sec}' missing")
        for key, val in TOK.findall(txt):
            n_tok += 1
            v, ok = lookup(led, key)
            if not ok:
                misses.append(f"{name}: [[{key}]] is not a ledger key")
            elif fmt(key, v) != val:
                misses.append(f"{name}: [[{key}]] says {val} but the ledger says {fmt(key, v)}")
    if misses:
        print("performance map lint: FAIL")
        for m in misses:
            print("  " + m)
        return 1
    print(f"performance map lint: OK ({n_tok} numbers agree with the ledger of {led.get('generated_at', '?')[:10]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

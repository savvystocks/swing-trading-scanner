"""Research try ledger: one append-only file of every study, its configuration count and its verdict, with the
project-wide luck bar computed from it. docs/research_ledger.jsonl is the count of record; HYPOTHESIS_LEDGER.md
stays the readable story.

  python3 scripts/research_ledger.py total            counted tries, uncounted studies, luck bar
  python3 scripts/research_ledger.py bar N            luck bar if a new study adds N configurations
  python3 scripts/research_ledger.py add ID N "hypothesis" PROTOCOL_PATH SHA256
  python3 scripts/research_ledger.py close ID "verdict" "record"
  python3 scripts/research_ledger.py list
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "research_ledger.jsonl")


def load():
    with open(PATH, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def studies(rows):
    out = {}
    for r in rows:
        if r["event"] == "open":
            if r["id"] in out:
                raise SystemExit(f"duplicate study id {r['id']}")
            out[r["id"]] = dict(r)
        elif r["event"] == "close":
            if r["id"] not in out:
                raise SystemExit(f"close for unknown study {r['id']}")
            out[r["id"]].update(verdict=r["verdict"], record=r["record"], closed=r["date"])
    return out


def bar(n):
    return math.sqrt(2 * math.log(n)) if n > 1 else 0.0


def total(s):
    counted = sum(v["configs"] for v in s.values() if v["configs"] is not None)
    uncounted = [k for k, v in s.items() if v["configs"] is None]
    return counted, uncounted


def append(row):
    row["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def main(a):
    s = studies(load())
    n, unc = total(s)
    if not a or a[0] == "total":
        print(f"counted configurations {n:,} across {len(s)} studies; {len(unc)} studies uncounted")
        print(f"luck bar sqrt(2 ln N) = {bar(n):.2f}")
        return 0
    if a[0] == "bar":
        k = int(a[1])
        print(f"N {n:,} + {k:,} = {n + k:,}; luck bar {bar(n + k):.2f}")
        return 0
    if a[0] == "add":
        sid, k, hyp, proto, sha = a[1], int(a[2]), a[3], a[4], a[5]
        if sid in s:
            raise SystemExit(f"study id {sid} already in the ledger")
        append({"event": "open", "id": sid, "configs": k, "hypothesis": hyp, "protocol": proto, "sha256": sha})
        print(f"added {sid}: N {n + k:,}; luck bar {bar(n + k):.2f}")
        return 0
    if a[0] == "close":
        if a[1] not in s:
            raise SystemExit(f"unknown study {a[1]}")
        if "verdict" in s[a[1]]:
            raise SystemExit(f"{a[1]} already closed")
        append({"event": "close", "id": a[1], "verdict": a[2], "record": a[3]})
        print(f"closed {a[1]}")
        return 0
    if a[0] == "list":
        for k, v in s.items():
            c = "uncounted" if v["configs"] is None else f"{v['configs']:,}"
            print(f"{k:42s} {c:>10s}  {v.get('verdict', 'OPEN')[:70]}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

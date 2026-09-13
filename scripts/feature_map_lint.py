"""FEATURE MAP LINT (learned from the 2026-09-11 Lauren Tan workshop: a feature map is only worth
keeping if it is mechanically kept true). Walks docs/feature_map/*.md and checks that every
backticked citation resolves in this checkout:
  `path/file.py:symbol`  -> the file exists and defines `symbol` (def / class / module assignment)
  `path/file.ext`        -> the file exists (py, sh, yml, json, md, jsonl, db are checked; data
                            files that are gitignored are allowed to be absent when listed in ALLOW_MISSING)
and that every subsystem file carries the seven sections agents look for. Exit 1 on any miss, with
the file and the citation named. MOT 6.18 runs it; run it yourself after any rename."""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(REPO, "docs", "feature_map")
MAP_BORN = "2026-09-13"          # incidents dated from here on must appear in a Traps section
SECTIONS = ["## What", "## Where", "## Exercise", "## Healthy", "## Evidence", "## Checks", "## Traps"]
NO_SECTIONS = {"README.md", "vps-crons.md", "gate-and-ship.md"}
ALLOW_MISSING = {"data/harvest.db", "data/uw_history.db", "data/hourly_paths.db", "data/harvest_inbox",
                 "reports/research/probe_tuner_rows_v3.jsonl", "reports/research/glide_fine_rows_v3.jsonl",
                 "reports/research/student_asof_v3.jsonl", "reports/shadow_lab/student_scores.jsonl",
                 "reports/shadow_lab/sentinels.jsonl", "reports/shadow_lab/ledger.jsonl",
                 "reports/shadow_lab/trajectory.log", "proactive_autopsy_log.md", "data/last_cycle_ok",
                 "reports/research/superseded"}
CITE = re.compile(r"`([A-Za-z0-9_./\-]+\.(?:py|sh|yml|json|md|jsonl|db|log))(?::([A-Za-z_][A-Za-z0-9_]*))?`")


def defines(path, sym):
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return False
    return bool(re.search(rf"^\s*(?:def|class)\s+{re.escape(sym)}\b|^{re.escape(sym)}\s*=", txt, re.M))


def main():
    if not os.path.isdir(MAP):
        print(f"feature map lint: {MAP} missing")
        return 1
    misses = []
    n_cites = 0
    for name in sorted(os.listdir(MAP)):
        if not name.endswith(".md"):
            continue
        txt = open(os.path.join(MAP, name), encoding="utf-8").read()
        if name not in NO_SECTIONS:
            for s in SECTIONS:
                if s not in txt:
                    misses.append(f"{name}: section '{s}' missing")
        for path, sym in CITE.findall(txt):
            if path.startswith("/") or path.startswith("~"):
                continue                                  # host paths (VPS logs) are not repo files
            n_cites += 1
            full = os.path.join(REPO, path)
            if not os.path.exists(full):
                if path in ALLOW_MISSING or any(path.startswith(a) for a in ALLOW_MISSING):
                    continue
                if "<" in path or "*" in path:
                    continue
                misses.append(f"{name}: `{path}` does not exist")
                continue
            if sym and not defines(full, sym):
                misses.append(f"{name}: `{path}:{sym}` not defined")
    # EVERY NEW INCIDENT MUST BE MAPPED (the video's rule: a review comment becomes a hard check):
    # each BREAKDOWNS.md entry dated on or after the map's birth must be cited by date in some
    # subsystem file's Traps. Same-day entries are matched by date, so one date covers its entries.
    try:
        bd = open(os.path.join(REPO, "BREAKDOWNS.md"), encoding="utf-8").read()
        dates = sorted({m.group(1) for m in re.finditer(r"^(20\d\d-\d\d-\d\d)", bd, re.M) if m.group(1) >= MAP_BORN})
        alltxt = " ".join(open(os.path.join(MAP, n), encoding="utf-8").read() for n in os.listdir(MAP) if n.endswith(".md"))
        for d in dates:
            if d not in alltxt:
                misses.append(f"BREAKDOWNS entry dated {d} is not mapped - add it to the Traps of the subsystem it hit")
    except Exception as e:
        misses.append(f"BREAKDOWNS cross-check failed: {type(e).__name__}")
    if misses:
        print("feature map lint: FAIL")
        for m in misses:
            print("  " + m)
        return 1
    print(f"feature map lint: OK ({n_cites} citations resolved, incidents since {MAP_BORN} mapped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

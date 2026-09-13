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
    if misses:
        print("feature map lint: FAIL")
        for m in misses:
            print("  " + m)
        return 1
    print(f"feature map lint: OK ({n_cites} citations resolved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

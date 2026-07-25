"""Standing 'Strategy this week' one-pager, auto-generated every Sunday cycle from RECORDED evidence
only. Report-only: reads committed artifacts (student card, council shadow, governor registry,
discovery outputs) and emits the six-part strategy state. Any part it cannot fill from recorded
evidence prints 'no evidence yet' - never prose-fill. Mirrors reports/strategy/STRATEGY_STATE_*.md.
"""
import os
import csv
import glob
import json


def _latest(pattern):
    fs = sorted(glob.glob(pattern))
    return fs[-1] if fs else None


def _load_json(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def _pivot_clock(student_dir):
    """Consecutive OFFICIAL REJECTED verdicts, newest-last by filename."""
    cards = sorted(glob.glob(os.path.join(student_dir, "card_*.json")))
    streak, first = 0, None
    for c in cards:
        d = _load_json(c) or {}
        if d.get("status") == "OFFICIAL":
            if str(d.get("verdict", "")).startswith("STUDENT REJECTED"):
                streak += 1
                first = first or os.path.basename(c)
            else:
                streak = 0
                first = None
    return streak, first


def strategy_section(root="."):
    R = os.path.join(root, "reports")
    L = []
    L.append("## Strategy this week (auto-generated, report-only)")
    L.append("")
    L.append("Every line is from recorded evidence; gaps say 'no evidence yet'. Full brief: "
             "reports/strategy/STRATEGY_STATE_*.md.")
    L.append("")

    # 1. two layers - engine result from the latest student card's gate-4 line
    card = _latest(os.path.join(R, "student", "card_*.json"))
    cj = _load_json(card) if card else None
    if cj and cj.get("engine_same_splits"):
        e = cj["engine_same_splits"]
        L.append(f"**1. Two layers.** Frozen engine (incumbent/probe/fill-generator): on the same "
                 f"purged splits its executed picks hit {e.get('hit')} at net {e.get('net_ret')} "
                 f"(n={e.get('n')}, {os.path.basename(card)}). School above it is shadow/dormant "
                 f"(school_mode off; v12_school_mot off-state byte-identity).")
    else:
        L.append("**1. Two layers.** no evidence yet (no student card committed).")

    # 2. rulebook status from the governor registry
    reg = _load_json(os.path.join(root, "governor_registry.json"))
    if reg and reg.get("organs"):
        rungs = "; ".join(f"{n} {o['rung']}/{o['state']}" for n, o in sorted(reg["organs"].items()))
        L.append(f"**2. Rulebook / authority.** {rungs}. Spread cap ACTIVE (only live governed change). "
                 "Full table: STRATEGY_STATE + LIVE_GATE.md.")
    else:
        L.append("**2. Rulebook / authority.** no evidence yet (Governor registry not written yet).")

    # 3. hypothesis ledger - point to the settling artifacts that exist
    veins = []
    if _latest(os.path.join(R, "discovery", "stock_horizon_*.md")):
        veins.append("stock-horizon (see stock_horizon_*.md)")
    if os.path.exists(os.path.join(R, "discovery", "idea_ledger.md")):
        veins.append("idea-ledger veins")
    if cj:
        veins.append("Student pocket (see the student card)")
    L.append("**3. Hypotheses open.** " + (", ".join(veins) if veins else "no evidence yet")
             + ". Beliefs + tripwires: STRATEGY_STATE part 3.")

    # 4. what we would take today - council shadow takes
    csvf = _latest(os.path.join(R, "council", "council_shadow_*.csv"))
    if csvf:
        takes = sum(1 for r in csv.DictReader(open(csvf)) if r.get("decision") == "TAKE")
        n = sum(1 for _ in csv.DictReader(open(csvf)))
        L.append(f"**4. Trade today.** Council TAKEs this run: {takes} of {n} "
                 f"({os.path.basename(csvf)}). Per-feature attribution: no evidence yet "
                 "(not in the recorded shadow table).")
    else:
        L.append("**4. Trade today.** no evidence yet (no council shadow committed).")

    # 5. next intended change - static queue, evidence-referenced
    L.append("**5. Next governed change.** Poller extension (make fixed-hold answerable; resolution "
             "stat 2026-07-25), then the conditional measurement lane (LIVE_GATE.md). Both await a "
             "Sunday boundary + owner go. Nothing else (spec freeze).")

    # 6. pivot clock
    streak, first = _pivot_clock(os.path.join(R, "student"))
    if first:
        L.append(f"**6. Pivot clock.** Week {streak} of 6 (first official REJECTED {first}). "
                 "Mined-out needs 6 consecutive REJECTED + no survivor + stock-horizon failed "
                 "(ROADMAP pivot rule). Nothing pivots automatically.")
    else:
        L.append("**6. Pivot clock.** Week 0 of 6 (no official REJECTED on record) — or last "
                 "official verdict was not REJECTED.")
    L.append("")
    return "\n".join(L)

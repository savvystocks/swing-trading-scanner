"""Measurement-lane TRIGGER CHECK (addendum Section 3) - report-only, never activates.

Runs every Sunday against the REAL fill-ledger. Answers one pre-registered question: do organic fills
fail to cover the spread buckets where the school actually selects? If yes, the trigger is MET and the
owner is told with the numbers - activation remains an owner decision, never automatic.

Pre-registered trigger (written 2026-07-25, before the fills exist), ALL must hold:
  (a) at least MIN_FILLS real entry fills exist (else NOT YET EVALUABLE);
  (b) the school concentrates >= SCHOOL_TIGHT_MIN of its selections in the tight (<2%) bucket
      (selections = Council TAKEs; if none, the top-quintile-by-blend as the would-select proxy);
  (c) tight-bucket fills are materially under-represented: fewer than TIGHT_FILL_FLOOR real fills.
Meeting all three => MET. The lane is FIREWALLED from the edge record: any lane fills feed cost
models only, never Gate 1-4 evidence.
"""
import os
import csv
import glob
import sqlite3

MIN_FILLS = 20
SCHOOL_TIGHT_MIN = 0.25          # >= 25% of school selections in the tight bucket
TIGHT_FILL_FLOOR = 10            # fewer than this many tight fills = materially under-covered


def _bucket(sp):
    if sp is None:
        return None
    sp = float(sp)
    return "tight<2" if sp < 2 else "med2-8" if sp < 8 else "wide8-20" if sp < 20 else "vwide>=20"


def _fills_by_bucket(con):
    try:
        rows = con.execute(
            "SELECT c.spread_pct FROM fills f JOIN candidates c ON c.occ_symbol = f.occ_symbol "
            "WHERE f.kind = 'entry_fill' AND f.terminal_state = 'filled'").fetchall()
    except sqlite3.OperationalError:
        return {}, 0                                  # no fills table yet
    out = {}
    for (sp,) in rows:
        b = _bucket(sp)
        if b:
            out[b] = out.get(b, 0) + 1
    return out, len(rows)


def _school_buckets(con, council_csv):
    """Where the school selects, by bucket. TAKEs first; if none, the top-quintile-by-blend proxy."""
    if not council_csv or not os.path.exists(council_csv):
        return {}, "no council shadow"
    rows = list(csv.DictReader(open(council_csv)))
    takes = [r for r in rows if r.get("decision") == "TAKE"]
    src = "council TAKEs"
    if not takes:                                     # no takes this week -> the would-select region
        scored = [r for r in rows if r.get("council_blend") not in (None, "", "nan")]
        scored.sort(key=lambda r: float(r["council_blend"]), reverse=True)
        takes = scored[: max(1, len(scored) // 5)]
        src = "top-quintile-by-blend proxy (no TAKEs)"
    ids = [r["candidate_id"] for r in takes if r.get("candidate_id")]
    if not ids:
        return {}, src
    q = "SELECT spread_pct FROM candidates WHERE candidate_id IN (%s)" % ",".join("?" * len(ids))
    out = {}
    for (sp,) in con.execute(q, ids).fetchall():
        b = _bucket(sp)
        if b:
            out[b] = out.get(b, 0) + 1
    return out, src


def trigger_check(db_path, council_csv):
    con = sqlite3.connect(db_path)
    fills, n_fills = _fills_by_bucket(con)
    school, src = _school_buckets(con, council_csv)
    con.close()

    school_tot = sum(school.values()) or 1
    tight_share = school.get("tight<2", 0) / school_tot
    tight_fills = fills.get("tight<2", 0)

    if n_fills < MIN_FILLS:
        met, reason = False, f"NOT YET EVALUABLE - only {n_fills} real entry fills (need >= {MIN_FILLS})"
    elif tight_share < SCHOOL_TIGHT_MIN:
        met, reason = False, (f"NOT MET - school concentrates {tight_share*100:.0f}% in tight "
                              f"(< {SCHOOL_TIGHT_MIN*100:.0f}% threshold); no tight-coverage gap to fill")
    elif tight_fills >= TIGHT_FILL_FLOOR:
        met, reason = False, (f"NOT MET - tight fills {tight_fills} >= floor {TIGHT_FILL_FLOOR}; "
                              "organic fills already cover where the school trades")
    else:
        met, reason = True, (f"MET - school puts {tight_share*100:.0f}% of selections in tight but only "
                             f"{tight_fills} tight fills exist ({n_fills} fills total, wide-skewed)")

    return {"met": met, "reason": reason, "n_fills": n_fills, "fills_by_bucket": fills,
            "school_by_bucket": school, "school_source": src, "tight_share": round(tight_share, 3),
            "constants": {"min_fills": MIN_FILLS, "school_tight_min": SCHOOL_TIGHT_MIN,
                          "tight_fill_floor": TIGHT_FILL_FLOOR}}


def render_line(chk):
    """One plain-English line for the digest / strategy section. Never activates anything."""
    verdict = "TRIGGER MET (owner decision to activate)" if chk["met"] else "trigger not met"
    return (f"Measurement-lane trigger: {verdict}. {chk['reason']}. "
            f"fills by bucket={chk['fills_by_bucket'] or 'none'}; school selects={chk['school_by_bucket'] or 'none'} "
            f"[{chk['school_source']}]. Report-only; activation stays owner-gated (LIVE_GATE.md).")

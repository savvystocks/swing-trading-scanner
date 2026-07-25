"""CLI: fold the week's organ results into the Governor registry and render the scoreboard.

    python -m src.brain.run_governor --reports reports/governor [--snapshot <dir-or-gz>]

Reads the structured artifacts each organ already writes (student card json, council shadow csv,
discovery convergence_state.json) plus an optional snapshot for the population-drift signature. Writes
governor_registry.json + reports/governor/governor_<week>.md. No engine contact; authority never moves
to LIVE here.
"""
import os
import csv
import glob
import json
import argparse
import datetime as _dt

from . import governor as G


def _latest(pattern):
    fs = sorted(glob.glob(pattern))
    return fs[-1] if fs else None


def _week_id():
    y, w, _ = _dt.datetime.now(_dt.timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def _student_verdict():
    card = _latest("reports/student/card_*.json")
    if not card:
        return None, None
    try:
        c = json.load(open(card))
    except Exception:
        return None, None
    gates = c.get("gates", {})
    g4 = bool(gates.get("4_beats_engine_same_splits"))
    allg = bool(c.get("all_gates_pass"))
    sel = c.get("selection", {})
    margin = None
    if sel.get("wilson_lo") is not None and c.get("hurdle") is not None:
        margin = round(float(sel["wilson_lo"]) - float(c["hurdle"]), 4)
    verdict = "GREEN" if allg else ("AMBER" if g4 else "RED")
    return verdict, margin


def _council_verdict():
    csvf = _latest("reports/council/council_shadow_*.csv")
    if not csvf:
        return None, None
    takes = hits = 0
    try:
        with open(csvf, newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("decision") == "TAKE":
                    takes += 1
                    hits += 1 if row.get("outcome") == "up" else 0
    except Exception:
        return None, None
    if takes == 0:
        return "AMBER", 0.0                     # abstaining is honest, not proof; holds the rung
    hit = hits / takes
    return ("GREEN" if hit >= 0.60 else ("AMBER" if hit >= 0.45 else "RED")), round(hit, 4)


def _survivor_verdicts():
    state = "reports/discovery/convergence_state.json"
    out = {}
    try:
        st = json.load(open(state))
    except Exception:
        return out
    for name, status in st.items():
        s = str(status)
        if s.startswith("SURVIVOR"):
            out[f"survivor:{name}"] = ("GREEN", None)
        elif s.startswith("LAPSED"):
            out[f"survivor:{name}"] = ("RED", None)
        elif s.startswith("FLICKER"):
            out[f"survivor:{name}"] = ("AMBER", None)
    return out


def _population_signature(snapshot):
    if not snapshot:
        return None
    try:
        from . import loader
        import sqlite3
        snap = loader.load_snapshot(snapshot, workdir="gov_work/snap")
        con = sqlite3.connect(snap["db_path"])
        row = con.execute(
            "SELECT AVG(CASE WHEN outcome='up' THEN 1.0 ELSE 0.0 END), "
            "AVG(CASE WHEN c.spread_pct >= 20 THEN 1.0 ELSE 0.0 END), "
            "AVG(CASE WHEN c.spread_pct < 2 THEN 1.0 ELSE 0.0 END) "
            "FROM labels l JOIN candidates c ON c.candidate_id=l.candidate_id "
            "WHERE l.outcome IN ('up','down','vertical') AND l.censored_reason IS NULL "
            "AND l.touch_ts_utc >= (SELECT MAX(touch_ts_utc) FROM labels) - 7*24*3600*1000").fetchone()
        con.close()
        return {"base_up": round(row[0] or 0, 4), "wide_share": round(row[1] or 0, 4),
                "tight_share": round(row[2] or 0, 4)}
    except Exception:
        return None


def run(reports_dir, snapshot=None):
    os.makedirs(reports_dir, exist_ok=True)
    reg = G.load_registry()
    week = _week_id()
    sig = _population_signature(snapshot)

    def _fresh(name):
        # idempotent per week: a manual re-dispatch in the same week must not inflate streaks
        o = reg["organs"].get(name)
        return not (o and o.get("last_week") == week)

    sv, smetric = _student_verdict()
    if sv and _fresh("student"):
        G.evaluate_organ(reg, "student", week, sv, metric=smetric, signature=sig)
    cv, cmetric = _council_verdict()
    if cv and _fresh("council"):
        G.evaluate_organ(reg, "council", week, cv, metric=cmetric, signature=sig)
    for name, (v, m) in _survivor_verdicts().items():
        if _fresh(name):
            G.evaluate_organ(reg, name, week, v, metric=m)

    reg["history"].append({"week": week, "signature": sig})
    reg["history"] = reg["history"][-52:]
    # measurement-lane trigger check (report-only; never activates) - needs the snapshot + council csv
    lane_line = None
    if snapshot:
        try:
            from . import loader, measurement_lane as ML
            snap2 = loader.load_snapshot(snapshot, workdir="gov_work/snap")
            council_csv = _latest("reports/council/council_shadow_*.csv")
            chk = ML.trigger_check(snap2["db_path"], council_csv)
            lane_line = ML.render_line(chk)
            print(lane_line)
            os.makedirs(reports_dir, exist_ok=True)
            open(os.path.join(reports_dir, f"measurement_lane_{week}.md"), "w", encoding="utf-8").write(
                f"# Measurement-lane trigger - {week}\n\n{lane_line}\n\n"
                f"pre-registered constants: {chk['constants']}\n")
        except Exception as e:
            print(f"measurement-lane trigger skipped: {type(e).__name__}: {e}")

    G.save_registry(reg)
    md = G.scoreboard_md(reg, week)
    if lane_line:
        md += "\n\n## Measurement-lane trigger (report-only)\n\n- " + lane_line
    path = os.path.join(reports_dir, f"governor_{week}.md")
    open(path, "w", encoding="utf-8").write(md)
    print(md)
    print("registry ->", G.REGISTRY_PATH)

    # standing 'Strategy this week' one-pager (report-only; recorded evidence + 'no evidence yet')
    try:
        from . import strategy_state
        sdir = os.path.join("reports", "strategy")
        os.makedirs(sdir, exist_ok=True)
        open(os.path.join(sdir, "strategy_this_week.md"), "w", encoding="utf-8").write(
            strategy_state.strategy_section("."))
        print("strategy section -> reports/strategy/strategy_this_week.md")
    except Exception as e:
        print(f"strategy section skipped: {type(e).__name__}: {e}")
    return {"report": path, "registry": reg}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", default="reports/governor")
    ap.add_argument("--snapshot", default=None)
    a = ap.parse_args()
    run(a.reports, a.snapshot)

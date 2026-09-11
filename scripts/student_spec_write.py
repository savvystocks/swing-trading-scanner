"""Write the probe.student block into the LIVE spec (run on the VPS). Reads the honest search
report, selects up to six configurations with positive search-window t,
distinct in (target, cohort, exit), ranked by search-window weekly t with >= 40 trades, and
writes them as pickers in SHADOW mode. Model files come from scripts/student_export.py.
Usage: python scripts/student_spec_write.py reports/research/student_formula_asof_<date>.md
"""
import json
import re
import sys

MAX_PICKERS = 6


def main():
    rep = sys.argv[1]
    rows = []
    for ln in open(rep, encoding="utf-8"):
        m = re.match(r"\| (PWIN|PBIG|EXPRET)/(\w+)/(BASE|WIDE)/k(\d) \| (\d+) \| (\d+) \| ([+-][\d.]+) \| (\d+)% \| ([+-]?\d+) \| ([+-][\d.]+) \|", ln)
        if m:
            rows.append({"target": m.group(1), "cohort": m.group(2), "exit": m.group(3), "k": int(m.group(4)),
                         "trades": int(m.group(5)), "per_trade": float(m.group(7)), "wk_t": float(m.group(10))})
    cands = [r for r in rows if r["trades"] >= 40 and r["wk_t"] > 0]
    cands.sort(key=lambda r: -r["wk_t"])
    chosen, seen = [], set()
    for r in cands:
        key = (r["target"], r["cohort"], r["exit"])
        if key in seen:
            continue
        seen.add(key); chosen.append(r)
        if len(chosen) >= MAX_PICKERS:
            break
    if not chosen:
        print("no eligible classifier configurations in the report"); return
    spec = json.load(open("fade_book_spec.json", encoding="utf-8"))
    pr = spec.setdefault("probe", {})
    exits = {"BASE": {"stop": 50.0, "trig": 50.0, "give": 0.20}, "WIDE": {"stop": 70.0, "trig": 80.0, "give": 0.30}}
    probes = {}
    for i, r in enumerate(chosen):
        name = f"STUDENT_{chr(65 + i)}"
        probes[name] = {"target": r["target"], "cohort": r["cohort"], "exit_label": r["exit"], "k_per_week": r["k"],
                        "search_rank": i + 1, "search_wk_t": r["wk_t"], "search_per_trade": r["per_trade"],
                        "holdout_touched": (i == 0), "model": None, "pulled": False}
        pr.setdefault("tuning", {})[name] = {"exits": exits[r["exit"]], "applied": None, "history": []}
    pr["student"] = {"enabled": True, "mode": "shadow", "bear_standdown": True, "max_model_age_days": 200,
                     "probes": probes,
                     "note": ("2026-09-11 owner order: student pickers on the roster at audition level. ONE seat "
                              "(STUDENT) scores every picker pre-sweep and enters best-first under the model's name. "
                              "mode shadow = score + log only; flip to live on the owner's word after the panel's "
                              "owner decisions. Only search_rank 1 touched the holdout; the others carry "
                              "search-window numbers only (selection-biased by construction).")}
    json.dump(spec, open("fade_book_spec.json", "w", encoding="utf-8"), indent=1)
    for n, c in probes.items():
        print(f"{n}: {c['target']}/{c['cohort']}/{c['exit_label']}/k{c['k_per_week']} search t{c['search_wk_t']:+.2f} {c['search_per_trade']:+.1f}%/trade")
    print("SPEC STUDENT BLOCK WRITTEN (shadow)")


if __name__ == "__main__":
    main()

"""School Phase 3 - the GOVERNOR: the accountability ledger and state machine for every school organ
(Student, Council, each discovery survivor). It is the ONLY place authority can change, and it changes
by evidence, never by drift or mood (NORTH_STAR: "Power flows to the brain only as its track record
justifies, and never by drift").

Contract:
  - The Governor never grants LIVE authority. Promotion tops out at ELIGIBLE_FOR_OWNER; the owner
    flips the final switch (an owner-only field the code never writes).
  - The Governor DOES demote on its own, immediately: any RED drops the organ one rung within one
    cycle (addendum: RED -> frozen engine / flat within one cycle).
  - Two drift species are first-class AMBER inputs:
      PERFORMANCE (concept) drift - the organ's own edge metric trending down.
      POPULATION (data) drift - the incoming candidate distribution shifting under a frozen model.

State ladder (per organ):
  CANDIDATE -> SHADOW_PROVEN (PROMOTE_WEEKS consecutive GREEN) -> ELIGIBLE_FOR_OWNER
Any RED demotes one rung and zeroes the green streak. AMBER holds the rung but breaks the streak.
"""
import os
import json
import numpy as np

REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "governor_registry.json")
PROMOTE_WEEKS = 6                 # consecutive GREEN weeks to climb a rung (matches the pivot-rule cadence)
RUNGS = ["FROZEN", "CANDIDATE", "SHADOW_PROVEN", "ELIGIBLE_FOR_OWNER", "LIVE"]
PERF_DRIFT_SLOPE = -0.02          # metric units/week below this -> performance-drift AMBER
DATA_DRIFT_L1 = 0.20             # population-signature L1 distance above this -> data-drift AMBER


def load_registry(path=REGISTRY_PATH):
    try:
        return json.load(open(path))
    except Exception:
        return {"organs": {}, "history": []}


def save_registry(reg, path=REGISTRY_PATH):
    json.dump(reg, open(path, "w"), indent=2, default=str)


def _organ(reg, name):
    return reg["organs"].setdefault(name, {
        "rung": "CANDIDATE", "state": "AMBER", "green_streak": 0, "history": [],
        "authority": "shadow", "owner_promoted": False})


def perf_drift(metric_series):
    """Concept drift: least-squares slope of the recent metric series (per week). Returns (slope, flag)."""
    y = np.asarray([v for v in metric_series if v is not None], dtype=np.float64)
    if len(y) < 3:
        return None, False
    x = np.arange(len(y), dtype=np.float64)
    slope = float(np.polyfit(x, y, 1)[0])
    return slope, slope < PERF_DRIFT_SLOPE


def data_drift(prev_sig, cur_sig):
    """Population drift: L1 distance between two population signatures (dicts of comparable scalars in
    roughly [0,1]). Returns (distance, flag). A frozen model's calibration is only valid while the
    population it scores stays put."""
    if not prev_sig or not cur_sig:
        return None, False
    keys = set(prev_sig) & set(cur_sig)
    if not keys:
        return None, False
    dist = float(sum(abs(float(cur_sig[k]) - float(prev_sig[k])) for k in keys) / len(keys))
    return dist, dist > DATA_DRIFT_L1


def evaluate_organ(reg, name, week_id, verdict, metric=None, signature=None):
    """Fold one week's result into an organ's record and run the state machine.
    verdict is the raw GREEN/AMBER/RED the caller derived from the organ's gates. This function then
    overlays the two drift species (either can pull GREEN down to AMBER, or confirm a RED) and moves
    the rung. Returns the organ dict."""
    o = _organ(reg, name)
    series = [h.get("metric") for h in o["history"]] + [metric]
    slope, pdrift = perf_drift(series)
    prev_sig = next((h.get("signature") for h in reversed(o["history"]) if h.get("signature")), None)
    dist, ddrift = data_drift(prev_sig, signature)

    state = verdict
    drift_flags = []
    if pdrift:
        drift_flags.append("performance_drift")
    if ddrift:
        drift_flags.append("population_drift")
    if state == "GREEN" and drift_flags:
        state = "AMBER"                    # drift never lets a GREEN stand unqualified

    if state == "GREEN":
        o["green_streak"] += 1
    elif state == "AMBER":
        o["green_streak"] = 0              # hold the rung, break the streak
    else:                                  # RED
        o["green_streak"] = 0
        idx = max(RUNGS.index(o["rung"]) - 1, 0)
        o["rung"] = RUNGS[idx]             # demote one rung within this cycle
        if o["rung"] in ("FROZEN", "CANDIDATE"):
            o["authority"] = "shadow"

    # promotion: evidence only, and never past ELIGIBLE_FOR_OWNER without the owner's own flag
    if state == "GREEN" and o["green_streak"] >= PROMOTE_WEEKS:
        cur = RUNGS.index(o["rung"])
        ceiling = RUNGS.index("LIVE") if o.get("owner_promoted") else RUNGS.index("ELIGIBLE_FOR_OWNER")
        if cur < ceiling:
            o["rung"] = RUNGS[cur + 1]
            o["green_streak"] = 0

    o["state"] = state
    o["last_week"] = week_id
    o["drift"] = {"slope": slope, "perf_drift": pdrift, "data_l1": dist, "data_drift": ddrift}
    o["history"].append({"week": week_id, "verdict": verdict, "state": state, "metric": metric,
                         "signature": signature, "drift": drift_flags})
    o["history"] = o["history"][-26:]     # keep half a year of weekly records
    return o


def _lifetime_trials_line():
    """Q1 (2026-07-29): the search's total size, always visible - the deflation bar every winner
    must clear reflects this number."""
    try:
        from . import trials_ledger as TL
        return (f"Lifetime search intensity: **{TL.lifetime_total():,} model/config trials** across "
                "all studies (feeds the deflated-Sharpe bar), plus the discovery rig's rule-search "
                "trials counted inside its own campaign PBO.")
    except Exception:
        return "Lifetime search intensity: ledger unavailable."


def scoreboard_md(reg, week_id):
    lines = [f"# Governor scoreboard - {week_id}", "",
             "Authority changes by evidence only. The Governor demotes on RED within one cycle; it never",
             "grants LIVE authority - that is the owner's switch (owner_promoted).", "",
             "| organ | rung | state | green streak | authority | drift |",
             "|---|---|---|---|---|---|"]
    for name, o in sorted(reg["organs"].items()):
        d = o.get("drift", {})
        flags = ",".join(f for f, on in (("perf", d.get("perf_drift")), ("data", d.get("data_drift"))) if on) or "-"
        lines.append(f"| {name} | {o['rung']} | {o['state']} | {o['green_streak']}/{PROMOTE_WEEKS} | "
                     f"{o['authority']} | {flags} |")
    elig = [n for n, o in reg["organs"].items() if o["rung"] == "ELIGIBLE_FOR_OWNER" and not o.get("owner_promoted")]
    fade_line = None
    try:
        import glob as _glob
        import os as _os
        from . import fade_health
        snaps = sorted(_glob.glob(_os.path.join("workdir", "harvest_*.db"))) or sorted(_glob.glob("harvest_*.db"))
        if snaps:
            fade_line = fade_health.render(snaps[-1])
    except Exception:
        fade_line = None
    lines += ["", ("**Awaiting owner review:** " + ", ".join(elig)) if elig
              else "No organ is awaiting owner review; nothing is eligible for promotion this week.",
              "", _lifetime_trials_line()]
    if fade_line:
        lines += ["", "## FADE book (the retooled system's life bar)", "", fade_line]
    lines += [
              "", "Demotions are automatic and immediate; promotions to LIVE require the owner to set",
              "`owner_promoted` in governor_registry.json. The frozen V10 engine is unaffected by any state here."]
    return "\n".join(lines)

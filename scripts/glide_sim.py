"""GLIDE POLICY SIMULATION (owner order 2026-09-03: "simulate the glide proposal first with
all the different variables... see if that's a better option and how much to move or glide by").

Phase 1: replay every corpus trigger under a FINE exit grid - stop {-45..-75 by 5} x trigger
{40..90 by 10} x give {.15...35 by .05} = 210 configs/trade (checkpointed).
Phase 2: walk history week by week PER STRATEGY. Each policy holds a config; each week it
evaluates the 8 coarse anchor cells vs its current config on the TRAILING 8 weeks only
(paired day diffs, bar t>=2 and +3/day - the live applier's bar), then moves by its rule:
  HOLD    never moves (baseline)
  JUMP    moves fully to the winning anchor (current live behaviour)
  G10/G15/G20/G25  glides that fraction toward the winner, per knob
  DRAMA   glides 15% normally; jumps fully when evidence is dramatic (t>=4 AND +8/day)
Scoring is strictly out-of-sample: week t+1's trades are scored under the config held at t
(snapped to the fine grid). Report: realized mean of weekly day-means, moves, whipsaws
(direction reversals), final config per strategy x policy. The recommendation is the policy
that wins ACROSS strategies, not the single best cell (policy chosen on one path is itself
a selection - robustness across the six strategies is the guard).
Output: reports/research/glide_sim_<date>.md"""
import json
import math
import os
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

STOPS = [-45.0, -50.0, -55.0, -60.0, -65.0, -70.0, -75.0]
TRIGS = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0]
GIVES = [0.15, 0.20, 0.25, 0.30, 0.35]
GRID = [(s, t, g) for s in STOPS for t in TRIGS for g in GIVES]
GIX = {c: i for i, c in enumerate(GRID)}
ANCHORS = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
           (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]
FINE = "reports/research/glide_fine_rows.jsonl"

STRATS = {
    "FOLLOW_CALLS": lambda r: r["side"] == "C",
    "CONSENSUS_CALLS": lambda r: r["side"] == "C" and not (r["smd"] < 0 and r["sp"] < 0),
    "BULL_DIP": lambda r: r["side"] == "C" and r["reg"] > 2 and r["smd"] < 0,
    "DIP_CONF_MILD": lambda r: r["side"] == "C" and -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0,
    "DIP_CONVEXITY": lambda r: r["side"] == "C" and r["reg"] < -2 and r["sp"] < 0,
    "FADE_BEAR": lambda r: r["reg"] < -2 and ((r["smd"] < 0 and r["sp"] < 0) if r["side"] == "C"
                                              else (r["smd"] > 0 and r["sp"] > 0)),
}
START = {"DIP_CONVEXITY": (-70.0, 80.0, 0.30), "FADE_BEAR": (-50.0, 50.0, 0.20)}


def replay(bars_today_after, bars_next, e, stop, trig, give):
    peak = -999.0
    on = False
    for (h, l, c) in bars_today_after:
        rh = (h / e - 1) * 100
        if rh >= trig:
            on = True
        peak = max(peak, rh)
    for (h, l, c) in bars_next:
        rh = (h / e - 1) * 100; rl = (l / e - 1) * 100
        if rh >= trig:
            on = True
        if on:
            peak = max(peak, rh)
            fl = peak * (1 - give)
            if rl <= fl:
                return fl
        if rl <= stop:
            return stop
    return (bars_next[-1][2] / e - 1) * 100 if bars_next else None


def build_fine():
    import sqlite3
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    cur = lib.cursor()
    prints = {}
    for occ, day, ts in src.execute("select occ, day, min(executed_at) from flow_prints group by occ, day"):
        prints[(occ, day)] = ts
    rows = []
    for line in open("reports/research/probe_tuner_rows.jsonl", encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    done = set()
    if os.path.exists(FINE):
        for line in open(FINE, encoding="utf-8"):
            try:
                done.add(json.loads(line)["occ"])
            except Exception:
                pass
        print(f"fine grid resume: {len(done)}", flush=True)
    out = open(FINE, "a", encoding="utf-8")
    n = 0
    for r in rows:
        if r["occ"] in done:
            continue
        pts = prints.get((r["occ"], r["day"]))
        if not pts:
            continue
        bars_ = cur.execute("select ts, h, l, c from bars where occ=? order by ts", (r["occ"],)).fetchall()
        ta = [(h, l, c) for ts_, h, l, c in bars_
              if ts_[:10] == r["day"] and ts_[11:19] > pts[11:19]]
        nx = [(h, l, c) for ts_, h, l, c in bars_ if ts_[:10] > r["day"]]
        if len(nx) < 3:
            continue
        e = ta[0][2] if ta else r["ask"]
        if e <= 0:
            continue
        rets = []
        for (s, t, g) in GRID:
            v = replay(ta, nx, e, s, t, g)
            rets.append(round(v, 2) if v is not None else None)
        out.write(json.dumps({"occ": r["occ"], "day": r["day"], "side": r["side"],
                              "smd": r["smd"], "reg": r["reg"], "sp": r["sp"], "rets": rets}) + "\n")
        n += 1
        if n % 2000 == 0:
            out.flush(); print(f"fine {n}", flush=True)
    out.close()
    print(f"FINE GRID COMPLETE (+{n})", flush=True)


def snap(cfg):
    s = min(STOPS, key=lambda x: abs(x - cfg[0]))
    t = min(TRIGS, key=lambda x: abs(x - cfg[1]))
    g = min(GIVES, key=lambda x: abs(x - cfg[2]))
    return (s, t, g)


def daymean(rows_wk, gi):
    per = defaultdict(list)
    for r in rows_wk:
        v = r["rets"][gi]
        if v is not None:
            per[r["day"]].append(v)
    if not per:
        return None
    return sum(sum(v) / len(v) for v in per.values()) / len(per)


def paired(rows_win, gi_a, gi_b):
    pa = defaultdict(list); pb = defaultdict(list)
    for r in rows_win:
        if r["rets"][gi_a] is not None:
            pa[r["day"]].append(r["rets"][gi_a])
        if r["rets"][gi_b] is not None:
            pb[r["day"]].append(r["rets"][gi_b])
    shared = sorted(set(pa) & set(pb))
    diffs = [sum(pa[d]) / len(pa[d]) - sum(pb[d]) / len(pb[d]) for d in shared]
    n = len(diffs)
    if n < 10:
        return None
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return {"mean": mu, "t": t, "n": n}


def simulate():
    rows = []
    for line in open(FINE, encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    print(f"sim corpus: {len(rows)}", flush=True)

    def wk(day):
        iso = date.fromisoformat(day).isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"

    POLICIES = ["HOLD", "JUMP", "G10", "G15", "G20", "G25", "DRAMA"]
    L = [f"# GLIDE POLICY SIMULATION - {date.today().isoformat()}", "",
         f"fine grid {len(GRID)} configs/trade, {len(rows)} triggers; move bar = paired t>=2 "
         "and +3/day on the trailing 8 weeks; scored strictly on the NEXT week under the held config.",
         ""]
    summary = defaultdict(list)
    for sname, sfil in STRATS.items():
        srows = [r for r in rows if sfil(r)]
        weeks = sorted({wk(r["day"]) for r in srows})
        by_wk = defaultdict(list)
        for r in srows:
            by_wk[wk(r["day"])].append(r)
        if len(weeks) < 12:
            L.append(f"## {sname}: thin ({len(weeks)} weeks) - skipped")
            continue
        L.append(f"## {sname} ({len(srows)} trades, {len(weeks)} weeks)")
        L.append("| policy | realized day-mean | moves | whipsaws | final config |")
        L.append("|---|---|---|---|---|")
        for pol in POLICIES:
            cfg = START.get(sname, (-50.0, 50.0, 0.20))
            scored = []
            moves = 0
            whips = 0
            lastdir = {}
            for i in range(8, len(weeks) - 1):
                win = [r for w in weeks[i - 8:i] for r in by_wk[w]]
                gi_cur = GIX[snap(cfg)]
                best = None
                for a in ANCHORS:
                    pr = paired(win, GIX[snap(a)], gi_cur)
                    if pr and pr["mean"] >= 3.0 and pr["t"] >= 2.0:
                        if best is None or pr["mean"] > best[1]["mean"]:
                            best = (a, pr)
                if best and pol != "HOLD":
                    tgt, pr = best
                    if pol == "JUMP" or (pol == "DRAMA" and pr["t"] >= 4.0 and pr["mean"] >= 8.0):
                        newcfg = tgt
                    else:
                        a = {"G10": .10, "G15": .15, "G20": .20, "G25": .25, "DRAMA": .15}[pol]
                        newcfg = tuple(c + a * (t_ - c) for c, t_ in zip(cfg, tgt))
                    for k in range(3):
                        d = 1 if newcfg[k] > cfg[k] else (-1 if newcfg[k] < cfg[k] else 0)
                        if d and lastdir.get(k) and d != lastdir[k]:
                            whips += 1
                        if d:
                            lastdir[k] = d
                    if snap(newcfg) != snap(cfg):
                        moves += 1
                    cfg = newcfg
                nxt = by_wk[weeks[i]]
                dm = daymean(nxt, GIX[snap(cfg)])
                if dm is not None:
                    scored.append(dm)
            real = sum(scored) / len(scored) if scored else 0.0
            fc = snap(cfg)
            summary[pol].append(real)
            L.append(f"| {pol} | {real:+.2f}%/day | {moves} | {whips} | "
                     f"{fc[0]:.0f}/{fc[1]:.0f}/{fc[2]:.2f} |")
        L.append("")
    L += ["## Across all strategies (mean of realized day-means)", "| policy | mean | wins |", "|---|---|---|"]
    best_by_strat = defaultdict(int)
    nstrat = len(next(iter(summary.values()))) if summary else 0
    for i in range(nstrat):
        vals = {p: summary[p][i] for p in summary}
        w = max(vals, key=vals.get)
        best_by_strat[w] += 1
    for pol in ["HOLD", "JUMP", "G10", "G15", "G20", "G25", "DRAMA"]:
        if summary.get(pol):
            L.append(f"| {pol} | {sum(summary[pol]) / len(summary[pol]):+.2f}%/day | "
                     f"{best_by_strat.get(pol, 0)} |")
    L += ["", "CAVEATS: one historical path; policy chosen here is itself a selection, so the",
          "recommendation is the policy family that is robust across strategies, not the single",
          "top cell. Bar-price replays; the live court remains the judge of whatever ships."]
    fn = f"reports/research/glide_sim_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("GLIDE SIM COMPLETE", flush=True)


if __name__ == "__main__":
    build_fine()
    simulate()

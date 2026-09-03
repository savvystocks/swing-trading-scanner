"""TUNER APPLY v2 - HOLD-strict, GLIDE-gentle, JUMP-only-on-drama (owner rule 2026-09-03,
set by the glide policy simulation: HOLD beat every moving policy on all four testable
strategies (+4.95 vs +3.2-3.6/day), and within movers gliding beat jumping everywhere).

The rule this encodes:
  - EVIDENCE stays coarse and strict: the 8 anchor exit cells vs the incumbent, paired day
    diffs over ALL shared days in the fine-grid corpus, bar = mean >= +3/day AND t >= 2,
    plus the anchor must PASS on its own (n>=150, both halves > 0, episode-drop > 0).
    14-day per-strategy cooldown. In practice this holds most weeks - as measured, holding
    IS the profitable behaviour once configs are archive-calibrated.
  - MOVEMENT is gentle: a clearing move glides 15% of the gap per knob toward the winner
    (continuous values; the engine reads any floats via _tuned).
  - DRAMA exception: paired t >= 4 AND >= +8/day -> full jump (the fire-alarm case).
  - Sanity clamps on anything written: stop [-80,-30], trig [30,120], give [0.10,0.40].
Buy-side changes remain REPORT-ONLY (instrument-mismatch lesson).
TUNER_APPLY_DRY=1 -> decisions printed, nothing written.
Cron: Friday, after probe_tuner refresh and the glide fine-grid build."""
import json
import math
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from glide_sim import GRID, GIX, snap, FINE, STRATS
from probe_tuner import BUY_VARIANTS

DRY = os.environ.get("TUNER_APPLY_DRY") == "1"
GLIDE = 0.15
INCUMBENT_POOL = {"FOLLOW_CALLS": "fullband", "CONSENSUS_CALLS": "fullband",
                  "BULL_DIP": "base_cheap", "DIP_CONF_MILD": "pricey_4_9",
                  "DIP_CONVEXITY": "base_cheap", "FADE_BEAR": "base_cheap"}
DEFAULT_EXITS = {"DIP_CONVEXITY": (-70.0, 80.0, 0.30), "BULL_DIP_X": (-70.0, 80.0, 0.30)}
ANCHORS = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
           (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]
CLAMP = {"stop": (-80.0, -30.0), "trig": (30.0, 120.0), "give": (0.10, 0.40)}


def tg(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat and not DRY:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass


def daymeans(rows_list, gi):
    per = defaultdict(list)
    for r in rows_list:
        v = r["rets"][gi]
        if v is not None:
            per[r["day"]].append(v)
    return {d: sum(v) / len(v) for d, v in per.items()}


def cellstat(rows_list, gi):
    per = sorted(daymeans(rows_list, gi).items())
    vals = [v for _, v in per]
    n = len(vals)
    if n < 15:
        return None
    h = n // 2
    wkm = defaultdict(list)
    for d, v in per:
        iso = date.fromisoformat(d).isocalendar()
        wkm[f"{iso[0]}-{iso[1]}"].append(v)
    wm = {k: sum(v) / len(v) for k, v in wkm.items()}
    edrop = None
    if len(wm) >= 3:
        best = max(wm, key=wm.get)
        rest = [x for k, v in wkm.items() if k != best for x in v]
        edrop = sum(rest) / len(rest) if rest else None
    ntr = sum(1 for r in rows_list if r["rets"][gi] is not None)
    return {"ok": (ntr >= 150 and sum(vals[:h]) / max(h, 1) > 0
                   and sum(vals[h:]) / max(n - h, 1) > 0 and (edrop is None or edrop > 0))}


def paired(rows_list, gi_a, gi_b):
    a = daymeans(rows_list, gi_a); b = daymeans(rows_list, gi_b)
    shared = sorted(set(a) & set(b))
    diffs = [a[d] - b[d] for d in shared]
    n = len(diffs)
    if n < 15:
        return None
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    return {"mean": mu, "t": mu / (sd / math.sqrt(n)) if sd > 0 else 0.0, "days": n}


def clamp(cfg):
    return (min(max(cfg[0], CLAMP["stop"][0]), CLAMP["stop"][1]),
            min(max(cfg[1], CLAMP["trig"][0]), CLAMP["trig"][1]),
            min(max(cfg[2], CLAMP["give"][0]), CLAMP["give"][1]))


def main():
    if not os.path.exists(FINE):
        print("no fine-grid rows - run glide_sim.py build first")
        return
    pa = {}
    for line in open("reports/research/probe_tuner_rows.jsonl", encoding="utf-8"):
        try:
            j = json.loads(line)
            pa[j["occ"]] = (j["prem"], j["ask"], j["t"])
        except Exception:
            pass
    rows = []
    for line in open(FINE, encoding="utf-8"):
        try:
            j = json.loads(line)
            j["prem"], j["ask"], j["t"] = pa.get(j["occ"], (None, None, ""))
            if j["prem"] is None:
                continue
            rows.append(j)
        except Exception:
            pass
    spec = json.load(open("fade_book_spec.json"))
    tuning = spec.setdefault("probe", {}).setdefault("tuning", {})
    today = date.today().isoformat()
    lines = [f"TUNER APPLY v2 {today} (glide rule; {len(rows)} fine-grid triggers)"
             + (" [DRY RUN]" if DRY else "")]
    changed = False
    for sname, sfil in STRATS.items():
        vname = INCUMBENT_POOL.get(sname, "base_cheap")
        vfil = dict(BUY_VARIANTS).get(vname) or (lambda r: True)
        srows = [r for r in rows if sfil(r) and vfil(r)]
        cur = tuning.get(sname, {})
        if cur.get("applied"):
            dd = (date.today() - date.fromisoformat(cur["applied"])).days
            if dd < 14:
                lines.append(f"{sname}: cooldown ({dd}d) - HOLD")
                continue
        ex = cur.get("exits") or {}
        if all(k in ex for k in ("stop", "trig", "give")):
            inc = clamp((-abs(float(ex["stop"])), float(ex["trig"]), float(ex["give"])))
        else:
            inc = DEFAULT_EXITS.get(sname, (-50.0, 50.0, 0.20))
        gi_inc = GIX[snap(inc)]
        best = None
        for a in ANCHORS:
            gia = GIX[snap(a)]
            if gia == gi_inc:
                continue
            cs = cellstat(srows, gia)
            if not (cs and cs["ok"]):
                continue
            pr = paired(srows, gia, gi_inc)
            if pr and pr["mean"] >= 3.0 and pr["t"] >= 2.0:
                if best is None or pr["mean"] > best[1]["mean"]:
                    best = (a, pr)
        if not best:
            lines.append(f"{sname}: no anchor beats the incumbent on the full window - "
                         f"HOLD at {inc[0]:.0f}/{inc[1]:.0f}/{inc[2]:.2f} (the measured sweet spot)")
            continue
        tgt, pr = best
        drama = pr["t"] >= 4.0 and pr["mean"] >= 8.0
        if drama:
            new = tgt
        else:
            new = tuple(c + GLIDE * (t_ - c) for c, t_ in zip(inc, tgt))
        new = clamp((round(new[0], 1), round(new[1], 1), round(new[2], 3)))
        mode = "JUMP (drama)" if drama else f"GLIDE {int(GLIDE*100)}%"
        lines.append(f"{sname}: {mode} {inc[0]:.0f}/{inc[1]:.0f}/{inc[2]:.2f} -> "
                     f"{new[0]:.1f}/{new[1]:.1f}/{new[2]:.3f} toward "
                     f"{tgt[0]:.0f}/{tgt[1]:.0f}/{tgt[2]:.2f} "
                     f"(paired {pr['mean']:+.1f}/day t{pr['t']:+.2f}, {pr['days']}d)")
        if not DRY:
            hist = cur.get("history", [])
            hist.append({"date": today, "mode": mode, "from": list(inc), "to": list(new),
                         "target": list(tgt), "paired_gain": round(pr["mean"], 1),
                         "paired_t": round(pr["t"], 2)})
            tuning[sname] = {"exits": {"stop": abs(new[0]), "trig": new[1], "give": new[2]},
                             "applied": today, "history": hist[-12:]}
            changed = True
    print("\n".join(lines), flush=True)
    if changed and not DRY:
        json.dump(spec, open("fade_book_spec.json", "w"), indent=1)
        subprocess.run("git add fade_book_spec.json && git commit -qm "
                       "'tuner apply v2: damped glide [skip ci]' && "
                       "git pull -q --rebase -X ours && git push -q", shell=True)
        tg("TUNER APPLY (glide rule):\n" + "\n".join(lines))
    elif not DRY:
        tg("TUNER APPLY: all strategies HOLDING at their measured sweet spots.\n" +
           "\n".join(lines[1:]))
    print("TUNER APPLY COMPLETE", flush=True)


if __name__ == "__main__":
    main()

"""TUNER APPLY - the damped weekly step of the dynamic tuning model (owner 2026-09-01:
"change day or weekly... hover where it finds the sweet spot").

Reads the tuner's scored rows (probe_tuner_rows.jsonl, built from ARCHIVE true-trigger
replays - never from thin live fills) and, per strategy, compares the champion exit config
against the incumbent PAIRED on shared days. Applies to spec probe.tuning.<strat>.exits only
when ALL hold:
  - champion cell PASSes (n>=150, both halves>0, episode-drop>0)
  - paired day-mean improvement >= 3 pts/day with paired t >= 2
  - at most ONE exit knob changes per apply (the hover: adjacent steps, never jumps)
  - strategy cooldown: no change within 14 days of its last one
Buy-side (pool/band) changes are REPORTED ONLY - they need per-probe execution wiring
(the instrument-mismatch lesson) and go through a session + the panel.
TUNER_APPLY_DRY=1 -> print decisions, write nothing. Real runs write spec, commit, telegram.
Cron: Fridays after the tuner refresh, before the boundary.
"""
import json
import math
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from probe_tuner import STRATS, BUY_VARIANTS, EXITS, CKPT

DRY = os.environ.get("TUNER_APPLY_DRY") == "1"
# incumbent buy variant per strategy (what the live probe actually trades today)
INCUMBENT_POOL = {"FOLLOW_CALLS": "base_cheap", "CONSENSUS_CALLS": "base_cheap",
                  "BULL_DIP": "base_cheap", "DIP_CONF_MILD": "pricey_4_9",
                  "DIP_CONVEXITY": "base_cheap", "FADE_BEAR": "base_cheap"}
DEFAULT_EXITS = {"DIP_CONVEXITY": (-70.0, 80.0, 0.30), "BULL_DIP_X": (-70.0, 80.0, 0.30)}


def tg(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat and not DRY:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass


def daymeans(rows_list, ei):
    per = defaultdict(list)
    for r in rows_list:
        if r["rets"][ei] is not None:
            per[r["day"]].append(r["rets"][ei])
    return {d: sum(v) / len(v) for d, v in per.items()}


def cellstat(rows_list, ei):
    per = daymeans(rows_list, ei)
    m = sorted(per.items())
    vals = [v for _, v in m]
    n = len(vals)
    if n < 15:
        return None
    mu = sum(vals) / n
    sd = (sum((x - mu) ** 2 for x in vals) / (n - 1)) ** 0.5
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    wk = defaultdict(list)
    for d, v in m:
        iso = date.fromisoformat(d).isocalendar()
        wk[f"{iso[0]}-{iso[1]}"].append(v)
    wmeans = {k: sum(v) / len(v) for k, v in wk.items()}
    edrop = None
    if len(wmeans) >= 3:
        best = max(wmeans, key=wmeans.get)
        rest = [x for k, v in wk.items() if k != best for x in v]
        edrop = sum(rest) / len(rest) if rest else None
    ntr = sum(1 for r in rows_list if r["rets"][ei] is not None)
    ok = (ntr >= 150 and n >= 15 and sum(vals[:h]) / max(h, 1) > 0
          and sum(vals[h:]) / max(n - h, 1) > 0 and (edrop is None or edrop > 0))
    return {"mean": mu, "t": t, "days": n, "n": ntr, "ok": ok}


def paired(rows_list, ei_a, ei_b):
    a = daymeans(rows_list, ei_a); b = daymeans(rows_list, ei_b)
    shared = sorted(set(a) & set(b))
    diffs = [a[d] - b[d] for d in shared]
    n = len(diffs)
    if n < 15:
        return None
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return {"mean": mu, "t": t, "days": n}


def knob_delta(a, b):
    return sum(1 for i in (0, 1, 2) if abs(a[i] - b[i]) > 1e-9)


def main():
    if not os.path.exists(CKPT):
        print("no tuner rows - run probe_tuner.py first")
        return
    rows = []
    for line in open(CKPT, encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    spec = json.load(open("fade_book_spec.json"))
    tuning = spec.setdefault("probe", {}).setdefault("tuning", {})
    today = date.today().isoformat()
    lines = [f"TUNER APPLY {today} ({len(rows)} scored contract-days){' [DRY RUN]' if DRY else ''}"]
    changed = False
    for sname, sfil in STRATS.items():
        vname = INCUMBENT_POOL.get(sname, "base_cheap")
        vfil = dict(BUY_VARIANTS)[vname]
        srows = [r for r in rows if sfil(r) and vfil(r)]
        cur = tuning.get(sname, {})
        if cur.get("applied"):
            dd = (date.today() - date.fromisoformat(cur["applied"])).days
            if dd < 14:
                lines.append(f"{sname}: cooldown ({dd}d since last change) - HOLD")
                continue
        inc_ex = (tuple(cur["exits"].values()) if isinstance(cur.get("exits"), dict) and
                  len(cur.get("exits", {})) == 3 else DEFAULT_EXITS.get(sname, (-50.0, 50.0, 0.20)))
        inc_ex = (float(inc_ex[0]) if inc_ex[0] < 0 else -float(inc_ex[0]),
                  float(inc_ex[1]), float(inc_ex[2]))
        try:
            inc_i = EXITS.index(inc_ex)
        except ValueError:
            lines.append(f"{sname}: incumbent exits {inc_ex} off-grid - report only")
            continue
        cells = []
        for ei in range(len(EXITS)):
            s = cellstat(srows, ei)
            if s:
                cells.append((ei, s))
        if not cells:
            lines.append(f"{sname}: thin ({len(srows)} trades on incumbent pool) - HOLD")
            continue
        # the hover: only configs ONE knob-step from the incumbent are reachable this week
        adjacent = [(ei, s) for ei, s in cells
                    if s["ok"] and knob_delta(EXITS[ei], EXITS[inc_i]) == 1]
        best = max(adjacent, key=lambda x: x[1]["t"], default=None)
        if not best:
            lines.append(f"{sname}: no PASSing adjacent config - HOLD (sweet spot or thin)")
            continue
        pr = paired(srows, best[0], inc_i)
        if not (pr and pr["mean"] >= 3.0 and pr["t"] >= 2.0):
            g = f"{pr['mean']:+.1f} t{pr['t']:+.2f}" if pr else "thin"
            lines.append(f"{sname}: adjacent best beats incumbent by {g} - below the bar, HOLD")
            continue
        st, tgg, gv = EXITS[best[0]]
        lines.append(f"{sname}: APPLY exits {inc_ex} -> ({st},{tgg},{gv}) "
                     f"paired +{pr['mean']:.1f}/day t{pr['t']:.2f} over {pr['days']}d")
        if not DRY:
            hist = cur.get("history", [])
            hist.append({"date": today, "from": list(inc_ex), "to": [st, tgg, gv],
                         "paired_gain": round(pr["mean"], 1), "paired_t": round(pr["t"], 2)})
            tuning[sname] = {"exits": {"stop": abs(st), "trig": tgg, "give": gv},
                             "applied": today, "history": hist[-10:]}
            changed = True
    print("\n".join(lines), flush=True)
    if changed and not DRY:
        json.dump(spec, open("fade_book_spec.json", "w"), indent=1)
        subprocess.run("git add fade_book_spec.json && git commit -qm "
                       "'tuner apply: damped weekly exit tuning [skip ci]' && "
                       "git pull -q --rebase -X ours && git push -q", shell=True)
        tg("TUNER APPLY:\n" + "\n".join(lines))
    elif not DRY:
        tg("TUNER APPLY: no change this week - every strategy holding at its spot.\n" +
           "\n".join(lines[1:]))
    print("TUNER APPLY COMPLETE", flush=True)


if __name__ == "__main__":
    main()

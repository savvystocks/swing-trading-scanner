"""V10 Research Sandbox - live scan autopsy (STANDALONE diagnostic).

Answers "why did today yield 0 trades?" by ingesting the committed funnel_*.jsonl log and
attributing every rejection to a funnel phase, checking the regime lock, sniffing the CI
logs for Alpaca 429/rate-limit errors, and - if the market has been NEUTRAL-locked for
more than 4 consecutive scan cycles - recommending the non-directional yield loosening
(pre-earnings calendars / iron condors) so the engine isn't idle in chop.

Reads V9 funnel logs read-only; imports the sandbox upgrades for the loosening demo only.
Run:  python v10_today_diagnostic.py [path/to/funnel_YYYY-MM-DD.jsonl]
"""

import os
import re
import sys
import glob
import json
import subprocess
from collections import Counter
from datetime import datetime

FUNNEL_DIR = os.path.join("data", "ambush_logs")
NEUTRAL_LOCK_CYCLES = 4

# map a free-text rejection reason to a funnel phase
REASON_PHASES = [
    ("Regime / positioning lock", lambda r: "regime bias" in r or "does not match" in r or "directional" in r),
    ("Spread (bid-ask > 1.5%)", lambda r: "bid-ask" in r),
    ("Contract RVOL (< 5x)", lambda r: "rvol" in r.lower()),
    ("Positioning signals (< min)", lambda r: "positioning signal" in r),
    ("Earnings blackout", lambda r: "earnings" in r.lower() or "blackout" in r.lower()),
    ("Sector cap", lambda r: "sector risk" in r.lower() or "sector cap" in r.lower()),
    ("No structurable combo", lambda r: "structurable" in r.lower() or "defined risk" in r.lower()),
]


def load_runs(path=None):
    if path is None:
        cand = os.path.join(FUNNEL_DIR, f"funnel_{datetime.utcnow().date().isoformat()}.jsonl")
        path = cand if os.path.exists(cand) else None
        if path is None:
            files = sorted(glob.glob(os.path.join(FUNNEL_DIR, "funnel_*.jsonl")))
            path = files[-1] if files else None
    runs = []
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    runs.append(json.loads(line))
                except Exception:
                    pass
    return runs, path


def funnel_report(runs):
    cheap, gate, decisions = Counter(), Counter(), Counter()
    total_cand = total_surv = n_enriched = alerts = 0
    for run in runs:
        total_cand += run.get("candidates", 0)
        total_surv += run.get("survivors", 0)
        alerts += run.get("alerts", 0)
        for k, v in (run.get("cheap_rejects") or {}).items():
            cheap[k] += v
        for e in run.get("enriched", []):
            n_enriched += 1
            decisions[e.get("decision", "?")] += 1
            matched = set()
            for reason in (e.get("reasons") or []):
                for label, fn in REASON_PHASES:
                    if fn(reason):
                        matched.add(label)
            for label in matched:
                gate[label] += 1
    return {"runs": len(runs), "candidates": total_cand, "survivors": total_surv,
            "enriched": n_enriched, "alerts": alerts,
            "cheap_rejects": cheap, "gate_blocks": gate, "decisions": decisions}


def regime_lock_analysis(runs, threshold=NEUTRAL_LOCK_CYCLES):
    regimes = [run.get("regime") for run in runs]
    consec = 0
    for reg in reversed(regimes):
        if reg == "C":
            consec += 1
        else:
            break
    return {"regimes": regimes, "consecutive_neutral": consec,
            "lock_triggered": consec > threshold, "threshold": threshold}


def check_alpaca_429(workflow="live_scan.yml", max_runs=6):
    """Best-effort: scan today's live-scan CI run logs for genuine rate-limit / data errors.
    The benign resolver line 'Alpaca creds ... rejected (401) - trying fallback' is EXCLUDED
    (that is the paper-key fallback working as designed, not a rate-limit)."""
    try:
        out = subprocess.run(["gh", "run", "list", f"--workflow={workflow}", "--limit", "10",
                              "--json", "databaseId,createdAt,conclusion"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        data = json.loads(out.stdout or "[]")
    except Exception as e:
        return {"error": f"could not query CI ({type(e).__name__})"}
    today = datetime.utcnow().date().isoformat()
    todays = [r for r in data if (r.get("createdAt") or "").startswith(today)]
    checked, flagged, detail = 0, 0, []
    for r in todays[:max_runs]:
        try:
            log = subprocess.run(["gh", "run", "view", str(r["databaseId"]), "--log"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            txt = (log.stdout or "").lower()
        except Exception:
            continue
        checked += 1
        # precise patterns only: bare "429" matches timestamps/byte-counts (false positives).
        # require it adjacent to http/error/status/apierror, or the explicit phrases.
        rl = len(re.findall(r"rate.?limit|too many request|(?:http|error|status|apierror)[^\n]{0,6}429", txt))
        data_html = txt.count("apierror: <html>")
        if rl or data_html:
            flagged += 1
            detail.append({"run": r["databaseId"], "rate_limit_hits": rl, "alpaca_html_errors": data_html})
    return {"runs_checked": checked, "runs_with_ratelimit": flagged, "detail": detail}


def dynamic_loosen(lock):
    if not lock["lock_triggered"]:
        return {"engaged": False,
                "reason": f"{lock['consecutive_neutral']} consecutive NEUTRAL <= {lock['threshold']} "
                          f"-> directional gates stay normal (no loosening yet)"}
    return {"engaged": True,
            "reason": f"{lock['consecutive_neutral']} consecutive NEUTRAL cycles > {lock['threshold']} -> chop persists",
            "action": "enable NON-DIRECTIONAL yield to maintain trade volume",
            "structures": ["CALENDAR_SPREAD (pre-earnings IV harvest)", "IRON_CONDOR (range-bound premium)"]}


def main():
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    runs, path = load_runs(path_arg)

    print("=" * 72)
    print("V10 TODAY DIAGNOSTIC - live scan autopsy")
    print("=" * 72)
    print(f"funnel log: {path or '(none found)'} | run-records: {len(runs)}")
    if not runs:
        print("no funnel records to analyse (logging began 2026-06-24; stage the log from main).")
        return

    fr = funnel_report(runs)
    print(f"\nfunnel totals: candidates={fr['candidates']}  survivors(post cheap-pass)={fr['survivors']}  "
          f"enriched={fr['enriched']}  ALERTS={fr['alerts']}")

    print("\n--- Phase 1: _cheap_pass rejections (free fields) ---")
    for k, v in fr["cheap_rejects"].most_common():
        print(f"    {k:<26} {v}")

    print("\n--- Phase 2: gate blocks among enriched survivors (a candidate can hit several) ---")
    for k, v in fr["gate_blocks"].most_common():
        print(f"    {k:<28} {v}/{fr['enriched']}")
    print("    decision mix: " + ", ".join(f"{k}={v}" for k, v in fr["decisions"].most_common()))

    lock = regime_lock_analysis(runs)
    print("\n--- Suspect A: Regime lock ---")
    print(f"    regimes this session: {lock['regimes']}")
    print(f"    consecutive NEUTRAL cycles: {lock['consecutive_neutral']} (loosen threshold > {lock['threshold']})")
    print(f"    LOCK TRIGGERED: {lock['lock_triggered']}")

    print("\n--- Suspect B: RVOL gate ---")
    rvol_blocks = fr["gate_blocks"].get("Contract RVOL (< 5x)", 0)
    print(f"    {rvol_blocks}/{fr['enriched']} enriched survivors blocked by the 5x RVOL gate")

    print("\n--- Suspect C: Alpaca 429 / rate-limit trap ---")
    rl = check_alpaca_429()
    if rl.get("error"):
        print(f"    {rl['error']} (run `gh auth status`; benign resolver 401-fallback is excluded by design)")
    else:
        print(f"    checked {rl['runs_checked']} live-scan runs today | runs with rate-limit/data errors: "
              f"{rl['runs_with_ratelimit']}")
        for d in rl["detail"]:
            print(f"      run {d['run']}: 429/rate-limit={d['rate_limit_hits']} alpaca_html={d['alpaca_html_errors']}")

    print("\n--- Dynamic gate loosening (anti-idle in chop) ---")
    loose = dynamic_loosen(lock)
    if loose["engaged"]:
        print(f"    ENGAGED: {loose['reason']}")
        print(f"    {loose['action']} -> {loose['structures']}")
        try:
            from sandbox_v10_upgrades import pre_earnings_harvest
            demo = pre_earnings_harvest("NVDA", 14, 30.0, 1.7, True, "2026-07-08")
            print(f"    e.g. {demo['ticker']} -> {demo['structure']} (hard exit {demo['hard_exit_date']})")
        except Exception:
            pass
    else:
        print(f"    not engaged: {loose['reason']}")
        # show what it WOULD do if the lock held (today only has a few cycles so far)
        demo_lock = {"consecutive_neutral": 5, "threshold": NEUTRAL_LOCK_CYCLES, "lock_triggered": True}
        d = dynamic_loosen(demo_lock)
        print(f"    [demo if 5 cycles] -> {d['action']}: {d['structures']}")


if __name__ == "__main__":
    main()

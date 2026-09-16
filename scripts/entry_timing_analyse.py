import json, math, os
from collections import defaultdict
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
rows = []
for l in open("reports/research/entry_timing_v1.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if "_meta" in r:
        META = r; continue
    rows.append(r)
ARMS = ["at_print", "at_close", "next_close"]
print(f"paired rows {len(rows):,} | days {len(set(r['day'] for r in rows))} | rule {META['rule']}")


def tstat(x):
    n = len(x)
    if n < 3:
        return 0.0
    m = sum(x) / n
    sd = (sum((v - m) ** 2 for v in x) / (n - 1)) ** 0.5
    return (m / (sd / math.sqrt(n))) if sd > 0 else 0.0


def daymeans(sel, key):
    d = defaultdict(list)
    for r in sel:
        v = r.get(key)
        if v is not None:
            d[r["day"]].append(v)
    return {k: sum(v) / len(v) for k, v in d.items()}, sum(len(v) for v in d.values())


def table(label, sel):
    print(f"\n--- {label}  (n={len(sel):,}) ---")
    print(f"  {'arm':<12} {'exit':<7} {'days':>5} {'trades':>7} {'mean/day':>10} {'t':>7} {'win':>6} {'halves':>17}")
    for ex in ("daily", "hourly"):
        for a in ARMS:
            dm, n = daymeans(sel, f"{a}_{ex}")
            if len(dm) < 30:
                print(f"  {a:<12} {ex:<7} thin"); continue
            days = sorted(dm); v = [dm[k] for k in days]; h = len(v) // 2
            wins = sum(1 for r in sel if (r.get(f'{a}_{ex}') or 0) > 0)
            print(f"  {a:<12} {ex:<7} {len(days):>5} {n:>7} {sum(v)/len(v):>+9.2f}% {tstat(v):>+7.2f} "
                  f"{wins/max(1,n):>5.1%} {sum(v[:h])/max(1,h):>+8.1f}/{sum(v[h:])/max(1,len(v)-h):>+7.1f}")
    # the pre-registered paired comparison: same contract-day, print vs close, HOURLY exits
    for ex in ("hourly", "daily"):
        d = defaultdict(list)
        for r in sel:
            a, b = r.get(f"at_print_{ex}"), r.get(f"at_close_{ex}")
            if a is not None and b is not None:
                d[r["day"]].append(b - a)
        if len(d) >= 30:
            days = sorted(d); v = [sum(d[k]) / len(d[k]) for k in days]; h = len(v) // 2
            print(f"  PAIRED close-minus-print ({ex}): {sum(v)/len(v):+7.2f} pts/day  t {tstat(v):+6.2f}  "
                  f"halves {sum(v[:h])/max(1,h):+7.1f}/{sum(v[h:])/max(1,len(v)-h):+7.1f}  days {len(days)}")
        d2 = defaultdict(list)
        for r in sel:
            a, b = r.get(f"at_print_{ex}"), r.get(f"next_close_{ex}")
            if a is not None and b is not None:
                d2[r["day"]].append(b - a)
        if len(d2) >= 30:
            days = sorted(d2); v = [sum(d2[k]) / len(d2[k]) for k in days]; h = len(v) // 2
            print(f"  PAIRED nextclose-minus-print ({ex}): {sum(v)/len(v):+7.2f} pts/day  t {tstat(v):+6.2f}  "
                  f"halves {sum(v[:h])/max(1,h):+7.1f}/{sum(v[h:])/max(1,len(v)-h):+7.1f}")


table("ALL qualifying contract-days", rows)
print("\n=== BY ASK BAND (the slice where the flip appeared) ===")
for lo, hi in ((0.30, 2), (2, 4), (4, 6), (6, 9.9), (9.9, 16), (16, 1e9)):
    sel = [r for r in rows if r.get("at_print") and lo <= r["at_print"] < hi]
    if len(sel) >= 300:
        table(f"ask ${lo}-{hi}", sel)
print("\n=== CALLS ONLY, affordable band ===")
sel = [r for r in rows if r.get("side") == "C" and r.get("at_print") and 0.30 <= r["at_print"] <= 9.90]
table("calls, ask $0.30-9.90", sel)
print("\n=== EXIT-RESOLUTION ARTEFACT: how often does hourly see a stop daily misses? ===")
for lo, hi, lab in ((0.30, 4, "cheap $0.30-4"), (4, 9.9, "mid $4-9.90"), (9.9, 1e9, "pricey $9.90+")):
    sel = [r for r in rows if r.get("at_print") and lo <= r["at_print"] < hi]
    if not sel:
        continue
    for a in ("at_print",):
        ds = sum(1 for r in sel if r.get(f"{a}_daily_why") == "stop")
        hs = sum(1 for r in sel if r.get(f"{a}_hourly_why") == "stop")
        both = sum(1 for r in sel if r.get(f"{a}_daily") is not None and r.get(f"{a}_hourly") is not None)
        gap = [r[f"{a}_hourly"] - r[f"{a}_daily"] for r in sel
               if r.get(f"{a}_daily") is not None and r.get(f"{a}_hourly") is not None]
        print(f"  {lab:<16} n {both:>6}  stops: daily {ds/max(1,len(sel)):>5.1%} hourly {hs/max(1,len(sel)):>5.1%}  "
              f"mean hourly-minus-daily {sum(gap)/max(1,len(gap)):+7.2f} pts")

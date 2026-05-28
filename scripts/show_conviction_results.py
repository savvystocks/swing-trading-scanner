import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCAN = "data/results/catalyst_2026-05-23.json"

with open(SCAN, encoding="utf-8") as f:
    scan = json.load(f)

all_picks = []
for tier in ("A++", "A+", "A"):
    for p in scan["aa_results"].get(tier, []):
        all_picks.append(p)


def conv(p):
    return (p.get("_conviction") or {}).get("score", 0) or 0


def overall(p):
    return (p.get("_overall_score") or {}).get("score", 0) or 0


all_picks.sort(key=lambda p: -conv(p))

# Tier breakdown
tiers = {"TAKE_HIGH": 0, "TAKE": 0, "WATCH": 0, "SKIP": 0, "AVOID": 0}
for p in all_picks:
    t = (p.get("_conviction") or {}).get("tier", "UNKNOWN")
    if t in tiers:
        tiers[t] += 1
print("=" * 80)
print(f"Scan date: {scan.get('scan_date')}  Total Tier A: {len(all_picks)}")
print(f"Conviction tier breakdown: TAKE_HIGH={tiers['TAKE_HIGH']} TAKE={tiers['TAKE']} WATCH={tiers['WATCH']} SKIP={tiers['SKIP']} AVOID={tiers['AVOID']}")
print("=" * 80)
print()

print("TOP 10 BY CONVICTION SCORE")
print()
print("{:<6} {:<5} {:>5} {:>5} {:<11} {:<10}".format("Tkr", "Tier", "Conv", "Ovr", "Conv tier", "LLM"))
print("-" * 55)
for p in all_picks[:10]:
    c = p.get("_conviction") or {}
    h = p.get("haiku_synthesis") or {}
    print("{:<6} {:<5} {:>5.0f} {:>5.0f} {:<11} {:<10}".format(
        p.get("ticker", "?"),
        p.get("_aa_tier", "?"),
        conv(p),
        overall(p),
        c.get("tier", "?"),
        f"{(h.get('verdict') or '--')[:4]} {h.get('confidence_pct') or 0}%",
    ))
print()

print("=" * 80)
print("COMPONENT BREAKDOWN FOR TOP 3 (Conviction = sum of weighted components)")
print("=" * 80)
print()
for p in all_picks[:3]:
    c = p.get("_conviction") or {}
    print(f"--- {p.get('ticker')} (Conviction {c.get('score')}/100, tier {c.get('tier')}) ---")
    comps = c.get("components") or {}
    weights = c.get("weights") or {}
    for k in ("llm_and_overall", "insider", "pead", "buyback_guidance", "options_flow", "stage2", "analyst", "whisper", "whalewisdom", "trends"):
        score = comps.get(k, 0)
        weight = int(weights.get(k, 0) * 100)
        marker = " <-- STRONG" if score >= 75 else ""
        print(f"  {k:18s} {score:>3} x {weight:>2}% = {score * weights.get(k, 0):>5.1f}{marker}")
    print()

print("=" * 80)
print("TAKE-GRADE PICKS (Conviction >= 70)")
print("=" * 80)
take_picks = [p for p in all_picks if conv(p) >= 70]
if not take_picks:
    print("No TAKE-grade picks today.")
else:
    for p in take_picks:
        c = p.get("_conviction") or {}
        comps = c.get("components") or {}
        strong_components = [k.replace("_", "/").upper() for k, v in comps.items() if v >= 75]
        h = p.get("haiku_synthesis") or {}
        print(f"  {p.get('ticker'):6} Conv={c.get('score'):>3} Tier={p.get('_aa_tier'):4} LLM={(h.get('verdict') or '--')[:4]} {h.get('confidence_pct') or 0}%")
        if strong_components:
            print(f"         Strong: {', '.join(strong_components[:4])}")
        cats = p.get("catalysts") or []
        cat_keys = [c.get("key") for c in cats[:3] if isinstance(c, dict)]
        if cat_keys:
            print(f"         Catalysts: {', '.join(cat_keys)}")
        print()

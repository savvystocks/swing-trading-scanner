import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.overall_score import compute_overall_score


path = "data/results/catalyst_2026-05-16.json"
with open(path, "r") as f:
    scan = json.load(f)

aa = scan["aa_results"]
all_picks = []
for tier in ("A++", "A+", "A"):
    for p in aa.get(tier, []):
        p["_overall_score"] = compute_overall_score(p)
        all_picks.append(p)

with open(path, "w") as f:
    json.dump(scan, f, indent=2, default=str)

all_picks.sort(key=lambda p: -p["_overall_score"]["score"])
print("Top 10 after LLM-aware bug fix:")
print()
hdr = ("Tkr", "Tier", "Overall", "Verdict", "PoP%", "LLM_v", "LLM_c", "Bear_v", "Bear_c", "Trap")
print("{:<6} {:<5} {:<8} {:<18} {:<5} {:<6} {:<6} {:<8} {:<7} {:<5}".format(*hdr))
print("-" * 80)
for p in all_picks[:10]:
    o = p["_overall_score"]
    forensic = p.get("unified_forensic") or p.get("haiku_synthesis") or {}
    bear = p.get("bear_verification") or {}
    row = (
        p["ticker"],
        p["_aa_tier"],
        o["score"],
        o["verdict"],
        o["probability_of_profit_pct"],
        forensic.get("verdict") or "--",
        forensic.get("confidence_pct") or "-",
        bear.get("bear_verdict") or "--",
        bear.get("bear_conviction_pct") or "-",
        "YES" if bear.get("is_this_trade_a_trap") else "no",
    )
    print("{:<6} {:<5} {:<8} {:<18} {:<5} {:<6} {:<6} {:<8} {:<7} {:<5}".format(*row))

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ANTHROPIC_API_KEY missing - cannot backfill. Set it then re-run.")
    sys.exit(1)

from src.catalyst.unified_forensic import apply_haiku_synthesis, apply_bear_case_verification
from src.catalyst.overall_score import compute_overall_score


path = "data/results/catalyst_2026-05-16.json"
with open(path, "r") as f:
    scan = json.load(f)

aa = scan["aa_results"]
all_picks = []
for tier in ("A++", "A+", "A"):
    for p in aa.get(tier, []):
        all_picks.append(p)

def _overall(p):
    v = (p.get("_overall_score") or {}).get("score")
    try:
        return float(v) if v is not None else -1
    except (TypeError, ValueError):
        return -1

candidates = [p for p in all_picks if _overall(p) >= 50]
without_llm = [p for p in candidates if not (p.get("haiku_synthesis") or {}).get("verdict")]

print(f"Total picks Overall>=50: {len(candidates)}")
print(f"Need backfill (no LLM yet): {len(without_llm)}")
print(f"Tickers to process: {[p['ticker'] for p in without_llm]}")
print()

if without_llm:
    print("Running Haiku bull pass...")
    apply_haiku_synthesis(without_llm, max_calls=len(without_llm), verbose=True)
    print()
    print("Running Haiku bear verification...")
    apply_bear_case_verification(without_llm, max_calls=len(without_llm), verbose=True)
    print()

print("Recomputing Overall scores for all candidates...")
for p in all_picks:
    p["_overall_score"] = compute_overall_score(p)

with open(path, "w") as f:
    json.dump(scan, f, indent=2, default=str)

print()
all_picks.sort(key=lambda p: -_overall(p))
print("Top 15 after full LLM backfill:")
print()
print("{:<6} {:<5} {:<8} {:<18} {:<5} {:<7} {:<5} {:<8} {:<5}".format("Tkr", "Tier", "Overall", "Verdict", "PoP%", "LLM_v", "Conf", "Bear", "Trap"))
print("-" * 75)
for p in all_picks[:15]:
    o = p["_overall_score"]
    h = p.get("haiku_synthesis") or {}
    b = p.get("bear_verification") or {}
    print("{:<6} {:<5} {:<8} {:<18} {:<5} {:<7} {:<5} {:<8} {:<5}".format(
        p["ticker"],
        p["_aa_tier"],
        o["score"],
        o["verdict"][:18],
        o["probability_of_profit_pct"],
        h.get("verdict") or "--",
        h.get("confidence_pct") or "-",
        b.get("bear_verdict") or "--",
        "YES" if b.get("is_this_trade_a_trap") else "no",
    ))

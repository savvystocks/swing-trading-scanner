import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with open("data/results/catalyst_2026-05-16.json", "r") as f:
    scan = json.load(f)

aa = scan["aa_results"]
rddt = None
for tier in ("A++", "A+", "A", "REJECT"):
    for p in aa.get(tier, []):
        if p.get("ticker") == "RDDT":
            rddt = p
            break

if not rddt:
    print("RDDT not found in scan.")
    sys.exit(1)

print("=" * 72)
print("RDDT FULL BREAKDOWN")
print("=" * 72)
print(f"Name: {rddt.get('name')}")
print(f"Sector: {rddt.get('sector')}  /  Industry: {rddt.get('industry')}")
print(f"Price: ${rddt.get('price')}")
print(f"Market cap: ${rddt.get('market_cap')}")
print(f"Tier: {rddt.get('_aa_tier')}")
print()
print(f"Returns: 5d {rddt.get('ret_5d')}%  30d {rddt.get('ret_30d')}%  90d {rddt.get('ret_90d')}%")
print(f"Above 50dMA: {rddt.get('above_50dma')}  Above 200dMA: {rddt.get('above_200dma')}")
print(f"Pct above 50dMA: {rddt.get('pct_above_50dma')}%")
print()
print("CATALYSTS:")
for c in rddt.get("catalysts", []):
    print(f"  - {c.get('key')}: {(c.get('details') or '')[:80]}")
print()
print(f"Stacked score: {rddt.get('_stacked_score')}")
print(f"Category count: {rddt.get('_category_count')}")
print(f"Active categories: {rddt.get('_active_categories')}")
print()

overall = rddt.get("_overall_score") or {}
print(f"OVERALL SCORE: {overall.get('score')} / 100  ({overall.get('verdict')})")
print(f"Plain English: {overall.get('plain_english')}")
print(f"Probability of profit: {overall.get('probability_of_profit_pct')}%")
print("Components:")
for k, v in (overall.get("components") or {}).items():
    print(f"  {k:24s} {v}")
print()

surv = rddt.get("_survival_score") or {}
print(f"SURVIVAL: {surv.get('score')} / 100  ({surv.get('verdict')})")
print(f"  Action: {surv.get('action')}")
if surv.get("kill_risks"):
    print("  Kill risks:")
    for kr in surv["kill_risks"]:
        print(f"    - {kr}")
print()

haiku = rddt.get("haiku_synthesis") or {}
print(f"HAIKU LLM VERDICT: {haiku.get('verdict')}  (confidence {haiku.get('confidence_pct')}%)")
print()
print("Bull thesis from Haiku:")
print(f"  {haiku.get('bull_thesis', '(none)')}")
print()
print("Bear thesis from Haiku:")
print(f"  {haiku.get('bear_thesis', '(none)')}")
print()
print("What kills this trade:")
print(f"  {haiku.get('what_kills_this_trade', '(none)')}")
print()
print("Warning signs to watch:")
for w in (haiku.get("warning_signs") or []):
    print(f"  - {w}")
print()
print(f"Synthesis note: {haiku.get('synthesis_note', '')}")
print()

bear = rddt.get("bear_verification") or {}
print(f"BEAR VERIFICATION: {bear.get('bear_verdict')} ({bear.get('bear_conviction_pct')}% conviction)")
if bear.get("killer_thesis"):
    print(f"  Killer thesis: {bear.get('killer_thesis')}")
if bear.get("is_this_trade_a_trap"):
    print("  ** TRAP FLAGGED **")
print()

eq = rddt.get("_earnings_quality") or {}
print(f"EARNINGS QUALITY: {eq.get('rating')} ({eq.get('earnings_quality_score')}/100)")
if eq.get("flags"):
    print(f"  Flags: {eq.get('flags')}")
print()

vol = rddt.get("_vol_microstructure") or {}
riv = vol.get("realized_vs_implied") or {}
sk = vol.get("skew") or {}
if riv.get("note"):
    print(f"VOL: {riv.get('note')}")
if sk.get("bias_note"):
    print(f"SKEW: {sk.get('bias_note')}")

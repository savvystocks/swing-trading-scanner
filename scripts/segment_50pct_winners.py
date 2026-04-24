import json
from collections import Counter, defaultdict
import pandas as pd

with open("data/results/50pct_movers_analyzed.json") as f:
    winners = json.load(f)

print(f"Total analyzed: {len(winners)}")

quality = []
for w in winners:
    cp = w["current_price"]
    pk = w["peak_price"]
    if pk > 0 and cp/pk >= 0.85:
        quality.append(w)
print(f"Quality subset (still within 15% of peak): {len(quality)}")

scanner_eligible = []
for w in winners:
    if w["pillars_pre"]["p1_trend"] in ("PASS","PASS_BONUS") and \
       w["pillars_pre"]["p4_rs"] in ("PASS","PASS_BONUS") and \
       w["fundamentals"]["market_cap_b"] >= 0.5 and \
       w["gates_pre"]["g6_liq"] in ("PASS","PASS_BONUS"):
        scanner_eligible.append(w)
print(f"Would-pass-our-scanner (P1+P4+G6): {len(scanner_eligible)}")

options_viable = []
for w in winners:
    if w["fundamentals"]["market_cap_b"] >= 2.0:
        options_viable.append(w)
print(f"Options-viable (mcap >=$2B for decent chain): {len(options_viable)}")

options_and_scanner = []
for w in winners:
    if w["pillars_pre"]["p1_trend"] in ("PASS","PASS_BONUS") and \
       w["pillars_pre"]["p4_rs"] in ("PASS","PASS_BONUS") and \
       w["fundamentals"]["market_cap_b"] >= 2.0:
        options_and_scanner.append(w)
print(f"Scanner + options-viable: {len(options_and_scanner)}")

print("\n" + "="*70)
print("SEGMENT 1: CLEAN BREAKOUTS (passed P1 trend + P4 RS, mcap >=$2B)")
print("="*70)
print("These are the ones our scanner would have flagged AND have usable options.\n")
print(f"{'TICKER':10s} {'MOVE%':>6s} {'DAYS':>4s} {'MCAP':>6s} {'SECTOR':16s} {'LB':>3s} {'EARN':>4s} {'NAME':28s}")
for w in sorted(options_and_scanner, key=lambda x: -x["move_pct"]):
    lb = w["lane_b_count_pre"]
    earn = "Y" if w["near_earnings"] else "-"
    print(f"{w['ticker']:10s} {w['move_pct']:>5.1f}% {w['days_to_peak']:>4d} {w['fundamentals']['market_cap_b']:>5.1f}B {(w['sector'] or '')[:16]:16s} {lb:>3d} {earn:>4s} {(w['name'] or '')[:28]:28s}")

print("\n" + "="*70)
print("SEGMENT 2: EARNINGS-TRIGGERED (earnings within +/-10 days of move)")
print("="*70)
earn_trig = [w for w in winners if w["near_earnings"]]
print(f"Count: {len(earn_trig)}/{len(winners)} ({len(earn_trig)*100/len(winners):.1f}%)\n")
print(f"{'TICKER':10s} {'MOVE%':>6s} {'SURPRISE':>8s} {'DAYS':>4s} {'MCAP':>6s} {'SECTOR':16s} {'NAME':28s}")
for w in sorted(earn_trig, key=lambda x: -x["move_pct"])[:25]:
    surprise = w["near_earnings"].get("surprise_pct") if w["near_earnings"] else None
    surprise_s = f"{surprise}%" if surprise is not None else "?"
    print(f"{w['ticker']:10s} {w['move_pct']:>5.1f}% {surprise_s:>8s} {w['near_earnings'].get('days_from_entry','?'):>4} {w['fundamentals']['market_cap_b']:>5.1f}B {(w['sector'] or '')[:16]:16s} {(w['name'] or '')[:28]:28s}")

print("\n" + "="*70)
print("SEGMENT 3: SHORT SQUEEZE CANDIDATES (P7 passed pre-move)")
print("="*70)
p7_fires = [w for w in winners if w["pillars_pre"]["p7_squeeze"] in ("PASS","PASS_BONUS")]
print(f"Count: {len(p7_fires)}/{len(winners)} ({len(p7_fires)*100/len(winners):.1f}%)\n")

print("\n" + "="*70)
print("SEGMENT 4: QUALITY WINNERS STILL HOLDING GAIN (within 15% of peak)")
print("="*70)
print(f"Count: {len(quality)}/{len(winners)}\n")
print(f"{'TICKER':10s} {'MOVE%':>6s} {'MCAP':>6s} {'P1':>4s} {'P4':>4s} {'P7':>4s} {'LB':>3s} {'EARN':>4s} {'NAME':28s}")
for w in sorted(quality, key=lambda x: -x["move_pct"])[:40]:
    p1 = "P" if w["pillars_pre"]["p1_trend"] in ("PASS","PASS_BONUS") else "F"
    p4 = "P" if w["pillars_pre"]["p4_rs"] in ("PASS","PASS_BONUS") else "F"
    p7 = "P" if w["pillars_pre"]["p7_squeeze"] in ("PASS","PASS_BONUS") else "F"
    lb = w["lane_b_count_pre"]
    earn = "Y" if w["near_earnings"] else "-"
    print(f"{w['ticker']:10s} {w['move_pct']:>5.1f}% {w['fundamentals']['market_cap_b']:>5.1f}B {p1:>4s} {p4:>4s} {p7:>4s} {lb:>3d} {earn:>4s} {(w['name'] or '')[:28]:28s}")

print("\n" + "="*70)
print("THE BIG PICTURE: PRE-MOVE SIGNATURE DISTRIBUTION")
print("="*70)

stats = {
    "All winners (n=295)": winners,
    "Quality (still holding) (n={})".format(len(quality)): quality,
    "Scanner + options ($2B+, P1+P4) (n={})".format(len(options_and_scanner)): options_and_scanner,
    "Earnings-triggered (n={})".format(len(earn_trig)): earn_trig,
}

header = f"{'METRIC':35s}  "
for k in stats:
    header += f"{k[:22]:>22s}  "
print(header)

def pct(lst, check):
    if not lst: return "n/a"
    c = sum(1 for x in lst if check(x))
    return f"{c*100/len(lst):>5.1f}%"

rows = [
    ("P1 Trend Template pass", lambda w: w["pillars_pre"]["p1_trend"] in ("PASS","PASS_BONUS")),
    ("P2 Vol Squeeze pass", lambda w: w["pillars_pre"]["p2_vol"] in ("PASS","PASS_BONUS")),
    ("P3 CAN-SLIM pass", lambda w: w["pillars_pre"]["p3_canslim"] in ("PASS","PASS_BONUS")),
    ("P4 RS vs SPY pass", lambda w: w["pillars_pre"]["p4_rs"] in ("PASS","PASS_BONUS")),
    ("P6 Earnings Revision pass", lambda w: w["pillars_pre"]["p6_erm"] in ("PASS","PASS_BONUS")),
    ("P7 Short Squeeze pass", lambda w: w["pillars_pre"]["p7_squeeze"] in ("PASS","PASS_BONUS")),
    ("Any Lane B fired", lambda w: w["lane_b_count_pre"] >= 1),
    ("2+ Lane B fired", lambda w: w["lane_b_count_pre"] >= 2),
    ("Near earnings +/-10d", lambda w: w["near_earnings"] is not None),
    ("Insider buys pre-move", lambda w: w["insider_pre_90d"]["buys"] > 0),
    ("Insider cluster 3+", lambda w: w["insider_pre_90d"]["buys"] >= 3),
    ("Above 50d MA pre-move", lambda w: (w["pre_move_snapshot"]["pct_above_50d"] or 0) > 0),
    ("Within 20% of 52w high", lambda w: (w["pre_move_snapshot"]["pct_from_52w_high"] or -99) > -20),
    ("Below 200d MA (broken)", lambda w: (w["pre_move_snapshot"]["pct_above_200d"] or 0) < 0),
    ("Mcap <$2B", lambda w: w["fundamentals"]["market_cap_b"] < 2),
    ("Mcap $2B-$10B", lambda w: 2 <= w["fundamentals"]["market_cap_b"] < 10),
    ("Mcap >$10B", lambda w: w["fundamentals"]["market_cap_b"] >= 10),
    ("Sector: Health Care", lambda w: w["sector"] == "Health Care"),
    ("Sector: Info Tech", lambda w: w["sector"] == "Information Technology"),
    ("Sector: Industrials", lambda w: w["sector"] == "Industrials"),
    ("Sector: Energy", lambda w: w["sector"] == "Energy"),
]

for label, check in rows:
    row = f"{label:35s}  "
    for k, lst in stats.items():
        row += f"{pct(lst, check):>22s}  "
    print(row)

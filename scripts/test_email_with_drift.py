"""Render the May 25 email with drift alerts injected to verify visual output."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Clear seen cache so alerts fire fresh for this render test
seen_path = "data/paper_trades/drift_alerts_seen.json"
if os.path.exists(seen_path):
    os.remove(seen_path)

from src.catalyst.conviction_drift import check_drift
from src.catalyst.conviction_trend import apply_trends
from src.catalyst.unified_email import render_unified_email


with open("data/results/catalyst_2026-05-25.json", encoding="utf-8") as f:
    scan = json.load(f)

apply_trends(scan, verbose=True)

# Re-check drift (won't be in JSON because scan was saved before we wired this in)
alerts = check_drift(scan, verbose=False)
scan["conviction_drift_alerts"] = alerts
print(f"Drift alerts: {len(alerts)}")
for a in alerts:
    print(f"  [{a['severity']}] {a['ticker']} {a['alert_type']}")

aa_results = scan.get("aa_results") or {}
aa_picks = scan.get("aa_picks") or {}
aa_rejections = scan.get("aa_rejections") or []

html = render_unified_email(scan, aa_results, aa_picks, aa_rejections, drift_alerts=alerts)
out_path = "data/results/test_email_with_drift.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"\nWrote {out_path}  ({len(html)} bytes)")

# Quick check: is the EXIT WARNINGS section in the output?
if "EXIT WARNINGS" in html:
    print("EXIT WARNINGS section rendered correctly")
else:
    print("WARNING: EXIT WARNINGS section NOT in output")

if "ETOR" in html:
    print("ETOR appears in output")

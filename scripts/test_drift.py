"""Test the drift detector against the May 23 -> May 25 ETOR flip case."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.catalyst.conviction_drift import check_drift, format_drift_alerts_text


print("Loading May 25 scan (where ETOR flipped CALL->PUT)...")
with open("data/results/catalyst_2026-05-25.json", encoding="utf-8") as f:
    scan = json.load(f)

print("Running drift check against journal (which has Friday May 23 entries)...")
print()
alerts = check_drift(scan, verbose=True)

print()
print("=" * 60)
print(f"ALERTS FIRED: {len(alerts)}")
print("=" * 60)

if alerts:
    for a in alerts:
        print(f"\n[{a['severity']}] {a['ticker']} ({a['alert_type']})")
        print(f"  {a['message']}")
        if a.get('entry_price') and a.get('current_price'):
            try:
                pct = (float(a['current_price']) - float(a['entry_price'])) / float(a['entry_price']) * 100
                print(f"  Price: ${a['entry_price']:.2f} -> ${a['current_price']:.2f} ({pct:+.1f}%)")
            except Exception:
                pass
else:
    print("No drift alerts. Something might be wrong with the detector.")

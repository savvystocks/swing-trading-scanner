import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.catalyst.macro_regime_detector import detect_macro_regime
from src.catalyst.macro_put_candidates import generate_macro_puts

print("=== MACRO REGIME ===")
r = detect_macro_regime()
print(f"Regime: {r['regime']} ({r['score']}/100)")
print(f"Label: {r['label']}")
print()
print("Components:")
for k, v in r["components"].items():
    print(f"  {k:30s} {v}")
print()
print("Notes:")
for n in r["notes"]:
    print(f"  - {n}")
print()
print("=== MACRO PUT CANDIDATES (if regime triggered) ===")
puts = generate_macro_puts(r, verbose=True)
print()
print(f"Generated {len(puts)} macro put candidates")
for p in puts:
    print(f"  {p['ticker']} @ ${p['price']:.2f} - bear_conv={p['_bear_conviction']['score']} - {p['_macro_put_rationale']}")

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.catalyst_performance import measure_catalyst_performance, suggest_weight_adjustments


def main():
    print("=== Catalyst Performance Refresh ===\n")
    perf = measure_catalyst_performance(lookback_days=90, verbose=True)
    if not perf:
        print("\nNo measured picks available. Run scans for 14+ days and let v4_paper_log measure outcomes first.")
        return

    print(f"\nWrote stats for {len(perf['catalyst_stats'])} catalyst types from {perf['total_picks_measured']} measured picks")

    suggestions = suggest_weight_adjustments(verbose=True)

    print("\n=== Done ===")
    print("Review suggestions above. To auto-apply weight changes to scoring.py:")
    print("  python scripts/apply_catalyst_weight_updates.py --confirm")


if __name__ == "__main__":
    main()

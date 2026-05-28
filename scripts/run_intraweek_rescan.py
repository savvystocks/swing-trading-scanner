"""Lightweight intra-week rescan: catalyst-only, no full universe scoring.

Use when something material happens between daily emails (CPI shock, FOMC,
earnings spike, breaking news). Reads today's existing scan results,
re-fetches news + EDGAR for the top 50 picks, recomputes catalyst-driven
modules, runs the conviction + drift check, and emits a focused email.

Targets a 3-5 minute runtime vs the 21-minute full daily scan.

Trigger options:
  - Manual: `python scripts/run_intraweek_rescan.py`
  - With email: SEND_EMAIL=1 python scripts/run_intraweek_rescan.py
  - Specific scan date: SCAN_DATE=2026-05-28 python scripts/run_intraweek_rescan.py
"""

import os
import sys
import json
import glob
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "data", "results")


def find_today_scan():
    today = datetime.utcnow().date().strftime("%Y-%m-%d")
    target = os.path.join(RESULTS_DIR, f"catalyst_{today}.json")
    if os.path.exists(target):
        return target, today
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, "catalyst_*.json")), reverse=True)
    files = [f for f in files if "_email" not in os.path.basename(f)]
    if not files:
        return None, None
    p = files[0]
    return p, os.path.basename(p).replace("catalyst_", "").replace(".json", "")


def refresh_catalysts(scan, top_n=50, verbose=True):
    from src.eodhd import EODHDClient
    from src.catalyst.edgar import EDGARClient, collect_material_signals, collect_form4_cluster
    from src.catalyst.news import fetch_recent_news
    from src.catalyst.signals import run_all_catalyst_detectors, detector_hits_to_signal_entries, append_signals_and_rescore
    from src.catalyst.scoring import CATALYST_TIERS, WEIGHT_CATALYST, cross_confirmation_score

    client = EODHDClient()
    edgar = EDGARClient()

    all_picks_flat = []
    aa = scan.get("aa_results") or {}
    for tier in ("A++", "A+", "A"):
        for p in aa.get(tier, []) or []:
            all_picks_flat.append(p)
    top = all_picks_flat[:top_n]
    if verbose:
        print(f"  intraweek refresh: re-pulling news/EDGAR for top {len(top)} picks")

    try:
        fresh_material = collect_material_signals(edgar, days_back=1)
        fresh_insider = collect_form4_cluster(edgar, days_back=2, min_buyers=3)
        if verbose:
            print(f"  EDGAR intraweek: {len(fresh_material)} material + {len(fresh_insider)} insider clusters")
    except Exception as e:
        fresh_material = {}
        fresh_insider = {}
        if verbose:
            print(f"  EDGAR intraweek failed: {type(e).__name__}: {e}")

    signals_added = 0
    for p in top:
        ticker = p.get("ticker")
        eodhd_ticker = p.get("eodhd_ticker") or (f"{ticker}.US" if ticker else None)
        if not ticker:
            continue
        try:
            raw_news = fetch_recent_news(client, eodhd_ticker, max_age_days=1, limit=20)
            fund = None
            try:
                fund = client.fundamentals(eodhd_ticker)
            except Exception:
                fund = None
            detectors = run_all_catalyst_detectors(raw_news, fund)
            entries = detector_hits_to_signal_entries(detectors)
            if entries:
                changed = append_signals_and_rescore(p, entries, CATALYST_TIERS, WEIGHT_CATALYST)
                if changed:
                    added = p.get("_signals_added") or []
                    signals_added += len(added)
        except Exception:
            pass

    if verbose:
        print(f"  intraweek: {signals_added} new catalyst signals added")
    return scan


def main():
    scan_path, scan_date = find_today_scan()
    if not scan_path:
        print("No scan JSON found in data/results")
        sys.exit(2)
    print(f"Loading scan from {scan_path}")

    with open(scan_path, "r", encoding="utf-8") as f:
        scan = json.load(f)

    refresh_catalysts(scan, top_n=50, verbose=True)

    try:
        from src.catalyst.signal_dedup import apply_signal_dedup
        from src.catalyst.conviction_score import apply_conviction_scores
        from src.catalyst.bear_conviction_score import apply_bear_conviction
        from src.catalyst.direction_picker import apply_directions
    except ImportError as e:
        print(f"Module import failed: {type(e).__name__}: {e}")
        sys.exit(2)

    aa = scan.get("aa_results") or {}
    all_picks = []
    for tier in ("A++", "A+", "A", "MACRO_PUT", "EXTERNAL_DISCOVERY"):
        for p in aa.get(tier, []) or []:
            all_picks.append(p)

    apply_signal_dedup(all_picks, verbose=True)
    apply_conviction_scores(all_picks, verbose=True, max_picks=60)
    apply_bear_conviction(all_picks, verbose=True, max_picks=60)
    try:
        apply_directions(all_picks, verbose=True)
    except Exception as e:
        print(f"  apply_directions failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.conviction_drift import check_drift
        alerts = check_drift(scan, verbose=True)
        scan["conviction_drift_alerts"] = alerts
        print(f"\nDrift alerts after intraweek refresh: {len(alerts)}")
        for a in alerts[:10]:
            print(f"  [{a['severity']}] {a['ticker']} - {a['alert_type']}")
    except Exception as e:
        alerts = []
        print(f"  drift check failed: {type(e).__name__}: {e}")

    out_path = scan_path.replace(".json", "_intraweek.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scan, f, indent=2, default=str)
    print(f"\nWrote {out_path}")

    if not os.environ.get("SEND_EMAIL"):
        print("\nSEND_EMAIL not set - skipping email. Set SEND_EMAIL=1 to deliver.")
        return

    try:
        from src.catalyst.unified_email import render_unified_email
        from src.email_report import send_email
        aa_results = scan.get("aa_results") or {}
        aa_picks = scan.get("aa_picks") or {}
        aa_rejections = scan.get("aa_rejections") or []
        html = render_unified_email(scan, aa_results, aa_picks, aa_rejections, drift_alerts=alerts)
        high = sum(1 for a in alerts if a.get("severity") == "HIGH")
        prefix = f"[INTRAWEEK · {high} EXIT ALERT{'S' if high != 1 else ''}] " if high else "[INTRAWEEK] "
        subject = f"{prefix}Catalyst refresh - {scan_date}"
        send_email(html, scan_date, subject=subject)
        print(f"Intraweek email sent (subject: {subject})")
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

import os
import sys
import json
import glob
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.unified_email import render_unified_email
from src.email_report import send_email
from src.eodhd import EODHDClient
from src.catalyst.edgar import EDGARClient, collect_material_signals, collect_form4_cluster
from src.catalyst.news import fetch_recent_news
from src.catalyst.signals import (
    run_all_catalyst_detectors, detector_hits_to_signal_entries, append_signals_and_rescore,
)
from src.catalyst.scoring import CATALYST_TIERS, WEIGHT_CATALYST, cross_confirmation_score


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "data", "results")


def morning_refresh(scan, top_n=100, verbose=True):
    client = EODHDClient()
    edgar = EDGARClient()
    all_scored = scan.get("all_scored") or []
    candidates = sorted(all_scored, key=lambda s: s.get("score") or 0, reverse=True)[:top_n]
    if verbose:
        print(f"  refreshing top {len(candidates)} candidates...")

    try:
        fresh_material = collect_material_signals(edgar, days_back=1)
        fresh_insider = collect_form4_cluster(edgar, days_back=2, min_buyers=3)
        if verbose:
            print(f"  EDGAR overnight: {len(fresh_material)} material + {len(fresh_insider)} insider clusters")
    except Exception as e:
        if verbose:
            print(f"  EDGAR refresh failed: {type(e).__name__}: {e}")
        fresh_material = {}
        fresh_insider = {}

    new_signals_added = 0
    edgar_signals_added = 0
    candidates_updated = set()
    for s in candidates:
        ticker = s.get("ticker")
        eodhd_ticker = s.get("eodhd_ticker") or (f"{ticker}.US" if ticker else None)
        if not ticker:
            continue

        try:
            raw_news = fetch_recent_news(client, eodhd_ticker, max_age_days=2, limit=30)
            fund = None
            try:
                fund = client.fundamentals(eodhd_ticker)
            except Exception:
                fund = None
            detectors = run_all_catalyst_detectors(raw_news, fund)
            entries = detector_hits_to_signal_entries(detectors)
            if entries:
                changed = append_signals_and_rescore(s, entries, CATALYST_TIERS, WEIGHT_CATALYST)
                if changed:
                    added = s.get("_signals_added") or []
                    new_signals_added += len(added)
                    candidates_updated.add(ticker)
        except Exception:
            pass

        if ticker in fresh_material:
            existing_keys = {c.get("key") for c in (s.get("catalysts") or [])}
            seen = set()
            for f in fresh_material[ticker].get("filings", []):
                match = f.get("match")
                if not match or match in seen or match in existing_keys:
                    continue
                seen.add(match)
                meta = CATALYST_TIERS.get(match)
                if not meta:
                    continue
                catalysts_full = (s.get("components", {}).get("catalyst_quality", {}) or {}).get("catalysts_full") or []
                catalysts_full.append({
                    "key": match,
                    "tier": meta["tier"],
                    "points": meta["points"],
                    "label": meta["label"],
                    "details": f"8-K filed {f.get('date')} (overnight)",
                    "direction": meta.get("direction", "bull"),
                    "event_timing": meta.get("event_timing", "fresh_breaking"),
                })
                catalysts_full.sort(key=lambda x: x["points"], reverse=True)
                primary = catalysts_full[0]["points"] if catalysts_full else 0
                secondary_bonus = sum(c["points"] for c in catalysts_full[1:]) * 0.25
                base = min(primary + secondary_bonus, 5.0)
                old_pts = s["components"]["catalyst_quality"].get("points", 0) or 0
                new_pts = base * WEIGHT_CATALYST
                s["components"]["catalyst_quality"]["points"] = round(new_pts, 2)
                s["components"]["catalyst_quality"]["catalysts_full"] = catalysts_full
                s["components"]["catalyst_quality"]["details"] = [c["label"] for c in catalysts_full]
                s["components"]["catalyst_quality"]["tier"] = catalysts_full[0]["tier"] if catalysts_full else "-"
                s["catalysts"] = catalysts_full
                s["catalyst_tier"] = catalysts_full[0]["tier"] if catalysts_full else "-"
                s["score"] = round((s.get("score") or 0) - old_pts + new_pts, 2)
                edgar_signals_added += 1
                candidates_updated.add(ticker)

    for s in candidates:
        catalysts_full = (s.get("components", {}).get("catalyst_quality", {}) or {}).get("catalysts_full") or []
        xconf = cross_confirmation_score(catalysts_full)
        old_xconf_pts = (s.get("components", {}).get("cross_confirmation", {}) or {}).get("points", 0) or 0
        s["components"]["cross_confirmation"] = xconf
        s["score"] = round((s.get("score") or 0) - old_xconf_pts + xconf["points"], 2)
        s["cross_confirmation"] = xconf

    candidates.sort(key=lambda s: s.get("score") or 0, reverse=True)

    if verbose:
        print(f"  morning refresh complete: {new_signals_added} new news signals, {edgar_signals_added} EDGAR overnight signals")
        print(f"  {len(candidates_updated)} candidates updated, EODHD={client.calls_made}, EDGAR={edgar.calls_made}")


def find_latest_scan_json():
    pattern = os.path.join(RESULTS_DIR, "catalyst_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    files = [f for f in files if "_email" not in os.path.basename(f)]
    if not files:
        return None
    return files[0]


def main():
    target_date = os.environ.get("CATALYST_DATE") or None
    explicit_path = os.environ.get("CATALYST_SCAN_JSON") or None

    if explicit_path and os.path.exists(explicit_path):
        scan_path = explicit_path
    elif target_date:
        scan_path = os.path.join(RESULTS_DIR, f"catalyst_{target_date}.json")
        if not os.path.exists(scan_path):
            print(f"Scan JSON not found at {scan_path}")
            sys.exit(2)
    else:
        scan_path = find_latest_scan_json()
        if not scan_path:
            print(f"No scan JSON found in {RESULTS_DIR}")
            sys.exit(2)

    print(f"Loading scan from {scan_path}")
    with open(scan_path, "r", encoding="utf-8") as f:
        scan = json.load(f)

    skip_refresh = os.environ.get("SKIP_MORNING_REFRESH", "")
    if not skip_refresh:
        try:
            print(f"Morning refresh: re-fetching overnight news/EDGAR/Form 4 for top 100...")
            morning_refresh(scan, top_n=100, verbose=True)
        except Exception as e:
            print(f"Morning refresh failed (non-fatal): {type(e).__name__}: {e}")
            traceback.print_exc()

        try:
            print(f"Opening-action boost: fetching live Alpaca quotes for top 200 to score today's gaps...")
            from src.catalyst.opening_action import apply_opening_action_boost
            apply_opening_action_boost(scan, top_n=200, verbose=True)
        except Exception as e:
            print(f"Opening-action boost failed (non-fatal): {type(e).__name__}: {e}")
            traceback.print_exc()

    print(f"Rendering UNIFIED v4 elite email (bracket-routed, A-only)...")

    aa_results = scan.get("aa_results") or {}
    aa_picks = scan.get("aa_picks") or {"micro": [], "small": [], "mid": []}
    aa_rejections = scan.get("aa_rejections") or []
    regime_info = scan.get("vol_regime_info")

    from src.catalyst.execution_intel import execution_context as get_exec_ctx
    exec_ctx = get_exec_ctx()

    try:
        html_main = render_unified_email(scan, aa_results, aa_picks, aa_rejections, regime_info=regime_info, execution_ctx=exec_ctx)
    except Exception as e:
        print(f"Unified email render failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)

    suffix = scan.get("scan_date", datetime.utcnow().strftime("%Y-%m-%d"))

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set -- writing HTML, not sending")
        main_path = os.path.join(RESULTS_DIR, f"catalyst_v4_elite_{suffix}.html")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(html_main)
        print(f"Wrote {main_path}")
        return

    email_sent = False
    try:
        a_count = len(aa_results.get("A++", [])) + len(aa_results.get("A+", [])) + len(aa_results.get("A", []))
        subject = f"Catalyst Scanner v4 — {a_count} A-grade picks — {suffix}"
        send_email(html_main, suffix, subject=subject)
        print("Unified email sent")
        email_sent = True
    except Exception as e:
        print(f"Unified email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()

    if not email_sent:
        sys.exit(1)


if __name__ == "__main__":
    main()

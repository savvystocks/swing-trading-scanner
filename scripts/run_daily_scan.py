import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scanner import run_scan, save_results
from src.email_report import render_email, render_options_email, send_email


def main():
    limit = None
    scan_limit_env = os.environ.get("SCAN_LIMIT", "").strip()
    if scan_limit_env and scan_limit_env.isdigit():
        limit = int(scan_limit_env)

    print(f"Starting daily scan (limit={limit})")
    scan = run_scan(universe_limit=limit)
    save_results(scan)

    scan_for_email = {
        "scan_date": scan["scan_date"],
        "universe_size": scan["universe_size"],
        "fast_filter_survivors": scan["fast_filter_survivors"],
        "scored_total": scan["scored_total"],
        "api_calls": scan["api_calls"],
        "vix_regime": scan["vix_regime"],
        "sector_performance": scan.get("sector_performance", []),
        "tickets": [r["ticket"] for r in scan["results"]],
    }

    html_main = render_email(scan_for_email)
    html_options = render_options_email(scan_for_email)

    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "results")
    os.makedirs(results_dir, exist_ok=True)

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set — not sending")
        main_path = os.path.join(results_dir, f"email_{scan['scan_date']}.html")
        opts_path = os.path.join(results_dir, f"email_options_{scan['scan_date']}.html")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(html_main)
        with open(opts_path, "w", encoding="utf-8") as f:
            f.write(html_options)
        print(f"Wrote {main_path}")
        print(f"Wrote {opts_path}")
        return

    try:
        send_email(html_main, scan["scan_date"], subject=f"Swing Scan {scan['scan_date']}")
        print("Main scan email sent")
    except Exception as e:
        print(f"Main email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        send_email(html_options, scan["scan_date"], subject=f"Options Plays {scan['scan_date']}")
        print("Options email sent")
    except Exception as e:
        print(f"Options email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

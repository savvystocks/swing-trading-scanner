import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scanner import run_scan, save_results
from src.email_report import render_email, send_email


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
        "tickets": [r["ticket"] for r in scan["results"]],
    }

    html = render_email(scan_for_email)

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set — not sending")
        out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "results", f"email_{scan['scan_date']}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Wrote {out}")
        return

    try:
        send_email(html, scan["scan_date"])
        print("Email sent")
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

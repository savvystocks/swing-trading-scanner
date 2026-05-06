import os
import sys
import json
import glob
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.email_template import render_catalyst_email
from src.catalyst.options_email import render_catalyst_options_email
from src.catalyst.factor_options_email import render_factor_options_email
from src.email_report import send_email


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "data", "results")


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

    print(f"Rendering catalyst email (live spot + options at send-time)...")
    html_main = render_catalyst_email(scan)

    try:
        html_lottery = render_catalyst_options_email(scan)
    except Exception as e:
        print(f"Lottery email render failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        html_lottery = None

    try:
        html_factors = render_factor_options_email(scan)
    except Exception as e:
        print(f"Factor options email render failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        html_factors = None

    suffix = scan.get("scan_date", datetime.utcnow().strftime("%Y-%m-%d"))

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set -- writing HTML, not sending")
        main_path = os.path.join(RESULTS_DIR, f"catalyst_email_morning_{suffix}.html")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(html_main)
        print(f"Wrote {main_path}")
        if html_lottery:
            opts_path = os.path.join(RESULTS_DIR, f"catalyst_options_email_morning_{suffix}.html")
            with open(opts_path, "w", encoding="utf-8") as f:
                f.write(html_lottery)
            print(f"Wrote {opts_path}")
        if html_factors:
            factor_path = os.path.join(RESULTS_DIR, f"factor_options_email_morning_{suffix}.html")
            with open(factor_path, "w", encoding="utf-8") as f:
                f.write(html_factors)
            print(f"Wrote {factor_path}")
        return

    email_sent = False
    try:
        send_email(html_main, suffix, subject=f"Catalyst Watchlist {suffix}")
        print("Catalyst email sent")
        email_sent = True
    except Exception as e:
        print(f"Catalyst email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()

    if html_lottery:
        try:
            send_email(html_lottery, suffix, subject=f"Catalyst Lottery Options {suffix}")
            print("Catalyst lottery options email sent")
        except Exception as e:
            print(f"Catalyst lottery options email send failed: {type(e).__name__}: {e}")
            traceback.print_exc()

    if html_factors:
        try:
            send_email(html_factors, suffix, subject=f"Top Factors Options {suffix}")
            print("Top factors options email sent")
        except Exception as e:
            print(f"Top factors options email send failed: {type(e).__name__}: {e}")
            traceback.print_exc()

    if not email_sent:
        sys.exit(1)


if __name__ == "__main__":
    main()

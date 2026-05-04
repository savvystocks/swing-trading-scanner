import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.premarket_refresh import load_latest_scan, build_refresh_payload, render_premarket_email
from src.email_report import send_email


def main():
    print("Pre-market refresh: starting")
    scan, scan_id = load_latest_scan()
    if not scan:
        print("No scan file found - run main scan first")
        sys.exit(0)
    print(f"Loaded {scan_id}")

    picks = build_refresh_payload(scan, verbose=True)
    if not picks:
        print("No actionable picks - skipping email")
        sys.exit(0)

    print(f"Built refresh payload: {len(picks)} picks")
    for p in picks[:5]:
        print(f"  {p['ticker']:12s} T{p['tier']} hunter={p['hunter_score']} {p['category']:15s} {p['delta_pct']:+.2f}%")

    date_str = scan.get("scan_date", scan_id.replace("scan_", ""))
    html = render_premarket_email(picks, date_str)
    if not html:
        print("No HTML rendered - exit")
        sys.exit(0)

    if os.environ.get("SKIP_EMAIL"):
        out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "results", f"premarket_{date_str}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"SKIP_EMAIL set - wrote {out}")
        return

    try:
        send_email(html, date_str, subject=f"Pre-Market Refresh {date_str}")
        print("Pre-market refresh email sent")
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

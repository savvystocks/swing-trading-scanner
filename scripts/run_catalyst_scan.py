import os
import sys
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.scanner import run_catalyst_scan
from src.catalyst.email_template import render_catalyst_email
from src.email_report import send_email


def main():
    target_date = os.environ.get("CATALYST_DATE") or None
    llm_max_env = os.environ.get("CATALYST_LLM_MAX", "").strip()
    llm_max = int(llm_max_env) if llm_max_env.isdigit() else 50

    print(f"Starting catalyst scan v2 (target_date={target_date}, llm_max={llm_max})")

    try:
        scan = run_catalyst_scan(target_date=target_date, llm_max_grade=llm_max)
    except Exception as e:
        from src.telegram import send_failure_alert
        import datetime as _dt
        today_str = target_date or _dt.datetime.utcnow().date().strftime("%Y-%m-%d")
        send_failure_alert(today_str, f"{type(e).__name__}: {e}")
        raise

    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "results")
    os.makedirs(results_dir, exist_ok=True)
    json_path = os.path.join(results_dir, f"catalyst_{scan['scan_date']}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scan, f, indent=2, default=str)
    print(f"Wrote {json_path}")

    html = render_catalyst_email(scan)

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set -- not sending")
        html_path = os.path.join(results_dir, f"catalyst_email_{scan['scan_date']}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Wrote {html_path}")
        return

    email_sent = False
    try:
        send_email(html, scan["scan_date"], subject=f"Catalyst Watchlist {scan['scan_date']}")
        print("Catalyst email sent")
        email_sent = True
    except Exception as e:
        print(f"Catalyst email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()

    try:
        from src.telegram import send_catalyst_alert
        ok = send_catalyst_alert(scan)
        print(f"Telegram alert sent: {ok}")
    except Exception as e:
        print(f"Telegram alert failed: {type(e).__name__}: {e}")

    if not email_sent:
        sys.exit(1)


if __name__ == "__main__":
    main()

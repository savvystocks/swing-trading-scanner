"""Entry point for the new flow-first scanner.

Replaces scripts/run_daily_scan.py for the UW-driven era.
Pulls flow universe, scores confluence, renders email, sends.

Two operation modes:
  EMAIL_MODE   : Full SMTP email + Telegram alerts. Fires at 3 designated times/day.
  ALERT_MODE   : JSON write + Telegram tier-change alerts only (no email spam).
                 Fires every 15 min during market hours.

Mode is auto-detected from current UTC time vs designated email windows.
Override: set FORCE_EMAIL=1 to always send email regardless of time.
"""

import os
import sys
import json
import traceback
from datetime import datetime, timezone


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.flow_scanner import run_flow_scan
from src.catalyst.flow_email import render_flow_email
from src.email_report import send_email
from src.catalyst.scan_state import update_state, format_event_for_telegram


# UTC hours when email should fire (in addition to JSON + Telegram).
# Each is +/- 8 min window to catch the actual cron firing.
EMAIL_WINDOWS_UTC = [
    (13, 30),  # 14:30 BST summer / 14:30 GMT winter - market open
    (17, 30),  # 18:30 BST summer / 17:30 GMT winter - midday
    (20, 30),  # 21:30 BST summer / 20:30 GMT winter - power hour
]


def is_email_time():
    if os.environ.get("FORCE_EMAIL") == "1":
        return True
    now = datetime.now(timezone.utc)
    for h, m in EMAIL_WINDOWS_UTC:
        target_minutes = h * 60 + m
        now_minutes = now.hour * 60 + now.minute
        if abs(now_minutes - target_minutes) <= 8:
            return True
    return False


def main():
    target_date = os.environ.get("CATALYST_DATE") or None
    print(f"Starting flow-first scan (target_date={target_date})")

    try:
        scan = run_flow_scan(target_date=target_date, verbose=True)
    except Exception as e:
        try:
            from src.telegram import send_failure_alert
            import datetime as _dt
            today_str = target_date or _dt.datetime.utcnow().date().strftime("%Y-%m-%d")
            send_failure_alert(today_str, f"{type(e).__name__}: {e}")
        except Exception:
            pass
        raise

    if not scan:
        print("Scan returned no data - UNUSUAL_WHALES_TOKEN missing?")
        sys.exit(1)

    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "results")
    os.makedirs(results_dir, exist_ok=True)

    json_path = os.path.join(results_dir, f"flow_scan_{scan['scan_date']}.json")
    slim = {k: v for k, v in scan.items() if k not in ("ranked_picks",)}
    slim["calls"] = [{k: v for k, v in p.items() if k != "_enriched_data"} for p in scan.get("calls", [])]
    slim["puts"] = [{k: v for k, v in p.items() if k != "_enriched_data"} for p in scan.get("puts", [])]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=2, default=str)
    print(f"Wrote {json_path}")

    try:
        from src.unusual_whales_api import get_client
        from src.catalyst.positions_panel import build_positions_panel
        scan["open_positions"] = build_positions_panel(get_client())
        if scan["open_positions"]:
            print(f"  positions panel: {len(scan['open_positions'])} open position(s)")
    except Exception as e:
        print(f"  positions panel failed (non-fatal): {type(e).__name__}: {e}")
        scan["open_positions"] = []

    try:
        html = render_flow_email(scan)
    except Exception as e:
        print(f"Email render failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        html = f"<html><body>Render failed: {type(e).__name__}</body></html>"

    html_path = os.path.join(results_dir, f"flow_email_{scan['scan_date']}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {html_path}")

    # Diff scan against last state for tier-change Telegram alerts (always runs)
    try:
        events = update_state(scan)
        if events:
            print(f"  scan_state: {len(events)} significant events detected")
        else:
            print(f"  scan_state: no significant tier changes since last scan")
    except Exception as e:
        events = []
        print(f"  scan_state failed: {type(e).__name__}: {e}")

    n_calls = len(scan.get("calls", []))
    n_puts = len(scan.get("puts", []))
    by_tier = scan.get("by_tier", {})
    top_tier = "PASS"
    for t in ("GAMMA_BOMB", "MAX_CONVICTION", "ELITE", "STRONG", "MODERATE"):
        if by_tier.get(t, 0) > 0:
            top_tier = t
            break

    meta = (scan.get("macro") or {}).get("meta_regime") or {}
    regime = meta.get("regime", "UNKNOWN")

    # Fire Telegram alerts on EVERY scan when significant events happen
    if events:
        try:
            from src.telegram import send_alert
            lines = [f"<b>FLOW UPDATE ({regime})</b>"]
            for ev in events[:6]:
                lines.append("")
                lines.append(format_event_for_telegram(ev))
            send_alert("\n".join(lines))
            print(f"Telegram alert sent: {len(events)} events")
        except Exception as e:
            print(f"Telegram alert failed: {type(e).__name__}: {e}")

    # Email decision
    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL env set - not sending")
        return

    if not is_email_time():
        print("Not within email window - alert-only mode (JSON + Telegram fired)")
        return

    subject = f"FLOW {regime} - {n_calls}C/{n_puts}P top: {top_tier} - {scan['scan_date']}"
    try:
        send_email(html, scan["scan_date"], subject=subject)
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

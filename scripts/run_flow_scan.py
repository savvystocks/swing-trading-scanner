"""Entry point for the new flow-first scanner.

Replaces scripts/run_daily_scan.py for the UW-driven era.
Pulls flow universe, scores confluence, renders email, sends.
"""

import os
import sys
import json
import traceback


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
        html = render_flow_email(scan)
    except Exception as e:
        print(f"Email render failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        html = f"<html><body>Render failed: {type(e).__name__}</body></html>"

    html_path = os.path.join(results_dir, f"flow_email_{scan['scan_date']}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {html_path}")

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set - not sending")
        return

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
    subject = f"FLOW {regime} - {n_calls}C/{n_puts}P top: {top_tier} - {scan['scan_date']}"
    try:
        send_email(html, scan["scan_date"], subject=subject)
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        from src.telegram import send_alert
        elite_calls = sum(1 for p in scan.get("calls", []) if (p.get("_confluence") or {}).get("tier") in ("ELITE", "MAX_CONVICTION", "GAMMA_BOMB"))
        elite_puts = sum(1 for p in scan.get("puts", []) if (p.get("_confluence") or {}).get("tier") in ("ELITE", "MAX_CONVICTION", "GAMMA_BOMB"))
        if elite_calls or elite_puts:
            lines = [f"<b>FLOW SCAN: {regime}</b>",
                     f"{elite_calls} elite CALLs, {elite_puts} elite PUTs"]
            for p in scan.get("calls", [])[:3]:
                c = p.get("_confluence") or {}
                lines.append(f"- {p['ticker']} {c.get('tier')} CALL score={c.get('score')}")
            for p in scan.get("puts", [])[:3]:
                c = p.get("_confluence") or {}
                lines.append(f"- {p['ticker']} {c.get('tier')} PUT score={c.get('score')}")
            send_alert("\n".join(lines))
    except Exception as e:
        print(f"Telegram alert failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

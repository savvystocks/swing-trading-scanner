import os
import sys
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.scanner import run_catalyst_scan
from src.catalyst.unified_email import render_unified_email
from src.catalyst.execution_intel import execution_context as get_exec_ctx
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

    aa_results = scan.get("aa_results") or {}
    aa_picks = scan.get("aa_picks") or {"micro": [], "small": [], "mid": []}
    aa_rejections = scan.get("aa_rejections") or []
    regime_info = scan.get("vol_regime_info")
    exec_ctx = get_exec_ctx()

    try:
        html_main = render_unified_email(scan, aa_results, aa_picks, aa_rejections, regime_info=regime_info, execution_ctx=exec_ctx)
    except Exception as e:
        print(f"Unified email render failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        html_main = "<html><body><h1>Render failed</h1></body></html>"

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set -- not sending")
        main_path = os.path.join(results_dir, f"catalyst_v4_elite_{scan['scan_date']}.html")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(html_main)
        print(f"Wrote {main_path}")
        return

    email_sent = False
    try:
        a_count = len(aa_results.get("A++", [])) + len(aa_results.get("A+", [])) + len(aa_results.get("A", []))
        send_email(html_main, scan["scan_date"], subject=f"Catalyst Scanner v4 — {a_count} A-grade picks — {scan['scan_date']}")
        print("Unified email sent")
        email_sent = True
    except Exception as e:
        print(f"Unified email send failed: {type(e).__name__}: {e}")
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

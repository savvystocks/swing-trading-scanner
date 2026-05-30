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

    BLOAT_KEYS_PER_PICK = ("_raw_fundamentals", "earnings_history", "_pre_stack_score")
    TOP_LEVEL_DUPLICATES = ("candidates", "all_scored")

    def _strip_pick(p):
        if not isinstance(p, dict):
            return p
        return {k: v for k, v in p.items() if k not in BLOAT_KEYS_PER_PICK}

    slim_scan = {k: v for k, v in scan.items() if k not in TOP_LEVEL_DUPLICATES}
    aa = slim_scan.get("aa_results") or {}
    if isinstance(aa, dict):
        slim_scan["aa_results"] = {
            tier: [_strip_pick(p) for p in (aa.get(tier) or [])]
            for tier in aa.keys()
        }
    aa_picks = slim_scan.get("aa_picks") or {}
    if isinstance(aa_picks, dict):
        slim_scan["aa_picks"] = {
            bracket: [_strip_pick(p) for p in (aa_picks.get(bracket) or [])]
            for bracket in aa_picks.keys()
        }
    pre_cat = slim_scan.get("pre_catalyst_watchlist") or []
    if isinstance(pre_cat, list):
        slim_scan["pre_catalyst_watchlist"] = [_strip_pick(p) for p in pre_cat]

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(slim_scan, f, indent=2, default=str)
    file_mb = os.path.getsize(json_path) / 1_000_000
    print(f"Wrote {json_path} ({file_mb:.1f} MB)")

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
        gs = scan.get("guardrail_state") or {}
        review_mode = gs.get("mode") == "REVIEW_MODE"
        review_prefix = "[REVIEW MODE] " if review_mode else ""
        drift_alerts = scan.get("conviction_drift_alerts") or []
        live_high_alerts = sum(1 for a in drift_alerts if a.get("severity") == "HIGH" and a.get("is_live"))
        alert_prefix = f"[{live_high_alerts} EXIT ALERT{'S' if live_high_alerts != 1 else ''}] " if live_high_alerts else ""
        macro_root = scan.get("macro") or {}
        macro_regime_block = macro_root.get("macro_regime") or {}
        regime = macro_regime_block.get("regime") or macro_root.get("regime") or "UNKNOWN"
        regime = str(regime).upper()
        n_take = len([p for tier in ("A++","A+","A") for p in (aa_results.get(tier) or []) if ((p.get("_action_signal") or {}).get("action") == "TAKE")])
        take_label = "SIT OUT" if n_take == 0 else f"{n_take} TAKE"
        subject = f"{review_prefix}{alert_prefix}{regime} — {take_label} — {scan['scan_date']}"
        send_email(html_main, scan["scan_date"], subject=subject)
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

    try:
        from src.telegram import send_priority_alerts
        n = send_priority_alerts(scan)
        if n:
            print(f"Telegram priority alerts sent: {n}")
    except Exception as e:
        print(f"Telegram priority alerts failed: {type(e).__name__}: {e}")

    if not email_sent:
        sys.exit(1)


if __name__ == "__main__":
    main()

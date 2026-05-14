import os
import sys
import json
import glob
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_morning_picks(target_date):
    pattern = f"data/results/catalyst_{target_date}.json"
    files = glob.glob(pattern)
    if not files:
        return set(), None
    try:
        with open(files[0]) as f:
            scan = json.load(f)
        aa = scan.get("aa_results") or {}
        morning_tickers = set()
        for tier in ("A++", "A+", "A"):
            for p in aa.get(tier, []):
                tk = p.get("ticker")
                if tk:
                    morning_tickers.add(tk)
        return morning_tickers, scan
    except Exception:
        return set(), None


def main():
    from src.catalyst.scanner import run_catalyst_scan

    target_date = os.environ.get("CATALYST_DATE") or datetime.utcnow().date().strftime("%Y-%m-%d")
    print(f"=== MID-DAY SCAN {target_date} (19:30 UTC) ===")

    morning_tickers, morning_scan = load_morning_picks(target_date)
    print(f"Morning scan had {len(morning_tickers)} A-grade tickers")

    print("Running mid-day scan...")
    llm_max = int(os.environ.get("CATALYST_LLM_MAX", "10"))
    try:
        scan = run_catalyst_scan(target_date=target_date, llm_max_grade=llm_max)
    except Exception as e:
        print(f"Mid-day scan failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    aa = scan.get("aa_results") or {}
    midday_tickers = set()
    for tier in ("A++", "A+", "A"):
        for p in aa.get(tier, []):
            tk = p.get("ticker")
            if tk:
                midday_tickers.add(tk)
    print(f"Mid-day scan: {len(midday_tickers)} A-grade tickers")

    new_tickers = midday_tickers - morning_tickers
    print(f"NEW vs morning: {len(new_tickers)} tickers")

    new_buys_with_llm = []
    for tier in ("A++", "A+", "A"):
        for p in aa.get(tier, []):
            tk = p.get("ticker")
            if tk in new_tickers:
                h = p.get("haiku_synthesis") or {}
                f = p.get("unified_forensic") or {}
                verdict = f.get("verdict") or h.get("verdict")
                if verdict in ("BUY", "STRONG_BUY"):
                    bear = p.get("bear_verification") or {}
                    if not bear.get("is_this_trade_a_trap"):
                        new_buys_with_llm.append({
                            "ticker": tk,
                            "tier": p.get("_aa_tier"),
                            "sector": p.get("sector"),
                            "verdict": verdict,
                            "confidence_pct": f.get("confidence_pct") or h.get("confidence_pct"),
                            "score": p.get("_stacked_score"),
                            "price": p.get("live_spot") or p.get("price"),
                        })

    if new_buys_with_llm:
        print(f"\n=== {len(new_buys_with_llm)} NEW BUY-rated picks since morning ===")
        for p in new_buys_with_llm:
            print(f"  {p['ticker']}  {p['tier']}  {p['sector']}  ${p['price']}  {p['verdict']} {p.get('confidence_pct')}%")

        try:
            from src.telegram import send_alert
            msg_lines = [f"[MID-DAY ALERT] {len(new_buys_with_llm)} NEW BUY-rated since morning scan:"]
            for p in new_buys_with_llm:
                conf = p.get('confidence_pct') or "?"
                msg_lines.append(f"  - {p['ticker']} ({p['tier']} {p['sector']}) ${p['price']} - {p['verdict']} {conf}%")
            msg_lines.append("Full email at 14:45 tomorrow; this is a heads-up for action today.")
            send_alert("\n".join(msg_lines))
            print("Telegram alert sent")
        except Exception as e:
            print(f"Telegram failed: {type(e).__name__}: {e}")
    else:
        print("No NEW BUY-rated picks since morning - no alert sent")

    out_path = f"data/results/midday_diff_{target_date}.json"
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump({
                "scan_date": target_date,
                "ran_at": datetime.utcnow().isoformat(),
                "morning_ticker_count": len(morning_tickers),
                "midday_ticker_count": len(midday_tickers),
                "new_tickers": sorted(new_tickers),
                "new_buy_rated": new_buys_with_llm,
            }, f, indent=2, default=str)
        print(f"Wrote {out_path}")
    except Exception as e:
        print(f"Failed to write diff: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

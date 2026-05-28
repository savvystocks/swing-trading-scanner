"""Sunday evening P&L digest.

Schedule: GitHub Actions cron at 19:00 UTC every Sunday.

Reads conviction_journal + account_ledger, sends a single email summarising:
- Week's closed trades (count, win rate, P&L)
- Account value vs peak vs goal pace
- Current open positions and drift warnings
- Subjects flag REVIEW MODE if active

Designed to make Sundays an enforced thesis-review checkpoint, not just a
"line went up / down" report.
"""
import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.catalyst.guardrails import evaluate as evaluate_guardrails, get_live_positions
from src.email_report import send_email


def closed_this_week():
    path = "data/paper_trades/conviction_journal.jsonl"
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    week_start = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    out = []
    for r in rows:
        o = r.get("outcomes") or {}
        if not o.get("measured_at"):
            continue
        if o.get("measured_at") < week_start:
            continue
        is_put = r.get("side") == "PUT"
        ret = o.get("ret_10d_pct") if o.get("ret_10d_pct") is not None else o.get("ret_5d_pct") or o.get("best_pct")
        if ret is None:
            continue
        if is_put:
            ret = -ret
        out.append({
            "scan_date": r.get("scan_date"),
            "ticker": r.get("ticker"),
            "side": r.get("side"),
            "winning_score": r.get("winning_score"),
            "ret_pct": ret,
            "won": ret > 0,
        })
    return out


def build_digest_html(state, week_trades):
    config = state["config"]
    current = state["current_account_gbp"]
    peak = state["peak_account_gbp"]
    drawdown = state["drawdown_pct"]
    pace = state["pace"] or {}
    mode = state["mode"]

    wins = [t for t in week_trades if t["won"]]
    losses = [t for t in week_trades if not t["won"]]
    week_win_rate = round(len(wins) / len(week_trades) * 100, 1) if week_trades else 0
    avg_win = round(sum(t["ret_pct"] for t in wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(t["ret_pct"] for t in losses) / len(losses), 2) if losses else 0

    live_positions = get_live_positions()

    parts = []
    parts.append(f"<h1>Weekly Digest — {datetime.utcnow().date().isoformat()}</h1>")

    if mode == "REVIEW_MODE":
        parts.append('<div style="padding:14px 18px; background:#fef2f2; border:2px solid #b91c1c; border-radius:8px; margin:14px 0;">')
        parts.append('<div style="font-weight:800; color:#b91c1c; font-size:16px;">REVIEW MODE ACTIVE</div>')
        for t in state.get("triggers") or []:
            parts.append(f'<div style="font-size:12px; color:#7f1d1d; margin-top:6px;">- {t["message"]}</div>')
        parts.append('</div>')

    parts.append('<div style="background:#1a1a1a; color:#fff; padding:16px; border-radius:8px; margin:14px 0; font-size:13px; line-height:1.7;">')
    parts.append(f'<div><strong>Account:</strong> £{int(current):,} (peak £{int(peak):,}, {drawdown:.1f}% drawdown)</div>')
    parts.append(f'<div><strong>Goal:</strong> £{int(config["goal_target_gbp"]):,} by {config["goal_deadline_iso"]}</div>')
    if pace:
        on_pace_color = "#86efac" if pace["on_pace"] else "#fca5a5"
        parts.append(f'<div><strong>Pace:</strong> <span style="color:{on_pace_color};">{ "ON TRACK" if pace["on_pace"] else "BEHIND" }</span> — {pace["weeks_left"]}w left, need {pace["required_weekly_growth_pct"]}%/wk, {pace["multiple_remaining"]}x to go</div>')
    parts.append('</div>')

    parts.append('<h2>This week</h2>')
    if week_trades:
        parts.append(f'<div>{len(week_trades)} trades closed. Win rate <strong>{week_win_rate}%</strong>. Avg win +{avg_win}%, avg loss {avg_loss}%.</div>')
        parts.append('<table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:12px;">')
        parts.append('<tr><th align="left" style="padding:6px; border-bottom:1px solid #ccc;">Ticker</th><th align="left" style="padding:6px; border-bottom:1px solid #ccc;">Side</th><th align="right" style="padding:6px; border-bottom:1px solid #ccc;">Score</th><th align="right" style="padding:6px; border-bottom:1px solid #ccc;">Return</th></tr>')
        for t in sorted(week_trades, key=lambda x: -x["ret_pct"]):
            color = "#15803d" if t["won"] else "#b91c1c"
            parts.append(f'<tr><td style="padding:6px;">{t["ticker"]}</td><td style="padding:6px;">{t["side"]}</td><td style="padding:6px;" align="right">{t["winning_score"]}</td><td style="padding:6px; color:{color}; font-weight:700;" align="right">{t["ret_pct"]:+.1f}%</td></tr>')
        parts.append('</table>')
    else:
        parts.append('<div style="color:#6b7280;">No trades closed this week.</div>')

    parts.append('<h2>Open live positions</h2>')
    if live_positions:
        parts.append('<table style="width:100%; border-collapse:collapse; font-size:12px;">')
        parts.append('<tr><th align="left">Ticker</th><th align="left">Contract</th><th align="right">Cost</th><th align="left">Opened</th></tr>')
        for p in live_positions:
            parts.append(f'<tr><td>{p.get("ticker")}</td><td>{p.get("strike")} {p.get("side")} {p.get("expiration")}</td><td align="right">£{p.get("cost_gbp")}</td><td>{p.get("opened_at")}</td></tr>')
        parts.append('</table>')
    else:
        parts.append('<div style="color:#6b7280;">No live positions logged. (Mark live trades in data/paper_trades/live_positions.json)</div>')

    parts.append('<h2>Thesis review checklist</h2>')
    parts.append('<ul style="line-height:1.7;">')
    parts.append('<li>What was my best-performing trade and why did it work?</li>')
    parts.append('<li>What was my worst trade and what would have warned me earlier?</li>')
    parts.append('<li>Are my picks coming from the same conviction signals each week, or am I jumping setups?</li>')
    parts.append('<li>If REVIEW MODE is active: am I trading my plan or revenge-trading?</li>')
    parts.append('<li>Is my account size growing? If not, what specific habit needs to change next week?</li>')
    parts.append('</ul>')

    return "<html><body style='font-family: -apple-system, sans-serif; max-width:680px; margin:0 auto; padding:20px;'>" + "".join(parts) + "</body></html>"


def main():
    state = evaluate_guardrails(verbose=True)
    trades = closed_this_week()
    html = build_digest_html(state, trades)

    out_path = f"data/results/weekly_digest_{datetime.utcnow().date().isoformat()}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nWrote {out_path}")

    if os.environ.get("SKIP_EMAIL"):
        print("SKIP_EMAIL set - not sending")
        return

    mode_prefix = "[REVIEW MODE] " if state["mode"] == "REVIEW_MODE" else ""
    pace = state.get("pace") or {}
    status = "ON TRACK" if pace.get("on_pace") else "BEHIND"
    subject = f"{mode_prefix}Weekly digest — £{int(state['current_account_gbp'])} ({status}) — {datetime.utcnow().date().isoformat()}"

    try:
        send_email(html, datetime.utcnow().date().isoformat(), subject=subject)
        print(f"Sent: {subject}")
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

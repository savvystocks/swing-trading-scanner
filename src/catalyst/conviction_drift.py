import os
import json
import pathlib
from datetime import datetime, timedelta

from src.catalyst.conviction_journal import (
    get_open_positions,
    update_position_drift,
)


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
ALERTS_SEEN_PATH = PROJECT_ROOT / "data" / "paper_trades" / "drift_alerts_seen.json"


DRIFT_WARN_PCT_DROP = 20
DRIFT_HARD_PCT_DROP = 30
SIDE_FLIP_ALWAYS_ALERT = True
MIN_ENTRY_SCORE_FOR_ALERT = 55
MIN_ENTRY_SCORE_FOR_DROPOUT_ALERT = 65
MIN_AGE_DAYS_FOR_DROPOUT_ALERT = 3


def _load_seen():
    if not ALERTS_SEEN_PATH.exists():
        return {}
    try:
        with open(ALERTS_SEEN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_seen(seen):
    ALERTS_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    cutoff = (datetime.utcnow() - timedelta(days=60)).isoformat()
    seen = {k: v for k, v in seen.items() if v.get("at", "") >= cutoff}
    with open(ALERTS_SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2)


def _winning_score(pick):
    d = pick.get("_direction") or {}
    ws = d.get("winning_score")
    if ws is not None:
        return ws
    c = (pick.get("_conviction") or {}).get("score") or 0
    b = (pick.get("_bear_conviction") or {}).get("score") or 0
    return max(c, b)


def _pick_side(pick):
    return (pick.get("_direction") or {}).get("side") or "CALL"


ACTIVE_TIERS_FOR_DRIFT = {"A++", "A+", "A", "MACRO_PUT"}


def _index_today_picks(scan):
    aa_results = scan.get("aa_results") or {}
    out = {}
    for tier, picks in aa_results.items():
        if tier not in ACTIVE_TIERS_FOR_DRIFT:
            continue
        for p in picks or []:
            t = p.get("ticker")
            if not t:
                continue
            out[t] = {
                "pick": p,
                "tier": tier,
                "side": _pick_side(p),
                "call_conviction": (p.get("_conviction") or {}).get("score") or 0,
                "bear_conviction": (p.get("_bear_conviction") or {}).get("score") or 0,
                "winning_score": _winning_score(p),
                "haiku_verdict": (p.get("haiku_synthesis") or {}).get("verdict"),
                "haiku_confidence": (p.get("haiku_synthesis") or {}).get("confidence_pct"),
                "price": p.get("live_spot") or p.get("price"),
                "bearish_signals": p.get("_bearish_signals") or {},
            }
    return out


def _load_live_tickers():
    try:
        from src.catalyst.guardrails import get_live_positions
        return {p.get("ticker") for p in get_live_positions() if p.get("ticker")}
    except Exception:
        return set()


def check_drift(scan, verbose=False):
    scan_date = scan.get("scan_date")
    if not scan_date:
        return []

    open_positions = get_open_positions(max_age_days=14)
    if not open_positions:
        if verbose:
            print(f"  conviction_drift: no open positions to check")
        return []

    live_tickers = _load_live_tickers()
    today_by_ticker = _index_today_picks(scan)
    seen = _load_seen()
    alerts = []

    for pos in open_positions:
        ticker = pos["ticker"]
        entry_score = pos.get("winning_score", 0)
        entry_side = pos.get("side") or "CALL"
        entry_scan_date = pos.get("scan_date")

        if entry_score < MIN_ENTRY_SCORE_FOR_ALERT:
            continue
        if entry_scan_date >= scan_date:
            continue

        today = today_by_ticker.get(ticker)
        if not today:
            try:
                entry_dt = datetime.strptime(entry_scan_date, "%Y-%m-%d").date()
                today_dt = datetime.strptime(scan_date, "%Y-%m-%d").date()
                age_days = (today_dt - entry_dt).days
            except Exception:
                age_days = 0
            if entry_score < MIN_ENTRY_SCORE_FOR_DROPOUT_ALERT or age_days < MIN_AGE_DAYS_FOR_DROPOUT_ALERT:
                continue
            if verbose:
                print(f"  conviction_drift: {ticker} dropped out of universe (entry score {entry_score}, age {age_days}d) - flagging")
            alerts.append({
                "ticker": ticker,
                "name": pos.get("name", ""),
                "alert_type": "DROPPED_OUT",
                "severity": "MED",
                "entry_scan_date": entry_scan_date,
                "entry_score": entry_score,
                "entry_side": entry_side,
                "today_score": None,
                "score_drop_pts": None,
                "side_flipped": False,
                "today_side": None,
                "is_live": ticker in live_tickers,
                "message": f"{ticker} no longer scoring A-grade for {age_days} days (entry score {entry_score}). Re-evaluate or close.",
            })
            update_position_drift(scan_date, ticker, 0, 0, "GONE")
            continue

        today_score = today["winning_score"]
        today_side = today["side"]
        today_call = today["call_conviction"]
        today_bear = today["bear_conviction"]

        update_position_drift(scan_date, ticker, today_call, today_bear, today_side)

        side_flipped = today_side != entry_side
        score_drop = entry_score - today_score

        bs = today.get("bearish_signals") or {}
        has_event_bear = bool(
            bs.get("insider_selling_cluster")
            or bs.get("dilution")
            or bs.get("going_concern")
            or bs.get("downgrade_cluster")
            or bs.get("earnings_miss")
            or bs.get("restatement")
            or bs.get("executive_departure")
        )

        if side_flipped and SIDE_FLIP_ALWAYS_ALERT and has_event_bear:
            severity = "HIGH"
            alert_type = "SIDE_FLIP_ON_EVENT"
            message = (
                f"{ticker} thesis FLIPPED with NEW bearish event: opened as {entry_side} on "
                f"{entry_scan_date} (score {entry_score}), now {today_side} ({today_score}). "
                f"Specific bearish catalyst now in data - close the position."
            )
        elif score_drop >= DRIFT_HARD_PCT_DROP and has_event_bear:
            severity = "HIGH"
            alert_type = "CONVICTION_COLLAPSE_ON_EVENT"
            message = (
                f"{ticker} conviction collapsed from {entry_score} to {today_score} AND "
                f"new bearish catalyst is in the data. Close or trim aggressively."
            )
        elif score_drop >= DRIFT_WARN_PCT_DROP and has_event_bear:
            severity = "MED"
            alert_type = "CONVICTION_DECAY_ON_EVENT"
            message = (
                f"{ticker} conviction decaying from {entry_score} to {today_score} with new "
                f"bearish event. Review thesis."
            )
        else:
            continue

        alert_key = f"{ticker}|{entry_scan_date}|{alert_type}|{scan_date}"
        if alert_key in seen:
            if verbose:
                print(f"  conviction_drift: {ticker} {alert_type} already alerted today, skipping")
            continue

        alerts.append({
            "ticker": ticker,
            "name": pos.get("name", ""),
            "alert_type": alert_type,
            "severity": severity,
            "entry_scan_date": entry_scan_date,
            "entry_score": entry_score,
            "entry_side": entry_side,
            "today_score": today_score,
            "today_side": today_side,
            "score_drop_pts": score_drop,
            "side_flipped": side_flipped,
            "entry_price": pos.get("entry_price"),
            "current_price": today.get("price"),
            "is_live": ticker in live_tickers,
            "message": message,
        })

        seen[alert_key] = {
            "at": datetime.utcnow().isoformat(),
            "ticker": ticker,
            "alert_type": alert_type,
            "score_drop": score_drop,
        }

    if alerts:
        _save_seen(seen)

    if verbose:
        print(f"  conviction_drift: {len(alerts)} drift alerts (out of {len(open_positions)} open positions)")
        for a in alerts:
            print(f"    [{a['severity']}] {a['ticker']}: {a['alert_type']} - {a['message'][:100]}")

    return alerts


def format_drift_alerts_html(alerts):
    if not alerts:
        return ""
    rows = []
    for a in alerts:
        color = "#b91c1c" if a["severity"] == "HIGH" else "#a16207"
        bg = "#fef2f2" if a["severity"] == "HIGH" else "#fefce8"
        side_str = a.get("entry_side") or ""
        if a.get("side_flipped"):
            side_str = f"{a.get('entry_side')} -> {a.get('today_side')}"
        price_str = ""
        if a.get("entry_price") and a.get("current_price"):
            try:
                pct = (float(a["current_price"]) - float(a["entry_price"])) / float(a["entry_price"]) * 100
                price_str = f"  Price: ${a['entry_price']:.2f} -> ${a['current_price']:.2f} ({pct:+.1f}%)"
            except Exception:
                pass
        rows.append(
            f"<div style='padding:10px 14px; margin:6px 0; background:{bg}; border-left:4px solid {color}; border-radius:5px;'>"
            f"<div style='font-weight:800; color:{color}; font-size:13px;'>"
            f"[{a['severity']}] {a['ticker']} - {a['alert_type'].replace('_', ' ')}"
            f"</div>"
            f"<div style='font-size:12px; color:#374151; margin-top:4px; line-height:1.4;'>"
            f"{a['message']}"
            f"</div>"
            f"<div style='font-size:11px; color:#6b7280; margin-top:4px;'>"
            f"Opened {a['entry_scan_date']} as {side_str}{price_str}"
            f"</div>"
            f"</div>"
        )
    return (
        "<hr class='section-rule'>"
        "<div class='section-label' style='color:#b91c1c;'>EXIT WARNINGS - Open positions losing conviction</div>"
        + "".join(rows)
    )


def format_drift_alerts_text(alerts):
    if not alerts:
        return ""
    lines = ["=" * 60, "EXIT WARNINGS - open positions losing conviction", "=" * 60]
    for a in alerts:
        lines.append(f"\n[{a['severity']}] {a['ticker']} ({a['alert_type']})")
        lines.append(f"  {a['message']}")
        if a.get("entry_price") and a.get("current_price"):
            try:
                pct = (float(a["current_price"]) - float(a["entry_price"])) / float(a["entry_price"]) * 100
                lines.append(f"  Price: ${a['entry_price']:.2f} -> ${a['current_price']:.2f} ({pct:+.1f}%)")
            except Exception:
                pass
    return "\n".join(lines)

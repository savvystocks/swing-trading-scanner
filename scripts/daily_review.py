"""Daily hyper-critical review of the flow scanner's picks.

Every evening after close this hands the day's output to Claude with a
ruthless-reviewer brief and asks the questions that dial the system in:
  - Is each pick's thesis real institutional conviction or a data artifact?
  - For open positions, is the flow following through or fading?
  - What is the exit discipline now, per the tier's rules?
  - Which patterns look predictive and which look like noise?
  - What is the single biggest thing the scanner is getting wrong, and the
    concrete testable fix?

It marks every open conviction pick to market (current option mid vs entry)
and folds in any trade that resolved today. Until the first outcomes resolve
(~7 days after the earliest MAX/ELITE picks) the review grades pick QUALITY and
tracks open positions; the win/loss autopsy section switches on automatically
once resolved trades exist.

Saves data/reviews/review_YYYY-MM-DD.md and emails it.

Env: ANTHROPIC_API_KEY, UNUSUAL_WHALES_TOKEN, GMAIL_USER, GMAIL_APP_PASSWORD.
"""

import os
import sys
import json
import glob
import smtplib
import pathlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.conviction_log import load_log
from src.unusual_whales_api import get_client

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

MODEL = os.environ.get("REVIEW_LLM_MODEL", "claude-sonnet-4-6")
RESULTS_DIR = pathlib.Path(__file__).parent.parent / "data" / "results"
REVIEW_DIR = pathlib.Path(__file__).parent.parent / "data" / "reviews"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)


REVIEWER_BRIEF = """You are the ruthless in-house reviewer for a one-man options-flow swing-trading system. Your job is to find what is WRONG with today's picks and tell the operator the truth, even when it is unflattering. He is trying to grow a 4,000 pound account to 20,000 and cannot afford polite, vague feedback. You are not a cheerleader and you do not pad.

The system surfaces live institutional options flow from Unusual Whales, scores each name on a stack of patterns (NOPE dealer-delta pressure, gamma-flip magnet, sweeps-then-floor, volume>open-interest = new positioning, above-ask urgency, institutional premium size, whisper-vs-consensus), and tiers them MODERATE / STRONG / ELITE / MAX_CONVICTION / GAMMA_BOMB. Picks are slightly-OTM calls or puts, 21-30 days out, held for a swing.

You receive:
- TODAY'S PICKS: ticker, side, tier, score, the patterns that fired with their numbers, the exact option ticket, total flow premium, and how many universe sources surfaced it.
- OPEN POSITIONS (the conviction log, marked to market): entry premium vs current premium, percent move, days held, the tier's hold window.
- RESOLVED TODAY: any trade that hit its review window, with realized percent and WIN/LOSS.

For EACH pick today, deliver three crisp lines:
1. REAL or ARTIFACT - is the thesis genuine institutional conviction, or a data quirk (zero/near-zero open-interest ratios, a single large print, a stale or mean-reverting NOPE, thin premium dressed up as size)? Name the specific tell.
2. WORKING or FADING - for anything also held open, is it moving the predicted way? Is the flow following through?
3. EXIT - given days held, premium decay and the tier's hold window, what do the SYSTEM'S rules imply now: take profit, cut, or hold, and the specific trigger.

Then system-level:
- PATTERN AUDIT: across today, which signals look predictive and which look like noise. Be specific and name them.
- BIGGEST FLAW: the single biggest thing the scanner got wrong today, and ONE concrete, testable fix (e.g. "down-weight above-ask when premium < 10M", "NOPE on utilities mean-reverts - cap its score there").
- GRADE: one letter grade (A-F) for the quality of today's picks, with one line of justification.

Rules:
- Brutal honesty over encouragement. Mediocre day, say mediocre. A MAX_CONVICTION pick that is junk, say junk and why.
- Specific and quantified. "NEE scored 105 off a 1300x vol/OI on a zero-OI strike - a divide-by-zero artifact, not conviction" beats "NEE looks weak".
- No hedging filler. No "keep an eye on", "could go either way", "time will tell".
- These are the SYSTEM'S own tracked paper picks, not the operator's brokerage positions. Frame every exit as what the system's rules imply, never as personal financial advice.
- Plain text with light markdown headings. No emojis."""


def _now():
    return datetime.now(timezone.utc)


def _parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _load_scan(date_str):
    path = RESULTS_DIR / f"flow_scan_{date_str}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")), date_str
        except Exception:
            pass
    # Fall back to the most recent scan file
    files = sorted(glob.glob(str(RESULTS_DIR / "flow_scan_*.json")))
    if not files:
        return None, date_str
    latest = files[-1]
    fallback_date = pathlib.Path(latest).stem.replace("flow_scan_", "")
    try:
        return json.loads(pathlib.Path(latest).read_text(encoding="utf-8")), fallback_date
    except Exception:
        return None, date_str


def _current_mark(uw, entry):
    """Mark an open conviction entry to market: current option mid + spot + % move."""
    tt = entry.get("trade_ticket") or {}
    ticker = entry.get("ticker")
    occ = tt.get("occ_symbol")
    entry_mid = tt.get("mid")
    if not (ticker and occ and entry_mid):
        return None
    try:
        data = uw._request(f"/stock/{ticker}/option-contracts", None,
                           cache_key="oi_per_strike", ttl=600)
        rows = (data or {}).get("data") or []
        cur_mid = None
        for r in rows:
            if isinstance(r, dict) and r.get("option_symbol") == occ:
                bid = float(r.get("nbbo_bid") or 0)
                ask = float(r.get("nbbo_ask") or 0)
                cur_mid = (bid + ask) / 2 if (bid and ask) else float(r.get("last_price") or 0)
                break
        if not cur_mid:
            return None
        spot_data = uw.stock_state(ticker)
        cur_spot = float((spot_data or {}).get("data", {}).get("close") or 0)
        logged = _parse_iso(entry.get("logged_at"))
        days_held = (_now() - logged).days if logged else 0
        pct = (cur_mid - entry_mid) / entry_mid * 100 if entry_mid else 0
        return {"cur_mid": round(cur_mid, 2), "entry_mid": entry_mid,
                "pct": round(pct, 1), "cur_spot": round(cur_spot, 2),
                "days_held": days_held}
    except Exception:
        return None


def _fmt_pick(p):
    c = p.get("_confluence") or {}
    tt = c.get("trade_ticket") or {}
    pick_side = c.get("side")
    scored, contra = [], []
    for pf in (c.get("patterns_fired") or []):
        lbl = pf.get("label")
        if not lbl:
            continue
        if pf.get("side") and pf.get("side") != pick_side:
            contra.append(lbl)
        else:
            scored.append(lbl)
    out = (
        f"{p.get('ticker')} {pick_side} | tier {c.get('tier')} | score {c.get('score')} | "
        f"premium ${(p.get('total_premium') or (p.get('_uw_flow') or {}).get('total_premium') or 0)/1e6:.1f}M | "
        f"sources {len(set(p.get('sources') or []))}\n"
        f"   ticket: {tt.get('occ_symbol')} | strike {tt.get('strike')} exp {tt.get('expiry')} "
        f"({tt.get('dte')}d) | mid {tt.get('mid')} delta {tt.get('delta')} | "
        f"target {c.get('target_pct')}% stop {c.get('stop_pct')}% hold {c.get('max_hold_days')}d\n"
        f"   patterns (scored, {pick_side} side): " + "; ".join(scored)
    )
    if contra:
        out += f"\n   contrarian flow ({'PUT' if pick_side == 'CALL' else 'CALL'} side, NOT scored): " + "; ".join(contra)
    return out


def build_digest(scan, scan_date, uw):
    lines = [f"REVIEW DATE: {scan_date}",
             f"Macro regime: {((scan.get('macro') or {}).get('meta_regime') or {}).get('regime', 'UNKNOWN')}",
             f"Universe scanned: {scan.get('universe_size')} | UW calls: {scan.get('uw_calls_made')}",
             ""]

    lines.append("=== TODAY'S PICKS ===")
    picks = [p for stream in ("calls", "puts") for p in (scan.get(stream) or [])
             if (p.get("_confluence") or {}).get("tier") not in (None, "PASS")]
    picks.sort(key=lambda p: (p.get("_confluence") or {}).get("score", 0), reverse=True)
    for p in picks:
        lines.append(_fmt_pick(p))
        lines.append("")

    log = load_log()
    open_entries = [e for e in log if not e.get("outcome")]
    resolved_today = [e for e in log if (e.get("outcome") or {}).get("checked_at", "")[:10] == _now().isoformat()[:10]]

    lines.append("=== OPEN POSITIONS (marked to market) ===")
    if not open_entries:
        lines.append("(none open)")
    for e in open_entries[:25]:
        mark = _current_mark(uw, e) if uw.enabled else None
        if mark:
            lines.append(
                f"{e['ticker']} {e['side']} {e['tier']} (logged {e['scan_date']}): "
                f"entry mid {mark['entry_mid']} -> now {mark['cur_mid']} ({mark['pct']:+.1f}%), "
                f"spot {mark['cur_spot']}, {mark['days_held']}d held")
        else:
            lines.append(f"{e['ticker']} {e['side']} {e['tier']} (logged {e['scan_date']}): no live mark")
    lines.append("")

    lines.append("=== RESOLVED TODAY ===")
    if not resolved_today:
        lines.append("(no trades hit their review window today - win/loss autopsy not yet active)")
    for e in resolved_today:
        o = e.get("outcome") or {}
        lines.append(f"{e['ticker']} {e['side']} {e['tier']}: {o.get('result')} "
                     f"({o.get('pct_return', '?')}%, {o.get('days_held', '?')}d)")

    return "\n".join(lines), bool(resolved_today)


def review_with_claude(digest, has_outcomes):
    if not ANTHROPIC_AVAILABLE or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    client = anthropic.Anthropic()
    note = ("" if has_outcomes else
            "\n\nNote: no trades have resolved yet, so skip the win/loss autopsy and focus "
            "on pick quality (real vs artifact), open-position follow-through, and what to dial in.")
    resp = client.messages.create(
        model=MODEL,
        max_tokens=9000,
        thinking={"type": "enabled", "budget_tokens": 3000},
        system=[{"type": "text", "text": REVIEWER_BRIEF + note,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": digest}],
    )
    return next((b.text for b in resp.content if b.type == "text"), "")


def _to_html(md, scan_date, grade_hint):
    body = (md or "(LLM review unavailable - ANTHROPIC_API_KEY not set)").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<html><body style="background:#0d0d0d;color:#e0e0e0;font-family:-apple-system,Segoe UI,Arial,sans-serif;padding:16px;">
<h2 style="color:#00ff88;margin:0 0 4px;">DAILY SCAN REVIEW - {scan_date}</h2>
<p style="color:#888;margin:0 0 16px;font-size:13px;">Hyper-critical review of the flow scanner's picks. System paper picks only.</p>
<pre style="white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;line-height:1.5;color:#e8e8e8;">{body}</pre>
</body></html>"""


def send_email(html, scan_date):
    user = os.environ.get("GMAIL_USER", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not user or not pw:
        print("GMAIL creds not set - skipping email (review still saved to disk)")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Scan Review - {scan_date}"
    msg["From"] = user
    msg["To"] = user
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(user, pw)
            smtp.sendmail(user, user, msg.as_string())
        print(f"Review emailed to {user}")
        return True
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")
        return False


def main():
    target = os.environ.get("CATALYST_DATE", "").strip() or _now().isoformat()[:10]
    scan, scan_date = _load_scan(target)
    if not scan:
        print("No scan file found - nothing to review")
        return

    uw = get_client()
    digest, has_outcomes = build_digest(scan, scan_date, uw)
    print(f"Digest built for {scan_date} ({len(digest)} chars). Outcomes active: {has_outcomes}")

    review = review_with_claude(digest, has_outcomes)
    if review:
        print("\n" + "=" * 70)
        print(review)
        print("=" * 70 + "\n")
    else:
        print("LLM review skipped (no ANTHROPIC_API_KEY or SDK).")

    md_path = REVIEW_DIR / f"review_{scan_date}.md"
    md_path.write_text(
        f"# Daily Scan Review - {scan_date}\n\n{review or '(LLM unavailable)'}\n\n"
        f"---\n\n## Raw digest\n\n```\n{digest}\n```\n", encoding="utf-8")
    print(f"Saved {md_path}")

    if review and os.environ.get("SKIP_EMAIL") != "1":
        send_email(_to_html(review, scan_date, None), scan_date)


if __name__ == "__main__":
    main()

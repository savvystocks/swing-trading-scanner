import os
import logging
import re
import requests

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def send_alert(text):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    try:
        r = requests.post(API_URL, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")
        return False


def send_priority_alerts(scan):
    """Fire phone push alerts for the high-priority signals in today's scan.

    Four alert types:
    1. REVIEW MODE triggered (drawdown or loss streak)
    2. EXIT WARNINGS on live positions (drift detector)
    3. ELITE confluence picks (5+ signals, 3+ categories, includes positioning)
    4. Bidirectional positioning summary (CALL + PUT extremes)
    """
    if not BOT_TOKEN or not CHAT_ID:
        return 0
    sent = 0
    scan_date = scan.get("scan_date", "?")

    bidir = scan.get("bidirectional") or {}
    bidir_summary = bidir.get("summary") or {}
    elite_calls = bidir_summary.get("elite_calls", 0)
    elite_puts = bidir_summary.get("elite_puts", 0)
    if elite_calls >= 1 or elite_puts >= 1:
        lines = [
            "<b>POSITIONING SIGNAL</b>",
            f"Date: {scan_date}",
            f"Macro: {bidir_summary.get('macro_regime', 'NEUTRAL')}",
            "",
            bidir_summary.get("thesis_summary", ""),
            "",
        ]
        calls = (bidir.get("calls") or [])[:3]
        if calls:
            lines.append("<b>CALL candidates:</b>")
            for c in calls:
                pf = c.get("_positioning_first") or {}
                top_signals = [s.get("key", "?") for s in (pf.get("positioning_signals") or [])[:2]]
                lines.append(f"- {c.get('ticker', '?')} ({pf.get('conviction_tier', '?')} {pf.get('score', 0)}): {', '.join(top_signals)}")
            lines.append("")
        puts = (bidir.get("puts") or [])[:3]
        if puts:
            lines.append("<b>PUT candidates:</b>")
            for c in puts:
                pf = c.get("_positioning_first") or {}
                top_signals = [s.get("key", "?") for s in (pf.get("positioning_signals") or [])[:2]]
                lines.append(f"- {c.get('ticker', '?')} ({pf.get('conviction_tier', '?')} {pf.get('score', 0)}): {', '.join(top_signals)}")
        if send_alert("\n".join(lines)):
            sent += 1

    gs = scan.get("guardrail_state") or {}
    if gs.get("mode") == "REVIEW_MODE":
        triggers = gs.get("triggers") or []
        high_triggers = [t for t in triggers if t.get("severity") == "HIGH"]
        if high_triggers:
            lines = ["<b>REVIEW MODE TRIGGERED</b>", f"Date: {scan_date}", ""]
            for t in high_triggers:
                lines.append(f"- {t.get('message', '')}")
            lines.append("")
            lines.append("Pause new entries until you've reviewed thesis.")
            if send_alert("\n".join(lines)):
                sent += 1

    drift = scan.get("conviction_drift_alerts") or []
    live_high = [a for a in drift if a.get("severity") == "HIGH" and a.get("is_live")]
    for alert in live_high[:3]:
        lines = [
            f"<b>EXIT ALERT: {alert.get('ticker')}</b>",
            f"Type: {(alert.get('alert_type') or '').replace('_', ' ')}",
            f"{alert.get('message', '')}",
        ]
        if send_alert("\n".join(lines)):
            sent += 1

    aa = scan.get("aa_results") or {}
    elite_picks = []
    for tier in ("A++", "A+", "A"):
        for p in aa.get(tier) or []:
            conf = p.get("_confluence") or {}
            action = (p.get("_action_signal") or {}).get("action")
            if action == "TAKE" and conf.get("sizing_tier") == "ELITE":
                elite_picks.append(p)
    for p in elite_picks[:3]:
        conf = p.get("_confluence") or {}
        ticker = p.get("ticker")
        firing = conf.get("signals_firing") or []
        signal_labels = [s.get("label") for s in firing[:5] if s.get("label")]
        lines = [
            f"<b>ELITE PICK: {ticker}</b>",
            f"Confluence: {conf.get('confluence_count')}/16 across {conf.get('category_breadth')} categories",
            f"Sizing: {conf.get('recommended_size_pct')}% (max position)",
            "",
            "Signals firing:",
        ]
        for s in signal_labels:
            lines.append(f"- {s}")
        if send_alert("\n".join(lines)):
            sent += 1

    return sent


def _first_sentence(text, max_len=200):
    if not text:
        return ""
    clean = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"^(.{30,}?[.!?])\s+[A-Z]", clean)
    if match:
        return match.group(1).rstrip(".!?")
    if clean.endswith("..."):
        return clean[:-3].rstrip(" .,")
    return clean[:max_len].rstrip(" .,")


def _strongest_drivers(t):
    drivers = []
    pillars = t.get("pillars", {})
    conv = t.get("conviction") or {}
    breakdown = conv.get("breakdown", {})

    p1 = pillars.get("p1", {})
    p3 = pillars.get("p3", {})
    p4 = pillars.get("p4", {})
    p6 = pillars.get("p6", {})
    p7 = pillars.get("p7", {})
    g4 = t.get("gates", {}).get("g4", {})
    g7 = t.get("gates", {}).get("g7", {})

    if "7/7" in p1.get("summary", ""):
        drivers.append("textbook Minervini setup (7/7 trend, Stage 2)")
    elif "6/7" in p1.get("summary", "") and "stage 2" in p1.get("summary", ""):
        drivers.append("clean Stage 2 uptrend")

    p3_summary = p3.get("summary", "")
    eps_match = re.search(r"EPS YoY ([+-]?\d+\.?\d*)%", p3_summary)
    rev_match = re.search(r"Rev YoY ([+-]?\d+\.?\d*)%", p3_summary)
    if eps_match and rev_match:
        eps = float(eps_match.group(1))
        rev = float(rev_match.group(1))
        if eps >= 30 and rev >= 20:
            drivers.append(f"accelerating growth (EPS +{eps:.0f}%, revenue +{rev:.0f}%)")
        elif eps >= 25:
            drivers.append(f"strong earnings growth (+{eps:.0f}% YoY)")

    p4_summary = p4.get("summary", "")
    rs_match = re.search(r"RS ([+-]?\d+\.?\d*)%", p4_summary)
    if rs_match:
        rs = float(rs_match.group(1))
        if rs >= 5:
            drivers.append(f"leading the tape (+{rs:.1f}% vs benchmark)")
        elif rs >= 3:
            drivers.append(f"outperforming the market ({rs:+.1f}% vs benchmark)")

    if p6.get("verdict") == "PASS_BONUS":
        beats_match = re.search(r"beats=(\d+)", p6.get("summary", ""))
        n = beats_match.group(1) if beats_match else "multiple"
        drivers.append(f"active beat-and-raise cycle ({n} consecutive beats)")

    if p7.get("verdict") in ("PASS", "PASS_BONUS"):
        si_match = re.search(r"SI ([\d.]+)%", p7.get("summary", ""))
        if si_match:
            si = float(si_match.group(1))
            if si >= 20:
                drivers.append(f"coiled-spring short interest ({si:.0f}% of float)")
            elif si >= 10:
                drivers.append(f"moderate short-squeeze fuel ({si:.0f}% SI)")

    if "POST-EARN" in g7.get("summary", ""):
        drivers.append("post-earnings momentum holding")

    if "Tier A" in g4.get("summary", ""):
        drivers.append("Tier A catalyst")

    udv = breakdown.get("up_down_vol", {})
    if udv.get("value") and isinstance(udv.get("value"), (int, float)) and udv["value"] >= 2.0:
        drivers.append(f"heavy institutional accumulation ({udv['value']:.1f}x up/down volume)")

    mtf = breakdown.get("multi_tf_trend", {})
    if mtf.get("value") == "weekly uptrend":
        drivers.append("weekly chart confirms daily trend")

    return drivers


def _caveats(t):
    notes = []
    g7 = t.get("gates", {}).get("g7", {})
    stress = t.get("stress") or {}
    conv = t.get("conviction") or {}
    breakdown = conv.get("breakdown", {})

    summary = g7.get("summary", "")
    days_match = re.search(r"\((\d+) days\)", summary)
    if days_match:
        days = int(days_match.group(1))
        if 10 < days <= 20:
            notes.append(f"earnings in {days} days — enter with a hard broker stop in place")

    if stress.get("overall") == "WARN":
        worst = None
        for key, test in stress.get("tests", {}).items():
            if test.get("label") == "FAIL":
                worst = key
                break
            if test.get("label") == "WARN" and worst is None:
                worst = key
        if worst == "drawdown_1y":
            notes.append("has had a meaningful 1-year drawdown, size accordingly")
        elif worst == "beta":
            notes.append("high beta — expect bigger intraday swings")
        elif worst == "spy_correlation":
            notes.append("highly correlated with SPY, edge depends on broad market")
        elif worst == "gap_frequency_1y":
            notes.append("prone to gap moves, tight stops may get run")

    pivot = breakdown.get("pivot_proximity", {})
    val = pivot.get("value", "")
    if isinstance(val, str):
        m = re.search(r"([+-]?\d+\.?\d*)%", val)
        if m and float(m.group(1)) > 20:
            notes.append("extended from the 50-day — wait for a pullback rather than chasing")

    return notes


def build_paragraph(t):
    parts = []

    desc = t.get("description", "")
    opener = _first_sentence(desc, max_len=180)
    if opener:
        parts.append(opener.rstrip(".") + ".")
    else:
        sector = t.get("sector", "")
        if sector:
            parts.append(f"{sector} name in the scanner universe.")

    drivers = _strongest_drivers(t)
    if drivers:
        top_drivers = drivers[:3]
        parts.append("Setup: " + ", ".join(top_drivers) + ".")

    conv = t.get("conviction") or {}
    score = conv.get("score")
    if score is not None:
        if score >= 75:
            conv_phrase = f"Conviction score {score}/100 is top-tier — this is one of the cleanest setups in today's universe."
        elif score >= 60:
            conv_phrase = f"Conviction {score}/100 — solid quality ranking, multiple confirmations."
        elif score >= 45:
            conv_phrase = f"Conviction {score}/100 — tradeable but not the strongest in today's list."
        else:
            conv_phrase = f"Conviction {score}/100 — tier says yes but the quality ranking is modest; consider smaller size."
        parts.append(conv_phrase)

    caveats = _caveats(t)
    if caveats:
        parts.append("Watch: " + "; ".join(caveats) + ".")

    return " ".join(parts)


def _stress_label(t):
    st = t.get("stress") or {}
    overall = st.get("overall")
    if overall == "PASS":
        return "[STRESS PASS]"
    if overall == "WARN":
        return "[STRESS WARN]"
    if overall == "FAIL":
        return "[STRESS FAIL]"
    return ""


def send_catalyst_alert(scan, max_picks=5):
    candidates = scan.get("candidates", [])
    strong = sorted(
        [c for c in candidates if c.get("bucket") == "STRONG"],
        key=lambda c: c["score"], reverse=True,
    )[:max_picks]
    if not strong:
        text = (
            f"<b>CATALYST SCAN {scan.get('scan_date', '')}</b>\n"
            f"No STRONG picks today. {scan.get('scored_total', 0)} names scored, "
            f"{scan.get('passed_cutoff', 0)} above WATCH threshold.\n"
            f"Check email for the WATCH list."
        )
        return send_alert(text)

    lines = [f"<b>CATALYST SCAN {scan.get('scan_date', '')} — top {len(strong)}</b>"]
    paper = scan.get("paper_stats")
    if paper and paper.get("n", 0) > 0:
        lines.append(
            f"\n<i>Paper P&amp;L 30d: ${paper['total_pnl_usd']:+.0f} on {paper['n']} trades, "
            f"win rate {paper['win_rate_pct']}%</i>"
        )

    for c in strong:
        bs = c.get("buy_signal") or {}
        signal = bs.get("signal", "?")
        prob = bs.get("probability_pct", 0)
        entry = bs.get("entry_price", 0)
        t1 = bs.get("target_1_price", 0)
        t2 = bs.get("target_2_price", 0)
        stop = bs.get("stop_price", 0)

        flags = []
        if c.get("deal_closed"):
            flags.append("DEAL CLOSED")
        if (c.get("components", {}).get("drift") or {}).get("extended"):
            flags.append("EXTENDED")
        if (c.get("components", {}).get("drift") or {}).get("pre_priced"):
            flags.append("PRE-PRICED")
        flag_str = f" [{' · '.join(flags)}]" if flags else ""

        deep = c.get("deep_research") or {}
        verdict = deep.get("verdict", "")
        verdict_str = f" → {verdict}" if verdict else ""

        cats = c.get("catalysts") or []
        primary = cats[0]["label"][:35] if cats else ""

        lines.append(
            f"\n<b>{c['ticker']}</b> · {signal} {prob}%{verdict_str}{flag_str}\n"
            f"  {primary}\n"
            f"  Entry ${entry:.2f} · Stop ${stop:.2f} · T1 ${t1:.2f} · T2 ${t2:.2f}"
        )

    lines.append(f"\n<i>Full email + deep research notes in your inbox.</i>")
    return send_alert("\n".join(lines))


def send_failure_alert(scan_date, error_msg):
    text = (
        f"<b>CATALYST SCAN FAILED — {scan_date}</b>\n\n"
        f"<code>{error_msg[:500]}</code>\n\n"
        f"Check GitHub Actions logs."
    )
    return send_alert(text)


def send_swing_alerts(tickets, min_tier=4, tier4_min_conviction=70):
    def _qualifies(t):
        tier = t.get("tier")
        if not tier or tier < min_tier:
            return False
        if tier >= 5:
            return True
        conv = (t.get("conviction") or {}).get("score")
        return conv is not None and conv >= tier4_min_conviction

    top = [t for t in tickets if _qualifies(t)]
    if not top:
        return 0
    top = sorted(top, key=lambda t: (t["tier"], (t.get("conviction") or {}).get("score") or 0), reverse=True)
    count = 0
    for t in top[:10]:
        tier = t["tier"]
        conv = t.get("conviction") or {}
        conv_score = conv.get("score")
        conv_str = f" · CONV {conv_score}/100" if conv_score is not None else ""
        stress_tag = _stress_label(t)

        post = ""
        g7 = t.get("gates", {}).get("g7", {})
        if "POST-EARN" in g7.get("summary", ""):
            post = " POST-EARN"

        sector_line = ""
        if t.get("sector"):
            sector_line = f"\n{t['sector']}"
            if t.get("industry"):
                sector_line += f" / {t['industry']}"

        paragraph = build_paragraph(t)

        options_block = ""
        opt = t.get("options_trade")
        if opt:
            options_block = (
                f"\n\n<b>Options swing trade</b>\n"
                f"{opt['strike']:.0f} call · exp {opt['expiration']} ({opt['dte']}d)\n"
                f"Premium ${opt['premium_mid']:.2f} (cost ${opt['cost_per_contract']:.0f}/contract) · delta {opt['delta']}\n"
                f"Breakeven ${opt['breakeven']:.2f} ({opt['breakeven_pct_move']:+.1f}% move) · IV {opt['iv_pct']}%\n"
                f"If stock hits +50% target: contract ~${opt['projected_value_at_target']:.2f} "
                f"(+{opt['projected_roi_pct']:.0f}% on premium)"
            )

        text = (
            f"<b>TIER {tier}{conv_str}{post}</b> {stress_tag}\n"
            f"<b>{t['ticker']}</b> · {t.get('name', '')[:32]}{sector_line}\n\n"
            f"Entry ${t['price']:.2f} · Stop ${t['stop_loss']:.2f} · "
            f"Target ${t['phase1_target']:.2f} (+50%) · R/R {t.get('risk_reward', '?')}\n\n"
            f"<i>{paragraph}</i>"
            f"{options_block}"
        )
        if send_alert(text):
            count += 1
    return count

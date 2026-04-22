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

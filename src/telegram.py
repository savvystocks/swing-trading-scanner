import os
import logging
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


def _explain_swing(t):
    parts = []
    pillars = t.get("pillars", {})

    p1 = pillars.get("p1", {})
    if "7/7" in p1.get("summary", ""):
        parts.append("perfect Minervini trend template (all 7 criteria pass)")
    elif "PASS" in p1.get("verdict", ""):
        parts.append("strong uptrend confirmed by Minervini template")

    p2 = pillars.get("p2", {})
    if "PASS" in p2.get("verdict", ""):
        parts.append("Bollinger squeeze detected (volatility contracting before breakout)")

    p3 = pillars.get("p3", {})
    if "PASS" in p3.get("verdict", ""):
        summary = p3.get("summary", "")
        parts.append(f"strong fundamentals ({summary})")

    p4 = pillars.get("p4", {})
    if "PASS" in p4.get("verdict", ""):
        parts.append(f"outperforming the market ({p4.get('summary', '')})")

    p7 = pillars.get("p7", {})
    if "PASS" in p7.get("verdict", ""):
        parts.append(f"short squeeze potential ({p7.get('summary', '')})")

    g7 = t.get("gates", {}).get("g7", {})
    if "POST-EARN CATALYST" in g7.get("summary", ""):
        parts.append("just beat earnings and holding the gap (post-earnings momentum)")

    sector = t.get("sector", "")
    if sector:
        parts.append(f"sector: {sector}")

    return ". ".join(parts) + "." if parts else ""


def send_swing_alerts(tickets, min_tier=4):
    top = [t for t in tickets if t.get("tier") and t["tier"] >= min_tier]
    if not top:
        return 0
    count = 0
    for t in top[:10]:
        post = ""
        g7 = t.get("gates", {}).get("g7", {})
        if "POST-EARN" in g7.get("summary", ""):
            post = " POST-EARN"
        explanation = _explain_swing(t)
        text = (
            f"<b>SWING TIER {t['tier']}{post}</b>\n"
            f"<b>{t['ticker']}</b> {t.get('name', '')[:25]}\n"
            f"Entry ${t['price']:.2f} | Stop ${t['stop_loss']:.2f}\n"
            f"Target ${t['phase1_target']:.2f} (+50%) | R/R {t.get('risk_reward', '?')}\n\n"
            f"<i>Why: {explanation}</i>"
        )
        if send_alert(text):
            count += 1
    return count

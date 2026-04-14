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
        text = (
            f"<b>SWING TIER {t['tier']}{post}</b>\n"
            f"<b>{t['ticker']}</b> {t.get('name', '')[:25]}\n"
            f"Entry ${t['price']:.2f} | Stop ${t['stop_loss']:.2f}\n"
            f"Target ${t['phase1_target']:.2f} (+50%)\n"
            f"Pillars {t['pillars_passed']}/{t['applicable_pillars']} | R/R {t.get('risk_reward', '?')}"
        )
        if send_alert(text):
            count += 1
    return count

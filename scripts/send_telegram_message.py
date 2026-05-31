"""Send a single Telegram message from a text file.

Used by .github/workflows/send-telegram.yml to push on-demand messages
to Savvas's phone using the existing TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
GitHub secrets.

Usage:
  python scripts/send_telegram_message.py data/telegram_outbox/latest.txt
"""
import os
import sys
import requests


def main():
    if len(sys.argv) < 2:
        print("usage: send_telegram_message.py <message_file>")
        sys.exit(2)
    msg_path = sys.argv[1]
    if not os.path.exists(msg_path):
        print(f"message file not found: {msg_path}")
        sys.exit(2)
    with open(msg_path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        print("message file is empty")
        sys.exit(2)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in env")
        sys.exit(2)

    chunks = []
    while len(text) > 3800:
        cut = text.rfind("\n", 0, 3800)
        if cut < 1000:
            cut = 3800
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    chunks.append(text)

    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": chunk, "parse_mode": "HTML"},
            timeout=15,
        )
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text[:200]}
        if not data.get("ok"):
            print(f"FAIL: {data}")
            sys.exit(2)
        print(f"sent {len(chunk)} chars")


if __name__ == "__main__":
    main()

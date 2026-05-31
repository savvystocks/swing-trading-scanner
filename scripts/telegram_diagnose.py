"""Diagnose Telegram bot setup. Identify bot + chat, send verification."""
import os
import sys
import requests


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("FAIL: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in env")
        sys.exit(2)

    print("=== Bot Identity (getMe) ===")
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = r.json()
        if data.get("ok"):
            bot = data["result"]
            print(f"  Bot username: @{bot.get('username')}")
            print(f"  Bot first name: {bot.get('first_name')}")
            print(f"  Bot ID: {bot.get('id')}")
            print(f"  Can join groups: {bot.get('can_join_groups')}")
        else:
            print(f"  FAIL: {data}")
            sys.exit(2)
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(2)

    print()
    print("=== Chat Identity (getChat) ===")
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getChat", params={"chat_id": chat}, timeout=10)
        data = r.json()
        if data.get("ok"):
            ch = data["result"]
            print(f"  Chat ID: {ch.get('id')}")
            print(f"  Chat type: {ch.get('type')}")
            print(f"  Chat title: {ch.get('title', '(private)')}")
            print(f"  Chat first name: {ch.get('first_name', '')}")
            print(f"  Chat last name: {ch.get('last_name', '')}")
            print(f"  Chat username: @{ch.get('username', '')}")
        else:
            print(f"  FAIL: {data}")
            sys.exit(2)
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(2)

    print()
    print("=== Sending verification message ===")
    from datetime import datetime
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    verification_text = (
        f"<b>Telegram verification {timestamp}</b>\n\n"
        f"If you see this, the bot @{data['result'].get('username', '?')} is correctly "
        f"connected to your Telegram chat (ID {chat}).\n\n"
        f"Position update for ETOR is in the next message."
    )
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": verification_text, "parse_mode": "HTML"},
        timeout=10,
    )
    data = r.json()
    if data.get("ok"):
        print(f"  Verification sent: message_id {data['result'].get('message_id')}")
    else:
        print(f"  FAIL: {data}")
        sys.exit(2)

    print()
    print("=== Sending position read (from data/telegram_outbox/latest.txt) ===")
    msg_path = "data/telegram_outbox/latest.txt"
    if not os.path.exists(msg_path):
        print(f"  No message file at {msg_path}")
        sys.exit(0)
    with open(msg_path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    chunks = []
    while len(text) > 3800:
        cut = text.rfind("\n", 0, 3800)
        if cut < 1000:
            cut = 3800
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    chunks.append(text)
    for i, chunk in enumerate(chunks, 1):
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": chunk, "parse_mode": "HTML"},
            timeout=10,
        )
        data = r.json()
        if not data.get("ok"):
            print(f"  Chunk {i} FAIL: {data}")
            sys.exit(2)
        print(f"  Chunk {i}: sent {len(chunk)} chars, message_id {data['result'].get('message_id')}")


if __name__ == "__main__":
    main()

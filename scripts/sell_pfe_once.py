"""One-shot owner-ordered cleanup (2026-08-31): sell the 1,300 PFE ghost shares at tomorrow's
open. They are the auto-exercise residue of a V10-era ITM call (2026-07-02) whose option record
was flushed - $37k of unmanaged single-stock exposure outside the book. Sleeps until 13:31 UTC
(one minute after open), market-sells, telegrams the fill, exits. Runs detached; safe to re-run
(position check first)."""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", ""),
     "Content-Type": "application/json"}


def tg(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass


def main():
    target = datetime(2026, 9, 1, 13, 31, tzinfo=timezone.utc)
    while datetime.now(timezone.utc) < target:
        time.sleep(30)
    try:
        req = urllib.request.Request("https://paper-api.alpaca.markets/v2/positions/PFE", headers=H)
        with urllib.request.urlopen(req, timeout=20) as r:
            pos = json.loads(r.read())
    except Exception:
        tg("PFE cleanup: no PFE position found at the broker - nothing to sell. Done.")
        return
    qty = int(float(pos.get("qty") or 0))
    if qty <= 0:
        tg("PFE cleanup: position already flat. Done.")
        return
    body = json.dumps({"symbol": "PFE", "qty": str(qty), "side": "sell",
                       "type": "market", "time_in_force": "day"}).encode()
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/orders", data=body,
                                 headers=H, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            o = json.loads(r.read())
        tg(f"PFE GHOST SOLD (owner order): market sell {qty} shares submitted at the open. "
           f"This was July's option-exercise residue riding unmanaged - banking the ~+$3,500 "
           f"and returning the book to records-match-reality. Order {o.get('id','?')[:8]}.")
        print("submitted", o.get("id"))
    except Exception as e:
        tg(f"PFE cleanup FAILED to submit: {type(e).__name__} - sell it manually or ask Claude to retry.")


if __name__ == "__main__":
    main()

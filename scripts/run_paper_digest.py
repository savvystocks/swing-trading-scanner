import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst import paper_pipeline
from src.telegram import send_alert


if __name__ == "__main__":
    cycle = paper_pipeline.run_mark_cycle()
    closed = sum(1 for a in cycle["actions"] if a.get("action") == "CLOSE")
    trimmed = sum(1 for a in cycle["actions"] if a.get("action") == "TRIM")
    d = paper_pipeline.digest()
    text = ("<b>V8.5 DAILY DIGEST</b>\n" + d["text"]
            + f"\nmark cycle: {cycle['marked']} marked, {trimmed} trimmed, {closed} closed")
    sent = send_alert(text) if "--no-telegram" not in sys.argv else False
    print(f"digest {'sent' if sent else 'not sent'} | marked {cycle['marked']} closed {closed}")
    print(d["text"])

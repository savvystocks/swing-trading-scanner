import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.ambush_generator import run

if __name__ == "__main__":
    if "--test-ping" in sys.argv:
        from src.telegram import send_alert
        ok = send_alert("<b>AMBUSH TEST PING</b>\nAlert pipe is live. This is a one-time test, not a trade signal.")
        print(f"test-ping: {'sent' if ok else 'NOT sent (no token/chat or send failed)'}")
        sys.exit(0)
    run(
        preview="--preview" in sys.argv,
        force="--force" in sys.argv,
        alert="--alert" in sys.argv,
    )

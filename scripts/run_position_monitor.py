import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.exit_alerts import check_open_positions, format_alert_message


def main():
    verbose = os.environ.get("EXIT_ALERTS_VERBOSE", "1") == "1"
    if verbose:
        print("=== Exit Alerts Check ===")

    triggers = check_open_positions(verbose=verbose)

    if not triggers:
        if verbose:
            print("No exit triggers fired this run.")
        return

    try:
        from src.telegram import send_alert
        telegram_available = True
    except Exception:
        telegram_available = False
        if verbose:
            print("Telegram module not available - printing alerts only")

    for t in triggers:
        msg = format_alert_message(t)
        print(f"\n{msg}\n")
        if telegram_available:
            try:
                send_alert(msg)
                if verbose:
                    print(f"  Sent Telegram alert for {t['ticker']}")
            except Exception as e:
                if verbose:
                    print(f"  Telegram failed for {t['ticker']}: {type(e).__name__}: {e}")

    print(f"\nDone: {len(triggers)} exit alerts sent")


if __name__ == "__main__":
    main()

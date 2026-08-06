"""VPS FAILOVER - EXIT PASS ONLY (owner order 2026-08-06 "make sure it doesn't happen again";
first installment of ROADMAP item 13 after the GitHub Actions incident cost a trading day).

When the GHA engine heartbeat goes stale during market hours, engine_watch.sh invokes this on
the VPS: it runs the EXIT state machine over open positions (stops/trails/expiry - the safety-
critical half of the engine) and pushes the updated records, which also refreshes the heartbeat.
It NEVER opens new positions - zero double-entry risk when GHA revives; missed entries during an
outage are accepted opportunity cost. --check mode: verify plumbing, touch nothing.
"""
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def main(check_only=False):
    now = datetime.now(timezone.utc)
    if not check_only:
        if now.weekday() > 4 or not (13 * 60 + 40 <= now.hour * 60 + now.minute <= 20 * 60):
            print(f"{now.isoformat()} outside market hours - skip")
            return 0
    import sandbox_proactive_lab as lab
    from src.alpaca_creds import working_creds
    creds = working_creds()
    if not creds or not all(creds):
        print("FAILOVER ABORT: no working Alpaca creds on this box")
        return 1
    params = lab.load_params()
    positions = lab.get_open_positions(creds)
    print(f"{now.isoformat()} failover: {len(positions)} open broker positions")
    if check_only:
        print("CHECK OK: imports, creds, positions readable - no actions taken")
        return 0
    closed, autopsies = lab.manage_open_positions(creds, params, positions=positions)
    print(f"exit pass: {len(closed)} closed, {len(autopsies)} autopsies")
    sh("git add -A data/harvest_inbox proactive_sandbox_logs.json sandbox_ticker_cooloff.json 2>/dev/null")
    st = sh("git status --porcelain --untracked-files=no")
    if st:
        sh('git commit -m "vps failover exit pass [skip ci]"')
        sh("git pull --rebase -X ours -q; git push -q")
        print("records pushed (heartbeat refreshed)")
    try:
        tok = os.environ.get("TELEGRAM_BOT_TOKEN"); chat = os.environ.get("TELEGRAM_CHAT_ID")
        if tok and chat:
            import urllib.request, urllib.parse
            msg = (f"ENGINE FAILOVER (VPS): GHA heartbeat stale - ran exit pass: "
                   f"{len(closed)} closed of {len(positions)} open. Entries paused until GHA revives.")
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(check_only="--check" in sys.argv))

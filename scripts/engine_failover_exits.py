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


def _in_session(now):
    """The XNYS session on the New York clock, 10 minutes after the open to the close (scripts/session_window.py,
    2026-10-05). The fixed 13:40-20:00 UTC gate it replaces was summer time only: from November it would have run a
    covering cycle before the open and refused the session's last hour. A helper that cannot answer lets the cycle
    run - the engine's own market gate still decides, and closed-for-exits is the exposure (BREAKDOWNS 2026-09-11)."""
    try:
        import importlib.util
        sp = importlib.util.spec_from_file_location("session_window", os.path.join(REPO, "scripts", "session_window.py"))
        sw = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(sw)
        return sw.in_window(now, close_margin_min=0)[0]
    except Exception:
        return True


def main(check_only=False):
    now = datetime.now(timezone.utc)
    if not check_only:
        if not _in_session(now):
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
    # FULL CYCLE (upgraded 2026-08-06 22:20: UW returns 200 from this box and the engine
    # imports clean - entries, exits and harvest all run here when GHA is dead. Only fires
    # when the heartbeat is >35 min stale, so GHA and VPS never trade simultaneously.)
    rec = lab.run_scheduled_cycle(mock=False)
    print(f"full failover cycle complete: entered={'yes: ' + rec['ticker'] if rec else 'none'}")
    # STAMP THE GOOD-CYCLE SENTINEL (2026-08-26 GitHub outage): a completed failover cycle IS
    # a good cycle. Without this, failover pushes kept the heartbeat fresh while the sentinel
    # went stale - the exact crash-not-dead signature - and the watchdog counted toward a
    # FALSE auto-rollback of healthy code while the real fault was GitHub's outage.
    sh("date -u +%FT%TZ > data/last_cycle_ok && git rev-parse HEAD >> data/last_cycle_ok")
    sh("git add data/last_cycle_ok 2>/dev/null")
    sh("git add -A data/harvest_inbox proactive_sandbox_logs.json sandbox_ticker_cooloff.json 2>/dev/null")
    st = sh("git status --porcelain --untracked-files=no")
    if st:
        sh('git commit -m "vps failover exit pass [skip ci]"')
        sh("git pull --rebase -X ours -q; git push -q")
        print("records pushed (heartbeat refreshed)")
    try:
        tok = os.environ.get("TELEGRAM_BOT_TOKEN"); chat = os.environ.get("TELEGRAM_CHAT_ID")
        if os.environ.get("FAILOVER_QUIET"):        # continuation ticks in failover-mode: no page
            tok = None
        if tok and chat:
            import urllib.request, urllib.parse
            msg = (f"ENGINE FAILOVER (VPS): GHA heartbeat stale - ran FULL cycle (entries+exits+harvest). "
                   f"{len(positions)} positions under management. GHA can take over any time.")
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(check_only="--check" in sys.argv))

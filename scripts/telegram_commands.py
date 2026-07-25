"""School 1e - authenticated owner commands over Telegram, polled from the VPS crontab (*/15).
Commands (from the allowlisted chat only): /halt, /resume, /flatten, /cancelflatten, /status.
Effect: writes halt.json into the harvest-snapshots checkout and pushes it; the engine's workflow
reads that flag each cycle and exports SCHOOL_HALT / SCHOOL_FLATTEN. Auth = Telegram chat id match
against TELEGRAM_CHAT_ID from the environment; anything else is ignored and logged.

Fail-open: any error leaves the previous flag state untouched. State (last update offset) in
~/telegram_commands_state.json so each command is processed exactly once.
"""
import os
import json
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timezone

SNAP = os.path.expanduser("~/harvest-snapshots")
STATE = os.path.expanduser("~/telegram_commands_state.json")
FLAG = os.path.join(SNAP, "halt.json")


def _api(method, **kw):
    tok = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{tok}/{method}"
    data = urllib.parse.urlencode(kw).encode() if kw else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.loads(r.read().decode())


def _flag_state():
    try:
        return json.load(open(FLAG))
    except Exception:
        return {"halt": False, "flatten": False}


def _write_flag(state, why):
    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    state["why"] = why
    json.dump(state, open(FLAG, "w"), indent=2)
    subprocess.run(["git", "-C", SNAP, "pull", "--rebase", "origin", "main"], capture_output=True)
    subprocess.run(["git", "-C", SNAP, "add", "halt.json"], capture_output=True)
    subprocess.run(["git", "-C", SNAP, "commit", "-m", f"owner command: {why} [skip ci]"], capture_output=True)
    subprocess.run(["git", "-C", SNAP, "push", "origin", "main"], capture_output=True)


def run():
    allow = str(os.environ.get("TELEGRAM_CHAT_ID", ""))
    if not allow:
        return
    st = {"offset": 0}
    try:
        st = json.load(open(STATE))
    except Exception:
        pass
    upd = _api("getUpdates", offset=st.get("offset", 0) + 1, timeout=0)
    if not upd.get("ok"):
        return
    for u in upd.get("result", []):
        st["offset"] = max(st.get("offset", 0), u["update_id"])
        msg = u.get("message") or {}
        chat = str((msg.get("chat") or {}).get("id", ""))
        text = (msg.get("text") or "").strip().lower()
        if chat != allow:
            print(f"ignored command from non-allowlisted chat {chat[:6]}...")
            continue
        flag = _flag_state()
        if text.startswith("/halt"):
            flag["halt"] = True
            _write_flag(flag, "HALT by owner")
            _api("sendMessage", chat_id=allow, text="HALT set - new entries pause from the next cycle. /resume to lift.")
        elif text.startswith("/resume"):
            flag["halt"] = False
            flag["flatten"] = False
            _write_flag(flag, "RESUME by owner")
            _api("sendMessage", chat_id=allow, text="RESUMED - entries re-enabled from the next cycle.")
        elif text.startswith("/cancelflatten"):
            flag["flatten"] = False
            _write_flag(flag, "FLATTEN cancelled by owner")
            _api("sendMessage", chat_id=allow, text="Flatten cancelled.")
        elif text.startswith("/flatten"):
            flag["flatten"] = True
            flag["halt"] = True
            _write_flag(flag, "FLATTEN by owner")
            _api("sendMessage", chat_id=allow,
                 text="FLATTEN armed (also halts entries) - all paper positions close at the next open-market cycle. /cancelflatten to abort before it fires.")
        elif text.startswith("/status"):
            f = _flag_state()
            _api("sendMessage", chat_id=allow,
                 text=f"halt={f.get('halt')} flatten={f.get('flatten')} (updated {f.get('updated_utc', 'never')})")
    json.dump(st, open(STATE, "w"))


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"telegram_commands failed open: {type(e).__name__}: {e}")

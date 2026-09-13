"""RETURNS ALARMS (2026-09-13): the page bundle idea pointed at performance. Nightly, after the
digest, recompute the ledger and fire ONE batched Telegram (plus an evidence bundle pushed to
main) when live returns diverge from what the evidence promised. No model in the loop; every
condition is a number the ledger already carries. Conditions, each pre-registered here:
  BIG_TRADE     a leg closed today at |return| >= 100% or |$| >= 1,500 (felt event, informational)
  DIVERGENCE    an active strategy with >= 20 live days whose live day-mean sits more than 5
                points below its archive %/day (the promise is not being kept live)
  CONCENTRATION an active strategy with >= 10 closed trades whose single best trade is more than
                half of its total positive dollars (one jackpot is carrying the book)
  CAPTURE       capture ratio < 0.6 with >= 20 live days (the proof-stint bar, watched early)
State in reports/performance/alarms_state.json so a condition pages once, not nightly."""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
STATE = "reports/performance/alarms_state.json"
BUNDLES = "reports/performance/alarm_bundles"


def tg(msg):
    try:
        tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if tok and chat:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
    except Exception:
        pass


def main():
    py = sys.executable
    subprocess.run([py, "scripts/returns_ledger.py", "--update-map"], capture_output=True, text=True)
    led = json.load(open("reports/performance/ledger.json", encoding="utf-8"))
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    today = date.today().isoformat()
    fired = []
    first_run = not state                             # seed: history is not news
    for s, x in led["strategies"].items():
        lv, ar = x.get("live") or {}, x.get("archive") or {}
        # BIG_TRADE: a closed trade the state has not seen yet whose size is a felt event
        for t in lv.get("trades") or []:
            key = f"BIG_TRADE:{t['id']}"
            if key in state:
                continue
            state[key] = today                        # seen once; never re-evaluated
            if first_run:
                continue
            if abs(t["ret"]) >= 100 or (t.get("usd") is not None and abs(t["usd"]) >= 1500):
                fired.append(("BIG_TRADE", s, f"{t['ticker']} {t['ret']:+.0f}% {('$%+.0f' % t['usd']) if t.get('usd') is not None else ''} (entered {t['day']})"))
        if not x.get("active"):
            continue
        if lv.get("units", 0) >= 20 and lv.get("unit") == "days" and isinstance(ar.get("per_day"), (int, float)):
            gap = lv["unit_mean"] - ar["per_day"]
            key = f"DIVERGENCE:{s}:{lv['units']}"
            if gap < -5 and key not in state:
                state[key] = today
                fired.append(("DIVERGENCE", s, f"live {lv['unit_mean']:+.1f}%/day vs archive {ar['per_day']:+.1f} over {lv['units']} days (gap {gap:+.1f})"))
        if lv.get("n_closed", 0) >= 10 and lv.get("trades"):
            pos = [t["usd"] for t in lv["trades"] if t.get("usd") is not None and t["usd"] > 0]
            if pos and max(pos) > 0.5 * sum(pos):
                key = f"CONCENTRATION:{s}:{lv['n_closed']}"
                if key not in state:
                    state[key] = today
                    fired.append(("CONCENTRATION", s, f"best trade ${max(pos):+,.0f} is {max(pos) / sum(pos):.0%} of ${sum(pos):,.0f} positive dollars over {lv['n_closed']} trades"))
        cap = (x.get("capture") or {}).get("ratio")
        if isinstance(cap, (int, float)) and cap < 0.6:
            key = f"CAPTURE:{s}:{lv.get('units')}"
            if key not in state:
                state[key] = today
                fired.append(("CAPTURE", s, f"capture {cap:.2f} of the archive cell over {lv.get('units')} days (bar 0.60)"))
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w", encoding="utf-8"), indent=1)
    if not fired:
        print(f"returns alarms {today}: nothing to report")
        return
    os.makedirs(BUNDLES, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = f"{BUNDLES}/{ts}_returns.md"
    L = [f"# RETURNS ALARM BUNDLE {ts}", ""]
    for kind, s, msg in fired:
        L.append(f"- {kind} {s}: {msg}")
        x = led["strategies"].get(s) or {}
        L.append(f"  ledger: live {json.dumps({k: v for k, v in (x.get('live') or {}).items() if k != 'trades'})}")
        L.append(f"  archive: {json.dumps(x.get('archive'))[:300]}")
        L.append(f"  court: {(x.get('court') or {}).get('standing')}")
    L += ["", "read next: docs/performance_map/<strategy>.md, then docs/feature_map/evidence-and-court.md"]
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    lines = [f"RETURNS ALARM ({len(fired)}):"] + [f"- {k} {s}: {m}" for k, s, m in fired] + [f"bundle: {out}"]
    tg("\n".join(lines)[:3500])
    print("\n".join(lines))
    subprocess.run(f"git add -f {out} {STATE} reports/performance/ledger.json reports/performance/ledger.md docs/performance_map && "
                   f"git -c user.name=returns -c user.email=returns@vps commit -qm 'returns alarm bundle {ts} [skip ci]' && "
                   "(git pull -q --rebase --autostash origin main || true) && git push -q origin HEAD:main", shell=True)


if __name__ == "__main__":
    main()

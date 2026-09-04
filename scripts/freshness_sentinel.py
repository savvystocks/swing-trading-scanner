"""FRESHNESS SENTINEL (owner order 2026-09-04: "keep up to date with the whole system,
make sure we have nothing in use never stale").

Born from the frozen-archive breakdown (BREAKDOWNS 2026-09-04): every process exited 0
nightly while the data underneath died for two weeks. This watches the DATA, not the exit
codes. Three check kinds:
  schedule - a file a cron writes: compute the most recent datetime its schedule should
             have fired (weekend/holiday-aware via day-of-week sets) and alarm if the file
             predates it (+2h grace). A missed weekday night alarms the next morning at
             08:00; a weekend gap never false-alarms.
  data_day - a sqlite max(day/ts) that must track the trading calendar: alarm when the
             newest data day falls more than max_td TRADING DAYS behind today.
  mtime    - a plain rolling file with a max age in hours (engine-cycle artifacts).
One batched Telegram ONLY when something is stale; Sundays send an all-clear heartbeat so
the sentinel's own death is visible (no Sunday message = the watchdog itself is down).
Cron: daily 08:00 UTC - after every nightly job, before the market day.
Registry maintenance: any NEW cron or data store ships with its row added here in the
same commit - a pipeline without a sentinel row is the next frozen archive."""
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
H = "/home/poller"
GRACE_H = 2.0

WEEKDAYS = {0, 1, 2, 3, 4}
DAILY = {0, 1, 2, 3, 4, 5, 6}

# (name, kind, target, spec, criticality)
# schedule spec: (utc_hour, utc_minute, {dows})   data_day spec: (db, query, max_td)
# mtime spec: max_hours
CHECKS = [
    # -- trade path: the engine and its lifelines
    ("engine last_cycle_ok", "schedule", "data/last_cycle_ok", (20, 30, WEEKDAYS), "TRADE"),
    ("engine records log", "schedule", "proactive_sandbox_logs.json", (20, 30, WEEKDAYS), "TRADE"),
    ("harvest poller log", "schedule", "data/poller.log", (21, 0, WEEKDAYS), "TRADE"),
    ("harvest state", "schedule", "data/harvest_state.json", (20, 30, WEEKDAYS), "TRADE"),
    ("engine watch log", "schedule", H + "/engine_watch.log", (21, 0, WEEKDAYS), "TRADE"),
    ("telegram commands log", "mtime", H + "/telegram_commands.log", 100.0, "MONITOR"),
    # -- harvest data: labels and candidates must track the market
    ("harvest candidates day", "data_day", "data/harvest.db",
     ("select date(cast(substr(cast(max(signal_ts_utc) as text),1,10) as int), 'unixepoch') from candidates", 2), "TRADE"),
    ("harvest labels day", "data_day", "data/harvest.db",
     ("select date(cast(substr(cast(max(touch_ts_utc) as text),1,10) as int), 'unixepoch') from labels", 5), "TRADE"),
    # -- evidence stores: everything tuning/promotion decisions read
    ("uw archive contracts", "data_day", "data/uw_history.db",
     ("select max(day) from contracts_daily", 3), "EVIDENCE"),
    ("uw archive prints", "data_day", "data/uw_history.db",
     ("select max(day) from flow_prints", 4), "EVIDENCE"),
    ("hourly bar library", "data_day", "data/hourly_paths.db",
     ("select max(substr(ts,1,10)) from bars", 8), "EVIDENCE"),
    ("tuner coarse corpus", "schedule", "reports/research/probe_tuner_rows.jsonl", (20, 15, {4}), "EVIDENCE"),
    ("glide fine corpus", "schedule", "reports/research/glide_fine_rows.jsonl", (21, 45, {4}), "EVIDENCE"),
    # -- nightly rhythm: courts, student, digests, integrity
    ("nightly boundary (SEQ_APPLY)", "schedule", H + "/trajectory_nightly.log", (22, 0, WEEKDAYS), "COURT"),
    ("friday court", "schedule", H + "/sunday_boundary.log", (22, 35, {4}), "COURT"),
    ("nightly student", "schedule", H + "/fade_meta.log", (22, 10, WEEKDAYS), "COURT"),
    ("shadow breaker", "schedule", "reports/shadow_lab/breaker.jsonl", (22, 12, WEEKDAYS), "COURT"),
    ("daily digest", "schedule", H + "/digest.log", (22, 20, WEEKDAYS), "MONITOR"),
    ("integrity gate", "schedule", H + "/integrity_gate.log", (22, 5, {1, 2, 3, 4, 5}), "MONITOR"),
    ("landing watch", "schedule", H + "/landing_watch.log", (22, 45, {0, 1, 2, 3, 4, 5}), "MONITOR"),
    ("archiver watch", "schedule", H + "/archiver_watch.log", (22, 15, WEEKDAYS), "MONITOR"),
    ("evening persist", "schedule", H + "/evening_persist.log", (22, 45, WEEKDAYS), "MONITOR"),
    ("off-box backup", "schedule", "data/snapshot.log", (21, 30, WEEKDAYS), "MONITOR"),
    ("uw pull log", "schedule", H + "/uw_pull.log", (22, 30, DAILY), "EVIDENCE"),
    ("uw prints log", "schedule", H + "/prints.log", (0, 15, DAILY), "EVIDENCE"),
    ("friday tuner chain", "schedule", H + "/tuner_apply.log", (21, 45, {4}), "EVIDENCE"),
]


def last_expected(hour, minute, dows, now):
    d = now.date()
    for _ in range(40):
        cand = datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)
        if d.weekday() in dows and cand <= now - timedelta(hours=GRACE_H):
            return cand
        d -= timedelta(days=1)
    return None


def trading_days_behind(day_iso, today):
    try:
        d = date.fromisoformat(day_iso[:10])
    except Exception:
        return 999
    n, cur = 0, d
    while cur < today:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def main():
    now = datetime.now(timezone.utc)
    today = now.date()
    stale, fresh = [], 0
    for name, kind, target, spec, crit in CHECKS:
        try:
            if kind == "schedule":
                exp = last_expected(spec[0], spec[1], spec[2], now)
                if exp is None:
                    continue
                mt = datetime.fromtimestamp(os.path.getmtime(target), tz=timezone.utc)
                if mt < exp:
                    stale.append(f"[{crit}] {name}: last update {mt:%a %d %H:%M}, "
                                 f"expected a run {exp:%a %d %H:%M} UTC")
                else:
                    fresh += 1
            elif kind == "data_day":
                q, max_td = spec
                con = sqlite3.connect(f"file:{target}?mode=ro", uri=True, timeout=30)
                v = con.execute(q).fetchone()[0]
                con.close()
                behind = trading_days_behind(str(v), today) if v else 999
                if behind > max_td:
                    stale.append(f"[{crit}] {name}: newest data {str(v)[:10]} - "
                                 f"{behind} trading days behind (max {max_td})")
                else:
                    fresh += 1
            else:
                age_h = (now.timestamp() - os.path.getmtime(target)) / 3600
                if age_h > spec:
                    stale.append(f"[{crit}] {name}: {age_h:.0f}h old (max {spec:.0f}h)")
                else:
                    fresh += 1
        except Exception as e:
            stale.append(f"[{crit}] {name}: CHECK FAILED - {str(e)[:60]}")
    lines = [f"FRESHNESS SENTINEL {now:%Y-%m-%d %H:%M}Z - {fresh} fresh, {len(stale)} stale"]
    lines += stale
    print("\n".join(lines), flush=True)
    heartbeat = now.weekday() == 6
    if stale or heartbeat:
        tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        msg = ("ALL FRESH - " + lines[0]) if not stale else "\n".join(lines)
        if tok and chat and os.environ.get("SENTINEL_DRY") != "1":
            try:
                urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                       urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
            except Exception:
                pass
    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()

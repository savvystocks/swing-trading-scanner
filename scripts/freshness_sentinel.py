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
# a schedule row whose log does not exist until its job first fires is "not yet due" until that firing (+ grace),
# never CHECK FAILED: name -> first scheduled firing, UTC. Rows leave this dict once their log exists for good.
FIRST_RUN = {
    "vps mirror sync": datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc),
    "proof stint judge": datetime(2026, 9, 28, 14, 7, tzinfo=timezone.utc),
}

try:                                    # holiday-aware (coverage audit 2026-09-07): the 07-02
    import pandas_market_calendars as _mcal    # harvest lesson - exchange calendars in ALL date
    _sch = _mcal.get_calendar("XNYS").schedule(
        start_date=(date.today() - timedelta(days=75)).isoformat(),
        end_date=date.today().isoformat())
    SESSIONS = {d.date() for d in _sch.index}
except Exception:
    SESSIONS = None


def is_session(d):
    return (d in SESSIONS) if SESSIONS is not None else (d.weekday() < 5)


def session_windows(today, lag, lookback, ref):
    """Sessions <= today, newest first, split into: `lag` ignored (pipeline latency), then
    `lookback` recent sessions to judge, then `ref` older sessions as the reference."""
    seq, d = [], today
    while len(seq) < lag + lookback + ref and d > today - timedelta(days=150):
        if is_session(d):
            seq.append(d)
        d -= timedelta(days=1)
    return seq[lag:lag + lookback], seq[lag + lookback:lag + lookback + ref]

# (name, kind, target, spec, criticality)
# schedule spec: (utc_hour, utc_minute, {dows})   data_day spec: (db, query, max_td)
# mtime spec: max_hours
# RETIRED 2026-09-21 (Unusual Whales ended; the directional strategies, the student, the shadow lab and
# the harvest feed are switched off): 31 rows whose data stops by design. Recoverable from git history.
CHECKS = [
    # -- trade path: the engine and its lifelines
    ("engine last_cycle_ok", "schedule", "data/last_cycle_ok", (20, 30, WEEKDAYS), "TRADE"),
    ("engine records log", "schedule", "proactive_sandbox_logs.json", (19, 30, WEEKDAYS), "TRADE"),
    # 19:30 (BREAKDOWNS 2026-09-24, third setting): proof_book.sample_equity rewrites the day's row on every
    # open-market cycle, the last at ~19:52 UTC in summer time (~20:52 in winter), and this file's mtime on the
    # VPS is the poller's quarter-hour reset that lands it (20:00 / 21:00). 14:30 paged every weekday because
    # the one write was at 13:3x and landed at 13:45; 20:30 would page every summer day for the same reason.
    # A schedule row's time is read from the writer's timestamp AND the pull that lands it, never assumed.
    ("proof book equity samples", "schedule", "proof_logs_equity.jsonl", (19, 30, WEEKDAYS), "TRADE"),
    # the poller is retired (2026-09-26) but its quarter-hour mirror of origin/main is not: scripts/mirror_sync_vps.sh
    # keeps the reset that lands the three files above, and this row proves it ran to the session's last slot
    ("vps mirror sync", "schedule", H + "/mirror_sync.log", (21, 45, WEEKDAYS), "TRADE"),
    ("engine watch log", "schedule", H + "/engine_watch.log", (19, 30, WEEKDAYS), "TRADE"),
    ("telegram commands state", "mtime", H + "/telegram_commands_state.json", 1.0, "MONITOR"),
    # RETIRED 2026-09-26 (the harvest froze on 2026-09-25 with its last label; the court's docket held no living
    # challenger): harvest poller log, nightly boundary, friday court, integrity gate, archiver watch, off-box backup,
    # off-box snapshot repo, challengers parses. Recoverable from git history.
    # -- nightly rhythm: the proof stint judge, digests, watches
    # the judge appends its own log on every run, so this row reads the writer's clock, not a landing pull
    ("proof stint judge", "schedule", H + "/proof_stint.log", (22, 18, WEEKDAYS), "MONITOR"),
    ("daily digest", "schedule", H + "/digest.log", (22, 20, WEEKDAYS), "MONITOR"),
    ("landing watch", "schedule", H + "/landing_watch.log", (22, 45, {0, 1, 2, 3, 4, 5}), "MONITOR"),
    ("evening persist", "schedule", H + "/evening_persist.log", (22, 45, WEEKDAYS), "MONITOR"),
    ("xsp quote log", "schedule", H + "/xsp_quotes.log", (19, 50, WEEKDAYS), "EVIDENCE"),
    ("trajectory scoreboard", "schedule", H + "/scoreboard.log", (22, 25, {4}), "MONITOR"),
    # -- v1.1 (registry sweep 2026-09-04): failure modes mtime checks cannot see
    ("repo push sync", "push_sync", ".", None, "COURT"),
    # the /halt kill switch publishes through this checkout (BREAKDOWNS 2026-09-26 second entry): an unpushed commit
    # here means a flag that never reached the engine, and a refused pull returns False there before any commit
    # exists (invisible to push_sync), so the pull itself is exercised every morning
    ("kill-switch repo push sync", "push_sync", H + "/harvest-snapshots", None, "TRADE"),
    ("kill-switch repo pull", "git_pull", H + "/harvest-snapshots", None, "TRADE"),
    ("spec parses", "json_ok", "fade_book_spec.json", None, "TRADE"),
    ("expired legs still open", "expired_open", "proactive_sandbox_logs.json", 1, "TRADE"),
    ("ghost open records", "ghost_open", "proactive_sandbox_logs.json", 10, "TRADE"),
    # the proof book keeps its own records, so the discovery rows above cannot see it (BREAKDOWNS 2026-09-22)
    ("expired legs still open (proof)", "expired_open", "proof_logs.json", 1, "TRADE"),
    ("ghost open records (proof)", "ghost_open", "proof_logs.json", 10, "TRADE"),
    ("daily bars archive", "schedule", H + "/daily_bars.log", (22, 15, WEEKDAYS), "EVIDENCE"),
    # -- v1.2 (MOT coverage audit 2026-09-07): frozen-window, disk, and failover classes
    ("vps disk headroom", "disk", "/", 85, "TRADE"),
    ("failover mode stuck", "flag_age", H + "/.engine_watch_failover_mode", 2.0, "TRADE"),
    ("morning analyst", "schedule", H + "/analyst.log", (8, 10, WEEKDAYS), "MONITOR"),
    # -- v1.3 (owner 2026-09-10, "why can't the system stay updated"): HOLES and THINNESS.
    #    Every newest-day check passed for a week while September held 14 corpus rows
    #    (prints marked done with zero rows, bars topped up Fridays only). A newest-day check
    #    cannot see a hole behind the newest day or a day that is 1% of normal.
    #    session_holes: (query of days, lookback sessions, lag)   day_density / jsonl_density:
    #    (query of day,count | -, lookback, ref sessions, min ratio vs ref median, lag)
    # ^ lag 2: day D lands at 22:30 UTC on D+1 (END = today-1), so at the 08:00 run on D+1 the
    #   newest complete session is D-1 - lag 1 would page every single morning
    # ^ lag 3: day D's contracts land 22:30 on D+1, the first prints attempt at 00:15 on D+2
    #   usually returns empty (vendor lag) and is deferred, the second at 00:15 on D+3 lands
]


def last_expected(hour, minute, dows, now):
    d = now.date()
    for _ in range(40):
        dow_ok = d.weekday() in dows
        if dows == WEEKDAYS and not is_session(d):
            dow_ok = False              # market-hours artifacts legitimately sleep on holidays
        cand = datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)
        if dow_ok and cand <= now - timedelta(hours=GRACE_H):
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
        if is_session(cur):
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
                if not os.path.exists(target) and name in FIRST_RUN and now < FIRST_RUN[name] + timedelta(hours=GRACE_H):
                    fresh += 1              # younger than its first expected run: not yet due
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
            elif kind == "session_holes":
                q, lookback, lag = spec
                con = sqlite3.connect(f"file:{target}?mode=ro", uri=True, timeout=30)
                have = {str(r[0])[:10] for r in con.execute(q)}
                con.close()
                recent, _ = session_windows(today, lag, lookback, 0)
                missing = [d.isoformat() for d in recent if d.isoformat() not in have]
                if missing:
                    stale.append(f"[{crit}] {name}: {len(missing)} session(s) with NO rows in the "
                                 f"last {lookback} ({', '.join(missing[:4])}) - a hole behind the newest day")
                else:
                    fresh += 1
            elif kind in ("day_density", "jsonl_density"):
                if kind == "day_density":
                    q, lookback, ref, min_ratio, lag = spec
                    con = sqlite3.connect(f"file:{target}?mode=ro", uri=True, timeout=30)
                    counts = {str(r[0])[:10]: int(r[1] or 0) for r in con.execute(q)}
                    con.close()
                else:
                    lookback, ref, min_ratio, lag = spec
                    import re as _re
                    counts = {}
                    for _d in _re.findall(r'"day":\s*"(20[0-9]{2}-[0-9]{2}-[0-9]{2})"',
                                          open(target, encoding="utf-8").read()):
                        counts[_d] = counts.get(_d, 0) + 1
                recent, reference = session_windows(today, lag, lookback, ref)
                refv = sorted(counts.get(d.isoformat(), 0) for d in reference)
                med = refv[len(refv) // 2] if refv else 0
                thin = [(d.isoformat(), counts.get(d.isoformat(), 0)) for d in recent
                        if counts.get(d.isoformat(), 0) < min_ratio * med]
                if med > 0 and thin:
                    stale.append(f"[{crit}] {name}: {len(thin)} thin session(s) vs trailing median "
                                 f"{med} ({', '.join(f'{d}={c}' for d, c in thin[:4])}) - a newest-day "
                                 "check cannot see this")
                else:
                    fresh += 1
            elif kind == "push_sync":
                import subprocess
                sb = subprocess.run(["git", "-C", target, "status", "-sb"],
                                    capture_output=True, text=True).stdout.splitlines()
                if sb and "ahead" in sb[0]:
                    stale.append(f"[{crit}] {name}: unpushed commits ({sb[0].strip()}) - "
                                 f"push credential or network dead; what {target} publishes is frozen on origin")
                else:
                    fresh += 1
            elif kind == "git_pull":
                import subprocess
                # scripts/telegram_commands.py:_write_flag publishes /halt by pull --rebase --autostash, commit, push;
                # a pull that a leftover rebase or a refused rebase blocks fails there silently (False before any
                # commit), so this row runs the same pull and pages on rc != 0 or on an unfinished rebase
                gd = os.path.join(target, ".git")
                left = [n for n in ("rebase-merge", "rebase-apply", "REBASE_HEAD") if os.path.exists(os.path.join(gd, n))]
                if left:
                    stale.append(f"[{crit}] {name}: unfinished rebase in {target} ({', '.join(left)}) - the /halt "
                                 "channel cannot publish until it is aborted (git rebase --abort)")
                else:
                    r = subprocess.run(["git", "-C", target, "pull", "--rebase", "--autostash", "origin", "main"],
                                       capture_output=True, text=True, timeout=120)
                    if r.returncode != 0:
                        stale.append(f"[{crit}] {name}: pull refused (rc {r.returncode}: "
                                     f"{(r.stderr or r.stdout).strip()[:80]}) - the /halt channel cannot publish")
                    else:
                        fresh += 1
            elif kind == "git_commit":
                import subprocess
                ct = subprocess.run(["git", "-C", target, "log", "-1", "--format=%ct"],
                                    capture_output=True, text=True).stdout.strip()
                exp = last_expected(spec[0], spec[1], spec[2], now)
                if exp and datetime.fromtimestamp(int(ct), tz=timezone.utc) < exp:
                    stale.append(f"[{crit}] {name}: last commit "
                                 f"{datetime.fromtimestamp(int(ct), tz=timezone.utc):%a %d %H:%M}, "
                                 f"expected {exp:%a %d %H:%M} UTC")
                else:
                    fresh += 1
            elif kind == "jsonl_day":
                import re as _re
                mx = ""                 # full-file scan: append order is NOT chronological
                _dp = _re.compile(r'"day":\s*"(20[0-9]{2}-[0-9]{2}-[0-9]{2})"')
                for ln in open(target, encoding="utf-8", errors="ignore"):
                    m = _dp.search(ln)
                    if m and m.group(1) > mx:
                        mx = m.group(1)
                days = [mx] if mx else []
                behind = trading_days_behind(mx, today) if mx else 999
                if behind > spec:
                    stale.append(f"[{crit}] {name}: newest content day "
                                 f"{max(days) if days else '?'} - {behind} trading days behind")
                else:
                    fresh += 1
            elif kind == "newest_file_day":
                import glob as _g
                import re as _re
                ds = [m.group(0) for f in _g.glob(target)
                      for m in [_re.search(r"\d{4}-\d{2}-\d{2}", os.path.basename(f))] if m]
                behind = trading_days_behind(max(ds), today) if ds else 999
                if behind > spec:
                    stale.append(f"[{crit}] {name}: newest file {max(ds) if ds else '?'} - "
                                 f"{behind} trading days behind (max {spec})")
                else:
                    fresh += 1
            elif kind == "disk":
                import shutil
                du = shutil.disk_usage(target)
                pct = du.used * 100.0 / du.total
                if pct > spec:
                    stale.append(f"[{crit}] {name}: {pct:.0f}% used (limit {spec}%) - a full disk "
                                 "kills every cron on the box including this sentinel")
                else:
                    fresh += 1
            elif kind == "flag_age":
                if os.path.exists(target):
                    age_h = (now.timestamp() - os.path.getmtime(target)) / 3600
                    if age_h > spec:
                        stale.append(f"[{crit}] {name}: {target} present for {age_h:.1f}h - "
                                     "failover engaged; verify GHA is really down or the "
                                     "stand-down match is broken")
                    else:
                        fresh += 1
                else:
                    fresh += 1
            elif kind == "json_ok":
                json.load(open(target, encoding="utf-8"))
                fresh += 1
            elif kind == "expired_open":
                import re
                bad = []
                for r in json.load(open(target, encoding="utf-8")):
                    if r.get("status") != "OPEN":
                        continue
                    _occs = [lg.get(k) for lg in (r.get("legs") or {}).values() if isinstance(lg, dict)
                             for k in ("occ_symbol", "front_occ", "back_occ")]
                    _occs.append(r.get("occ"))
                    _om = r.get("occ_more")
                    if isinstance(_om, list):
                        _occs.extend(_om)
                    for o in _occs:
                            m = re.search(r"(\d{6})[CP]\d{8}$", o or "")
                            if m:
                                ed = datetime.strptime(m.group(1), "%y%m%d").date()
                                if ed < today and trading_days_behind(ed.isoformat(), today) > spec:
                                    bad.append(o)
                if bad:
                    stale.append(f"[{crit}] {name}: {len(bad)} expired contract(s) still OPEN "
                                 f"({', '.join(bad[:3])}) - settle/exit machinery broken")
                else:
                    fresh += 1
            elif kind == "ghost_open":
                ghosts = []
                for r in json.load(open(target, encoding="utf-8")):
                    if r.get("status") != "OPEN":
                        continue
                    ets = (r.get("entry_ts_utc") or r.get("timestamp") or "")[:10]
                    if not ets or trading_days_behind(ets, today) <= spec:
                        continue
                    has_occ = any("occ" in kk and isinstance(vv, str) and vv
                                  for lg in (r.get("legs") or {}).values() if isinstance(lg, dict)
                                  for kk, vv in lg.items())
                    if not has_occ:
                        ghosts.append(f"{r.get('probe_strategy') or r.get('set_type')}/{r.get('ticker')}@{ets}")
                if ghosts:
                    stale.append(f"[{crit}] {name}: {len(ghosts)} OPEN record(s) aged >{spec} trading "
                                 f"days with NO leg occs - unsettleable ghosts no exit sweep can "
                                 f"reach ({', '.join(ghosts[:4])})")
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
            sent = False
            for attempt in range(3):    # the watchdog's messenger gets retries and a loud log -
                try:                    # a swallowed morning blip silenced the 2026-09-07 report
                    urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                           urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=20)
                    sent = True
                    break
                except Exception as e:
                    print(f"TELEGRAM SEND ATTEMPT {attempt + 1} FAILED: {repr(e)[:120]}", flush=True)
                    import time
                    time.sleep(20 * (attempt + 1))
            if not sent:
                print("TELEGRAM SEND GAVE UP - the report above never reached the owner", flush=True)
        elif not tok or not chat:
            print("TELEGRAM ENV MISSING - report not sent", flush=True)
    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()

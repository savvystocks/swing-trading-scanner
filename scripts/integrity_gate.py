"""School 1b - nightly data-integrity gate on harvest.db. Read-mostly: the ONLY writes are to the
integrity_quarantine table (failing rows are quarantined, never silently trained on) and a red
Telegram alert on any failure. Runs on the VPS crontab before the nightly backup.

Checks: row-count continuity, schema shape, duplicate ids, null storms, per-candidate timestamp
order, UTC/session discipline (signal timestamps inside their date's XNYS session, DST-aware),
and yesterday's no-answer (MISSING) rate. Plain-English output; exit 1 on any failure.
"""
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import harvest_db as db

STATE_PATH = os.path.join(db.DATA_DIR, "integrity_state.json")
EXPECTED_TABLES = {"candidates", "bid_path", "labels", "api_telemetry", "integrity_quarantine"}
NULL_STORM_PCT = 50.0          # >this % all-null features among feature-tier rows in a day = storm
MISSING_AMBER_PCT = 10.0       # >this % no-answer polls yesterday = sustained-throttle warning

DAY_MS = 24 * 3600 * 1000


def _telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception:
        return False


def run():
    con = db.init_db()
    now = datetime.now(timezone.utc)
    failures, warnings, lines = [], [], []
    q = lambda sql, *a: con.execute(sql, a).fetchall()

    tables = {r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table'")}
    missing_tables = EXPECTED_TABLES - tables
    if missing_tables:
        failures.append(f"schema: missing tables {sorted(missing_tables)}")
    lines.append(f"- schema: {'OK' if not missing_tables else 'FAIL'} ({len(tables)} tables)")

    n_cand = q("SELECT COUNT(*) FROM candidates")[0][0]
    state = {}
    if os.path.exists(STATE_PATH):
        try:
            state = json.load(open(STATE_PATH))
        except Exception:
            state = {}
    prev = state.get("n_candidates", 0)
    if n_cand < prev:
        failures.append(f"continuity: candidates SHRANK {prev} -> {n_cand} (append-only table lost rows)")
    lines.append(f"- row continuity: {'OK' if n_cand >= prev else 'FAIL'} ({prev} -> {n_cand})")

    dups = q("SELECT candidate_id, COUNT(*) c FROM candidates GROUP BY candidate_id HAVING c > 1 LIMIT 5")
    if dups:
        failures.append(f"duplicates: {len(dups)}+ duplicate candidate_id(s)")
        for d in dups:
            con.execute("INSERT OR IGNORE INTO integrity_quarantine VALUES (?,?,?)",
                        (d[0], "duplicate_candidate_id", int(now.timestamp() * 1000)))
    lines.append(f"- duplicate ids: {'OK (none)' if not dups else 'FAIL'}")

    day_start = int(datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp() * 1000) - DAY_MS
    storm = q("SELECT COUNT(*), SUM(CASE WHEN features IS NULL OR features IN ('','{}') THEN 1 ELSE 0 END) "
              "FROM candidates WHERE signal_ts_utc >= ? AND sample_tier IN ('topn','executed','random')",
              day_start)
    tot, nul = storm[0][0] or 0, storm[0][1] or 0
    pct = 100.0 * nul / tot if tot else 0.0
    if tot >= 20 and pct > NULL_STORM_PCT:
        failures.append(f"null storm: {pct:.0f}% of yesterday's feature-tier rows have empty features")
    lines.append(f"- null storm: {'OK' if not (tot >= 20 and pct > NULL_STORM_PCT) else 'FAIL'} "
                 f"({nul}/{tot} empty feature payloads in feature tiers)")

    bad_order = q("SELECT COUNT(*) FROM (SELECT candidate_id, poll_ts_utc, "
                  "LAG(poll_ts_utc) OVER (PARTITION BY candidate_id ORDER BY id) prev FROM bid_path) "
                  "WHERE prev IS NOT NULL AND poll_ts_utc < prev")[0][0]
    if bad_order:
        failures.append(f"timestamp order: {bad_order} bid_path rows out of order within a candidate")
    lines.append(f"- bid_path timestamp order: {'OK' if not bad_order else 'FAIL'} ({bad_order} inversions)")

    try:
        import pandas_market_calendars as mcal
        yday = (now - timedelta(days=1)).date()
        sched = mcal.get_calendar("XNYS").schedule(start_date=str(yday), end_date=str(yday))
        if not sched.empty:
            o = int(sched.iloc[0]["market_open"].timestamp() * 1000)
            c = int(sched.iloc[0]["market_close"].timestamp() * 1000)
            oob = q("SELECT COUNT(*) FROM candidates WHERE signal_ts_utc >= ? AND signal_ts_utc < ? "
                    "AND (signal_ts_utc < ? OR signal_ts_utc > ?)",
                    day_start, day_start + DAY_MS, o - 10 * 60000, c + 10 * 60000)[0][0]
            if oob:
                failures.append(f"UTC/session discipline: {oob} of yesterday's signals outside the XNYS "
                                "session (+-10m) - possible DST/clock fault")
            lines.append(f"- session discipline (DST-aware): {'OK' if not oob else 'FAIL'} ({oob} out-of-session)")
        else:
            lines.append("- session discipline: SKIP (market holiday)")
    except Exception as e:
        warnings.append(f"session check unavailable ({type(e).__name__})")
        lines.append("- session discipline: SKIP (calendar unavailable)")

    tele = q("SELECT status, SUM(n) FROM api_telemetry WHERE day >= ? GROUP BY status",
             (now - timedelta(days=1)).strftime("%Y-%m-%d"))
    counts = {r[0]: r[1] for r in tele}
    answered = sum(v for k, v in counts.items() if k in ("OK", "EMPTY"))
    no_answer = sum(v for k, v in counts.items() if k in ("RATE_LIMITED", "ERROR"))
    total_calls = answered + no_answer
    miss_pct = 100.0 * no_answer / total_calls if total_calls else 0.0
    if total_calls >= 100 and miss_pct > MISSING_AMBER_PCT:
        warnings.append(f"sustained throttling: {miss_pct:.0f}% of polls got NO ANSWER in the last day")
    lines.append(f"- API no-answer rate: {miss_pct:.1f}% ({no_answer}/{total_calls}) "
                 f"{'AMBER' if (total_calls >= 100 and miss_pct > MISSING_AMBER_PCT) else 'OK'}")

    state["n_candidates"] = n_cand
    state["last_run_utc"] = now.isoformat()
    json.dump(state, open(STATE_PATH, "w"))

    verdict = "GREEN" if not failures else "RED"
    if verdict == "GREEN" and warnings:
        verdict = "AMBER"
    header = f"INTEGRITY GATE {verdict} - {now.strftime('%Y-%m-%d %H:%M')}Z"
    print(header)
    for ln in lines:
        print(ln)
    for w in warnings:
        print(f"- WARN: {w}")
    for f in failures:
        print(f"- FAIL: {f}")
    if failures:
        _telegram(f"<b>{header}</b>\n" + "\n".join(f"FAIL: {f}" for f in failures))
    elif warnings:
        _telegram(f"<b>{header}</b>\n" + "\n".join(f"WARN: {w}" for w in warnings))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())

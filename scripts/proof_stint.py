"""PROOF STINT JUDGE (owner order 2026-09-24/25; the design is
~/research_data/learning_2026-09-24/proof_stint_design.md and its readings A1-A11 stand until the owner amends one).

The one live strategy sits on the proof account under a pre-registered rule (NORTH_STAR v1.4/v1.6/v1.7/v1.9)
that nothing computed. This job computes it, OFF the trade path: it reads proof_logs.json,
proof_logs_equity.jsonl and proof_account.seats[0] in fade_book_spec.json, derives the whole stint state on
every run (never accumulates), writes /home/poller/proof_stint.json (durable, outside the tree, so the mirror's
quarter-hour reset cannot take it) and on Fridays reports/performance/proof_stint.json (committed and pushed),
and sends the week-close, streak-met, pass, fail and breach telegrams once each, marked only after a confirmed
send. It calls no broker, writes no spec, unseats nothing, halts nothing.

The rule as read: week = ISO week of a record's expiry; a traded week is RISING when its settled pnl_usd is
positive; a week with no record is PAUSED (BEAR stand-down re-derived from data/daily_bars.db) or
PAUSED-UNEXPLAINED with a page; the streak counts consecutive rising traded weeks, resets on a non-rising one
and holds through a pause; FAIL on a daily-equity mark 30% or more below the stint's high-water mark or on
3 non-rising traded weeks in any 5 consecutive traded weeks; STREAK MET at 8 with the settled curve above
water; PASS only at 20 closed trades with capture >= 60% of the frozen +$21.6 per traded week, and capture
under 60% at 20 fails. A settled week whose daily equity series has a hole is UNCOUNTED (fails closed).
The capture test runs ONCE, on the walk cut at the expiry of the week in which the 20th closed record settles,
and its verdict is latched there: a PASSED or FAILED stint freezes its counters at that date and later weeks
are reported outside them. A stint's records are those entered on or after seats[0].seated (a re-seat dated a
Friday or Saturday never inherits the previous stint's expiry), and its first week is the ISO week after the
seat date unless the seat's own week holds such a record. The Monday :07 runs judge the drawdown bound on the
marks up to yesterday's close (today's row is an intraday mark, shown but not judged); the 22:18 run judges
the day's close mark too.

On its face every output says this tests survival and mechanics, not edge, and prints the 95%
Clopper-Pearson upper bound on the losing-week rate beside the streak.

  ./.venv/bin/python scripts/proof_stint.py                 write durable; Friday also tracked + commit + push
  ./.venv/bin/python scripts/proof_stint.py --dry           compute and print; no write, no telegram
  ./.venv/bin/python scripts/proof_stint.py --as-of 2026-10-05   replay from the same files; print only
Module-level imports are stdlib only: the scoreboard, digest and analyst import this under python3."""
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from math import exp, lgamma

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DURABLE = os.environ.get("PROOF_STINT_STATE") or "/home/poller/proof_stint.json"
TRACKED = os.path.join(REPO, "reports", "performance", "proof_stint.json")
RECORDS = os.path.join(REPO, "proof_logs.json")
EQUITY = os.path.join(REPO, "proof_logs_equity.jsonl")
SPEC = os.path.join(REPO, "fade_book_spec.json")
BARS_DB = os.path.join(REPO, "data", "daily_bars.db")
DD_BOUND = 0.30
STREAK_BAR = 8
CAPTURE_TRADES = 20
CAPTURE_BAR = 0.60
ROLLING = 5
ROLLING_FAIL = 3
ACCOUNT_USD = 5000.0
HONEST = ("Honest expectation at seating (audit 2026-09-20): +$10 to +$22 per traded week, 95% range -$3 to +$40, "
          "P(true edge > 0) about 35-40%.")
_CAL = {"lo": None, "hi": None, "days": [], "ok": None}


def cp_upper(k, n, a=0.05):
    def bcdf(x, p, q):
        N = 3000
        s = sum(((i + 0.5) / N * x) ** (p - 1) * (1 - (i + 0.5) / N * x) ** (q - 1) for i in range(N)) * x / N
        return s / exp(lgamma(p) + lgamma(q) - lgamma(p + q))
    if n <= 0:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if (1 - bcdf(mid, k + 1, n - k) if n - k > 0 else 1.0) > a:
            lo = mid
        else:
            hi = mid
    return hi


def _d(v):
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def sessions_between(lo, hi):
    lo, hi = _d(lo), _d(hi)
    if _CAL["lo"] is None or lo < _CAL["lo"] or hi > _CAL["hi"]:
        a, b = min(lo, _CAL["lo"] or lo) - timedelta(days=30), max(hi, _CAL["hi"] or hi) + timedelta(days=400)
        try:
            import pandas_market_calendars as mcal
            sch = mcal.get_calendar("XNYS").schedule(start_date=a.isoformat(), end_date=b.isoformat())
            _CAL.update(lo=a, hi=b, days=[d.date() for d in sch.index], ok=True)
        except Exception:
            days, d = [], a
            while d <= b:
                if d.weekday() < 5:
                    days.append(d)
                d += timedelta(days=1)
            _CAL.update(lo=a, hi=b, days=days, ok=False)
    return [d for d in _CAL["days"] if lo <= d <= hi]


def calendar_ok():
    return _CAL["ok"]


def next_session_after(day):
    s = sessions_between(_d(day) + timedelta(days=1), _d(day) + timedelta(days=14))
    return s[0] if s else _d(day) + timedelta(days=1)


def settle_clock(day):
    try:
        from zoneinfo import ZoneInfo
        off = datetime(day.year, day.month, day.day, 12, tzinfo=ZoneInfo("America/New_York")).utcoffset()
        return "~13:45 UTC" if off == timedelta(hours=-4) else "~14:45 UTC"
    except Exception:
        return "~13:45 UTC in summer time / ~14:45 in winter"


def regime_at(day, db=BARS_DB):
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
        rows = con.execute("select day, close from bars where symbol='SPY' and day<=? order by day desc limit 50",
                           (_d(day).isoformat(),)).fetchall()
        con.close()
        if len(rows) < 50 or _d(rows[0][0]) < _d(day) - timedelta(days=4):
            return None, None
        closes = [float(r[1]) for r in rows]
        dist = closes[0] / (sum(closes) / len(closes)) - 1
        return ("BEAR" if dist < -0.02 else "BULL" if dist > 0.02 else "MILD"), round(dist, 4)
    except Exception:
        return None, None


def cycle_seen(day):
    d = _d(day).isoformat()
    try:
        out = subprocess.run(["git", "-C", REPO, "log", "--format=%ci", f"--since={d} 14:55", f"--until={d} 15:30",
                              "--", "proof_logs_equity.jsonl", "proof_logs.json"], capture_output=True, text=True, timeout=60).stdout
        return bool(out.strip())
    except Exception:
        return None


def xsp_close_on_disk(today, db=BARS_DB):
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
        row = con.execute("select day, close from index_bars where symbol='^XSP' and day<=? order by day desc limit 1",
                          (_d(today).isoformat(),)).fetchone()
        con.close()
        return (row[0], float(row[1])) if row else None
    except Exception:
        return None


def _is_open_mark(row):
    try:
        return int(str(row.get("ts_utc"))[11:13]) < 16
    except Exception:
        return False


def _mark_clock(row):
    ts = str(row.get("ts_utc") or "")
    return ts[11:16] if len(ts) >= 16 and ts[13] == ":" else "??:??"


def _stint_records(records, seated):
    """The stint's own records: book PROOF, entered on or after the seat date (a record with no entry stamp
    counts when its expiry is after the seat date). A re-seat dated a Friday or Saturday therefore never
    inherits the previous stint's Friday expiry."""
    seated = _d(seated)
    out = []
    for r in records:
        if (r.get("book") or "PROOF").upper() != "PROOF":
            continue
        try:
            exp = _d(r.get("expiry"))
        except Exception:
            continue
        ets = str(r.get("entry_ts_utc") or "")[:10]
        if ets:
            if ets < seated.isoformat():
                continue
        elif exp <= seated:
            continue
        out.append(r)
    return out


def _stint_monday(kept, seated):
    """First week of the stint: the ISO week of the day after the seat date; when the seat date sits inside
    that week (a Monday-to-Saturday seat) the week counts only if it holds one of the stint's own records,
    otherwise the stint starts the following Monday."""
    seated = _d(seated)
    y, w, _ = (seated + timedelta(days=1)).isocalendar()
    monday = date.fromisocalendar(y, w, 1)
    if monday <= seated:
        wk = monday.isocalendar()[:2]
        if not any(_d(r["expiry"]).isocalendar()[:2] == wk for r in kept):
            monday += timedelta(days=7)
    return monday


def _short_unfilled(r):
    return any(lg.get("filled") is False for lg in ((r.get("structure") or {}).get("short") or []))


def _strikes(r):
    st = r.get("structure") or {}
    sk = [lg.get("k") for lg in (st.get("short") or [])]
    lk = [lg.get("k") for lg in (st.get("long") or [])]
    return (sk[0] if sk else None), (lk[0] if lk else None)


def _sessions_after(expiry, today):
    return len(sessions_between(_d(expiry) + timedelta(days=1), today))


def week_rows(records, equity_rows, seated, today, regime_at=None, cycle_seen=None):
    seated, today = _d(seated), _d(today)
    rg_fn = regime_at or globals()["regime_at"]
    cs_fn = cycle_seen or globals()["cycle_seen"]
    kept = _stint_records(records, seated)
    monday = _stint_monday(kept, seated)
    by_week = {}
    for r in kept:
        exp = _d(r["expiry"])
        if exp < monday:
            continue
        by_week.setdefault(exp.isocalendar()[:2], []).append(r)
    eq_days = {str(x.get("day"))[:10] for x in equity_rows}
    open_days = {str(x.get("day"))[:10] for x in equity_rows if _is_open_mark(x)}
    rows = []
    while True:
        friday = monday + timedelta(days=4)
        if friday >= today:
            break
        sess = sessions_between(monday, friday)
        recs = sorted(by_week.get(monday.isocalendar()[:2], []), key=lambda r: str(r.get("entry_ts_utc") or ""))
        row = {"expiry": friday.isoformat(), "kind": None, "verdict": None, "pnl_usd": None, "credit_usd": None,
               "short_k": None, "long_k": None, "xsp_settle": None, "records": len(recs), "closed_early": False,
               "wings_only": False, "equity_basis": None, "regime_rederived": None, "regime_dist": None,
               "cycle_seen": None, "settled_at": None, "holes": [], "mechanics": []}
        if recs:
            row["expiry"] = max(_d(r["expiry"]) for r in recs).isoformat()
            closed = [r for r in recs if r.get("status") == "CLOSED" and isinstance(r.get("settle"), dict)]
            pending = [r for r in recs if r not in closed]
            sk, lk = _strikes(recs[0])
            row.update(short_k=sk, long_k=lk,
                       credit_usd=round(sum(float(r.get("net_credit") or 0) * 100 * int(r.get("contracts") or 1) for r in recs), 2))
            if pending:
                row["kind"] = "TRADED_PENDING"
                n_after = _sessions_after(row["expiry"], today)
                row["sessions_pending"] = n_after
                if n_after > 2:
                    row["mechanics"].append({"date": row["expiry"], "kind": "SETTLE_PENDING",
                                             "text": f"settle pending since {row['expiry']}: {n_after} sessions and no settle booked "
                                                     "(Yahoo hole on the expiry close, or the Monday cycle did not run)"})
            else:
                pnl = round(sum(float(r["settle"].get("pnl_usd") or 0) for r in closed), 2)
                row.update(kind="TRADED", pnl_usd=pnl, verdict="RISING" if pnl > 0 else "NON_RISING",
                           xsp_settle=closed[-1]["settle"].get("xsp"),
                           settled_at=max(str(r["settle"].get("at") or "") for r in closed),
                           closed_early=any(bool(r["settle"].get("closed_early")) for r in closed),
                           wings_only=any(_short_unfilled(r) for r in closed))
                row["holes"] = [d.isoformat() for d in sess if d.isoformat() not in eq_days]
                row["equity_basis"] = "open" if any(d.isoformat() in open_days for d in sess) else "close"
                if row["holes"]:
                    row["kind"] = "UNCOUNTED"
                    row["mechanics"].append({"date": row["expiry"], "kind": "EQUITY_HOLE",
                                             "text": f"week {row['expiry']} settled {pnl:+.0f} but UNCOUNTED: no daily equity mark on "
                                                     f"{', '.join(row['holes'])} (fails closed; restore the mark from the broker's "
                                                     "portfolio history and the next run counts it)"})
                if len(closed) > 1:
                    row["mechanics"].append({"date": row["expiry"], "kind": "DOUBLE_RECORD",
                                             "text": f"week {row['expiry']} holds {len(closed)} records "
                                                     f"({', '.join(str(r.get('trade_set_id')) for r in closed)}): one traded week on the "
                                                     "summed P&L, but the account carried twice the risk"})
                if row["closed_early"]:
                    row["mechanics"].append({"date": row["expiry"], "kind": "CLOSED_EARLY",
                                             "text": f"week {row['expiry']}: legs closed early at the broker; realised P&L {pnl:+.0f} counts"})
                if row["wings_only"]:
                    row["mechanics"].append({"date": row["expiry"], "kind": "WINGS_ONLY",
                                             "text": f"week {row['expiry']}: the short leg never filled (wings only)"})
        else:
            fs = sess[0] if sess else monday
            rg, dist = rg_fn(fs)
            row.update(regime_rederived=rg, regime_dist=dist)
            if rg == "BEAR":
                row["kind"] = "PAUSED"
            else:
                row["kind"] = "PAUSED_UNEXPLAINED"
                seen = cs_fn(fs)
                row["cycle_seen"] = seen
                seen_txt = "yes" if seen else ("no" if seen is False else "unknown")
                rg_txt = (f"{rg} (SPY {dist * 100:+.1f}% vs 50d)" if rg and dist is not None else "unknown")
                row["mechanics"].append({"date": row["expiry"], "kind": "UNEXPLAINED_UNTRADED",
                                         "text": f"no record for the week expiring {row['expiry']} and the re-derived regime was "
                                                 f"{rg_txt}; engine cycle seen in the entry window: {seen_txt}. Counted as PAUSED; "
                                                 "this is a mechanics miss"})
        rows.append(row)
        monday += timedelta(days=7)
    return rows


def _walk(rows, cutoff=None):
    s = {"streak": 0, "cum_pnl_usd": 0.0, "traded": 0, "paused": 0, "paused_unexplained": 0, "uncounted": 0,
         "pending": 0, "non_rising": 0, "losses": 0, "wins": [], "verdicts": [], "streak_met_on": None,
         "under_water_at_8": None, "worst_week_usd": None, "worst_week_expiry": None, "last_scored": None}
    for w in rows:
        if cutoff and w["expiry"] > cutoff:
            break
        k = w["kind"]
        s["last_scored"] = w["expiry"]
        if k == "TRADED":
            pnl = float(w["pnl_usd"])
            s["traded"] += 1
            s["cum_pnl_usd"] = round(s["cum_pnl_usd"] + pnl, 2)
            s["verdicts"].append((w["expiry"], w["verdict"], pnl))
            if w["verdict"] == "RISING":
                s["streak"] += 1
                s["wins"].append(pnl)
            else:
                s["streak"] = 0
                s["non_rising"] += 1
                s["losses"] += int(pnl < 0)
            if s["worst_week_usd"] is None or pnl < s["worst_week_usd"]:
                s["worst_week_usd"], s["worst_week_expiry"] = pnl, w["expiry"]
            if s["streak"] >= STREAK_BAR and s["streak_met_on"] is None:
                if s["cum_pnl_usd"] > 0:
                    s["streak_met_on"] = w["expiry"]
                elif s["under_water_at_8"] is None:
                    s["under_water_at_8"] = w["expiry"]
        elif k == "PAUSED":
            s["paused"] += 1
        elif k == "PAUSED_UNEXPLAINED":
            s["paused"] += 1
            s["paused_unexplained"] += 1
        elif k == "UNCOUNTED":
            s["uncounted"] += 1
        elif k == "TRADED_PENDING":
            s["pending"] += 1
    return s


def _three_in_five(verdicts):
    for i in range(len(verdicts)):
        win = verdicts[max(0, i - ROLLING + 1):i + 1]
        bad = [(e, p) for e, v, p in win if v == "NON_RISING"]
        if len(bad) >= ROLLING_FAIL:
            return verdicts[i][0], bad
    return None, []


def _equity(equity_rows, seated, today, include_today):
    """The drawdown walk. Today's row is rewritten on every open-market cycle, so it is an INTRADAY mark until
    the close: the Monday :07 runs (include_today False) show it on the display line but judge the bound and
    the high-water only on the rows up to yesterday; the 22:18 run (include_today True) judges today's close."""
    seated, today = _d(seated), _d(today)
    rows = sorted([x for x in equity_rows if seated <= _d(x.get("day")) <= today], key=lambda x: str(x.get("day")))
    judged = rows if include_today else [x for x in rows if _d(x.get("day")) < today]
    out = {"last": None, "last_day": None, "hwm": None, "hwm_day": None, "floor": None, "dd_pct": None,
           "max_dd_pct": 0.0, "breach_day": None, "holes": [], "open_mark_days": [], "open_mark_clock": {},
           "judged_through": None, "today_intraday": False, "n": len(rows)}
    hwm = None
    for x in judged:
        e, day = float(x["equity"]), str(x["day"])[:10]
        if hwm is None or e > hwm:
            hwm, out["hwm_day"] = e, day
        dd = (e / hwm - 1) * 100
        out["max_dd_pct"] = round(min(out["max_dd_pct"], dd), 2)
        if out["breach_day"] is None and e <= round((1 - DD_BOUND) * hwm, 2):
            out["breach_day"] = day
        out.update(last=e, last_day=day, hwm=hwm, floor=round((1 - DD_BOUND) * hwm, 2), dd_pct=round(dd, 2),
                   judged_through=day)
    if rows and rows[-1] is not (judged[-1] if judged else None):
        x = rows[-1]
        e, day = float(x["equity"]), str(x["day"])[:10]
        out.update(last=e, last_day=day, today_intraday=True)
        if hwm:
            out["dd_pct"] = round(min(0.0, (e / hwm - 1) * 100), 2)
    for x in rows:
        if _is_open_mark(x):
            day = str(x["day"])[:10]
            out["open_mark_days"].append(day)
            out["open_mark_clock"][day] = _mark_clock(x)
    have = {str(x["day"])[:10] for x in rows}
    y, w, _ = (seated + timedelta(days=1)).isocalendar()
    scan_to = today if include_today else today - timedelta(days=1)
    out["holes"] = [d.isoformat() for d in sessions_between(date.fromisocalendar(y, w, 1), scan_to) if d.isoformat() not in have]
    return out


def _mark_basis(eq, day=None):
    day = day or eq.get("last_day")
    if day in (eq.get("open_mark_days") or []):
        return f"open mark ({(eq.get('open_mark_clock') or {}).get(day, '??:??')} UTC)"
    return "intraday mark (not yet judged)" if eq.get("today_intraday") and day == eq.get("last_day") else "close"


def _open_block(records, today, eq, xsp_close):
    today = _d(today)
    cands = [r for r in records if r.get("status") == "OPEN" and (r.get("book") or "PROOF").upper() == "PROOF"
             and _d(r.get("expiry", "1970-01-01")) >= today]
    if not cands:
        return None
    r = sorted(cands, key=lambda r: str(r.get("expiry")))[-1]
    sk, lk = _strikes(r)
    n = int(r.get("contracts") or 1)
    credit = round(float(r.get("net_credit") or 0) * 100 * n, 2)
    max_loss = round((sk - lk) * 100 * n - credit, 2) if sk is not None and lk is not None else None
    exp = _d(r["expiry"])
    o = {"expiry": exp.isoformat(), "trade_set_id": r.get("trade_set_id"), "short_k": sk, "long_k": lk,
         "credit_usd": credit, "max_loss_usd": max_loss, "sessions_to_expiry": len(sessions_between(today + timedelta(days=1), exp)),
         "xsp_close": None, "xsp_close_day": None, "dist_to_short_pct": None, "full_loss_breaches": None,
         "next_settle": next_session_after(exp).isoformat()}
    if xsp_close:
        o["xsp_close_day"], o["xsp_close"] = xsp_close[0], round(xsp_close[1], 2)
        if sk:
            o["dist_to_short_pct"] = round((xsp_close[1] / sk - 1) * 100, 2)
    if max_loss is not None and eq.get("hwm"):
        o["full_loss_breaches"] = bool(DD_BOUND * eq["hwm"] < max_loss)
    return o


def _tail(walk, C, open_block):
    n, k = walk["traded"], walk["losses"]
    mean_win = (sum(walk["wins"]) / len(walk["wins"])) if walk["wins"] else float(C["archive_mean_win_usd"])
    loss = abs(float(C["archive_mean_loss_usd"]))
    max_open = (open_block or {}).get("max_loss_usd") or float(C["archive_max_loss_usd"])
    stint = {"n": n, "k": k, "ub": None, "ev_realised": None, "ev_max": None, "mean_win": round(mean_win, 2), "max_loss_ref": max_open}
    if n > 0:
        ub = cp_upper(k, n)
        stint.update(ub=round(ub, 4), ev_realised=round((1 - ub) * mean_win - ub * loss, 2),
                     ev_max=round((1 - ub) * mean_win - ub * max_open, 2))
    N, K = int(C["archive_weeks"]) + n, int(C["archive_losses"]) + k
    ubp = cp_upper(K, N)
    aw = float(C["archive_mean_win_usd"])
    pooled = {"n": N, "k": K, "ub": round(ubp, 4), "ev_realised": round((1 - ubp) * aw - ubp * loss, 2),
              "ev_max": round((1 - ubp) * aw - ubp * float(C["archive_max_loss_usd"]), 2)}
    return {"stint": stint, "pooled": pooled}


def _fridays_from(day):
    d = _d(day)
    d = d + timedelta(days=(4 - d.weekday()) % 7)
    while True:
        yield d
        d += timedelta(days=7)


def _next_line(state, rows, open_block, today):
    today = _d(today)
    parts = []
    pend = [w for w in rows if w["kind"] == "TRADED_PENDING"]
    if open_block:
        ns = _d(open_block["next_settle"])
        parts.append(f"settle of the {open_block['expiry']} spread lands {ns:%a} {ns.isoformat()}")
    elif pend:
        parts.append(f"settle of the {pend[-1]['expiry']} spread is pending (expected {next_session_after(pend[-1]['expiry']).isoformat()})")
    else:
        parts.append("no open spread; the next entry is the first session of the coming week")
    if state["status"] in ("RUNNING",):
        need = max(STREAK_BAR - state["streak"], 0)
        if pend:
            start = _d(pend[0]["expiry"])
        elif rows:
            start = _d(rows[-1]["expiry"]) + timedelta(days=7)
        else:
            start = today
        if open_block and _d(open_block["expiry"]) < start:
            start = _d(open_block["expiry"])
        if need:
            g = _fridays_from(start)
            target = None
            for _ in range(need):
                target = next(g)
            parts.append(f"streak can reach {STREAK_BAR} no earlier than the {target.isoformat()} expiry")
    elif state["status"] == "STREAK_MET_EXTENDING":
        parts.append(f"capture test at {CAPTURE_TRADES} closed trades ({state['capture']['closed']} so far)")
    return "; ".join(parts)


def judge(weeks, equity_rows, constants, today, seated, records=(), xsp_close=None, include_today=False):
    today, seated = _d(today), _d(seated)
    C = constants
    rows = [dict(w) for w in weeks]
    eq = _equity(equity_rows, seated, today, include_today)
    full = _walk(rows)
    fail_reason, fail_date, fail_detail = None, None, ""
    tif_on, tif_bad = _three_in_five(full["verdicts"])
    if eq["breach_day"]:
        fail_reason, fail_date = "DD_BREACH", eq["breach_day"]
    if tif_on and (fail_date is None or tif_on < fail_date):
        fail_reason, fail_date = "THREE_IN_FIVE", tif_on
        fail_detail = ", ".join(f"{e} {p:+.0f}" for e, p in tif_bad)
    kept = _stint_records(records, seated)
    monday = _stint_monday(kept, seated)
    closed_all = sorted([r for r in kept if r.get("status") == "CLOSED" and isinstance(r.get("settle"), dict)
                         and _d(r["expiry"]) >= monday and str(r["settle"].get("at") or "")[:10] <= today.isoformat()],
                        key=lambda r: (str(r["settle"].get("at") or ""), str(r["expiry"])))
    denom = float(C["denominator_usd_per_traded_week"])
    # THE CAPTURE TEST RUNS ONCE (latched): on the walk cut at the expiry of the week in which the 20th closed record
    # settles. Before that week's row exists (a closed-early record can settle before its Friday) the test is not due.
    cap_expiry, cap_walk = None, None
    if len(closed_all) >= CAPTURE_TRADES:
        wk20 = _d(closed_all[CAPTURE_TRADES - 1]["expiry"]).isocalendar()[:2]
        for w in rows:
            if _d(w["expiry"]).isocalendar()[:2] == wk20 and w["kind"] != "TRADED_PENDING":
                cap_expiry = w["expiry"]
                break
    prior_fail = bool(cap_expiry and fail_date and fail_date <= cap_expiry)
    pass_date, cap_ratio, cap_mean, cap_closed = None, None, None, None
    if cap_expiry and not prior_fail:
        cap_walk = _walk(rows, cutoff=cap_expiry)
        cap_closed = sum(1 for r in closed_all if _d(r["expiry"]) <= _d(cap_expiry))
        cap_mean = round(cap_walk["cum_pnl_usd"] / cap_walk["traded"], 2) if cap_walk["traded"] else None
        cap_ratio = round(cap_mean / denom, 3) if cap_mean is not None else None
        if cap_ratio is None or cap_ratio < CAPTURE_BAR or cap_walk["cum_pnl_usd"] <= 0:
            fail_reason, fail_date = "CAPTURE_BELOW_60", cap_expiry     # earlier than any later breach, so it wins
            fail_detail = f"capture {cap_ratio * 100 if cap_ratio is not None else 0:.0f}% at {cap_closed} closed trades (tested at the {cap_expiry} expiry)"
        elif cap_walk["streak_met_on"]:
            pass_date = cap_expiry
        elif full["streak_met_on"] and not (fail_date and fail_date <= full["streak_met_on"]):
            pass_date = full["streak_met_on"]          # capture passed at 20; the streak was met later
    if pass_date and fail_date and fail_date > pass_date:
        fail_reason, fail_date, fail_detail = None, None, ""       # the stint passed first; a later breach is outside the counters
    latch = fail_date or pass_date
    walk = _walk(rows, cutoff=latch) if latch else full
    closed = [r for r in closed_all if not latch or _d(r["expiry"]) <= _d(latch)]
    n_closed = len(closed)
    mean = round(walk["cum_pnl_usd"] / walk["traded"], 2) if walk["traded"] else None
    evaluable = bool(cap_expiry) and not prior_fail
    ratio = cap_ratio if evaluable else (round(mean / denom, 3) if mean is not None else None)
    if fail_reason:
        status = "FAILED"
    elif pass_date:
        status = "PASSED"
    elif walk["streak_met_on"]:
        status = "STREAK_MET_EXTENDING"
    else:
        status = "RUNNING"
    open_block = _open_block(kept, today, eq, xsp_close)
    tail = _tail(walk, C, open_block)
    mech = [m for w in rows for m in w.get("mechanics", [])]
    for w in rows:
        w.pop("mechanics", None)
    state = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "judged_for": today.isoformat(),
             "seated": seated.isoformat(), "status": status, "fail_reason": fail_reason, "fail_date": fail_date,
             "fail_detail": fail_detail, "pass_date": pass_date, "latched_on": latch,
             "streak": walk["streak"], "streak_met_on": walk["streak_met_on"],
             "under_water_at_8": walk["under_water_at_8"], "traded": walk["traded"], "paused": walk["paused"],
             "paused_unexplained": walk["paused_unexplained"], "uncounted": walk["uncounted"], "pending": walk["pending"],
             "non_rising": walk["non_rising"], "rolling5_non_rising": sum(1 for _, v, _ in walk["verdicts"][-ROLLING:] if v == "NON_RISING"),
             "cum_pnl_usd": walk["cum_pnl_usd"], "mean_per_traded_week_usd": mean, "worst_week_usd": walk["worst_week_usd"],
             "worst_week_expiry": walk["worst_week_expiry"],
             "capture": {"closed": n_closed, "denominator": denom, "ratio": ratio, "evaluable": evaluable,
                         "tested_on": cap_expiry if evaluable else None, "closed_at_test": cap_closed if evaluable else None,
                         "mean_at_test": cap_mean if evaluable else None,
                         "passed": (None if not evaluable else fail_reason != "CAPTURE_BELOW_60")},
             "equity": eq, "tail": tail, "open": open_block, "weeks": rows, "mechanics": mech, "announced": [],
             "constants": dict(C), "calendar_ok": calendar_ok(), "next_line": None}
    state["next_line"] = _next_line(state, rows, open_block, today)
    state["honesty"] = honesty_lines(state)
    return state


def _usd(v, plus=True):
    if v is None:
        return "n/a"
    return f"{'+' if plus and v > 0 else '-' if v < 0 else ''}${abs(v):,.0f}"


def _pct(p):
    return "n/a" if p is None else f"{p * 100:.1f}%"


def honesty_lines(st):
    C = st["constants"]
    win = round(1 - int(C["archive_losses"]) / int(C["archive_weeks"]), 2)
    p8 = round(win ** STREAK_BAR * 100)
    t = st["tail"]
    s, p = t["stint"], t["pooled"]
    if s["n"] > 0:
        stint_txt = (f"this stint {s['k']} losses in {s['n']} traded week{'s' if s['n'] != 1 else ''} -> up to {_pct(s['ub'])}; "
                     f"expectancy at that rate {_usd(s['ev_realised'])}/wk with losses at the archive's realised size "
                     f"({_usd(C['archive_mean_loss_usd'])}) and {_usd(s['ev_max'])}/wk at max loss (${s['max_loss_ref']:,.0f})")
    else:
        stint_txt = "this stint has no traded week yet"
    cap = st["capture"]
    if cap["evaluable"]:
        cap_txt = (f"Capture (tested once, at the {cap.get('tested_on')} expiry with {cap.get('closed_at_test')} closed trades): mean "
                   f"{_usd(cap.get('mean_at_test'))} per traded week = {(cap['ratio'] or 0) * 100:.0f}% of the frozen "
                   f"+${cap['denominator']:.1f} (bar {CAPTURE_BAR * 100:.0f}%) - {'PASSED' if cap.get('passed') else 'FAILED'}, latched.")
    else:
        m = st["mean_per_traded_week_usd"]
        mean_txt = ("n/a" if m is None else f"{'+' if m > 0 else '-' if m < 0 else ''}${abs(m):,.1f}")
        cap_txt = (f"Capture: {cap['closed']} closed trade{'s' if cap['closed'] != 1 else ''} of the {CAPTURE_TRADES} needed before the "
                   f"{CAPTURE_BAR * 100:.0f}% test; mean {mean_txt} per traded week against the frozen +${cap['denominator']:.1f}.")
    return [
        f"What {STREAK_BAR} weeks test: survival and mechanics (fills, settlement, gate timing, drawdown behaviour), NOT edge. "
        f"Weekly P&L sd is about ${C['weekly_sd_usd']:.0f} and the archive win rate about {win * 100:.0f}%, so {STREAK_BAR} loss-free "
        f"weeks happen {p8}% of the time ({win:.2f}^{STREAK_BAR}) whether the true edge is +$20 a week or zero. A pass here means "
        f"\"no loss week yet\"; a fail means \"one ordinary loss week arrived\" ({(1 - win) * 100:.0f}% a week).",
        f"Tail bound, 95% Clopper-Pearson upper bound on the losing-week rate: {stint_txt}. Pooled with the archive "
        f"({C['archive_weeks']} weeks, {C['archive_losses']} losses -> {p['n']}/{p['k']}): {_pct(p['ub'])}; {_usd(p['ev_realised'])}/wk "
        f"realised, {_usd(p['ev_max'])}/wk at max loss. Each loss-free week lowers the pooled bound by about 0.1 point; this stint "
        f"cannot close it.",
        cap_txt,
        HONEST,
    ]


def week_line(w):
    e = w["expiry"]
    k = w["kind"]
    if k in ("TRADED", "UNCOUNTED"):
        strikes = f"short {w['short_k']} / long {w['long_k']}" if w.get("short_k") else "strikes unknown"
        xsp = f"XSP settled {w['xsp_settle']:.2f} vs {strikes}" if w.get("xsp_settle") is not None else strikes
        txt = f"Week {e}: {_usd(w['pnl_usd'])} ({xsp}; credit {_usd(w['credit_usd'], plus=False)} from booked fills)."
        if k == "UNCOUNTED":
            txt += f" UNCOUNTED - daily equity missing on {', '.join(w['holes'])} (fails closed; restore the mark to count it)."
        if w.get("closed_early"):
            txt += f" LEGS CLOSED EARLY AT THE BROKER - P&L is realised, not expiry (the engine paged this on {str(w.get('settled_at'))[:10]})."
        if w.get("records", 1) > 1:
            txt += f" {w['records']} records in one week (double entry)."
        if w.get("wings_only"):
            txt += " Short leg never filled (wings only)."
        return txt
    if k == "TRADED_PENDING":
        return f"Week {e}: settle pending since {e} ({w.get('sessions_pending', 0)} sessions)."
    rg = w.get("regime_rederived")
    dist = w.get("regime_dist")
    dist_txt = f"re-derived: SPY {dist * 100:+.1f}% vs 50d" if dist is not None else "re-derived, distance unknown"
    rg_txt = f"{rg} ({dist_txt})" if rg else "unknown regime"
    if k == "PAUSED":
        return f"Week {e}: paused - BEAR at the first session ({dist_txt})."
    seen = w.get("cycle_seen")
    return (f"Week {e}: NO RECORD and the re-derived regime was {rg_txt}; engine cycle seen in the entry window: "
            f"{'yes' if seen else 'no' if seen is False else 'unknown'}. Counted as PAUSED; this is a mechanics miss.")


def render(st):
    as_of = st["as_of"].replace("T", " ")[:16]
    L = [f"PROOF STINT - XSP 2%/4% put credit spread, promotion 1 (${ACCOUNT_USD:,.0f}), seated {st['seated']}. State as of {as_of} UTC."]
    line2 = (f"Streak {st['streak']} of {STREAK_BAR} rising traded weeks. Traded {st['traded']}, paused {st['paused']}, "
             f"non-rising {st['non_rising']} ({ROLLING_FAIL} non-rising in any {ROLLING} traded weeks fails). Status {st['status']}.")
    if st["status"] == "FAILED":
        line2 += f" Failed on {st['fail_date']}: {st['fail_reason']}{' - ' + st['fail_detail'] if st['fail_detail'] else ''}; counters frozen at that date."
    elif st["status"] == "PASSED":
        line2 += f" Passed on {st.get('pass_date')}; counters frozen at that date."
    if st["paused_unexplained"]:
        line2 += f" {st['paused_unexplained']} unexplained untraded week{'s' if st['paused_unexplained'] != 1 else ''}."
    if st["uncounted"]:
        line2 += f" {st['uncounted']} settled week{'s' if st['uncounted'] != 1 else ''} uncounted (equity hole)."
    if st["under_water_at_8"] and not st["streak_met_on"]:
        line2 += f" Streak reached {STREAK_BAR} on {st['under_water_at_8']} but curve under water: extends."
    L.append(line2)
    for w in st["weeks"][-8:]:
        L.append(week_line(w))
    if len(st["weeks"]) > 8:
        L.append(f"({len(st['weeks']) - 8} earlier weeks not shown)")
    eq = st["equity"]
    if eq["last"] is not None:
        om = eq["open_mark_days"]
        clk = eq.get("open_mark_clock") or {}
        if eq.get("hwm") is None:
            hw_txt = "no judged mark yet (today's row is intraday)"
        else:
            hw_txt = (f"high-water {eq['hwm']:,.2f}; drawdown {abs(eq['dd_pct'] or 0):.1f}% (bound -{DD_BOUND * 100:.0f}%, "
                      f"floor {eq['floor']:,.2f})")
        L.append(f"Curve {_usd(st['cum_pnl_usd'])} settled since seating. Equity {eq['last']:,.2f} at the {eq['last_day']} "
                 f"{_mark_basis(eq)}; {hw_txt}."
                 + (f" Bound judged through {eq['judged_through']}." if eq.get("today_intraday") and eq.get("judged_through") else "")
                 + (f" Worst so far {abs(eq['max_dd_pct']):.1f}%." if eq["max_dd_pct"] < -0.005 else "")
                 + (f" Breached on {eq['breach_day']}." if eq["breach_day"] else "")
                 + ((f" Marks on {om[0]}..{om[-1]} are open marks ({clk.get(om[0], '??:??')}..{clk.get(om[-1], '??:??')} UTC)."
                     if len(om) > 1 else f" The {om[0]} mark is an open mark ({clk.get(om[0], '??:??')} UTC).") if om else "")
                 + (f" Equity holes: {', '.join(eq['holes'])}." if eq["holes"] else ""))
    else:
        L.append(f"Curve {_usd(st['cum_pnl_usd'])} settled since seating. No daily equity row since seating.")
    o = st["open"]
    if o:
        exp = _d(o["expiry"])
        txt = f"Open: {o['short_k']}/{o['long_k']} expires {exp:%a} {o['expiry']} ({o['sessions_to_expiry']} sessions); "
        if o["xsp_close"] is not None and o["dist_to_short_pct"] is not None:
            txt += f"XSP {o['xsp_close']:.2f} on {o['xsp_close_day']} is {o['dist_to_short_pct']:.2f}% above the short strike; "
        else:
            txt += "no ^XSP close on disk; "
        if o["max_loss_usd"] is None:
            txt += "max loss unknown (a strike is missing from the record)."
        else:
            txt += f"max loss ${o['max_loss_usd']:,.0f} = {o['max_loss_usd'] / ACCOUNT_USD * 100:.1f}% of the account"
            if o["full_loss_breaches"]:
                txt += (f" - a full loss this week breaches the -{DD_BOUND * 100:.0f}% bound "
                        f"(high-water below ${o['max_loss_usd'] / DD_BOUND:,.0f}).")
            elif o["full_loss_breaches"] is False:
                txt += "; a full loss this week stays inside the bound."
            else:
                txt += "."
        L.append(txt)
        ns = _d(o["next_settle"])
        rest = st["next_line"].split("; ", 1)
        tail = (rest[1][0].upper() + rest[1][1:] + ".") if len(rest) > 1 else ""
        L.append(f"Next settle lands {ns:%a} {o['next_settle']} {settle_clock(ns)}. {tail}".rstrip())
    else:
        L.append("Open: none.")
        L.append(st["next_line"][0].upper() + st["next_line"][1:] + ".")
    if st["mechanics"]:
        L.append("Mechanics: " + " | ".join(m["text"] for m in st["mechanics"][-4:]))
    L.extend(st["honesty"])
    if st.get("calendar_ok") is False:
        L.append("(calendar unreadable: sessions counted as weekdays)")
    return "\n".join(L)


def healthy_line(st):
    ns = (st["open"] or {}).get("next_settle") or "-"
    dd = st["equity"]["dd_pct"]
    return (f"PROOF STINT {st['judged_for']} status {st['status']} streak {st['streak']}/{STREAK_BAR} traded {st['traded']} "
            f"paused {st['paused']} non-rising {st['non_rising']} curve {_usd(st['cum_pnl_usd'])} "
            f"dd {abs(dd) if dd is not None else 0:.1f}% next-settle {ns}")


def _survival_pct(st):
    C = st["constants"]
    return round(round(1 - C["archive_losses"] / C["archive_weeks"], 2) ** STREAK_BAR * 100)


def _streak_sentence(st, w):
    streak, before = 0, 0
    for x in st["weeks"]:
        if x["kind"] != "TRADED":
            continue
        before = streak
        streak = streak + 1 if x["verdict"] == "RISING" else 0
        if x["expiry"] == w["expiry"]:
            break
    if w.get("verdict") == "RISING":
        return f"Streak {streak}/{STREAK_BAR} rising traded weeks"
    if w["kind"] == "UNCOUNTED":
        return f"Streak held at {st['streak']}/{STREAK_BAR} (week uncounted)"
    return f"Streak reset to 0 (was {before})"


def week_close_text(st, w):
    n = sum(1 for x in st["weeks"] if x["kind"] in ("TRADED", "UNCOUNTED") and x["expiry"] <= w["expiry"])
    strikes = f"short {w['short_k']} / long {w['long_k']}" if w.get("short_k") else "strikes unknown"
    xsp = f"XSP settled {w['xsp_settle']:.2f} vs {strikes}" if w.get("xsp_settle") is not None else strikes
    L = [f"PROOF WEEK {n} CLOSED (expiry {w['expiry']}): {_usd(w['pnl_usd'])}. {xsp}; credit {_usd(w['credit_usd'], plus=False)} from booked fills."]
    if w["kind"] == "UNCOUNTED":
        L.append(f"UNCOUNTED: no daily equity mark on {', '.join(w['holes'])} - the week is neither rising nor non-rising until the mark is restored.")
    if w.get("closed_early"):
        L.append(f"LEGS CLOSED EARLY AT THE BROKER - P&L is realised, not expiry (the engine paged this on {str(w.get('settled_at'))[:10]}).")
    if w.get("records", 1) > 1:
        L.append(f"{w['records']} records in one expiry week - one traded week on the summed P&L; the account carried double risk.")
    eq = st["equity"]
    curve = f"Curve {_usd(st['cum_pnl_usd'])}" + ("" if st["cum_pnl_usd"] > 0 else ", under water")
    latch = st.get("latched_on")
    if latch and w["expiry"] > latch:
        # after a verdict the counters are frozen; a later week is reported, never counted (2026-09-26 fix E)
        why = f" ({st['fail_reason']})" if st["status"] == "FAILED" and st.get("fail_reason") else ""
        line = (f"Stint {st['status']} on {latch}{why}; this week is outside the counters "
                f"(frozen there: traded {st['traded']}, streak {st['streak']}/{STREAK_BAR}, {curve.lower()})")
    else:
        line = (f"{_streak_sentence(st, w)} (traded {st['traded']}, paused {st['paused']}, non-rising {st['non_rising']} of the "
                f"{ROLLING_FAIL}-in-{ROLLING} that fails). {curve}")
    if eq["last"] is not None and eq.get("hwm") is not None:
        line += f"; equity {eq['last']:,.2f}, {abs(eq['dd_pct'] or 0):.1f}% below high-water (bound -{DD_BOUND * 100:.0f}%)."
    else:
        line += "."
    L.append(line)
    o = st["open"]
    if o:
        ns = _d(o["next_settle"])
        L.append(f"Next: {o['short_k']}/{o['long_k']} expires {_d(o['expiry']):%a} {o['expiry']}; settle lands {ns:%a} {o['next_settle']} {settle_clock(ns)}.")
    L.append(f"This tests survival and mechanics, not edge: weekly sd ~${st['constants']['weekly_sd_usd']:.0f}; {STREAK_BAR} loss-free "
             f"weeks happen {_survival_pct(st)}% of the time whether the edge is +$20/wk or zero.")
    t = st["tail"]
    s, p = t["stint"], t["pooled"]
    if s["n"]:
        L.append(f"Tail bound (95% Clopper-Pearson): {s['k']} losses in {s['n']} -> up to {_pct(s['ub'])} -> {_usd(s['ev_max'])}/wk at max loss; "
                 f"pooled with the archive {_pct(p['ub'])} -> {_usd(p['ev_max'])}/wk at max loss, {_usd(p['ev_realised'])}/wk at the realised loss size.")
    return "\n".join(L)


def _event_texts(st):
    out = []
    for w in st["weeks"]:
        if w["kind"] == "TRADED":
            out.append((w["expiry"], week_close_text(st, w)))
        elif w["kind"] == "UNCOUNTED":
            # keyed apart from the counted verdict (2026-09-26 fix D): when the hole is restored the week becomes
            # TRADED under the plain expiry key and its counted week-close pages once
            out.append((f"UNCOUNTED:{w['expiry']}", week_close_text(st, w)))
    for m in st["mechanics"]:
        if m["kind"] in ("UNEXPLAINED_UNTRADED", "SETTLE_PENDING", "EQUITY_HOLE"):
            out.append((f"MECH:{m['date']}:{m['kind']}", f"[MONITOR] PROOF STINT: {m['text']}."))
        elif m["kind"] in ("DOUBLE_RECORD",):
            out.append((f"MECH:{m['date']}:{m['kind']}", f"[TRADE] PROOF STINT: {m['text']}."))
    if st["streak_met_on"]:
        eq = st["equity"]
        out.append((f"STREAK_MET:{st['streak_met_on']}",
                    f"PROOF STINT: {STREAK_BAR} rising traded weeks reached (expiry {st['streak_met_on']}); curve {_usd(st['cum_pnl_usd'])} above water; "
                    f"worst drawdown {abs(eq['max_dd_pct']):.1f}%. NOT a pass yet: capture is evaluable only at {CAPTURE_TRADES} closed trades "
                    f"({st['capture']['closed']} so far) - the stint extends to {CAPTURE_TRADES} under the same fail rules. Survival, not edge: "
                    f"{_survival_pct(st)}% of edge-less stints get here."))
    if st["status"] == "PASSED":
        eq, t, cap = st["equity"], st["tail"]["stint"], st["capture"]
        out.append((f"PASSED:{st.get('pass_date')}",
                    f"PROOF STINT PASSED on the {st.get('pass_date')} expiry: {STREAK_BAR} rising traded weeks met on {st['streak_met_on']}, "
                    f"curve {_usd(st['cum_pnl_usd'])}, worst drawdown {abs(eq['max_dd_pct']):.1f}%, capture {(cap['ratio'] or 0) * 100:.0f}% of the "
                    f"frozen +${cap['denominator']:.1f}/wk (bar {CAPTURE_BAR * 100:.0f}%; tested once at the {cap.get('tested_on')} expiry with "
                    f"{cap.get('closed_at_test')} closed trades). Counters are frozen there. NORTH_STAR v1.4: the first real GBP 1,000-5,000 is now "
                    f"your decision, subject to the pre-registered live-gate items (ROADMAP item 14). Nothing here moves money. "
                    f"Tail bound at {t['n']} traded weeks with {t['k']} losses: up to {_pct(t['ub'])} -> {_usd(t['ev_max'])}/wk at max loss."))
    if st["status"] == "FAILED":
        eq = st["equity"]
        court = ("NORTH_STAR v1.6/v1.7: the strategy returns to court for a fresh case. Nothing has been unseated - the book keeps trading "
                 "until you say the word (proof_account.enabled or /halt).")
        if st["fail_reason"] == "DD_BREACH":
            txt = (f"PROOF STINT FAILED - drawdown bound breached: equity at the {eq['breach_day']} mark fell {DD_BOUND * 100:.0f}% or more below "
                   f"high-water (bound -{DD_BOUND * 100:.0f}%; today equity {eq['last']:,.2f}, high-water {eq['hwm']:,.2f}, floor {eq['floor']:,.2f}). {court}")
        elif st["fail_reason"] == "THREE_IN_FIVE":
            txt = f"PROOF STINT FAILED - {ROLLING_FAIL} non-rising traded weeks in the last {ROLLING} ({st['fail_detail']}). {court}"
        else:
            txt = (f"PROOF STINT FAILED - {st['fail_detail']} (bar {CAPTURE_BAR * 100:.0f}% of +${st['capture']['denominator']:.1f}/wk). {court}")
        out.append((f"FAILED:{st['fail_reason']}:{st['fail_date']}", txt))
    return out


def announce(st, sender, log=print):
    done = list(st.get("announced") or [])
    results = []
    for key, text in _event_texts(st):
        if key in done:
            continue
        ok = False
        try:
            ok = bool(sender(text))
        except Exception:
            ok = False
        if ok:
            done.append(key)
            log(f"proof stint: {key} - telegram sent")
        else:
            log(f"proof stint: {key} - TELEGRAM SEND FAILED, will retry")
        results.append((key, ok))
    st["announced"] = done
    return results


def send_telegram(text):
    import time
    import urllib.parse
    import urllib.request
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    for i in range(3):
        try:
            with urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                        urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}), timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(10 * (i + 1))
    return False


def read_state():
    for p in (DURABLE, TRACKED):
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    raise FileNotFoundError(f"no proof stint state at {DURABLE} or {TRACKED}")


def _stale(st, today):
    try:
        return _d(st["as_of"]) < _d(today) - timedelta(days=1)
    except Exception:
        return False


def scoreboard_block(st, today=None):
    today = _d(today) if today else date.today()
    eq, cap, p = st["equity"], st["capture"], st["tail"]["pooled"]
    C = st["constants"]
    tag = f" (state from {st['as_of'][:16].replace('T', ' ')} UTC)" if _stale(st, today) else ""
    L = [f"PROOF STINT{tag}: streak {st['streak']}/{STREAK_BAR} rising traded weeks, status {st['status']}; traded {st['traded']}, "
         f"paused {st['paused']}, non-rising {st['non_rising']}" + (f", {st['paused_unexplained']} unexplained" if st["paused_unexplained"] else "") + "."]
    mean = f"{st['mean_per_traded_week_usd']:+.1f}" if st["mean_per_traded_week_usd"] is not None else "n/a"
    worst = f"; worst week {_usd(st['worst_week_usd'])} ({st['worst_week_expiry']})" if st["worst_week_usd"] is not None else ""
    L.append(f"Settled {_usd(st['cum_pnl_usd'])} since seating = ${mean} per traded week (frozen bar +${cap['denominator']:.1f}; capture judged at "
             f"{CAPTURE_TRADES} closed trades, {cap['closed']} so far){worst}.")
    if eq["last"] is not None and eq.get("hwm") is not None:
        L.append(f"Equity {eq['last']:,.2f}; drawdown {abs(eq['dd_pct'] or 0):.1f}% from high-water {eq['hwm']:,.2f} (bound -{DD_BOUND * 100:.0f}%, "
                 f"floor {eq['floor']:,.2f}). Next: {st['next_line']}.")
    else:
        L.append(f"No judged daily equity row yet. Next: {st['next_line']}.")
    win = round(1 - C["archive_losses"] / C["archive_weeks"], 2)
    L.append(f"Survival, not edge: {STREAK_BAR} loss-free weeks happen {round(win ** STREAK_BAR * 100)}% of the time with or without an edge "
             f"(weekly sd ~${C['weekly_sd_usd']:.0f}). Tail bound pooled with the archive {_pct(p['ub'])} -> {_usd(p['ev_max'])}/wk at max loss.")
    if st["status"] == "FAILED":
        L.append(f"FAILED on {st['fail_date']} ({st['fail_reason']}); counters frozen there.")
    elif st["status"] == "PASSED":
        L.append(f"PASSED on {st.get('pass_date')}; counters frozen there.")
    return "\n".join(L)


def digest_line(st, today):
    today = _d(today)
    eq, o = st["equity"], st["open"]
    tag = f" (state from {st['as_of'][:10]})" if _stale(st, today) else ""
    settled = [w for w in st["weeks"] if w["kind"] in ("TRADED", "UNCOUNTED") and str(w.get("settled_at") or "")[:10] == today.isoformat()]
    head = f"Proof stint{tag}:"
    if settled:
        w = settled[-1]
        xsp = f"XSP {w['xsp_settle']:.2f} vs short {w['short_k']}" if w.get("xsp_settle") is not None else "settled"
        head += f" week {w['expiry']} settled {_usd(w['pnl_usd'])} ({xsp}) -"
    parts = [f"{head} {st['streak']}/{STREAK_BAR} rising traded weeks ({st['status']}); {_usd(st['cum_pnl_usd'])} settled"]
    if eq["last"] is not None and eq.get("hwm") is not None:
        parts.append(f"equity {eq['last']:,.0f} at the {eq['last_day']} {_mark_basis(eq)}, "
                     f"{abs(eq['dd_pct'] or 0):.1f}% below high-water (bound -{DD_BOUND * 100:.0f}%)")
    if o:
        dist = f", XSP {o['dist_to_short_pct']:.2f}% above the short strike" if o["dist_to_short_pct"] is not None else ""
        parts.append(f"{o['short_k']}/{o['long_k']} expires {_d(o['expiry']):%a} {o['expiry']}{dist}")
    else:
        paused = [w for w in st["weeks"] if w["kind"] in ("PAUSED", "PAUSED_UNEXPLAINED")]
        if paused and paused[-1]["expiry"] >= (today - timedelta(days=7)).isoformat():
            parts.append(f"paused - {'BEAR at the first session' if paused[-1]['kind'] == 'PAUSED' else 'no record and no BEAR (mechanics miss)'}, "
                         f"streak held at {st['streak']}")
        else:
            parts.append("no open spread")
    if st["status"] == "FAILED":
        parts.append(f"FAILED on {st['fail_date']} ({st['fail_reason']})")
    elif st["status"] == "PASSED":
        parts.append(f"PASSED on {st.get('pass_date')}")
    return "; ".join(parts) + "."


def brief_block(st, today):
    today = _d(today)
    eq, o, p = st["equity"], st["open"], st["tail"]["pooled"]
    tag = f" (state from {st['as_of'][:16].replace('T', ' ')} UTC)" if _stale(st, today) else ""
    L = [f"Streak {st['streak']}/{STREAK_BAR} rising traded weeks; status {st['status']}; traded {st['traded']}, paused {st['paused']}, "
         f"non-rising {st['non_rising']}; settled {_usd(st['cum_pnl_usd'])}{tag}."]
    if o:
        dist = (f"XSP {o['xsp_close']:.2f} on {o['xsp_close_day']} is {o['dist_to_short_pct']:.2f}% above the short strike"
                if o["xsp_close"] is not None and o["dist_to_short_pct"] is not None else "no ^XSP close on disk")
        ml = ("max loss unknown (a strike is missing from the record)" if o["max_loss_usd"] is None
              else f"max loss ${o['max_loss_usd']:,.0f}" + (" - a full loss breaches the -30% bound" if o["full_loss_breaches"] else ""))
        L.append(f"Open spread {o['short_k']}/{o['long_k']} expires {_d(o['expiry']):%a} {o['expiry']} ({o['sessions_to_expiry']} sessions); {dist}; {ml}.")
    else:
        L.append("No open spread (" + st["next_line"] + ").")
    if eq["last"] is not None and eq.get("hwm") is not None:
        L.append(f"Equity {eq['last']:,.2f} at the {eq['last_day']} {_mark_basis(eq)}; high-water {eq['hwm']:,.2f}; drawdown {abs(eq['dd_pct'] or 0):.1f}% "
                 f"(bound -{DD_BOUND * 100:.0f}%, floor {eq['floor']:,.2f}).")
    yday = today - timedelta(days=1)
    for w in st["weeks"]:
        if w["kind"] in ("TRADED", "UNCOUNTED") and str(w.get("settled_at") or "")[:10] in (yday.isoformat(), today.isoformat()):
            L.append(f"Settled: week {w['expiry']} {_usd(w['pnl_usd'])}" + (f" (XSP {w['xsp_settle']:.2f})" if w.get("xsp_settle") is not None else "") + ".")
    if st["mechanics"]:
        L.append("Mechanics: " + " | ".join(m["text"] for m in st["mechanics"][-2:]) + ".")
    L.append(st["honesty"][0])
    L.append(f"Tail bound pooled with the archive: {_pct(p['ub'])} -> {_usd(p['ev_realised'])}/wk realised, {_usd(p['ev_max'])}/wk at max loss.")
    return "\n".join(L)


def load_inputs(today):
    today = _d(today)
    recs = json.load(open(RECORDS, encoding="utf-8"))
    recs = recs if isinstance(recs, list) else []
    out = []
    for r in recs:
        r = dict(r)
        if str(r.get("entry_ts_utc") or "")[:10] > today.isoformat():
            continue
        if r.get("status") == "CLOSED" and isinstance(r.get("settle"), dict) and str(r["settle"].get("at") or "")[:10] > today.isoformat():
            r["status"] = "OPEN"
            r.pop("settle", None)
        out.append(r)
    eq = [json.loads(l) for l in open(EQUITY, encoding="utf-8") if l.strip()]
    eq = [x for x in eq if str(x.get("day"))[:10] <= today.isoformat()]
    spec = json.load(open(SPEC, encoding="utf-8"))
    pa = spec.get("proof_account") or {}
    seat = (pa.get("seats") or [{}])[0]
    seated = _d(seat["seated"])
    C = seat["stint_constants"]
    return out, eq, seated, C, bool(pa.get("enabled"))


def _write_json(path, st):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1)
    os.replace(tmp, path)


def _publish_tracked(st, today):
    os.makedirs(os.path.dirname(TRACKED), exist_ok=True)
    _write_json(TRACKED, st)
    try:
        run = lambda *a: subprocess.run(list(a), cwd=REPO, capture_output=True, text=True, timeout=180)
        run("git", "add", "-f", os.path.relpath(TRACKED, REPO))
        c = run("git", "-c", "user.name=proofstint", "-c", "user.email=proofstint@vps", "commit", "-qm",
                f"proof stint state {today} [skip ci]")
        if c.returncode != 0:
            print("proof stint: tracked copy unchanged, nothing to push")
            return
        run("git", "pull", "-q", "--rebase", "--autostash", "origin", "main")
        p = run("git", "push", "-q", "origin", "HEAD:main")
        print("proof stint: tracked copy pushed" if p.returncode == 0 else f"proof stint: PUSH FAILED: {p.stderr.strip()[:200]}")
    except Exception as e:
        print(f"proof stint: publish failed open: {type(e).__name__}: {e}")


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    dry = "--dry" in args
    as_of = None
    if "--as-of" in args:
        as_of = _d(args[args.index("--as-of") + 1])
    now = datetime.now(timezone.utc)
    today = as_of or now.date()
    # ONE guarded path (2026-09-26 fix G): a raise anywhere here would put a traceback into the cron log and skip the
    # page; every failure prints one PROOF STINT: FAILED line and pages [MONITOR] instead. rc 1 only when the inputs
    # could not be read (the design's contract); a failure after the judge ran returns 0 with the line and the page.
    stage = "READ inputs"
    try:
        records, equity, seated, C, enabled = load_inputs(today)
        stage = "JUDGE"
        weeks = week_rows(records, equity, seated, today)
        st = judge(weeks, equity, C, today, seated, records=records, xsp_close=xsp_close_on_disk(today),
                   include_today=(as_of is not None or now.hour >= 21))
        st["proof_account_enabled"] = enabled
        try:
            prev = read_state()
            if prev.get("seated") == st["seated"]:
                st["announced"] = list(prev.get("announced") or [])
        except Exception:
            pass
        stage = "RENDER"
        print(healthy_line(st), flush=True)
        print(render(st), flush=True)
        if dry or as_of is not None:
            print("(dry run - nothing written, nothing sent)" if dry else f"(replay as of {as_of} - nothing written, nothing sent)")
            return 0
        stage = "ANNOUNCE"
        announce(st, send_telegram)
        stage = f"WRITE {DURABLE}"
        _write_json(DURABLE, st)
        if now.weekday() == 4:
            stage = "PUBLISH tracked copy"
            _publish_tracked(st, today.isoformat())
        return 0
    except Exception as e:
        msg = f"PROOF STINT: FAILED at {stage} ({RECORDS}, {EQUITY}, {SPEC}): {type(e).__name__}: {str(e)[:200]}"
        print(msg, flush=True)
        if not dry and as_of is None:
            try:
                send_telegram("[MONITOR] " + msg)
            except Exception:
                pass
        return 1 if stage == "READ inputs" else 0


if __name__ == "__main__":
    sys.exit(main())

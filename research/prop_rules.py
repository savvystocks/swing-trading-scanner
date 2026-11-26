"""Prop-firm challenge rules as code (FTMO 2-Step shape; PROP_FIRMS.md, read 2026-11-10).

Rules modelled, each a parameter:
- daily loss: equity may not fall below (balance at the local midnight that started the day) - daily_pct x initial.
  Local midnight is Europe/Prague (CET/CEST). An open loss carried over midnight still counts, because the
  reference is the closed balance. TO VERIFY against the firm's own wording before any paid challenge.
- total loss: equity may never fall below (1 - total_pct) x initial (a static floor).
- a phase is passed at the first mark where the account is flat, equity >= (1 + target) x initial, and at least
  min_days distinct local dates have traded.
- phase 2 starts on a fresh account at the next mark where the strategy is flat.

A mark is (utc_datetime, equity, balance, traded, flat). Equity must be the WORST value since the previous mark
(use the bar's adverse extreme), or intraday breaches are invisible. Marks are rebased to the phase start, so the
caller passes one continuous account path of any size.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")
PASS, BREACH_DAILY, BREACH_TOTAL, OPEN = "PASS", "BREACH_DAILY", "BREACH_TOTAL", "OPEN"


def run_phase(marks, start, target, daily_pct=0.05, total_pct=0.10, min_days=4, tz=PRAGUE):
    """Evaluate one phase from marks[start] (which must be flat). Returns (outcome, index_of_outcome)."""
    t0, eq0, bal0, _, flat0 = marks[start]
    if not flat0 or eq0 <= 0 or abs(eq0 - bal0) > 1e-9 * max(eq0, 1.0):
        raise ValueError("a phase must start flat, with equity equal to balance")
    floor_total = 1.0 - total_pct
    day = t0.astimezone(tz).date()
    day_ref = 1.0
    last_balance = 1.0
    traded_days = set()
    for i in range(start + 1, len(marks)):
        t, eq, bal, traded, flat = marks[i]
        if t.tzinfo is None:
            raise ValueError("marks need timezone-aware datetimes")
        d = t.astimezone(tz).date()
        if d != day:
            day, day_ref = d, last_balance
        e, b = eq / eq0, bal / eq0
        if traded:
            traded_days.add(d)
        if e < floor_total - 1e-12:
            return BREACH_TOTAL, i
        if e < day_ref - daily_pct - 1e-12:
            return BREACH_DAILY, i
        if flat and e >= 1.0 + target - 1e-12 and len(traded_days) >= min_days:
            return PASS, i
        last_balance = b
    return OPEN, len(marks) - 1


def run_challenge(marks, start=0, targets=(0.10, 0.05), **rules):
    """Both phases in order. Returns (outcome, index, phase_number)."""
    i = start
    for n, target in enumerate(targets, 1):
        outcome, i = run_phase(marks, i, target, **rules)
        if outcome != PASS:
            return outcome, i, n
    return PASS, i, len(targets)


def utc(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)

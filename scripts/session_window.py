"""SESSION WINDOW (2026-10-05): is this instant inside the NYSE session, read on the New York clock?

Every hour on the VPS is UTC, and the NYSE trades 13:30-20:00 UTC only while the US is on daylight time; from the
first Sunday of November it trades 14:30-21:00 UTC. `scripts/engine_watch.sh` judged the engine's liveness inside a
fixed 13:40-20:05 UTC window, which in winter pages (and starts the VPS failover) before the open and leaves the
session's last hour unwatched (BREAKDOWNS 2026-10-05). This module answers from the XNYS calendar, holidays and
13:00 half days included, and when the calendar cannot be read it falls back to the New York wall clock, Monday to
Friday, 09:30-16:00 - never to a UTC hour.

  ./.venv/bin/python scripts/session_window.py                          INSIDE ... / OUTSIDE ... (exit 0 either way)
  ./.venv/bin/python scripts/session_window.py --at 2026-11-02T14:45:00Z
A caller reads the first word; anything else (a traceback, nothing at all) means the helper did not answer and the
caller uses its own New York clock fallback."""
import sys
from datetime import datetime, timedelta, timezone

NY = "America/New_York"
OPEN_MARGIN_MIN = 10
CLOSE_MARGIN_MIN = 5


def _ny():
    from zoneinfo import ZoneInfo
    return ZoneInfo(NY)


def session_utc(day):
    """(open, close, source) in UTC for the XNYS session on `day`, or (None, None, source) when there is none."""
    try:
        import pandas_market_calendars as mcal
        sch = mcal.get_calendar("XNYS").schedule(start_date=day.isoformat(), end_date=day.isoformat())
        if not len(sch):
            return None, None, "xnys"
        o = sch.iloc[0]["market_open"].to_pydatetime().astimezone(timezone.utc)
        c = sch.iloc[0]["market_close"].to_pydatetime().astimezone(timezone.utc)
        return o, c, "xnys"
    except Exception:
        pass
    if day.weekday() > 4:
        return None, None, "ny-clock"
    tz = _ny()
    o = datetime(day.year, day.month, day.day, 9, 30, tzinfo=tz).astimezone(timezone.utc)
    c = datetime(day.year, day.month, day.day, 16, 0, tzinfo=tz).astimezone(timezone.utc)
    return o, c, "ny-clock"


def in_window(now=None, open_margin_min=OPEN_MARGIN_MIN, close_margin_min=CLOSE_MARGIN_MIN):
    """(inside, text): True from `open_margin_min` after the session's open through `close_margin_min` after its
    close, on the session of the New York date `now` falls on."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    day = now.astimezone(_ny()).date()
    o, c, src = session_utc(day)
    if o is None:
        return False, f"no session on {day} ({src})"
    lo, hi = o + timedelta(minutes=open_margin_min), c + timedelta(minutes=close_margin_min)
    return lo <= now <= hi, f"{lo:%H:%M}-{hi:%H:%M} UTC on {day} ({src})"


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    now = None
    if "--at" in args:
        now = datetime.fromisoformat(args[args.index("--at") + 1].replace("Z", "+00:00"))
    inside, why = in_window(now)
    print(("INSIDE " if inside else "OUTSIDE ") + why, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

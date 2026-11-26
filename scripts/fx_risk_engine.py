"""Risk engine: the one pure coordinator between any book's signals and its orders (FX, index and gold CFDs).
Owner's fixed rules, every limit a fraction of the start balance B0: no new trade once equity (NAV, floating included)
is 2.5% of B0 below the balance at Europe/Prague midnight; no new trade ever again once NAV falls to 94% of B0;
open initial risk in total at most 2.5% of B0; today's loss from the Prague-midnight balance (floating included) plus
all open initial risk, the new trade's included, at most 4% of B0 (the cushion); each trade's risk as the book gives it.
Correlation clusters, whose combined initial risk may not exceed the proposed trade's risk r: same-direction USD
exposure across FX pairs, and equity-index longs. A trade that does not fit the open-risk cap or its cluster is cut to
the room left, or skipped when that room is below 0.25 r; a trade that, at that size, would pass the cushion is
refused."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")
DAY_STOP, TOTAL_PAUSE, OPEN_RISK_CAP, CUSHION, MIN_CUT = 0.025, 0.06, 0.025, 0.04, 0.25
INDEX_LONGS = {"US500", "US100", "US30", "US2000", "GER40", "UK100", "JP225", "EU50"}
ALIASES = {"SPX500USD": "US500", "NAS100USD": "US100", "US30USD": "US30", "US2000USD": "US2000", "DE30EUR": "GER40",
           "DE40EUR": "GER40", "UK100GBP": "UK100", "JP225USD": "JP225", "EU50EUR": "EU50"}
METALS = {"XAU", "XAG", "XPT", "XPD"}


def symbol(instrument):
    s = instrument.upper().replace(".CASH", "").replace("_", "").replace("/", "")
    return ALIASES.get(s, s)


def cluster(instrument, direction):
    s = symbol(instrument)
    if s in INDEX_LONGS:
        return "equity index long" if direction == 1 else None
    if len(s) == 6 and s.isalpha() and s[:3] not in METALS and s[3:] not in METALS:
        if s[3:] == "USD":
            return "USD short" if direction == 1 else "USD long"
        if s[:3] == "USD":
            return "USD long" if direction == 1 else "USD short"
    return None


def prague_midnight_ns(now_ns):
    loc = datetime.fromtimestamp(now_ns // 10**9, tz=timezone.utc).astimezone(PRAGUE)
    return int(loc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) * 10**9


def prague_day(now_ns):
    return datetime.fromtimestamp(now_ns // 10**9, tz=timezone.utc).astimezone(PRAGUE).date().isoformat()


def refresh(guard, balance, nav, now_ns, closed=()):
    """New guard state. B0 = first balance seen; the day reference is set on the first run of each Prague day, with the
    realized P&L of trades closed after that midnight (closed = (close_ns, pl) pairs) taken back out; the pause latches."""
    g = dict(guard)
    g.setdefault("B0", balance)
    day = prague_day(now_ns)
    if g.get("prague_day") != day:
        m0 = prague_midnight_ns(now_ns)
        g["prague_day"], g["prague_ref"] = day, balance - sum(pl for t, pl in closed if t >= m0)
    if nav <= (1 - TOTAL_PAUSE) * g["B0"]:
        g["paused"] = True
    return g


def assess(account, prague_balance, trade):
    """account: nav, start (B0), paused, open = [{instrument, direction, risk_usd}]; trade: instrument, direction,
    risk_usd. Returns (allowed_units_fraction, reason)."""
    nav, b0 = float(account["nav"]), float(account["start"])
    if account.get("paused") or nav <= (1 - TOTAL_PAUSE) * b0:
        return 0.0, f"PAUSED: NAV {nav:,.0f} at or below 94% of the start balance {b0:,.0f} (6% total pause, no new trades)"
    if nav <= prague_balance - DAY_STOP * b0:
        return 0.0, (f"day stop: NAV {nav:,.0f} is 2.5% of {b0:,.0f} below the Prague-midnight balance "
                     f"{prague_balance:,.0f}")
    r = float(trade["risk_usd"])
    held = account.get("open", ())
    room, why = r, ""
    cap_room = OPEN_RISK_CAP * b0 - sum(p["risk_usd"] for p in held)
    if cap_room < room:
        room, why = cap_room, f"open-risk cap: {OPEN_RISK_CAP * b0 - cap_room:,.2f} of {OPEN_RISK_CAP * b0:,.2f} USD already at risk"
    c = cluster(trade["instrument"], trade["direction"])
    if c:
        in_c = sum(p["risk_usd"] for p in held if cluster(p["instrument"], p["direction"]) == c)
        if r - in_c < room:
            room, why = r - in_c, (f"same-direction {'dollar bet' if c.startswith('USD') else c} already open: the {c} "
                                   f"cluster holds {in_c:,.2f} of the {r:,.2f} USD single-trade risk")
    if room < MIN_CUT * r:
        return 0.0, why + " (room below 0.25 of the trade's risk, skipped)"
    take = min(room, r)
    loss, at_risk = max(0.0, prague_balance - nav), sum(p["risk_usd"] for p in held)
    if loss + at_risk + take > CUSHION * b0:
        return 0.0, (f"4% cushion: today's loss {loss:,.2f} plus {at_risk:,.2f} USD open risk plus this trade's "
                     f"{take:,.2f} would pass {CUSHION * b0:,.2f} USD (refused)")
    if room >= r:
        return 1.0, ""
    return room / r, why + f" (cut to {room / r:.0%} of the trade's risk)"

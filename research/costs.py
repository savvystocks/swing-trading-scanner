"""Executable costs for FX research on FTMO terms (ftmo.com/en/symbols, read 2026-11-26; swing_research/data/ftmo_costs_2026-11-26.md).
Entries buy the ask and sell the bid, exits the other side; a stop gapped through is booked at the bar's open, never at the stop;
commission is 5 USD per lot (100,000 units) with the per-side vs round-turn basis a parameter because the page does not say;
swap is FTMO points per lot per night, charged at each 17:00 New York rollover Monday-Friday and tripled on one weekday."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
FX_LOT = 100_000
FTMO_FX_COMMISSION_PER_LOT = 5.0
FTMO_FX_SWAP_POINTS = {"EURUSD": (-9.21, 0.04), "GBPUSD": (-4.93, -8.23), "AUDUSD": (-2.74, -10.14),
                       "NZDUSD": (-4.72, -0.10), "USDJPY": (0.35, -21.10), "USDCHF": (0.27, -16.54),
                       "USDCAD": (0.43, -10.59)}


def symbol(pair):
    return pair.upper().replace("_", "").replace("/", "")


def point(pair):
    return 0.001 if symbol(pair).endswith("JPY") else 0.00001


def entry_price(direction, bid, ask):
    return ask if direction == 1 else bid


def exit_price(direction, bid, ask):
    return bid if direction == 1 else ask


def stop_exit(direction, stop, side_open, side_extreme, slip=0.0):
    """Exit-side prices only: bid open and bid low for a long, ask open and ask high for a short."""
    if (side_open - stop) * direction <= 0:
        return side_open - slip * direction
    if (side_extreme - stop) * direction <= 0:
        return stop - slip * direction
    return None


def commission_usd(units, basis="per_side", per_lot=FTMO_FX_COMMISSION_PER_LOT, lot=FX_LOT):
    return abs(units) / lot * per_lot * {"per_side": 2, "round_turn": 1}[basis]


def swap_nights(t_in, t_out, triple_weekday=2, roll_hour=17, tz=NY):
    """Rollovers with t_in < roll <= t_out (aware datetimes), weighted 3 on triple_weekday (0 = Monday)."""
    d = t_in.astimezone(tz).date()
    end = t_out.astimezone(tz).date()
    n = 0
    while d <= end:
        if d.weekday() < 5:
            roll = datetime(d.year, d.month, d.day, roll_hour, tzinfo=tz)
            if t_in < roll <= t_out:
                n += 3 if d.weekday() == triple_weekday else 1
        d += timedelta(days=1)
    return n


def swap_quote(points, pair, units, nights):
    return points * point(pair) * abs(units) * nights


def to_usd(amount, pair, rate):
    s = symbol(pair)
    if s[3:] == "USD":
        return amount
    if s[:3] == "USD":
        return amount / rate
    raise ValueError(f"{pair}: no USD leg, pass the amount already in USD")


def trade_pnl_usd(pair, direction, units, entry, exit, t_in, t_out, basis="per_side", swap_points=None):
    """Net USD of one FX trade at executable prices: price move, FTMO swap for the side held, commission."""
    pts = (swap_points or FTMO_FX_SWAP_POINTS)[symbol(pair)][0 if direction == 1 else 1]
    quote = (exit - entry) * direction * abs(units) + swap_quote(pts, pair, units, swap_nights(t_in, t_out))
    return to_usd(quote, pair, exit) - commission_usd(units, basis)

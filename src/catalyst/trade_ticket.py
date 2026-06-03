"""Trade ticket builder.

Turns a confluence pick into an actionable order: exact strike, expiry,
contract symbol, and live premium so the user can paste into Robinhood
without further lookup.
"""

from datetime import date, timedelta


def _round_strike(price, side, vehicle):
    """Pick a strike based on vehicle intent + current spot."""
    if "far OTM" in vehicle:
        offset = 0.05 if side == "CALL" else -0.05
    elif "0.5 ITM" in vehicle or "ITM" in vehicle:
        offset = -0.015 if side == "CALL" else 0.015
    else:
        offset = 0

    target = price * (1 + offset)

    if target < 50:
        return round(target * 2) / 2  # nearest 0.5
    if target < 200:
        return round(target)
    if target < 500:
        return round(target / 5) * 5
    return round(target / 10) * 10


def _parse_target_dte(vehicle):
    """Extract DTE midpoint from vehicle string."""
    if "0-3 DTE" in vehicle:
        return 2
    if "7d" in vehicle or "MODERATE" in vehicle:
        return 7
    if "21-30d" in vehicle:
        return 25
    return 21


def _next_friday(target_date):
    """Round to next standard option expiry Friday."""
    days_ahead = (4 - target_date.weekday()) % 7
    if days_ahead == 0:
        return target_date
    return target_date + timedelta(days=days_ahead)


def _occ_symbol(ticker, expiry, side, strike):
    """OCC standard option symbol: TICKERYYMMDDC00STRIKE000."""
    cp = "C" if side == "CALL" else "P"
    strike_int = int(round(strike * 1000))
    return f"{ticker}{expiry.strftime('%y%m%d')}{cp}{strike_int:08d}"


def _fetch_contract_quote(uw_client, ticker, expiry, side, strike):
    """Pull live bid/ask/last from UW option-chains for the specific contract."""
    try:
        chain = uw_client.option_chains(ticker)
    except Exception:
        return None
    if not chain:
        return None
    rows = chain.get("data") if isinstance(chain, dict) else chain
    if not isinstance(rows, list):
        return None
    cp = "C" if side == "CALL" else "P"
    occ_prefix = f"{ticker}{expiry.strftime('%y%m%d')}{cp}"
    strike_int = int(round(strike * 1000))
    occ = f"{occ_prefix}{strike_int:08d}"
    for r in rows:
        if not isinstance(r, dict):
            continue
        sym = r.get("option_symbol") or r.get("symbol")
        if sym == occ:
            return {
                "bid": _safe_float(r.get("bid")),
                "ask": _safe_float(r.get("ask")),
                "last": _safe_float(r.get("last") or r.get("last_price")),
                "iv": _safe_float(r.get("implied_volatility") or r.get("iv")),
                "delta": _safe_float(r.get("delta")),
                "volume": r.get("volume"),
                "open_interest": r.get("open_interest"),
            }
    return None


def _safe_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def compute_trade_ticket(ticker, spot, side, vehicle, uw_client=None, today=None):
    """Build a copy-pasteable order from a confluence pick.

    Returns dict with strike, expiry, contract symbol, mid price.
    """
    if not side or not spot or not ticker:
        return None
    today = today or date.today()
    target_dte = _parse_target_dte(vehicle)
    expiry = _next_friday(today + timedelta(days=target_dte))
    strike = _round_strike(spot, side, vehicle)
    occ = _occ_symbol(ticker, expiry, side, strike)

    ticket = {
        "ticker": ticker,
        "side": side,
        "strike": strike,
        "expiry": expiry.isoformat(),
        "dte": (expiry - today).days,
        "occ_symbol": occ,
        "vehicle_description": vehicle,
        "spot": spot,
    }

    if uw_client and uw_client.enabled:
        quote = _fetch_contract_quote(uw_client, ticker, expiry, side, strike)
        if quote:
            ticket["quote"] = quote
            bid = quote.get("bid") or 0
            ask = quote.get("ask") or 0
            if bid and ask:
                ticket["mid"] = round((bid + ask) / 2, 2)
            else:
                ticket["mid"] = quote.get("last")

    return ticket


def format_order_line(ticket):
    """Single-line order text for the email/Telegram."""
    if not ticket:
        return "no trade ticket"
    t = ticket["ticker"]
    side = ticket["side"]
    strike = ticket["strike"]
    expiry = ticket["expiry"]
    dte = ticket.get("dte", "?")
    mid = ticket.get("mid")
    line = f"{t} {side} ${strike} exp {expiry} ({dte}d)"
    if mid:
        line += f"  @ ${mid:.2f} mid"
    return line

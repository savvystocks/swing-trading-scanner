"""Trade ticket builder.

Turns a confluence pick into an actionable order: exact strike, expiry,
contract symbol, live premium, delta, IV, OI, volume.
"""

import math
from datetime import date, timedelta


def _norm_cdf(x):
    """Standard normal CDF using math.erf - no scipy needed."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_delta(side, spot, strike, dte_days, iv, r=0.05):
    """Black-Scholes delta. dte_days in calendar days, iv as decimal (0.30 = 30%)."""
    if not spot or not strike or not iv or dte_days is None or dte_days <= 0:
        return None
    try:
        T = dte_days / 365.0
        d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * T) / (iv * math.sqrt(T))
        if side == "CALL":
            return round(_norm_cdf(d1), 3)
        return round(_norm_cdf(d1) - 1, 3)
    except (ValueError, ZeroDivisionError):
        return None


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


def _parse_symbol(sym):
    """OCC format: AAPL260703C00310000 -> (ticker, date, side, strike_float)."""
    if not sym or len(sym) < 16:
        return None
    # Find where digits start
    i = 0
    while i < len(sym) and sym[i].isalpha():
        i += 1
    ticker = sym[:i]
    if len(sym) < i + 7:
        return None
    yymmdd = sym[i:i+6]
    cp = sym[i+6]
    strike_raw = sym[i+7:]
    try:
        yr = 2000 + int(yymmdd[:2])
        mo = int(yymmdd[2:4])
        dy = int(yymmdd[4:6])
        d = date(yr, mo, dy)
        side = "CALL" if cp == "C" else "PUT"
        strike = int(strike_raw) / 1000.0
        return (ticker, d, side, strike)
    except Exception:
        return None


def _find_best_contract(uw_client, ticker, side, target_expiry, target_strike):
    """Search chain for best matching contract by expiry + strike."""
    try:
        chain = uw_client.option_chains(ticker)
    except Exception:
        return None
    if not chain:
        return None
    syms = chain.get("data") if isinstance(chain, dict) else chain
    if not isinstance(syms, list):
        return None

    best = None
    best_distance = (float("inf"), float("inf"))  # (expiry_days, strike_diff)
    for sym in syms:
        if not isinstance(sym, str):
            continue
        parsed = _parse_symbol(sym)
        if not parsed:
            continue
        s_ticker, s_date, s_side, s_strike = parsed
        if s_ticker != ticker or s_side != side:
            continue
        expiry_diff = abs((s_date - target_expiry).days)
        strike_diff = abs(s_strike - target_strike)
        # Prioritize matching expiry within 5d, then closest strike
        if expiry_diff > 5:
            continue
        if (expiry_diff, strike_diff) < best_distance:
            best_distance = (expiry_diff, strike_diff)
            best = (sym, s_date, s_strike)
    return best


def _fetch_contract_data(uw_client, ticker, target_symbol):
    """Pull contract-level data: NBBO quotes, IV, OI, volume, sweep/floor share."""
    try:
        data = uw_client._request(f"/stock/{ticker}/option-contracts", None,
                                   cache_key="oi_per_strike", ttl=600)
    except Exception:
        return None
    if not data:
        return None
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return None
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("option_symbol") == target_symbol:
            return {
                "bid": _safe_float(r.get("nbbo_bid")),
                "ask": _safe_float(r.get("nbbo_ask")),
                "last": _safe_float(r.get("last_price")),
                "iv": _safe_float(r.get("implied_volatility")),
                "volume": r.get("volume"),
                "open_interest": r.get("open_interest"),
                "prev_oi": r.get("prev_oi"),
                "sweep_volume": r.get("sweep_volume"),
                "floor_volume": r.get("floor_volume"),
                "ask_volume": r.get("ask_volume"),
                "bid_volume": r.get("bid_volume"),
                "total_premium": _safe_float(r.get("total_premium")),
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
        # Step 1: validate contract exists in chain (find closest match)
        best = _find_best_contract(uw_client, ticker, side, expiry, strike)
        if best:
            actual_sym, actual_expiry, actual_strike = best
            ticket["occ_symbol"] = actual_sym
            ticket["strike"] = actual_strike
            ticket["expiry"] = actual_expiry.isoformat()
            ticket["dte"] = (actual_expiry - today).days
            # Step 2: pull live contract data (NBBO, IV, OI, volume)
            quote = _fetch_contract_data(uw_client, ticker, actual_sym)
            if quote:
                ticket["quote"] = quote
                bid = quote.get("bid") or 0
                ask = quote.get("ask") or 0
                if bid and ask:
                    ticket["mid"] = round((bid + ask) / 2, 2)
                elif quote.get("last"):
                    ticket["mid"] = quote.get("last")
                # Step 3: compute delta from BS using IV + spot + strike + dte
                iv = quote.get("iv")
                if iv:
                    delta = _bs_delta(side, spot, ticket["strike"], ticket["dte"], iv)
                    if delta is not None:
                        ticket["delta"] = delta

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

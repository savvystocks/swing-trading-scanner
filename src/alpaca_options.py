import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")


def get_live_price(symbol):
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
        client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        result = client.get_stock_latest_trade(req)
        trade = result.get(symbol) if isinstance(result, dict) else result
        if trade and hasattr(trade, "price") and trade.price:
            return float(trade.price)
    except Exception as e:
        logger.warning(f"Live price fetch for {symbol}: {e}")
    return None


def get_options_chain(symbol, direction, current_price):
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None

    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        logger.warning("alpaca-py not installed")
        return None

    try:
        client = OptionHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

        today = datetime.now()
        min_exp = (today + timedelta(days=14)).strftime("%Y-%m-%d")
        max_exp = (today + timedelta(days=50)).strftime("%Y-%m-%d")

        right = "call" if direction == "call" else "put"

        if direction == "call":
            strike_lo = current_price * 0.90
            strike_hi = current_price * 1.15
        else:
            strike_lo = current_price * 0.85
            strike_hi = current_price * 1.10

        request = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(strike_lo, 2)),
            strike_price_lte=str(round(strike_hi, 2)),
            type=right,
        )
        snapshots = client.get_option_chain(request)
    except Exception as e:
        logger.warning(f"Alpaca chain fetch for {symbol}: {e}")
        return None

    if not snapshots:
        return None

    contracts = []
    for contract_symbol, snapshot in snapshots.items():
        try:
            greeks = snapshot.greeks
            quote = snapshot.latest_quote
            trade = snapshot.latest_trade

            if not greeks or not quote:
                continue

            delta = abs(greeks.delta) if greeks.delta else 0
            if delta < 0.30 or delta > 0.70:
                continue

            bid = float(quote.bid_price) if quote.bid_price else 0
            ask = float(quote.ask_price) if quote.ask_price else 0
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
            if mid <= 0.10:
                continue

            spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 100
            if spread_pct > 40:
                continue

            parts = contract_symbol.split()
            strike = None
            expiration = None
            contract_right = "C"
            try:
                sym_str = contract_symbol if isinstance(contract_symbol, str) else str(contract_symbol)
                import re
                m = re.match(r'([A-Z]+)(\d{6})([CP])(\d+)', sym_str)
                if m:
                    exp_raw = m.group(2)
                    contract_right = m.group(3)
                    strike_raw = m.group(4)
                    expiration = f"20{exp_raw[:2]}-{exp_raw[2:4]}-{exp_raw[4:6]}"
                    strike = int(strike_raw) / 1000
            except Exception:
                pass

            if not strike or not expiration:
                continue

            dte = (datetime.strptime(expiration, "%Y-%m-%d") - datetime.now()).days
            if dte < 14 or dte > 50:
                continue

            oi = int(snapshot.open_interest) if snapshot.open_interest else 0
            vol = int(trade.size) if trade else 0

            score = 0
            if 0.40 <= delta <= 0.60:
                score += 3
            else:
                score += 1
            if oi >= 500:
                score += 2
            elif oi >= 100:
                score += 1
            if 21 <= dte <= 35:
                score += 2
            else:
                score += 1
            if spread_pct < 10:
                score += 2
            elif spread_pct < 20:
                score += 1

            contracts.append({
                "strike": strike,
                "expiration": expiration,
                "dte": dte,
                "delta": round(delta, 3),
                "gamma": round(abs(greeks.gamma), 4) if greeks.gamma else 0,
                "theta": round(greeks.theta, 4) if greeks.theta else 0,
                "vega": round(greeks.vega, 4) if greeks.vega else 0,
                "impliedVol": round(greeks.implied_volatility, 4) if greeks.implied_volatility else 0,
                "bid": bid,
                "ask": ask,
                "mid": round(mid, 2),
                "openInterest": oi,
                "volume": vol,
                "spread_pct": round(spread_pct, 1),
                "score": score,
                "right": contract_right,
            })
        except Exception as e:
            continue

    if not contracts:
        return None
    contracts.sort(key=lambda x: x["score"], reverse=True)
    return contracts[0]

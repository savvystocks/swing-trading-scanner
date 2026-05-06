import os
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def detect_unusual_options_activity(symbol, current_price):
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        return None
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None

    today = datetime.now()
    min_exp = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    max_exp = (today + timedelta(days=45)).strftime("%Y-%m-%d")

    try:
        client = OptionHistoricalDataClient(api_key, api_secret)
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(current_price * 0.85, 2)),
            strike_price_lte=str(round(current_price * 1.20, 2)),
        )
        snaps = client.get_option_chain(req)
    except Exception as e:
        logger.warning(f"options_flow {symbol}: {e}")
        return None

    if not snaps:
        return None

    call_volume_total = 0
    put_volume_total = 0
    call_oi_total = 0
    put_oi_total = 0
    otm_call_oi = 0
    otm_put_oi = 0
    call_ivs_atm = []
    put_ivs_atm = []
    call_ivs_otm = []
    put_ivs_otm = []
    block_trades = []

    for sym, snap in snaps.items():
        try:
            sym_str = sym if isinstance(sym, str) else str(sym)
            m = re.match(r"[A-Z]+\d{6}([CP])(\d+)", sym_str)
            if not m:
                continue
            is_call = m.group(1) == "C"
            strike = int(m.group(2)) / 1000

            quote = getattr(snap, "latest_quote", None)
            trade = getattr(snap, "latest_trade", None)
            greeks = getattr(snap, "greeks", None)

            vol = int(trade.size) if trade and getattr(trade, "size", None) else 0
            if is_call:
                call_volume_total += vol
            else:
                put_volume_total += vol

            iv_raw = getattr(snap, "implied_volatility", None)
            if iv_raw is None and greeks:
                iv_raw = getattr(greeks, "implied_volatility", None)
            try:
                iv = float(iv_raw) if iv_raw else 0
            except (TypeError, ValueError):
                iv = 0
            iv_pct = iv * 100 if iv and iv < 5 else iv

            delta = abs(float(greeks.delta)) if greeks and greeks.delta else 0

            if 0.40 <= delta <= 0.55:
                if is_call and iv_pct > 0:
                    call_ivs_atm.append(iv_pct)
                elif iv_pct > 0:
                    put_ivs_atm.append(iv_pct)
            elif 0.20 <= delta < 0.40:
                if is_call and iv_pct > 0:
                    call_ivs_otm.append(iv_pct)
                elif iv_pct > 0:
                    put_ivs_otm.append(iv_pct)

            if quote and quote.bid_price and quote.ask_price:
                bid = float(quote.bid_price)
                ask = float(quote.ask_price)
                mid = (bid + ask) / 2
                if vol >= 100 and mid * vol * 100 >= 50000:
                    block_trades.append({
                        "type": "call" if is_call else "put",
                        "strike": strike,
                        "volume": vol,
                        "premium_value": round(mid * vol * 100, 0),
                    })
        except Exception:
            continue

    avg_call_iv_atm = sum(call_ivs_atm) / len(call_ivs_atm) if call_ivs_atm else None
    avg_put_iv_atm = sum(put_ivs_atm) / len(put_ivs_atm) if put_ivs_atm else None
    avg_call_iv_otm = sum(call_ivs_otm) / len(call_ivs_otm) if call_ivs_otm else None
    avg_put_iv_otm = sum(put_ivs_otm) / len(put_ivs_otm) if put_ivs_otm else None

    skew_atm = (avg_put_iv_atm - avg_call_iv_atm) if avg_call_iv_atm and avg_put_iv_atm else None
    skew_otm = (avg_put_iv_otm - avg_call_iv_otm) if avg_call_iv_otm and avg_put_iv_otm else None

    cp_ratio = call_volume_total / put_volume_total if put_volume_total > 0 else None

    bullish_signals = []
    bearish_signals = []

    if cp_ratio is not None and cp_ratio >= 2.0:
        bullish_signals.append(f"call/put volume ratio {cp_ratio:.1f}x (heavy call buying)")
    elif cp_ratio is not None and cp_ratio <= 0.5:
        bearish_signals.append(f"call/put ratio {cp_ratio:.2f}x (puts dominant)")

    if skew_atm is not None and skew_atm < -3:
        bullish_signals.append(f"ATM IV skew {skew_atm:+.1f}% (calls expensive vs puts)")
    elif skew_atm is not None and skew_atm > 5:
        bearish_signals.append(f"ATM IV skew {skew_atm:+.1f}% (puts expensive)")

    big_call_blocks = [b for b in block_trades if b["type"] == "call"]
    if len(big_call_blocks) >= 3:
        total_call_premium = sum(b["premium_value"] for b in big_call_blocks)
        bullish_signals.append(f"{len(big_call_blocks)} call blocks, ${total_call_premium/1000:.0f}k premium")

    sentiment = "BULLISH" if len(bullish_signals) > len(bearish_signals) else (
        "BEARISH" if len(bearish_signals) > len(bullish_signals) else "NEUTRAL"
    )

    return {
        "sentiment": sentiment,
        "call_volume": call_volume_total,
        "put_volume": put_volume_total,
        "call_put_ratio": round(cp_ratio, 2) if cp_ratio else None,
        "atm_iv_skew_pct": round(skew_atm, 2) if skew_atm is not None else None,
        "otm_iv_skew_pct": round(skew_otm, 2) if skew_otm is not None else None,
        "block_trade_count": len(block_trades),
        "block_trades": block_trades[:5],
        "bullish_signals": bullish_signals,
        "bearish_signals": bearish_signals,
    }

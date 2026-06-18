import os
import json
import urllib.request
from datetime import datetime, timedelta

from src.alpaca_ohlcv import get_daily_bars_eodhd_format
from src.alpaca_options import get_live_price


SPX_PROXY = "SPY"


def _env_float(key, default):
    raw = os.environ.get(key, "")
    if isinstance(raw, str):
        raw = raw.strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def get_config():
    return {
        "sma_buffer_pct": _env_float("REGIME_SMA_BUFFER_PCT", 1.0),
        "yen_slope_tol_pct": _env_float("REGIME_YEN_SLOPE_TOL_PCT", 0.05),
    }


def _sma(values, n):
    if len(values) < n:
        return None
    return sum(values[:n]) / n


def _spx_state(config):
    bars = get_daily_bars_eodhd_format(
        SPX_PROXY, from_date=(datetime.utcnow().date() - timedelta(days=400)).isoformat())
    if not bars:
        return None
    bars.sort(key=lambda b: b["date"], reverse=True)
    closes = [b["close"] for b in bars]
    sma20 = _sma(closes, 20)
    if sma20 is None:
        return None
    live = get_live_price(SPX_PROXY)
    spot = live if live else closes[0]
    buffer = config["sma_buffer_pct"] / 100.0
    upper = sma20 * (1.0 + buffer)
    lower = sma20 * (1.0 - buffer)
    window_high = max(closes) if closes else spot
    new_ath = spot >= window_high
    if spot > upper:
        zone = "ABOVE"
    elif spot < lower:
        zone = "BELOW"
    else:
        zone = "WITHIN"
    return {
        "spot": round(spot, 2),
        "sma20": round(sma20, 2),
        "buffer_pct": config["sma_buffer_pct"],
        "upper_band": round(upper, 2),
        "lower_band": round(lower, 2),
        "zone": zone,
        "new_ath": bool(new_ath),
        "source": "live" if live else f"close {bars[0]['date']}",
    }


def _yen_state(config):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/JPY=X?interval=1d&range=1mo"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c is not None]
    except Exception as e:
        return {"slope_dir": None, "reason": f"yen fetch failed: {type(e).__name__}"}
    if len(closes) < 10:
        return {"slope_dir": None, "reason": "insufficient yen data"}
    sma5_now = sum(closes[-5:]) / 5.0
    sma5_prev = sum(closes[-10:-5]) / 5.0
    slope_pct = (sma5_now - sma5_prev) / sma5_prev * 100.0 if sma5_prev else 0.0
    tol = config["yen_slope_tol_pct"]
    if slope_pct < -tol:
        slope_dir = "FALLING"
    elif slope_pct > tol:
        slope_dir = "RISING"
    else:
        slope_dir = "FLAT"
    return {
        "usdjpy": round(closes[-1], 3),
        "sma5_now": round(sma5_now, 3),
        "sma5_prev": round(sma5_prev, 3),
        "slope_pct": round(slope_pct, 3),
        "slope_dir": slope_dir,
        "yen_strengthening": slope_dir == "FALLING",
        "reason": f"USDJPY 5d SMA {sma5_now:.2f} vs prior {sma5_prev:.2f} ({slope_pct:+.2f}%) -> {slope_dir}",
    }


def evaluate(config=None, verbose=False):
    if config is None:
        config = get_config()

    spx = _spx_state(config)
    yen = _yen_state(config)

    if spx is None:
        regime, bias, directions, reason = "C", "NEUTRAL", [], "no SPX data -> suppress directional"
    else:
        zone = spx["zone"]
        yen_dir = yen.get("slope_dir")
        short_ok = zone == "BELOW" and yen_dir == "FALLING"
        long_ok = (zone == "ABOVE" or spx["new_ath"]) and yen_dir in ("RISING", "FLAT")
        if short_ok:
            regime, bias, directions = "A", "SHORT", ["PUT", "BEAR_PUT_DEBIT", "BEAR_CALL_CREDIT"]
            reason = "liquidity contraction: SPX below 20d SMA buffer AND yen strengthening"
        elif long_ok:
            regime, bias, directions = "B", "LONG", ["CALL", "BULL_CALL_DEBIT", "BULL_PUT_CREDIT"]
            reason = "liquidity expansion: SPX above 20d SMA buffer/ATH AND yen not strengthening"
        elif zone == "WITHIN":
            regime, bias, directions = "C", "NEUTRAL", []
            reason = f"SPY inside +/-{config['sma_buffer_pct']}% of 20d SMA -> chop, suppress directional"
        else:
            regime, bias, directions = "C", "NEUTRAL", []
            reason = f"SPX zone {zone} and yen {yen_dir} disagree -> no clean regime, suppress directional"

    state = {
        "regime": regime,
        "bias": bias,
        "allowed_directions": directions,
        "directional_locked": regime == "C",
        "spx": spx,
        "yen": yen,
        "reason": reason,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }

    if verbose:
        z = spx["zone"] if spx else "n/a"
        print(f"  regime_compass: REGIME {regime} ({bias}) | SPX {z} | yen {yen.get('slope_dir')}")
        print(f"  regime_compass: {reason}")

    return state


def direction_allowed(side, state=None):
    if state is None:
        state = evaluate()
    side = (side or "").upper()
    if state["regime"] == "C":
        return False
    if state["bias"] == "SHORT":
        return side in ("PUT", "SHORT", "BEARISH")
    if state["bias"] == "LONG":
        return side in ("CALL", "LONG", "BULLISH")
    return False


if __name__ == "__main__":
    evaluate(verbose=True)

import os
import json
import time
import pathlib
import urllib.request
from datetime import datetime, timedelta

from src.alpaca_ohlcv import get_daily_bars_eodhd_format
from src.alpaca_options import get_live_price


def _yahoo_chart_closes(symbol, rng="1mo", attempts=3, sleep_s=2.0):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={rng}"
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode())
            closes = [c for c in d["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c is not None]
            if closes:
                return closes
        except Exception:
            pass
        if i < attempts - 1:
            time.sleep(sleep_s)
    return None


SPX_PROXY = "SPY"
_SPX_CACHE = pathlib.Path(__file__).parent.parent.parent / "data" / "ambush_logs" / "regime_cache.json"


def _load_spx_cache():
    try:
        return json.load(open(_SPX_CACHE, encoding="utf-8")) if _SPX_CACHE.exists() else {}
    except Exception:
        return {}


def _save_spx_cache(d):
    try:
        _SPX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(_SPX_CACHE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


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
    today = datetime.utcnow().date().isoformat()
    cache = _load_spx_cache()
    fresh = cache.get("date") == today
    sma20 = cache.get("sma20") if fresh else None
    window_high = cache.get("window_high") if fresh else None
    last_close = cache.get("last_close") if fresh else None

    if sma20 is None or window_high is None:
        bars = get_daily_bars_eodhd_format(
            SPX_PROXY, from_date=(datetime.utcnow().date() - timedelta(days=400)).isoformat())
        if bars:
            bars.sort(key=lambda b: b["date"], reverse=True)
            closes = [b["close"] for b in bars]
            sma20 = _sma(closes, 20)
            window_high = max(closes) if closes else None
            last_close = closes[0] if closes else None
            if sma20 is not None and window_high is not None:
                _save_spx_cache({"date": today, "sma20": sma20, "window_high": window_high, "last_close": last_close})

    if sma20 is None or window_high is None:
        return None
    live = get_live_price(SPX_PROXY)
    spot = live if live else last_close
    if spot is None:
        return None
    buffer = config["sma_buffer_pct"] / 100.0
    upper = sma20 * (1.0 + buffer)
    lower = sma20 * (1.0 - buffer)
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
        "source": "live" if live else "cached close",
    }


def _yen_state(config):
    closes = _yahoo_chart_closes("JPY=X", "1mo")
    if not closes:
        return {"slope_dir": None, "reason": "yen fetch failed after 3 retries -> neutral"}
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


def _vix_term():
    def _close(sym):
        cl = _yahoo_chart_closes(sym, "10d")
        return cl[-1] if cl else None
    vix = _close("%5EVIX")
    vix3m = _close("%5EVIX3M")
    vix9d = _close("%5EVIX9D")
    if vix is None or vix3m is None:
        return {"available": False, "reason": "vix fetch failed after 3 retries -> unavailable"}
    backwardation = vix > vix3m
    return {
        "available": True,
        "vix": round(vix, 2),
        "vix3m": round(vix3m, 2),
        "vix9d": round(vix9d, 2) if vix9d is not None else None,
        "structure": "BACKWARDATION" if backwardation else "CONTANGO",
        "backwardation": bool(backwardation),
    }


def _third_friday(year, month):
    from datetime import date
    first = date(year, month, 1)
    offset = (4 - first.weekday()) % 7
    return date(year, month, 1 + offset + 14)


def _opex_state(today=None):
    if today is None:
        today = datetime.utcnow().date()
    this_opex = _third_friday(today.year, today.month)
    next_opex = this_opex
    if today > this_opex:
        ny = today.year + (1 if today.month == 12 else 0)
        nm = 1 if today.month == 12 else today.month + 1
        next_opex = _third_friday(ny, nm)
    days_to = (next_opex - today).days
    last_opex = this_opex
    if today < this_opex:
        py = today.year - (1 if today.month == 1 else 0)
        pm = 12 if today.month == 1 else today.month - 1
        last_opex = _third_friday(py, pm)
    return {
        "next_opex": next_opex.isoformat(),
        "days_to_opex": days_to,
        "pre_opex_week": bool(0 <= days_to <= 6 and today.weekday() < 5),
        "post_opex_monday": bool(today.weekday() == 0 and 0 <= (today - last_opex).days <= 3),
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

    vix_term = _vix_term()
    opex = _opex_state()
    try:
        from src.catalyst import breadth_alpaca
        breadth = breadth_alpaca.compute_breadth()
    except Exception as e:
        breadth = {"available": False, "reason": f"breadth error: {type(e).__name__}"}

    breadth_warning = False
    if regime == "B" and breadth.get("available") and breadth.get("breadth_state") == "narrow":
        regime, bias, directions = "C", "NEUTRAL", []
        pct = breadth.get("pct_above_50d") or 0
        reason = f"narrow breadth ({pct*100:.0f}% of SP500 > 50d SMA) -> SPX up-move is a narrow fake-out, suppress"
        breadth_warning = True

    opex_suppress = bool(opex.get("pre_opex_week") and regime in ("A", "B"))
    if opex_suppress:
        reason = f"{reason} | pre-OpEx week (heavy-gamma chop) -> directional suppressed"

    state = {
        "regime": regime,
        "bias": bias,
        "allowed_directions": directions,
        "directional_locked": regime == "C" or opex_suppress,
        "spx": spx,
        "yen": yen,
        "vix_term": vix_term,
        "breadth": breadth,
        "opex": opex,
        "breadth_warning": breadth_warning,
        "backspread_unlock": bool(vix_term.get("backwardation")),
        "post_opex_unlock": bool(opex.get("post_opex_monday")),
        "opex_suppress": opex_suppress,
        "reason": reason,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }

    if verbose:
        z = spx["zone"] if spx else "n/a"
        print(f"  regime_compass: REGIME {regime} ({bias}) | SPX {z} | yen {yen.get('slope_dir')} "
              f"| VIX {vix_term.get('structure')} | breadth {breadth.get('breadth_state')} "
              f"| OpEx in {opex.get('days_to_opex')}d")
        print(f"  regime_compass: {reason}")

    return state


def direction_allowed(side, state=None):
    if state is None:
        state = evaluate()
    side = (side or "").upper()
    if state.get("directional_locked"):
        return False
    if state["bias"] == "SHORT":
        return side in ("PUT", "SHORT", "BEARISH")
    if state["bias"] == "LONG":
        return side in ("CALL", "LONG", "BULLISH")
    return False


if __name__ == "__main__":
    evaluate(verbose=True)

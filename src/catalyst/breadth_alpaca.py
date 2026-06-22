import os
import json
import pathlib
from datetime import datetime, timedelta

from src.alpaca_creds import working_creds


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
UNIVERSE_PATH = PROJECT_ROOT / "data" / "universe" / "universe.json"
CACHE_PATH = PROJECT_ROOT / "data" / "ambush_logs" / "breadth_cache.json"
BATCH = 200


def _today():
    return datetime.utcnow().date().isoformat()


def _sp500():
    try:
        with open(UNIVERSE_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return [(r.get("ticker") or "").split(".")[0] for r in rows if (r.get("index") or "").upper() == "SP500"]
    except Exception:
        return []


def _sma(values, n):
    return sum(values[-n:]) / n if len(values) >= n else None


def _load_cache():
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _state(pct):
    if pct is None:
        return "unknown"
    if pct >= 0.55:
        return "broad"
    if pct >= 0.40:
        return "mixed"
    return "narrow"


def compute_breadth(force=False):
    cache = _load_cache()
    if not force and cache.get("date") == _today() and cache.get("data"):
        return cache["data"]

    creds = working_creds()
    if not creds:
        return {"available": False, "reason": "no working alpaca credentials"}
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
    except Exception:
        return {"available": False, "reason": "alpaca-py unavailable"}

    tickers = _sp500()
    if not tickers:
        return {"available": False, "reason": "no SP500 universe"}

    client = StockHistoricalDataClient(creds[0], creds[1])
    start = (datetime.utcnow().date() - timedelta(days=110)).isoformat()
    above_50 = 0
    counted = 0
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        try:
            req = StockBarsRequest(symbol_or_symbols=batch, timeframe=TimeFrame.Day, start=start, feed=DataFeed.IEX)
            data = client.get_stock_bars(req).data
        except Exception:
            continue
        for sym, series in data.items():
            closes = [b.close for b in series if b.close is not None]
            ma50 = _sma(closes, 50)
            if ma50 is None or not closes:
                continue
            counted += 1
            if closes[-1] > ma50:
                above_50 += 1

    if counted == 0:
        return {"available": False, "reason": "no bars returned"}
    pct = above_50 / counted
    out = {
        "available": True,
        "pct_above_50d": round(pct, 3),
        "counted": counted,
        "breadth_state": _state(pct),
    }
    _save_cache({"date": _today(), "data": out})
    return out

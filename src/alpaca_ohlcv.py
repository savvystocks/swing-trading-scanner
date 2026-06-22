import os
import json
import hashlib
import pathlib
import time
import logging
from datetime import datetime, timedelta

from src.alpaca_creds import working_creds, is_auth_error

logger = logging.getLogger(__name__)

CACHE_DIR = pathlib.Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_SECONDS = 24 * 3600

IEX_TO_CONSOLIDATED_VOLUME_MULTIPLIER = 33.0


def _cache_path(symbol, from_date, to_date):
    key = hashlib.md5(f"alpaca-ohlcv|{symbol}|{from_date}|{to_date}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _normalize_alpaca_symbol(symbol):
    """Alpaca uses dot for class shares (BRK.B), not dash (BRK-B)."""
    if not symbol:
        return symbol
    if "-" in symbol and len(symbol) <= 6:
        # BRK-B / BF-B / MOG-A / HEI-A style
        return symbol.replace("-", ".")
    return symbol


def get_daily_bars_eodhd_format(symbol, from_date=None, to_date=None):
    creds = working_creds()
    if not creds:
        return None
    api_key, api_secret = creds

    symbol = _normalize_alpaca_symbol(symbol)
    cache = _cache_path(symbol, from_date, to_date)
    if cache.exists():
        age = time.time() - cache.stat().st_mtime
        if age < CACHE_SECONDS:
            try:
                cached = json.loads(cache.read_text())
                if isinstance(cached, list):
                    return cached
            except Exception:
                pass

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
    except ImportError:
        return None

    result = None
    for attempt in range(3):
        try:
            client = StockHistoricalDataClient(api_key, api_secret)
            if from_date:
                start = datetime.strptime(from_date, "%Y-%m-%d")
            else:
                start = datetime.utcnow() - timedelta(days=420)
            if to_date:
                end = datetime.strptime(to_date, "%Y-%m-%d")
            else:
                end = datetime.utcnow()
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed=DataFeed.IEX,
            )
            result = client.get_stock_bars(req).data.get(symbol, [])
            break
        except Exception as e:
            es = str(e).lower()
            if is_auth_error(e):
                logger.warning(f"Alpaca auth rejected for {symbol} (check ALPACA_API_KEY / paper keys)")
                return None
            rate_limited = "429" in es or "too many" in es or "rate limit" in es or "html" in es
            if rate_limited and attempt < 2:
                logger.warning(f"Alpaca rate-limit on {symbol} (attempt {attempt + 1}/3), backing off")
                time.sleep(0.8 * (2 ** attempt))
                continue
            logger.warning(f"Alpaca OHLCV fetch for {symbol}: {type(e).__name__}: {str(e)[:80]}")
            return None

    if not result:
        return None

    out = []
    for b in result:
        try:
            out.append({
                "date": b.timestamp.strftime("%Y-%m-%d"),
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "adjusted_close": float(b.close),
                "volume": int(float(b.volume) * IEX_TO_CONSOLIDATED_VOLUME_MULTIPLIER),
            })
        except Exception:
            continue

    if not out:
        return None

    try:
        cache.write_text(json.dumps(out))
    except Exception:
        pass

    return out

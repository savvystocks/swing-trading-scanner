import os
import json
import pathlib
from datetime import datetime


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
UNIVERSE_PATH = PROJECT_ROOT / "data" / "universe" / "universe.json"
COOLDOWN_PATH = PROJECT_ROOT / "data" / "ambush_logs" / "alert_cooldown.json"
EARNINGS_CACHE_PATH = PROJECT_ROOT / "data" / "ambush_logs" / "event_cache.json"

CRYPTO_PROXIES = {
    "MSTR", "COIN", "MARA", "RIOT", "CLSK", "BTDR", "BITF", "HUT", "WULF", "CIFR", "IREN", "HOOD",
}

_UNIVERSE_CACHE = {"set": None}


def _allowed_indices():
    raw = os.environ.get("SCAN_ALLOWED_INDICES", "SP500")
    return {x.strip().upper() for x in raw.split(",") if x.strip()}


def _base(ticker):
    return (ticker or "").upper().split(".")[0]


def load_universe(allowed_indices=None):
    if _UNIVERSE_CACHE["set"] is not None and allowed_indices is None:
        return _UNIVERSE_CACHE["set"]
    allowed = allowed_indices or _allowed_indices()
    tickers = set(CRYPTO_PROXIES)
    try:
        with open(UNIVERSE_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
        for r in rows:
            if (r.get("index") or "").upper() in allowed:
                tickers.add(_base(r.get("ticker")))
    except Exception:
        pass
    if allowed_indices is None:
        _UNIVERSE_CACHE["set"] = tickers
    return tickers


def in_universe(ticker, universe=None):
    if universe is None:
        universe = load_universe()
    return _base(ticker) in universe


def event_blackout(candidate, max_days=7):
    e = candidate.get("earnings_in_days")
    x = candidate.get("exdiv_in_days")
    reasons = []
    if e is not None and 0 <= e <= max_days:
        reasons.append(f"earnings in {e}d")
    if x is not None and 0 <= x <= max_days:
        reasons.append(f"ex-div in {x}d")
    return {
        "blackout": bool(reasons),
        "reasons": reasons,
        "checked": e is not None or x is not None,
    }


def _load_json(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _today():
    return datetime.utcnow().date().isoformat()


def earnings_exdiv_days(ticker, fundamentals=None):
    cache = _load_json(EARNINGS_CACHE_PATH)
    day = _today()
    key = _base(ticker)
    if cache.get("day") == day and key in cache.get("tickers", {}):
        return cache["tickers"][key]

    earnings_in = None
    exdiv_in = None
    ok = False
    try:
        import yfinance as yf
        cal = yf.Ticker(key).calendar or {}
        if cal:
            today = datetime.utcnow().date()
            ed = cal.get("Earnings Date")
            if isinstance(ed, (list, tuple)):
                ed = ed[0] if ed else None
            if ed is not None:
                ed = ed if hasattr(ed, "year") else datetime.strptime(str(ed)[:10], "%Y-%m-%d").date()
                d = (ed - today).days
                if d >= 0:
                    earnings_in = d
            xd = cal.get("Ex-Dividend Date")
            if xd is not None:
                xd = xd if hasattr(xd, "year") else datetime.strptime(str(xd)[:10], "%Y-%m-%d").date()
                d = (xd - today).days
                if d >= 0:
                    exdiv_in = d
            ok = True
    except Exception:
        pass

    result = {"earnings_in_days": earnings_in, "exdiv_in_days": exdiv_in}
    if ok:
        if cache.get("day") != day:
            cache = {"day": day, "tickers": {}}
        cache.setdefault("tickers", {})[key] = result
        _save_json(EARNINGS_CACHE_PATH, cache)
    return result


def load_cooldown():
    return _load_json(COOLDOWN_PATH)


def already_alerted(ticker, cache=None):
    if cache is None:
        cache = load_cooldown()
    return _base(ticker) in set(cache.get(_today(), []))


def mark_alerted(ticker):
    day = _today()
    cache = load_cooldown()
    todays = cache.get(day, [])
    t = _base(ticker)
    if t not in todays:
        todays.append(t)
    _save_json(COOLDOWN_PATH, {day: todays})
    return todays

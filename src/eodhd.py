import os
import time
import json
import hashlib
import pathlib
import requests

BASE = "https://eodhd.com/api"
CACHE_DIR = pathlib.Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class EODHDClient:
    def __init__(self, api_key=None, cache_hours=24):
        self.api_key = api_key or os.environ["EODHD_API_KEY"]
        self.cache_seconds = cache_hours * 3600
        self.session = requests.Session()
        self.calls_made = 0

    def _cache_path(self, path, params):
        key = hashlib.md5(f"{path}|{json.dumps(params, sort_keys=True)}".encode()).hexdigest()
        return CACHE_DIR / f"{key}.json"

    def _get(self, path, params=None, use_cache=True):
        params = dict(params or {})
        cache_file = self._cache_path(path, params)

        if use_cache and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < self.cache_seconds:
                return json.loads(cache_file.read_text())

        params["api_token"] = self.api_key
        params.setdefault("fmt", "json")

        for attempt in range(3):
            try:
                r = self.session.get(f"{BASE}{path}", params=params, timeout=30)
                self.calls_made += 1
                if r.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                data = r.json()
                cache_file.write_text(json.dumps(data))
                return data
            except requests.HTTPError as e:
                if r.status_code in (404,):
                    return None
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def ohlcv(self, ticker, from_date=None, to_date=None):
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return self._get(f"/eod/{ticker}", params)

    def fundamentals(self, ticker):
        return self._get(f"/fundamentals/{ticker}")

    def insider_transactions(self, ticker, limit=50):
        return self._get("/insider-transactions", {"code": ticker, "limit": limit})

    def earnings_calendar(self, from_date, to_date):
        return self._get("/calendar/earnings", {"from": from_date, "to": to_date})

    def economic_events(self, from_date, to_date, country=None, limit=100):
        params = {"from": from_date, "to": to_date, "limit": limit}
        if country:
            params["country"] = country
        return self._get("/economic-events", params)

    def news(self, ticker, limit=20):
        return self._get("/news", {"s": ticker, "limit": limit})

    def exchange_tickers(self, exchange_code):
        return self._get(f"/exchange-symbol-list/{exchange_code}")

    def clear_cache(self):
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()

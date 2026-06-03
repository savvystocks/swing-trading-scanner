"""Unusual Whales API Client.

Replaces the EODHD-based wide-universe scan with a flow-driven pipeline.
The educator's 6 institutional signals all live here:
  - Options flow (sweeps, blocks)
  - 0DTE flow
  - IV surface (per-strike IV via Greeks endpoint)
  - Net gamma exposure (GEX)
  - Open interest
  - Vanna / Charm exposure (the "Venaflow"-class signals)

Token: UNUSUAL_WHALES_TOKEN env var. Already referenced in workflow yaml.
Without token, every method returns None gracefully so the scanner keeps
working off the positioning stack alone.

Auth: Bearer token in Authorization header.
Base: https://api.unusualwhales.com
"""

import os
import json
import time
import hashlib
import pathlib
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)

API_BASE = "https://api.unusualwhales.com/api"
CACHE_DIR = pathlib.Path(__file__).parent.parent / "data" / "cache_uw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Short cache for flow data (refreshed often), longer for chain/GEX
CACHE_TTL_SECONDS = {
    "flow_alerts": 300,
    "flow_recent": 300,
    "contract_screener": 300,
    "darkpool_recent": 600,
    "darkpool_ticker": 600,
    "greek_exposure": 900,
    "spot_exposures": 60,
    "option_chains": 600,
    "greeks": 600,
    "iv_rank": 3600,
    "interpolated_iv": 1800,
    "oi_change": 1800,
    "oi_per_strike": 1800,
    "max_pain": 1800,
}


class UnusualWhalesClient:
    def __init__(self, token=None, verbose=False):
        self.token = token or os.environ.get("UNUSUAL_WHALES_TOKEN", "")
        self.verbose = verbose
        self.calls_made = 0
        self.cache_hits = 0

    @property
    def enabled(self):
        return bool(self.token)

    def _cache_key(self, path, params):
        raw = f"uw|{path}|{json.dumps(params or {}, sort_keys=True)}"
        return CACHE_DIR / f"{hashlib.md5(raw.encode()).hexdigest()}.json"

    def _read_cache(self, path_key, ttl_seconds, cache_path):
        if not cache_path.exists():
            return None
        age = time.time() - cache_path.stat().st_mtime
        if age > ttl_seconds:
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                self.cache_hits += 1
                return json.load(f)
        except Exception:
            return None

    def _write_cache(self, cache_path, data):
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _request(self, path, params=None, cache_key=None, ttl=300):
        if not self.enabled:
            return None
        cache_path = self._cache_key(path, params)
        cached = self._read_cache(cache_key, ttl, cache_path)
        if cached is not None:
            return cached

        try:
            import requests
        except ImportError:
            logger.debug("requests not available")
            return None

        url = f"{API_BASE}{path}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        try:
            r = requests.get(url, headers=headers, params=params or {}, timeout=20)
            self.calls_made += 1
            if r.status_code != 200:
                if self.verbose:
                    logger.debug(f"UW {path}: HTTP {r.status_code}")
                return None
            data = r.json()
            self._write_cache(cache_path, data)
            return data
        except Exception as e:
            if self.verbose:
                logger.debug(f"UW {path} failed: {type(e).__name__}: {e}")
            return None

    # === FLOW ===

    def flow_alerts(self, ticker=None, limit=100, is_otm=None, min_premium=None):
        """Real-time unusual option flow alerts. ticker=None for whole market."""
        params = {"limit": limit}
        if is_otm is not None:
            params["is_otm"] = str(is_otm).lower()
        if min_premium is not None:
            params["min_premium"] = min_premium
        if ticker:
            path = f"/stock/{ticker}/flow-alerts"
        else:
            path = "/option-trades/flow-alerts"
        return self._request(path, params, cache_key="flow_alerts", ttl=CACHE_TTL_SECONDS["flow_alerts"])

    def flow_recent(self, ticker, limit=50):
        """Latest option flow per ticker."""
        return self._request(f"/stock/{ticker}/flow-recent", {"limit": limit},
                            cache_key="flow_recent", ttl=CACHE_TTL_SECONDS["flow_recent"])

    def contract_screener(self, sort_by="premium", limit=50, side=None, expiry_min_days=None):
        """Hottest option contracts by flow metrics. Used as universe builder."""
        params = {"limit": limit}
        if sort_by:
            params["order"] = sort_by
        if side in ("call", "put"):
            params["option_type"] = side
        if expiry_min_days:
            params["min_days_to_expiry"] = expiry_min_days
        return self._request("/screener/option-contracts", params,
                            cache_key="contract_screener", ttl=CACHE_TTL_SECONDS["contract_screener"])

    # === GREEK EXPOSURE ===

    def greek_exposure(self, ticker, date=None):
        """Net aggregate GEX/DEX/Vanna/Charm for ticker."""
        params = {"date": date} if date else None
        return self._request(f"/stock/{ticker}/greek-exposure", params,
                            cache_key="greek_exposure", ttl=CACHE_TTL_SECONDS["greek_exposure"])

    def greek_exposure_by_strike(self, ticker, date=None):
        """GEX distributed across strikes. Find gamma walls + zero-gamma flip."""
        params = {"date": date} if date else None
        return self._request(f"/stock/{ticker}/greek-exposure/strike", params,
                            cache_key="greek_exposure", ttl=CACHE_TTL_SECONDS["greek_exposure"])

    def greek_exposure_by_expiry(self, ticker, date=None):
        """GEX distributed by expiry. Identify 0DTE concentration."""
        params = {"date": date} if date else None
        return self._request(f"/stock/{ticker}/greek-exposure/expiry", params,
                            cache_key="greek_exposure", ttl=CACHE_TTL_SECONDS["greek_exposure"])

    def spot_exposures(self, ticker):
        """1-minute spot GEX snapshots. Real-time dealer positioning."""
        return self._request(f"/stock/{ticker}/spot-exposures/one-minute", None,
                            cache_key="spot_exposures", ttl=CACHE_TTL_SECONDS["spot_exposures"])

    # === OPTION CHAINS / IV / GREEKS ===

    def option_chains(self, ticker):
        """Full option chain with IV + Greeks per contract."""
        return self._request(f"/stock/{ticker}/option-chains", None,
                            cache_key="option_chains", ttl=CACHE_TTL_SECONDS["option_chains"])

    def greeks(self, ticker, expiry=None):
        """Per-contract greeks."""
        params = {"expiry": expiry} if expiry else None
        return self._request(f"/stock/{ticker}/greeks", params,
                            cache_key="greeks", ttl=CACHE_TTL_SECONDS["greeks"])

    def iv_rank(self, ticker):
        """IV rank percentile."""
        return self._request(f"/stock/{ticker}/iv-rank", None,
                            cache_key="iv_rank", ttl=CACHE_TTL_SECONDS["iv_rank"])

    def interpolated_iv(self, ticker, expiry):
        """Interpolated IV at a specific expiry."""
        return self._request(f"/stock/{ticker}/interpolated-iv", {"expiry": expiry},
                            cache_key="interpolated_iv", ttl=CACHE_TTL_SECONDS["interpolated_iv"])

    def iv_term_structure(self, ticker):
        """IV term structure across expiries (the IV surface)."""
        return self._request(f"/stock/{ticker}/implied-volatility-term-structure", None,
                            cache_key="interpolated_iv", ttl=CACHE_TTL_SECONDS["interpolated_iv"])

    # === OPEN INTEREST ===

    def oi_change(self, ticker):
        """OI changes day-over-day."""
        return self._request(f"/stock/{ticker}/oi-change", None,
                            cache_key="oi_change", ttl=CACHE_TTL_SECONDS["oi_change"])

    def oi_per_strike(self, ticker, expiry=None):
        """OI distributed across strikes. Find gravity wells."""
        params = {"expiry": expiry} if expiry else None
        return self._request(f"/stock/{ticker}/oi-per-strike", params,
                            cache_key="oi_per_strike", ttl=CACHE_TTL_SECONDS["oi_per_strike"])

    def max_pain(self, ticker, expiry=None):
        """Max pain strike for expiry."""
        params = {"expiry": expiry} if expiry else None
        return self._request(f"/stock/{ticker}/max-pain", params,
                            cache_key="max_pain", ttl=CACHE_TTL_SECONDS["max_pain"])

    # === DARK POOL ===

    def darkpool_recent(self, limit=50):
        return self._request("/darkpool/recent", {"limit": limit},
                            cache_key="darkpool_recent", ttl=CACHE_TTL_SECONDS["darkpool_recent"])

    def darkpool_ticker(self, ticker, limit=50):
        return self._request(f"/darkpool/{ticker}", {"limit": limit},
                            cache_key="darkpool_ticker", ttl=CACHE_TTL_SECONDS["darkpool_ticker"])

    # === PROPRIETARY METRICS (NOPE, market tide, etc.) ===

    def nope(self, ticker):
        """Net Option Position Effect - dealer-induced delta pressure on stock."""
        return self._request(f"/stock/{ticker}/nope", None,
                            cache_key="oi_change", ttl=300)

    def net_prem_ticks(self, ticker):
        """Net premium tick-by-tick (live flow direction)."""
        return self._request(f"/stock/{ticker}/net-prem-ticks", None,
                            cache_key="flow_recent", ttl=300)

    def market_tide(self):
        """Overall market flow direction (real-time)."""
        return self._request("/market/market-tide", None,
                            cache_key="darkpool_recent", ttl=300)

    def etf_tide(self):
        """Sector ETF flow direction."""
        return self._request("/market/etf-tide", None,
                            cache_key="darkpool_recent", ttl=300)

    def historical_risk_reversal_skew(self, ticker):
        """25-delta skew dynamics over time."""
        return self._request(f"/stock/{ticker}/historical-risk-reversal-skew", None,
                            cache_key="iv_rank", ttl=1800)

    # === SMART MONEY ===

    def congress_recent_trades(self, limit=50):
        return self._request("/congress/recent-trades", {"limit": limit},
                            cache_key="oi_change", ttl=3600)

    def institution_activity(self, ticker):
        return self._request(f"/institution/activity", {"ticker": ticker},
                            cache_key="oi_change", ttl=3600)

    def insider_ticker_flow(self, ticker):
        return self._request(f"/insiders/ticker-flow", {"ticker": ticker},
                            cache_key="oi_change", ttl=3600)

    # === EARNINGS ===

    def earnings_premarket(self):
        return self._request("/earnings/premarket", None,
                            cache_key="oi_change", ttl=1800)

    def earnings_afterhours(self):
        return self._request("/earnings/afterhours", None,
                            cache_key="oi_change", ttl=1800)

    def earnings_ticker(self, ticker):
        return self._request(f"/earnings/{ticker}", None,
                            cache_key="oi_change", ttl=3600)

    def earnings_estimates(self, ticker):
        return self._request(f"/companies/earnings-estimates", {"ticker": ticker},
                            cache_key="iv_rank", ttl=3600)

    # === STOCK INFO (replaces EODHD fundamentals) ===

    def stock_info(self, ticker):
        return self._request(f"/stock/{ticker}/info", None,
                            cache_key="oi_per_strike", ttl=3600)

    def stock_ohlc(self, ticker, candle_size="1d"):
        return self._request(f"/stock/{ticker}/ohlc/{candle_size}", None,
                            cache_key="oi_per_strike", ttl=1800)

    # === NEWS ===

    def news_headlines(self, ticker=None, limit=50):
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        return self._request("/news/headlines", params,
                            cache_key="flow_alerts", ttl=300)


# Module-level singleton
_CLIENT = None


def get_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = UnusualWhalesClient()
    return _CLIENT

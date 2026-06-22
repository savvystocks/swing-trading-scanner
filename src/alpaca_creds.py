import os
import logging
import urllib.request

logger = logging.getLogger(__name__)

_WORKING = None
_PROBED = False


def _pairs():
    seen = set()
    out = []
    for kk, sk in (("ALPACA_API_KEY", "ALPACA_SECRET_KEY"),
                   ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_SECRET_KEY")):
        k = (os.environ.get(kk) or "").strip()
        s = (os.environ.get(sk) or "").strip()
        if k and s and (k, s) not in seen:
            seen.add((k, s))
            out.append((k, s))
    return out


def _probe(k, s):
    url = "https://data.alpaca.markets/v2/stocks/SPY/trades/latest?feed=iex"
    req = urllib.request.Request(url, headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return None


def working_creds():
    global _WORKING, _PROBED
    if _WORKING:
        return _WORKING
    pairs = _pairs()
    if not pairs:
        return None
    if _PROBED:
        return _WORKING
    network_seen = False
    for k, s in pairs:
        ok = _probe(k, s)
        if ok:
            _WORKING = (k, s)
            _PROBED = True
            return _WORKING
        if ok is False:
            network_seen = True
            logger.warning("Alpaca creds %s..%s rejected (401) - trying fallback", k[:4], k[-2:])
    if network_seen:
        _PROBED = True
        return None
    return pairs[0]


def is_auth_error(exc):
    es = str(exc).lower()
    return ("401" in es or "403" in es or "unauthorized" in es
            or "authorization required" in es or "forbidden" in es)


def reset():
    global _WORKING, _PROBED
    _WORKING = None
    _PROBED = False

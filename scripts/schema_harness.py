import os
import sys
import json
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS = []


def add(name, status, detail):
    RESULTS.append((name, status, detail))


def check_keys(name, present, expected):
    missing = [k for k in expected if k not in present]
    if missing:
        add(name, "DRIFT", f"missing {missing} | present sample: {sorted(present)[:10]}")
    else:
        add(name, "OK", f"{len(expected)} expected keys present")


def _telegram(msg):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=15)
    except Exception:
        pass


def check_uw():
    from src.unusual_whales_api import UnusualWhalesClient
    uw = UnusualWhalesClient()
    if not getattr(uw, "enabled", False):
        add("unusual_whales", "UNREACHABLE", "UNUSUAL_WHALES_TOKEN unset / client disabled")
        return
    probe, occ = "NVDA", None  # fixed liquid equity for ticker-based endpoints
    fa = uw.flow_alerts(limit=20, min_premium=500000) or {}
    rows = fa.get("data") or []
    if rows:
        check_keys("uw.flow_alerts", set(rows[0].keys()),
                   ["ticker", "underlying_price", "total_premium", "type", "option_chain",
                    "volume", "open_interest", "strike", "expiry"])
        occ = rows[0].get("option_chain") or rows[0].get("option_symbol")
    else:
        add("uw.flow_alerts", "EMPTY", "no alerts (market closed?)")

    g = uw.greek_exposure_by_strike(probe) or {}
    grows = g.get("data") or []
    if grows:
        check_keys("uw.greek_exposure_by_strike", set(grows[0].keys()), ["strike", "call_gex", "put_gex"])
    else:
        add("uw.greek_exposure_by_strike", "EMPTY", f"no data for {probe}")

    ga = uw.greek_exposure(probe) or {}
    garows = ga.get("data") or []
    if garows:
        check_keys("uw.greek_exposure(agg)", set(garows[0].keys()), ["call_gamma", "put_gamma"])
    else:
        add("uw.greek_exposure(agg)", "EMPTY", f"no data for {probe}")

    dp = uw.darkpool_ticker(probe) or {}
    dprows = dp.get("data") or []
    if dprows:
        check_keys("uw.darkpool_ticker", set(dprows[0].keys()), ["price", "size"])
    else:
        add("uw.darkpool_ticker", "EMPTY", f"no prints for {probe}")

    ir = uw.iv_rank(probe) or {}
    irows = ir.get("data") or []
    if irows:
        check_keys("uw.iv_rank", set(irows[0].keys()), ["date", "iv_rank_1y"])
    else:
        add("uw.iv_rank", "EMPTY", f"no data for {probe}")

    # the RVOL bug endpoint: top-level MUST be 'chains', not 'data'
    if occ:
        h = uw.option_contract_historic(occ) or {}
        if "chains" in h:
            hrows = h.get("chains") or []
            if hrows:
                # the RVOL feed only consumes 'volume' off each chain row; date/open_interest confirm shape
                check_keys("uw.option_contract_historic.chains", set(hrows[0].keys()),
                           ["date", "volume", "open_interest"])
            else:
                add("uw.option_contract_historic.chains", "EMPTY", f"chains empty for {occ}")
        else:
            add("uw.option_contract_historic", "DRIFT",
                f"top-level 'chains' key GONE (RVOL feed) - has {list(h.keys())}")
    else:
        add("uw.option_contract_historic", "SKIP", "no OCC available to probe")


def check_yahoo():
    def closes(sym):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        return d["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    for sym, label in (("%5EVIX", "yahoo.VIX"), ("%5EVIX3M", "yahoo.VIX3M"), ("JPY=X", "yahoo.USDJPY")):
        try:
            cl = closes(sym)
            add(label, "OK" if cl else "EMPTY",
                "chart.result[0].indicators.quote[0].close present" if cl else "empty series")
        except Exception as e:
            add(label, "DRIFT", f"close path broke: {type(e).__name__}: {str(e)[:60]}")


def check_yfinance():
    try:
        import yfinance as yf
        cal = yf.Ticker("AAPL").calendar or {}
        if cal:
            check_keys("yfinance.calendar", set(cal.keys()), ["Earnings Date", "Ex-Dividend Date"])
        else:
            add("yfinance.calendar", "EMPTY", "empty calendar (rate-limited / blocked?)")
    except Exception as e:
        add("yfinance.calendar", "UNREACHABLE", f"{type(e).__name__}")


def check_alpaca():
    try:
        from src.alpaca_creds import working_creds
        creds = working_creds()
        if not creds:
            add("alpaca", "UNREACHABLE", "no working creds")
            return
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        import datetime as dt
        sc = StockHistoricalDataClient(creds[0], creds[1])
        bars = sc.get_stock_bars(StockBarsRequest(
            symbol_or_symbols="SPY", timeframe=TimeFrame.Day,
            start=dt.datetime(2026, 6, 1), feed=DataFeed.IEX)).data.get("SPY", [])
        if bars:
            missing = [a for a in ("open", "high", "low", "close", "volume", "timestamp") if not hasattr(bars[-1], a)]
            add("alpaca.bars", "DRIFT" if missing else "OK",
                f"missing attrs {missing}" if missing else "OHLCV attributes present")
        else:
            add("alpaca.bars", "EMPTY", "no bars returned")
    except Exception as e:
        add("alpaca.bars", "UNREACHABLE", f"{type(e).__name__}: {str(e)[:60]}")


def main():
    for fn in (check_uw, check_yahoo, check_yfinance, check_alpaca):
        try:
            fn()
        except Exception as e:
            add(fn.__name__, "ERROR", f"{type(e).__name__}: {str(e)[:80]}")

    drift = [r for r in RESULTS if r[1] in ("DRIFT", "ERROR")]
    print("=" * 66)
    print("V9 PROVIDER SCHEMA HARNESS")
    print("=" * 66)
    for name, status, detail in RESULTS:
        print(f"  [{status:<11}] {name}: {detail}")
    print(f"\n{len(drift)} drift/error / {len(RESULTS)} checks")

    if drift:
        msg = "⚠️ V9 SCHEMA DRIFT - a provider changed its payload:\n" + \
              "\n".join(f"- {n}: {d}" for n, _, d in drift)
        _telegram(msg)
        sys.exit(1)
    print("all provider schemas match expected keys")
    sys.exit(0)


if __name__ == "__main__":
    main()

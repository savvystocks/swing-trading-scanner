import os
from datetime import datetime, timezone


def fetch_premarket_movers(symbols, threshold_pct=3.0):
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        return [], "no Alpaca keys"
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
    except ImportError:
        return [], "alpaca-py not importable"

    if not symbols:
        return [], "no symbols"
    symbols = list({s.replace(".US", "") for s in symbols if s})

    try:
        sc = StockHistoricalDataClient(api_key, api_secret)
        trades = sc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbols))
        quotes = sc.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbols))
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:200]}"

    out = []
    if not isinstance(trades, dict):
        return [], "unexpected trades format"

    for sym, trade in trades.items():
        try:
            price = float(trade.price) if trade.price else 0
            if price <= 0:
                continue
            ts = trade.timestamp
            session = _classify_session(ts)
            quote = quotes.get(sym) if isinstance(quotes, dict) else None
            bid = float(quote.bid_price) if quote and quote.bid_price else None
            ask = float(quote.ask_price) if quote and quote.ask_price else None
            out.append({
                "symbol": sym,
                "price": price,
                "timestamp": str(ts) if ts else None,
                "session": session,
                "bid": bid,
                "ask": ask,
            })
        except Exception:
            continue
    return out, None


def _classify_session(ts):
    if not ts:
        return "unknown"
    try:
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        et_offset = -4
        utc_hour = ts.hour + ts.minute / 60
        et_hour = (utc_hour + et_offset) % 24
        if 4.0 <= et_hour < 9.5:
            return "pre-market"
        elif 9.5 <= et_hour < 16.0:
            return "regular"
        elif 16.0 <= et_hour < 20.0:
            return "after-hours"
        else:
            return "closed"
    except Exception:
        return "unknown"


def detect_premarket_spikes(scored_results, prev_close_lookup, min_spike_pct=3.0, min_volume_x=1.5):
    spikes = []
    symbols = [s.get("ticker", "").replace(".US", "") for s in scored_results if s.get("ticker")]
    movers, err = fetch_premarket_movers(symbols)
    if err:
        return [], err
    for m in movers:
        if m["session"] != "pre-market":
            continue
        prev_close = prev_close_lookup.get(m["symbol"])
        if not prev_close:
            continue
        delta_pct = (m["price"] - prev_close) / prev_close * 100
        if abs(delta_pct) >= min_spike_pct:
            spikes.append({
                "ticker": m["symbol"],
                "premarket_price": m["price"],
                "prev_close": prev_close,
                "change_pct": round(delta_pct, 2),
                "session": m["session"],
                "direction": "UP" if delta_pct > 0 else "DOWN",
            })
    spikes.sort(key=lambda s: abs(s["change_pct"]), reverse=True)
    return spikes, None

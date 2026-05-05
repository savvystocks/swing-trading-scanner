import os
from datetime import datetime, timezone


def _classify_session(ts_utc):
    if not ts_utc:
        return "unknown", None
    try:
        if isinstance(ts_utc, str):
            ts_utc = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        et_offset_hours = -4
        et_dt = ts_utc.astimezone(timezone.utc)
        utc_hour = et_dt.hour + et_dt.minute / 60
        et_hour = (utc_hour + et_offset_hours) % 24
        age_min = (datetime.now(timezone.utc) - ts_utc).total_seconds() / 60
        if 4.0 <= et_hour < 9.5:
            session = "pre-market"
        elif 9.5 <= et_hour < 16.0:
            session = "regular"
        elif 16.0 <= et_hour < 20.0:
            session = "after-hours"
        else:
            session = "closed"
        return session, round(age_min, 1)
    except Exception:
        return "unknown", None


def enrich_with_live_spots(tickets, verbose=True):
    if not tickets:
        return
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        if verbose:
            print("  live_spot: ALPACA keys missing - skipping enrichment")
        return

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
    except ImportError:
        if verbose:
            print("  live_spot: alpaca-py not installed - skipping")
        return

    sc = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])

    us_tickets = []
    for t in tickets:
        tk = t.get("ticker", "")
        if not tk or not t.get("price"):
            continue
        if tk.endswith(".US"):
            us_tickets.append(t)
        elif "." not in tk and tk.replace("-", "").replace(".", "").isalnum():
            us_tickets.append(t)
    if not us_tickets:
        if verbose:
            print("  live_spot: no US tickets to enrich")
        return

    symbols = list({t["ticker"].replace(".US", "") for t in us_tickets})
    try:
        trades = sc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbols))
        quotes = sc.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbols))
    except Exception as e:
        if verbose:
            print(f"  live_spot: batch fetch failed: {type(e).__name__}: {str(e)[:120]}")
        return

    live_map = {}
    if isinstance(trades, dict):
        for sym, trade in trades.items():
            try:
                rec = {"price": float(trade.price), "trade_time": trade.timestamp}
                if isinstance(quotes, dict):
                    q = quotes.get(sym)
                    if q:
                        rec["bid"] = float(q.bid_price) if q.bid_price else None
                        rec["ask"] = float(q.ask_price) if q.ask_price else None
                live_map[sym] = rec
            except (AttributeError, ValueError, TypeError):
                pass

    enriched = 0
    big_movers = 0
    pre_market_count = 0
    stale_count = 0
    for t in us_tickets:
        sym = t["ticker"].replace(".US", "")
        rec = live_map.get(sym)
        if not rec or rec["price"] <= 0:
            continue
        live = rec["price"]
        close = t.get("price")
        if not close or close <= 0:
            continue
        session, age_min = _classify_session(rec.get("trade_time"))
        if session == "pre-market":
            pre_market_count += 1
        if age_min and age_min > 60:
            stale_count += 1
        delta_pct = (live / close - 1) * 100
        delta_usd = live - close
        t["live_spot"] = live
        t["live_change_pct"] = delta_pct
        t["live_change_usd"] = delta_usd
        t["live_bid"] = rec.get("bid")
        t["live_ask"] = rec.get("ask")
        t["live_session"] = session
        t["live_age_min"] = age_min
        ot = t.get("options_trade")
        if ot and ot.get("strike"):
            new_breakeven_pct = (ot["breakeven"] - live) / live * 100 if live > 0 else None
            ot["breakeven_pct_from_live"] = round(new_breakeven_pct, 2) if new_breakeven_pct is not None else None
            ot["live_underlying"] = live
        if abs(delta_pct) >= 3:
            big_movers += 1
        enriched += 1

    if verbose:
        sessions_msg = f"({pre_market_count} pre-market, {stale_count} stale >60min)" if (pre_market_count or stale_count) else ""
        print(f"  live_spot: enriched {enriched}/{len(us_tickets)} US tickets ({big_movers} moved 3%+) {sessions_msg}")

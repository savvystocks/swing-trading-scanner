import os


def enrich_with_live_spots(tickets, verbose=True):
    if not tickets:
        return
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        if verbose:
            print("  live_spot: ALPACA keys missing - skipping enrichment")
        return

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
    except ImportError:
        if verbose:
            print("  live_spot: alpaca-py not installed - skipping")
        return

    sc = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])

    us_tickets = [t for t in tickets if t.get("ticker", "").endswith(".US") and t.get("price")]
    if not us_tickets:
        if verbose:
            print("  live_spot: no US tickets to enrich")
        return

    symbols = list({t["ticker"].replace(".US", "") for t in us_tickets})
    try:
        req = StockLatestTradeRequest(symbol_or_symbols=symbols)
        trades = sc.get_stock_latest_trade(req)
    except Exception as e:
        if verbose:
            print(f"  live_spot: batch fetch failed: {type(e).__name__}: {str(e)[:120]}")
        return

    live_map = {}
    if isinstance(trades, dict):
        for sym, trade in trades.items():
            try:
                live_map[sym] = float(trade.price)
            except (AttributeError, ValueError, TypeError):
                pass

    enriched = 0
    big_movers = 0
    for t in us_tickets:
        sym = t["ticker"].replace(".US", "")
        live = live_map.get(sym)
        if live is None or live <= 0:
            continue
        close = t.get("price")
        if not close or close <= 0:
            continue
        delta_pct = (live / close - 1) * 100
        delta_usd = live - close
        t["live_spot"] = live
        t["live_change_pct"] = delta_pct
        t["live_change_usd"] = delta_usd
        if abs(delta_pct) >= 3:
            big_movers += 1
        enriched += 1

    if verbose:
        print(f"  live_spot: enriched {enriched}/{len(us_tickets)} US tickets ({big_movers} moved 3%+ overnight)")

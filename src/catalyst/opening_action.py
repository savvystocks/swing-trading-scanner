import os
from datetime import datetime, timezone


def fetch_live_quotes(symbols):
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        return {}, "no Alpaca keys"
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
    except ImportError:
        return {}, "alpaca-py not importable"

    syms = list({s.replace(".US", "") for s in symbols if s})
    if not syms:
        return {}, "no symbols"

    out = {}
    BATCH = 200
    try:
        sc = StockHistoricalDataClient(api_key, api_secret)
        for i in range(0, len(syms), BATCH):
            batch = syms[i:i + BATCH]
            try:
                trades = sc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=batch))
            except Exception:
                continue
            if not isinstance(trades, dict):
                continue
            for sym, t in trades.items():
                try:
                    price = float(t.price) if t.price else 0
                    if price <= 0:
                        continue
                    out[sym] = {"price": price, "timestamp": str(t.timestamp) if t.timestamp else None}
                except Exception:
                    continue
    except Exception as e:
        return out, f"{type(e).__name__}: {str(e)[:200]}"
    return out, None


def _session_label(ts):
    if not ts:
        return "unknown"
    try:
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        et_hour = (ts.hour - 4) % 24 + ts.minute / 60
        if 4.0 <= et_hour < 9.5:
            return "pre-market"
        if 9.5 <= et_hour < 16.0:
            return "regular"
        if 16.0 <= et_hour < 20.0:
            return "after-hours"
        return "closed"
    except Exception:
        return "unknown"


def apply_opening_action_boost(scan, top_n=200, verbose=True):
    all_scored = scan.get("all_scored") or []
    if not all_scored:
        return scan

    top = sorted(all_scored, key=lambda s: s.get("score") or 0, reverse=True)[:top_n]
    symbols = []
    prev_close_lookup = {}
    for s in top:
        ticker = s.get("ticker")
        if not ticker:
            continue
        bare = ticker.replace(".US", "").replace(".LSE", "")
        if (s.get("eodhd_ticker") or ticker).endswith(".LSE"):
            continue
        symbols.append(bare)
        prev_close_lookup[bare] = s.get("price") or 0

    quotes, err = fetch_live_quotes(symbols)
    if err:
        if verbose:
            print(f"  opening_action: {err}")
        return scan

    adjustments = 0
    boosted = 0
    flagged_chase = 0
    flagged_sell_news = 0

    for s in top:
        ticker = s.get("ticker")
        if not ticker:
            continue
        bare = ticker.replace(".US", "").replace(".LSE", "")
        if bare not in quotes:
            continue
        prev_close = prev_close_lookup.get(bare, 0)
        if not prev_close or prev_close <= 0:
            continue

        live_price = quotes[bare]["price"]
        gap_pct = (live_price - prev_close) / prev_close * 100
        session = _session_label(quotes[bare].get("timestamp"))

        tier = s.get("catalyst_tier") or ""
        has_strong_catalyst = tier in ("S", "A")
        components = s.get("components") or {}

        score_delta = 0
        label = ""

        if gap_pct >= 15:
            score_delta = -10
            label = f"EXTENDED — already +{gap_pct:.1f}%, do not chase"
            flagged_chase += 1
        elif gap_pct >= 7:
            score_delta = -3
            label = f"extended +{gap_pct:.1f}%, late entry"
            flagged_chase += 1
        elif gap_pct >= 3 and has_strong_catalyst:
            score_delta = 8
            label = f"confirmed catalyst breakout +{gap_pct:.1f}%"
            boosted += 1
        elif gap_pct >= 3:
            score_delta = 2
            label = f"gap +{gap_pct:.1f}% (no strong catalyst — unconfirmed)"
        elif gap_pct <= -7:
            score_delta = -15
            label = f"thesis broken {gap_pct:.1f}%"
            flagged_sell_news += 1
        elif gap_pct <= -3 and has_strong_catalyst:
            score_delta = -10
            label = f"SELL THE NEWS {gap_pct:.1f}% despite catalyst"
            flagged_sell_news += 1
        elif gap_pct <= -3:
            score_delta = -5
            label = f"opening weakness {gap_pct:.1f}%"

        if score_delta != 0:
            old_score = s.get("score") or 0
            s["score"] = round(old_score + score_delta, 2)
            components["opening_action"] = {
                "points": score_delta,
                "label": label,
                "gap_pct": round(gap_pct, 2),
                "live_price": live_price,
                "session": session,
            }
            s["components"] = components
            s["opening_gap_pct"] = round(gap_pct, 2)
            s["live_spot_at_scan"] = live_price
            adjustments += 1
            if gap_pct >= 15 or gap_pct <= -7:
                s["opening_action_skip_chase"] = True
                drift = components.get("drift") or {}
                drift["skip_chase"] = True
                components["drift"] = drift

    if verbose:
        print(f"  opening_action: {adjustments} score adjustments ({boosted} confirmed-breakout, {flagged_chase} chase-risk, {flagged_sell_news} sell-news)")

    try:
        from src.catalyst.scoring import assign_buckets
        top_pct_strong = scan.get("top_pct_strong", 5)
        top_pct_watch = scan.get("top_pct_watch", 15)
        scan["all_scored"] = assign_buckets(all_scored, top_pct_strong=top_pct_strong, top_pct_watch=top_pct_watch)
        new_strong = [s for s in scan["all_scored"] if s.get("bucket") == "STRONG"]
        new_watch = [s for s in scan["all_scored"] if s.get("bucket") == "WATCH"]
        scan["candidates"] = new_strong + new_watch
        if verbose:
            print(f"  opening_action rebucket: {len(new_strong)} STRONG / {len(new_watch)} WATCH")
    except Exception as e:
        if verbose:
            print(f"  opening_action rebucket failed: {type(e).__name__}: {e}")

    return scan

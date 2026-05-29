import os
import json
from datetime import datetime, timedelta


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V4_PICKS_PATH = os.path.join(PROJECT_ROOT, "data", "paper_trades", "v4_picks.json")


def _load():
    if not os.path.exists(V4_PICKS_PATH):
        return []
    try:
        with open(V4_PICKS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(entries):
    os.makedirs(os.path.dirname(V4_PICKS_PATH), exist_ok=True)
    with open(V4_PICKS_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


def log_picks(scan_date, ranked_picks, top_pick=None, haiku_picks=None, verbose=False):
    if not ranked_picks:
        if verbose:
            print(f"  v4_paper_log: 0 picks to log")
        return
    entries = _load()
    existing_keys = {(e.get("scan_date"), e.get("ticker")) for e in entries}
    added = 0
    for rank, pick in enumerate(ranked_picks[:3], start=1):
        ticker = pick.get("ticker")
        if not ticker:
            continue
        key = (scan_date, ticker)
        if key in existing_keys:
            continue
        forensic = pick.get("unified_forensic") or {}
        haiku = pick.get("haiku_synthesis") or {}
        used_sonnet = pick is top_pick
        used_haiku = (haiku_picks or []) and pick in (haiku_picks or [])
        entry = {
            "scan_date": scan_date,
            "rank": rank,
            "ticker": ticker,
            "name": pick.get("name", "")[:50],
            "bracket": pick.get("bracket"),
            "tier": pick.get("_aa_tier"),
            "stacked_score": pick.get("_stacked_score") or pick.get("score"),
            "categories_active": pick.get("_category_count"),
            "active_categories": pick.get("_active_categories"),
            "entry_price": pick.get("live_spot") or pick.get("price"),
            "sector": pick.get("sector"),
            "industry": pick.get("industry"),
            "market_cap": pick.get("market_cap"),
            "smart_money_signals": pick.get("_smart_money_signals") or [],
            "catalysts": [{"key": c.get("key"), "tier": c.get("tier"), "label": c.get("label")} for c in (pick.get("catalysts") or [])[:5]],
            "iv_percentile": (pick.get("iv_percentile_analysis") or {}).get("iv_percentile"),
            "trade_ticket": pick.get("trade_ticket") or {},
            "forensic_verdict": forensic.get("verdict") or haiku.get("verdict"),
            "forensic_confidence_pct": forensic.get("confidence_pct") or haiku.get("confidence_pct"),
            "forensic_model": "sonnet" if used_sonnet and forensic else ("haiku" if used_haiku and haiku else None),
            "extension_check": pick.get("_extension_check"),
            "logged_at": datetime.utcnow().isoformat() + "Z",
            "outcomes": {
                "measured_at": None,
                "price_1d": None,
                "price_5d": None,
                "price_14d": None,
                "price_30d": None,
                "max_high_to_30d": None,
                "max_low_to_30d": None,
                "max_drawdown_pct": None,
                "best_pct": None,
                "hit_t1_pct50": False,
                "hit_t2_pct100": False,
                "hit_t3_pct200": False,
                "hit_stop_neg40": False,
            },
        }
        entries.append(entry)
        added += 1
    if added:
        _save(entries)
    if verbose:
        print(f"  v4_paper_log: appended {added} new entries (total entries on disk: {len(entries)})")


def measure_outcomes(eodhd_client, target_date=None, verbose=False):
    if isinstance(target_date, str):
        today = datetime.strptime(target_date, "%Y-%m-%d").date()
    elif target_date:
        today = target_date
    else:
        today = datetime.utcnow().date()

    entries = _load()
    if not entries:
        return
    pending = [e for e in entries if e.get("outcomes", {}).get("measured_at") is None]
    if not pending:
        if verbose:
            print(f"  v4_paper_log measure: no pending outcomes")
        return

    fetched_cache = {}
    measured = 0
    for entry in pending:
        try:
            scan_dt = datetime.strptime(entry["scan_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        days_since = (today - scan_dt).days
        if days_since < 1:
            continue
        ticker = entry.get("ticker")
        if not ticker:
            continue
        eodhd_ticker = f"{ticker}.US"

        bars = fetched_cache.get(eodhd_ticker)
        if bars is None:
            try:
                from_d = scan_dt.strftime("%Y-%m-%d")
                to_d = (scan_dt + timedelta(days=45)).strftime("%Y-%m-%d")
                bars = eodhd_client.ohlcv(eodhd_ticker, from_date=from_d, to_date=to_d) or []
                fetched_cache[eodhd_ticker] = bars
            except Exception:
                fetched_cache[eodhd_ticker] = []
                bars = []
        if not bars:
            continue

        entry_price = entry.get("entry_price")
        if not entry_price:
            continue
        try:
            entry_price = float(entry_price)
        except (TypeError, ValueError):
            continue

        prices_after = []
        for b in bars:
            try:
                bd = datetime.strptime(b.get("date") or "", "%Y-%m-%d").date()
            except Exception:
                continue
            if bd <= scan_dt:
                continue
            prices_after.append({"date": bd, "high": float(b.get("high") or 0), "low": float(b.get("low") or 0), "close": float(b.get("close") or 0)})

        if not prices_after:
            continue

        def _close_at_offset(offset_days):
            target = scan_dt + timedelta(days=offset_days)
            for p in prices_after:
                if p["date"] >= target:
                    return p["close"]
            return prices_after[-1]["close"] if prices_after else None

        outcomes = entry.setdefault("outcomes", {})
        outcomes["price_1d"] = _close_at_offset(1)
        outcomes["price_5d"] = _close_at_offset(5)
        outcomes["price_14d"] = _close_at_offset(14)
        outcomes["price_30d"] = _close_at_offset(30)

        if days_since >= 30:
            window_30d = [p for p in prices_after if (p["date"] - scan_dt).days <= 30]
            if window_30d:
                highest = max(p["high"] for p in window_30d)
                lowest = min(p["low"] for p in window_30d)
                outcomes["max_high_to_30d"] = round(highest, 2)
                outcomes["max_low_to_30d"] = round(lowest, 2)
                outcomes["best_pct"] = round((highest - entry_price) / entry_price * 100, 2)
                outcomes["max_drawdown_pct"] = round((lowest - entry_price) / entry_price * 100, 2)
                outcomes["hit_t1_pct50"] = outcomes["best_pct"] >= 50
                outcomes["hit_t2_pct100"] = outcomes["best_pct"] >= 100
                outcomes["hit_t3_pct200"] = outcomes["best_pct"] >= 200
                outcomes["hit_stop_neg40"] = outcomes["max_drawdown_pct"] <= -40
                outcomes["measured_at"] = today.isoformat()
                measured += 1

    if measured:
        _save(entries)
    if verbose:
        print(f"  v4_paper_log measure: completed outcome measurement for {measured} entries")


def get_v4_stats(days_back=30):
    entries = _load()
    if not entries:
        return None
    cutoff = (datetime.utcnow().date() - timedelta(days=days_back)).isoformat()
    recent = [e for e in entries if (e.get("outcomes", {}).get("measured_at") or "") >= cutoff and e.get("outcomes", {}).get("best_pct") is not None]
    if not recent:
        return None
    by_rank = {1: [], 2: [], 3: []}
    by_tier = {"A++": [], "A+": [], "A": []}
    by_bracket = {"micro": [], "small": [], "mid": []}
    for e in recent:
        rank = e.get("rank")
        tier = e.get("tier")
        bracket = e.get("bracket")
        if rank in by_rank:
            by_rank[rank].append(e)
        if tier in by_tier:
            by_tier[tier].append(e)
        if bracket in by_bracket:
            by_bracket[bracket].append(e)

    def _summarize(group):
        if not group:
            return None
        bests = [e["outcomes"]["best_pct"] for e in group if e["outcomes"].get("best_pct") is not None]
        if not bests:
            return None
        wins_t1 = sum(1 for e in group if e["outcomes"].get("hit_t1_pct50"))
        wins_t2 = sum(1 for e in group if e["outcomes"].get("hit_t2_pct100"))
        stops = sum(1 for e in group if e["outcomes"].get("hit_stop_neg40"))
        return {
            "n": len(group),
            "win_rate_t1_pct": round(wins_t1 / len(group) * 100, 1),
            "win_rate_t2_pct": round(wins_t2 / len(group) * 100, 1),
            "stop_rate_pct": round(stops / len(group) * 100, 1),
            "avg_best_pct": round(sum(bests) / len(bests), 1),
            "max_best_pct": round(max(bests), 1),
            "worst_best_pct": round(min(bests), 1),
        }

    return {
        "total_picks_measured": len(recent),
        "days_back": days_back,
        "by_rank": {k: _summarize(v) for k, v in by_rank.items()},
        "by_tier": {k: _summarize(v) for k, v in by_tier.items()},
        "by_bracket": {k: _summarize(v) for k, v in by_bracket.items()},
    }

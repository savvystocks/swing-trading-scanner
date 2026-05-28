import os
import json
import pathlib
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
JOURNAL_PATH = PROJECT_ROOT / "data" / "paper_trades" / "conviction_journal.jsonl"


MIN_LOG_CONVICTION = 55
WATCH_TIERS = {"A++", "A+", "A", "MACRO_PUT"}


def _ensure_dir():
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_all():
    if not JOURNAL_PATH.exists():
        return []
    rows = []
    with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _save_all(rows):
    _ensure_dir()
    with open(JOURNAL_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


def _append(rows_to_add):
    if not rows_to_add:
        return
    _ensure_dir()
    with open(JOURNAL_PATH, "a", encoding="utf-8") as f:
        for r in rows_to_add:
            f.write(json.dumps(r, default=str) + "\n")


def _extract_winning_score(pick):
    d = pick.get("_direction") or {}
    ws = d.get("winning_score")
    if ws is not None:
        return ws
    c = (pick.get("_conviction") or {}).get("score") or 0
    b = (pick.get("_bear_conviction") or {}).get("score") or 0
    return max(c, b)


def _extract_side(pick):
    d = pick.get("_direction") or {}
    return d.get("side") or "CALL"


def _key_components(pick):
    conv = (pick.get("_conviction") or {}).get("components") or {}
    bear = (pick.get("_bear_conviction") or {}).get("components") or {}
    return {
        "conviction_components": {k: round(v, 1) if isinstance(v, (int, float)) else v for k, v in conv.items()},
        "bear_components": {k: round(v, 1) if isinstance(v, (int, float)) else v for k, v in bear.items()},
    }


def log_picks_from_scan(scan, verbose=False):
    scan_date = scan.get("scan_date")
    if not scan_date:
        if verbose:
            print(f"  conviction_journal: no scan_date, skipping")
        return 0

    aa_results = scan.get("aa_results") or {}
    existing = _load_all()
    existing_keys = {(r.get("scan_date"), r.get("ticker")) for r in existing}

    macro = (scan.get("macro") or {}).get("macro_regime") or {}
    macro_regime = macro.get("regime") or "UNKNOWN"
    macro_score = macro.get("score")

    added = []
    for tier, picks in aa_results.items():
        if tier not in WATCH_TIERS:
            continue
        for p in picks or []:
            ticker = p.get("ticker")
            if not ticker:
                continue
            key = (scan_date, ticker)
            if key in existing_keys:
                continue
            winning = _extract_winning_score(p)
            if winning < MIN_LOG_CONVICTION:
                continue
            side = _extract_side(p)
            conv = (p.get("_conviction") or {}).get("score") or 0
            bear = (p.get("_bear_conviction") or {}).get("score") or 0
            haiku = p.get("haiku_synthesis") or {}
            comps = _key_components(p)
            entry_price = p.get("live_spot") or p.get("price")

            row = {
                "scan_date": scan_date,
                "logged_at": datetime.utcnow().isoformat() + "Z",
                "ticker": ticker,
                "name": (p.get("name") or "")[:60],
                "sector": p.get("sector"),
                "tier": tier,
                "side": side,
                "entry_price": entry_price,
                "winning_score": winning,
                "call_conviction": conv,
                "bear_conviction": bear,
                "edge_pts": (p.get("_direction") or {}).get("edge_pts"),
                "llm_verdict": haiku.get("verdict"),
                "llm_confidence_pct": haiku.get("confidence_pct"),
                "catalysts": [c.get("key") for c in (p.get("catalysts") or [])[:5] if c.get("key")],
                "macro_regime_at_open": macro_regime,
                "macro_score_at_open": macro_score,
                "stage2_zone": (p.get("_stage2_zone") or {}).get("zone"),
                "pead_window": (p.get("_pead") or {}).get("window"),
                "components": comps,
                "status": "OPEN",
                "outcomes": {
                    "measured_at": None,
                    "price_1d": None,
                    "price_3d": None,
                    "price_5d": None,
                    "price_10d": None,
                    "price_15d": None,
                    "ret_1d_pct": None,
                    "ret_3d_pct": None,
                    "ret_5d_pct": None,
                    "ret_10d_pct": None,
                    "ret_15d_pct": None,
                    "max_high_15d": None,
                    "max_low_15d": None,
                    "best_pct": None,
                    "worst_pct": None,
                },
                "drift_history": [],
            }
            added.append(row)
            existing_keys.add(key)

    if added:
        _append(added)
    if verbose:
        print(f"  conviction_journal: logged {len(added)} new picks (total on disk: {len(existing) + len(added)})")
    return len(added)


def _get_bars(client, eodhd_ticker, scan_date_str):
    try:
        from_d = scan_date_str
        scan_dt = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
        to_d = (scan_dt + timedelta(days=25)).strftime("%Y-%m-%d")
        bars = client.ohlcv(eodhd_ticker, from_date=from_d, to_date=to_d) or []
        return bars
    except Exception:
        return []


def _bar_at_or_after(bars_after, target_date):
    for b in bars_after:
        if b["date"] >= target_date:
            return b
    return bars_after[-1] if bars_after else None


def mark_forward_returns(eodhd_client, target_date=None, verbose=False):
    if target_date is None:
        today = datetime.utcnow().date()
    elif isinstance(target_date, str):
        today = datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        today = target_date

    rows = _load_all()
    if not rows:
        if verbose:
            print(f"  conviction_journal: no rows to mark")
        return 0

    pending = [r for r in rows if not r.get("outcomes", {}).get("measured_at")]
    if not pending:
        if verbose:
            print(f"  conviction_journal: no pending outcomes to mark")
        return 0

    by_ticker_bars = {}
    measured = 0
    for r in pending:
        try:
            scan_dt = datetime.strptime(r["scan_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        days_since = (today - scan_dt).days
        if days_since < 1:
            continue

        ticker = r["ticker"]
        entry = r.get("entry_price")
        if not ticker or not entry:
            continue
        try:
            entry_f = float(entry)
        except (TypeError, ValueError):
            continue
        if entry_f <= 0:
            continue

        eodhd_ticker = f"{ticker}.US"
        if eodhd_ticker not in by_ticker_bars:
            by_ticker_bars[eodhd_ticker] = _get_bars(eodhd_client, eodhd_ticker, r["scan_date"])
        bars = by_ticker_bars[eodhd_ticker]
        if not bars:
            continue

        bars_after = []
        for b in bars:
            try:
                bd = datetime.strptime(b.get("date") or "", "%Y-%m-%d").date()
            except Exception:
                continue
            if bd <= scan_dt:
                continue
            bars_after.append({
                "date": bd,
                "open": float(b.get("open") or 0),
                "high": float(b.get("high") or 0),
                "low": float(b.get("low") or 0),
                "close": float(b.get("close") or 0),
            })
        if not bars_after:
            continue

        outcomes = r.setdefault("outcomes", {})
        for offset in (1, 3, 5, 10, 15):
            target = scan_dt + timedelta(days=offset)
            bar = _bar_at_or_after(bars_after, target)
            if bar:
                price = bar["close"]
                outcomes[f"price_{offset}d"] = round(price, 4)
                outcomes[f"ret_{offset}d_pct"] = round((price - entry_f) / entry_f * 100, 2)

        window = [b for b in bars_after if (b["date"] - scan_dt).days <= 15]
        if window:
            hi = max(b["high"] for b in window)
            lo = min(b["low"] for b in window)
            outcomes["max_high_15d"] = round(hi, 4)
            outcomes["max_low_15d"] = round(lo, 4)
            outcomes["best_pct"] = round((hi - entry_f) / entry_f * 100, 2)
            outcomes["worst_pct"] = round((lo - entry_f) / entry_f * 100, 2)

        if days_since >= 15:
            outcomes["measured_at"] = today.isoformat()
            r["status"] = "CLOSED"
            measured += 1

    _save_all(rows)
    if verbose:
        print(f"  conviction_journal: stamped forward returns ({measured} closed, {len(pending) - measured} still open)")
    return measured


def get_journal_stats(days_back=60):
    rows = _load_all()
    if not rows:
        return None
    cutoff = (datetime.utcnow().date() - timedelta(days=days_back)).isoformat()
    recent = [r for r in rows if r.get("scan_date", "") >= cutoff and r.get("outcomes", {}).get("best_pct") is not None]
    if not recent:
        return None

    by_side = {"CALL": [], "PUT": []}
    by_tier = {"A++": [], "A+": [], "A": [], "MACRO_PUT": []}
    by_score_band = {"80+": [], "70-79": [], "60-69": [], "55-59": []}

    for r in recent:
        side = r.get("side") or "CALL"
        tier = r.get("tier")
        ws = r.get("winning_score") or 0
        if side in by_side:
            by_side[side].append(r)
        if tier in by_tier:
            by_tier[tier].append(r)
        if ws >= 80:
            by_score_band["80+"].append(r)
        elif ws >= 70:
            by_score_band["70-79"].append(r)
        elif ws >= 60:
            by_score_band["60-69"].append(r)
        else:
            by_score_band["55-59"].append(r)

    def summarize(group, is_put_bucket=False):
        if not group:
            return None
        bests = []
        rets_5d = []
        rets_10d = []
        wins = 0
        for r in group:
            o = r.get("outcomes") or {}
            best = o.get("best_pct")
            worst = o.get("worst_pct")
            r5 = o.get("ret_5d_pct")
            r10 = o.get("ret_10d_pct")
            target_metric = best if not is_put_bucket else (-1 * worst if worst is not None else None)
            if target_metric is not None:
                bests.append(target_metric)
                if target_metric >= 5:
                    wins += 1
            if r5 is not None:
                rets_5d.append(r5 if not is_put_bucket else -r5)
            if r10 is not None:
                rets_10d.append(r10 if not is_put_bucket else -r10)
        n = len(group)
        return {
            "n": n,
            "win_rate_pct": round(wins / n * 100, 1) if n else 0,
            "avg_best_pct": round(sum(bests) / len(bests), 2) if bests else None,
            "avg_5d_pct": round(sum(rets_5d) / len(rets_5d), 2) if rets_5d else None,
            "avg_10d_pct": round(sum(rets_10d) / len(rets_10d), 2) if rets_10d else None,
        }

    return {
        "lookback_days": days_back,
        "total_measured": len(recent),
        "by_side": {
            "CALL": summarize(by_side["CALL"], is_put_bucket=False),
            "PUT": summarize(by_side["PUT"], is_put_bucket=True),
        },
        "by_tier": {k: summarize(v, is_put_bucket=False) for k, v in by_tier.items()},
        "by_score_band": {k: summarize(v, is_put_bucket=False) for k, v in by_score_band.items()},
    }


def get_open_positions(max_age_days=14):
    rows = _load_all()
    cutoff = (datetime.utcnow().date() - timedelta(days=max_age_days)).isoformat()
    return [r for r in rows if r.get("status") == "OPEN" and r.get("scan_date", "") >= cutoff]


def update_position_drift(scan_date, ticker, current_conviction, current_bear, current_side):
    rows = _load_all()
    changed = False
    for r in rows:
        if r.get("ticker") != ticker:
            continue
        if r.get("status") != "OPEN":
            continue
        history = r.setdefault("drift_history", [])
        if history and history[-1].get("scan_date") == scan_date:
            continue
        history.append({
            "scan_date": scan_date,
            "call_conviction": current_conviction,
            "bear_conviction": current_bear,
            "side": current_side,
            "winning_score": max(current_conviction, current_bear),
        })
        changed = True
    if changed:
        _save_all(rows)
    return changed

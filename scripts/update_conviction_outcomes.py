"""Resolve outcomes on logged high-conviction picks.

For each open entry in conviction_log.json (not yet outcome-filled),
check if enough time has passed to evaluate:
  - GAMMA_BOMB:     3+ days since logged
  - MAX/ELITE:      7+ days since logged

If yes, fetch realized price + current option mid, compute return,
mark WIN/LOSS/EXPIRED.

Run daily via GitHub Actions (separate workflow or piggybacked on flow-scan).
"""

import os
import sys
import json
import pathlib
from datetime import datetime, timezone, timedelta


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.conviction_log import load_log, save_log
from src.catalyst import exit_policy
from src.unusual_whales_api import get_client


REVIEW_WINDOW_DAYS = {
    "GAMMA_BOMB": 3,
    "MAX_CONVICTION": 7,
    "ELITE": 7,
}


def _now():
    return datetime.now(timezone.utc)


def _parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _f(v):
    try:
        x = float(v)
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def _fetch_history(uw, occ, scan_date, window):
    data = uw.option_contract_historic(occ)
    rows = (data or {}).get("chains") or []
    start = _parse_date(scan_date)
    if not start:
        return None, []
    entry_mid = None
    path = []
    for r in rows:
        d = _parse_date(r.get("date"))
        if not d:
            continue
        bid, ask = _f(r.get("nbbo_bid")), _f(r.get("nbbo_ask"))
        last = _f(r.get("last_price"))
        mid = (bid + ask) / 2 if (bid and ask) else last
        if d == start:
            entry_mid = mid
            continue
        if d < start or (d - start).days > window:
            continue
        cands_hi = [v for v in (mid, ask, last) if v]
        cands_lo = [v for v in (mid, bid, last) if v]
        high = _f(r.get("high_price")) or (max(cands_hi) if cands_hi else None)
        low = _f(r.get("low_price")) or (min(cands_lo) if cands_lo else None)
        close = mid or last
        op = _f(r.get("open_price")) or mid or last
        if not (high and low and close and op):
            continue
        path.append({"date": r["date"][:10], "open": op, "high": high, "low": low, "close": close})
    path.sort(key=lambda x: x["date"])
    return entry_mid, path


def resolve_outcome(uw, entry):
    """Return outcome dict (final) or None if still open."""
    if entry.get("outcome"):
        return None
    logged_at = _parse_iso(entry.get("logged_at"))
    if not logged_at:
        return None
    days_since = (_now() - logged_at).days

    ticker = entry.get("ticker")
    tt = entry.get("trade_ticket") or {}
    occ = tt.get("occ_symbol")
    entry_mid = tt.get("mid")
    if not (ticker and occ):
        return {"checked_at": _now().isoformat(), "result": "MISSING_DATA",
                "days_held": days_since}

    window = REVIEW_WINDOW_DAYS.get(entry["tier"], 7)
    scan_date = entry.get("scan_date") or logged_at.date().isoformat()
    hist_entry, days = _fetch_history(uw, occ, scan_date, window)
    if not entry_mid:
        entry_mid = hist_entry
        if entry_mid:
            tt["mid"] = round(entry_mid, 2)
    if not (entry_mid and days):
        return None

    sim = exit_policy.simulate(entry_mid, days)
    if not sim:
        return None

    if sim["exited"]:
        result = "WIN" if sim["exit_reason"] == "ARM_TRAIL" else "LOSS"
        realized, exit_reason, exit_date = sim["realized_pct"], sim["exit_reason"], sim["exit_date"]
    elif days_since >= window:
        realized, exit_reason, exit_date = sim["end_pct"], "TIME_STOP", sim["end_date"]
        result = "WIN" if realized > 0 else "LOSS"
    else:
        return None

    return {
        "checked_at": _now().isoformat(),
        "days_held": days_since,
        "result": result,
        "exit_reason": exit_reason,
        "exit_date": exit_date,
        "realized_pct": realized,
        "pct_return": realized,
        "peak_pct": sim["peak_pct"],
        "peak_date": sim["peak_date"],
        "trough_pct": sim["trough_pct"],
        "end_pct": sim["end_pct"],
        "armed": sim["armed"],
    }


def main():
    log = load_log()
    if not log:
        print("Conviction log empty - nothing to resolve")
        return

    uw = get_client()
    if not uw.enabled:
        print("UW token missing")
        sys.exit(1)

    n_open = sum(1 for e in log if not e.get("outcome"))
    print(f"Conviction log: {len(log)} entries, {n_open} unresolved")

    resolved = 0
    for entry in log:
        outcome = resolve_outcome(uw, entry)
        if outcome:
            entry["outcome"] = outcome
            resolved += 1
            print(f"  {entry['ticker']:6} {entry['tier']:15} {entry['side']:4}  -> {outcome['result']:4} {outcome.get('pct_return', '?')}% via {outcome.get('exit_reason', '?')} (peak {outcome.get('peak_pct', '?')}%)")

    save_log(log)

    # Summary stats per tier
    print("")
    by_tier = {}
    for e in log:
        o = e.get("outcome") or {}
        tier = e.get("tier", "?")
        slot = by_tier.setdefault(tier, {"n": 0, "wins": 0, "losses": 0, "open": 0, "sum_return": 0, "n_with_return": 0})
        slot["n"] += 1
        result = o.get("result", "")
        if result == "WIN":
            slot["wins"] += 1
        elif result == "LOSS":
            slot["losses"] += 1
        elif result == "OPEN":
            slot["open"] += 1
        if o.get("pct_return") is not None:
            slot["sum_return"] += o["pct_return"]
            slot["n_with_return"] += 1

    print(f"{'Tier':18} {'Total':>5} {'Wins':>4} {'Loss':>4} {'Open':>4} {'Avg%':>7}")
    for tier in ("GAMMA_BOMB", "MAX_CONVICTION", "ELITE"):
        s = by_tier.get(tier)
        if not s:
            continue
        avg = s["sum_return"] / s["n_with_return"] if s["n_with_return"] else 0
        print(f"  {tier:18} {s['n']:>5} {s['wins']:>4} {s['losses']:>4} {s['open']:>4} {avg:>6.1f}%")

    print(f"\nResolved {resolved} new outcomes this run.")


if __name__ == "__main__":
    main()

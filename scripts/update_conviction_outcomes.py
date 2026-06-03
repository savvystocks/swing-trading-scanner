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


def resolve_outcome(uw, entry):
    """Return outcome dict or None if not ready to evaluate."""
    if entry.get("outcome"):
        return None
    logged_at = _parse_iso(entry.get("logged_at"))
    if not logged_at:
        return None
    days_since = (_now() - logged_at).days
    window = REVIEW_WINDOW_DAYS.get(entry["tier"], 7)
    if days_since < window:
        return None

    ticker = entry.get("ticker")
    tt = entry.get("trade_ticket") or {}
    occ = tt.get("occ_symbol")
    entry_mid = tt.get("mid")
    expiry = tt.get("expiry")
    if not (ticker and occ and entry_mid):
        return {"checked_at": _now().isoformat(), "result": "MISSING_DATA",
                "days_held": days_since}

    # Has the contract expired?
    expiry_date = _parse_iso(expiry + "T00:00:00Z") if expiry else None
    if expiry_date and _now() > expiry_date:
        return {"checked_at": _now().isoformat(), "result": "EXPIRED",
                "days_held": days_since,
                "note": "Contract expired before review - cannot fetch current premium"}

    # Pull current option intraday + spot
    try:
        data = uw._request(f"/stock/{ticker}/option-contracts", None,
                            cache_key="oi_per_strike", ttl=600)
        if not data:
            return {"checked_at": _now().isoformat(), "result": "FETCH_FAILED",
                    "days_held": days_since}
        rows = data.get("data") or []
        cur_mid = None
        for r in rows:
            if isinstance(r, dict) and r.get("option_symbol") == occ:
                bid = float(r.get("nbbo_bid") or 0)
                ask = float(r.get("nbbo_ask") or 0)
                if bid and ask:
                    cur_mid = (bid + ask) / 2
                else:
                    cur_mid = float(r.get("last_price") or 0)
                break
        if not cur_mid:
            return {"checked_at": _now().isoformat(), "result": "NO_QUOTE",
                    "days_held": days_since}

        # Live spot
        spot_data = uw.stock_state(ticker)
        cur_spot = float((spot_data or {}).get("data", {}).get("close") or 0)

        pct_return = (cur_mid - entry_mid) / entry_mid * 100
        result = "WIN" if pct_return >= 50 else ("LOSS" if pct_return <= -50 else "OPEN")
        return {
            "checked_at": _now().isoformat(),
            "days_held": days_since,
            "exit_premium": round(cur_mid, 2),
            "exit_spot": round(cur_spot, 2),
            "pct_return": round(pct_return, 1),
            "result": result,
        }
    except Exception as e:
        return {"checked_at": _now().isoformat(),
                "result": "ERROR",
                "error": f"{type(e).__name__}: {e}",
                "days_held": days_since}


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
            print(f"  {entry['ticker']:6} {entry['tier']:15} {entry['side']:4}  -> {outcome['result']}  ({outcome.get('pct_return', '?')}%)")

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

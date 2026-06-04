"""High-conviction pick paper trail.

Every ELITE / MAX_CONVICTION / GAMMA_BOMB pick from any scan gets appended
to data/conviction_log.json with full entry details. A separate periodic
job (scripts/update_conviction_outcomes.py) fills in realized outcomes
as days pass so we can backtest hit rate per tier over time.

Schema:
[
  {
    "logged_at": "2026-06-03T20:00:00Z",
    "scan_date": "2026-06-03",
    "ticker": "TSLA",
    "tier": "MAX_CONVICTION",
    "side": "CALL",
    "score": 114,
    "size_pct": 40,
    "trade_ticket": {
      "occ_symbol": "TSLA260702C00430000",
      "strike": 430,
      "expiry": "2026-07-02",
      "dte": 29,
      "mid": 19.82,
      "delta": 0.50,
      "iv": 0.48
    },
    "patterns_fired": ["nope", "gamma_flip", "volume_oi", ...],
    "sources": ["premium_top30", "sweep_volume", ...],
    "thesis": "TSLA CALL (MAX_CONVICTION): NOPE +0.53 ...",
    "entry_spot": 432.4,
    "macro_regime": "RISK_OFF_PRESSURE",
    "outcome": null  // filled in later
  },
  ...
]

The outcome dict (when filled by the review job):
  {
    "checked_at": "2026-06-10T20:00:00Z",
    "days_held": 7,
    "exit_premium": 34.50,
    "exit_spot": 458.20,
    "pct_return": 74.1,
    "result": "WIN" | "LOSS" | "OPEN" | "EXPIRED"
  }
"""

import json
import pathlib
from datetime import datetime, timezone


LOG_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "conviction_log.json"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


TRACKED_TIERS = {"ELITE", "MAX_CONVICTION", "GAMMA_BOMB"}


def load_log():
    if not LOG_PATH.exists():
        return []
    try:
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_log(log):
    LOG_PATH.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")


def _entry_key(scan_date, ticker, side):
    """One idea per name per direction per day. Strike/tier deliberately excluded:
    intraday the strike drifts as price moves and the tier oscillates, which used
    to log the same chased idea many times and pollute the hit-rate. The single
    surviving row is the highest-scored scan of the day (its peak conviction)."""
    return f"{scan_date}|{ticker}|{side}"


def append_picks(scan, verbose=False):
    """Pull all ELITE+ picks from a scan dict and append to the log.
    Dedupes by (scan_date, ticker, tier, side, strike) so 30-min re-scans of
    the same pick don't create duplicates - the highest score in the day wins.
    """
    if not scan:
        return 0
    log = load_log()
    existing_keys = {_entry_key(e.get("scan_date"), e.get("ticker"), e.get("side")): i
                     for i, e in enumerate(log)}

    macro_regime = ((scan.get("macro") or {}).get("meta_regime") or {}).get("regime", "UNKNOWN")
    scan_date = scan.get("scan_date", "")
    now = datetime.now(timezone.utc).isoformat()

    appended = 0
    upgraded = 0
    for stream in ("calls", "puts"):
        for pick in scan.get(stream) or []:
            c = pick.get("_confluence") or {}
            tier = c.get("tier")
            if tier not in TRACKED_TIERS:
                continue
            ticker = pick.get("ticker")
            tt = c.get("trade_ticket") or {}
            strike = tt.get("strike")
            entry = {
                "logged_at": now,
                "scan_date": scan_date,
                "ticker": ticker,
                "tier": tier,
                "side": c.get("side"),
                "score": c.get("score"),
                "size_pct": c.get("size_pct"),
                "trade_ticket": {
                    "occ_symbol": tt.get("occ_symbol"),
                    "strike": strike,
                    "expiry": tt.get("expiry"),
                    "dte": tt.get("dte"),
                    "mid": tt.get("mid"),
                    "delta": tt.get("delta"),
                    "iv": (tt.get("quote") or {}).get("iv"),
                },
                "patterns_fired": [p.get("key") for p in (c.get("patterns_fired") or [])],
                "sources": pick.get("sources") or [],
                "thesis": c.get("thesis", ""),
                "entry_spot": pick.get("live_spot") or pick.get("price"),
                "macro_regime": macro_regime,
                "outcome": None,
            }
            key = _entry_key(scan_date, ticker, c.get("side"))
            if key in existing_keys:
                # Same-day re-appearance (any strike/tier): keep the HIGHER-scored version
                idx = existing_keys[key]
                if (entry["score"] or 0) > (log[idx].get("score") or 0):
                    # Preserve outcome if already filled in
                    entry["outcome"] = log[idx].get("outcome")
                    log[idx] = entry
                    upgraded += 1
            else:
                log.append(entry)
                existing_keys[key] = len(log) - 1
                appended += 1

    save_log(log)
    if verbose:
        print(f"  conviction_log: +{appended} new picks, {upgraded} re-scored. Total log: {len(log)} entries")
    return appended


def get_open_picks(max_days_old=30):
    """Return picks that need outcome resolution (not yet checked, within window)."""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days_old)
    out = []
    for e in load_log():
        if e.get("outcome"):
            continue
        try:
            logged = datetime.fromisoformat(e["logged_at"].replace("Z", "+00:00"))
            if logged < cutoff:
                continue
        except Exception:
            pass
        out.append(e)
    return out

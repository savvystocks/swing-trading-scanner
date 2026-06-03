"""FINRA Margin Debt - monthly contrarian positioning indicator.

FINRA publishes total margin debt outstanding monthly on the 4th business week.
Historical context:
  Margin debt growth >25% YoY = late-cycle euphoria (contrarian short)
  Margin debt YoY decline >15% = capitulation (contrarian long)
  Multi-year low of margin debt = oversold / bottom

Source: https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics
Backup: historical data on web archive.

Used as a STANDING signal on the macro_positioning regime + as a confluence
input on Stocks 500/1000 wide-market PUT theses.

Free, no auth. Updates monthly so cache for 25 days.
"""

import json
import pathlib
import re
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
MARGIN_HISTORY_PATH = PROJECT_ROOT / "data" / "finra_margin" / "history.jsonl"
MARGIN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
CACHE_PATH = PROJECT_ROOT / "data" / "finra_margin" / "snapshot.json"


def _load_history():
    if not MARGIN_HISTORY_PATH.exists():
        return []
    rows = []
    with open(MARGIN_HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _save_history(rows):
    with open(MARGIN_HISTORY_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


def _is_cache_fresh(days=25):
    if not CACHE_PATH.exists():
        return False
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("_cached_at")
        if not ts:
            return False
        cached = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.utcnow() - cached.replace(tzinfo=None)).days < days
    except Exception:
        return False


MANUAL_OVERRIDE_PATH = PROJECT_ROOT / "data" / "finra_margin" / "manual_override.json"


def _load_manual_override():
    """If FINRA scrape is broken, allow manual JSON override.

    Expected schema:
      [{"month": "2026-05", "debit_balance_usd": 870000000000,
        "free_credit_balance_usd": 0, "net": 0}, ...]
    """
    if not MANUAL_OVERRIDE_PATH.exists():
        return None
    try:
        with open(MANUAL_OVERRIDE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            data.sort(key=lambda x: x.get("month", ""), reverse=True)
            return data[0]
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def fetch_finra_margin(verbose=False):
    """Scrape latest FINRA margin debt total from public page.

    Falls back to manual override file at data/finra_margin/manual_override.json.

    Returns dict {month, debit_balance_usd, free_credit_balance_usd, net} or None.
    """
    if _is_cache_fresh():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("snapshot")
        except Exception:
            pass

    # Seed history from full manual override file (not just latest) so YoY calc has data
    if MANUAL_OVERRIDE_PATH.exists():
        try:
            with open(MANUAL_OVERRIDE_PATH, "r", encoding="utf-8") as f:
                override_data = json.load(f)
            if isinstance(override_data, list):
                history = _load_history()
                seen = {h.get("month") for h in history}
                added = 0
                for entry in override_data:
                    if entry.get("month") not in seen:
                        history.append(entry)
                        added += 1
                if added:
                    history.sort(key=lambda x: x.get("month", ""))
                    _save_history(history)
        except Exception:
            pass

    override = _load_manual_override()
    if override:
        if verbose:
            print(f"  finra_margin: using manual override for {override.get('month')}")
        return {**override, "_source": "manual_override", "_cached_at": datetime.utcnow().isoformat() + "Z"}

    try:
        import requests
        r = requests.get(
            "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics",
            headers={"User-Agent": "Mozilla/5.0 (compatible; SwingScanner/1.0)"},
            timeout=20,
        )
        if r.status_code != 200:
            if verbose:
                print(f"  finra_margin: HTTP {r.status_code}")
            return None
        html = r.text

        # FINRA renders a table of monthly figures. Find the most recent month with debit balance.
        # Pattern: a row with month name + 4 columns of dollar values.
        month_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})"
        rows = re.findall(
            month_pattern + r"[\s\S]{0,1500}?\$?([\d,]+)[\s\S]{0,200}?\$?([\d,]+)[\s\S]{0,200}?\$?([\d,]+)",
            html,
        )
        if not rows:
            if verbose:
                print("  finra_margin: no month rows matched")
            return None

        snapshots = []
        for r_data in rows[:24]:
            month_name, year_str, debit_str, free_credit_str, net_str = r_data
            try:
                debit = int(debit_str.replace(",", ""))
                free_credit = int(free_credit_str.replace(",", ""))
                net = int(net_str.replace(",", ""))
                # FINRA reports in millions; convert to USD
                snapshots.append({
                    "month": f"{year_str}-{datetime.strptime(month_name, '%B').month:02d}",
                    "debit_balance_usd": debit * 1_000_000,
                    "free_credit_balance_usd": free_credit * 1_000_000,
                    "net": net * 1_000_000,
                })
            except (TypeError, ValueError):
                continue

        if not snapshots:
            return None

        snapshots.sort(key=lambda x: x["month"], reverse=True)
        latest = snapshots[0]

        # Persist history (de-dupe by month)
        history = _load_history()
        seen_months = {h.get("month") for h in history}
        for s in snapshots:
            if s["month"] not in seen_months:
                history.append(s)
        history.sort(key=lambda x: x["month"])
        _save_history(history)

        out = {**latest, "_cached_at": datetime.utcnow().isoformat() + "Z"}
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"snapshot": out, "_cached_at": out["_cached_at"]}, f)
        except Exception:
            pass

        if verbose:
            print(f"  finra_margin: latest {latest['month']} debit ${latest['debit_balance_usd']/1e9:.1f}B")
        return out
    except Exception as e:
        if verbose:
            print(f"  finra_margin fetch failed: {type(e).__name__}: {e}")
        return None


def analyze_margin_regime(snapshot=None, verbose=False):
    """Classify current margin debt regime vs 12m history.

    Returns:
      {regime: EUPHORIC_LATE_CYCLE | NORMAL | CAPITULATION_BOTTOM,
       yoy_change_pct, score, label}
    """
    if snapshot is None:
        snapshot = fetch_finra_margin(verbose=verbose)
    if not snapshot:
        return None

    history = _load_history()
    if len(history) < 12:
        return {
            "regime": "INSUFFICIENT_HISTORY",
            "label": f"Margin debit ${snapshot['debit_balance_usd']/1e9:.1f}B (need 12m history)",
            "score": 50,
        }

    history.sort(key=lambda x: x["month"])
    current = history[-1]
    year_ago = history[-13] if len(history) >= 13 else history[0]

    cur_debit = current.get("debit_balance_usd", 0)
    prev_debit = year_ago.get("debit_balance_usd", 1)
    if prev_debit <= 0:
        prev_debit = 1
    yoy_change = (cur_debit - prev_debit) / prev_debit * 100

    if yoy_change >= 25:
        regime = "EUPHORIC_LATE_CYCLE"
        label = f"Margin debt +{yoy_change:.0f}% YoY ${cur_debit/1e9:.0f}B - late-cycle euphoria, contrarian short bias"
        score = 75
        direction = "CONTRARIAN_SHORT"
    elif yoy_change <= -15:
        regime = "CAPITULATION_BOTTOM"
        label = f"Margin debt {yoy_change:+.0f}% YoY ${cur_debit/1e9:.0f}B - leverage capitulation, contrarian long bias"
        score = 75
        direction = "CONTRARIAN_LONG"
    elif yoy_change >= 15:
        regime = "ELEVATED"
        label = f"Margin debt +{yoy_change:.0f}% YoY ${cur_debit/1e9:.0f}B - elevated leverage building"
        score = 55
        direction = "CAUTION_SHORT"
    else:
        regime = "NORMAL"
        label = f"Margin debt {yoy_change:+.0f}% YoY ${cur_debit/1e9:.0f}B - normal range"
        score = 50
        direction = "NEUTRAL"

    if verbose:
        print(f"  finra_margin regime: {regime} ({yoy_change:+.1f}% YoY)")
    return {
        "regime": regime,
        "yoy_change_pct": round(yoy_change, 1),
        "current_debit_usd": cur_debit,
        "label": label,
        "score": score,
        "direction": direction,
        "month": current.get("month"),
    }


def enrich_picks_with_margin(picks, regime_data=None, verbose=False):
    """Attach margin debt regime as a market-wide overlay on every pick."""
    if not picks:
        return picks
    if regime_data is None:
        regime_data = analyze_margin_regime(verbose=verbose)
    if not regime_data or regime_data.get("regime") == "INSUFFICIENT_HISTORY":
        return picks

    for p in picks:
        p["_finra_margin_regime"] = regime_data
    if verbose:
        print(f"  finra_margin: {len(picks)} picks tagged with {regime_data['regime']}")
    return picks

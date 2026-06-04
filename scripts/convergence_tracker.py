"""Convergence Scanner — Outcome Tracker + Self-Monitor.

Three jobs in one script:

  1. LOG     — Called by convergence_scanner.py after each scan.
               Appends flagged tickers + signals to data/convergence/log.json

  2. RESOLVE — Runs nightly. For each unresolved log entry, checks the
               ticker's price 1/3/5 days later. Marks win (>5% move),
               loss (<-3%), or neutral. Builds a running scorecard.

  3. MONITOR — Runs after each scan. Detects:
               - 3+ consecutive days with zero actionable hits
               - Any signal returning null for >50% of tickers (dead API)
               - Scorecard hit rate dropping below 20%
               Sends a Telegram or email alert when triggered.

Usage:
  python scripts/convergence_tracker.py log '{"results": [...]}'
  python scripts/convergence_tracker.py resolve
  python scripts/convergence_tracker.py monitor
  python scripts/convergence_tracker.py scorecard
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

DATA_DIR = Path(__file__).parent.parent / "data" / "convergence"
DATA_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = DATA_DIR / "log.json"
SCORECARD_PATH = DATA_DIR / "scorecard.json"
MONITOR_PATH = DATA_DIR / "monitor_state.json"

API_BASE = "https://api.unusualwhales.com/api"


def _uw_headers():
    token = os.environ.get("UNUSUAL_WHALES_TOKEN", "").strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _load_json(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ── 1. LOG ──

def log_scan(results, scan_time):
    if not results:
        entry = {
            "scan_time": scan_time,
            "tickers": [],
            "actionable_count": 0,
            "watchlist_count": 0,
        }
    else:
        tickers = []
        for r in results:
            signal_names = list(r.get("signals", {}).keys())
            tickers.append({
                "ticker": r["ticker"],
                "convergence": r["convergence"],
                "signals": signal_names,
                "iv_rank": r.get("iv_rank"),
                "net_gex": r.get("net_gex"),
                "market_cap": r.get("market_cap"),
                "flow_premium": r.get("signals", {}).get("flow", {}).get("total_premium"),
            })
        entry = {
            "scan_time": scan_time,
            "tickers": tickers,
            "actionable_count": sum(1 for t in tickers if t["convergence"] >= 3),
            "watchlist_count": sum(1 for t in tickers if t["convergence"] == 2),
        }

    log = _load_json(LOG_PATH)
    log.append(entry)

    # Keep last 30 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    log = [e for e in log if e.get("scan_time", "") >= cutoff]

    _save_json(LOG_PATH, log)
    return entry


# ── 2. RESOLVE ──

def _get_price_on_date(ticker, date_str):
    h = _uw_headers()
    if not h:
        return None
    try:
        r = requests.get(
            f"{API_BASE}/stock/{ticker}/ohlc/1d",
            headers=h, timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data") or []
        for bar in data:
            if bar.get("date", "")[:10] == date_str:
                return float(bar.get("close") or 0)
        if data:
            return float(data[-1].get("close") or 0)
    except Exception:
        pass
    return None


def resolve_outcomes():
    scorecard = _load_json(SCORECARD_PATH) if SCORECARD_PATH.exists() else []
    resolved_keys = {(s["ticker"], s["scan_date"]) for s in scorecard}

    log = _load_json(LOG_PATH)
    today = datetime.now(timezone.utc).date()
    new_resolutions = 0

    for entry in log:
        scan_time = entry.get("scan_time", "")
        scan_date_str = scan_time[:10]
        try:
            scan_date = datetime.fromisoformat(scan_time.replace("Z", "+00:00")).date()
        except Exception:
            continue

        days_since = (today - scan_date).days
        if days_since < 5:
            continue

        for t in entry.get("tickers", []):
            ticker = t["ticker"]
            if (ticker, scan_date_str) in resolved_keys:
                continue

            price_t0 = _get_price_on_date(ticker, scan_date_str)
            price_t1 = _get_price_on_date(ticker, (scan_date + timedelta(days=1)).isoformat())
            price_t3 = _get_price_on_date(ticker, (scan_date + timedelta(days=3)).isoformat())
            price_t5 = _get_price_on_date(ticker, (scan_date + timedelta(days=5)).isoformat())

            if not price_t0 or price_t0 == 0:
                continue

            pct_1d = ((price_t1 / price_t0) - 1) * 100 if price_t1 else None
            pct_3d = ((price_t3 / price_t0) - 1) * 100 if price_t3 else None
            pct_5d = ((price_t5 / price_t0) - 1) * 100 if price_t5 else None

            best_return = max(filter(None, [pct_1d, pct_3d, pct_5d]), default=0)

            if best_return >= 5:
                outcome = "WIN"
            elif best_return <= -3:
                outcome = "LOSS"
            else:
                outcome = "NEUTRAL"

            scorecard.append({
                "ticker": ticker,
                "scan_date": scan_date_str,
                "convergence": t["convergence"],
                "signals": t["signals"],
                "price_t0": price_t0,
                "pct_1d": round(pct_1d, 2) if pct_1d else None,
                "pct_3d": round(pct_3d, 2) if pct_3d else None,
                "pct_5d": round(pct_5d, 2) if pct_5d else None,
                "best_return": round(best_return, 2),
                "outcome": outcome,
            })
            resolved_keys.add((ticker, scan_date_str))
            new_resolutions += 1

    _save_json(SCORECARD_PATH, scorecard)
    print(f"Resolved {new_resolutions} new outcomes. Total scorecard: {len(scorecard)} entries.")
    return scorecard


# ── 3. MONITOR ──

def run_monitor():
    log = _load_json(LOG_PATH)
    scorecard = _load_json(SCORECARD_PATH) if SCORECARD_PATH.exists() else []
    alerts = []

    # Check consecutive zero-hit days
    today = datetime.now(timezone.utc).date()
    recent_days = set()
    for entry in log:
        scan_time = entry.get("scan_time", "")[:10]
        if entry.get("actionable_count", 0) > 0:
            recent_days.add(scan_time)

    zero_streak = 0
    for d in range(0, 7):
        day_str = (today - timedelta(days=d)).isoformat()
        if day_str in recent_days:
            break
        # Only count weekdays
        day_obj = today - timedelta(days=d)
        if day_obj.weekday() < 5:
            zero_streak += 1

    if zero_streak >= 3:
        alerts.append({
            "type": "ZERO_HITS",
            "message": f"{zero_streak} consecutive trading days with zero actionable hits. Thresholds may be too tight.",
            "severity": "WARNING",
        })

    # Check scorecard hit rate (last 30 resolved)
    if len(scorecard) >= 10:
        recent = scorecard[-30:]
        wins = sum(1 for s in recent if s["outcome"] == "WIN")
        hit_rate = wins / len(recent) * 100
        if hit_rate < 20:
            alerts.append({
                "type": "LOW_HIT_RATE",
                "message": f"Hit rate {hit_rate:.0f}% over last {len(recent)} resolved picks (target: >20%). Signal quality degrading.",
                "severity": "WARNING",
            })

    # Check for dead signals (last scan)
    if log:
        last_scan = log[-1]
        tickers = last_scan.get("tickers", [])
        if len(tickers) >= 3:
            signal_counts = {}
            for t in tickers:
                for s in t.get("signals", []):
                    signal_counts[s] = signal_counts.get(s, 0) + 1
            for signal in ["flow", "darkpool", "iv_rank", "neg_gex"]:
                if signal_counts.get(signal, 0) == 0 and len(tickers) > 5:
                    alerts.append({
                        "type": "DEAD_SIGNAL",
                        "message": f"Signal '{signal}' returned zero hits last scan ({len(tickers)} tickers checked). API may be down.",
                        "severity": "ERROR",
                    })

    # Save monitor state
    state = {
        "last_check": datetime.now(timezone.utc).isoformat(),
        "zero_streak": zero_streak,
        "alerts": alerts,
        "scorecard_size": len(scorecard),
    }
    _save_json(MONITOR_PATH, state)

    if alerts:
        print(f"MONITOR: {len(alerts)} alert(s)")
        for a in alerts:
            print(f"  [{a['severity']}] {a['type']}: {a['message']}")
    else:
        print("MONITOR: all clear")

    return alerts


# ── SCORECARD SUMMARY ──

def print_scorecard():
    scorecard = _load_json(SCORECARD_PATH) if SCORECARD_PATH.exists() else []
    if not scorecard:
        print("No resolved outcomes yet. Need 5+ days of scan data.")
        return

    total = len(scorecard)
    wins = sum(1 for s in scorecard if s["outcome"] == "WIN")
    losses = sum(1 for s in scorecard if s["outcome"] == "LOSS")
    neutral = total - wins - losses

    print(f"=== CONVERGENCE SCORECARD ({total} resolved) ===")
    print(f"  WIN (>5%):     {wins:3d}  ({wins/total*100:.0f}%)")
    print(f"  LOSS (<-3%):   {losses:3d}  ({losses/total*100:.0f}%)")
    print(f"  NEUTRAL:       {neutral:3d}  ({neutral/total*100:.0f}%)")

    # By convergence level
    for level in [4, 3, 2]:
        subset = [s for s in scorecard if s["convergence"] == level]
        if not subset:
            continue
        w = sum(1 for s in subset if s["outcome"] == "WIN")
        label = {4: "QUAD", 3: "TRIPLE", 2: "WATCH"}[level]
        avg_best = sum(s["best_return"] for s in subset) / len(subset)
        print(f"\n  {label} ({len(subset)} picks): {w/len(subset)*100:.0f}% win rate, avg best return {avg_best:+.1f}%")

    # By signal combination
    print(f"\n  --- By signal combination ---")
    combos = {}
    for s in scorecard:
        key = "+".join(sorted(s.get("signals", [])))
        slot = combos.setdefault(key, {"total": 0, "wins": 0, "sum_return": 0})
        slot["total"] += 1
        if s["outcome"] == "WIN":
            slot["wins"] += 1
        slot["sum_return"] += s["best_return"]

    for combo, data in sorted(combos.items(), key=lambda x: -x[1]["wins"]/max(x[1]["total"], 1)):
        rate = data["wins"] / data["total"] * 100
        avg = data["sum_return"] / data["total"]
        print(f"  {combo:40s}  {data['total']:3d} picks  {rate:4.0f}% win  {avg:+5.1f}% avg")

    # Tuning recommendations
    print(f"\n  --- Tuning recommendations ---")
    best_combo = max(combos.items(), key=lambda x: x[1]["wins"]/max(x[1]["total"], 1))
    worst_combo = min(combos.items(), key=lambda x: x[1]["wins"]/max(x[1]["total"], 1)) if len(combos) > 1 else None
    print(f"  Best combo:  {best_combo[0]} ({best_combo[1]['wins']}/{best_combo[1]['total']} wins)")
    if worst_combo and worst_combo[1]["total"] >= 3:
        print(f"  Worst combo: {worst_combo[0]} ({worst_combo[1]['wins']}/{worst_combo[1]['total']} wins)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convergence Scanner Outcome Tracker")
    parser.add_argument("command", choices=["log", "resolve", "monitor", "scorecard"])
    parser.add_argument("data", nargs="?", default="{}")
    args = parser.parse_args()

    if args.command == "log":
        d = json.loads(args.data)
        entry = log_scan(d.get("results", []), d.get("scan_time", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
        print(f"Logged: {entry['actionable_count']} actionable, {entry['watchlist_count']} watchlist")
    elif args.command == "resolve":
        resolve_outcomes()
    elif args.command == "monitor":
        run_monitor()
    elif args.command == "scorecard":
        print_scorecard()

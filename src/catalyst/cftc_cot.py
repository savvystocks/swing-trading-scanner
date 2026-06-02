"""CFTC Commitments of Traders (COT) Tracker.

Published every Friday at 3:30 PM ET. Tuesday's positioning data, released Friday.
Free download from cftc.gov. $20T futures markets coverage.

This module tracks managed money + asset manager + leveraged fund net positioning
across 7 critical contracts and computes 52-week percentile rank.

Tracked contracts:
  - E-mini S&P 500 (ES) - broad market positioning
  - E-mini Nasdaq 100 (NQ) - tech beta
  - E-mini Russell 2000 (RTY) - small cap positioning
  - VIX futures (VX) - volatility positioning
  - 10Y Treasury (ZN) - rate positioning
  - Crude oil (CL) - energy + risk-on/off proxy
  - US Dollar Index (DX) - currency positioning

Edge:
  Managed money at >85th percentile net long = CROWDED, contrarian short
  Managed money at <15th percentile net long = capitulation, mean reversion long
  Quantpedia + Larry Williams research: +3-5% additional return on COT extremes

Storage: data/cftc_history/<contract>.jsonl
Output: confluence signal cot_extreme (POSITIONING category)
"""

import os
import json
import pathlib
import re
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
COT_HISTORY_DIR = PROJECT_ROOT / "data" / "cftc_history"
COT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# CFTC market codes - dataset endpoint varies by contract type
# TFF (Traders in Financial Futures) covers equity indexes, VIX, currencies
# Disaggregated Futures Only covers commodities (crude, gold etc)
TFF_ENDPOINT = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
DISAGG_ENDPOINT = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

CFTC_CONTRACTS = {
    "ES": {"market_code": "13874A", "label": "E-mini S&P 500", "type": "equity_index", "endpoint": TFF_ENDPOINT},
    "NQ": {"market_code": "209742", "label": "Nasdaq Mini", "type": "equity_index", "endpoint": TFF_ENDPOINT},
    "RTY": {"market_code": "239741", "label": "Russell 2000 Stock Index", "type": "equity_index", "endpoint": TFF_ENDPOINT},
    "VX": {"market_code": "1170E1", "label": "VIX Futures", "type": "volatility", "endpoint": TFF_ENDPOINT},
    "CL": {"market_code": "067411", "label": "WTI Crude Oil", "type": "energy", "endpoint": DISAGG_ENDPOINT},
}

HISTORY_WINDOW_WEEKS = 52


def _history_path(symbol):
    return COT_HISTORY_DIR / f"{symbol}.jsonl"


def _load_history(symbol):
    path = _history_path(symbol)
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _save_history(symbol, rows):
    path = _history_path(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


def fetch_cftc_data(market_code, endpoint, weeks_back=104):
    """Fetch raw CFTC data for a market code from public API."""
    try:
        import requests
        end = datetime.utcnow().date()
        start = end - timedelta(weeks=weeks_back)
        params = {
            "$where": f"cftc_contract_market_code='{market_code}' AND report_date_as_yyyy_mm_dd >= '{start.isoformat()}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 200,
        }
        r = requests.get(endpoint, params=params, timeout=30)
        if r.status_code != 200:
            return []
        data = r.json()
        return data or []
    except Exception:
        return []


def _parse_cot_row(row):
    """Extract managed money + asset manager + leveraged fund nets."""
    try:
        date_str = row.get("report_date_as_yyyy_mm_dd", "")[:10]
        def _num(key):
            v = row.get(key)
            if v is None:
                return 0
            try:
                return int(float(str(v).replace(",", "")))
            except Exception:
                return 0

        mm_long = _num("m_money_positions_long_all")
        mm_short = _num("m_money_positions_short_all")
        am_long = _num("asset_mgr_positions_long")
        am_short = _num("asset_mgr_positions_short")
        lev_long = _num("lev_money_positions_long")
        lev_short = _num("lev_money_positions_short")
        oi = _num("open_interest_all")

        return {
            "date": date_str,
            "managed_money_long": mm_long,
            "managed_money_short": mm_short,
            "managed_money_net": mm_long - mm_short,
            "asset_manager_long": am_long,
            "asset_manager_short": am_short,
            "asset_manager_net": am_long - am_short,
            "leveraged_long": lev_long,
            "leveraged_short": lev_short,
            "leveraged_net": lev_long - lev_short,
            "open_interest": oi,
            "managed_money_net_pct_oi": (mm_long - mm_short) / oi * 100 if oi > 0 else 0,
        }
    except Exception:
        return None


def refresh_contract(symbol, verbose=False):
    """Pull latest CFTC data for a contract, append to history, return current state."""
    config = CFTC_CONTRACTS.get(symbol)
    if not config:
        return None
    raw = fetch_cftc_data(config["market_code"], config["endpoint"])
    if not raw:
        if verbose:
            print(f"  cftc_cot {symbol}: no data returned")
        return None
    parsed_rows = [_parse_cot_row(r) for r in raw]
    parsed_rows = [p for p in parsed_rows if p and p.get("date")]
    parsed_rows.sort(key=lambda x: x["date"])
    _save_history(symbol, parsed_rows)
    if verbose:
        latest = parsed_rows[-1] if parsed_rows else None
        if latest:
            print(f"  cftc_cot {symbol}: refreshed {len(parsed_rows)} weeks, latest {latest['date']}")
    return parsed_rows[-1] if parsed_rows else None


def compute_positioning_percentile(symbol):
    """Return dict with managed_money_pctile, asset_manager_pctile etc. None if insufficient history."""
    history = _load_history(symbol)
    if len(history) < 26:
        return None
    window = history[-HISTORY_WINDOW_WEEKS:]
    current = window[-1]

    def _pctile(values, current_val):
        if not values:
            return 50
        sorted_vals = sorted(values)
        below = sum(1 for v in sorted_vals if v <= current_val)
        return round(below / len(sorted_vals) * 100, 1)

    mm_nets = [w["managed_money_net"] for w in window]
    am_nets = [w["asset_manager_net"] for w in window]
    lev_nets = [w["leveraged_net"] for w in window]

    return {
        "symbol": symbol,
        "label": CFTC_CONTRACTS[symbol]["label"],
        "report_date": current["date"],
        "managed_money_net": current["managed_money_net"],
        "managed_money_pctile": _pctile(mm_nets, current["managed_money_net"]),
        "asset_manager_net": current["asset_manager_net"],
        "asset_manager_pctile": _pctile(am_nets, current["asset_manager_net"]),
        "leveraged_net": current["leveraged_net"],
        "leveraged_pctile": _pctile(lev_nets, current["leveraged_net"]),
        "weeks_history": len(window),
    }


def classify_positioning(pctile_dict):
    """Return regime label + signal direction based on extremes."""
    if not pctile_dict:
        return None
    mm = pctile_dict.get("managed_money_pctile", 50)
    am = pctile_dict.get("asset_manager_pctile", 50)
    lev = pctile_dict.get("leveraged_pctile", 50)

    extreme_long_count = sum(1 for v in (mm, am, lev) if v >= 85)
    extreme_short_count = sum(1 for v in (mm, am, lev) if v <= 15)

    if extreme_long_count >= 2:
        return {
            "regime": "CROWDED_LONG",
            "direction": "CONTRARIAN_SHORT",
            "label": f"{pctile_dict['label']}: Managed money {mm}th %ile + asset mgr {am}th %ile = CROWDED long. Contrarian short bias.",
            "score": 85,
        }
    if extreme_short_count >= 2:
        return {
            "regime": "CROWDED_SHORT",
            "direction": "CONTRARIAN_LONG",
            "label": f"{pctile_dict['label']}: Managed money {mm}th %ile + asset mgr {am}th %ile = CROWDED short. Contrarian long bias.",
            "score": 85,
        }
    if mm >= 75:
        return {
            "regime": "MODERATELY_LONG",
            "direction": "CAUTION_LONG",
            "label": f"{pctile_dict['label']}: Managed money {mm}th %ile = leaning long but not extreme.",
            "score": 60,
        }
    if mm <= 25:
        return {
            "regime": "MODERATELY_SHORT",
            "direction": "CAUTION_SHORT",
            "label": f"{pctile_dict['label']}: Managed money {mm}th %ile = leaning short.",
            "score": 60,
        }
    return {
        "regime": "NEUTRAL",
        "direction": "NEUTRAL",
        "label": f"{pctile_dict['label']}: positioning neutral ({mm}th %ile managed money).",
        "score": 50,
    }


def get_market_positioning_snapshot(refresh=False, verbose=False):
    """Return positioning regime for all 7 contracts."""
    snapshot = {}
    for symbol in CFTC_CONTRACTS.keys():
        if refresh:
            refresh_contract(symbol, verbose=verbose)
        pctile = compute_positioning_percentile(symbol)
        if pctile:
            classification = classify_positioning(pctile)
            snapshot[symbol] = {
                "percentiles": pctile,
                "classification": classification,
            }
    return snapshot


def enrich_picks_with_cot(picks, snapshot=None, verbose=False):
    """For each pick, attach positioning context based on ticker's sector/type.

    Mapping:
      Small-cap pick (mcap <$2B) -> RTY (Russell) positioning
      Tech pick (Technology sector) -> NQ positioning
      Energy pick -> CL positioning
      Financials pick -> ES positioning (broad)
      Any other -> ES positioning
    """
    if not picks:
        return picks
    if snapshot is None:
        snapshot = get_market_positioning_snapshot(refresh=False, verbose=verbose)
    if not snapshot:
        return picks

    es_class = (snapshot.get("ES") or {}).get("classification")
    nq_class = (snapshot.get("NQ") or {}).get("classification")
    rty_class = (snapshot.get("RTY") or {}).get("classification")
    cl_class = (snapshot.get("CL") or {}).get("classification")

    flagged = 0
    for p in picks:
        sector = (p.get("sector") or "").lower()
        mcap = p.get("market_cap") or 0
        try:
            mcap = float(mcap)
        except Exception:
            mcap = 0

        if "technology" in sector or "communication" in sector:
            relevant = nq_class
            contract = "NQ"
        elif "energy" in sector:
            relevant = cl_class
            contract = "CL"
        elif mcap and mcap < 2_000_000_000:
            relevant = rty_class
            contract = "RTY"
        else:
            relevant = es_class
            contract = "ES"

        if relevant:
            p["_cot_positioning"] = {
                "relevant_contract": contract,
                "regime": relevant["regime"],
                "direction": relevant["direction"],
                "label": relevant["label"],
                "score": relevant["score"],
            }
            flagged += 1

    if verbose:
        print(f"  cftc_cot: {flagged} picks tagged with positioning regime")
    return picks

"""Activist 13D Surfacing with Named-Investor Boost.

When a hedge fund crosses the 5% ownership threshold, they file a Schedule 13D
within 10 days. When that filer is a known ACTIVIST (vs passive investor),
the academic edge is enormous:

  Brav, Jiang, Partnoy, Thomas (Columbia): +7% announcement-window abnormal return
  Bebchuk, Brav, Jiang (2015): NO long-term reversal - returns persist
  NYU 2009 study: +10.2% during filing window + 11.4% subsequent year

This module:
1. Scans recent 13D filings via EDGAR full-text search
2. Pattern-matches filer names against a known-activist list
3. Attaches _activist_13d field to picks when a named activist filed on them
4. Feeds confluence detector + catalyst_window auto-scores to 95

Free data - uses existing EDGARClient.
"""

import re
from datetime import datetime, timedelta


# Known activists with aliases. Add new names as they emerge.
# Keys are the canonical name; values are regex patterns matching the
# filer name as it appears in EDGAR display_names.
NAMED_ACTIVISTS = {
    "Carl Icahn": [
        r"\bicahn\b",
        r"icahn capital",
        r"icahn enterprises",
        r"high river limited partnership",
    ],
    "Bill Ackman / Pershing Square": [
        r"pershing square",
        r"\backman\b",
        r"ps capital",
    ],
    "Elliott Investment Management": [
        r"elliott investment management",
        r"elliott associates",
        r"elliott international",
        r"paul singer",
    ],
    "ValueAct Capital": [
        r"valueact",
        r"\bjeffrey ubben\b",
    ],
    "Engaged Capital": [
        r"engaged capital",
        r"glenn welling",
    ],
    "Starboard Value": [
        r"starboard value",
        r"jeffrey smith",
    ],
    "Third Point": [
        r"third point",
        r"daniel loeb",
        r"\bdan loeb\b",
    ],
    "JANA Partners": [
        r"jana partners",
        r"\bbarry rosenstein\b",
    ],
    "Engine Capital": [
        r"engine capital",
        r"\barnaud ajdler\b",
    ],
    "Trian Fund Management": [
        r"trian fund",
        r"trian partners",
        r"nelson peltz",
    ],
    "Sachem Head": [
        r"sachem head",
        r"\bscott ferguson\b",
    ],
    "D.E. Shaw": [
        r"d\.e\.\s*shaw",
        r"\bde shaw\b",
    ],
    "Land & Buildings": [
        r"land\s*&\s*buildings",
        r"\bjonathan litt\b",
    ],
    "Saba Capital": [
        r"saba capital",
        r"boaz weinstein",
    ],
    "Browning West": [
        r"browning west",
    ],
}


def detect_named_activist(display_names_or_text):
    """Pattern-match against named activist list.

    Accepts either a list of display_names or a single text blob.
    Returns the canonical activist name if matched, else None.
    """
    if isinstance(display_names_or_text, list):
        text = " | ".join(display_names_or_text or []).lower()
    else:
        text = str(display_names_or_text or "").lower()
    if not text:
        return None
    for activist, patterns in NAMED_ACTIVISTS.items():
        for pat in patterns:
            if re.search(pat, text, flags=re.IGNORECASE):
                return activist
    return None


def collect_activist_13d_filings(edgar_client, days_back=14):
    """Scan recent 13D filings, detect activist filers, return dict by ticker.

    Returns: {ticker: {filings: [...], activist_name: str or None, fires: bool, ...}}
    """
    results = {}
    try:
        hits = edgar_client.search(["SCHEDULE 13D", "SCHEDULE 13D/A"], days_back=days_back, max_results=200)
    except Exception:
        return results

    for h in hits or []:
        ticker = h.get("ticker")
        if not ticker:
            continue

        raw_hit = h.get("_raw")
        display_names = []
        if isinstance(raw_hit, dict):
            src = raw_hit.get("_source") or {}
            display_names = src.get("display_names") or []
        else:
            display_names = [h.get("company", "")]

        activist = detect_named_activist(display_names)
        is_amendment = "13D/A" in (h.get("form") or "")

        entry = results.setdefault(ticker, {
            "ticker": ticker,
            "company": h.get("company"),
            "filings": [],
            "activist_name": None,
            "fires": False,
            "is_amendment": False,
        })
        entry["filings"].append({
            "form": h.get("form"),
            "date": h.get("date"),
            "accession": h.get("accession"),
            "display_names": display_names,
            "matched_activist": activist,
        })
        if activist:
            entry["activist_name"] = activist
            entry["fires"] = True
        if is_amendment:
            entry["is_amendment"] = True

    return results


def enrich_picks_with_activist_13d(picks, edgar_client, days_back=14, verbose=False):
    """For each pick, check if a named activist recently filed 13D on it."""
    if not picks:
        return picks
    try:
        index = collect_activist_13d_filings(edgar_client, days_back=days_back)
    except Exception as e:
        if verbose:
            print(f"  activist_13d index failed: {type(e).__name__}: {e}")
        return picks

    if not index:
        if verbose:
            print(f"  activist_13d: no 13D filings in last {days_back}d")
        return picks

    hits = 0
    named_hits = 0
    for p in picks:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        entry = index.get(ticker)
        if not entry:
            continue

        p["_activist_13d"] = {
            "fires": entry["fires"],
            "name": entry.get("activist_name"),
            "is_amendment": entry.get("is_amendment", False),
            "filings_count": len(entry.get("filings") or []),
            "most_recent_date": (entry.get("filings") or [{}])[-1].get("date"),
        }
        hits += 1
        if entry["fires"]:
            named_hits += 1
            try:
                fc = p.get("_forward_catalyst") or {}
                fc["activist_overlay"] = True
                fc["window_score"] = 95
                fc["type"] = "activist_13d"
                fc["details"] = f"{entry['activist_name']} disclosed 5%+ stake"
                p["_forward_catalyst"] = fc
            except Exception:
                pass

    if verbose:
        print(f"  activist_13d: {hits} picks have recent 13D, {named_hits} matched named activists")
    return picks

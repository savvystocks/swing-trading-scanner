import os
import re
import time
import json
import pathlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime


SEC_RSS_BASE = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
SEEN_FILE = pathlib.Path(__file__).parent.parent.parent / "data" / "catalyst" / "edgar_rss_seen.json"

UA = "Catalyst-Scanner savvastgeorgiou@gmail.com"

ALERT_FORM_TYPES = {
    "8-K": "Material event",
    "8-K/A": "Material event amended",
    "13D": "Activist stake (>5%)",
    "13D/A": "Activist stake update",
    "13G": "Passive >5% stake",
    "4": "Insider transaction",
    "S-3": "Shelf registration (dilution risk)",
    "424B5": "Pricing supplement (dilution)",
    "8-K12B": "Material event - registration",
}


def _load_seen():
    if not SEEN_FILE.exists():
        return set()
    try:
        with open(SEEN_FILE) as f:
            data = json.load(f)
        cutoff = time.time() - 7 * 86400
        return {k for k, v in data.items() if v >= cutoff}
    except Exception:
        return set()


def _save_seen(seen_dict):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 7 * 86400
    seen_dict = {k: v for k, v in seen_dict.items() if v >= cutoff}
    with open(SEEN_FILE, "w") as f:
        json.dump(seen_dict, f, indent=2)


def fetch_recent_filings(form_types=None, count=100):
    if form_types is None:
        form_types = list(ALERT_FORM_TYPES.keys())
    out = []
    for ft in form_types:
        url = f"{SEC_RSS_BASE}&type={ft}&output=atom&count={count}"
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            r.raise_for_status()
        except Exception:
            continue
        try:
            root = ET.fromstring(r.text)
        except Exception:
            continue
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "", ns)
            updated = entry.findtext("atom:updated", "", ns)
            link_elem = entry.find("atom:link", ns)
            link = link_elem.get("href") if link_elem is not None else ""
            company_match = re.search(r"\((\d{10})\)\s+\(Filer\)", title)
            cik = company_match.group(1) if company_match else None
            ticker_match = re.search(r"\(([A-Z]{1,5})\)", title)
            ticker = ticker_match.group(1) if ticker_match else None
            company_match2 = re.match(r"^[\w\-]+\s+-\s+(.+?)\s+\(", title)
            company = company_match2.group(1) if company_match2 else ""

            entry_id = entry.findtext("atom:id", "", ns)
            out.append({
                "form_type": ft,
                "title": title,
                "company": company,
                "ticker": ticker,
                "cik": cik,
                "filed_at": updated,
                "link": link,
                "id": entry_id,
            })
    return out


def filter_to_watchlist(filings, watchlist_tickers):
    if not watchlist_tickers:
        return []
    wl = {t.upper() for t in watchlist_tickers}
    return [f for f in filings if f.get("ticker") in wl]


def detect_new_filings(filings, seen_dict):
    new = []
    now = time.time()
    for f in filings:
        fid = f.get("id") or f"{f.get('cik')}_{f.get('filed_at')}_{f.get('form_type')}"
        if fid in seen_dict:
            continue
        seen_dict[fid] = now
        new.append(f)
    return new


def alert_message(filing):
    form = filing["form_type"]
    label = ALERT_FORM_TYPES.get(form, form)
    ticker = filing.get("ticker") or "?"
    company = filing.get("company", "")[:60]
    link = filing.get("link", "")
    return (
        f"SEC ALERT: {ticker} ({company}) — {label} ({form})\n"
        f"Filed: {filing.get('filed_at', '')}\n"
        f"{link}"
    )


def poll_and_alert(watchlist_tickers, telegram_callback=None, verbose=False):
    seen = {}
    seen_set = _load_seen()
    seen.update({k: time.time() for k in seen_set})
    filings = fetch_recent_filings()
    if verbose:
        print(f"  edgar_rss: pulled {len(filings)} recent filings")
    relevant = filter_to_watchlist(filings, watchlist_tickers)
    new_filings = detect_new_filings(relevant, seen)
    if verbose:
        print(f"  edgar_rss: {len(relevant)} on watchlist, {len(new_filings)} new")
    sent = 0
    for f in new_filings:
        msg = alert_message(f)
        if telegram_callback:
            try:
                telegram_callback(msg)
                sent += 1
            except Exception as e:
                if verbose:
                    print(f"    telegram alert failed: {type(e).__name__}: {e}")
        elif verbose:
            print(f"    [NEW] {msg[:120]}")
    _save_seen(seen)
    return new_filings, sent

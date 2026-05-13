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


BULLISH_FORMS = {"8-K", "8-K/A", "13D", "13D/A", "13G", "4", "8-K12B"}
BEARISH_FORMS = {"S-3", "424B5", "S-3/A"}


def score_alert_priority(filing, latest_scan=None):
    ticker = (filing.get("ticker") or "").upper()
    form = filing.get("form_type", "")
    if not ticker:
        return ("SKIP", "no ticker parsed")

    priority = "LOW"
    reasons = []

    if latest_scan and isinstance(latest_scan, dict):
        aa = latest_scan.get("aa_results") or {}
        for tier in ("A++", "A+"):
            picks = aa.get(tier, [])
            for p in picks:
                if (p.get("ticker") or "").upper() == ticker:
                    priority = "HIGH"
                    reasons.append(f"in v4 scan as {tier}")
                    break
            if priority == "HIGH":
                break
        if priority != "HIGH":
            a_picks = aa.get("A", [])
            for p in a_picks:
                if (p.get("ticker") or "").upper() == ticker:
                    priority = "MED"
                    reasons.append("in v4 scan as A")
                    break

    if form in BULLISH_FORMS:
        if priority == "LOW":
            priority = "MED"
        reasons.append(f"bullish form ({form})")
    elif form in BEARISH_FORMS:
        if priority == "HIGH":
            priority = "MED"
        reasons.append(f"bearish-bias form ({form})")

    return (priority, "; ".join(reasons))


def alert_message(filing, latest_scan=None, priority=None, reason=None):
    form = filing["form_type"]
    label = ALERT_FORM_TYPES.get(form, form)
    ticker = filing.get("ticker") or "?"
    company = filing.get("company", "")[:60]
    link = filing.get("link", "")

    pri_label = ""
    if priority == "HIGH":
        pri_label = "[HIGH PRIORITY] "
    elif priority == "MED":
        pri_label = "[MED] "

    tier_context = ""
    if latest_scan and isinstance(latest_scan, dict):
        aa = latest_scan.get("aa_results") or {}
        for tier in ("A++", "A+", "A"):
            for p in aa.get(tier, []):
                if (p.get("ticker") or "").upper() == (ticker or "").upper():
                    cats = p.get("catalysts") or []
                    cat_keys = [c.get("key", "") for c in cats[:4] if isinstance(c, dict)]
                    spot = p.get("live_spot") or p.get("price") or "?"
                    sm = p.get("_smart_money_signals") or []
                    tier_context = (
                        f"\nV4 tier: {tier} · Score: {int(p.get('_stacked_score') or 0)} · "
                        f"Cats: {p.get('_category_count', 0)} ({', '.join(cat_keys)}) · "
                        f"Smart money: {len(sm)} signal(s)\n"
                        f"Spot: ${spot}"
                    )
                    break
            if tier_context:
                break

    base = (
        f"{pri_label}SEC ALERT: {ticker} ({company}) -- {label} ({form})\n"
        f"Filed: {filing.get('filed_at', '')}\n"
        f"{link}"
    )
    if tier_context:
        base += tier_context
    if reason:
        base += f"\nReason: {reason}"
    return base


def poll_and_alert(watchlist_tickers, telegram_callback=None, verbose=False, latest_scan=None, min_priority="MED"):
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

    priority_order = {"HIGH": 3, "MED": 2, "LOW": 1, "SKIP": 0}
    min_pri_score = priority_order.get(min_priority, 2)

    sent = 0
    skipped = 0
    by_priority = {"HIGH": 0, "MED": 0, "LOW": 0, "SKIP": 0}
    for f in new_filings:
        pri, reason = score_alert_priority(f, latest_scan=latest_scan)
        by_priority[pri] = by_priority.get(pri, 0) + 1
        if priority_order.get(pri, 0) < min_pri_score:
            skipped += 1
            if verbose:
                print(f"    [SKIP {pri}] {f.get('ticker')} {f.get('form_type')}")
            continue
        msg = alert_message(f, latest_scan=latest_scan, priority=pri, reason=reason)
        if telegram_callback:
            try:
                telegram_callback(msg)
                sent += 1
                if verbose:
                    print(f"    [SENT {pri}] {f.get('ticker')} {f.get('form_type')}")
            except Exception as e:
                if verbose:
                    print(f"    telegram alert failed: {type(e).__name__}: {e}")
        elif verbose:
            print(f"    [NEW {pri}] {msg[:120]}")
    if verbose:
        print(f"  edgar_rss: by priority: HIGH={by_priority['HIGH']} MED={by_priority['MED']} LOW={by_priority['LOW']} SKIP={by_priority['SKIP']}")
        print(f"  edgar_rss: sent={sent}, skipped (below {min_priority})={skipped}")
    _save_seen(seen)
    return new_filings, sent


def load_latest_scan_for_alerts():
    import glob
    results_dir = pathlib.Path(__file__).parent.parent.parent / "data" / "results"
    pattern = str(results_dir / "catalyst_*.json")
    files = sorted([f for f in glob.glob(pattern) if "_email" not in os.path.basename(f) and "_morning" not in os.path.basename(f)], reverse=True)
    if not files:
        return None
    try:
        with open(files[0]) as f:
            return json.load(f)
    except Exception:
        return None

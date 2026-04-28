import os
import re
import time
import json
import hashlib
import pathlib
import requests

EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
USER_AGENT = "SwingTradingScanner savvastgeorgiou@gmail.com"
CACHE_DIR = pathlib.Path(__file__).parent.parent.parent / "data" / "cache_edgar"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MATERIAL_8K_ITEMS = {"1.01", "1.02", "2.01", "2.02", "2.03", "3.02", "5.02", "5.07", "8.01"}

ITEM_LABELS = {
    "1.01": "material definitive agreement",
    "1.02": "termination of agreement",
    "2.01": "asset acquisition or disposition",
    "2.02": "earnings results",
    "2.03": "material financial obligation",
    "3.01": "delisting risk",
    "3.02": "private placement",
    "5.02": "leadership change",
    "5.07": "shareholder vote",
    "7.01": "regulation FD disclosure",
    "8.01": "other material event",
}


class EDGARClient:
    def __init__(self, cache_minutes=30):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.cache_seconds = cache_minutes * 60
        self.calls_made = 0

    def _cache_path(self, params):
        key = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
        return CACHE_DIR / f"{key}.json"

    def _get(self, params, use_cache=True):
        cache_file = self._cache_path(params)
        if use_cache and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < self.cache_seconds:
                return json.loads(cache_file.read_text())
        for attempt in range(3):
            try:
                r = self.session.get(EDGAR_SEARCH, params=params, timeout=30)
                self.calls_made += 1
                if r.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                data = r.json()
                cache_file.write_text(json.dumps(data))
                return data
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def search(self, forms, query="", days_back=2, end_date=None, max_results=200):
        from datetime import datetime, timedelta
        end = end_date or datetime.utcnow().date()
        if isinstance(end, str):
            end = datetime.strptime(end, "%Y-%m-%d").date()
        start = end - timedelta(days=days_back)
        params = {
            "q": query,
            "forms": ",".join(forms) if isinstance(forms, list) else forms,
            "dateRange": "custom",
            "startdt": start.strftime("%Y-%m-%d"),
            "enddt": end.strftime("%Y-%m-%d"),
        }
        data = self._get(params)
        if not data:
            return []
        hits = (data.get("hits") or {}).get("hits") or []
        out = []
        for h in hits[:max_results]:
            parsed = self._parse_hit(h)
            if parsed:
                out.append(parsed)
        return out

    def _parse_hit(self, hit):
        src = hit.get("_source") or {}
        names = src.get("display_names") or []
        ticker = None
        company = ""
        for n in names:
            m = re.search(r"\(([A-Z][A-Z0-9.\-]{0,9})\)", n)
            if m:
                candidate = m.group(1)
                if candidate not in ("CIK",):
                    ticker = candidate
                    company = re.sub(r"\s*\(.*?\)\s*", "", n).strip()
                    break
        return {
            "ticker": ticker,
            "company": company,
            "cik": (src.get("ciks") or [None])[0],
            "form": src.get("form"),
            "date": src.get("file_date"),
            "items": src.get("items") or [],
            "accession": hit.get("_id", "").split(":")[0],
        }


def collect_material_signals(client, days_back=2, end_date=None):
    out = {}
    queries = [
        ('"definitive agreement"', "definitive_agreement"),
        ('"private placement"', "private_placement"),
        ('"merger agreement"', "merger"),
        ('"asset purchase agreement"', "asset_sale"),
        ('"phase 3" OR "phase 2/3" OR "phase 1/2"', "clinical_milestone"),
        ('"FDA approval" OR "PDUFA" OR "Breakthrough Therapy"', "fda_event"),
        ('"strategic alliance" OR "strategic partnership"', "strategic_partnership"),
        ('"contract award" OR "tender award"', "contract_win"),
        ('"forbearance agreement" OR "credit agreement amendment"', "covenant_relief"),
        ('"name change" OR "ticker change"', "rebrand"),
        ('"share repurchase" OR "buyback program"', "buyback"),
    ]
    forms = ["8-K", "6-K"]
    for q, label in queries:
        try:
            hits = client.search(forms, query=q, days_back=days_back, end_date=end_date, max_results=120)
            for h in hits:
                if not h.get("ticker"):
                    continue
                t = h["ticker"]
                if t not in out:
                    out[t] = {"ticker": t, "company": h["company"], "filings": []}
                out[t]["filings"].append({
                    "form": h.get("form"),
                    "date": h["date"],
                    "match": label,
                    "items": h.get("items") or [],
                    "accession": h["accession"],
                })
        except Exception as e:
            print(f"  edgar material search failed ({label}): {type(e).__name__}: {e}")
    return out


collect_8k_signals = collect_material_signals


def collect_13d_signals(client, days_back=10, end_date=None):
    out = {}
    try:
        hits = client.search(["SCHEDULE 13D", "SCHEDULE 13D/A"], days_back=days_back, end_date=end_date, max_results=200)
        for h in hits:
            if not h.get("ticker"):
                continue
            t = h["ticker"]
            if t not in out:
                out[t] = {"ticker": t, "company": h["company"], "filings": []}
            out[t]["filings"].append({
                "form": h["form"],
                "date": h["date"],
                "match": "activist_stake",
                "accession": h["accession"],
            })
    except Exception as e:
        print(f"  edgar 13D search failed: {type(e).__name__}: {e}")
    return out


def collect_form4_cluster(client, days_back=14, end_date=None, min_buyers=3):
    by_ticker = {}
    try:
        hits = client.search(["4"], days_back=days_back, end_date=end_date, max_results=400)
        for h in hits:
            if not h.get("ticker"):
                continue
            t = h["ticker"]
            by_ticker.setdefault(t, []).append(h)
    except Exception as e:
        print(f"  edgar Form 4 search failed: {type(e).__name__}: {e}")
        return {}
    out = {}
    for t, filings in by_ticker.items():
        unique_ciks = {f.get("cik") for f in filings if f.get("cik")}
        if len(unique_ciks) >= min_buyers:
            out[t] = {
                "ticker": t,
                "company": filings[0]["company"],
                "buyer_count": len(unique_ciks),
                "filing_count": len(filings),
                "filings": filings[:10],
            }
    return out

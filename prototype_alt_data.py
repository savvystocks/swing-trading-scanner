"""V10 Research Sandbox - Alternative Data Prototype (STANDALONE, wired to nothing).

Two genuinely-free, ZERO-API-KEY edges for the 3-5 day options momentum strategy,
chosen because they are orthogonal to our existing UW (institutional flow) + Alpaca
(price/volume) stack:

  EDGE 1 - Retail attention spikes  (ApeWisdom / Reddit)  -> the crowd catalyst
  EDGE 2 - Insider Form 4 buys       (SEC EDGAR)            -> the smart-money catalyst

No paid keys, no signup, urllib only (no new dependencies). This file does not import
or touch any V9 engine module. Run it directly: python prototype_alt_data.py
"""

import re
import json
import time
import urllib.request
from datetime import datetime, timedelta

UA = {"User-Agent": "v10-research-sandbox swing research (savvastgeorgiou@gmail.com)"}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _get_json(url, timeout=20):
    return json.loads(_get(url, timeout))


# ----------------------------------------------------------------------------
# EDGE 1 - Reddit retail attention (ApeWisdom, free / no key)
#   apewisdom.io aggregates WSB + investing subreddits. The 24h mention + rank
#   deltas are the signal: a ticker lighting up is a fast retail momentum catalyst.
# ----------------------------------------------------------------------------
APEWISDOM = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/{p}"


def reddit_attention(max_pages=3):
    rows = []
    for p in range(1, max_pages + 1):
        try:
            d = _get_json(APEWISDOM.format(p=p))
        except Exception:
            break
        for r in d.get("results", []):
            m = r.get("mentions") or 0
            m24 = r.get("mentions_24h_ago") or 0
            spike = ((m - m24) / m24 * 100.0) if m24 else (100.0 if m else 0.0)
            rank, rank24 = r.get("rank"), r.get("rank_24h_ago")
            rows.append({
                "ticker": r.get("ticker"),
                "mentions": m,
                "mentions_24h_ago": m24,
                "mention_spike_pct": round(spike, 1),
                "rank": rank,
                "rank_24h_ago": rank24,
                "rank_jump": (rank24 - rank) if (rank and rank24) else None,
                "upvotes": r.get("upvotes"),
            })
    return rows


def reddit_spikes(min_mentions=40, min_spike_pct=80):
    """The fast retail catalyst: meaningful mention count AND a sharp 24h jump."""
    spikes = [r for r in reddit_attention()
              if r["mentions"] >= min_mentions and r["mention_spike_pct"] >= min_spike_pct]
    spikes.sort(key=lambda x: x["mention_spike_pct"], reverse=True)
    return spikes


def reddit_for(ticker):
    """Cross-reference a single scanner candidate against Reddit attention."""
    t = (ticker or "").upper().split(".")[0]
    for r in reddit_attention(max_pages=11):
        if r["ticker"] == t:
            return r
    return None


# ----------------------------------------------------------------------------
# EDGE 2 - SEC EDGAR insider Form 4 buys (free / no key)
#   SEC publishes Form 4 within ~1s of acceptance, so a poller always catches
#   fresh insider transactions same-day. Code 'P' = open-market purchase = the
#   bullish 3-5 day catalyst (a cluster of execs buying their own stock).
# ----------------------------------------------------------------------------
_CIK = {"map": None}


def _ticker_to_cik(ticker):
    if _CIK["map"] is None:
        try:
            m = _get_json("https://www.sec.gov/files/company_tickers.json")
            _CIK["map"] = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in m.values()}
        except Exception:
            _CIK["map"] = {}
    return _CIK["map"].get((ticker or "").upper().split(".")[0])


def recent_insider_form4(ticker, lookback_days=21, max_filings=8, polite=0.12):
    cik = _ticker_to_cik(ticker)
    if not cik:
        return {"ticker": ticker, "error": "CIK not found"}
    sub = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    rec = sub.get("filings", {}).get("recent", {})
    cutoff = (datetime.utcnow().date() - timedelta(days=lookback_days)).isoformat()
    events, n = [], 0
    for i in range(len(rec.get("form", []))):
        if rec["form"][i] != "4" or rec["filingDate"][i] < cutoff:
            continue
        if n >= max_filings:
            break
        n += 1
        acc = rec["accessionNumber"][i].replace("-", "")
        fname = rec["primaryDocument"][i].split("/")[-1]  # strip xsl viewer prefix -> raw XML
        try:
            xml = _get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{fname}")
            time.sleep(polite)
        except Exception:
            continue
        codes = re.findall(r"<transactionCode>\s*([A-Z])\s*</transactionCode>", xml)
        sh = re.findall(r"<transactionShares>\s*<value>([\d.]+)</value>", xml)
        owner = re.search(r"<rptOwnerName>\s*([^<]+?)\s*</rptOwnerName>", xml)
        is_dir = "<isDirector>1</isDirector>" in xml
        is_off = "<isOfficer>1</isOfficer>" in xml
        events.append({
            "filed": rec["filingDate"][i],
            "owner": owner.group(1).strip() if owner else None,
            "role": "/".join([r for r in (("director" if is_dir else None),
                                          ("officer" if is_off else None)) if r]) or "other",
            "codes": codes,
            "purchases": codes.count("P"),
            "sales": codes.count("S"),
            "shares": [float(s) for s in sh[:6]],
        })
    buys = sum(e["purchases"] for e in events)
    return {
        "ticker": ticker, "cik": cik, "form4_count": len(events),
        "open_market_purchases": buys, "events": events,
        "signal": "INSIDER_BUY_CLUSTER" if buys >= 2 else ("INSIDER_BUY" if buys else "none"),
    }


# ----------------------------------------------------------------------------
# DEMO + latency probe
# ----------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("V10 ALT-DATA PROTOTYPE  -  retail attention + insider Form 4")
    print("standalone | zero API keys | urllib only | wired to nothing")
    print("=" * 72)

    print("\n--- EDGE 1: Reddit attention spikes (ApeWisdom) ---")
    t = time.time()
    spikes = reddit_spikes()
    print(f"  fetched 3 pages in {time.time() - t:.2f}s -> {len(spikes)} spike(s):")
    for r in spikes[:8]:
        print(f"    {r['ticker']:<6} mentions {r['mentions']:>5} (was {r['mentions_24h_ago']}, "
              f"+{r['mention_spike_pct']:.0f}%)  rank {r['rank']} (was {r['rank_24h_ago']})")

    print("\n  cross-reference scanner candidates:")
    for tk in ("NVDA", "MU", "AMD"):
        r = reddit_for(tk)
        print(f"    {tk:<5} {('mentions %s (+%.0f%%) rank %s' % (r['mentions'], r['mention_spike_pct'], r['rank'])) if r else 'not in Reddit top mentions'}")

    print("\n--- EDGE 2: Insider Form 4 buys (SEC EDGAR) ---")
    for tk in ("NVDA", "AAPL"):
        t = time.time()
        res = recent_insider_form4(tk)
        print(f"    {tk:<5} {res.get('form4_count')} Form4 in 21d, "
              f"{res.get('open_market_purchases')} open-market purchases -> {res.get('signal')} "
              f"({time.time() - t:.2f}s)")
        for e in res.get("events", [])[:2]:
            print(f"        {e['filed']} {e['owner']} ({e['role']}) codes={e['codes']} "
                  f"P={e['purchases']} S={e['sales']}")


if __name__ == "__main__":
    main()

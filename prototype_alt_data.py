"""V10 Research Sandbox - Alternative Data Prototype (STANDALONE, wired to nothing).

Two genuinely-free, ZERO-API-KEY edges orthogonal to our UW (institutional flow) +
Alpaca (price/volume) stack, for the 3-5 day options momentum strategy:

  EDGE 1 - Retail attention spikes  (ApeWisdom / Reddit)  -> the crowd catalyst
  EDGE 2 - Insider Form 4 buys       (SEC EDGAR/edgartools)-> the smart-money catalyst

EDGE 2 now uses the edgartools library (production-grade Form 4 parsing) and extracts
the exact Share Count + Dollar Value of open-market purchases (code 'P'), filtering out
nominal/DRIP noise and routine RSU/option activity (codes F/M/S).

No paid keys, no signup. Does not import or touch any V9 engine module.
Run directly: python prototype_alt_data.py     (needs: pip install edgartools)
"""

import json
import time
import math
import urllib.request
from datetime import datetime, timedelta

UA = {"User-Agent": "v10-research-sandbox swing research (savvastgeorgiou@gmail.com)"}
SEC_IDENTITY = "Savvas Georgiou savvastgeorgiou@gmail.com"


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# EDGE 1 - Reddit retail attention (ApeWisdom, free / no key)
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
                "ticker": r.get("ticker"), "mentions": m, "mentions_24h_ago": m24,
                "mention_spike_pct": round(spike, 1), "rank": rank, "rank_24h_ago": rank24,
                "rank_jump": (rank24 - rank) if (rank and rank24) else None,
                "upvotes": r.get("upvotes"),
            })
    return rows


def reddit_attention_map(max_pages=11):
    """One market-wide fetch -> {TICKER: attention dict}. Efficient for batch enrichment."""
    return {r["ticker"]: r for r in reddit_attention(max_pages=max_pages)}


def reddit_spikes(min_mentions=40, min_spike_pct=80):
    spikes = [r for r in reddit_attention()
              if r["mentions"] >= min_mentions and r["mention_spike_pct"] >= min_spike_pct]
    spikes.sort(key=lambda x: x["mention_spike_pct"], reverse=True)
    return spikes


# ----------------------------------------------------------------------------
# EDGE 2 - SEC EDGAR insider Form 4 buys (edgartools, free / no key)
#   Code 'P' = open-market purchase = the bullish 3-5d catalyst. Filters nominal
#   (<min_value, e.g. $0.02 DRIP entries) and routine RSU/option codes (F/M/S).
# ----------------------------------------------------------------------------
_EDGAR = {"ready": False}


def _ensure_edgar():
    if not _EDGAR["ready"]:
        from edgar import set_identity
        set_identity(SEC_IDENTITY)
        _EDGAR["ready"] = True


def insider_open_market_buys(ticker, lookback_days=90, min_value=25000):
    from edgar import Company
    _ensure_edgar()
    cutoff = (datetime.utcnow().date() - timedelta(days=lookback_days)).isoformat()
    t = (ticker or "").upper().split(".")[0]
    try:
        fs = Company(t).get_filings(form="4", filing_date=f"{cutoff}:")
    except Exception as e:
        return {"ticker": ticker, "signal": "none", "error": type(e).__name__, "buys": [],
                "n_buys": 0, "n_insiders": 0, "total_value": 0}
    buys, insiders = [], set()
    for f in fs:
        try:
            df = f.obj().to_dataframe()
        except Exception:
            continue
        for _, r in df[df["Code"] == "P"].iterrows():
            sh = _num(r.get("Shares")) or 0.0
            price = _num(r.get("Price")) or 0.0
            val = _num(r.get("Value"))
            if val is None:
                val = sh * price
            if val < min_value:                     # drop nominal / DRIP / issuer noise
                continue
            name = str(r.get("Insider") or "").strip()
            buys.append({"date": str(r.get("Date"))[:10], "insider": name,
                         "position": r.get("Position"), "shares": int(sh),
                         "price": round(price, 2), "value": round(val, 0)})
            insiders.add(name)
    buys.sort(key=lambda b: b["date"], reverse=True)
    signal = "INSIDER_BUY_CLUSTER" if len(insiders) >= 2 else ("INSIDER_BUY" if buys else "none")
    return {
        "ticker": ticker, "n_buys": len(buys), "n_insiders": len(insiders),
        "total_shares": sum(b["shares"] for b in buys),
        "total_value": sum(b["value"] for b in buys),
        "latest_buy": buys[0]["date"] if buys else None,
        "signal": signal, "buys": buys[:5],
    }


# ----------------------------------------------------------------------------
# DEMO
# ----------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("V10 ALT-DATA PROTOTYPE  -  retail attention + insider Form 4 (edgartools)")
    print("standalone | zero API keys | wired to nothing")
    print("=" * 72)

    print("\n--- EDGE 1: Reddit attention spikes (ApeWisdom) ---")
    t = time.time()
    spikes = reddit_spikes()
    print(f"  {len(spikes)} spike(s) in {time.time() - t:.2f}s:")
    for r in spikes[:6]:
        print(f"    {r['ticker']:<6} {r['mentions']:>5} mentions (was {r['mentions_24h_ago']}, "
              f"+{r['mention_spike_pct']:.0f}%)  rank {r['rank']}<-{r['rank_24h_ago']}")

    print("\n--- EDGE 2: Insider open-market buys (SEC EDGAR / edgartools) ---")
    for tk in ("HOOD", "SOFI", "NVDA"):
        t = time.time()
        res = insider_open_market_buys(tk)
        print(f"    {tk:<5} {res['signal']:<20} {res['n_buys']} buys / {res['n_insiders']} insiders / "
              f"${res['total_value']:,.0f}  ({time.time() - t:.1f}s)")
        for b in res["buys"][:2]:
            print(f"        {b['date']} {b['insider'][:30]:<30} {b['shares']:>8,} @ ${b['price']} = ${b['value']:,.0f}")


if __name__ == "__main__":
    main()

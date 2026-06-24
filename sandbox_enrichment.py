"""V10 Research Sandbox - alt-data enrichment + correlation test (STANDALONE).

Part A: take a mocked "Top 5 Survivors" payload (the shape run_scan produces after
        _cheap_pass) and enrich it efficiently with ApeWisdom + insider Form 4.
Part B: a lightweight correlation test - 5 hypothesized momentum runners vs 5
        flat/chop names - showing whether the alt-data signals fired on the movers.

Wired to nothing. Imports only the sandbox prototype (no V9 engine).
Run: python sandbox_enrichment.py
"""

import time

from prototype_alt_data import reddit_attention_map, insider_open_market_buys


# ----------------------------------------------------------------------------
# Part A - Top-5 survivor enrichment
# ----------------------------------------------------------------------------
def mock_top5_survivors():
    """Mirrors run_scan's post-_cheap_pass candidate shape (subset of fields)."""
    return [
        {"ticker": "HOOD", "side": "CALL", "spot": 83.5, "premium": 3_200_000, "flow_dominance_pct": 78},
        {"ticker": "SOFI", "side": "CALL", "spot": 18.2, "premium": 1_500_000, "flow_dominance_pct": 66},
        {"ticker": "WEN",  "side": "CALL", "spot": 12.1, "premium": 900_000,   "flow_dominance_pct": 61},
        {"ticker": "NVDA", "side": "CALL", "spot": 132.5, "premium": 8_700_000, "flow_dominance_pct": 73},
        {"ticker": "MU",   "side": "PUT",  "spot": 110.0, "premium": 2_100_000, "flow_dominance_pct": 59},
    ]


def enrich_survivors(survivors):
    reddit = reddit_attention_map()          # ONE market-wide fetch for all 5 (efficient)
    out = []
    for c in survivors:
        t = c["ticker"]
        ra = reddit.get(t)
        ib = insider_open_market_buys(t, lookback_days=60)
        reddit_confirm = bool(ra and ra["mentions"] >= 30 and ra["mention_spike_pct"] >= 50)
        insider_confirm = ib["signal"] != "none"
        # illustrative conviction modifier (same spirit as the options-flow +/-0.5 tier rule)
        boost = round(0.5 * reddit_confirm + 0.5 * insider_confirm, 1)
        out.append({**c,
                    "reddit": (f"{ra['mentions']}m +{ra['mention_spike_pct']:.0f}% #{ra['rank']}" if ra else "-"),
                    "reddit_confirm": reddit_confirm,
                    "insider": ib["signal"], "insider_value": ib["total_value"],
                    "insider_confirm": insider_confirm,
                    "altdata_boost": boost})
    return out


# ----------------------------------------------------------------------------
# Part B - correlation test
# ----------------------------------------------------------------------------
def price_moves(ticker):
    import yfinance as yf
    try:
        h = yf.Ticker(ticker).history(period="2mo")
        closes = [c for c in h["Close"].tolist() if c == c]
    except Exception:
        return None
    if len(closes) < 21:
        return None
    last = closes[-1]
    ret5 = (last / closes[-6] - 1) * 100
    ret20 = (last / closes[-21] - 1) * 100
    max5 = max((closes[i] / closes[i - 5] - 1) * 100 for i in range(5, len(closes)))
    return {"last": round(last, 2), "ret5": round(ret5, 1),
            "ret20": round(ret20, 1), "max5d_run": round(max5, 1)}


def correlation_test(runners, chop):
    reddit = reddit_attention_map()
    rows = []
    for group, tickers in (("RUNNER", runners), ("CHOP", chop)):
        for t in tickers:
            pm = price_moves(t) or {}
            ra = reddit.get(t)
            ib = insider_open_market_buys(t, lookback_days=60)
            reddit_sig = bool(ra and ra["mentions"] >= 30 and ra["mention_spike_pct"] >= 50)
            insider_sig = ib["signal"] != "none"
            rows.append({
                "ticker": t, "group": group,
                "ret5": pm.get("ret5"), "ret20": pm.get("ret20"), "run": pm.get("max5d_run"),
                "reddit": (f"{ra['mentions']}m/+{ra['mention_spike_pct']:.0f}%" if ra else "-"),
                "reddit_sig": reddit_sig,
                "insider": ib["signal"].replace("INSIDER_BUY", "BUY").replace("_CLUSTER", "+CLUS").replace("none", "-"),
                "insider_date": ib.get("latest_buy") or "-",
                "insider_sig": insider_sig,
                "any_sig": reddit_sig or insider_sig,
            })
    return rows


def _print_table(rows):
    hdr = f"{'ticker':<6}{'grp':<7}{'5d%':>7}{'20d%':>7}{'maxrun%':>9}  {'reddit':<14}{'rd?':<5}{'insider':<8}{'buy_date':<12}{'in?':<5}{'SIGNAL':<5}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['ticker']:<6}{r['group']:<7}"
              f"{(r['ret5'] if r['ret5'] is not None else 0):>7.1f}{(r['ret20'] if r['ret20'] is not None else 0):>7.1f}"
              f"{(r['run'] if r['run'] is not None else 0):>9.1f}  {r['reddit']:<14}{('YES' if r['reddit_sig'] else '.'):<5}"
              f"{r['insider']:<8}{r['insider_date']:<12}{('YES' if r['insider_sig'] else '.'):<5}"
              f"{('FIRE' if r['any_sig'] else '.'):<5}")


def main():
    print("=" * 72)
    print("PART A  -  Top-5 survivor enrichment (one ApeWisdom fetch + per-ticker Form4)")
    print("=" * 72)
    t = time.time()
    enriched = enrich_survivors(mock_top5_survivors())
    print(f"enriched 5 survivors in {time.time() - t:.1f}s\n")
    print(f"{'ticker':<6}{'side':<6}{'flow%':>6}  {'reddit':<16}{'rd?':<5}{'insider':<22}{'$value':>14}{'boost':>7}")
    print("-" * 90)
    for c in enriched:
        print(f"{c['ticker']:<6}{c['side']:<6}{c['flow_dominance_pct']:>6}  {c['reddit']:<16}"
              f"{('YES' if c['reddit_confirm'] else '.'):<5}{c['insider']:<22}{c['insider_value']:>14,.0f}{c['altdata_boost']:>7}")

    print("\n" + "=" * 72)
    print("PART B  -  Correlation test: 5 runners vs 5 chop (did the signals fire?)")
    print("=" * 72)
    runners = ["HOOD", "SOFI", "WEN", "GME", "RIVN"]
    chop = ["JNJ", "PG", "KO", "VZ", "WMT"]
    t = time.time()
    rows = correlation_test(runners, chop)
    _print_table(rows)
    # summary
    rn = [r for r in rows if r["group"] == "RUNNER"]
    ch = [r for r in rows if r["group"] == "CHOP"]
    rn_hit = sum(1 for r in rn if r["any_sig"])
    ch_hit = sum(1 for r in ch if r["any_sig"])
    print(f"\nrunners with an alt-data signal: {rn_hit}/{len(rn)}   |   chop with a signal: {ch_hit}/{len(ch)}")
    print(f"(completed in {time.time() - t:.0f}s)")


if __name__ == "__main__":
    main()

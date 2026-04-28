import time
import traceback
from datetime import datetime, timedelta

from src.eodhd import EODHDClient
from src.indicators import to_dataframe
from src.catalyst.edgar import (
    EDGARClient, collect_material_signals, collect_13d_signals, collect_form4_cluster,
)
from src.catalyst.calendar import earnings_signals_for_tomorrow
from src.catalyst.cohorts import cohort_signals
from src.catalyst.scoring import score_ticker, max_possible_score, CATALYST_TIERS


def _normalize(t):
    if "." in t:
        return t.split(".")[0]
    return t


def _suffix_for(ticker_short, eodhd_universe_lookup=None):
    if eodhd_universe_lookup and ticker_short in eodhd_universe_lookup:
        return eodhd_universe_lookup[ticker_short]
    return f"{ticker_short}.US"


def gather_catalysts(client, edgar, target_date=None):
    if target_date and isinstance(target_date, str):
        end_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    elif target_date:
        end_date = target_date
    else:
        end_date = datetime.utcnow().date()

    print(f"  pulling earnings calendar for {end_date} -> tomorrow...")
    earnings = earnings_signals_for_tomorrow(client, target_date=end_date)
    print(f"    {len(earnings)} earnings signals")

    print(f"  pulling EDGAR 8-K / 6-K material filings (2 day window)...")
    material = collect_material_signals(edgar, days_back=2, end_date=end_date)
    print(f"    {len(material)} tickers with material filings")

    print(f"  pulling EDGAR 13D / 13D-A (10 day window)...")
    activist = collect_13d_signals(edgar, days_back=10, end_date=end_date)
    print(f"    {len(activist)} tickers with activist stakes")

    print(f"  pulling EDGAR Form 4 insider cluster (14 day window, 3+ buyers)...")
    insider = collect_form4_cluster(edgar, days_back=14, end_date=end_date, min_buyers=3)
    print(f"    {len(insider)} tickers with insider cluster")

    print(f"  loading cohort lists...")
    cohorts = cohort_signals()
    print(f"    {len(cohorts)} tickers across all cohorts")

    return {
        "earnings": earnings,
        "material": material,
        "activist": activist,
        "insider": insider,
        "cohorts": cohorts,
    }


def build_signals_per_ticker(catalysts):
    out = {}

    for t, info in catalysts["earnings"].items():
        ts = _normalize(t)
        out.setdefault(ts, {"signals": [], "company": "", "sources": []})
        out[ts]["signals"].append({
            "key": info["label"],
            "details": f"reports {info['report_date']} {info.get('before_after_market', '')}".strip(),
        })
        out[ts]["sources"].append("earnings_calendar")

    for t, info in catalysts["material"].items():
        ts = _normalize(t)
        out.setdefault(ts, {"signals": [], "company": info.get("company", ""), "sources": []})
        if not out[ts].get("company"):
            out[ts]["company"] = info.get("company", "")
        seen = set()
        for f in info.get("filings", []):
            match = f.get("match")
            if match in seen:
                continue
            seen.add(match)
            out[ts]["signals"].append({
                "key": match,
                "details": f"8-K/6-K filed {f.get('date')}",
            })
        out[ts]["sources"].append("edgar_material")

    for t, info in catalysts["activist"].items():
        ts = _normalize(t)
        out.setdefault(ts, {"signals": [], "company": info.get("company", ""), "sources": []})
        if not out[ts].get("company"):
            out[ts]["company"] = info.get("company", "")
        out[ts]["signals"].append({
            "key": "activist_stake",
            "details": f"13D filing {info['filings'][0].get('date')}",
        })
        out[ts]["sources"].append("edgar_13d")

    for t, info in catalysts["insider"].items():
        ts = _normalize(t)
        out.setdefault(ts, {"signals": [], "company": info.get("company", ""), "sources": []})
        if not out[ts].get("company"):
            out[ts]["company"] = info.get("company", "")
        out[ts]["signals"].append({
            "key": "insider_cluster",
            "details": f"{info['buyer_count']} unique buyers, {info['filing_count']} forms",
        })
        out[ts]["sources"].append("edgar_form4")

    for t, cohort_list in catalysts["cohorts"].items():
        ts = _normalize(t)
        out.setdefault(ts, {"signals": [], "company": "", "sources": []})
        for c in cohort_list:
            cohort_key = f"cohort_{c['cohort']}"
            out[ts]["signals"].append({
                "key": cohort_key,
                "details": c.get("description", "")[:80],
            })
        out[ts]["sources"].append("cohort")

    return out


def _detect_dollar_volume(df, lookback=20):
    if df is None or len(df) < lookback:
        return None
    recent = df.tail(lookback)
    return float((recent["close"] * recent["volume"]).mean())


def _detect_above_200dma(df, lookback=200):
    if df is None or len(df) < lookback:
        return None
    sma_200 = df["close"].tail(lookback).mean()
    return bool(df["close"].iloc[-1] > sma_200)


def _detect_recent_shelf(fundamentals):
    if not fundamentals:
        return False
    filings = (fundamentals.get("Filings") or {}).get("Last_Filings") or []
    cutoff = datetime.utcnow().date() - timedelta(days=90)
    for f in filings if isinstance(filings, list) else []:
        form = (f.get("type") or "").upper()
        date_str = f.get("date") or ""
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if d >= cutoff and form in ("S-3", "424B5", "S-3/A"):
            return True
    return False


def _detect_beat_streak(fundamentals, min_streak=3, min_surprise=2.0):
    if not fundamentals:
        return False
    earnings = fundamentals.get("Earnings") or {}
    history = earnings.get("History") or {}
    if not history:
        return False
    rows = []
    for date, row in history.items():
        try:
            d = datetime.strptime(date, "%Y-%m-%d").date()
        except Exception:
            continue
        sp = row.get("surprisePercent")
        if sp is None:
            continue
        try:
            sp = float(sp)
        except Exception:
            continue
        rows.append((d, sp))
    if not rows:
        return False
    rows.sort(reverse=True)
    streak = 0
    for d, sp in rows[:8]:
        if sp >= min_surprise:
            streak += 1
            if streak >= min_streak:
                return True
        else:
            break
    return False


def enrich_ticker(client, ticker_short, signals, suffix_hint=None):
    candidates = []
    if suffix_hint:
        candidates.append(suffix_hint)
    candidates += [f"{ticker_short}.US", f"{ticker_short}.LSE"]
    seen = set()
    candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    df = None
    fund = None
    eodhd_ticker = None
    for full in candidates:
        try:
            ohlcv = client.ohlcv(full)
            if ohlcv and len(ohlcv) >= 20:
                df = to_dataframe(ohlcv)
                eodhd_ticker = full
                break
        except Exception:
            continue
    if df is None:
        return None

    try:
        fund = client.fundamentals(eodhd_ticker)
    except Exception:
        fund = None

    general = (fund or {}).get("General", {}) or {}
    highlights = (fund or {}).get("Highlights", {}) or {}
    shares = (fund or {}).get("SharesStats", {}) or {}
    name = general.get("Name") or ""
    sector = general.get("Sector") or ""
    industry = general.get("Industry") or ""
    description = general.get("Description") or ""

    mcap = highlights.get("MarketCapitalization")
    short_pct = shares.get("ShortPercentFloat")
    pct_inst = shares.get("PercentInstitutions")

    going_concern = False
    desc_lower = (description or "").lower()
    if "going concern" in desc_lower or "substantial doubt" in desc_lower:
        going_concern = True

    cohort_count = sum(1 for s in signals if s.get("key", "").startswith("cohort_"))
    has_fresh_filing = any(
        s.get("key", "") in ("definitive_agreement", "private_placement", "merger", "asset_sale",
                              "covenant_relief", "fda_event", "clinical_milestone", "strategic_partnership",
                              "contract_win", "buyback")
        for s in signals
    )

    has_earnings_signal = any(s.get("key", "").startswith("earnings_") for s in signals)
    beat_streak = _detect_beat_streak(fund) if has_earnings_signal else False

    return {
        "ticker": ticker_short,
        "eodhd_ticker": eodhd_ticker,
        "name": name,
        "sector": sector,
        "industry": industry,
        "description": description[:300],
        "price": float(df["close"].iloc[-1]) if len(df) else None,
        "market_cap": mcap,
        "short_pct_float": short_pct,
        "pct_inst_held": pct_inst,
        "dollar_volume_20d": _detect_dollar_volume(df),
        "above_200dma": _detect_above_200dma(df),
        "going_concern": going_concern,
        "recent_shelf": _detect_recent_shelf(fund),
        "sector_tailwind": False,
        "cohort_stack": cohort_count >= 2 or (cohort_count >= 1 and has_fresh_filing),
        "beat_streak": beat_streak,
    }


def apply_sector_tailwind(scored, sector_perf):
    perf_map = {}
    for s in sector_perf or []:
        if s.get("ret_5d") and s["ret_5d"] >= 2.0:
            perf_map[s["sector"]] = s["ret_5d"]
    for r in scored:
        sector = r.get("sector")
        if sector and sector in perf_map:
            r["data"]["sector_tailwind"] = True
            r["sector_5d"] = perf_map[sector]


def run_catalyst_scan(target_date=None, score_cutoff=6.0, verbose=True):
    client = EODHDClient()
    edgar = EDGARClient()

    if verbose:
        print(f"=== Catalyst Scan ({target_date or datetime.utcnow().date()}) ===")
        print(f"Step 1/4: gather catalyst signals")

    catalysts = gather_catalysts(client, edgar, target_date=target_date)
    per_ticker = build_signals_per_ticker(catalysts)
    if verbose:
        print(f"  raw candidates with any signal: {len(per_ticker)}")

    pre_filtered = {
        t: info for t, info in per_ticker.items()
        if max_possible_score(info["signals"]) >= score_cutoff
    }
    if verbose:
        print(f"  passing max-possible-score >= {score_cutoff}: {len(pre_filtered)}")
        print(f"Step 2/4: enrich {len(pre_filtered)} unique tickers with quality data")
    per_ticker = pre_filtered

    enriched = []
    skipped = 0
    start = time.time()
    for i, (ticker_short, info) in enumerate(per_ticker.items()):
        if verbose and i > 0 and i % 50 == 0:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(per_ticker)}] enriched={len(enriched)} skipped={skipped} rate={rate:.1f}/s")
        try:
            data = enrich_ticker(client, ticker_short, info["signals"])
            if not data:
                skipped += 1
                continue
            if not data.get("price") or data["price"] < 1.0:
                skipped += 1
                continue
            enriched.append({
                "ticker": ticker_short,
                "company": info.get("company") or data.get("name") or "",
                "signals": info["signals"],
                "sources": info.get("sources", []),
                "data": data,
                "name": data.get("name"),
                "sector": data.get("sector"),
            })
        except Exception as e:
            skipped += 1
            if verbose and skipped < 5:
                print(f"  enrich failed for {ticker_short}: {type(e).__name__}: {e}")

    if verbose:
        print(f"  enriched: {len(enriched)}, skipped: {skipped}")
        print(f"Step 3/4: score and rank")

    try:
        from src.sectors import fetch_sector_performance
        spy_df = to_dataframe(client.ohlcv("SPY.US", from_date=(datetime.utcnow().date() - timedelta(days=200)).strftime("%Y-%m-%d")))
        sector_perf = fetch_sector_performance(client, spy_df, (datetime.utcnow().date() - timedelta(days=200)).strftime("%Y-%m-%d"))
    except Exception as e:
        if verbose:
            print(f"  sector performance unavailable: {e}")
        sector_perf = []

    apply_sector_tailwind(enriched, sector_perf)

    scored = []
    for r in enriched:
        s = score_ticker(r["ticker"], r["signals"], r["data"])
        s["company"] = r["company"]
        s["name"] = r.get("name")
        s["sector"] = r.get("sector")
        s["price"] = r["data"].get("price")
        s["market_cap"] = r["data"].get("market_cap")
        s["dollar_volume_20d"] = r["data"].get("dollar_volume_20d")
        s["short_pct_float"] = r["data"].get("short_pct_float")
        s["sources"] = r.get("sources", [])
        s["eodhd_ticker"] = r["data"].get("eodhd_ticker")
        scored.append(s)

    scored.sort(key=lambda x: x["score"], reverse=True)

    cut = [s for s in scored if s["score"] >= score_cutoff]
    if verbose:
        from collections import Counter
        buckets = Counter(s["bucket"] for s in scored)
        print(f"  scored: {len(scored)}  STRONG: {buckets.get('STRONG',0)}  WATCH: {buckets.get('WATCH',0)}  SPEC: {buckets.get('SPECULATIVE',0)}")
        print(f"  passing cutoff (>= {score_cutoff}): {len(cut)}")
        print(f"Step 4/4: done. Total API: EODHD={client.calls_made}  EDGAR={edgar.calls_made}")

    return {
        "scan_date": (target_date if isinstance(target_date, str) else (target_date or datetime.utcnow().date()).strftime("%Y-%m-%d")),
        "candidates_total": len(per_ticker),
        "enriched_total": len(enriched),
        "scored_total": len(scored),
        "passed_cutoff": len(cut),
        "score_cutoff": score_cutoff,
        "candidates": cut,
        "all_scored": scored,
        "eodhd_calls": client.calls_made,
        "edgar_calls": edgar.calls_made,
    }

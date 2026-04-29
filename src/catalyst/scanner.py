import os
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
from src.catalyst.scoring import (
    score_ticker, max_possible_base, assign_buckets, CATALYST_TIERS,
)
from src.catalyst.news import news_score, fetch_recent_news
from src.catalyst.drift import compute_drift, drift_score
from src.catalyst.historical import historical_earnings_reaction, historical_score
from src.catalyst.peers import peer_signals, peer_confirmation_score
from src.catalyst.freshness import freshness_score
from src.catalyst.llm_grader import grade_candidates, llm_score_to_points
from src.catalyst.buy_signal import buy_signal
from src.catalyst.tracker import (
    snapshot_predictions, measure_outcomes, get_recent_stats,
)
from src.catalyst.risk_audit import audit_risks
from src.catalyst.insider_depth import analyze_insider
from src.catalyst.options_check import implied_move, options_check_score
from src.catalyst.deep_research import deep_research
from src.catalyst.paper_trading import simulate_outcomes as simulate_paper, get_paper_stats


def _normalize(t):
    if "." in t:
        return t.split(".")[0]
    return t


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
            "details": f"13D filed {info['filings'][0].get('date')}",
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


def enrich_ticker(client, ticker_short, signals, suffix_hint=None, fetch_news=False):
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

    drift = compute_drift(df)
    hist_reaction = historical_earnings_reaction(fund, df)

    news_data = None
    if fetch_news:
        news_data = news_score(client, ticker_short, eodhd_ticker)

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
        "drift": drift,
        "hist_reaction": hist_reaction,
        "news": news_data,
        "df": df,
        "fundamentals": fund,
    }


def run_catalyst_scan(target_date=None, top_pct_strong=5, top_pct_watch=15,
                       news_max_fetch=150, llm_max_grade=50, deep_research_max=5,
                       insider_max_fetch=80, options_max_fetch=30, min_base_pts=2.0, verbose=True):
    client = EODHDClient()
    edgar = EDGARClient()

    if verbose:
        print(f"=== Catalyst Scan v2 ({target_date or datetime.utcnow().date()}) ===")
        print(f"Step 0/6: measure outcomes for prior predictions")
    today = (target_date if isinstance(target_date, str) else (target_date or datetime.utcnow().date()).strftime("%Y-%m-%d"))
    today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    measured_total = 0
    for back in range(1, 8):
        prior = (today_dt - timedelta(days=back)).strftime("%Y-%m-%d")
        try:
            measured, _ = measure_outcomes(client, prior)
            measured_total += measured
        except Exception as e:
            if verbose:
                print(f"  outcome measure failed for {prior}: {e}")
    try:
        new_paper, total_paper = simulate_paper(client)
        if verbose:
            print(f"  paper trading: simulated {new_paper} new trades, {total_paper} total")
    except Exception as e:
        if verbose:
            print(f"  paper trading sim failed: {e}")
    if verbose:
        print(f"  measured outcomes for {measured_total} prior predictions")
        print(f"Step 1/6: gather catalyst signals")

    catalysts = gather_catalysts(client, edgar, target_date=target_date)
    per_ticker = build_signals_per_ticker(catalysts)
    if verbose:
        print(f"  raw candidates with any signal: {len(per_ticker)}")

    pre_filtered = {
        t: info for t, info in per_ticker.items()
        if max_possible_base(info["signals"]) >= min_base_pts
    }
    if verbose:
        print(f"  passing min base catalyst >= {min_base_pts}: {len(pre_filtered)}")
        print(f"Step 2/6: enrich {len(pre_filtered)} tickers (OHLCV + fundamentals)")
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
        print(f"Step 3/6: initial score (no news, no LLM yet)")

    sector_map = peer_signals([
        {"ticker": r["ticker"], "sector": r["sector"], "catalysts": r["signals"]}
        for r in enriched
    ])

    pre_scored = []
    for r in enriched:
        data = r["data"]
        peer_data = peer_confirmation_score(r["ticker"], r.get("sector"), sector_map)
        drift_pts = drift_score(data.get("drift"), signals=r["signals"])
        hist_pts = historical_score(data.get("hist_reaction"))
        fresh_pts = freshness_score(r["signals"])

        s = score_ticker(
            r["ticker"], r["signals"], data,
            news_data=None,
            drift_data=drift_pts,
            historical_data=hist_pts,
            freshness_data=fresh_pts,
            peer_data=peer_data,
            llm_data=None,
        )
        s["company"] = r["company"]
        s["name"] = r.get("name")
        s["sector"] = r.get("sector")
        s["price"] = data.get("price")
        s["market_cap"] = data.get("market_cap")
        s["dollar_volume_20d"] = data.get("dollar_volume_20d")
        s["short_pct_float"] = data.get("short_pct_float")
        s["sources"] = r.get("sources", [])
        s["eodhd_ticker"] = data.get("eodhd_ticker")
        s["news"] = None
        s["_enriched_data"] = data
        s["base_points"] = s["components"]["catalyst_quality"]["points"]
        s["modifier_points"] = sum(
            s["components"][k].get("points", 0)
            for k in ("liquidity_setup", "drift", "historical", "freshness", "peer")
        )
        pre_scored.append(s)

    pre_scored.sort(key=lambda x: x["score"], reverse=True)
    if verbose:
        print(f"  pre-scored: {len(pre_scored)}")
        print(f"Step 4/6: fetch news for top {min(news_max_fetch, len(pre_scored))} candidates")

    top_for_news = pre_scored[:news_max_fetch]
    for i, s in enumerate(top_for_news):
        if verbose and i > 0 and i % 30 == 0:
            print(f"  [news {i}/{len(top_for_news)}]")
        try:
            news_data = news_score(client, s["ticker"], s.get("eodhd_ticker"))
            s["news"] = news_data
            s["components"]["news"] = news_data
            s["score"] = round(s["score"] + news_data["points"], 2)
        except Exception as e:
            if verbose:
                print(f"  news fetch failed for {s['ticker']}: {type(e).__name__}")

    if verbose:
        print(f"  running risk audit + insider depth on top {insider_max_fetch} candidates")
    for i, s in enumerate(pre_scored[:insider_max_fetch]):
        data = s.get("_enriched_data") or {}
        fund = data.get("fundamentals")
        news_headlines = (s.get("news") or {}).get("headlines") or []
        try:
            risk = audit_risks(fund, news_headlines, signals=s.get("catalysts"))
            s["risk_audit"] = risk
            s["components"]["risk_flags"] = {"points": risk["penalty_points"], "label": f"{len(risk['flags'])} risk flag(s)", "flags": risk["flags"]}
            s["score"] = round(s["score"] + risk["penalty_points"], 2)
        except Exception:
            s["risk_audit"] = {"flags": [], "penalty_points": 0, "high_severity_count": 0}
        try:
            insider = analyze_insider(client, s.get("eodhd_ticker"))
            if insider:
                s["insider_depth"] = insider
                s["components"]["insider"] = {"points": insider["points"], "label": ", ".join(insider["signals"][:2]) or "no insider activity"}
                s["score"] = round(s["score"] + insider["points"], 2)
        except Exception:
            pass

    if verbose:
        print(f"  running options reality check on top {options_max_fetch}")
    pre_scored_sorted_temp = sorted(pre_scored, key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(pre_scored_sorted_temp[:options_max_fetch]):
        if not s.get("eodhd_ticker", "").endswith(".US"):
            continue
        try:
            symbol = s["eodhd_ticker"].replace(".US", "")
            opts = implied_move(symbol, s.get("price"))
            if opts:
                from src.catalyst.buy_signal import buy_signal as _bs_fn
                placeholder_bs = _bs_fn({"price": s.get("price")}, s["components"], df=(s.get("_enriched_data") or {}).get("df"), catalyst_tier=s.get("catalyst_tier", "-"), confidence=s.get("confidence", "MEDIUM"))
                check = options_check_score(placeholder_bs, opts)
                s["options_check"] = check
                s["components"]["options"] = {"points": check["points"], "label": check["label"]}
                s["score"] = round(s["score"] + check["points"], 2)
        except Exception:
            pass

    if verbose:
        print(f"Step 5/6: LLM grading top {llm_max_grade} candidates")

    llm_grades = grade_candidates(pre_scored, max_grade=llm_max_grade, verbose=verbose)

    final_scored = []
    from src.catalyst.scoring import confidence_label
    for s in pre_scored:
        grade = llm_grades.get(s["ticker"])
        llm_pts = llm_score_to_points(grade) if grade else {"points": 0.0, "label": "not LLM-graded"}
        s["components"]["llm"] = llm_pts
        s["score"] = round(s["score"] + llm_pts["points"], 2)
        s["confidence"] = confidence_label(s["components"])
        enriched_data = s.get("_enriched_data") or {}
        s["buy_signal"] = buy_signal(
            ticker_data={"price": s.get("price")},
            components=s["components"],
            df=enriched_data.get("df"),
            catalyst_tier=s.get("catalyst_tier", "-"),
            confidence=s.get("confidence", "MEDIUM"),
        )
        s.pop("_enriched_data", None)
        final_scored.append(s)

    final_scored = assign_buckets(final_scored, top_pct_strong=top_pct_strong, top_pct_watch=top_pct_watch)
    if verbose:
        from collections import Counter
        buckets = Counter(s.get("bucket") for s in final_scored)
        print(f"  STRONG: {buckets.get('STRONG',0)}  WATCH: {buckets.get('WATCH',0)}  SPEC: {buckets.get('SPECULATIVE',0)}")

    if deep_research_max > 0:
        if verbose:
            print(f"  running deep research (Opus + web search) on top {deep_research_max}")
        top_for_deep = sorted(final_scored, key=lambda x: x["score"], reverse=True)[:deep_research_max]
        deep_results = deep_research(top_for_deep, max_tickers=deep_research_max, verbose=verbose)
        for s in final_scored:
            if s["ticker"] in deep_results:
                s["deep_research"] = deep_results[s["ticker"]]

    scan_date_str = (target_date if isinstance(target_date, str) else (target_date or datetime.utcnow().date()).strftime("%Y-%m-%d"))
    snap_count, _ = snapshot_predictions(scan_date_str, final_scored)
    if verbose:
        print(f"  saved {snap_count} predictions to tracker")

    tracker_stats = get_recent_stats(days=30)
    paper_stats = get_paper_stats(days=30)
    if verbose and tracker_stats and tracker_stats.get("BUY"):
        b = tracker_stats["BUY"]
        print(f"  tracker BUY 30d: n={b['n']} hit_t1={b['hit_t1_pct']}% avg_high={b['avg_next_high_pct']}%")
    if verbose and paper_stats:
        print(f"  paper P&L 30d: ${paper_stats['total_pnl_usd']:+.2f} on {paper_stats['n']} trades, {paper_stats['win_rate_pct']}% wins, ROI {paper_stats['roi_pct']}%")
    if verbose:
        print(f"Step 6/6: done. EODHD={client.calls_made}  EDGAR={edgar.calls_made}")

    candidates = [s for s in final_scored if s.get("bucket") in ("STRONG", "WATCH")]

    return {
        "scan_date": scan_date_str,
        "tracker_stats": tracker_stats,
        "paper_stats": paper_stats,
        "candidates_total": len(per_ticker),
        "enriched_total": len(enriched),
        "scored_total": len(final_scored),
        "passed_cutoff": len(candidates),
        "top_pct_strong": top_pct_strong,
        "top_pct_watch": top_pct_watch,
        "candidates": candidates,
        "all_scored": final_scored,
        "eodhd_calls": client.calls_made,
        "edgar_calls": edgar.calls_made,
        "llm_graded": len(llm_grades),
    }

import os
import sys
import time
import traceback
from datetime import datetime, timedelta

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.eodhd import EODHDClient
from src.indicators import to_dataframe
from src.catalyst.edgar import (
    EDGARClient, collect_material_signals, collect_13d_signals, collect_form4_cluster,
)
from src.catalyst.calendar import earnings_signals_for_tomorrow, earnings_lead_up_window
from src.catalyst.cohorts import cohort_signals
from src.catalyst.scoring import (
    score_ticker, max_possible_base, assign_buckets, CATALYST_TIERS, WEIGHT_CATALYST,
)
from src.catalyst.news import news_score, fetch_recent_news
from src.catalyst.signals import (
    run_all_catalyst_detectors, detector_hits_to_signal_entries, append_signals_and_rescore,
)
from src.catalyst.inflection import inflection_readiness_score
from src.catalyst.options_flow import detect_unusual_options_activity
from src.catalyst.position_in_theme import annotate_with_position_in_theme
from src.catalyst.smart_money import days_to_cover, short_squeeze_setup_score, beneish_m_score
from src.catalyst.macro_indicators import fetch_macro_snapshot, macro_regime_summary, index_rebalance_candidates
from src.catalyst.pre_catalyst import (
    build_pre_catalyst_watchlist, get_upcoming_conferences, get_high_momentum_tickers,
)
from src.catalyst.forward_calendar import build_forward_calendar
from src.catalyst.portfolio_context import (
    get_position_summary, yesterdays_lottery_followup, get_recent_paper_trade_stats,
)
from src.catalyst.post_earnings_drift import detect_post_earnings_drift, apply_ped_scoring
from src.catalyst.analyst_changes import detect_analyst_changes, apply_analyst_scoring
from src.catalyst.sympathy_detector import detect_sympathy_moves, apply_sympathy_scoring
from src.catalyst.crypto_regime import fetch_crypto_regime, apply_crypto_regime_boost
from src.catalyst.bracket_router import route_candidates
from src.catalyst.landmine_filter import filter_landmines
from src.catalyst.extension_filter import filter_extension
from src.catalyst.smart_money_required import filter_smart_money_required
from src.catalyst.stacking_engine import apply_stacking
from src.catalyst.iv_percentile import apply_iv_percentile
from src.catalyst.options_market_critic import apply_options_market_critic
from src.catalyst.peer_benchmarker import apply_peer_benchmarking
from src.catalyst.sector_rotation_gate import apply_sector_rotation_gate
from src.catalyst.vol_regime_tuner import classify_vol_regime
from src.catalyst.insider_seniority import enrich_insider_quality
from src.catalyst.allocator_tier import enrich_allocator_tier
from src.catalyst.composite_quality import enrich_composite_quality
from src.catalyst.news_tiering import enrich_news_quality
from src.catalyst.aa_gates import assign_tiers, pick_top_per_bracket
from src.catalyst.pre_mortem import apply_pre_mortem
from src.catalyst.unified_forensic import apply_unified_forensic, apply_haiku_synthesis, apply_bear_case_verification
from src.catalyst.catalyst_performance import annotate_picks_with_performance, measure_catalyst_performance
from src.catalyst.v4_paper_log import log_picks as log_v4_picks, measure_outcomes as measure_v4_outcomes, get_v4_stats
from src.catalyst.conviction_journal import log_picks_from_scan as log_conviction_picks, mark_forward_returns as mark_conviction_forward, get_journal_stats as get_conviction_stats
from src.catalyst.conviction_drift import check_drift as check_conviction_drift
from src.catalyst.sam_gov import fetch_recent_contract_awards, map_awardees_to_tickers
from src.catalyst.drift import compute_drift, drift_score, timing_bonus
from src.catalyst.historical import historical_earnings_reaction, historical_score
from src.catalyst.peers import peer_signals, peer_confirmation_score
from src.catalyst.freshness import freshness_score
from src.catalyst.llm_grader import grade_candidates, llm_score_to_points
from src.catalyst.buy_signal import buy_signal
from src.catalyst.tracker import (
    snapshot_predictions, measure_outcomes, get_recent_stats,
)
from src.catalyst.risk_audit import audit_risks, detect_deal_closed
from src.catalyst.insider_depth import analyze_insider
from src.catalyst.options_check import implied_move, options_check_score
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

    print(f"  pulling earnings lead-up window (1-15d ahead)...")
    earnings_lead_up = earnings_lead_up_window(client, target_date=end_date, days_ahead=15)
    print(f"    {len(earnings_lead_up)} tickers with earnings in next 15d")

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

    print(f"  loading index inclusion signals (Nasdaq-100, S&P 500, etc.)...")
    try:
        from src.catalyst.index_inclusion import get_index_signals
        index_signals = get_index_signals(target_date=target_date, max_days_until=14)
        print(f"    {len(index_signals)} tickers with index inclusion/exit within 14d")
    except Exception as e:
        print(f"    index inclusion load failed: {type(e).__name__}: {e}")
        index_signals = {}

    return {
        "earnings": earnings,
        "earnings_lead_up": earnings_lead_up,
        "material": material,
        "activist": activist,
        "insider": insider,
        "cohorts": cohorts,
        "index_inclusion": index_signals,
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

    for t, info in (catalysts.get("index_inclusion") or {}).items():
        ts = _normalize(t)
        out.setdefault(ts, {"signals": [], "company": "", "sources": []})
        out[ts]["signals"].append({
            "key": info.get("key", "index_inclusion"),
            "details": info.get("details", ""),
        })
        out[ts]["sources"].append("index_inclusion")

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
                       news_max_fetch=150, llm_max_grade=50,
                       insider_max_fetch=80, options_max_fetch=30, min_base_pts=2.0, verbose=True):
    client = EODHDClient()
    edgar = EDGARClient()

    if verbose:
        print(f"=== Catalyst Scan v2 ({target_date or datetime.utcnow().date()}) ===")
        print(f"Step 0/6: macro snapshot + measure outcomes for prior predictions")
    macro = None
    try:
        macro_snap = fetch_macro_snapshot(client)
        macro = macro_regime_summary(macro_snap)
        if verbose:
            print(f"  macro: regime={macro.get('regime')} vix={macro.get('vix')}")
            for flag in (macro.get("flags") or [])[:3]:
                print(f"    - {flag}")
    except Exception as e:
        if verbose:
            print(f"  macro snapshot failed: {type(e).__name__}: {e}")
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
        s["industry"] = data.get("industry") or ""
        s["description"] = data.get("description") or ""
        s["price"] = data.get("price")
        s["market_cap"] = data.get("market_cap")
        s["dollar_volume_20d"] = data.get("dollar_volume_20d")
        s["short_pct_float"] = data.get("short_pct_float")
        s["sources"] = r.get("sources", [])
        s["eodhd_ticker"] = data.get("eodhd_ticker")
        s["news"] = None
        s["_enriched_data"] = data
        s["_raw_fundamentals"] = data.get("fundamentals") or {}
        s["above_50dma"] = None
        s["above_200dma"] = data.get("above_200dma")
        df = data.get("df")
        try:
            if df is not None and len(df) >= 5:
                close = df["close"]
                last = float(close.iloc[-1])
                if len(close) >= 6:
                    p5 = float(close.iloc[-6])
                    if p5 > 0:
                        s["ret_5d"] = round((last - p5) / p5 * 100, 2)
                if len(close) >= 31:
                    p30 = float(close.iloc[-31])
                    if p30 > 0:
                        s["ret_30d"] = round((last - p30) / p30 * 100, 2)
                if len(close) >= 91:
                    p90 = float(close.iloc[-91])
                    if p90 > 0:
                        s["ret_90d"] = round((last - p90) / p90 * 100, 2)
                if len(close) >= 50:
                    sma50 = float(close.iloc[-50:].mean())
                    if sma50 > 0:
                        s["pct_above_50dma"] = round((last - sma50) / sma50 * 100, 2)
                        s["above_50dma"] = last > sma50
                if len(close) >= 200:
                    sma200 = float(close.iloc[-200:].mean())
                    if sma200 > 0:
                        s["pct_above_200dma"] = round((last - sma200) / sma200 * 100, 2)
                if len(close) >= 252:
                    low_52w = float(close.iloc[-252:].min())
                    if low_52w > 0:
                        s["pct_off_52w_low"] = round((last - low_52w) / low_52w * 100, 2)
        except Exception:
            pass
        try:
            fund = data.get("fundamentals") or {}
            earnings = fund.get("Earnings") or {}
            history = earnings.get("History") or {}
            if isinstance(history, dict):
                s["earnings_history"] = sorted(list(history.values()), key=lambda x: x.get("reportDate") or "", reverse=True)[:8]
            elif isinstance(history, list):
                s["earnings_history"] = history[:8]
        except Exception:
            pass
        catalysts_full = s["components"]["catalyst_quality"].get("catalysts_full") or []
        timing_pts = timing_bonus(catalysts_full, data.get("drift"))
        s["components"]["timing"] = timing_pts
        s["score"] = round(s["score"] + timing_pts["points"], 2)
        s["ideal_setup"] = timing_pts.get("ideal_setup", False)
        s["base_points"] = s["components"]["catalyst_quality"]["points"]
        s["modifier_points"] = sum(
            s["components"][k].get("points", 0)
            for k in ("liquidity_setup", "drift", "historical", "freshness", "peer", "timing")
        )
        pre_scored.append(s)

    pre_scored.sort(key=lambda x: x["score"], reverse=True)
    if verbose:
        print(f"  pre-scored: {len(pre_scored)}")
        print(f"Step 4/6: fetch news for top {min(news_max_fetch, len(pre_scored))} candidates")

    top_for_news = pre_scored[:news_max_fetch]
    new_signals_added_total = 0
    for i, s in enumerate(top_for_news):
        if verbose and i > 0 and i % 30 == 0:
            print(f"  [news {i}/{len(top_for_news)}]  new_signals_added={new_signals_added_total}")
        try:
            news_data = news_score(client, s["ticker"], s.get("eodhd_ticker"))
            s["news"] = news_data
            s["components"]["news"] = news_data
            s["score"] = round(s["score"] + news_data["points"], 2)
        except Exception as e:
            if verbose:
                print(f"  news fetch failed for {s['ticker']}: {type(e).__name__}")
            continue
        try:
            raw_headlines = fetch_recent_news(
                client,
                s.get("eodhd_ticker") or s["ticker"],
                max_age_days=21,
                limit=30,
            )
            fund = (s.get("_enriched_data") or {}).get("fundamentals")
            detectors = run_all_catalyst_detectors(raw_headlines, fund)
            new_entries = detector_hits_to_signal_entries(detectors)
            if new_entries:
                changed = append_signals_and_rescore(s, new_entries, CATALYST_TIERS, WEIGHT_CATALYST)
                if changed:
                    new_signals_added_total += len(s.get("_signals_added") or [])
                    s["new_signal_detectors"] = {
                        k: {kk: vv for kk, vv in v.items() if kk != "evidence"}
                        for k, v in detectors.items() if v.get("fired")
                    }
        except Exception as e:
            if verbose:
                print(f"  signal detector failed for {s['ticker']}: {type(e).__name__}: {e}")
    if verbose:
        print(f"  new catalyst signals appended: {new_signals_added_total}")

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
            atr_pct = (data.get("atr_pct") if isinstance(data.get("atr_pct"), (int, float)) else None)
            if atr_pct is None and data.get("df") is not None:
                from src.catalyst.buy_signal import compute_atr_pct
                atr_pct = compute_atr_pct(data["df"])
            deal_closed = detect_deal_closed(s.get("catalysts"), atr_pct, news_headlines, dollar_volume=s.get("dollar_volume_20d"))
            if deal_closed:
                s["deal_closed"] = deal_closed
                s["components"]["deal_closed"] = {"points": -50, "label": deal_closed["reason"]}
                s["score"] = round(s["score"] - 50, 2)
        except Exception:
            pass
        try:
            insider = analyze_insider(client, s.get("eodhd_ticker"))
            if insider:
                s["insider_depth"] = insider
                s["components"]["insider"] = {"points": insider["points"], "label": ", ".join(insider["signals"][:2]) or "no insider activity"}
                s["score"] = round(s["score"] + insider["points"], 2)
        except Exception:
            pass

    if verbose:
        print(f"  running inflection readiness scorer on top {min(insider_max_fetch, len(pre_scored))}")
    for i, s in enumerate(pre_scored[:insider_max_fetch]):
        data = s.get("_enriched_data") or {}
        df = data.get("df")
        try:
            inf = inflection_readiness_score(df)
            s["inflection"] = inf
            s["components"]["inflection"] = {
                "points": inf["points"],
                "label": inf["label"],
                "components_fired": inf["components_fired"],
            }
            s["score"] = round(s.get("score", 0) + inf["points"], 2)
        except Exception:
            s["inflection"] = None

    if verbose:
        print(f"  running options reality check + unusual flow on top {options_max_fetch}")
    pre_scored_sorted_temp = sorted(pre_scored, key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(pre_scored_sorted_temp[:options_max_fetch]):
        if not s.get("eodhd_ticker", "").endswith(".US"):
            continue
        try:
            symbol = s["eodhd_ticker"].replace(".US", "")
            try:
                flow = detect_unusual_options_activity(symbol, s.get("price"))
                if flow:
                    s["options_flow"] = flow
                    if flow.get("sentiment") == "BULLISH":
                        s["score"] = round(s.get("score", 0) + 5, 2)
                        s["components"]["options_flow"] = {"points": 5, "label": f"BULLISH flow: {', '.join(flow.get('bullish_signals', [])[:2])}"}
                    elif flow.get("sentiment") == "BEARISH":
                        s["score"] = round(s.get("score", 0) - 5, 2)
                        s["components"]["options_flow"] = {"points": -5, "label": f"BEARISH flow: {', '.join(flow.get('bearish_signals', [])[:2])}"}
            except Exception:
                pass
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
        if s.get("deal_closed"):
            s["buy_signal"]["signal"] = "SKIP"
            s["buy_signal"]["signal_color"] = "#c94545"
            s["buy_signal"]["probability_pct"] = max(5, s["buy_signal"]["probability_pct"] - 50)
            s["buy_signal"]["deal_closed_reason"] = s["deal_closed"]["reason"]
        s.pop("_enriched_data", None)
        final_scored.append(s)

    try:
        from src.sectors import fetch_sector_performance
        from src.catalyst.sector_overlay import apply_catalyst_sector_overlay
        spy_ohlcv = client.ohlcv("SPY.US", from_date=(datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d"))
        spy_df = to_dataframe(spy_ohlcv) if spy_ohlcv else None
        if spy_df is not None:
            sector_perf = fetch_sector_performance(client, spy_df, from_date=(datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d"))
            if verbose:
                print(f"Step 6.5/6: applying sector rotation overlay to catalyst scores...")
            apply_catalyst_sector_overlay(final_scored, sector_perf, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  sector overlay skipped: {type(e).__name__}: {e}")

    from src.catalyst.scoring import cross_confirmation_score
    for s in final_scored:
        catalysts_full = (s.get("components", {}).get("catalyst_quality", {}) or {}).get("catalysts_full") or []
        xconf = cross_confirmation_score(catalysts_full)
        s["components"]["cross_confirmation"] = xconf
        s["score"] = round(s["score"] + xconf["points"], 2)
        s["cross_confirmation"] = xconf

    try:
        if verbose:
            print(f"  post-earnings drift detection (5d lookback)...")
        ped_signals = detect_post_earnings_drift(final_scored, lookback_days=5)
        apply_ped_scoring(final_scored, ped_signals)
        if verbose:
            print(f"    {len(ped_signals)} names with post-earnings drift (beat + momentum)")
    except Exception as e:
        if verbose:
            print(f"  post_earnings_drift failed: {type(e).__name__}: {e}")

    try:
        if verbose:
            print(f"  analyst rating change detection...")
        analyst_signals = detect_analyst_changes(final_scored)
        apply_analyst_scoring(final_scored, analyst_signals)
        if verbose:
            print(f"    {len(analyst_signals)} names with bullish/bearish analyst consensus")
    except Exception as e:
        if verbose:
            print(f"  analyst_changes failed: {type(e).__name__}: {e}")

    try:
        if verbose:
            print(f"  sympathy / sector ripple detection (industry peers ≥+5%/5d)...")
        sympathy_signals = detect_sympathy_moves(final_scored, min_peers_moved=2, peer_move_threshold=5.0)
        apply_sympathy_scoring(final_scored, sympathy_signals)
        if verbose:
            print(f"    {len(sympathy_signals)} laggard names in sectors-on-the-move")
    except Exception as e:
        if verbose:
            print(f"  sympathy_detector failed: {type(e).__name__}: {e}")

    try:
        if verbose:
            print(f"  crypto regime detection (BTC/ETH momentum)...")
        crypto_regime = fetch_crypto_regime(client)
        from src.catalyst.cohorts import load_cohorts
        cohorts_data = load_cohorts()
        crypto_tickers = (cohorts_data.get("crypto_treasury") or {}).get("tickers", [])
        apply_crypto_regime_boost(final_scored, crypto_regime, crypto_tickers)
        if verbose:
            print(f"    crypto regime: {crypto_regime['regime']} (BTC {crypto_regime.get('btc_7d_pct', 'n/a')}%/7d)")
    except Exception as e:
        if verbose:
            print(f"  crypto_regime failed: {type(e).__name__}: {e}")

    if verbose:
        print(f"  annotating position-in-theme across all scored names...")
    try:
        annotate_with_position_in_theme(final_scored)
        for s in final_scored:
            pos = s.get("position_in_theme")
            if pos and pos.get("rank") in ("laggard", "deep_laggard"):
                s["score"] = round(s.get("score", 0) + 4, 2)
                s["components"]["position_in_theme"] = {"points": 4, "label": f"{pos['rank']} in theme — asymmetric setup"}
    except Exception as e:
        if verbose:
            print(f"  position_in_theme failed: {type(e).__name__}: {e}")

    final_scored = assign_buckets(final_scored, top_pct_strong=top_pct_strong, top_pct_watch=top_pct_watch)
    if verbose:
        from collections import Counter
        buckets = Counter(s.get("bucket") for s in final_scored)
        print(f"  STRONG: {buckets.get('STRONG',0)}  WATCH: {buckets.get('WATCH',0)}  SPEC: {buckets.get('SPECULATIVE',0)}")

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

    rebalance = {}
    try:
        rebalance = index_rebalance_candidates(final_scored)
    except Exception:
        rebalance = {}

    if verbose:
        print(f"  fetching SAM.gov contract awards (last 2 days, high-value keywords)...")
    sam_awards_by_ticker = {}
    try:
        awards, sam_err = fetch_recent_contract_awards(days_back=3, limit=200)
        if sam_err:
            if verbose:
                print(f"    SAM.gov: {sam_err}")
        elif awards:
            ticker_companies = {s.get("ticker"): s.get("name") for s in final_scored if s.get("ticker") and s.get("name")}
            sam_awards_by_ticker = map_awardees_to_tickers(awards, ticker_companies)
            for ticker, ticker_awards in sam_awards_by_ticker.items():
                target = next((s for s in final_scored if s.get("ticker") == ticker), None)
                if target:
                    catalysts_full = (target.get("components", {}).get("catalyst_quality", {}) or {}).get("catalysts_full") or []
                    existing_keys = {c.get("key") for c in catalysts_full}
                    if "major_contract_win" not in existing_keys:
                        award = ticker_awards[0]
                        catalysts_full.append({
                            "key": "major_contract_win",
                            "tier": "S",
                            "points": 5.0,
                            "label": "Government contract win (SAM.gov)",
                            "details": f"{award.get('agency','?')} — {award.get('title','')[:80]}",
                            "direction": "bull",
                            "event_timing": "post_event",
                        })
                        catalysts_full.sort(key=lambda x: x["points"], reverse=True)
                        primary = catalysts_full[0]["points"]
                        secondary_bonus = sum(c["points"] for c in catalysts_full[1:]) * 0.25
                        base = min(primary + secondary_bonus, 5.0)
                        old_pts = target["components"]["catalyst_quality"].get("points", 0) or 0
                        new_pts = base * WEIGHT_CATALYST
                        target["components"]["catalyst_quality"]["points"] = round(new_pts, 2)
                        target["components"]["catalyst_quality"]["catalysts_full"] = catalysts_full
                        target["catalysts"] = catalysts_full
                        target["catalyst_tier"] = catalysts_full[0]["tier"]
                        target["score"] = round(target.get("score", 0) - old_pts + new_pts, 2)
                        target["sam_gov_awards"] = ticker_awards
            if verbose:
                print(f"    SAM.gov: {len(awards)} awards in window, matched to {len(sam_awards_by_ticker)} tickers in scan")
    except Exception as e:
        if verbose:
            print(f"    SAM.gov fetch failed: {type(e).__name__}: {str(e)[:100]}")

    pre_catalyst_watchlist = []
    upcoming_conferences = []
    if verbose:
        print(f"  building pre-catalyst watchlist (5-45 day forward earnings + signal stack)...")
    try:
        cohort_tickers = get_high_momentum_tickers()
        pre_catalyst_watchlist = build_pre_catalyst_watchlist(
            client, final_scored, cohort_tickers,
            days_min=5, days_max=45, verbose=verbose,
        )
        upcoming_conferences = get_upcoming_conferences(days_max=60)
        scored_by_ticker = {s.get("ticker"): s for s in final_scored}
        for w in pre_catalyst_watchlist:
            if w["pre_catalyst_verdict"] in ("HIGH_CONVICTION", "STRONG"):
                target = scored_by_ticker.get(w["ticker"])
                if target:
                    target["pre_catalyst_high_conviction"] = True
                    target["pre_catalyst_score"] = w["pre_catalyst_score"]
                    target["pre_catalyst_event_date"] = w["event_date"]
                    target["pre_catalyst_days_until"] = w["days_until"]
        if verbose:
            high_conv = sum(1 for w in pre_catalyst_watchlist if w["pre_catalyst_verdict"] == "HIGH_CONVICTION")
            strong = sum(1 for w in pre_catalyst_watchlist if w["pre_catalyst_verdict"] == "STRONG")
            print(f"  pre-catalyst watchlist: {len(pre_catalyst_watchlist)} names with earnings 5-45d out — {high_conv} HIGH_CONVICTION, {strong} STRONG")
    except Exception as e:
        if verbose:
            print(f"  pre-catalyst watchlist failed: {type(e).__name__}: {e}")

    forward_calendar = None
    try:
        watchlist_tickers = [c.get("ticker") for c in candidates[:60] if c.get("ticker")]
        vix_level = (macro or {}).get("vix") if macro else None
        forward_calendar = build_forward_calendar(client, watchlist_tickers, days_ahead=5,
                                                   target_date=scan_date_str, vix_level=vix_level)
        if verbose:
            ec = (forward_calendar.get("earnings") or {}).get("on_watchlist_count", 0)
            mc = len(forward_calendar.get("macro_events") or [])
            mt = len(forward_calendar.get("macro_trade_suggestions") or [])
            print(f"  forward calendar: {ec} watchlist earnings + {mc} macro events ({mt} trade plays) in 5d")
    except Exception as e:
        if verbose:
            print(f"  forward calendar failed: {type(e).__name__}: {e}")

    portfolio_summary = None
    yesterdays_followup = []
    win_rate_stats = None
    try:
        portfolio_summary = get_position_summary()
        yesterdays_followup = yesterdays_lottery_followup()
        win_rate_stats = get_recent_paper_trade_stats(lookback_days=30)
        if verbose:
            print(f"  portfolio: {portfolio_summary['n_open']}/{portfolio_summary['max_concurrent']} slots used, "
                  f"{len(yesterdays_followup)} closed yesterday, "
                  f"win rate (30d): {win_rate_stats['win_rate_pct'] if win_rate_stats else 'n/a'}%")
    except Exception as e:
        if verbose:
            print(f"  portfolio context failed: {type(e).__name__}: {e}")

    aa_results = None
    aa_picks = None
    aa_rejections = []
    regime_info = None
    v4_stats = None
    try:
        if verbose:
            print(f"=== V4 ELITE PIPELINE: bracket routing → A-only gates ===")
        regime_info = classify_vol_regime(macro)
        if verbose:
            print(f"  vol regime: {regime_info.get('regime')} → tier cap {regime_info.get('tier_cap')} · pos × {regime_info.get('position_multiplier')}")

        enrich_insider_quality(final_scored, verbose=verbose)
        enrich_allocator_tier(final_scored, verbose=verbose)
        enrich_composite_quality(final_scored, verbose=verbose)
        enrich_news_quality(final_scored, verbose=verbose)
        apply_peer_benchmarking(final_scored, verbose=verbose)
        apply_sector_rotation_gate(final_scored, macro, verbose=verbose)
        try:
            from src.catalyst.catalyst_windows import apply_catalyst_windows
            earnings_lookup = catalysts.get("earnings_lead_up") or {}
            apply_catalyst_windows(final_scored, verbose=verbose, earnings_lookup=earnings_lookup)
        except Exception as e:
            if verbose:
                print(f"  catalyst_windows failed (non-fatal): {type(e).__name__}: {e}")
        try:
            from src.catalyst.sentiment_layer import apply_sentiment_buzz_catalyst
            apply_sentiment_buzz_catalyst(final_scored, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  sentiment_buzz failed (non-fatal): {type(e).__name__}: {e}")
        apply_stacking(final_scored, verbose=verbose)

        bracketed = route_candidates(final_scored)
        if verbose:
            print(f"  bracket routing: micro={len(bracketed['micro'])} small={len(bracketed['small'])} mid={len(bracketed['mid'])} filtered={len(bracketed['filtered_out'])}")

        bracketed_filtered = {}
        for bracket in ("micro", "small", "mid"):
            bucket = bracketed[bracket]
            bucket, rejected_landmine = filter_landmines(bucket, verbose=verbose)
            bucket, rejected_extension = filter_extension(bucket, verbose=verbose)
            bucket, rejected_smart_money = filter_smart_money_required(bucket, bracket=bracket, verbose=verbose)
            bracketed_filtered[bracket] = bucket

        if verbose:
            total_filtered = sum(len(v) for v in bracketed_filtered.values())
            print(f"  pre-AA filtered total: {total_filtered}")

        top_candidates_for_research = []
        for bracket in ("micro", "small", "mid"):
            bracketed_filtered[bracket].sort(key=lambda s: s.get("_stacked_score") or s.get("score") or 0, reverse=True)
            top_candidates_for_research.extend(bracketed_filtered[bracket][:5])

        try:
            apply_iv_percentile(top_candidates_for_research, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  iv_percentile failed: {type(e).__name__}: {e}")

        try:
            apply_options_market_critic(top_candidates_for_research, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  options_market_critic failed: {type(e).__name__}: {e}")

        aa_results, aa_rejections = assign_tiers(bracketed_filtered, regime_info=regime_info, verbose=verbose)

        aa_picks = pick_top_per_bracket(aa_results, per_bracket=2)

        ranked_picks = []
        for tier in ("A++", "A+", "A"):
            for s in aa_results.get(tier) or []:
                ranked_picks.append(s)

        try:
            from src.catalyst.calendar_signals import enrich_macro_with_calendar
            macro = enrich_macro_with_calendar(macro or {})
            if verbose:
                cal_risks = (macro or {}).get("near_term_calendar_risks") or []
                if cal_risks:
                    print(f"  calendar signals: near-term risks = {cal_risks}")
        except Exception as e:
            if verbose:
                print(f"  calendar_signals failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.correlation_regime import compute_correlation_regime
            corr_info = compute_correlation_regime(client, lookback_days=30)
            if corr_info and macro is not None:
                macro["correlation_regime"] = corr_info
                if verbose:
                    print(f"  correlation_regime: {corr_info['regime']} avg={corr_info['avg_correlation']:.2f}")
        except Exception as e:
            if verbose:
                print(f"  correlation_regime failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.earnings_quality import apply_earnings_quality
            apply_earnings_quality(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  earnings_quality failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.news_sentiment import apply_news_sentiment
            apply_news_sentiment(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  news_sentiment failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.vol_microstructure import apply_vol_microstructure
            apply_vol_microstructure(ranked_picks[:10], eodhd_client=client, verbose=verbose, max_picks=10)
        except Exception as e:
            if verbose:
                print(f"  vol_microstructure failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.trade_survival_score import apply_survival_scores
            apply_survival_scores(ranked_picks, macro=macro, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  trade_survival_score failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.multi_leg_suggester import apply_multi_leg_suggestions
            apply_multi_leg_suggestions(ranked_picks, verbose=verbose, max_picks=5)
        except Exception as e:
            if verbose:
                print(f"  multi_leg_suggester failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.stage2_entry import apply_stage2_zones
            apply_stage2_zones(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  stage2_entry failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.fresh_context import apply_fresh_context
            apply_fresh_context(ranked_picks, max_picks=30, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  fresh_context failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.openinsider_scraper import apply_openinsider_signals
            apply_openinsider_signals(ranked_picks, days_back=14, min_buyers=2, min_value_usd=50_000, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  openinsider failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.options_flow_diy import apply_options_flow_diy
            apply_options_flow_diy(ranked_picks, max_picks=50, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  options_flow_diy failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.analyst_rating_news import apply_analyst_rating_news
            apply_analyst_rating_news(ranked_picks, max_picks=50, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  analyst_rating_news failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.earnings_whisper import apply_earnings_whisper
            apply_earnings_whisper(ranked_picks, max_picks=50, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  earnings_whisper failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.wsb_mentions import apply_wsb_mentions
            apply_wsb_mentions(ranked_picks, max_picks=10, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  wsb_mentions failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.google_trends_buzz import apply_google_trends
            apply_google_trends(ranked_picks, max_picks=10, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  google_trends failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.pead_scanner import apply_pead_scanner
            apply_pead_scanner(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  pead_scanner failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.edgar_keyword_scanner import apply_edgar_keyword_scanner
            apply_edgar_keyword_scanner(ranked_picks, max_picks=25, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  edgar_keyword_scanner failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.streetinsider_scraper import apply_streetinsider
            apply_streetinsider(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  streetinsider failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.whalewisdom_13f import apply_whalewisdom
            apply_whalewisdom(ranked_picks, max_picks=50, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  whalewisdom_13f failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.candidate_aggregator import discover_external_candidates, find_missed_high_quality_candidates
            external_candidates = discover_external_candidates(existing_picks=ranked_picks, verbose=verbose)
            missed = find_missed_high_quality_candidates(aa_results, external_candidates)
            if missed:
                if verbose:
                    print(f"  candidate_aggregator: {len(missed)} HIGH-QUALITY tickers our scan MISSED (from external signals):")
                    for m in missed[:10]:
                        sources_str = " + ".join(m["sources"])
                        print(f"    {m['ticker']:7} composite={m['composite_score']:3} via {sources_str}")
            if external_candidates and aa_results is not None:
                if "EXTERNAL_DISCOVERY" not in aa_results:
                    aa_results["EXTERNAL_DISCOVERY"] = []
                stub_externals = []
                for m in missed[:15]:
                    candidate_pick = {
                        "ticker": m["ticker"],
                        "_aa_tier": "EXT",
                        "_discovered_from": m["sources"],
                        "_discovery_reasons": m["reasons"],
                        "_discovery_composite_score": m["composite_score"],
                        "catalysts": [{"key": f"external_{s}", "label": r} for s, r in zip(m["sources"], m["reasons"])],
                    }
                    aa_results["EXTERNAL_DISCOVERY"].append(candidate_pick)
                    stub_externals.append(candidate_pick)

                try:
                    from src.catalyst.external_enrichment import enrich_externals
                    promoted = enrich_externals(stub_externals, client, max_enrich=5, run_haiku=True, verbose=verbose)
                    if promoted:
                        existing_tickers = {p.get("ticker") for p in ranked_picks if p.get("ticker")}
                        for p in promoted:
                            if p.get("ticker") and p["ticker"] not in existing_tickers:
                                ranked_picks.append(p)
                        if verbose:
                            print(f"  external_enrichment: {len(promoted)} externals merged into ranked_picks")
                except Exception as e:
                    if verbose:
                        print(f"  external_enrichment failed (non-fatal): {type(e).__name__}: {e}")
        except Exception as e:
            if verbose:
                print(f"  candidate_aggregator failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.overall_score import apply_overall_scores
            apply_overall_scores(ranked_picks, verbose=verbose, max_picks=50)
        except Exception as e:
            if verbose:
                print(f"  overall_score failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.macro_regime_detector import detect_macro_regime
            macro_regime = detect_macro_regime()
            if macro is None:
                macro = {}
            macro["macro_regime"] = macro_regime
            if verbose and macro_regime:
                print(f"  macro_regime: {macro_regime['regime']} ({macro_regime['score']}/100) - {macro_regime['label']}")
                for n in macro_regime.get('notes', [])[:5]:
                    print(f"    - {n}")
        except Exception as e:
            macro_regime = None
            if verbose:
                print(f"  macro_regime failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.macro_put_candidates import generate_macro_puts
            macro_puts = generate_macro_puts(macro_regime, verbose=verbose)
            if macro_puts:
                ranked_picks.extend(macro_puts)
                if "MACRO_PUT" not in aa_results:
                    aa_results["MACRO_PUT"] = []
                aa_results["MACRO_PUT"].extend(macro_puts)
        except Exception as e:
            if verbose:
                print(f"  macro_put_candidates failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.bearish_signals import apply_bearish_signals
            apply_bearish_signals(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  bearish_signals failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.signal_dedup import apply_signal_dedup
            apply_signal_dedup(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  signal_dedup failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.conviction_score import apply_conviction_scores
            apply_conviction_scores(ranked_picks, verbose=verbose, max_picks=60)
        except Exception as e:
            if verbose:
                print(f"  conviction_score failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.bear_conviction_score import apply_bear_conviction
            apply_bear_conviction(ranked_picks, verbose=verbose, max_picks=60)
        except Exception as e:
            if verbose:
                print(f"  bear_conviction failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.direction_picker import apply_directions
            apply_directions(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  direction_picker failed (non-fatal): {type(e).__name__}: {e}")

        def _provisional_score(p):
            c = (p.get("_conviction") or {}).get("score")
            if c is not None:
                try:
                    return float(c)
                except (TypeError, ValueError):
                    pass
            o = (p.get("_overall_score") or {}).get("score")
            try:
                return float(o) if o is not None else -1
            except (TypeError, ValueError):
                return -1

        ranked_picks.sort(key=lambda p: -_provisional_score(p))
        if verbose and ranked_picks:
            top_ranks = [(p.get("ticker"), int(_provisional_score(p))) for p in ranked_picks[:5]]
            print(f"  llm_target_selection: re-sorted by CONVICTION score, top 5 = {top_ranks}")

        top_pick = ranked_picks[0] if ranked_picks else None

        def _sector_bucket_simple(sec):
            s = (sec or "").lower()
            if "tech" in s or "communication" in s or "information" in s:
                return "Technology"
            if "health" in s or "pharma" in s or "biotech" in s:
                return "Healthcare"
            if "industrial" in s or "aerospace" in s or "defense" in s:
                return "Industrials"
            if "financial" in s or "bank" in s or "insurance" in s:
                return "Financials"
            if "consumer" in s or "retail" in s:
                return "Consumer"
            if "energy" in s or "oil" in s or "gas" in s:
                return "Energy"
            if "material" in s or "metal" in s or "mining" in s:
                return "Materials"
            return "Other"

        LLM_CONVICTION_THRESHOLD = 50
        LLM_HARD_CAP = 30

        def _overall_of(p):
            c = (p.get("_conviction") or {}).get("score")
            if c is not None:
                try:
                    return float(c)
                except (TypeError, ValueError):
                    pass
            v = (p.get("_overall_score") or {}).get("score")
            try:
                return float(v) if v is not None else -1
            except (TypeError, ValueError):
                return -1

        haiku_targets = [p for p in ranked_picks if _overall_of(p) >= LLM_CONVICTION_THRESHOLD][:LLM_HARD_CAP]

        if haiku_targets:
            if verbose:
                est_cost = len(haiku_targets) * 0.005
                tickers = [p.get("ticker") for p in haiku_targets]
                print(f"  haiku_synthesis: {len(haiku_targets)} Haiku bull calls (all picks Conviction >= {LLM_CONVICTION_THRESHOLD}): {', '.join(tickers[:10])}{'...' if len(tickers) > 10 else ''} ~${est_cost:.3f}")
            try:
                apply_haiku_synthesis(haiku_targets, max_calls=len(haiku_targets), verbose=verbose)
            except Exception as e:
                if verbose:
                    print(f"  haiku_synthesis failed (non-fatal): {type(e).__name__}: {e}")

        if haiku_targets:
            if verbose:
                print(f"  bear_case_verification: Haiku bear pass on {len(haiku_targets)} picks ~${len(haiku_targets)*0.005:.3f}")
            try:
                apply_bear_case_verification(haiku_targets, max_calls=len(haiku_targets), verbose=verbose)
            except Exception as e:
                if verbose:
                    print(f"  bear_case_verification failed (non-fatal): {type(e).__name__}: {e}")

        buy_after_synthesis = []
        for p in haiku_targets:
            haiku = p.get("haiku_synthesis") or {}
            verdict = haiku.get("verdict")
            bear = p.get("bear_verification") or {}
            is_trap = bear.get("is_this_trade_a_trap") or False
            if verdict in ("BUY", "STRONG_BUY") and not is_trap:
                bull_conf = haiku.get("confidence_pct") or 0
                bear_conv = bear.get("bear_conviction_pct") or 0
                p["_net_edge"] = bull_conf - bear_conv
                buy_after_synthesis.append(p)

        buy_after_synthesis.sort(key=lambda p: -(p.get("_net_edge") or 0))

        top_pick = buy_after_synthesis[0] if buy_after_synthesis else None

        if top_pick:
            if verbose:
                net = top_pick.get("_net_edge")
                print(f"  sonnet_deep_dive: 1 Sonnet+web call on email #1 ({top_pick['ticker']} net_edge={net}) ~$1.20")
            try:
                apply_unified_forensic([top_pick], max_calls=1, verbose=verbose)
            except Exception as e:
                if verbose:
                    print(f"  sonnet_deep_dive failed (non-fatal): {type(e).__name__}: {e}")
        else:
            if verbose:
                print(f"  sonnet_deep_dive: SKIPPED - no BUY-rated picks remain after Haiku bull+bear synthesis (saved $1.20)")

        try:
            from src.catalyst.overall_score import apply_overall_scores as _apply_final_overall
            _apply_final_overall(ranked_picks, verbose=verbose, max_picks=50)
        except Exception as e:
            if verbose:
                print(f"  overall_score final recompute failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.signal_dedup import apply_signal_dedup as _apply_final_dedup
            _apply_final_dedup(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  signal_dedup final recompute failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.forward_calendar import enrich_picks_with_forward_catalyst
            enrich_picks_with_forward_catalyst(ranked_picks, max_picks=30, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  forward_calendar enrichment failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.vcp_detector import enrich_picks_with_vcp
            enrich_picks_with_vcp(ranked_picks, max_picks=30, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  vcp_detector enrichment failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.iv_window import enrich_picks_with_iv_window
            enrich_picks_with_iv_window(ranked_picks, max_picks=30, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  iv_window enrichment failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.confluence import apply_confluence
            apply_confluence(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  confluence detector failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.conviction_score import apply_conviction_scores as _apply_final_conviction
            _apply_final_conviction(ranked_picks, verbose=verbose, max_picks=60)
            from src.catalyst.bear_conviction_score import apply_bear_conviction as _apply_final_bear
            _apply_final_bear(ranked_picks, verbose=verbose, max_picks=60)
            from src.catalyst.direction_picker import apply_directions as _apply_final_dirs
            _apply_final_dirs(ranked_picks, verbose=verbose)

            def _winning_score(p):
                d = p.get("_direction") or {}
                return d.get("winning_score") or 0

            ranked_picks.sort(key=lambda p: -_winning_score(p))
            if verbose and ranked_picks:
                final_top = []
                for p in ranked_picks[:5]:
                    d = p.get("_direction") or {}
                    final_top.append((p.get("ticker"), d.get("side"), int(_winning_score(p))))
                print(f"  FINAL ranking (call/put unified): top 5 = {final_top}")
        except Exception as e:
            if verbose:
                print(f"  final scoring failed (non-fatal): {type(e).__name__}: {e}")

        try:
            measure_catalyst_performance(lookback_days=90, verbose=verbose)
            annotate_picks_with_performance(ranked_picks, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  catalyst_performance failed (non-fatal): {type(e).__name__}: {e}")

        try:
            from src.catalyst.position_intelligence import confirm_new_pick
            from src.catalyst.action_signal import compute_action
            confirmed = 0
            blocked = 0
            for p in ranked_picks[:15]:
                action = (p.get("_action_signal") or compute_action(p)).get("action")
                if action != "TAKE":
                    continue
                passes, _ = confirm_new_pick(p, verbose=False)
                if not passes:
                    p["_action_signal"] = {"action": "SKIP", "badge": "SKIP",
                                           "reason_code": "entry_intel_blocked",
                                           "why": "Failed 7-factor entry check (need 3+ pass, max 1 fail)"}
                    blocked += 1
                else:
                    confirmed += 1
            if verbose:
                print(f"  entry_intelligence: {confirmed} TAKE picks confirmed, {blocked} downgraded to SKIP")
        except Exception as e:
            if verbose:
                print(f"  entry_intelligence failed (non-fatal): {type(e).__name__}: {e}")

        all_picks_flat = []
        for bracket in ("micro", "small", "mid"):
            all_picks_flat.extend(aa_picks.get(bracket, []))
        for s in all_picks_flat:
            try:
                apply_pre_mortem([s], verbose=False)
            except Exception:
                pass

        try:
            log_v4_picks(scan_date_str, ranked_picks, top_pick=top_pick, haiku_picks=haiku_targets, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  v4_paper_log log failed: {type(e).__name__}: {e}")

        try:
            measure_v4_outcomes(client, target_date=scan_date_str, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  v4_paper_log measure failed: {type(e).__name__}: {e}")

        try:
            v4_stats = get_v4_stats(days_back=30)
            if verbose and v4_stats:
                print(f"  v4 paper log (30d): {v4_stats.get('total_picks_measured', 0)} measured")
                for rank, summary in (v4_stats.get('by_rank') or {}).items():
                    if summary:
                        print(f"    rank #{rank}: {summary['n']} picks, t1 win {summary['win_rate_t1_pct']}%, avg best {summary['avg_best_pct']}%")
        except Exception as e:
            v4_stats = None
            if verbose:
                print(f"  v4_paper_log get_stats failed: {type(e).__name__}: {e}")
        if verbose:
            total = sum(len(v) for v in aa_picks.values())
            print(f"=== V4 OUTPUT: {total} A-grade picks (A++ {len(aa_results['A++'])}, A+ {len(aa_results['A+'])}, A {len(aa_results['A'])}) ===")
    except Exception as e:
        if verbose:
            import traceback
            print(f"  V4 pipeline failed (non-fatal): {type(e).__name__}: {e}")
            traceback.print_exc()

    conviction_drift_alerts = []
    conviction_journal_stats = None
    try:
        try:
            from src.catalyst.conviction_trend import apply_trends
            _trend_scan = {"scan_date": scan_date_str, "aa_results": aa_results}
            apply_trends(_trend_scan, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  conviction_trend failed (non-fatal): {type(e).__name__}: {e}")

        _scan_for_journal = {
            "scan_date": scan_date_str,
            "macro": macro,
            "aa_results": aa_results,
        }
        log_conviction_picks(_scan_for_journal, verbose=verbose)
        try:
            mark_conviction_forward(client, target_date=scan_date_str, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  conviction_journal mark_forward failed: {type(e).__name__}: {e}")
        try:
            conviction_drift_alerts = check_conviction_drift(_scan_for_journal, verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  conviction_drift check failed: {type(e).__name__}: {e}")
        try:
            conviction_journal_stats = get_conviction_stats(days_back=60)
            if verbose and conviction_journal_stats:
                by_side = conviction_journal_stats.get("by_side") or {}
                cs = by_side.get("CALL") or {}
                ps = by_side.get("PUT") or {}
                print(f"  conviction_journal stats (60d): {conviction_journal_stats.get('total_measured', 0)} measured  CALL n={cs.get('n', 0)} win={cs.get('win_rate_pct', 0)}%  PUT n={ps.get('n', 0)} win={ps.get('win_rate_pct', 0)}%")
        except Exception as e:
            if verbose:
                print(f"  conviction_journal stats failed: {type(e).__name__}: {e}")
    except Exception as e:
        if verbose:
            import traceback
            print(f"  conviction_journal pipeline failed (non-fatal): {type(e).__name__}: {e}")
            traceback.print_exc()

    try:
        from src.catalyst.barchart_premier import annotate_picks_with_barchart
        annotate_picks_with_barchart(ranked_picks[:20], verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  barchart annotate failed (non-fatal): {type(e).__name__}: {e}")

    try:
        from src.catalyst.unusual_whales import annotate_picks_with_flow
        annotate_picks_with_flow(ranked_picks[:20], verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  unusual_whales annotate failed (non-fatal): {type(e).__name__}: {e}")

    try:
        from src.catalyst.insiderfinance import annotate_picks_with_insiderfinance
        annotate_picks_with_insiderfinance(ranked_picks[:20], verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  insiderfinance annotate failed (non-fatal): {type(e).__name__}: {e}")

    guardrail_state = None
    try:
        from src.catalyst.guardrails import evaluate as evaluate_guardrails
        guardrail_state = evaluate_guardrails(verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  guardrails evaluate failed (non-fatal): {type(e).__name__}: {e}")

    position_intel = []
    try:
        from src.catalyst.position_intelligence import analyze_all_live_positions
        position_intel = analyze_all_live_positions(verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  position_intelligence failed (non-fatal): {type(e).__name__}: {e}")

    return {
        "scan_date": scan_date_str,
        "macro": macro,
        "tracker_stats": tracker_stats,
        "paper_stats": paper_stats,
        "conviction_drift_alerts": conviction_drift_alerts,
        "conviction_journal_stats": conviction_journal_stats,
        "guardrail_state": guardrail_state,
        "position_intelligence": position_intel,
        "candidates_total": len(per_ticker),
        "enriched_total": len(enriched),
        "scored_total": len(final_scored),
        "passed_cutoff": len(candidates),
        "top_pct_strong": top_pct_strong,
        "top_pct_watch": top_pct_watch,
        "candidates": candidates,
        "all_scored": final_scored,
        "rebalance_candidates": rebalance,
        "pre_catalyst_watchlist": pre_catalyst_watchlist,
        "upcoming_conferences": upcoming_conferences,
        "forward_calendar": forward_calendar,
        "portfolio_summary": portfolio_summary,
        "yesterdays_followup": yesterdays_followup,
        "win_rate_stats": win_rate_stats,
        "aa_results": aa_results,
        "aa_picks": aa_picks,
        "aa_rejections": aa_rejections,
        "vol_regime_info": regime_info,
        "v4_stats": v4_stats,
        "eodhd_calls": client.calls_made,
        "edgar_calls": edgar.calls_made,
        "llm_graded": len(llm_grades),
    }

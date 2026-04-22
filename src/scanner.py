import json
import pathlib
import time
import sys
import traceback

from src.eodhd import EODHDClient
from src.indicators import to_dataframe, compute_all
from src.pillars import (
    pillar_1_trend_following,
    pillar_2_volatility_breakout,
    pillar_3_can_slim,
    pillar_4_statarb,
    pillar_5_global_macro,
    pillar_6_erm,
    pillar_7_short_squeeze,
    gate_3_rvol,
    gate_4_catalyst,
    gate_6_liquidity,
    gate_7_earnings_blackout,
    pick_benchmark,
)
from src.scoring import score_candidate, build_trade_ticket
from src.sectors import fetch_sector_performance, sector_maturity_map, GICS_TO_ETF
from src.conviction import conviction_score, compute_composite_rs_percentiles
from src.stress_tests import run_stress_tests
from src.options_suggest import suggest_options_trade
from src.breadth import compute_market_breadth
from src.telegram import send_swing_alerts
from src.lane_b import run_all_lane_b, compute_peer_pack_rotation, lane_b_signal_count

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
UNIVERSE_PATH = PROJECT_ROOT / "data" / "universe" / "universe.json"
RESULTS_DIR = PROJECT_ROOT / "data" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

from datetime import datetime, timedelta
FROM_DATE = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")


def load_universe(limit=None):
    with open(UNIVERSE_PATH) as f:
        tickers = json.load(f)
    if limit:
        tickers = tickers[:limit]
    return tickers


def fast_filter(client, ticker_row, spy_df, vix_pillar, ftse_df):
    ticker = ticker_row["ticker"]
    is_us = ticker.endswith(".US")

    ohlcv = client.ohlcv(ticker, from_date=FROM_DATE)
    if not ohlcv or len(ohlcv) < 210:
        return None, "insufficient ohlcv history"

    df = to_dataframe(ohlcv)
    ind = compute_all(df)
    last_close = float(ind["close"].iloc[-1])
    if last_close < 5:
        return None, "sub-$5 price filter"

    p1 = pillar_1_trend_following(ind)
    if p1["verdict"] == "FAIL":
        return None, f"p1 fail: {p1['trend_template_passed']}/7 template, stage {p1['stage']}"

    benchmark_df = ftse_df if ticker.endswith(".LSE") else spy_df
    p4 = pillar_4_statarb(ind, benchmark_df, lookback=20)
    if p4["verdict"] == "FAIL":
        return None, f"p4 fail: rs={p4.get('rs_score', 0):.2f}"

    return {
        "ticker": ticker,
        "name": ticker_row.get("name", ""),
        "index": ticker_row.get("index", ""),
        "sector_hint": ticker_row.get("sector", ""),
        "is_us": is_us,
        "df": df,
        "ind": ind,
        "p1": p1,
        "p4": p4,
    }, None


def full_score(client, candidate, vix_pillar):
    ticker = candidate["ticker"]
    ind = candidate["ind"]
    is_us = candidate["is_us"]

    try:
        fundamentals = client.fundamentals(ticker)
    except Exception:
        fundamentals = None
    if not fundamentals:
        return None, "no fundamentals"

    p2 = pillar_2_volatility_breakout(ind)
    p3 = pillar_3_can_slim(fundamentals)
    p6 = pillar_6_erm(fundamentals, is_us)

    try:
        insider = client.insider_transactions(ticker, limit=20) if is_us else None
    except Exception:
        insider = None
    p7 = pillar_7_short_squeeze(fundamentals, ind, insider, is_us)

    try:
        news = client.news(ticker, limit=20)
    except Exception:
        news = None

    g3 = gate_3_rvol(ind)
    g4 = gate_4_catalyst(fundamentals, news)
    g6 = gate_6_liquidity(fundamentals, ind)
    g7 = gate_7_earnings_blackout(fundamentals, ind)

    pillars = {
        "pillar_1": candidate["p1"],
        "pillar_2": p2,
        "pillar_3": p3,
        "pillar_4": candidate["p4"],
        "pillar_5": vix_pillar,
        "pillar_6": p6,
        "pillar_7": p7,
    }
    gates = {
        "gate_3": g3,
        "gate_4": g4,
        "gate_6": g6,
        "gate_7": g7,
        "gate_5_modifier": {"direction": "neutral"},
    }

    tier_info = score_candidate(pillars, gates, is_us)
    price = float(ind["close"].iloc[-1])
    general = fundamentals.get("General", {}) or {}
    name = general.get("Name", candidate["name"])
    sector = general.get("Sector", "") or ""
    industry = general.get("Industry", "") or ""
    description = general.get("Description", "") or ""
    ticket = build_trade_ticket(
        ticker, name, price, tier_info, pillars, gates,
        vix_pillar.get("regime", "unknown"),
        sector=sector, industry=industry, description=description,
    )

    return {
        "ticket": ticket,
        "pillars": pillars,
        "gates": gates,
        "tier_info": tier_info,
        "ind": ind,
        "fundamentals": fundamentals,
        "sector": sector,
        "insider": insider,
    }, None


def run_scan(universe_limit=None, verbose=True):
    client = EODHDClient()
    universe = load_universe(limit=universe_limit)

    if verbose:
        print(f"Loading benchmarks (SPY, VUKE, VIX)...")
    spy_df = to_dataframe(client.ohlcv("SPY.US", from_date=FROM_DATE))
    try:
        vuke_df = to_dataframe(client.ohlcv("VUKE.LSE", from_date=FROM_DATE))
    except Exception:
        vuke_df = spy_df

    try:
        vix_ohlcv = client.ohlcv("VIX.INDX", from_date=FROM_DATE)
        vix_df = to_dataframe(vix_ohlcv) if vix_ohlcv else None
    except Exception:
        vix_df = None
    vix_pillar = pillar_5_global_macro(vix_df)
    if verbose:
        print(f"VIX regime: {vix_pillar.get('regime')} (vix={vix_pillar.get('vix')})")

    sector_perf = fetch_sector_performance(client, spy_df, FROM_DATE)
    breadth = compute_market_breadth(client)
    if verbose:
        print(f"Sector ETFs loaded: {len(sector_perf)}")
        print(f"Breadth: {breadth['regime']} ({breadth.get('pct_above_200', '?')}% above 200d MA)")
        print(f"Scanning {len(universe)} tickers...")

    candidates = []
    fast_rejected = 0
    errors = 0
    start = time.time()
    for i, row in enumerate(universe):
        if verbose and i > 0 and i % 100 == 0:
            elapsed = time.time() - start
            rate = i / elapsed
            eta = (len(universe) - i) / rate
            print(f"  [{i}/{len(universe)}] kept={len(candidates)} rejected={fast_rejected} err={errors} rate={rate:.1f}/s eta={eta/60:.1f}m")
        try:
            c, reason = fast_filter(client, row, spy_df, vix_pillar, vuke_df)
            if c:
                candidates.append(c)
            else:
                fast_rejected += 1
        except Exception as e:
            errors += 1
            if verbose and errors < 5:
                print(f"  error on {row['ticker']}: {type(e).__name__}: {e}")

    if verbose:
        print(f"\nFast filter: {len(candidates)} candidates survived, {fast_rejected} rejected, {errors} errors")
        print(f"Running full scoring on {len(candidates)} candidates...")

    scored = []
    for c in candidates:
        try:
            result, reason = full_score(client, c, vix_pillar)
            if result:
                scored.append(result)
        except Exception as e:
            errors += 1
            if verbose and errors < 10:
                print(f"  score error on {c['ticker']}: {type(e).__name__}: {e}")
                traceback.print_exc()

    if verbose:
        print(f"\nComputing Lane B detectors (pocket pivot / base quality / insider cluster / revenue accel / earnings turn)...")
    for r in scored:
        lane_b = run_all_lane_b(r["ind"], r.get("fundamentals"), r.get("insider"))
        r["lane_b"] = lane_b
        r["ticket"]["lane_b"] = lane_b

    if verbose:
        print(f"Computing peer pack rotation across {len(scored)} scored names...")
    peer_signals = compute_peer_pack_rotation(scored)
    for r in scored:
        sig = peer_signals.get(r["ticket"]["ticker"])
        if sig:
            r["lane_b"]["peer_pack"] = sig
            r["ticket"]["lane_b"]["peer_pack"] = sig
        else:
            r["lane_b"]["peer_pack"] = {"fired": False}
            r["ticket"]["lane_b"]["peer_pack"] = {"fired": False}

    for r in scored:
        r["ticket"]["lane_b_signal_count"] = lane_b_signal_count(r["lane_b"])

    if verbose:
        lb_hits = sum(1 for r in scored if r["ticket"]["lane_b_signal_count"] > 0)
        print(f"  Lane B signals: {lb_hits} names fired at least one detector")

    maturity_by_short = sector_maturity_map(sector_perf)
    for r in scored:
        sec = r["ticket"].get("sector") or ""
        short = GICS_TO_ETF.get(sec, (None, None))[1]
        maturity = maturity_by_short.get(short, "N/A")
        r["ticket"]["sector_maturity"] = maturity

    if verbose:
        print(f"\nComputing conviction scores and stress tests for Tier 3+ candidates...")
    actionable_ind = {r["ticket"]["ticker"]: r["ind"] for r in scored if r["tier_info"]["tier"] and r["tier_info"]["tier"] >= 3}
    rs_percentiles = compute_composite_rs_percentiles(actionable_ind)

    for r in scored:
        tier = r["tier_info"]["tier"]
        if not tier or tier < 3:
            r["ticket"]["conviction"] = None
            r["ticket"]["stress"] = None
            continue
        ticker = r["ticket"]["ticker"]
        bench = vuke_df if ticker.endswith(".LSE") else spy_df
        cs = conviction_score(
            ticker=ticker,
            df_ind=r["ind"],
            fundamentals=r["fundamentals"],
            sector=r["sector"],
            sector_performance=sector_perf,
            composite_rs_percentile=rs_percentiles.get(ticker),
        )
        st = run_stress_tests(r["ind"], bench)
        r["ticket"]["conviction"] = cs
        r["ticket"]["stress"] = st

    scored.sort(
        key=lambda r: (
            r["tier_info"]["tier"] or 0,
            (r["ticket"].get("conviction") or {}).get("score", -1),
            r["tier_info"]["pillars_passed"],
        ),
        reverse=True,
    )

    top_conviction_us = [
        r for r in scored
        if r["ticket"].get("conviction")
        and r["ticket"]["ticker"].endswith(".US")
        and r["ticket"].get("tier", 0) >= 3
    ]
    top_conviction_us.sort(
        key=lambda r: r["ticket"]["conviction"]["score"],
        reverse=True,
    )
    if verbose:
        print(f"\nFetching options trade suggestions for top 3 conviction US picks...")
    for r in top_conviction_us[:3]:
        try:
            t = r["ticket"]
            opt = suggest_options_trade(
                ticker=t["ticker"],
                phase1_target=t["phase1_target"],
                current_price=t["price"],
                df_ind=r["ind"],
            )
            t["options_trade"] = opt
            if verbose and opt:
                print(f"  {t['ticker']}: {opt['strike']:.0f}C {opt['expiration']} @ ${opt['premium_mid']:.2f} (delta {opt['delta']}, ROI if target {opt['projected_roi_pct']:.0f}%)")
            elif verbose:
                print(f"  {t['ticker']}: no suitable contract found")
        except Exception as e:
            if verbose:
                print(f"  options fetch error on {r['ticket']['ticker']}: {type(e).__name__}: {e}")

    tickets_for_alerts = [r["ticket"] for r in scored]
    try:
        sent = send_swing_alerts(tickets_for_alerts, min_tier=4, tier4_min_conviction=70)
        if verbose and sent:
            print(f"Sent {sent} Telegram alerts")
    except Exception as e:
        if verbose:
            print(f"Telegram alert batch failed: {e}")

    if verbose:
        print(f"\nScored {len(scored)} candidates. Top tier breakdown:")
        from collections import Counter
        tiers = Counter(r["tier_info"]["tier"] for r in scored)
        for t in sorted(tiers.keys(), reverse=True):
            print(f"  Tier {t}: {tiers[t]}")
        top5 = [r for r in scored if r["ticket"].get("conviction")][:5]
        if top5:
            print(f"Top 5 by conviction:")
            for r in top5:
                cs = r["ticket"]["conviction"]
                st = r["ticket"]["stress"]
                print(f"  {r['ticket']['ticker']:12s} T{r['tier_info']['tier']} conv={cs['score']}/100 stress={st['overall']}")
        print(f"Total API calls: {client.calls_made}")

    return {
        "scan_date": time.strftime("%Y-%m-%d"),
        "vix_regime": vix_pillar,
        "sector_performance": sector_perf,
        "breadth": breadth,
        "universe_size": len(universe),
        "fast_filter_survivors": len(candidates),
        "scored_total": len(scored),
        "api_calls": client.calls_made,
        "results": scored,
    }


def save_results(scan, path=None):
    out_path = path or RESULTS_DIR / f"scan_{scan['scan_date']}.json"
    serializable = {
        "scan_date": scan["scan_date"],
        "vix_regime": scan["vix_regime"],
        "sector_performance": scan.get("sector_performance", []),
        "universe_size": scan["universe_size"],
        "fast_filter_survivors": scan["fast_filter_survivors"],
        "scored_total": scan["scored_total"],
        "api_calls": scan["api_calls"],
        "tickets": [r["ticket"] for r in scan["results"]],
    }
    with open(out_path, "w") as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"Saved {out_path}")
    return out_path


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    scan = run_scan(universe_limit=limit)
    save_results(scan)

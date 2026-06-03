"""Positioning-First Scoring Engine - Phase 4a (Path 3 / Option C rebuild).

Replaces backward-looking gating with positioning-driven ranking.

Runs BEFORE bracket_routing, AA gates, landmine filter etc. so that positioning
extremes drive which tickers ever reach the email - not yesterday's price action
filtering out a ticker before its forward-looking positioning thesis is computed.

Bidirectional symmetric logic:
  CALL candidates fire when:
    - COT regime CROWDED_SHORT (mean reversion long edge)  OR
    - Macro regime RISK_ON + sector/squeeze tailwind        OR
    - GEX NEGATIVE_AMP (dealers short calls = amplification up)
  PUT candidates fire when:
    - COT regime CROWDED_LONG (peak positioning = exhaustion)
    - Macro regime RISK_OFF_PRESSURE + extension above 200dma
    - GEX positive on extended name (pinning + downside vol)
    - Sentiment GREED_EXTREME + SKEW elevated

Weighting (the architectural change vs old pipeline):
  POSITIONING signals     -> FULL weight (1.0)
  BACKWARD-LOOKING tech   -> HALF weight (0.5)
    (VCP, pocket pivot, quiet RS, MTF trend, auction level)

Output per pick:
  _positioning_first = {
    "score": int 0-100,
    "side": "CALL" | "PUT" | "NEUTRAL",
    "bull_score": int,
    "bear_score": int,
    "positioning_signals": [list of firing positioning signals],
    "technical_signals_half_weight": [list of firing backward signals at 0.5],
    "thesis": "plain english thesis",
    "regime_context": "RISK_ON" | "RISK_OFF" | "NEUTRAL",
    "conviction_tier": "ELITE" | "STRONG" | "MODERATE" | "WEAK",
  }
"""

from datetime import datetime


POSITIONING_WEIGHT = 1.0
TECHNICAL_WEIGHT = 0.5


def _bull_positioning_score(pick, macro_regime):
    """Score how much positioning supports a CALL trade. Out of 100."""
    score = 0
    signals = []

    cot = pick.get("_cot_positioning") or {}
    regime = cot.get("regime")
    if regime == "CROWDED_SHORT":
        score += 25
        signals.append({"key": "cot_crowded_short", "label": cot.get("label") or "COT crowded short = mean reversion long edge", "pts": 25})
    elif regime == "MODERATELY_SHORT":
        score += 15
        signals.append({"key": "cot_lean_short", "label": cot.get("label") or "COT lean short", "pts": 15})

    gex = pick.get("_dealer_gex") or pick.get("_if_gex") or {}
    if gex.get("regime") == "NEGATIVE_AMP":
        score += 20
        signals.append({"key": "gex_amplification", "label": "negative GEX (amplification regime - gamma squeeze tailwind)", "pts": 20})

    if macro_regime == "RISK_ON":
        score += 20
        signals.append({"key": "macro_risk_on", "label": "macro: RISK_ON regime", "pts": 20})
    elif macro_regime == "NEUTRAL":
        score += 5
        signals.append({"key": "macro_neutral", "label": "macro: neutral (no tailwind/headwind)", "pts": 5})

    opt_pos = pick.get("_options_positioning") or {}
    findings = opt_pos.get("findings") or []
    for f in findings:
        sig = f.get("signal") if isinstance(f, dict) else None
        if sig in ("CPC_EXTREME_PUTS", "CPCE_RETAIL_PUTS"):
            score += 15
            signals.append({"key": "pc_extreme_puts", "label": f.get("label") or "extreme put buying = contrarian long edge", "pts": 15})
            break
        if sig == "VIX_DEEP_CONTANGO":
            score += 10
            signals.append({"key": "vix_contango", "label": "VIX deep contango = complacency dispelled on rallies", "pts": 10})
            break

    squeeze = pick.get("_squeeze_setup") or {}
    if squeeze.get("fires"):
        sq_score = squeeze.get("score") or 50
        pts = min(15, sq_score // 5)
        score += pts
        signals.append({"key": "squeeze_loaded", "label": squeeze.get("label") or "squeeze setup loaded", "pts": pts})

    sentiment = pick.get("_sentiment_stack") or {}
    sentiment_findings = sentiment.get("findings") or []
    for f in sentiment_findings:
        sig = f.get("signal") if isinstance(f, dict) else None
        if sig == "STACKED_FEAR_EXTREME":
            score += 15
            signals.append({"key": "stacked_fear", "label": f.get("label") or "stacked sentiment extremes - high-conviction contrarian long", "pts": 15})
            break
        if sig == "FEAR_EXTREME":
            score += 10
            signals.append({"key": "sentiment_fear", "label": "F&G in extreme fear = contrarian long edge", "pts": 10})
            break

    pb = pick.get("_pb_flow") or {}
    if pb.get("aligned") and (pb.get("side") or "").upper() == "LONG":
        score += 10
        signals.append({"key": "pb_long_flow", "label": pb.get("label") or "PB flow aligned long", "pts": 10})

    ar = pick.get("_analyst_revisions") or {}
    if ar.get("verdict") == "POSITIVE_REVISIONS":
        score += 5
        signals.append({"key": "analyst_revisions_up", "label": ar.get("label") or "positive EPS revisions", "pts": 5})

    # FINRA margin debt CAPITULATION_BOTTOM = late-stage forced selling = contrarian long edge.
    margin = pick.get("_finra_margin_regime") or {}
    if margin.get("regime") == "CAPITULATION_BOTTOM":
        score += 10
        signals.append({"key": "margin_capitulation", "label": margin.get("label") or "margin debt capitulation", "pts": 10})

    # === Unusual Whales institutional signals (educator's 6 signals) ===

    uw_flow = pick.get("_uw_flow") or {}
    if uw_flow.get("dominant_side") == "CALL" and uw_flow.get("call_put_ratio", 0) >= 2:
        score += 18
        signals.append({"key": "uw_call_dominant_flow",
                        "label": f"UW: {uw_flow['calls']} calls / {uw_flow['puts']} puts (${uw_flow['total_premium']/1e6:.1f}M premium) = institutional call buying",
                        "pts": 18})

    uw_gex = pick.get("_uw_gex") or {}
    if uw_gex.get("dealer_regime") == "NEGATIVE_AMP":
        score += 15
        signals.append({"key": "uw_negative_gex",
                        "label": uw_gex.get("label") or "negative net GEX = dealer amplification regime",
                        "pts": 15})

    # 0DTE call dominance = squeeze setup
    if uw_flow.get("zero_dte_share", 0) >= 0.30 and uw_flow.get("dominant_side") == "CALL":
        score += 12
        signals.append({"key": "uw_0dte_call_squeeze",
                        "label": f"UW: {int(uw_flow['zero_dte_share']*100)}% of flow is 0DTE calls = gamma squeeze risk",
                        "pts": 12})

    uw_iv = pick.get("_uw_iv") or {}
    if uw_iv.get("iv_rank") is not None and uw_iv["iv_rank"] < 30:
        score += 8
        signals.append({"key": "uw_iv_cheap",
                        "label": f"UW: IV rank {uw_iv['iv_rank']:.0f} = options cheap, asymmetric upside",
                        "pts": 8})

    uw_dp = pick.get("_uw_dark_pool") or {}
    if uw_dp.get("total_value_usd", 0) >= 5_000_000:
        score += 8
        signals.append({"key": "uw_dark_pool_accumulation",
                        "label": f"UW: ${uw_dp['total_value_usd']/1e6:.1f}M dark pool prints = institutional accumulation",
                        "pts": 8})

    # Lever 2: free per-ticker bull signals from data already attached in Step 2 enrichment.
    # Zero API cost - all derived from price action + fundamentals already on disk.

    # Short percent float extreme (squeeze candidate)
    short_pct = pick.get("short_pct_float")
    try:
        if short_pct is not None and float(short_pct) >= 20:
            score += 15
            signals.append({"key": "high_short_pct", "label": f"short interest {float(short_pct):.0f}% float = squeeze loaded", "pts": 15})
        elif short_pct is not None and float(short_pct) >= 12:
            score += 8
            signals.append({"key": "elevated_short_pct", "label": f"short interest {float(short_pct):.0f}% float = squeeze potential", "pts": 8})
    except (TypeError, ValueError):
        pass

    # Days to cover - synthesize from short% + dollar volume
    try:
        if short_pct is not None and pick.get("dollar_volume_20d") and pick.get("price"):
            short_shares = float(short_pct) / 100 * (pick.get("market_cap") or 0) / (pick["price"] or 1)
            daily_vol_shares = (pick["dollar_volume_20d"] or 1) / (pick["price"] or 1)
            if daily_vol_shares > 0:
                dtc = short_shares / daily_vol_shares
                if dtc >= 5:
                    score += 10
                    signals.append({"key": "days_to_cover_high", "label": f"days to cover {dtc:.1f} = squeeze pressure", "pts": 10})
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    # Base building near 200dma (key support test)
    pct_above_200 = pick.get("pct_above_200dma")
    try:
        if pct_above_200 is not None:
            v = float(pct_above_200)
            if -10 <= v <= 5:
                score += 10
                signals.append({"key": "base_near_200dma", "label": f"price {v:+.1f}% from 200dma = base build near key MA", "pts": 10})
    except (TypeError, ValueError):
        pass

    # Near 52w low (deep value / capitulation)
    pct_off_low = pick.get("pct_off_52w_low")
    try:
        if pct_off_low is not None and float(pct_off_low) < 15:
            score += 8
            signals.append({"key": "near_52w_low", "label": f"{float(pct_off_low):.0f}% off 52w low = capitulation zone", "pts": 8})
    except (TypeError, ValueError):
        pass

    # Volatility contraction (VCP precursor) - 5d return absolute value low + 30d return positive
    ret_5d = pick.get("ret_5d")
    ret_30d = pick.get("ret_30d")
    try:
        if ret_5d is not None and ret_30d is not None:
            r5 = float(ret_5d)
            r30 = float(ret_30d)
            if abs(r5) < 2 and r30 > 0 and r30 < 15:
                score += 10
                signals.append({"key": "volatility_contraction", "label": f"5d range {r5:+.1f}% (tight) + 30d {r30:+.1f}% = VCP precursor", "pts": 10})
    except (TypeError, ValueError):
        pass

    # Dollar volume expanding (accumulation) - inferred from above_200dma + 30d positive return
    try:
        if pct_above_200 is not None and ret_30d is not None:
            if 0 <= float(pct_above_200) <= 25 and float(ret_30d) > 5:
                score += 8
                signals.append({"key": "accumulation", "label": "stage 2 trend setup (above 200dma + 30d positive)", "pts": 8})
    except (TypeError, ValueError):
        pass

    return min(score, 100), signals


def _bear_positioning_score(pick, macro_regime):
    """Score how much positioning supports a PUT trade. Out of 100.

    Path 3 Fix 2: macro-overlay points (cot crowded long, macro risk-off, margin
    euphoria, stacked greed, etc.) only count if at least ONE per-ticker bear
    signal fires. Otherwise every Tech name gets 40+ pts from macro alone,
    burying fresh extension PUTs (AMD/AMAT/INTC) under already-broken names
    (CAG/CMG that have already cratered).
    """
    score = 0
    signals = []

    # === PER-TICKER BEAR SIGNALS (must have at least 1 for macro overlay to count) ===

    per_ticker_pts = 0
    pct_above_200 = pick.get("pct_above_200dma")
    try:
        if pct_above_200 is not None:
            v = float(pct_above_200)
            if v > 40:
                per_ticker_pts += 15
                signals.append({"key": "extension_above_200_extreme", "label": f"extended {v:.0f}% above 200dma = climax risk", "pts": 15})
            elif v > 25:
                per_ticker_pts += 10
                signals.append({"key": "extension_above_200", "label": f"extended {v:.0f}% above 200dma", "pts": 10})
            elif v > 15:
                per_ticker_pts += 5
                signals.append({"key": "extension_mild", "label": f"+{v:.0f}% above 200dma = elevated", "pts": 5})
    except (TypeError, ValueError):
        pass

    ret_30d = pick.get("ret_30d")
    try:
        if ret_30d is not None:
            r = float(ret_30d)
            if r > 25:
                per_ticker_pts += 10
                signals.append({"key": "vertical_30d", "label": f"+{r:.0f}% in 30d = vertical move", "pts": 10})
            elif r > 15:
                per_ticker_pts += 6
                signals.append({"key": "strong_30d_uptrend", "label": f"+{r:.0f}% in 30d = strong uptrend", "pts": 6})
    except (TypeError, ValueError):
        pass

    ret_5d = pick.get("ret_5d")
    try:
        if ret_5d is not None and float(ret_5d) > 7:
            per_ticker_pts += 8
            signals.append({"key": "vertical_5d", "label": f"+{float(ret_5d):.1f}% in 5d = blow-off top risk", "pts": 8})
    except (TypeError, ValueError):
        pass

    ar = pick.get("_analyst_revisions") or {}
    if ar.get("verdict") == "NEGATIVE_REVISIONS":
        per_ticker_pts += 5
        signals.append({"key": "analyst_revisions_down", "label": ar.get("label") or "negative EPS revisions", "pts": 5})

    pb = pick.get("_pb_flow") or {}
    if pb.get("aligned") and (pb.get("side") or "").upper() == "SHORT":
        per_ticker_pts += 10
        signals.append({"key": "pb_short_flow", "label": pb.get("label") or "PB flow aligned short", "pts": 10})

    gex = pick.get("_dealer_gex") or pick.get("_if_gex") or {}
    if gex.get("regime") == "POSITIVE_PIN":
        try:
            if pct_above_200 is not None and float(pct_above_200) > 15:
                per_ticker_pts += 8
                signals.append({"key": "gex_pin_extended", "label": "GEX pinning + extended = downside vol risk", "pts": 8})
        except (TypeError, ValueError):
            pass

    # Live gap-up suggests intraday chase setup → PUT
    la = pick.get("_live_action") or {}
    if la.get("flag") == "DO_NOT_CHASE":
        per_ticker_pts += 12
        signals.append({"key": "intraday_chase_risk", "label": la.get("label") or "intraday chase risk - PUT entry", "pts": 12})

    # === UW per-ticker bear signals ===

    uw_flow = pick.get("_uw_flow") or {}
    # Put-dominant flow with high call extension = institutions hedging the top
    if uw_flow.get("dominant_side") == "PUT" and uw_flow.get("call_put_ratio", 100) <= 0.5:
        per_ticker_pts += 15
        signals.append({"key": "uw_put_dominant_flow",
                        "label": f"UW: {uw_flow['puts']} puts / {uw_flow['calls']} calls (${uw_flow['total_premium']/1e6:.1f}M premium) = institutional put buying",
                        "pts": 15})

    uw_gex = pick.get("_uw_gex") or {}
    flip = uw_gex.get("gamma_flip_strike")
    if flip is not None and uw_gex.get("above_gamma_flip") is False:
        per_ticker_pts += 10
        signals.append({"key": "uw_below_gamma_flip",
                        "label": uw_gex.get("label") or "below gamma flip = downside vol amplification regime",
                        "pts": 10})

    if uw_flow.get("zero_dte_share", 0) >= 0.30 and uw_flow.get("dominant_side") == "PUT":
        per_ticker_pts += 10
        signals.append({"key": "uw_0dte_put_dominance",
                        "label": f"UW: {int(uw_flow['zero_dte_share']*100)}% 0DTE puts = institutional intraday hedging",
                        "pts": 10})

    uw_iv = pick.get("_uw_iv") or {}
    if uw_iv.get("iv_rank") is not None and uw_iv["iv_rank"] > 75:
        per_ticker_pts += 5
        signals.append({"key": "uw_iv_extreme",
                        "label": f"UW: IV rank {uw_iv['iv_rank']:.0f} = vol elevated, premium overpriced",
                        "pts": 5})

    score += per_ticker_pts

    # === MACRO OVERLAY (only counts if a per-ticker bear signal fired) ===

    if per_ticker_pts == 0:
        # No per-ticker bear edge - macro tide doesn't justify a PUT setup.
        # Return early with whatever per-ticker signals fired (which is none here).
        return min(score, 100), signals

    cot = pick.get("_cot_positioning") or {}
    regime = cot.get("regime")
    if regime == "CROWDED_LONG":
        score += 25
        signals.append({"key": "cot_crowded_long", "label": cot.get("label") or "COT crowded long = peak positioning exhaustion", "pts": 25})
    elif regime == "MODERATELY_LONG":
        score += 12
        signals.append({"key": "cot_lean_long", "label": cot.get("label") or "COT lean long", "pts": 12})

    if macro_regime == "RISK_OFF_PRESSURE":
        score += 25
        signals.append({"key": "macro_risk_off", "label": "macro: RISK_OFF pressure", "pts": 25})

    opt_pos = pick.get("_options_positioning") or {}
    findings = opt_pos.get("findings") or []
    for f in findings:
        sig = f.get("signal") if isinstance(f, dict) else None
        if sig in ("CPC_EXTREME_CALLS", "CPCE_RETAIL_CALLS"):
            score += 15
            signals.append({"key": "pc_extreme_calls", "label": f.get("label") or "retail call mania = contrarian short edge", "pts": 15})
            break
        if sig in ("VIX_BACKWARDATION", "SHORT_TERM_FEAR"):
            score += 15
            signals.append({"key": "vix_backwardation", "label": "VIX backwardation = stress regime", "pts": 15})
            break
        if sig == "SKEW_ELEVATED":
            score += 10
            signals.append({"key": "skew_elevated", "label": "SKEW elevated = tail hedging building", "pts": 10})
            break

    sentiment = pick.get("_sentiment_stack") or {}
    sentiment_findings = sentiment.get("findings") or []
    for f in sentiment_findings:
        sig = f.get("signal") if isinstance(f, dict) else None
        if sig == "STACKED_GREED_EXTREME":
            score += 15
            signals.append({"key": "stacked_greed", "label": f.get("label") or "stacked sentiment extremes", "pts": 15})
            break
        if sig == "GREED_EXTREME":
            score += 15
            signals.append({"key": "sentiment_greed", "label": "F&G extreme greed", "pts": 15})
            break
        if sig == "PB_LEAK":
            score += 10
            signals.append({"key": "pb_leak", "label": "prime brokerage flow leak", "pts": 10})
            break

    margin = pick.get("_finra_margin_regime") or {}
    if margin.get("regime") == "EUPHORIC_LATE_CYCLE":
        score += 15
        signals.append({"key": "margin_euphoria", "label": margin.get("label") or "margin debt euphoric late cycle", "pts": 15})

    return min(score, 100), signals


def _technical_half_weight_score(pick, side="CALL"):
    """Backward-looking technicals at HALF weight. Max 25 points.

    Same signals on both sides: VCP, pocket pivot, quiet RS, MTF trend, auction position.
    Direction-aware: aligned_up boosts CALL, aligned_down boosts PUT.
    """
    score = 0
    signals = []
    side_up = (side == "CALL")

    vcp = pick.get("_vcp_setup") or {}
    verdict = vcp.get("verdict")
    if side_up:
        if verdict == "PRIME_BREAKOUT":
            pts = int(10 * TECHNICAL_WEIGHT)
            score += pts
            signals.append({"key": "vcp_prime", "label": "VCP prime breakout (half weight)", "pts": pts})
        elif verdict == "BREAKOUT_SETUP":
            pts = int(7 * TECHNICAL_WEIGHT)
            score += pts
            signals.append({"key": "vcp_setup", "label": "VCP breakout setup (half weight)", "pts": pts})

    mtf = pick.get("_mtf_trend") or {}
    if side_up and mtf.get("aligned_up"):
        pts = int(8 * TECHNICAL_WEIGHT)
        score += pts
        signals.append({"key": "mtf_up", "label": "trend aligned D+W+M (half weight)", "pts": pts})
    elif not side_up and mtf.get("aligned_down"):
        pts = int(8 * TECHNICAL_WEIGHT)
        score += pts
        signals.append({"key": "mtf_down", "label": "trend aligned down D+W+M (half weight)", "pts": pts})

    if side_up:
        factors = vcp.get("factors") or {}
        qrs = factors.get("quiet_rs") or {}
        if qrs.get("pass") is True:
            pts = int(8 * TECHNICAL_WEIGHT)
            score += pts
            signals.append({"key": "quiet_rs", "label": qrs.get("verdict") or "quiet RS (half weight)", "pts": pts})

    if side_up:
        pp = pick.get("_pocket_pivot") or {}
        if pp.get("fires"):
            pts = int(7 * TECHNICAL_WEIGHT)
            score += pts
            signals.append({"key": "pocket_pivot", "label": pp.get("label") or "pocket pivot (half weight)", "pts": pts})

    al = pick.get("_auction_levels") or {}
    position = al.get("position")
    if side_up and position == "ABOVE_VALUE":
        pts = int(7 * TECHNICAL_WEIGHT)
        score += pts
        signals.append({"key": "auction_above", "label": f"auction above value (POC ${al.get('poc')}) (half weight)", "pts": pts})
    elif not side_up and position == "BELOW_VALUE":
        pts = int(7 * TECHNICAL_WEIGHT)
        score += pts
        signals.append({"key": "auction_below", "label": f"auction below value (POC ${al.get('poc')}) (half weight)", "pts": pts})

    return min(score, 25), signals


def _conviction_tier(score, n_positioning_signals):
    if score >= 70 and n_positioning_signals >= 3:
        return "ELITE"
    if score >= 55 and n_positioning_signals >= 2:
        return "STRONG"
    if score >= 40:
        return "MODERATE"
    if score >= 25:
        return "WEAK"
    return "NONE"


def _thesis(side, positioning_signals, regime_context, ticker):
    if not positioning_signals:
        return f"{ticker}: no firing positioning signals - neutral."
    top = positioning_signals[:3]
    drivers = ", ".join(s.get("key", "?").replace("_", " ") for s in top)
    if side == "CALL":
        return f"{ticker} CALL thesis: {drivers} in {regime_context} regime. Bullish positioning + tailwind."
    if side == "PUT":
        return f"{ticker} PUT thesis: {drivers} in {regime_context} regime. Bearish positioning + headwind."
    return f"{ticker}: positioning signals firing but no clear directional edge."


def score_pick(pick, macro_regime="NEUTRAL"):
    """Compute positioning-first score + direction + thesis for a single pick.

    macro_regime is the global macro positioning regime (RISK_ON / NEUTRAL / RISK_OFF_PRESSURE).
    Returns dict that becomes pick['_positioning_first'].
    """
    ticker = pick.get("ticker") or "?"

    bull_pos_score, bull_pos_signals = _bull_positioning_score(pick, macro_regime)
    bear_pos_score, bear_pos_signals = _bear_positioning_score(pick, macro_regime)

    if bull_pos_score >= bear_pos_score and bull_pos_score >= 25:
        side = "CALL"
        side_score = bull_pos_score
        positioning_signals = bull_pos_signals
    elif bear_pos_score > bull_pos_score and bear_pos_score >= 25:
        side = "PUT"
        side_score = bear_pos_score
        positioning_signals = bear_pos_signals
    else:
        side = "NEUTRAL"
        side_score = max(bull_pos_score, bear_pos_score)
        positioning_signals = bull_pos_signals if bull_pos_score >= bear_pos_score else bear_pos_signals

    tech_score, tech_signals = _technical_half_weight_score(pick, side=side if side != "NEUTRAL" else "CALL")
    final_score = min(100, side_score + tech_score)
    n_pos = len(positioning_signals)
    tier = _conviction_tier(final_score, n_pos)

    if final_score >= 70 and n_pos >= 3:
        sizing_pct = 33
    elif final_score >= 55 and n_pos >= 2:
        sizing_pct = 25
    elif final_score >= 40:
        sizing_pct = 20
    else:
        sizing_pct = 0

    return {
        "score": final_score,
        "side": side,
        "bull_score": bull_pos_score,
        "bear_score": bear_pos_score,
        "technical_half_weight_score": tech_score,
        "positioning_signals": positioning_signals,
        "technical_signals_half_weight": tech_signals,
        "n_positioning_signals": n_pos,
        "conviction_tier": tier,
        "recommended_size_pct": sizing_pct,
        "regime_context": macro_regime,
        "thesis": _thesis(side, positioning_signals, macro_regime, ticker),
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }


def apply_positioning_first(picks, macro=None, verbose=False):
    """Apply positioning-first scoring to the entire wide pool.

    Call this BEFORE bracket_routing, AA gates, landmines.
    Picks become ranked by positioning extremes + half-weight technicals, with
    directional bias (CALL/PUT) attached as `_positioning_first.side`.
    """
    if not picks:
        return picks

    macro_regime = _resolve_macro_regime(macro)

    tiers = {"ELITE": 0, "STRONG": 0, "MODERATE": 0, "WEAK": 0, "NONE": 0}
    sides = {"CALL": 0, "PUT": 0, "NEUTRAL": 0}

    for p in picks:
        try:
            res = score_pick(p, macro_regime=macro_regime)
            p["_positioning_first"] = res
            tiers[res["conviction_tier"]] = tiers.get(res["conviction_tier"], 0) + 1
            sides[res["side"]] = sides.get(res["side"], 0) + 1
        except Exception as e:
            if verbose:
                print(f"  positioning_first failed for {p.get('ticker')}: {type(e).__name__}: {e}")
            continue

    if verbose:
        print(f"  positioning_first: macro={macro_regime}  ELITE={tiers['ELITE']} STRONG={tiers['STRONG']} "
              f"MODERATE={tiers['MODERATE']} WEAK={tiers['WEAK']} NONE={tiers['NONE']}  "
              f"sides CALL={sides['CALL']} PUT={sides['PUT']} NEUTRAL={sides['NEUTRAL']}")

    return picks


def _resolve_macro_regime(macro):
    if not isinstance(macro, dict):
        return "NEUTRAL"
    # Path 3 Fix 1: prefer the meta_regime that aggregates the full new stack
    # (FINRA + sentiment + COT + options positioning + macro positioning + VIX).
    meta = macro.get("meta_regime") or {}
    meta_regime = meta.get("regime")
    if meta_regime in ("RISK_ON", "RISK_OFF_PRESSURE", "NEUTRAL"):
        return meta_regime
    # Fallback to legacy macro_positioning-only verdict.
    mp = macro.get("macro_positioning") or {}
    regime = mp.get("regime")
    if regime in ("RISK_ON", "RISK_OFF_PRESSURE", "NEUTRAL"):
        return regime
    mr = macro.get("macro_regime") or {}
    raw = (mr.get("regime") or "").upper()
    if "RISK_ON" in raw or raw in ("BULLISH", "GROWTH"):
        return "RISK_ON"
    if "RISK_OFF" in raw or raw in ("BEARISH", "FEAR"):
        return "RISK_OFF_PRESSURE"
    return "NEUTRAL"


def rank_by_positioning(picks, side_filter=None, min_tier="MODERATE"):
    """Return picks sorted by positioning-first score, optionally filtered by side.

    side_filter: "CALL" / "PUT" / None (both)
    min_tier: minimum conviction tier
    """
    tier_order = {"ELITE": 4, "STRONG": 3, "MODERATE": 2, "WEAK": 1, "NONE": 0}
    min_tier_rank = tier_order.get(min_tier, 2)

    out = []
    for p in picks:
        pf = p.get("_positioning_first") or {}
        if not pf:
            continue
        if tier_order.get(pf.get("conviction_tier", "NONE"), 0) < min_tier_rank:
            continue
        if side_filter and pf.get("side") != side_filter:
            continue
        out.append(p)

    out.sort(key=lambda p: (p.get("_positioning_first") or {}).get("score", 0), reverse=True)
    return out


def split_into_bidirectional(picks, max_calls=10, max_puts=5, min_tier="MODERATE"):
    """Split ranked picks into CALL and PUT buckets for bidirectional output.

    Returns: {"calls": [...], "puts": [...], "neutral_rejected": [...]}
    """
    calls = rank_by_positioning(picks, side_filter="CALL", min_tier=min_tier)[:max_calls]
    puts = rank_by_positioning(picks, side_filter="PUT", min_tier=min_tier)[:max_puts]
    return {
        "calls": calls,
        "puts": puts,
        "n_calls": len(calls),
        "n_puts": len(puts),
    }

import os
import json
import time


try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


FORENSIC_MODEL = os.environ.get("FORENSIC_MODEL", "claude-sonnet-4-6")
FORENSIC_SLEEP = int(os.environ.get("FORENSIC_SLEEP", "65"))
HAIKU_MODEL = os.environ.get("HAIKU_FORENSIC_MODEL", "claude-haiku-4-5")


FORENSIC_SYSTEM = """You are a quantitative analyst producing the COMPLETE forensic report for a trade about to be executed. ONE call, COMPLETE output. The trader is sizing $400-2,000 in lottery options targeting 200-500% in 14-45 days.

You will receive: ticker, fundamentals snapshot, catalyst stack, smart money signals, technical setup, options market data.

Use web_search aggressively to:
1. VERIFY the catalyst is real (primary source: company IR, SEC filing, news)
2. Find 5-7 HISTORICAL ANALOGS from last 24 months — same sector, same mcap bracket, same catalyst type, same signal stack
3. Compute statistics on analog outcomes (win rate, median move, drawdown)
4. Identify the BEAR thesis — what kills this trade
5. Read tone of recent earnings calls if available
6. Cross-check options market positioning (call sweeps, skew, IV vs realized)

Output STRICTLY this JSON (no preamble, no markdown):
{
  "verdict": "STRONG_BUY|BUY|HOLD|SKIP",
  "confidence_pct": 0-100,
  "catalyst_verified": true|false,
  "catalyst_status": {
    "status": "HAPPENED|SCHEDULED|RUMORED|EXPECTED",
    "event_date": "YYYY-MM-DD or null",
    "days_until": -2 or 7 or null,
    "countdown_label": "in 3d AMC" or "happened yesterday",
    "verified_via": "8-K / IR page / Reuters / etc."
  },
  "bull_thesis": "3 sentences with cited evidence",
  "bear_thesis": "3 sentences ruthless counter-case",
  "what_kills_this_trade": "single most likely failure mode",
  "warning_signs": ["sign 1", "sign 2", "sign 3"],
  "analogs": {
    "n_found": 5,
    "list": [
      {"ticker": "ABCD", "date": "2025-08-15", "catalyst": "1-line", "next_day_pct": 14, "one_week_pct": 22, "note": "1-line"}
    ],
    "stats": {
      "win_rate_next_day_pct": 67,
      "median_next_day_pct": 12.5,
      "p25_next_day_pct": 4,
      "p75_next_day_pct": 22,
      "worst_outcome_pct": -8
    }
  },
  "expected_move": {
    "if_positive_pct": 14,
    "if_negative_pct": -8,
    "expected_value_pct": 8
  },
  "options_market_read": {
    "implied_move_pct": 12,
    "analog_median_pct": 14,
    "edge_label": "MARKET_UNDERPRICING|FAIRLY_PRICED|MARKET_OVERPRICING",
    "iv_assessment": "COMPRESSED|FAIR|ELEVATED|PEAK",
    "smart_money_positioning": "1 sentence on call/put flow"
  },
  "lottery_thesis": {
    "best_strike_otm_pct": 5,
    "best_dte_days": 21,
    "expected_premium_target_move_pct": 12,
    "thesis_paragraph": "Buy 21-DTE 5% OTM. Catalyst on DATE. Win prob X% based on Y analogs. Target +Z% premium ROI. Stop -50%. Risk: NEGATIVE_OUTCOME."
  },
  "pre_mortem_paragraph": "If this fails, the reason will be X. Specific warning signs to watch in first 48 hours.",
  "research_note": "180-300 word synthesis with specific facts, analog reads, and verdict reasoning",
  "red_flags_found": ["specific flag 1", "specific flag 2"]
}

Be ruthless on the bear case. Bull theses are easy. Bear theses save accounts. If you cannot find 5+ analogs, set verdict to HOLD or SKIP and explain why in research_note."""


def _build_user_prompt(candidate):
    cats = candidate.get("catalysts") or []
    cat_lines = [f"- [{c.get('tier','?')}] {c.get('label','')}: {c.get('details','')[:120]}" for c in cats[:5]]
    sm = candidate.get("_smart_money_signals") or []
    landmines = candidate.get("_landmine_flags") or []
    landmine_lines = [f"- {f['severity']}: {f['label']}" for f in landmines]
    iv_data = candidate.get("iv_percentile_analysis") or {}
    options_check = candidate.get("options_check") or {}
    peer = candidate.get("peer_benchmark") or {}
    insider = candidate.get("insider_depth") or {}

    return f"""Ticker: {candidate['ticker']} ({candidate.get('name','')})
Bracket: {candidate.get('bracket','?')} (${(candidate.get('market_cap') or 0)/1e9:.2f}B mcap)
Sector: {candidate.get('sector','')} / Industry: {candidate.get('industry','')}
Price: ${candidate.get('price', 0):.2f}
Stacked categories: {candidate.get('_category_count', 0)} ({', '.join(candidate.get('_active_categories') or [])})
Proposed AA tier: {candidate.get('_aa_tier', 'unknown')}

CATALYSTS:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

SMART MONEY: {', '.join(sm) or 'none detected'}
INSIDER DEPTH: {insider.get('buyer_count', 0)} buyers, ${insider.get('total_value_usd', 0)/1000:.0f}k, CEO/CFO bought: {insider.get('ceo_or_cfo_bought', False)}

OPTIONS MARKET:
Implied 1d move: {options_check.get('implied_move_1d_pct', '?')}%
IV percentile: {iv_data.get('iv_percentile', '?')}
IV regime: {(iv_data.get('interpretation') or {}).get('regime', '?')}
Realized vol 30d: {iv_data.get('realized_vol_30d', '?')}%

TECHNICAL:
Return 5d: {candidate.get('ret_5d', '?')}% / 30d: {candidate.get('ret_30d', '?')}% / 90d: {candidate.get('ret_90d', '?')}%
Above 50dMA: {candidate.get('above_50dma', '?')} / Above 200dMA: {candidate.get('above_200dma', '?')}
Distance above 50dMA: {candidate.get('pct_above_50dma', '?')}%

PEER BENCHMARKS:
Growth percentile: {peer.get('growth_percentile_avg', '?')} / Quality percentile: {peer.get('quality_percentile_avg', '?')}

LANDMINES:
{chr(10).join(landmine_lines) if landmine_lines else '(none detected)'}

Produce the complete forensic report. Find 5-7 analogs via web_search. Verify catalyst from primary source. Write ruthless bear case. Output STRICT JSON only."""


def research_unified(candidate, verbose=False):
    if not ANTHROPIC_AVAILABLE or not os.environ.get("ANTHROPIC_API_KEY"):
        if verbose:
            print(f"    forensic skip: anthropic missing or ANTHROPIC_API_KEY not set")
        return None
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=FORENSIC_MODEL,
            max_tokens=4000,
            system=FORENSIC_SYSTEM,
            messages=[{"role": "user", "content": _build_user_prompt(candidate)}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        data = _extract_json(text)
        if not data:
            if verbose:
                print(f"    forensic for {candidate.get('ticker')}: JSON extraction failed from {len(text)} chars of text")
                preview = text[:300].encode("ascii", "replace").decode("ascii")
                print(f"      preview: {preview}")
            return None
        data["_input_tokens"] = response.usage.input_tokens
        data["_output_tokens"] = response.usage.output_tokens
        data["_cost_usd"] = (response.usage.input_tokens * 3.0 + response.usage.output_tokens * 15.0) / 1_000_000
        if verbose:
            print(f"    forensic OK {candidate.get('ticker')}: verdict={data.get('verdict')} conf={data.get('confidence_pct')}% cost=${data['_cost_usd']:.3f}")
        return data
    except Exception as e:
        if verbose:
            err_msg = str(e).encode("ascii", "replace").decode("ascii")
            print(f"    forensic FAILED for {candidate.get('ticker')}: {type(e).__name__}: {err_msg[:200]}")
        return None


def apply_unified_forensic(picks, max_calls=6, verbose=False):
    if not picks:
        return picks
    enriched = 0
    total_cost = 0.0
    for i, pick in enumerate(picks[:max_calls]):
        if i > 0 and FORENSIC_SLEEP > 0:
            time.sleep(FORENSIC_SLEEP)
        ticker = pick.get("ticker")
        if verbose:
            print(f"    [forensic {i+1}/{min(max_calls, len(picks))}] {ticker}...")
        result = research_unified(pick, verbose=verbose)
        if result:
            pick["unified_forensic"] = result
            pick["deep_research"] = {
                "verdict": result.get("verdict", "HOLD"),
                "confidence_pct": result.get("confidence_pct", 50),
                "research_note": result.get("research_note", ""),
                "reason_to_buy": result.get("bull_thesis", ""),
                "reason_to_avoid": result.get("bear_thesis", ""),
                "catalyst_status": result.get("catalyst_status") or {},
                "expected_move": result.get("expected_move") or {},
                "lottery_thesis": result.get("lottery_thesis") or {},
            }
            analogs_block = result.get("analogs") or {}
            pick["analog_set"] = {
                "analogs": analogs_block.get("list") or [],
                "statistics": {
                    "n_analogs": analogs_block.get("n_found", 0),
                    **(analogs_block.get("stats") or {}),
                },
                "summary": "",
            }
            pick["counter_thesis"] = {
                "bear_thesis": result.get("bear_thesis", ""),
                "what_kills_this_trade": result.get("what_kills_this_trade", ""),
                "warning_signs_to_watch": result.get("warning_signs") or [],
                "verdict_on_bull_thesis": "STRONG" if result.get("verdict") in ("STRONG_BUY", "BUY") else "WEAK",
            }
            enriched += 1
            total_cost += result.get("_cost_usd", 0)
    if verbose:
        print(f"  unified_forensic: {enriched} picks researched, total cost ~${total_cost:.2f}")
    return picks


HAIKU_SYSTEM = """You are a quantitative analyst writing a SHORT forensic synthesis for a trade candidate. You don't have web search — synthesize from the data provided. The trader is sizing a lottery option targeting 200-500% in 14-45 days.

Output STRICTLY this JSON (no preamble, no markdown):
{
  "verdict": "STRONG_BUY|BUY|HOLD|SKIP",
  "confidence_pct": 0-100,
  "bull_thesis": "2-3 sentences",
  "bear_thesis": "2-3 sentences ruthless counter-case",
  "what_kills_this_trade": "1 sentence — single most likely failure mode",
  "warning_signs": ["sign 1", "sign 2"],
  "synthesis_note": "100-150 word summary",
  "red_flags_found": ["specific flag 1", "specific flag 2"]
}

Be ruthless on the bear case. No analog research (you don't have web access)."""


BEAR_CASE_SYSTEM = """You are a SHORT-SELLER hunting for reasons this trade FAILS. You don't have web search. Read the data and produce the most ruthless bear case possible. Assume bulls have already convinced themselves — your job is to find what they're missing.

Common failure modes for retail options plays:
- Catalyst already priced in (run-up before event, sell the news)
- Crowded trade (everyone bullish = no marginal buyer left)
- IV crush eats premium even on directional win
- Liquidity gap (wide spreads kill realized return vs paper return)
- Sector ETF in downtrend (good prints fade)
- Insider selling cluster despite Form 4 buys
- Going concern / dilution risk
- Failed analog cases in same setup type
- Macro headwinds (yield curve, dollar, oil) crushing risk-on

Output STRICTLY this JSON (no preamble, no markdown):
{
  "bear_verdict": "STRONG_BEAR|BEAR|NEUTRAL|WEAK_BEAR",
  "bear_conviction_pct": 0-100,
  "killer_thesis": "single sentence: the most likely reason this fails",
  "specific_failure_modes": ["mode 1", "mode 2", "mode 3"],
  "what_to_watch_to_invalidate": "what would convince you the bear case is wrong",
  "expected_loss_pct_if_wrong": -50 to -90,
  "is_this_trade_a_trap": true|false,
  "trap_reasoning": "1-2 sentences if trap=true, empty otherwise"
}

Be cynical. Bull theses are easy. The job here is to find the kill shot."""


def _build_bear_prompt(candidate, bull_data=None):
    cats = candidate.get("catalysts") or []
    cat_lines = [f"- [{c.get('tier','?')}] {c.get('label','')}" for c in cats[:5] if isinstance(c, dict)]
    sm = candidate.get("_smart_money_signals") or []
    landmines = candidate.get("_landmine_flags") or []
    landmine_lines = [f"- {f['severity']}: {f['label']}" for f in landmines if isinstance(f, dict)]
    iv_data = candidate.get("iv_percentile_analysis") or {}
    insider = candidate.get("insider_depth") or {}

    bull_summary = ""
    if bull_data:
        bull_summary = f"\n\nBULL THESIS (your job: tear this apart):\n{bull_data.get('bull_thesis') or bull_data.get('research_note', '')[:600]}"

    return f"""Ticker: {candidate['ticker']} ({candidate.get('name','')})
Bracket: {candidate.get('bracket','?')} (${(candidate.get('market_cap') or 0)/1e9:.2f}B)
Sector: {candidate.get('sector','')}
Price: ${candidate.get('price', 0):.2f}
Stacked categories: {candidate.get('_category_count', 0)}
AA tier proposed: {candidate.get('_aa_tier', 'unknown')}

CATALYSTS:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

SMART MONEY: {', '.join(sm) or 'none'}
INSIDER: {insider.get('buyer_count', 0)} buyers, ${insider.get('total_value_usd', 0)/1000:.0f}k, CEO/CFO: {insider.get('ceo_or_cfo_bought', False)}

OPTIONS / TECHNICALS:
IV percentile: {iv_data.get('iv_percentile', '?')}
Return 5d: {candidate.get('ret_5d', '?')}% / 30d: {candidate.get('ret_30d', '?')}% / 90d: {candidate.get('ret_90d', '?')}%
Above 50dMA: {candidate.get('above_50dma', '?')} / Above 200dMA: {candidate.get('above_200dma', '?')}

LANDMINES:
{chr(10).join(landmine_lines) if landmine_lines else '(none detected)'}{bull_summary}

Write the BEAR case. Find the failure mode. Is this trade a trap? JSON only."""


def verify_with_bear_case(candidate, verbose=False):
    if not ANTHROPIC_AVAILABLE or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    bull_data = candidate.get("unified_forensic") or candidate.get("haiku_synthesis") or {}
    if not bull_data:
        return None
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1200,
            system=BEAR_CASE_SYSTEM,
            messages=[{"role": "user", "content": _build_bear_prompt(candidate, bull_data)}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        data = _extract_json(text)
        if data:
            data["_input_tokens"] = response.usage.input_tokens
            data["_output_tokens"] = response.usage.output_tokens
            data["_cost_usd"] = (response.usage.input_tokens * 1.0 + response.usage.output_tokens * 5.0) / 1_000_000
            if verbose:
                print(f"    bear-case {candidate.get('ticker')}: verdict={data.get('bear_verdict')} bear_conv={data.get('bear_conviction_pct')}% trap={data.get('is_this_trade_a_trap')}")
        return data
    except Exception as e:
        if verbose:
            err_msg = str(e).encode("ascii", "replace").decode("ascii")
            print(f"    bear-case FAILED for {candidate.get('ticker')}: {type(e).__name__}: {err_msg[:200]}")
        return None


def apply_bear_case_verification(picks, max_calls=4, verbose=False):
    if not picks:
        return picks
    flipped = 0
    confirmed = 0
    total_cost = 0.0
    for i, pick in enumerate(picks[:max_calls]):
        bull = pick.get("unified_forensic") or pick.get("haiku_synthesis") or {}
        if not bull:
            continue
        bull_verdict = bull.get("verdict")
        if bull_verdict not in ("BUY", "STRONG_BUY"):
            continue
        bear = verify_with_bear_case(pick, verbose=verbose)
        if not bear:
            continue
        pick["bear_verification"] = bear
        bear_conv = bear.get("bear_conviction_pct", 0) or 0
        is_trap = bear.get("is_this_trade_a_trap", False)
        if bear_conv >= 65 or is_trap:
            original_verdict = bull.get("verdict")
            adjusted = "HOLD" if bear_conv < 80 else "SKIP"
            bull["verdict_pre_bear_check"] = original_verdict
            bull["verdict"] = adjusted
            bull["verdict_adjustment_reason"] = f"bear-case conviction {bear_conv}% (trap={is_trap}) overrides bull verdict"
            deep = pick.get("deep_research") or {}
            if deep:
                deep["verdict"] = adjusted
            flipped += 1
            if verbose:
                print(f"    {pick.get('ticker')}: {original_verdict} -> {adjusted} (bear conviction {bear_conv}%)")
        else:
            confirmed += 1
        total_cost += bear.get("_cost_usd", 0)
    if verbose:
        print(f"  bear-case verification: {confirmed} confirmed BUY, {flipped} downgraded, total cost ~${total_cost:.3f}")
    return picks


def _build_haiku_prompt(candidate):
    cats = candidate.get("catalysts") or []
    cat_lines = [f"- [{c.get('tier','?')}] {c.get('label','')}: {c.get('details','')[:120]}" for c in cats[:5]]
    sm = candidate.get("_smart_money_signals") or []
    landmines = candidate.get("_landmine_flags") or []
    landmine_lines = [f"- {f['severity']}: {f['label']}" for f in landmines]
    iv_data = candidate.get("iv_percentile_analysis") or {}
    options_check = candidate.get("options_check") or {}
    peer = candidate.get("peer_benchmark") or {}
    insider = candidate.get("insider_depth") or {}

    return f"""Ticker: {candidate['ticker']} ({candidate.get('name','')})
Bracket: {candidate.get('bracket','?')} (${(candidate.get('market_cap') or 0)/1e9:.2f}B)
Sector: {candidate.get('sector','')} / Industry: {candidate.get('industry','')}
Price: ${candidate.get('price', 0):.2f}
Stacked categories: {candidate.get('_category_count', 0)}
AA tier: {candidate.get('_aa_tier', 'unknown')}

CATALYSTS:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

SMART MONEY: {', '.join(sm) or 'none'}
INSIDER: {insider.get('buyer_count', 0)} buyers, ${insider.get('total_value_usd', 0)/1000:.0f}k, CEO/CFO: {insider.get('ceo_or_cfo_bought', False)}

OPTIONS: implied {options_check.get('implied_move_1d_pct', '?')}% · IV pctile {iv_data.get('iv_percentile', '?')} · regime {(iv_data.get('interpretation') or {}).get('regime', '?')}

TECHNICAL: 5d {candidate.get('ret_5d', '?')}% · 30d {candidate.get('ret_30d', '?')}% · above50dMA {candidate.get('above_50dma', '?')} · above200dMA {candidate.get('above_200dma', '?')}

PEER PERCENTILE: growth {peer.get('growth_percentile_avg', '?')} · quality {peer.get('quality_percentile_avg', '?')}

LANDMINES:
{chr(10).join(landmine_lines) if landmine_lines else '(none)'}

Write the SHORT forensic synthesis. Bull + bear + what kills it. JSON only."""


def synthesize_haiku(candidate, verbose=False):
    if not ANTHROPIC_AVAILABLE or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1500,
            system=HAIKU_SYSTEM,
            messages=[{"role": "user", "content": _build_haiku_prompt(candidate)}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        data = _extract_json(text)
        if data:
            data["_input_tokens"] = response.usage.input_tokens
            data["_output_tokens"] = response.usage.output_tokens
            data["_cost_usd"] = (response.usage.input_tokens * 1.0 + response.usage.output_tokens * 5.0) / 1_000_000
            data["_model"] = "haiku"
            if verbose:
                print(f"    haiku OK {candidate.get('ticker')}: verdict={data.get('verdict')} conf={data.get('confidence_pct')}%")
        return data
    except Exception as e:
        if verbose:
            err_msg = str(e).encode("ascii", "replace").decode("ascii")
            print(f"    haiku FAILED for {candidate.get('ticker')}: {type(e).__name__}: {err_msg[:200]}")
        return None


def apply_haiku_synthesis(picks, max_calls=3, verbose=False):
    if not picks:
        return picks
    enriched = 0
    total_cost = 0.0
    for i, pick in enumerate(picks[:max_calls]):
        ticker = pick.get("ticker")
        if verbose:
            print(f"    [haiku {i+1}/{min(max_calls, len(picks))}] {ticker}...")
        result = synthesize_haiku(pick, verbose=verbose)
        if result:
            pick["haiku_synthesis"] = result
            pick["deep_research"] = pick.get("deep_research") or {
                "verdict": result.get("verdict", "HOLD"),
                "confidence_pct": result.get("confidence_pct", 50),
                "research_note": result.get("synthesis_note", ""),
                "reason_to_buy": result.get("bull_thesis", ""),
                "reason_to_avoid": result.get("bear_thesis", ""),
            }
            pick["counter_thesis"] = pick.get("counter_thesis") or {
                "bear_thesis": result.get("bear_thesis", ""),
                "what_kills_this_trade": result.get("what_kills_this_trade", ""),
                "warning_signs_to_watch": result.get("warning_signs") or [],
                "verdict_on_bull_thesis": "STRONG" if result.get("verdict") in ("STRONG_BUY", "BUY") else "WEAK",
            }
            enriched += 1
            total_cost += result.get("_cost_usd", 0)
    if verbose:
        print(f"  haiku_synthesis: {enriched} picks synthesized, total cost ~${total_cost:.3f}")
    return picks


def _extract_json(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None

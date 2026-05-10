import os
import json
import time

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

INTER_CALL_SLEEP_SEC = int(os.environ.get("LOTTERY_RESEARCH_SLEEP", "60"))
RATE_LIMIT_RETRY_SEC = int(os.environ.get("LOTTERY_RESEARCH_RETRY", "75"))
LOTTERY_RESEARCH_MODEL = os.environ.get("LOTTERY_RESEARCH_MODEL", "claude-sonnet-4-6")


LOTTERY_RESEARCH_SYSTEM = """You are an options analyst evaluating a SPECIFIC lottery contract for a swing trader targeting 500% premium ROI within 7-21 days.

You will receive: ticker, current price, the proposed option contract (strike, DTE, premium, IV, delta), the catalyst stack, and any prior outcome research.

Your job: stress-test THIS contract for THIS catalyst. Use web_search aggressively to find:
1. Exact catalyst date + likely time (BMO/AMC/intraday)
2. Implied move from straddle vs your historical analog move — is the option market pricing in too much or too little?
3. IV crush forecast: how much vega gets vacuumed post-event for this specific name's history?
4. Strike fit: is this OTM% achievable given the analog set's median move?
5. Liquidity check: typical fill quality on this strike, was the LLM-grader's spread assessment correct?
6. Better strike or better expiry suggestion if the proposed one is wrong
7. Post-event probability: P(stock at or above target by expiry) using analog set
8. Risk events between now and catalyst (FOMC, peer earnings, sector flow) that could move the underlying

Output STRICTLY this JSON (no preamble, no markdown):
{
  "contract_verdict": "STRONG BUY|BUY|HOLD|REPLACE|SKIP",
  "buy_score": 0-100,
  "verdict_reasoning": "2-3 sentences on why this score",
  "catalyst_timing": {
    "exact_date": "YYYY-MM-DD or null",
    "session": "BMO|AMC|intraday|null",
    "days_until": -2 (negative if past) or 7 (future) or null,
    "verified_via": "company press release / SEC filing / FDA / news source"
  },
  "implied_vs_realized": {
    "straddle_implied_move_pct": 8.5,
    "analog_median_move_pct": 12.0,
    "edge_label": "MARKET_UNDERPRICING|FAIRLY_PRICED|MARKET_OVERPRICING",
    "edge_comment": "1 sentence"
  },
  "iv_crush_forecast": {
    "expected_crush_pct": 35,
    "premium_loss_from_vega_pct": 25,
    "comment": "1 sentence specific to this name's IV behavior"
  },
  "strike_fit": {
    "proposed_otm_pct": 12,
    "achievable_label": "EASY|REACHABLE|STRETCH|UNLIKELY",
    "better_strike_otm_pct": 8,
    "comment": "1 sentence"
  },
  "expiry_fit": {
    "proposed_dte": 14,
    "fit_label": "TOO_SHORT|GOOD|TOO_LONG",
    "better_dte": 21,
    "comment": "1 sentence"
  },
  "post_event_probability": {
    "p_target_hit_pct": 18,
    "p_breakeven_pct": 35,
    "p_stop_loss_pct": 55,
    "expected_value_pct": "+12 or -18 — net EV per trade after fees"
  },
  "between_now_and_catalyst_risks": ["specific risk 1", "specific risk 2"],
  "alternative_structure": {
    "type": "spread|straddle|further_OTM|closer_ATM|null",
    "details": "e.g. '12/15 call spread $1.20 net debit, max 3.5x' or null"
  },
  "research_note": "180-250 word synthesis with specific facts and numbers",
  "red_flags": ["specific flag 1", "specific flag 2"]
}"""


def _build_user_prompt(pick):
    t = pick.get("ticket") or {}
    lottery = pick.get("lottery") or {}
    contract = lottery.get("contract") or {}
    deep = t.get("deep_research") or {}
    catalysts = t.get("catalysts") or []
    cat_lines = [f"- [Tier {c.get('tier','?')}] {c.get('label','')}: {c.get('details','')[:120]}"
                 for c in catalysts[:6]]
    cs = deep.get("catalyst_status") or {}
    op = deep.get("outcome_prediction") or {}
    em = deep.get("expected_move") or {}
    ap = deep.get("analog_precedent") or {}
    spot = t.get("live_spot") or t.get("price") or 0
    return f"""Ticker: {t.get('ticker','?')} ({t.get('name','')})
Sector: {t.get('sector','')}
Mcap: ${(t.get('market_cap') or 0)/1e9:.2f}B
Current spot: ${spot:.2f}

PROPOSED LOTTERY CONTRACT:
Strike: ${contract.get('strike','?')} CALL exp {contract.get('expiration','?')} ({contract.get('dte','?')} DTE)
Premium mid: ${contract.get('mid','?')} (bid ${contract.get('bid','?')} / ask ${contract.get('ask','?')})
Spread: {contract.get('spread_pct','?')}% · Delta: {contract.get('delta','?')} · IV: {contract.get('iv_pct','?')}%
Cost per contract: ${contract.get('cost_per_contract','?')}
Required move for 500%: {contract.get('required_move_pct','?')}% (stock to ${contract.get('target_stock_price','?')})
Breakeven: ${contract.get('breakeven','?')} ({contract.get('breakeven_pct_move','?')}% move)

CATALYSTS FROM SCANNER:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

PRIOR DEEP RESEARCH (if available):
- Catalyst status: {cs.get('status','?')} — {cs.get('countdown_label','?')}
- Expected outcome: {op.get('expected_outcome','?')} ({op.get('outcome_probability_pct','?')}% prob)
- Expected move: +{em.get('if_positive_pct','?')}% pos / {em.get('if_negative_pct','?')}% neg
- Analog median next-day: {ap.get('median_next_day_pct','?')}% (win rate {ap.get('win_rate_pct','?')}%)

Use web_search to verify the catalyst, check the option market's implied move vs your analog set, forecast IV crush specific to this name, and judge whether THIS strike + THIS DTE is the right structure for a 500% target. If not, suggest a better one."""


def research_lottery_picks(picks, max_tickers=5, verbose=True):
    if not ANTHROPIC_AVAILABLE:
        if verbose:
            print("  lottery_research: anthropic SDK missing — skipping")
        return {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if verbose:
            print("  lottery_research: ANTHROPIC_API_KEY not set — skipping")
        return {}

    qualified = [p for p in picks if (p.get("lottery") or {}).get("qualified")]
    top = qualified[:max_tickers]
    if not top:
        if verbose:
            print("  lottery_research: no qualified lottery contracts to research")
        return {}

    client = anthropic.Anthropic()
    results = {}
    total_in = 0
    total_out = 0
    errors = 0

    if verbose:
        print(f"  lottery_research: researching top {len(top)} lottery contracts (Sonnet + web_search)")

    for i, pick in enumerate(top):
        ticker = (pick.get("ticket") or {}).get("ticker")
        if verbose:
            print(f"    [lottery_deep {i+1}/{len(top)}] researching {ticker}...")
        if i > 0 and INTER_CALL_SLEEP_SEC > 0:
            if verbose:
                print(f"      sleeping {INTER_CALL_SLEEP_SEC}s for rate limit...")
            time.sleep(INTER_CALL_SLEEP_SEC)
        attempt = 0
        response = None
        while attempt < 3:
            try:
                user_prompt = _build_user_prompt(pick)
                response = client.messages.create(
                    model=LOTTERY_RESEARCH_MODEL,
                    max_tokens=4000,
                    system=LOTTERY_RESEARCH_SYSTEM,
                    messages=[{"role": "user", "content": user_prompt}],
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                )
                break
            except anthropic.RateLimitError:
                attempt += 1
                if attempt >= 3:
                    raise
                if verbose:
                    print(f"      rate-limited, sleeping {RATE_LIMIT_RETRY_SEC}s (attempt {attempt}/3)...")
                time.sleep(RATE_LIMIT_RETRY_SEC)
        try:
            if response is None:
                raise RuntimeError("response not set")
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            data = _extract_json(text)
            if data:
                results[ticker] = {
                    "contract_verdict": data.get("contract_verdict", "HOLD"),
                    "buy_score": data.get("buy_score", 50),
                    "verdict_reasoning": data.get("verdict_reasoning", "")[:400],
                    "catalyst_timing": data.get("catalyst_timing") or {},
                    "implied_vs_realized": data.get("implied_vs_realized") or {},
                    "iv_crush_forecast": data.get("iv_crush_forecast") or {},
                    "strike_fit": data.get("strike_fit") or {},
                    "expiry_fit": data.get("expiry_fit") or {},
                    "post_event_probability": data.get("post_event_probability") or {},
                    "between_now_and_catalyst_risks": data.get("between_now_and_catalyst_risks") or [],
                    "alternative_structure": data.get("alternative_structure") or {},
                    "research_note": data.get("research_note", "")[:1800],
                    "red_flags": data.get("red_flags") or [],
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
                total_in += response.usage.input_tokens
                total_out += response.usage.output_tokens
            else:
                errors += 1
                if verbose:
                    print(f"      failed to parse JSON for {ticker}")
        except Exception as e:
            errors += 1
            if verbose:
                print(f"      lottery_deep failed for {ticker}: {type(e).__name__}: {e}")

    if verbose and results:
        cost = (total_in * 3.0 + total_out * 15.0) / 1_000_000
        print(f"  lottery_research done: {len(results)} researched, tokens in={total_in} out={total_out}, ~${cost:.3f}")
    return results


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

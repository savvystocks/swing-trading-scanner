import os
import json
import time

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

DEEP_INTER_CALL_SLEEP_SEC = int(os.environ.get("CATALYST_DEEP_SLEEP", "60"))
DEEP_RATE_LIMIT_RETRY_SEC = int(os.environ.get("CATALYST_DEEP_RETRY", "75"))

DEEP_MODEL = os.environ.get("CATALYST_DEEP_MODEL", "claude-sonnet-4-6")

DEEP_SYSTEM = """You are a swing-trading analyst predicting the OUTCOME of an upcoming or just-occurred catalyst event. The trader is sizing 1-2 week call options for a 500% lottery target with -50% premium stop. Your job is to produce a structured catalyst card that tells them: did it already happen, when does it happen, what's the historical analog set, and what's the asymmetric trade.

PRIMARY MISSION: produce structured, scannable JSON with TIME-AWARE catalyst data and HISTORICAL ANALOGS.

Use web_search aggressively to find:

For TIMING:
- Exact event date (earnings BMO/AMC, PDUFA date, deal vote, ex-date)
- Has it already happened? Or is it scheduled? Or rumored?
- Time-to-event in days

For OUTCOME PREDICTION:
- Consensus EPS / revenue / endpoint hit-rate / approval probability
- Whisper number, beat streak, peer reads
- Insider activity, options skew, short interest delta
- AdComm votes, Phase 2/3 historical approval rates by drug class
- M&A deal spread, antitrust risk, financing committed

For ANALOG PRECEDENTS (CRITICAL):
- Find 2-3 SIMILAR setups in the last 12-24 months: same catalyst type, same sector, similar market cap, similar signal stack
- Cite ticker + date + what happened (next-day, 1-week move %)
- Compute median outcome and win rate from the analog set
- Use these to calibrate your expected_move

For STACKING ANALYSIS:
- The scanner has identified multiple catalysts firing simultaneously (e.g., earnings beat + insider cluster + revision spike)
- When 3+ catalysts stack like this, what's the historical amplification factor?
- Cite a recent analog where similar stacking occurred

For LOTTERY THESIS:
- Recommend optimal strike (% OTM) and DTE for a 500% target trade
- What stock move is needed? Is it achievable based on your expected_move?
- What's the strongest argument for entry?

Output STRICTLY this JSON (no preamble, no markdown):
{
  "catalyst_status": {
    "status": "HAPPENED|SCHEDULED|RUMORED|EXPECTED",
    "event_date": "YYYY-MM-DD or null if rumored",
    "days_until": -2 (negative if past) or 7 (future),
    "countdown_label": "happened 2 days ago" OR "in 7 days" OR "rumored, no date",
    "verified_via": "company press release / SEC 8-K / FDA / news source"
  },
  "outcome_prediction": {
    "catalyst_type": "earnings|fda|ma|clinical|spinoff|index|hyperscaler_deal|other",
    "expected_outcome": "BEAT_AND_RAISE|BEAT|INLINE|MISS|APPROVAL|CRL|DEAL_CLOSE|DEAL_BREAK|DATA_HIT|DATA_MISS|SPINOFF_COMPLETE|INDEX_ADD|other",
    "outcome_probability_pct": 0-100,
    "outcome_reasoning": "Why this outcome is most likely. Cite consensus numbers, beat history, peer reads, AdComm votes, etc.",
    "consensus_data": "specific facts: 'consensus EPS $2.10, whisper $2.15, beat 4 of last 4'"
  },
  "expected_move": {
    "if_positive_pct": "+X (numeric, e.g. 18 for +18%)",
    "if_negative_pct": "-X (numeric, e.g. -12 for -12%)",
    "expected_value_pct": "weighted EV based on outcome probability"
  },
  "analog_precedent": {
    "similar_setups": [
      {"ticker": "ABCD", "date": "2025-08-15", "catalyst": "Q2 beat + raise", "next_day_pct": 18.5, "one_week_pct": 22.0, "note": "1-line context"},
      {"ticker": "EFGH", "date": "2024-11-22", "catalyst": "FDA approval", "next_day_pct": -5.0, "one_week_pct": -12.0, "note": "missed expectations"}
    ],
    "median_next_day_pct": 12.5,
    "win_rate_pct": 67,
    "summary": "1-2 sentence pattern across analogs"
  },
  "stacking_analysis": {
    "stacked_catalysts": ["earnings beat", "insider cluster", "revision spike"],
    "compounding_effect": "When this combination stacks, historical avg move is X% with Y% win rate based on analogs",
    "amplification_factor": 1.5
  },
  "lottery_thesis": {
    "best_strike_otm_pct": 12,
    "best_dte_days": 14,
    "expected_premium_500pct_target_move_pct": 25,
    "thesis_paragraph": "Buy 14-DTE 12% OTM call. Catalyst on DATE. If outcome is X (Z% probable), stock moves +Y% based on N analogs. Contract 5x's at $TARGET. Stop at -50% premium. Risk: NEGATIVE_OUTCOME."
  },
  "verdict": "STRONG BUY|BUY|HOLD|SKIP",
  "confidence_pct": 0-100,
  "reason_to_buy": "1-2 sentence strongest bull case",
  "reason_to_avoid": "1-2 sentence strongest bear case",
  "research_note": "180-250 word synthesis with specific facts and analog reads",
  "red_flags_found": ["specific flag 1", "specific flag 2"]
}"""


def _build_user_prompt(c):
    cats = c.get("catalysts") or []
    cat_lines = [f"- {x.get('label', x.get('key', ''))}: {x.get('details', '')}" for x in cats[:5]]
    news = (c.get("news") or {}).get("headlines") or []
    news_lines = [f"- [{h.get('date','')[:10]}] {h.get('title','')}" for h in news[:6] if h.get('title')]
    bs = c.get("buy_signal") or {}
    return f"""Ticker: {c['ticker']} ({c.get('name', '')})
Sector: {c.get('sector', 'unknown')}
Mcap: ${(c.get('market_cap') or 0)/1e9:.2f}B
Price: ${c.get('price', 0):.2f}
$Volume 20d: ${(c.get('dollar_volume_20d') or 0)/1e6:.0f}M
Short Interest: {c.get('short_pct_float') or 'n/a'}%

Catalyst events from scanner:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

Recent news:
{chr(10).join(news_lines) if news_lines else '(none)'}

Scanner says: signal={bs.get('signal')}, probability={bs.get('probability_pct')}%, expected move {bs.get('expected_move_low_pct')}-{bs.get('expected_move_high_pct')}% next day.

Use web_search to verify the catalyst, check recent analyst coverage, and look for risks the scanner missed. Then write the research note."""


def deep_research(top_candidates, max_tickers=5, verbose=True):
    if not ANTHROPIC_AVAILABLE:
        if verbose:
            print("  anthropic SDK not installed -- skipping deep research")
        return {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if verbose:
            print("  ANTHROPIC_API_KEY not set -- skipping deep research")
        return {}

    client = anthropic.Anthropic()
    results = {}
    total_in = 0
    total_out = 0
    errors = 0

    for i, c in enumerate(top_candidates[:max_tickers]):
        if verbose:
            print(f"  [deep {i+1}/{min(max_tickers, len(top_candidates))}] researching {c['ticker']}...")
        if i > 0 and DEEP_INTER_CALL_SLEEP_SEC > 0:
            if verbose:
                print(f"    sleeping {DEEP_INTER_CALL_SLEEP_SEC}s to respect Anthropic rate limit (30K tok/min)...")
            time.sleep(DEEP_INTER_CALL_SLEEP_SEC)
        attempt = 0
        response = None
        while attempt < 3:
            try:
                user_prompt = _build_user_prompt(c)
                response = client.messages.create(
                    model=DEEP_MODEL,
                    max_tokens=4000,
                    system=DEEP_SYSTEM,
                    messages=[{"role": "user", "content": user_prompt}],
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                )
                break
            except anthropic.RateLimitError as e:
                attempt += 1
                if attempt >= 3:
                    raise
                if verbose:
                    print(f"    rate-limited, sleeping {DEEP_RATE_LIMIT_RETRY_SEC}s (attempt {attempt}/3)...")
                time.sleep(DEEP_RATE_LIMIT_RETRY_SEC)
        try:
            if response is None:
                raise RuntimeError("response not set after retries")
            text_blocks = [b.text for b in response.content if b.type == "text"]
            joined_no_breaks = "".join(text_blocks).strip()
            data = _extract_json(joined_no_breaks)
            if not data:
                joined_with_breaks = "\n".join(text_blocks).strip()
                data = _extract_json(joined_with_breaks)
            if data:
                results[c["ticker"]] = {
                    "verdict": data.get("verdict", "HOLD"),
                    "confidence_pct": data.get("confidence_pct", 50),
                    "reason_to_buy": data.get("reason_to_buy", "")[:300],
                    "reason_to_avoid": data.get("reason_to_avoid", "")[:300],
                    "research_note": data.get("research_note", "")[:1800],
                    "red_flags_found": data.get("red_flags_found", [])[:5],
                    "outcome_prediction": data.get("outcome_prediction") or {},
                    "expected_move": data.get("expected_move") or {},
                    "catalyst_status": data.get("catalyst_status") or {},
                    "analog_precedent": data.get("analog_precedent") or {},
                    "stacking_analysis": data.get("stacking_analysis") or {},
                    "lottery_thesis": data.get("lottery_thesis") or {},
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
                total_in += response.usage.input_tokens
                total_out += response.usage.output_tokens
            else:
                errors += 1
                if verbose:
                    print(f"    failed to parse JSON for {c['ticker']}")
        except Exception as e:
            errors += 1
            if verbose:
                print(f"    deep research failed for {c['ticker']}: {type(e).__name__}: {e}")

    if verbose and results:
        if "opus" in DEEP_MODEL.lower():
            in_rate, out_rate = 5.0, 25.0
        elif "sonnet" in DEEP_MODEL.lower():
            in_rate, out_rate = 3.0, 15.0
        elif "haiku" in DEEP_MODEL.lower():
            in_rate, out_rate = 1.0, 5.0
        else:
            in_rate, out_rate = 3.0, 15.0
        cost_in = total_in * in_rate / 1_000_000
        cost_out = total_out * out_rate / 1_000_000
        print(f"  deep research ({DEEP_MODEL}): {len(results)} notes, tokens in={total_in} out={total_out}, ~${cost_in + cost_out:.3f}")
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

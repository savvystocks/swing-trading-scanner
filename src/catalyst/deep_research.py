import os
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

DEEP_MODEL = os.environ.get("CATALYST_DEEP_MODEL", "claude-sonnet-4-6")

DEEP_SYSTEM = """You are a swing-trading analyst predicting the OUTCOME of tomorrow's catalyst event. The trader buys at today's US close to capture the overnight gap, so your job is forecasting WHAT THE CATALYST WILL ACTUALLY DELIVER, not just verifying it exists.

PRIMARY MISSION: forecast the outcome with conviction.

Use web_search aggressively to find concrete numbers:

For EARNINGS catalysts:
- Consensus EPS / revenue estimates from Yahoo Finance, MarketWatch, Zacks
- Whisper number from EarningsWhispers, Estimize, Seeking Alpha
- Beat streak: did they beat last 4 quarters? By how much?
- Recent guidance: did management raise or lower in last earnings call?
- Sector peers' recent prints: Q1 results from same-industry names already reported (read across)
- Analyst revisions: upgrades/downgrades/PT changes in last 30 days
- Insider activity: buying or selling pre-print

For FDA / CLINICAL catalysts:
- Phase 3 endpoint hit/missed in actual data readout
- Statistical significance (p-values, hazard ratio)
- Safety profile vs comparable drugs
- Prior FDA AdComm vote if applicable
- Drug class historical approval rate (e.g. checkpoint inhibitors approve at X%)
- Comparable trial outcomes (similar drug, similar endpoint)

For M&A catalysts:
- Deal price vs current spread (% upside if closes)
- Antitrust risk (HHI, market share concentration, prior similar deals blocked)
- Financing committed (cash, stock, debt; rating agency views)
- Termination fees, MAC clauses, walk-rights
- Other bidders, potential topping bids
- Shareholder vote dates

For ANY catalyst, also predict the asymmetric outcomes:
- If POSITIVE outcome: expected next-day move % (cite comparable historical reactions)
- If NEGATIVE outcome: expected downside % (cite comparable failures)

THEN verify the catalyst is real, cross-check from 2+ sources, and identify any scanner-missed risks.

Output strictly this JSON:
{
  "outcome_prediction": {
    "catalyst_type": "earnings|fda|ma|clinical|other",
    "expected_outcome": "BEAT_AND_RAISE|BEAT|INLINE|MISS|APPROVAL|CRL|DEAL_CLOSE|DEAL_BREAK|DATA_HIT|DATA_MISS|other",
    "outcome_probability_pct": 0-100,
    "outcome_reasoning": "Why this outcome is most likely. Cite consensus numbers, beat history, peer reads, AdComm votes, etc.",
    "consensus_data": "specific facts: 'consensus EPS $2.10, whisper $2.15, beat 4 of last 4'"
  },
  "expected_move": {
    "if_positive_pct": "+X% based on Y comparable",
    "if_negative_pct": "-X%",
    "expected_value_pct": "weighted EV % considering probability"
  },
  "verdict": "STRONG BUY|BUY|HOLD|SKIP",
  "confidence_pct": 0-100,
  "reason_to_buy": "1-2 sentence strongest bull case with specifics",
  "reason_to_avoid": "1-2 sentence strongest bear case with specifics",
  "research_note": "180-250 word synthesis citing specific facts, reading across peers, and forecasting the outcome",
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
        try:
            user_prompt = _build_user_prompt(c)
            response = client.messages.create(
                model=DEEP_MODEL,
                max_tokens=4000,
                system=DEEP_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
            )
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

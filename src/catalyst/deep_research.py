import os
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

DEEP_MODEL = os.environ.get("CATALYST_DEEP_MODEL", "claude-opus-4-7")

DEEP_SYSTEM = """You are a senior swing-trading analyst writing a 200-word research note for tomorrow's overnight trade. You can use web_search to verify facts, find recent analyst takes, and cross-check news.

For each ticker you receive:
1. Verify the catalyst is real and material (search for the actual filing or press release)
2. Identify any risks the front-line scanner might have missed (lawsuits, dilution, fraud allegations, regulatory issues)
3. Cross-check news from at least two independent sources
4. Identify the strongest single reason TO buy and the strongest reason NOT to buy
5. Give a final verdict: STRONG BUY / BUY / HOLD / SKIP

Keep notes tight: 150-220 words. Cite specific dollar amounts, dates, percentages where possible. Write for a trader who needs to decide in 30 seconds.

Respond with ONLY a JSON object:
{
  "verdict": "STRONG BUY" | "BUY" | "HOLD" | "SKIP",
  "confidence_pct": 0-100,
  "reason_to_buy": "1-2 sentence strongest bull case with specifics",
  "reason_to_avoid": "1-2 sentence strongest bear case with specifics",
  "research_note": "150-220 word synthesis citing specific facts",
  "red_flags_found": ["short specific flag 1", "flag 2"]
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
            full_text = "\n".join(text_blocks).strip()
            data = _extract_json(full_text)
            if data:
                results[c["ticker"]] = {
                    "verdict": data.get("verdict", "HOLD"),
                    "confidence_pct": data.get("confidence_pct", 50),
                    "reason_to_buy": data.get("reason_to_buy", "")[:300],
                    "reason_to_avoid": data.get("reason_to_avoid", "")[:300],
                    "research_note": data.get("research_note", "")[:1500],
                    "red_flags_found": data.get("red_flags_found", [])[:5],
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
        cost_in = total_in * 5.0 / 1_000_000
        cost_out = total_out * 25.0 / 1_000_000
        print(f"  deep research: {len(results)} notes, tokens in={total_in} out={total_out}, ~${cost_in + cost_out:.3f}")
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

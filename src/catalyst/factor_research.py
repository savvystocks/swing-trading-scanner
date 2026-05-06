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
FACTOR_RESEARCH_MODEL = os.environ.get("FACTOR_RESEARCH_MODEL", "claude-sonnet-4-6")


FACTOR_RESEARCH_SYSTEM = """You are a swing-trading analyst evaluating a lower-cap stock that matches multiple of the 20 factors that drove last year's top 20 best-performing US stocks. The trader is looking for the NEXT generation of these movers — small/mid caps in the right business with room to re-rate.

These are NOT catalyst-driven binary trades. They're trend / theme exposure trades. The thesis is: this company sits in a hot theme (AI infrastructure, data center power, optical, memory, etc.) at a small-mid mcap where re-rating is still possible. The trade is held 30-60 days for 100-200% returns on options or 20-50% on stock.

You will receive:
- Ticker, name, sector, industry, mcap
- Description of the business
- Matched factors (themes + events firing for this name)

Use web_search aggressively to find:
1. WHY this company is positioned for the matched themes — specific products, customers, capacity, recent news
2. Upcoming catalysts (earnings date, product launch, contract awards, etc.)
3. Recent analog: a similar-cap name in the same theme that re-rated 50-200% in the last 12 months — what drove it, what would drive this one similarly
4. Recommended options structure (strike OTM%, DTE) — typically 30-45 DTE, 0-10% OTM, target 100-200% premium ROI
5. Risk factors specific to this name
6. Position-in-theme: within their cohort, are they a leader or laggard? Laggards-with-strong-fundamentals are the asymmetric trade.

Output STRICTLY this JSON (no preamble, no markdown):
{
  "thesis_status": {
    "status": "FRESH_OPPORTUNITY|EARLY_INNINGS|MID_CYCLE|LATE_CYCLE",
    "label": "1 sentence on where this name is in the theme cycle"
  },
  "next_catalyst": {
    "type": "earnings|product_launch|contract|conference|fda|other",
    "expected_date": "YYYY-MM-DD or null",
    "days_until": -10 or 25 or null,
    "description": "1 sentence"
  },
  "theme_exposure": {
    "primary_theme": "AI data center / Memory / Optical / etc.",
    "exposure_pct": "rough % of revenue tied to theme — cite source if found",
    "key_customers": ["customer1", "customer2"],
    "thesis_strength": "STRONG|MODERATE|WEAK",
    "summary": "2-3 sentence explanation"
  },
  "analog_precedent": {
    "similar_setup": {"ticker": "ABCD", "date": "2025-08-15", "reason": "similar size + theme exposure", "return_pct": 120},
    "summary": "What we'd expect if this name re-rates similarly"
  },
  "position_in_theme": {
    "rank": "leader|mid|laggard|unknown",
    "ytd_return_estimate_pct": 15,
    "asymmetry_score": "HIGH|MEDIUM|LOW",
    "comment": "1 sentence"
  },
  "options_thesis": {
    "best_strike_otm_pct": 8,
    "best_dte_days": 35,
    "target_return_pct": 150,
    "expected_premium_target_move_pct": 18,
    "thesis_paragraph": "Buy 35-DTE 8% OTM call. The theme is X, this name has Y exposure. Expected stock move: +Z% over 1 month. If hits, contract 2.5x's. Stop -50% premium."
  },
  "verdict": "STRONG BUY|BUY|HOLD|SKIP",
  "confidence_pct": 0-100,
  "research_note": "180-250 word synthesis with specific facts and analog reads",
  "red_flags_found": ["specific flag 1", "specific flag 2"]
}"""


def _build_factor_prompt(match):
    matched_themes = [f["factor_name"] for f in match.get("matched_factors", []) if f.get("type") == "theme"]
    matched_events = [f["factor_name"] for f in match.get("matched_factors", []) if f.get("type") == "event"]
    desc = (match.get("description") or "")[:500]
    return f"""Ticker: {match['ticker']} ({match.get('name', '')})
Sector: {match.get('sector', '')}
Industry: {match.get('industry', '')}
Mcap: ${(match.get('market_cap') or 0)/1e9:.2f}B
Price: ${match.get('price') or match.get('live_spot') or 0:.2f}

Description:
{desc}

Matched THEMES (from top-20-mover factor screener):
{chr(10).join('- ' + t for t in matched_themes) if matched_themes else '(none)'}

Matched EVENTS firing today:
{chr(10).join('- ' + e for e in matched_events) if matched_events else '(none)'}

Research this name as a candidate for the next generation of theme movers. Use web_search to verify thesis, find peers, identify upcoming catalysts, and recommend an options trade structure."""


def research_factor_finds(matches, max_tickers=5, verbose=True):
    if not ANTHROPIC_AVAILABLE:
        if verbose:
            print("  factor_research: anthropic SDK missing -- skipping")
        return {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if verbose:
            print("  factor_research: ANTHROPIC_API_KEY not set -- skipping")
        return {}

    client = anthropic.Anthropic()
    results = {}
    total_in = 0
    total_out = 0
    errors = 0

    top = matches[:max_tickers]
    if verbose:
        print(f"  factor_research: researching top {len(top)} factor finds (Sonnet + web_search)")

    for i, m in enumerate(top):
        if verbose:
            print(f"    [factor_deep {i+1}/{len(top)}] researching {m['ticker']}...")
        if i > 0 and DEEP_INTER_CALL_SLEEP_SEC > 0:
            if verbose:
                print(f"      sleeping {DEEP_INTER_CALL_SLEEP_SEC}s for rate limit...")
            time.sleep(DEEP_INTER_CALL_SLEEP_SEC)
        attempt = 0
        response = None
        while attempt < 3:
            try:
                user_prompt = _build_factor_prompt(m)
                response = client.messages.create(
                    model=FACTOR_RESEARCH_MODEL,
                    max_tokens=4000,
                    system=FACTOR_RESEARCH_SYSTEM,
                    messages=[{"role": "user", "content": user_prompt}],
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                )
                break
            except anthropic.RateLimitError:
                attempt += 1
                if attempt >= 3:
                    raise
                if verbose:
                    print(f"      rate-limited, sleeping {DEEP_RATE_LIMIT_RETRY_SEC}s (attempt {attempt}/3)...")
                time.sleep(DEEP_RATE_LIMIT_RETRY_SEC)
        try:
            if response is None:
                raise RuntimeError("response not set")
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            data = _extract_json(text)
            if data:
                results[m["ticker"]] = {
                    "thesis_status": data.get("thesis_status") or {},
                    "next_catalyst": data.get("next_catalyst") or {},
                    "theme_exposure": data.get("theme_exposure") or {},
                    "analog_precedent": data.get("analog_precedent") or {},
                    "position_in_theme": data.get("position_in_theme") or {},
                    "options_thesis": data.get("options_thesis") or {},
                    "verdict": data.get("verdict", "HOLD"),
                    "confidence_pct": data.get("confidence_pct", 50),
                    "research_note": data.get("research_note", "")[:1800],
                    "red_flags_found": data.get("red_flags_found", [])[:5],
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
                total_in += response.usage.input_tokens
                total_out += response.usage.output_tokens
            else:
                errors += 1
                if verbose:
                    print(f"      failed to parse JSON for {m['ticker']}")
        except Exception as e:
            errors += 1
            if verbose:
                print(f"      factor_deep failed for {m['ticker']}: {type(e).__name__}: {e}")

    if verbose and results:
        cost = (total_in * 3.0 + total_out * 15.0) / 1_000_000
        print(f"  factor_research done: {len(results)} researched, tokens in={total_in} out={total_out}, ~${cost:.3f}")
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

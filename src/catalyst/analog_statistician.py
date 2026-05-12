import os
import json
import time


try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


ANALOG_MODEL = os.environ.get("ANALOG_MODEL", "claude-sonnet-4-6")
ANALOG_SLEEP = int(os.environ.get("ANALOG_SLEEP", "65"))


ANALOG_SYSTEM = """You are a quantitative trading analyst building an ANALOG SET for a current setup. Your job: find 5-7 historical analogs from the last 24 months where the EXACT SAME pattern fired, then compute statistics on outcomes.

A valid analog requires:
- Same sector or theme
- Similar market cap (within 50%)
- Same catalyst type (earnings vs FDA vs M&A — don't mix)
- Same signal stack (insider + analyst + theme is different from just earnings)
- Same market regime (don't mix bear-market analogs into bull-market setup)

Use web_search aggressively to find these. Cite tickers, dates, catalyst details, and actual price moves.

Output STRICTLY this JSON:
{
  "analogs": [
    {"ticker": "ABCD", "date": "2025-08-15", "catalyst": "1-line description", "mcap_b": 4.2, "next_day_pct": 18.5, "one_week_pct": 22.0, "two_week_pct": 24.0, "max_drawdown_pct": -8.0, "note": "1-line context"}
  ],
  "statistics": {
    "n_analogs": 6,
    "win_rate_next_day_pct": 67,
    "win_rate_one_week_pct": 71,
    "median_next_day_pct": 12.5,
    "median_one_week_pct": 14.2,
    "p25_next_day_pct": 4.0,
    "p75_next_day_pct": 22.0,
    "mean_drawdown_pct": -7.0,
    "worst_outcome_pct": -8.0
  },
  "quality_score": 0-100,
  "confidence": "HIGH|MEDIUM|LOW",
  "summary": "1-2 sentence pattern across analogs",
  "thesis_validation": "STRONG|MODERATE|WEAK|REJECT",
  "thesis_validation_reasoning": "why analogs support or refute the bull thesis"
}

If you cannot find 5+ analogs: set n_analogs to what you found, set quality_score low, set thesis_validation to WEAK or REJECT."""


def _build_user_prompt(candidate):
    cats = candidate.get("catalysts") or []
    cat_lines = [f"- [{c.get('tier','?')}] {c.get('label','')}: {c.get('details','')[:120]}" for c in cats[:5]]
    return f"""Ticker: {candidate['ticker']} ({candidate.get('name','')})
Sector: {candidate.get('sector','')}
Industry: {candidate.get('industry','')}
Mcap: ${(candidate.get('market_cap') or 0)/1e9:.2f}B
Bracket: {candidate.get('bracket', 'unknown')}

Catalysts firing:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

Smart money signals: {', '.join(candidate.get('_smart_money_signals') or []) or 'none'}

Find 5-7 historical analogs from last 24 months matching this setup exactly. Compute statistics on outcomes. Validate or reject the bull thesis based on analog evidence."""


def research_analogs(candidate, verbose=False):
    if not ANTHROPIC_AVAILABLE or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=ANALOG_MODEL,
            max_tokens=4000,
            system=ANALOG_SYSTEM,
            messages=[{"role": "user", "content": _build_user_prompt(candidate)}],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        data = _extract_json(text)
        if data:
            data["_input_tokens"] = response.usage.input_tokens
            data["_output_tokens"] = response.usage.output_tokens
        return data
    except Exception as e:
        if verbose:
            print(f"    analog_research failed for {candidate.get('ticker')}: {type(e).__name__}: {e}")
        return None


def apply_analog_validation(candidates, max_calls=10, verbose=False):
    if not candidates:
        return candidates
    enriched = 0
    for i, s in enumerate(candidates[:max_calls]):
        if i > 0 and ANALOG_SLEEP > 0:
            time.sleep(ANALOG_SLEEP)
        if verbose:
            print(f"    [analog {i+1}/{min(max_calls, len(candidates))}] {s.get('ticker')}...")
        result = research_analogs(s, verbose=verbose)
        if result:
            s["analog_set"] = result
            enriched += 1
    if verbose:
        print(f"  analog statistician: {enriched}/{min(max_calls, len(candidates))} validated")
    return candidates


def analog_passes_bracket_gate(candidate, bracket, tier):
    aset = candidate.get("analog_set") or {}
    stats = aset.get("statistics") or {}
    n = stats.get("n_analogs") or 0
    win_rate = stats.get("win_rate_next_day_pct") or 0
    if tier == "A++":
        thresholds = {"micro": {"min_n": 6, "min_win": 65}, "small": {"min_n": 7, "min_win": 60}, "mid": {"min_n": 7, "min_win": 55}}
    elif tier == "A+":
        thresholds = {"micro": {"min_n": 4, "min_win": 55}, "small": {"min_n": 5, "min_win": 50}, "mid": {"min_n": 5, "min_win": 45}}
    else:
        thresholds = {"micro": {"min_n": 3, "min_win": 45}, "small": {"min_n": 3, "min_win": 40}, "mid": {"min_n": 3, "min_win": 35}}
    t = thresholds.get(bracket, {"min_n": 3, "min_win": 45})
    if not aset:
        return tier == "A"
    return n >= t["min_n"] and win_rate >= t["min_win"]


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

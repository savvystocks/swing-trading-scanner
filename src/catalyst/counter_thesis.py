import os
import json


try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


COUNTER_MODEL = os.environ.get("COUNTER_MODEL", "claude-sonnet-4-6")


COUNTER_SYSTEM = """You are a SHORT-SELLER analyst writing the bear thesis against a long trade your firm is considering. Your job: be ruthless. Find every reason this trade fails.

You will receive: ticker, the BULL thesis someone wrote, the catalyst stack, financial data, and analog history.

Output STRICTLY this JSON:
{
  "bear_thesis": "3-sentence ruthless counter-case",
  "specific_risks": ["specific risk 1 with evidence", "specific risk 2", "specific risk 3"],
  "bear_score": 0-100,
  "what_kills_this_trade": "the SINGLE most likely failure mode in plain English",
  "warning_signs_to_watch": ["sign 1 — what to look for", "sign 2", "sign 3"],
  "max_drawdown_scenario_pct": -X,
  "verdict_on_bull_thesis": "STRONG|MODERATE|WEAK|REJECTED"
}

Be harsh. Bull theses are easy to write. Bear theses save accounts."""


def _build_prompt(candidate, bull_thesis):
    cats = candidate.get("catalysts") or []
    cat_lines = [f"- [{c.get('tier','?')}] {c.get('label','')}" for c in cats[:5]]
    landmines = candidate.get("_landmine_flags") or []
    landmine_lines = [f"- {f['severity']}: {f['label']}" for f in landmines]
    analog_set = candidate.get("analog_set") or {}
    stats = analog_set.get("statistics") or {}
    peer = candidate.get("peer_benchmark") or {}

    return f"""Ticker: {candidate['ticker']} ({candidate.get('name','')})
Mcap: ${(candidate.get('market_cap') or 0)/1e9:.2f}B
Bracket: {candidate.get('bracket')}
Industry: {candidate.get('industry','')}

CATALYSTS:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

LANDMINES DETECTED:
{chr(10).join(landmine_lines) if landmine_lines else '(none detected — does NOT mean none exist)'}

ANALOG STATS:
N={stats.get('n_analogs', '?')}, win rate={stats.get('win_rate_next_day_pct', '?')}%, worst case={stats.get('worst_outcome_pct', '?')}%

PEER BENCHMARKS:
Growth percentile: {peer.get('growth_percentile_avg', '?')}, Quality percentile: {peer.get('quality_percentile_avg', '?')}

BULL THESIS provided by long-side analyst:
{bull_thesis}

Now: write the SHORT thesis. Find what's wrong with the bull case. Be specific."""


def generate_counter_thesis(candidate, bull_thesis):
    if not ANTHROPIC_AVAILABLE or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    if not bull_thesis:
        return None
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=COUNTER_MODEL,
            max_tokens=2000,
            system=COUNTER_SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(candidate, bull_thesis)}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        data = _extract_json(text)
        if data:
            data["_input_tokens"] = response.usage.input_tokens
            data["_output_tokens"] = response.usage.output_tokens
        return data
    except Exception:
        return None


def apply_counter_thesis(candidates, max_calls=6, verbose=False):
    enriched = 0
    for s in candidates[:max_calls]:
        deep = s.get("deep_research") or {}
        bull = deep.get("research_note") or deep.get("reason_to_buy") or ""
        if not bull:
            continue
        result = generate_counter_thesis(s, bull)
        if result:
            s["counter_thesis"] = result
            enriched += 1
    if verbose:
        print(f"  counter_thesis: {enriched}/{min(max_calls, len(candidates))} bear cases generated")
    return candidates


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

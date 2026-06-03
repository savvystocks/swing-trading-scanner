import os
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

MODEL = os.environ.get("CATALYST_LLM_MODEL", "claude-haiku-4-5")

SYSTEM_PROMPT = """You are a swing trading analyst grading overnight catalyst plays.

For each ticker, you receive:
- Catalyst event(s) filed or scheduled
- Recent news headlines
- Company context (sector, market cap)

Rate the bullish strength for the next-day stock move on a 0-10 scale:
0-2: Negative or neutral (sell signal, dilution, miss, lawsuit, going concern)
3-4: Weak positive (vague PR, fluff partnership, tier-D filing)
5-6: Moderate positive (standard earnings beat, tier-B filing, modest deal)
7-8: Strong positive (clear strategic win, beat + raise guidance, FDA approval, large M&A)
9-10: Exceptional (cash buyout at premium, breakthrough therapy, transformative deal)

Consider: deal value relative to mcap, premium offered, strategic fit, surprise factor, balance sheet impact, dilution risk, competitive positioning, recency.

Penalize:
- Going-concern language, recent dilution, micro-float pump signals
- Vague PR with no concrete deal value or terms
- Chinese small-cap ADRs without verifiable catalysts

Reward:
- Specific dollar amounts, premiums, percentages disclosed
- Clear strategic win (M&A, FDA approval, large contract)
- Multiple corroborating positive signals across catalysts and news

Respond with ONLY a JSON object:
{"score": X.X, "reasoning": "1-2 sentence justification", "key_signal": "the strongest single signal"}"""


BEAR_SYSTEM_PROMPT = """You are a swing trading analyst grading PUT/SHORT setups.

For each ticker, you receive:
- Positioning context (this ticker is flagged as a potential SHORT/PUT trade)
- Recent news headlines
- Company context (sector, market cap)
- Why positioning thinks it's extended/euphoric

Rate the BEARISH strength for the next 5-15 day stock move on a 0-10 scale:
0-2: No short edge (no extension, no negative catalysts, positioning is wrong)
3-4: Weak bearish (mild extension, sector weakness only)
5-6: Moderate bearish (extended technicals + macro headwind, no positive catalysts)
7-8: Strong bearish (vertical move + negative news + extension above 200dma + crowded long)
9-10: Exceptional short (climax run + earnings miss + insider selling + sector breakdown + crowded positioning)

Consider for SHORT:
- Pct extended above 200dma + recent vertical move = climax risk
- COT crowded long + macro RISK_OFF + IV skew (call buying mania) = positioning exhaustion
- Negative analyst revisions + insider selling + competition disruption
- Sector breakdown + relative underperformance vs peers

Beware:
- Squeeze risk - high short interest + retail buying flow can squeeze a "shorting setup"
- Acquisition rumors - any cash buyout = SKIP the short
- Dividend dates - shorting through ex-div is expensive
- Federal/government action - antitrust could cut either way

Reward in scoring:
- Hard evidence of overheated positioning (specific COT percentiles, specific extension %, specific recent return)
- Negative catalysts converging (downgrade + miss + guidance cut)
- Technical breakdown confirmation (broken support, MA cross down)

Respond with ONLY a JSON object:
{"score": X.X, "reasoning": "1-2 sentence justification", "key_signal": "the strongest single short signal", "squeeze_risk": "LOW|MED|HIGH"}"""


def _build_user_prompt(ticker, name, sector, mcap, catalysts, news_headlines):
    mcap_str = f"${mcap/1e9:.2f}B" if mcap else "n/a"
    cat_lines = []
    for c in catalysts[:5]:
        cat_lines.append(f"- {c.get('label', c.get('key', ''))}: {c.get('details', '')}")
    news_lines = []
    for h in (news_headlines or [])[:5]:
        title = h.get("title", "")[:140]
        date = h.get("date", "")[:10]
        if title:
            news_lines.append(f"- [{date}] {title}")

    return f"""Ticker: {ticker} ({name})
Sector: {sector or 'unknown'} | Mcap: {mcap_str}

Catalyst events:
{chr(10).join(cat_lines) if cat_lines else '(none)'}

Recent news:
{chr(10).join(news_lines) if news_lines else '(none in last 7 days)'}

Grade this catalyst setup."""


def grade_one(client, ticker, name, sector, mcap, catalysts, news_headlines, side="CALL", positioning_signals=None):
    user_prompt = _build_user_prompt(ticker, name, sector, mcap, catalysts, news_headlines)
    if side == "PUT" and positioning_signals:
        sig_lines = "\n".join(f"- {s.get('label', s.get('key', ''))}" for s in positioning_signals[:5])
        user_prompt = user_prompt + f"\n\nPositioning context (why flagged SHORT):\n{sig_lines}\n\nGrade the BEARISH/PUT setup."
    system_prompt_text = BEAR_SYSTEM_PROMPT if side == "PUT" else SYSTEM_PROMPT
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=[{
                "type": "text",
                "text": system_prompt_text,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
        return {
            "score": float(data.get("score", 0)),
            "reasoning": data.get("reasoning", "")[:200],
            "key_signal": data.get("key_signal", "")[:100],
            "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    except Exception as e:
        return {
            "score": 0.0,
            "reasoning": f"grading error: {type(e).__name__}",
            "key_signal": "",
            "error": str(e)[:200],
        }


def grade_candidates(candidates, max_grade=50, verbose=True):
    if not ANTHROPIC_AVAILABLE:
        if verbose:
            print("  anthropic SDK not installed -- skipping LLM grading")
        return {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if verbose:
            print("  ANTHROPIC_API_KEY not set -- skipping LLM grading (set the secret to enable)")
        return {}

    client = anthropic.Anthropic()
    sorted_candidates = sorted(
        candidates,
        key=lambda c: c.get("base_points", 0) + c.get("modifier_points", 0),
        reverse=True,
    )[:max_grade]

    results = {}
    total_in = 0
    total_out = 0
    total_cached = 0
    errors = 0

    from concurrent.futures import ThreadPoolExecutor, as_completed

    max_workers = int(os.environ.get("LLM_GRADER_WORKERS", "8"))

    def _grade_safely(c):
        try:
            pf = c.get("_positioning_first") or {}
            side = pf.get("side") or "CALL"
            grade = grade_one(
                client,
                ticker=c["ticker"],
                name=c.get("name") or c.get("company") or "",
                sector=c.get("sector"),
                mcap=c.get("market_cap"),
                catalysts=c.get("catalysts") or [],
                news_headlines=(c.get("news") or {}).get("headlines") or [],
                side=side,
                positioning_signals=pf.get("positioning_signals") or [],
            )
            if grade:
                grade["side"] = side
            return c["ticker"], grade, None
        except Exception as e:
            return c.get("ticker"), None, e

    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_grade_safely, c): c for c in sorted_candidates}
        for fut in as_completed(futures):
            ticker, grade, err = fut.result()
            completed += 1
            if err:
                errors += 1
                if verbose and errors < 3:
                    print(f"  llm grade failed for {ticker}: {type(err).__name__}: {err}")
                continue
            results[ticker] = grade
            total_in += grade.get("input_tokens", 0)
            total_out += grade.get("output_tokens", 0)
            total_cached += grade.get("cache_read", 0)
            if grade.get("error"):
                errors += 1
            if verbose and completed > 0 and completed % 10 == 0:
                print(f"  [LLM {completed}/{len(sorted_candidates)}] cached_tokens={total_cached} errors={errors}")

    if verbose:
        cost_in = (total_in - total_cached) * 1.0 / 1_000_000
        cost_cached = total_cached * 0.1 / 1_000_000
        cost_out = total_out * 5.0 / 1_000_000
        total_cost = cost_in + cost_cached + cost_out
        print(f"  LLM graded {len(results)} names. Tokens: in={total_in} cached={total_cached} out={total_out}. ~${total_cost:.3f}")

    return results


def llm_score_to_points(grade, points_max=30.0):
    if not grade:
        return {"points": 0.0, "label": "no LLM grade"}
    score = grade.get("score", 0)
    points = score / 10.0 * points_max
    return {
        "points": round(points, 2),
        "label": f"LLM {score:.1f}/10: {grade.get('key_signal', '')[:60]}",
        "llm_score": score,
        "reasoning": grade.get("reasoning", ""),
        "key_signal": grade.get("key_signal", ""),
    }

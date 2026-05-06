import os
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

GRADER_MODEL = os.environ.get("CATALYST_OPTION_GRADER_MODEL", "claude-haiku-4-5")

GRADER_SYSTEM = """You are an options pricing analyst grading a specific call contract picked by a scanner. The trader is targeting a 500% gain in 1-2 weeks with a -50% premium stop. Your job is to assess whether THIS CONTRACT is well-priced for the expected catalyst, and whether the trader should take it as-is, switch to a spread, change the strike, or skip entirely.

You will receive:
- Underlying ticker, current price
- Contract details: strike, expiration, DTE, mid, bid, ask, spread%, delta, gamma, theta, vega, IV%
- Catalyst context: expected move (+/-), days to event, outcome probability
- Required stock move for 500% target return

Assess each of:

1. IV LEVEL — is the implied vol elevated (event premium), fair, or compressed? Compare to typical post-earnings/post-event IV. Above 60% on a non-binary catalyst is expensive; below 30% on a binary catalyst is cheap. Consider the catalyst type (FDA/M&A binary catalysts justify higher IV).

2. IV CRUSH RISK — for binary/scheduled events, IV typically craters 30-50% post-event. Estimate how much premium the trader could lose to IV alone if the stock doesn't move enough. A delta 0.3 ATM call with IV 80% might shed 30% of value just from IV crush even if stock holds.

3. DELTA & STRIKE EFFICIENCY — given the expected move, is this strike too far OTM (low probability) or too close (low leverage for 500%)? Sweet spot for 500% lottery is delta 0.20-0.40 typically. Note if the expected move barely covers the required move (low margin of safety).

4. SPREAD COST — round-trip slippage. Spread% > 20 is concerning. Above 30 makes the trade unworkable for an exit.

5. THETA BURN — daily premium decay as % of mid. If theta burn > 5%/day and DTE is short, the trade has a tight window.

6. GREEKS BALANCE — is gamma high enough to amplify a move? Is vega exposure manageable?

VERDICT options:
- BUY_AS_IS: contract is well-priced, take as suggested
- PREFER_SPREAD: high IV crush risk, recommend bull call spread to cap vega exposure
- GO_FURTHER_OTM: cheaper higher-delta strike fits 500% better
- GO_CLOSER_ATM: closer to money for higher delta + lower IV crush impact
- SKIP: don't take the trade

Output ONLY this JSON (no markdown, no preamble):
{
  "iv_assessment": {
    "level": "ELEVATED|FAIR|COMPRESSED",
    "iv_pct": 67.6,
    "interpretation": "1 sentence on what current IV implies"
  },
  "iv_crush_risk": {
    "estimated_crush_pct": 30,
    "post_event_premium_loss_pct": 25,
    "concern_level": "HIGH|MEDIUM|LOW"
  },
  "strike_efficiency": {
    "delta": 0.37,
    "rating": "GOOD|OK|POOR",
    "comment": "1 sentence on delta vs required move"
  },
  "spread_quality": {
    "spread_pct": 24.8,
    "rating": "WIDE|FAIR|TIGHT",
    "round_trip_slippage_pct": 12
  },
  "theta_burn": {
    "per_day_pct": 8,
    "warning": "1 sentence if concerning"
  },
  "verdict": "BUY_AS_IS|PREFER_SPREAD|GO_FURTHER_OTM|GO_CLOSER_ATM|SKIP",
  "verdict_reasoning": "2-3 sentence concise reasoning citing specific numbers",
  "suggested_alternative": "1 sentence if applicable, e.g. 'Bull call spread 149/155 cuts IV crush exposure 40% with R/R 3.85 vs naked 5x'",
  "buy_score": 0-100
}"""


def _build_user_prompt(ticker, current_price, contract, deep_research, lottery_ticket):
    cs = (deep_research or {}).get("catalyst_status") or {}
    op = (deep_research or {}).get("outcome_prediction") or {}
    em = (deep_research or {}).get("expected_move") or {}
    spread = lottery_ticket.get("spread_alternative") or {}
    spread_str = ""
    if spread:
        spread_str = f"\nSpread alt available: {spread.get('long_leg',{}).get('strike')}/{spread.get('short_leg',{}).get('strike')}C debit ${spread.get('net_debit')}, max ${spread.get('max_profit_per_spread')}, R/R {spread.get('risk_reward_ratio')}"

    return f"""Ticker: {ticker}
Current price: ${current_price}

Contract picked:
- {contract.get('strike')} CALL exp {contract.get('expiration')} ({contract.get('dte')} DTE)
- Mid ${contract.get('mid')} (bid ${contract.get('bid')}/ask ${contract.get('ask')}, spread {contract.get('spread_pct')}%)
- Delta {contract.get('delta')}, Gamma {contract.get('gamma')}, Theta {contract.get('theta')}, Vega {contract.get('vega')}
- IV {contract.get('iv_pct')}%
- Cost ${contract.get('cost_per_contract')}/contract
- Required stock move for 500% target: {contract.get('required_move_pct')}%

Catalyst context:
- Status: {cs.get('status', 'unknown')} {cs.get('countdown_label', '')}
- Type: {op.get('catalyst_type', 'unknown')}
- Expected outcome: {op.get('expected_outcome', '?')} ({op.get('outcome_probability_pct', '?')}% probability)
- Expected move if positive: {em.get('if_positive_pct', '?')}
- Expected move if negative: {em.get('if_negative_pct', '?')}{spread_str}

Grade this specific contract pick."""


def grade_option_pick(ticker, current_price, lottery_ticket, deep_research_data, verbose=False):
    if not ANTHROPIC_AVAILABLE or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    if not lottery_ticket or not lottery_ticket.get("qualified") or not lottery_ticket.get("contract"):
        return None

    contract = lottery_ticket["contract"]
    user_prompt = _build_user_prompt(ticker, current_price, contract, deep_research_data, lottery_ticket)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=GRADER_MODEL,
            max_tokens=1000,
            system=[{"type": "text", "text": GRADER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
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
        data = json.loads(text[start:end + 1])
        data["_input_tokens"] = response.usage.input_tokens
        data["_output_tokens"] = response.usage.output_tokens
        if verbose:
            print(f"  option_grader {ticker}: verdict={data.get('verdict')} score={data.get('buy_score')}")
        return data
    except Exception as e:
        if verbose:
            print(f"  option_grader {ticker} failed: {type(e).__name__}: {str(e)[:120]}")
        return None


def grade_option_picks(picks, verbose=True):
    total_in = 0
    total_out = 0
    graded = 0
    for p in picks:
        lottery = p.get("lottery") or {}
        if not lottery.get("qualified"):
            continue
        ticket = p.get("ticket") or {}
        ticker = ticket.get("ticker")
        live_price = (p.get("live") or {}).get("spot") or ticket.get("live_spot") or ticket.get("price")
        deep = ticket.get("deep_research")
        if not ticker or not live_price:
            continue
        grade = grade_option_pick(ticker, live_price, lottery, deep, verbose=verbose)
        if grade:
            lottery["llm_option_grade"] = grade
            total_in += grade.get("_input_tokens", 0)
            total_out += grade.get("_output_tokens", 0)
            graded += 1
    if verbose and graded:
        cost_in = total_in * 1.0 / 1_000_000
        cost_out = total_out * 5.0 / 1_000_000
        print(f"  option_grader: graded {graded} picks, tokens in={total_in} out={total_out}, ~${cost_in + cost_out:.4f}")
    return picks

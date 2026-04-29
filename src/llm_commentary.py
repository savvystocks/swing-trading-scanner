import os
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

MODEL = os.environ.get("OPTIONS_LLM_MODEL", "claude-sonnet-4-6")
TOP_N_DEFAULT = 5

SYSTEM_PROMPT = """You are a swing trading analyst writing trade theses for one trader's personal options book.

Audience: the trader himself. Non-coder. Runs a quantitative scanner that pre-filters everything before it reaches him. He reads each card on his phone before deciding to act. He wants the WHY in plain English, fast. He thinks in letter grades - his first live trade was self-rated C+ because the size was over cap and DTE was inside 21.

For each pick you receive:
- Hunter score 0-100 (validated pre-50%-mover signature: P7 short squeeze x2, P6 earnings revisions x2, earnings sweet-spot 11-21d, proximity to 52w high, sector tilt)
- Tier 0-5 (system score)
- Conviction, Opportunity scores
- Ticker, name, sector, market cap
- Pillar summaries (P1 trend, P3 fundamentals, P4 RS, P6 earnings/analysts, P7 supply/demand)
- Gate summaries (G4 catalyst, G7 earnings window)
- Lane B early signals firing
- Move ETA
- Options contract chosen

Produce three outputs per pick:
1. RATING: a single letter grade for the overall trade setup quality.
   A+ = exceptional, top 1% of universe. Multiple high-conviction signals stacked, clean Stage 2, near 52w high, low IV, clean earnings window.
   A  = strong, top 5%. Most signals firing, no major caveats.
   A- = strong with one minor caveat (tight DTE, modest IV, etc).
   B+ = solid, tradeable, multiple confirmations but missing one or two ideal traits.
   B  = decent, average for what makes it through the scanner.
   B- = tradeable but not the strongest in today's list - size smaller.
   C+ = mediocre, takes a leap of faith on one pillar; only if better is unavailable.
   C  = weak, only if conviction is high on a non-quant factor.
   D  = skip. Setup is broken or the options structure is poor (wide spread, IV crush risk, OI thin).
2. THESIS: 2-3 sentences on why this fires NOW. Lead with the strongest single driver. Translate numbers into meaning - "Hunter 78" alone is data, "78/100 because P6 shows 5 consecutive beats and P7 has 18% short interest" is a thesis. Past tense for what already happened, present for the current setup.
3. RISK: ONE sentence on the main thing to size around. Specific - "earnings 8 days out, IV could collapse 30 points" beats "earnings risk".

Style rules:
- Direct. He knows the system, you don't need to teach him basics.
- Quantify when you can. "Doubled volume on the breakout" not "strong volume".
- Honest. Half the picks should grade B+ or below. If everything reads A, the rating is useless.
- Specific to THIS ticker. Avoid generic phrases like "growth name in a hot sector" or "interesting setup worth watching".
- No fluff: skip "this looks interesting", "could see momentum", "watch for follow-through", "worth keeping on the radar".
- Plain text. No emojis. No markdown.

Output ONLY a JSON object: {"rating": "B+", "thesis": "...", "risk": "..."}"""


JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "rating": {
            "type": "string",
            "enum": ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D"],
        },
        "thesis": {"type": "string"},
        "risk": {"type": "string"},
    },
    "required": ["rating", "thesis", "risk"],
    "additionalProperties": False,
}


def _build_user_prompt(t):
    name = t.get("name") or ""
    ticker = t.get("ticker") or "?"
    sector = t.get("sector") or "?"
    industry = t.get("industry") or ""
    mcap = t.get("market_cap")
    mcap_str = f"${mcap/1e9:.1f}B" if mcap else "n/a"

    tier = t.get("tier")
    hunter = t.get("hunter") or {}
    hunter_score = hunter.get("score")
    hunter_eta = hunter.get("eta_label", "")
    hunter_reasons = hunter.get("reasons") or []

    conv_score = (t.get("conviction") or {}).get("score")
    opp_score = (t.get("opportunity") or {}).get("score")

    pillars = t.get("pillars") or {}
    gates = t.get("gates") or {}

    def _summary(d, key):
        return ((d.get(key) or {}).get("summary") or "")[:160]

    lane_b = t.get("lane_b") or {}
    lane_b_signals = []
    if (lane_b.get("pocket_pivot") or {}).get("fired"):
        lane_b_signals.append("Pocket Pivot")
    if (lane_b.get("base_quality") or {}).get("fired"):
        bq = lane_b["base_quality"].get("score", "?")
        lane_b_signals.append(f"Base Quality {bq}/10")
    if (lane_b.get("insider_cluster") or {}).get("fired"):
        ic = lane_b["insider_cluster"].get("buyer_count", "?")
        lane_b_signals.append(f"Insider Cluster {ic} buyers")
    if (lane_b.get("revenue_acceleration") or {}).get("fired"):
        ra = lane_b["revenue_acceleration"].get("latest_qoq_pct", "?")
        lane_b_signals.append(f"Rev Accel {ra}% QoQ")
    if (lane_b.get("earnings_turn") or {}).get("fired"):
        lane_b_signals.append("Earnings Turn")
    if (lane_b.get("peer_pack") or {}).get("fired"):
        lane_b_signals.append("Peer Pack Laggard")

    parts = [
        f"Ticker: {ticker} ({name})",
        f"Sector: {sector}{' / ' + industry if industry else ''}   Mcap: {mcap_str}",
        f"Scores: T{tier}  Hunter {hunter_score}/100  Conviction {conv_score}  Opportunity {opp_score}",
    ]
    if hunter_eta:
        parts.append(f"Move ETA: {hunter_eta}")
    if hunter_reasons:
        parts.append(f"Hunter reasons: {' | '.join(str(r) for r in hunter_reasons[:6])}")
    if lane_b_signals:
        parts.append(f"Lane B firing: {', '.join(lane_b_signals)}")

    parts.append(
        f"Levels: Entry ${t.get('price', 0):.2f}  Stop ${t.get('stop_loss', 0):.2f}  "
        f"Phase1 ${t.get('phase1_target', 0):.2f}  R/R {t.get('risk_reward', '?')}"
    )

    for label, key in [("P1 trend", "p1"), ("P3 fundamentals", "p3"), ("P4 RS", "p4"),
                       ("P6 earnings/analysts", "p6"), ("P7 supply/demand", "p7")]:
        s = _summary(pillars, key)
        if s:
            parts.append(f"{label}: {s}")
    for label, key in [("G4 catalyst", "g4"), ("G7 earnings window", "g7")]:
        s = _summary(gates, key)
        if s:
            parts.append(f"{label}: {s}")

    opt = t.get("options_trade") or {}
    if opt:
        parts.append(
            f"Options pick: {opt.get('strike')}C exp {opt.get('expiration')} ({opt.get('dte')}d), "
            f"delta {opt.get('delta')}, premium ${opt.get('premium_mid', 0):.2f}, "
            f"breakeven ${opt.get('breakeven', 0):.2f} ({opt.get('breakeven_pct_move', 0):+.1f}%), "
            f"IV {opt.get('iv_pct')}%"
        )

    return "\n".join(parts)


def commentary_one(client, ticket):
    user_prompt = _build_user_prompt(ticket)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": JSON_SCHEMA},
            },
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        if not text.strip():
            return {
                "rating": "", "thesis": "", "risk": "",
                "error": f"empty text block (stop_reason={response.stop_reason}, content types={[b.type for b in response.content]})",
            }
        data = json.loads(text)
        return {
            "rating": (data.get("rating") or "").strip()[:3],
            "thesis": (data.get("thesis") or "")[:600],
            "risk": (data.get("risk") or "")[:300],
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            "cache_write": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        }
    except Exception as e:
        return {
            "rating": "",
            "thesis": "",
            "risk": "",
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        }


def add_commentary(tickets, top_n=TOP_N_DEFAULT, verbose=True):
    if not ANTHROPIC_AVAILABLE:
        if verbose:
            print("  llm_commentary: anthropic SDK not installed - skipping")
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if verbose:
            print("  llm_commentary: ANTHROPIC_API_KEY not set - skipping")
        return

    hunter_qualified = [
        t for t in tickets
        if t.get("hunter") and t["hunter"].get("qualified")
    ]
    if not hunter_qualified:
        if verbose:
            print("  llm_commentary: no Hunter-qualified picks - skipping")
        return

    hunter_qualified.sort(key=lambda t: t["hunter"].get("score", 0), reverse=True)
    top = hunter_qualified[:top_n]

    client = anthropic.Anthropic()
    total_in = 0
    total_out = 0
    total_cached = 0
    errors = 0

    for t in top:
        result = commentary_one(client, t)
        if result.get("error"):
            errors += 1
            if verbose:
                print(f"  llm_commentary: {t.get('ticker')} failed: {result['error']}")
            continue
        t["llm_rating"] = result["rating"]
        t["llm_thesis"] = result["thesis"]
        t["llm_risk"] = result["risk"]
        total_in += result.get("input_tokens", 0)
        total_out += result.get("output_tokens", 0)
        total_cached += result.get("cache_read", 0)

    if verbose:
        cost_fresh = max(0, total_in - total_cached) * 3.0 / 1_000_000
        cost_cached = total_cached * 0.3 / 1_000_000
        cost_out = total_out * 15.0 / 1_000_000
        total_cost = cost_fresh + cost_cached + cost_out
        successes = len(top) - errors
        print(f"  llm_commentary: {successes}/{len(top)} picks. tokens in={total_in} cached={total_cached} out={total_out}. ~${total_cost:.3f}")

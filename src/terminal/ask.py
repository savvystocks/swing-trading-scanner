import json
import os

from src.terminal import data as D
from src.terminal import formatters as F


SYSTEM_PROMPT = """You are a data-grounded analyst answering questions about a retail option-trading scanner's output. Be concise, plain English, no hedging or marketing tone. If the data does not contain the answer, say so explicitly rather than guessing.

The user trades 1-2 week call options on US small/mid-caps from a $3-5k account. Answer in a way that helps them decide whether to take, hold, or skip trades."""


def _slim_pick(p):
    overall = p.get("_overall_score") or {}
    surv = p.get("_survival_score") or {}
    eq = p.get("_earnings_quality") or {}
    forensic = p.get("unified_forensic") or p.get("haiku_synthesis") or {}
    bear = p.get("bear_verification") or {}
    iv = p.get("iv_percentile_analysis") or {}
    cats_raw = p.get("catalysts") or []
    cats = []
    for c in cats_raw[:6]:
        if isinstance(c, dict):
            cats.append({"key": c.get("key"), "details": c.get("details", "")[:120]})
    return {
        "ticker": p.get("ticker"),
        "name": p.get("name"),
        "sector": p.get("sector"),
        "tier": p.get("_aa_tier"),
        "price": p.get("price"),
        "ret_5d": p.get("ret_5d"),
        "ret_30d": p.get("ret_30d"),
        "overall_score": overall.get("score"),
        "overall_verdict": overall.get("verdict"),
        "probability_of_profit": overall.get("probability_of_profit_pct"),
        "survival_score": surv.get("score"),
        "survival_verdict": surv.get("verdict"),
        "survival_kill_risks": surv.get("kill_risks"),
        "earnings_quality": eq.get("rating"),
        "iv_percentile": iv.get("iv_percentile"),
        "llm_verdict": forensic.get("verdict"),
        "llm_confidence": forensic.get("confidence_pct"),
        "bull_thesis": (forensic.get("bull_thesis") or "")[:300],
        "bear_killer": (bear.get("killer_thesis") or "")[:300],
        "bear_conviction": bear.get("bear_conviction_pct"),
        "is_trap": bear.get("is_this_trade_a_trap"),
        "catalysts": cats,
        "cat_count": p.get("_category_count"),
        "stacked_score": p.get("_stacked_score"),
    }


def _build_context(scan_date=None, max_picks=12):
    scan = D.load_scan(scan_date)
    if not scan:
        return {"error": "No scan loaded.", "scan_date": scan_date}
    picks = D.all_picks(scan)[:max_picks]
    slim_picks = [_slim_pick(p) for p in picks]
    macro = scan.get("macro") or {}
    macro_slim = {
        k: macro.get(k) for k in [
            "vix", "vix_5d_change_pct", "yield_10y_5d_change_bps", "dxy_5d_change_pct",
            "days_to_next_fomc", "days_to_next_cpi", "days_to_next_nfp", "days_to_next_opex",
            "near_term_calendar_risks", "correlation_regime",
        ] if macro.get(k) is not None
    }
    open_pos = D.open_positions() + D.live_open_positions()
    open_pos_slim = [
        {
            "ticker": p.get("ticker"),
            "contract": p.get("contract"),
            "size": p.get("size_contracts"),
            "entry_mid": p.get("entry_mid"),
            "current_mid": p.get("current_mid"),
            "pnl_pct": p.get("current_pnl_pct"),
            "pnl_usd": p.get("current_pnl_usd"),
            "opened_at": p.get("opened_at"),
        }
        for p in open_pos
    ]
    closed = D.closed_positions() + D.live_closed_positions()
    closed_slim = []
    for c in sorted(closed, key=lambda c: c.get("closed_at") or "", reverse=True)[:15]:
        closed_slim.append({
            "ticker": c.get("ticker"),
            "contract": c.get("contract"),
            "pnl_pct": c.get("realized_pnl_pct") or c.get("current_pnl_pct"),
            "pnl_usd": c.get("total_realized_pnl_usd") or c.get("current_pnl_usd"),
            "exit_reason": c.get("exit_reason"),
            "closed_at": c.get("closed_at"),
            "days_held": c.get("days_held"),
        })
    stats = D.aggregate_win_rate_stats(window_days=90)
    by_cat = D.win_rate_by_catalyst(window_days=90)
    return {
        "scan_date": scan.get("_scan_date_resolved") or scan.get("scan_date"),
        "macro": macro_slim,
        "picks": slim_picks,
        "open_positions": open_pos_slim,
        "recent_closed": closed_slim,
        "performance_90d": stats,
        "win_rate_by_catalyst_90d": dict(list(by_cat.items())[:20]),
    }


def ask_claude(question, scan_date=None, model="claude-haiku-4-5"):
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        return ("ANTHROPIC_API_KEY not set. Either export it in your shell or use the structured "
                "CLI commands (swing picks --filter, swing ticker, swing stats) which do not need an API key.")
    try:
        from anthropic import Anthropic
    except ImportError:
        return "Anthropic Python SDK not installed. Run: pip install anthropic"

    context = _build_context(scan_date=scan_date)
    context_json = json.dumps(context, default=str, indent=2)
    if len(context_json) > 60_000:
        context_json = context_json[:60_000] + "\n... [truncated for token budget]"

    user_msg = (
        f"Question:\n{question}\n\n"
        f"Use the JSON data below as the ONLY ground truth. If the data does not contain the "
        f"answer, say so plainly.\n\nDATA:\n{context_json}"
    )

    client = Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as e:
        return f"Anthropic API call failed: {type(e).__name__}: {e}"

    parts = []
    for block in resp.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts).strip() or "(no response text)"

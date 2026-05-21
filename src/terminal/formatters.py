try:
    from src.catalyst.humanize import humanize_catalyst_key, humanize_catalyst_list
except ImportError:
    def humanize_catalyst_key(k):
        return (k or "").replace("_", " ").strip()
    def humanize_catalyst_list(cats, max_items=4):
        out = []
        for c in (cats or [])[:max_items]:
            if isinstance(c, dict):
                k = c.get("key") or c.get("label") or ""
            else:
                k = str(c)
            if k:
                out.append(k.replace("_", " ").strip())
        return out


def pick_summary_row(p):
    overall = p.get("_overall_score") or {}
    survival = p.get("_survival_score") or {}
    forensic = p.get("unified_forensic") or p.get("haiku_synthesis") or {}
    return {
        "ticker": p.get("ticker", "?"),
        "name": (p.get("name") or "")[:30],
        "tier": p.get("_aa_tier", "?"),
        "sector": (p.get("sector") or "")[:20],
        "price": p.get("price"),
        "overall_score": overall.get("score"),
        "overall_verdict": overall.get("verdict"),
        "probability": overall.get("probability_of_profit_pct"),
        "stacked_score": p.get("_stacked_score") or p.get("score"),
        "cat_count": p.get("_category_count") or 0,
        "survival_score": survival.get("score"),
        "survival_verdict": survival.get("verdict"),
        "llm_verdict": forensic.get("verdict"),
        "llm_conf": forensic.get("confidence_pct"),
    }


def _contract_str(c):
    if c is None:
        return "—"
    if isinstance(c, str):
        return c
    if isinstance(c, dict):
        strike = c.get("strike")
        exp = c.get("expiration") or c.get("exp")
        right = (c.get("right") or "call")[0].upper()
        if strike is not None and exp:
            return f"${int(strike) if float(strike).is_integer() else strike}{right} {exp}"
        return str(c)
    return str(c)


def position_summary_row(p, live=False):
    return {
        "ticker": p.get("ticker", "?"),
        "contract": _contract_str(p.get("contract")),
        "size": p.get("size_contracts"),
        "entry_mid": p.get("entry_mid"),
        "current_mid": p.get("current_mid"),
        "spot_now": p.get("current_spot"),
        "entry_spot": p.get("opened_at_spot"),
        "pnl_usd": p.get("current_pnl_usd"),
        "pnl_pct": p.get("current_pnl_pct"),
        "opened_at": (p.get("opened_at") or "")[:10],
        "live": live,
    }


def closed_position_row(p, live=False):
    return {
        "ticker": p.get("ticker", "?"),
        "contract": _contract_str(p.get("contract")),
        "size": p.get("size_contracts"),
        "entry_mid": p.get("entry_mid"),
        "exit_mid": p.get("exit_mid"),
        "pnl_usd": p.get("total_realized_pnl_usd") or p.get("current_pnl_usd"),
        "pnl_pct": p.get("realized_pnl_pct") or p.get("current_pnl_pct"),
        "exit_reason": p.get("exit_reason"),
        "days_held": p.get("days_held"),
        "opened_at": (p.get("opened_at") or "")[:10],
        "closed_at": (p.get("closed_at") or "")[:10],
        "live": live,
    }


def pick_full_detail(p):
    overall = p.get("_overall_score") or {}
    survival = p.get("_survival_score") or {}
    vol_micro = p.get("_vol_microstructure") or {}
    eq = p.get("_earnings_quality") or {}
    forensic = p.get("unified_forensic") or {}
    haiku = p.get("haiku_synthesis") or {}
    bear = p.get("bear_verification") or {}
    pre_mortem = p.get("pre_mortem") or {}
    iv = p.get("iv_percentile_analysis") or {}
    catalysts_human = humanize_catalyst_list(p.get("catalysts") or [], max_items=10)
    return {
        "ticker": p.get("ticker"),
        "name": p.get("name"),
        "sector": p.get("sector"),
        "industry": p.get("industry"),
        "bracket": p.get("bracket"),
        "tier": p.get("_aa_tier"),
        "price": p.get("price"),
        "market_cap": p.get("market_cap"),
        "dollar_volume_20d": p.get("dollar_volume_20d"),
        "ret_5d": p.get("ret_5d"),
        "ret_30d": p.get("ret_30d"),
        "ret_90d": p.get("ret_90d"),
        "above_50dma": p.get("above_50dma"),
        "above_200dma": p.get("above_200dma"),
        "pct_above_50dma": p.get("pct_above_50dma"),
        "stacked_score": p.get("_stacked_score") or p.get("score"),
        "cat_count": p.get("_category_count"),
        "active_categories": p.get("_active_categories") or [],
        "catalysts_human": catalysts_human,
        "overall": overall,
        "survival": survival,
        "vol_micro": vol_micro,
        "earnings_quality": eq,
        "iv_percentile": iv.get("iv_percentile"),
        "llm_forensic": {
            "verdict": forensic.get("verdict") or haiku.get("verdict"),
            "confidence": forensic.get("confidence_pct") or haiku.get("confidence_pct"),
            "bull": forensic.get("bull_thesis") or haiku.get("bull_thesis"),
            "kills": forensic.get("what_kills_this_trade") or haiku.get("what_kills_this_trade"),
        },
        "bear": {
            "verdict": bear.get("bear_verdict"),
            "conviction": bear.get("bear_conviction_pct"),
            "killer": bear.get("killer_thesis"),
            "is_trap": bear.get("is_this_trade_a_trap"),
        },
        "pre_mortem": pre_mortem,
        "multi_leg": p.get("_multi_leg_suggestions") or [],
    }


def fmt_money(v):
    if v is None:
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 1_000_000_000:
        return f"${v/1e9:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1_000:
        return f"${v/1e3:.1f}k"
    if abs(v) >= 100:
        return f"${v:.0f}"
    return f"${v:.2f}"


def fmt_pct(v):
    if v is None:
        return "—"
    try:
        return f"{float(v):+.1f}%"
    except (TypeError, ValueError):
        return "—"


def fmt_int_or_dash(v):
    if v is None:
        return "—"
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return "—"


def fmt_score_or_dash(v):
    if v is None:
        return "—"
    try:
        return f"{int(round(float(v)))}"
    except (TypeError, ValueError):
        return "—"

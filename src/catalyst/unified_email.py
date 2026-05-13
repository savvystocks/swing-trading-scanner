from datetime import datetime
from jinja2 import Template


EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; background:#f6f7f9; margin:0; padding:18px; color:#1a1a1a; }
  .wrap { max-width:780px; margin:0 auto; background:#fff; padding:28px 32px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
  h1 { font-size:20px; margin:0 0 4px; font-weight:700; letter-spacing:-0.3px; }
  .header-meta { color:#666; font-size:12px; margin-bottom:24px; }
  .section-rule { border:0; height:1px; background:#e5e7eb; margin:28px 0 14px; }
  .section-label { font-size:11px; font-weight:700; letter-spacing:1.2px; color:#6b7280; text-transform:uppercase; margin-bottom:14px; }
  .pick { margin-bottom:24px; padding-bottom:20px; border-bottom:1px solid #f1f3f5; }
  .pick:last-child { border-bottom:0; }
  .pick-header { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
  .pick-rank { font-size:13px; font-weight:700; color:#9ca3af; min-width:28px; }
  .pick-ticker { font-size:18px; font-weight:800; color:#111; letter-spacing:-0.2px; }
  .pick-tier { font-size:10px; font-weight:800; padding:2px 8px; border-radius:3px; letter-spacing:0.5px; }
  .pick-tier.app { background:#065f46; color:#fff; }
  .pick-tier.ap { background:#15803d; color:#fff; }
  .pick-tier.a { background:#1d4ed8; color:#fff; }
  .pick-name { font-size:13px; color:#4b5563; flex:1; min-width:200px; }
  .pick-price { font-size:13px; font-weight:600; color:#111; }
  .pick-move-up { color:#15803d; font-weight:700; }
  .pick-move-down { color:#b91c1c; font-weight:700; }
  .pick-row { font-size:13px; line-height:1.6; margin:5px 0; padding-left:38px; }
  .pick-row-label { display:inline-block; min-width:62px; font-size:11px; font-weight:800; letter-spacing:0.6px; color:#6b7280; text-transform:uppercase; vertical-align:top; }
  .pick-row-trade { color:#111; font-weight:600; }
  .pick-row-odds { color:#111; }
  .pick-row-bet { color:#374151; }
  .table { width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }
  .table th { background:#f9fafb; padding:6px 10px; text-align:left; font-weight:700; color:#4b5563; font-size:11px; border-bottom:1px solid #e5e7eb; }
  .table td { padding:6px 10px; border-bottom:1px solid #f3f4f6; vertical-align:top; }
  .table td.tkr { font-weight:700; color:#111; }
  .subsection-label { font-size:12px; font-weight:700; color:#111; margin-bottom:4px; }
  .subsection-hint { font-size:11px; color:#6b7280; margin-bottom:8px; }
  .skip-table { width:100%; border-collapse:collapse; font-size:11px; }
  .skip-table td { padding:4px 8px; border-bottom:1px solid #f3f4f6; color:#4b5563; }
  .skip-table td.tkr { font-weight:700; color:#374151; min-width:60px; }
  .discipline { background:#f9fafb; padding:14px 18px; border-radius:6px; font-size:12px; line-height:1.7; color:#4b5563; }
  .discipline strong { color:#111; }
  .empty-state { text-align:center; padding:40px 20px; color:#6b7280; font-size:13px; }
  .footer { margin-top:28px; padding-top:14px; border-top:1px solid #e5e7eb; font-size:10px; color:#9ca3af; text-align:center; }
</style>
</head>
<body>
<div class="wrap">

  <h1>Micro · Small · Mid Setups</h1>
  <div class="header-meta">
    {{ scan_day_label }} · {{ picks|length }} BUY-rated · {{ filtered_out_count }} filtered out (HOLD/SKIP)
    {% if regime_label %}· {{ regime_label }} regime{% endif %}
  </div>
  <div class="header-meta" style="margin-top:-18px; margin-bottom:24px; font-size:11px;">
    A++ {{ a_pp_count }} · A+ {{ a_p_count }} · A {{ a_count }} total tier output · {{ pre_earnings_count }} pre-earnings setups
  </div>

  {% if picks %}
  <hr class="section-rule">
  <div class="section-label">The Picks</div>

  {% for p in picks %}
  <div class="pick">
    <div class="pick-header">
      <span class="pick-rank">#{{ loop.index }}</span>
      <span class="pick-ticker">{{ p.ticker }}</span>
      <span class="pick-tier {{ p.tier_class }}">{{ p.tier }}</span>
      <span class="pick-name">{{ p.name }} · {{ p.sector }} {{ p.bracket }}</span>
      <span class="pick-price">${{ p.price_fmt }}{% if p.move_pct_fmt %} <span class="{{ p.move_class }}">{{ p.move_pct_fmt }}</span>{% endif %}</span>
    </div>
    <div class="pick-row"><span class="pick-row-label">Trade</span><span class="pick-row-trade">{{ p.trade_line }}</span></div>
    <div class="pick-row"><span class="pick-row-label">Odds</span><span class="pick-row-odds">{{ p.odds_line }}</span></div>
    <div class="pick-row"><span class="pick-row-label">Bet</span><span class="pick-row-bet">{{ p.bet_line }}</span></div>
  </div>
  {% endfor %}
  {% else %}
  <div class="empty-state"><strong>No BUY-rated picks today.</strong><br>{{ filtered_out_count }} candidate(s) graded HOLD or SKIP by the LLM forensic — nothing met the buy bar. Sit out.</div>
  {% endif %}

  {% if pre_earnings_lead_up or pre_earnings_imminent %}
  <hr class="section-rule">
  <div class="section-label">Pre-Earnings Window · {{ pre_earnings_count }} setups for 20-50% in a week</div>

  {% if pre_earnings_lead_up %}
  <div class="subsection-label">10-15 days out — institutional positioning sweet spot</div>
  <div class="subsection-hint">Entry zone where IV is still cheap and the run-up typically starts. Hold until 1-3d before the print.</div>
  <table class="table">
    <tr><th>Ticker</th><th>Spot</th><th>Earnings</th><th>Stacked Catalysts</th></tr>
    {% for s in pre_earnings_lead_up %}
    <tr>
      <td class="tkr">{{ s.ticker }}</td>
      <td>${{ s.price_fmt }}</td>
      <td>{{ s.report_date }} ({{ s.days_until }}d)</td>
      <td>{{ s.catalysts_joined }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}

  {% if pre_earnings_imminent %}
  <div class="subsection-label" style="margin-top:18px;">5-9 days out — IV expansion zone</div>
  <div class="subsection-hint">Late but still actionable. Premium higher, exit 1-2d before the print to avoid IV crush.</div>
  <table class="table">
    <tr><th>Ticker</th><th>Spot</th><th>Earnings</th><th>Stacked Catalysts</th></tr>
    {% for s in pre_earnings_imminent %}
    <tr>
      <td class="tkr">{{ s.ticker }}</td>
      <td>${{ s.price_fmt }}</td>
      <td>{{ s.report_date }} ({{ s.days_until }}d)</td>
      <td>{{ s.catalysts_joined }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}
  {% endif %}

  {% if skip_list %}
  <hr class="section-rule">
  <div class="section-label">Skip List · Top {{ skip_list|length }} Rejected</div>
  <table class="skip-table">
    {% for s in skip_list %}
    <tr><td class="tkr">{{ s.ticker }}</td><td>{{ s.reason }}</td></tr>
    {% endfor %}
  </table>
  {% endif %}

  <hr class="section-rule">
  <div class="section-label">Discipline</div>
  <div class="discipline">
    Vol regime: <strong>{{ regime_label or 'NORMAL' }}</strong> · position size × {{ position_mult }}<br>
    Win rate (30d): <strong>{{ win_rate_pct }}%</strong> on {{ win_rate_n }} paper trades<br>
    Open positions: <strong>{{ open_slots }} of {{ max_slots }} slots</strong>
  </div>

  <div class="footer">v4 scanner · {{ scan_date }} · catalyst stack engine · auto-generated</div>
</div>
</body>
</html>
"""


def _move_class(pct):
    if pct is None:
        return ""
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return "pick-move-up"
    if v < 0:
        return "pick-move-down"
    return ""


def _fmt_pct(pct):
    if pct is None:
        return ""
    try:
        return f"{float(pct):+.1f}%"
    except (TypeError, ValueError):
        return ""


def _fmt_price(p):
    if p is None:
        return "?"
    try:
        v = float(p)
    except (TypeError, ValueError):
        return "?"
    if v >= 100:
        return f"{v:,.2f}"
    return f"{v:.2f}"


def _tier_class(tier):
    return {"A++": "app", "A+": "ap", "A": "a"}.get(tier, "a")


def _build_trade_line(pick):
    trade = pick.get("trade_ticket") or {}
    if trade and trade.get("option_action"):
        action = trade.get("option_action", "BUY")
        n = trade.get("option_contracts", 1)
        exp = trade.get("option_expiry", "")
        strike = trade.get("option_strike", "")
        side = trade.get("option_side", "C")
        mid = trade.get("option_mid_price")
        target = trade.get("option_target")
        stop = trade.get("option_stop")
        line = f"{action} {n}x {pick.get('ticker')} {exp} ${strike}{side} @ ${mid}"
        if target:
            line += f" · target ${target}"
        if stop:
            line += f" · stop ${stop}"
        return line

    price = pick.get("live_spot") or pick.get("price")
    if not price:
        return "Trade ticket unavailable"
    try:
        price = float(price)
    except (TypeError, ValueError):
        return "Trade ticket unavailable"

    atr_pct = pick.get("atr_pct") or 3.5
    try:
        atr_pct = float(atr_pct)
    except (TypeError, ValueError):
        atr_pct = 3.5

    target = price * 1.085
    stop = price * (1 - atr_pct / 100.0)
    strike = round(price * 1.05 / 0.5) * 0.5
    return (
        f"Buy {pick.get('ticker')} stock at ~${_fmt_price(price)} · "
        f"target ${_fmt_price(target)} (+8.5%) · "
        f"stop ${_fmt_price(stop)} (-{atr_pct:.1f}%) · "
        f"or call ~${_fmt_price(strike)} strike 30-45d expiry"
    )


def _build_odds_line(pick):
    forensic = pick.get("unified_forensic") or {}
    haiku = pick.get("haiku_synthesis") or {}
    conf = forensic.get("confidence_pct") or haiku.get("confidence_pct")
    verdict = forensic.get("verdict") or haiku.get("verdict")

    if conf and verdict:
        return f"{conf}% probability of profit · {verdict} (LLM forensic)"

    score = pick.get("_stacked_score") or pick.get("score") or 0
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0
    if score >= 300:
        prob = 70
    elif score >= 200:
        prob = 60
    elif score >= 150:
        prob = 55
    elif score >= 100:
        prob = 50
    else:
        prob = 45
    return f"~{prob}% probability of profit · derived from stacked score {score:.0f} (no LLM forensic available)"


def _build_bet_line(pick):
    forensic = pick.get("unified_forensic") or {}
    haiku = pick.get("haiku_synthesis") or {}
    bull_case = (
        forensic.get("bull_thesis")
        or forensic.get("research_note")
        or haiku.get("bull_thesis")
        or haiku.get("synthesis_note")
    )
    if bull_case:
        risk = forensic.get("what_kills_this_trade") or haiku.get("what_kills_this_trade")
        out = str(bull_case)[:380]
        if risk:
            out += f" Risk: {str(risk)[:120]}."
        return out

    cats = pick.get("catalysts") or []
    cat_labels = []
    for c in cats[:3]:
        if isinstance(c, dict):
            label = c.get("label") or c.get("key", "")
            cat_labels.append(label)
    cat_text = " · ".join(cat_labels) if cat_labels else "no specific catalyst label"
    active = pick.get("_active_categories") or []
    cat_count = pick.get("_category_count") or len(cats)
    score = pick.get("_stacked_score") or pick.get("score") or 0

    pre_mortem = pick.get("pre_mortem") or {}
    risk = pre_mortem.get("most_likely_failure")
    if not risk:
        warnings = pre_mortem.get("warning_signs")
        if isinstance(warnings, list) and warnings:
            risk = warnings[0]

    parts = []
    parts.append(f"Stacked {cat_count} dimensions ({', '.join(active[:5])}).")
    parts.append(f"Drivers: {cat_text}.")
    if risk:
        risk_str = str(risk)[:120]
        parts.append(f"Main risk: {risk_str}.")
    return " ".join(parts)


def _build_pick(pick, rank):
    tier = pick.get("_aa_tier", "A")
    price_raw = pick.get("live_spot") or pick.get("price")
    move_pct = pick.get("today_pct_change") or pick.get("intraday_pct_change")
    return {
        "rank": rank,
        "ticker": pick.get("ticker", "?"),
        "name": (pick.get("name") or "")[:40],
        "sector": (pick.get("sector") or "")[:18],
        "bracket": pick.get("bracket", "?"),
        "tier": tier,
        "tier_class": _tier_class(tier),
        "price_fmt": _fmt_price(price_raw),
        "move_pct": move_pct,
        "move_pct_fmt": _fmt_pct(move_pct),
        "move_class": _move_class(move_pct),
        "trade_line": _build_trade_line(pick),
        "odds_line": _build_odds_line(pick),
        "bet_line": _build_bet_line(pick),
    }


def _build_pre_earnings_row(pick):
    cats = pick.get("catalysts") or []
    visible_cats = []
    earn_cat = None
    for c in cats:
        if not isinstance(c, dict):
            continue
        k = c.get("key", "")
        if k in ("earnings_lead_up_10_15d", "earnings_imminent_5_9d", "earnings_peak_iv_3_4d"):
            if earn_cat is None:
                earn_cat = c
            continue
        if k:
            visible_cats.append(k)
        if len(visible_cats) >= 4:
            break

    days_until = (earn_cat or {}).get("days_until")
    report_date = (earn_cat or {}).get("report_date")
    return {
        "ticker": pick.get("ticker", "?"),
        "price_fmt": _fmt_price(pick.get("live_spot") or pick.get("price")),
        "report_date": report_date or "?",
        "days_until": days_until if days_until is not None else 99,
        "catalysts_joined": " + ".join(visible_cats) if visible_cats else "?",
    }


def render_unified_email(scan, aa_results, aa_picks, aa_rejections, regime_info=None, execution_ctx=None):
    scan_date = scan.get("scan_date") or datetime.utcnow().date().isoformat()
    try:
        scan_day_label = datetime.strptime(scan_date, "%Y-%m-%d").strftime("%A %d %B %Y")
    except Exception:
        scan_day_label = scan_date

    a_pp_count = len(aa_results.get("A++", []))
    a_p_count = len(aa_results.get("A+", []))
    a_count = len(aa_results.get("A", []))

    all_tier_picks = []
    for tier in ("A++", "A+", "A"):
        all_tier_picks.extend(aa_results.get(tier, []))
    all_tier_picks.sort(key=lambda p: (-({"A++": 3, "A+": 2, "A": 1}.get(p.get("_aa_tier"), 0)), -(p.get("_stacked_score") or p.get("score") or 0)))

    def _is_buy_signal(pick):
        forensic = pick.get("unified_forensic") or {}
        haiku = pick.get("haiku_synthesis") or {}
        deep = pick.get("deep_research") or {}
        verdict = forensic.get("verdict") or haiku.get("verdict") or deep.get("verdict")
        if verdict is None:
            return pick.get("_aa_tier") in ("A++", "A+")
        return verdict in ("BUY", "STRONG_BUY")

    def _sector_bucket(sec):
        s = (sec or "").lower()
        if "tech" in s or "communication" in s or "information" in s:
            return "Technology"
        if "health" in s or "pharma" in s or "biotech" in s:
            return "Healthcare"
        if "industrial" in s or "aerospace" in s or "defense" in s:
            return "Industrials"
        if "financial" in s or "bank" in s or "insurance" in s:
            return "Financials"
        if "consumer" in s or "retail" in s or "restaurant" in s:
            return "Consumer"
        if "energy" in s or "oil" in s or "gas" in s:
            return "Energy"
        if "material" in s or "metal" in s or "mining" in s:
            return "Materials"
        return "Other"

    SECTOR_CAPS = {
        "Technology": 3,
        "Healthcare": 2,
        "Industrials": 2,
        "Financials": 2,
        "Consumer": 2,
        "Energy": 1,
        "Materials": 1,
        "Other": 1,
    }

    buy_picks = [p for p in all_tier_picks if _is_buy_signal(p)]
    buy_picks.sort(key=lambda p: -((p.get("unified_forensic") or {}).get("confidence_pct") or (p.get("haiku_synthesis") or {}).get("confidence_pct") or 50))

    picked = []
    sector_counts = {}
    for p in buy_picks:
        bucket = _sector_bucket(p.get("sector"))
        cap = SECTOR_CAPS.get(bucket, 1)
        if sector_counts.get(bucket, 0) >= cap:
            continue
        picked.append(p)
        sector_counts[bucket] = sector_counts.get(bucket, 0) + 1
        if len(picked) >= 5:
            break

    top_picks = picked
    picks_out = [_build_pick(p, i + 1) for i, p in enumerate(top_picks)]

    filtered_out_count = len(all_tier_picks) - len(buy_picks)

    pre_earnings_lead_up = []
    pre_earnings_imminent = []
    seen_tickers = set()
    for p in all_tier_picks:
        t = p.get("ticker")
        if t in seen_tickers:
            continue
        cats = p.get("catalysts") or []
        for c in cats:
            if not isinstance(c, dict):
                continue
            k = c.get("key", "")
            if k == "earnings_lead_up_10_15d":
                pre_earnings_lead_up.append(_build_pre_earnings_row(p))
                seen_tickers.add(t)
                break
            if k in ("earnings_imminent_5_9d", "earnings_peak_iv_3_4d"):
                pre_earnings_imminent.append(_build_pre_earnings_row(p))
                seen_tickers.add(t)
                break
    pre_earnings_lead_up.sort(key=lambda r: r["days_until"])
    pre_earnings_imminent.sort(key=lambda r: r["days_until"])
    pre_earnings_count = len(pre_earnings_lead_up) + len(pre_earnings_imminent)

    skip_list = []
    for r in (aa_rejections or [])[:15]:
        reason = r.get("reason", "")
        lower = reason.lower()
        if "extension" in lower:
            short_reason = "extension RED — already chased"
        elif "landmine" in lower:
            short_reason = "landmine — " + reason.split(":")[-1].strip()[:60]
        elif "sector" in lower:
            short_reason = "sector headwind too strong"
        elif "iv percentile" in lower:
            short_reason = "IV too high — premium over-priced"
        elif "stacked" in lower or "categories" in lower:
            short_reason = reason[:80]
        elif "smart money" in lower:
            short_reason = "no smart-money signal"
        else:
            short_reason = reason[:80]
        skip_list.append({"ticker": r.get("ticker", "?"), "reason": short_reason})

    regime_label = (regime_info or {}).get("regime", "NORMAL")
    position_mult = (regime_info or {}).get("position_multiplier", 1.0)
    win_rate_stats = scan.get("win_rate_stats") or {}
    portfolio = scan.get("portfolio_summary") or {}

    template = Template(EMAIL_TEMPLATE)
    return template.render(
        scan_date=scan_date,
        scan_day_label=scan_day_label,
        a_pp_count=a_pp_count,
        a_p_count=a_p_count,
        a_count=a_count,
        regime_label=regime_label,
        position_mult=position_mult,
        win_rate_pct=win_rate_stats.get("win_rate_pct", "n/a"),
        win_rate_n=win_rate_stats.get("n", "?"),
        open_slots=portfolio.get("n_open", "?"),
        max_slots=portfolio.get("max_concurrent", "?"),
        picks=picks_out,
        pre_earnings_lead_up=pre_earnings_lead_up,
        pre_earnings_imminent=pre_earnings_imminent,
        pre_earnings_count=pre_earnings_count,
        skip_list=skip_list,
        filtered_out_count=filtered_out_count,
    )

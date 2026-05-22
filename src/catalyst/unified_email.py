from datetime import datetime
from jinja2 import Template

try:
    from src.catalyst.live_option_picker import find_best_call, project_outcomes, build_trade_line, build_kelly_line
    LIVE_OPTIONS_AVAILABLE = True
except ImportError:
    LIVE_OPTIONS_AVAILABLE = False

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

import os


def _safe_float_env(key, default):
    raw = os.environ.get(key, "")
    if isinstance(raw, str):
        raw = raw.strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


ACCOUNT_SIZE_USD = _safe_float_env("ACCOUNT_SIZE_USD", 4300)


EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; background:#f6f7f9; margin:0; padding:18px; color:#1a1a1a; }
  .wrap { max-width:820px; margin:0 auto; background:#fff; padding:28px 32px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
  h1 { font-size:22px; margin:0 0 4px; font-weight:700; letter-spacing:-0.3px; }
  .header-meta { color:#666; font-size:12px; margin-bottom:24px; }
  .section-rule { border:0; height:1px; background:#e5e7eb; margin:28px 0 14px; }
  .section-label { font-size:11px; font-weight:700; letter-spacing:1.2px; color:#6b7280; text-transform:uppercase; margin-bottom:14px; }

  .pick { margin-bottom:30px; padding:18px 20px 20px; border:1px solid #e5e7eb; border-radius:10px; background:#fcfcfd; }
  .pick-header { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:12px; }
  .pick-rank { font-size:13px; font-weight:700; color:#9ca3af; }
  .pick-ticker { font-size:22px; font-weight:800; color:#111; letter-spacing:-0.3px; }
  .pick-name { font-size:12px; color:#4b5563; flex:1; min-width:160px; }
  .pick-price { font-size:14px; font-weight:700; color:#111; }
  .pick-move-up { color:#15803d; font-weight:700; }
  .pick-move-down { color:#b91c1c; font-weight:700; }

  .overall-score-box { display:flex; align-items:center; gap:14px; margin:8px 0 16px; padding:14px 18px; border-radius:10px; border:2px solid; }
  .overall-score-box.overall-strong { background:#ecfdf5; border-color:#065f46; }
  .overall-score-box.overall-good { background:#f0fdf4; border-color:#15803d; }
  .overall-score-box.overall-borderline { background:#fefce8; border-color:#a16207; }
  .overall-score-box.overall-watch { background:#f9fafb; border-color:#6b7280; }
  .overall-score-box.overall-avoid { background:#fef2f2; border-color:#b91c1c; }
  .score-circle { font-size:32px; font-weight:800; min-width:64px; text-align:center; }
  .overall-strong .score-circle { color:#065f46; }
  .overall-good .score-circle { color:#15803d; }
  .overall-borderline .score-circle { color:#a16207; }
  .overall-watch .score-circle { color:#6b7280; }
  .overall-avoid .score-circle { color:#b91c1c; }
  .score-info { flex:1; }
  .score-verdict { font-size:16px; font-weight:800; margin-bottom:2px; }
  .overall-strong .score-verdict { color:#065f46; }
  .overall-good .score-verdict { color:#15803d; }
  .overall-borderline .score-verdict { color:#a16207; }
  .overall-watch .score-verdict { color:#6b7280; }
  .overall-avoid .score-verdict { color:#b91c1c; }
  .score-plain { font-size:12px; color:#374151; line-height:1.5; }

  .key-numbers { display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 14px; }
  .key-num { flex:1; min-width:130px; padding:10px 12px; background:#fff; border:1px solid #e5e7eb; border-radius:8px; }
  .key-num-label { font-size:10px; font-weight:700; color:#6b7280; letter-spacing:0.5px; text-transform:uppercase; margin-bottom:3px; }
  .key-num-value { font-size:18px; font-weight:800; color:#111; }
  .key-num-value.win { color:#15803d; }
  .key-num-value.lose { color:#b91c1c; }

  .trade-block { margin:10px 0 12px; padding:14px 16px; background:#eff6ff; border-left:4px solid #2563eb; border-radius:6px; }
  .trade-block-label { font-size:11px; font-weight:800; letter-spacing:0.8px; color:#1d4ed8; text-transform:uppercase; margin-bottom:4px; }
  .trade-block-text { font-size:14px; font-weight:700; color:#111; line-height:1.5; }
  .trade-block-detail { font-size:12px; color:#4b5563; margin-top:6px; line-height:1.5; }

  .why-block, .risks-block, .catalysts-block { margin:10px 0; }
  .why-block { padding:10px 14px; background:#ecfdf5; border-left:3px solid #15803d; border-radius:5px; font-size:13px; color:#065f46; line-height:1.55; }
  .risks-block { padding:10px 14px; background:#fef2f2; border-left:3px solid #b91c1c; border-radius:5px; font-size:12px; color:#7f1d1d; line-height:1.55; }
  .catalysts-block { padding:8px 14px; background:#f9fafb; border-left:3px solid #6b7280; border-radius:5px; font-size:13px; color:#374151; line-height:1.55; }
  .catalysts-block strong, .why-block strong, .risks-block strong { font-weight:800; display:block; margin-bottom:4px; font-size:11px; letter-spacing:0.5px; text-transform:uppercase; }
  .catalysts-list { list-style:none; padding-left:0; margin:0; }
  .catalysts-list li { padding:2px 0; }

  .grade-pill { display:inline-block; padding:2px 7px; border-radius:3px; font-size:10px; font-weight:800; letter-spacing:0.4px; }
  .grade-pill.highest { background:#065f46; color:#fff; }
  .grade-pill.high { background:#15803d; color:#fff; }
  .grade-pill.med { background:#ca8a04; color:#fff; }
  .grade-pill.low { background:#9ca3af; color:#fff; }

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

  <h1>Today's Top Trades</h1>
  <div class="header-meta">
    {{ scan_day_label }} · {{ picks|length }} picks selected from {{ filtered_out_count + picks|length }} candidates
    {% if regime_label %}· Market mood: {{ regime_label }}{% endif %}
  </div>

  {% if picks %}
  <hr class="section-rule">
  <div class="section-label">The Picks</div>

  {% for p in picks %}
  <div class="pick">
    <div class="pick-header">
      <span class="pick-rank">#{{ loop.index }}</span>
      <span class="pick-ticker">{{ p.ticker }}</span>
      <span class="pick-name">{{ p.name }}{% if p.sector %} · {{ p.sector }}{% endif %}</span>
      <span class="pick-price">${{ p.price_fmt }}{% if p.move_pct_fmt %} <span class="{{ p.move_class }}">{{ p.move_pct_fmt }}</span>{% endif %}</span>
    </div>

    <div class="overall-score-box {{ p.overall.verdict_class }}">
      <div class="score-circle">{{ p.overall.score }}</div>
      <div class="score-info">
        <div class="score-verdict">{{ p.overall.verdict }}</div>
        <div class="score-plain">{{ p.overall.plain_english }}</div>
      </div>
    </div>

    <div class="key-numbers">
      <div class="key-num">
        <div class="key-num-label">Chance of profit</div>
        <div class="key-num-value {% if p.overall.probability_of_profit_pct >= 55 %}win{% elif p.overall.probability_of_profit_pct < 40 %}lose{% endif %}">{{ p.overall.probability_of_profit_pct }}%</div>
      </div>
      <div class="key-num">
        <div class="key-num-label">{{ p.target_label }}</div>
        <div class="key-num-value {% if p.target_return_pct is not none and p.target_return_pct >= 30 %}win{% elif p.target_return_pct is not none and p.target_return_pct < 0 %}lose{% endif %}">{% if p.target_return_pct is none %}n/a{% elif p.target_return_pct > 0 %}+{{ p.target_return_pct }}%{% else %}{{ p.target_return_pct }}%{% endif %}</div>
      </div>
      <div class="key-num">
        <div class="key-num-label">Cost per contract</div>
        <div class="key-num-value">{% if p.contract_cost %}${{ p.contract_cost }}{% else %}n/a{% endif %}</div>
      </div>
      <div class="key-num">
        <div class="key-num-label">Size suggestion</div>
        <div class="key-num-value">{% if p.size_contracts %}{{ p.size_contracts }} contract{% if p.size_contracts > 1 %}s{% endif %}{% else %}n/a{% endif %}</div>
      </div>
    </div>

    <div class="trade-block">
      <div class="trade-block-label">The trade</div>
      <div class="trade-block-text">{{ p.trade_line }}</div>
      {% if p.trade_detail %}
      <div class="trade-block-detail">{{ p.trade_detail }}</div>
      {% endif %}
    </div>

    {% if p.why %}
    <div class="why-block">
      <strong>Why this trade</strong>
      {{ p.why }}
    </div>
    {% endif %}

    {% if p.catalyst_lines %}
    <div class="catalysts-block">
      <strong>What's driving the move</strong>
      <ul class="catalysts-list">
        {% for cat in p.catalyst_lines %}
        <li>· {{ cat }}</li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    {% if p.risks %}
    <div class="risks-block">
      <strong>What could go wrong</strong>
      {% for r in p.risks %}
      <div>· {{ r }}</div>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  {% endfor %}
  {% else %}
  <div class="empty-state"><strong>No buy-rated picks today.</strong><br>{{ filtered_out_count }} candidates were graded HOLD or SKIP by the AI forensic - nothing cleared the bar. Sit out.</div>
  {% endif %}

  {% if pre_earnings_lead_up or pre_earnings_imminent %}
  <hr class="section-rule">
  <div class="section-label">Pre-Earnings Window · {{ pre_earnings_count }} setups for 20-50% in a week</div>

  {% if pre_earnings_lead_up %}
  <div class="subsection-label">10-15 days out — institutional positioning sweet spot</div>
  <div class="subsection-hint">Entry zone where IV is still cheap and the run-up typically starts. Hold until 1-3d before the print.</div>
  <table class="table">
    <tr><th>Ticker</th><th>Spot</th><th>Earnings</th><th>Quality</th><th>Score</th><th>Stacked Catalysts</th></tr>
    {% for s in pre_earnings_lead_up %}
    <tr>
      <td class="tkr">{{ s.ticker }}</td>
      <td>${{ s.price_fmt }}</td>
      <td>{{ s.report_date }} ({{ s.days_until }}d)</td>
      <td><span class="grade-pill {{ s.grade_class }}">{{ s.grade }}</span> {{ s.tier }}</td>
      <td>{{ s.score }} · {{ s.cat_count }} cats</td>
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
    ticker = pick.get("ticker")
    price = pick.get("live_spot") or pick.get("price")
    if price:
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = None

    if LIVE_OPTIONS_AVAILABLE and price and ticker:
        try:
            option = find_best_call(ticker, price)
            if option:
                line = build_trade_line(ticker, price, option)
                pick["_live_option"] = option
                return line
        except Exception:
            pass

    if not price:
        return "Trade ticket unavailable (no live price, no option chain)"

    atr_pct = pick.get("atr_pct") or 3.5
    try:
        atr_pct = float(atr_pct)
    except (TypeError, ValueError):
        atr_pct = 3.5

    target = price * 1.085
    stop = price * (1 - atr_pct / 100.0)
    return (
        f"Buy {ticker} stock at roughly ${_fmt_price(price)}, "
        f"target ${_fmt_price(target)} (about +8.5%), "
        f"stop ${_fmt_price(stop)} (about -{atr_pct:.1f}%). "
        f"Option chain too thin for a clean contract."
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


def _detect_catalyst_flags(pick):
    cats = pick.get("catalysts") or []
    earnings_imminent_keys = {"earnings_imminent_5_9d", "earnings_peak_iv_3_4d", "earnings_amc_today", "earnings_bmo_tomorrow"}
    earnings_lead_up_keys = {"earnings_lead_up_10_15d"}
    general_catalyst_keys = {
        "clinical_milestone", "fda_event", "merger", "definitive_agreement",
        "ai_deal_announcement", "semis_capex_signal", "defense_contract_award",
        "activist_stake", "13d", "13d_a", "strategic_partnership", "contract_win",
        "post_earnings_beat", "bank_post_earnings_drift",
    }
    has_imminent = False
    has_lead_up = False
    has_general = False
    for c in cats:
        if not isinstance(c, dict):
            continue
        k = c.get("key", "")
        if k in earnings_imminent_keys:
            has_imminent = True
        elif k in earnings_lead_up_keys:
            has_lead_up = True
        elif k in general_catalyst_keys:
            has_general = True
    return has_imminent, has_lead_up, has_general


def _build_why_text(pick):
    forensic = pick.get("unified_forensic") or {}
    haiku = pick.get("haiku_synthesis") or {}
    bull = forensic.get("bull_thesis") or haiku.get("bull_thesis") or forensic.get("research_note") or haiku.get("synthesis_note")
    if bull:
        return str(bull)[:380]
    cats = pick.get("catalysts") or []
    human = humanize_catalyst_list(cats, max_items=3)
    if human:
        return "Catalyst stack: " + " · ".join(human) + "."
    return ""


def _build_risks(pick):
    out = []
    bear_v = pick.get("bear_verification") or {}
    killer = bear_v.get("killer_thesis")
    is_trap = bear_v.get("is_this_trade_a_trap")
    if killer:
        if is_trap:
            out.append("TRAP FLAGGED: " + str(killer)[:200])
        else:
            out.append("Bear case: " + str(killer)[:200])

    survival = pick.get("_survival_score") or {}
    for kr in (survival.get("kill_risks") or [])[:2]:
        if ":" in kr:
            cat, rest = kr.split(":", 1)
            humanised = _humanize_kill_risk(cat.strip(), rest.strip())
            out.append(humanised)
        else:
            out.append(kr)

    if not out:
        pre_mortem = pick.get("pre_mortem") or {}
        risk = pre_mortem.get("most_likely_failure")
        if risk:
            out.append(str(risk)[:200])
    return out[:3]


def _humanize_kill_risk(category, note):
    cat_map = {
        "Calendar": "Macro calendar",
        "Vol regime": "Market volatility",
        "Sector": "Sector backdrop",
        "Credit/rates": "Rates/credit backdrop",
        "News": "News sentiment",
        "Company": "Company-level risk",
        "Exhaustion": "Already extended",
        "Positioning": "Options positioning",
    }
    label = cat_map.get(category, category)
    return f"{label}: {note}"


def _build_pick(pick, rank):
    tier = pick.get("_aa_tier", "A")
    price_raw = pick.get("live_spot") or pick.get("price")
    move_pct = pick.get("today_pct_change") or pick.get("intraday_pct_change")

    trade_line = _build_trade_line(pick)
    live_option = pick.get("_live_option")
    outcomes = []
    iv_crush_note = None
    if live_option and price_raw:
        try:
            has_imminent, has_lead_up, has_general = _detect_catalyst_flags(pick)
            outcomes, crush_info = project_outcomes(
                live_option,
                float(price_raw),
                has_earnings_imminent=has_imminent,
                has_earnings_lead_up=has_lead_up,
                has_general_catalyst=has_general,
            )
            iv_crush_note = crush_info.get("scenario_label")
            iv_pts = crush_info.get("iv_change_pts")
            iv_dollar = crush_info.get("iv_dollar_impact")
            if iv_pts is not None and iv_pts < 0:
                iv_crush_note = (
                    f"IV crush built-in: {iv_pts:.0f} vol points · "
                    f"~${iv_dollar:.2f}/contract drag · {iv_crush_note}"
                )
        except Exception:
            outcomes = []

    kelly_line = None
    if outcomes and live_option:
        try:
            forensic = pick.get("unified_forensic") or {}
            haiku = pick.get("haiku_synthesis") or {}
            win_prob = forensic.get("confidence_pct") or haiku.get("confidence_pct")
            if win_prob:
                kelly_line = build_kelly_line(
                    win_prob_pct=float(win_prob),
                    outcomes=outcomes,
                    option_mid=live_option.get("mid"),
                    account_size_usd=ACCOUNT_SIZE_USD,
                )
        except Exception:
            kelly_line = None

    forensic = pick.get("unified_forensic") or {}
    haiku = pick.get("haiku_synthesis") or {}
    bear_v = pick.get("bear_verification") or {}

    bull_conf = forensic.get("confidence_pct") or haiku.get("confidence_pct") or 0
    bull_verdict = forensic.get("verdict") or haiku.get("verdict") or "UNKNOWN"
    bull_thesis = forensic.get("bull_thesis") or haiku.get("bull_thesis") or ""

    bear_conv = bear_v.get("bear_conviction_pct") or 0
    bear_verdict = bear_v.get("bear_verdict") or "NOT_TESTED"
    killer = bear_v.get("killer_thesis") or ""
    is_trap = bear_v.get("is_this_trade_a_trap") or False

    net_edge = bull_conf - bear_conv if bull_conf else None
    if is_trap:
        final_rating = "SKIP - TRAP"
        rating_class = "rating-skip"
        stars = 1
    elif net_edge is None:
        final_rating = "NO LLM REVIEW"
        rating_class = "rating-neutral"
        stars = 2
    elif bull_verdict == "SKIP":
        final_rating = "SKIP"
        rating_class = "rating-skip"
        stars = 1
    elif bull_verdict == "HOLD":
        final_rating = "HOLD"
        rating_class = "rating-hold"
        stars = 2
    elif bull_verdict in ("BUY", "STRONG_BUY"):
        if net_edge >= 40:
            final_rating = "STRONG BUY"
            rating_class = "rating-strong"
            stars = 5
        elif net_edge >= 25:
            final_rating = "BUY"
            rating_class = "rating-buy"
            stars = 4
        elif net_edge >= 10:
            final_rating = "WEAK BUY"
            rating_class = "rating-weak"
            stars = 3
        elif net_edge >= -10:
            final_rating = "HOLD"
            rating_class = "rating-hold"
            stars = 2
        else:
            final_rating = "SKIP"
            rating_class = "rating-skip"
            stars = 1
    else:
        final_rating = "NO LLM REVIEW"
        rating_class = "rating-neutral"
        stars = 2

    star_display = "*" * stars + "-" * (5 - stars)
    rating_summary = {
        "final_rating": final_rating,
        "rating_class": rating_class,
        "stars": stars,
        "star_display": star_display,
        "net_edge": net_edge,
        "bull_conf": int(bull_conf) if bull_conf else None,
        "bear_conv": int(bear_conv) if bear_conv else None,
        "bull_verdict": bull_verdict,
        "bear_verdict": bear_verdict,
        "bull_thesis": bull_thesis[:400] if bull_thesis else "",
        "killer_thesis": killer[:300] if killer else "",
        "is_trap": is_trap,
    }

    bear_note = None
    if bear_v:
        if is_trap or (bear_conv and bear_conv >= 50):
            bear_note = f"Bear case ({bear_verdict}, {bear_conv}% conviction): {killer[:200]}"
        elif bear_conv:
            bear_note = f"Bear case stress-tested: {bear_verdict} ({bear_conv}% conviction) - BULL THESIS HOLDS"

    overall = pick.get("_overall_score") or {}
    if not overall:
        try:
            from src.catalyst.overall_score import compute_overall_score
            overall = compute_overall_score(pick)
        except Exception:
            overall = {
                "score": 50,
                "verdict": "BORDERLINE",
                "verdict_class": "overall-borderline",
                "plain_english": "Score unavailable - mixed signals.",
                "probability_of_profit_pct": 50,
                "components": {},
            }

    target_return_pct = None
    target_label = "If stock moves +8%"
    contract_cost = None
    size_contracts = None
    trade_detail = None
    if live_option:
        contract_cost = int(round(live_option.get("mid", 0) * 100))
        target_8 = None
        for o in outcomes:
            if o.get("underlying_pct") == 8:
                target_8 = o
                break
        if target_8 is None and outcomes:
            target_8 = outcomes[len(outcomes) // 2]
            target_label = f"If stock moves +{target_8.get('underlying_pct', 8)}%"
        if target_8:
            target_return_pct = int(round(target_8.get("return_pct", 0)))
        bits = []
        if live_option.get("iv_pct") is not None:
            bits.append(f"Option's implied volatility: {live_option['iv_pct']}%")
        if iv_crush_note:
            simple_iv = iv_crush_note.replace("IV crush built-in:", "Volatility drop priced in:")
            simple_iv = simple_iv.replace("vol points", "vol pts")
            bits.append(simple_iv)
        trade_detail = " · ".join(bits) if bits else None

    if kelly_line and live_option and live_option.get("mid"):
        try:
            import re as _re
            m = _re.search(r"(\d+)\s+contracts?", kelly_line)
            if m:
                size_contracts = int(m.group(1))
        except Exception:
            size_contracts = None

    if size_contracts is None and live_option and contract_cost:
        survival = pick.get("_survival_score") or {}
        size_mult = survival.get("size_multiplier", 1.0)
        if overall.get("verdict") in ("AVOID", "WAIT FOR BETTER"):
            size_contracts = 0
        else:
            base_dollars = ACCOUNT_SIZE_USD * 0.05 * (size_mult if size_mult else 1.0)
            size_contracts = max(1, int(base_dollars / max(1, contract_cost)))

    why = _build_why_text(pick)
    catalyst_lines = humanize_catalyst_list(pick.get("catalysts") or [], max_items=4)
    risks = _build_risks(pick)

    return {
        "rank": rank,
        "ticker": pick.get("ticker", "?"),
        "name": (pick.get("name") or "")[:50],
        "sector": (pick.get("sector") or "")[:24],
        "bracket": pick.get("bracket", "?"),
        "tier": tier,
        "tier_class": _tier_class(tier),
        "price_fmt": _fmt_price(price_raw),
        "move_pct": move_pct,
        "move_pct_fmt": _fmt_pct(move_pct),
        "move_class": _move_class(move_pct),
        "trade_line": trade_line,
        "trade_detail": trade_detail,
        "outcomes": outcomes,
        "has_outcomes": bool(outcomes),
        "iv_crush_note": iv_crush_note,
        "kelly_line": kelly_line,
        "bear_note": bear_note,
        "rating_summary": rating_summary,
        "overall": overall,
        "target_return_pct": target_return_pct,
        "target_label": target_label,
        "contract_cost": contract_cost,
        "size_contracts": size_contracts,
        "why": why,
        "catalyst_lines": catalyst_lines,
        "risks": risks,
    }


def _quality_grade(score, cat_count, tier):
    if tier == "A++":
        return ("S", "highest")
    if tier == "A+" and score >= 250 and cat_count >= 4:
        return ("HIGH", "high")
    if score >= 200 and cat_count >= 3:
        return ("HIGH", "high")
    if score >= 100 and cat_count >= 3:
        return ("MED", "med")
    if cat_count >= 2:
        return ("LOW", "low")
    return ("?", "low")


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
            visible_cats.append(humanize_catalyst_key(k))
        if len(visible_cats) >= 3:
            break

    days_until = (earn_cat or {}).get("days_until")
    report_date = (earn_cat or {}).get("report_date")
    score = pick.get("_stacked_score") or pick.get("score") or 0
    cat_count = pick.get("_category_count") or len(cats)
    tier = pick.get("_aa_tier", "A")
    grade, grade_class = _quality_grade(score, cat_count, tier)

    return {
        "ticker": pick.get("ticker", "?"),
        "price_fmt": _fmt_price(pick.get("live_spot") or pick.get("price")),
        "report_date": report_date or "?",
        "days_until": days_until if days_until is not None else 99,
        "catalysts_joined": " · ".join(visible_cats) if visible_cats else "—",
        "tier": tier,
        "score": int(score),
        "cat_count": cat_count,
        "grade": grade,
        "grade_class": grade_class,
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
        "Financials": 1,
        "Consumer": 1,
        "Energy": 1,
        "Materials": 1,
        "Other": 1,
    }

    def _overall_score_of(p):
        v = (p.get("_overall_score") or {}).get("score")
        try:
            return float(v) if v is not None else -1
        except (TypeError, ValueError):
            return -1

    def _overall_sort_key(p):
        return -_overall_score_of(p)

    try:
        from src.catalyst.catalyst_quality import is_speculative_only
    except ImportError:
        def is_speculative_only(p):
            return False

    try:
        from src.catalyst.action_signal import compute_action
    except ImportError:
        compute_action = None

    def _is_take_or_watch(pick):
        if compute_action is None:
            return _is_buy_signal(pick)
        action = pick.get("_action_signal") or compute_action(pick)
        return action.get("action") in ("TAKE", "WATCH")

    buy_picks = [p for p in all_tier_picks if _is_take_or_watch(p) and not is_speculative_only(p)]
    buy_picks.sort(key=_overall_sort_key)

    MIN_PICKS_TARGET = 10
    fallback_picks = []
    if len(buy_picks) < MIN_PICKS_TARGET:
        already_included = set(id(p) for p in buy_picks)
        candidates_with_overall = [
            p for p in all_tier_picks
            if id(p) not in already_included
            and _overall_score_of(p) >= 50
            and not is_speculative_only(p)
        ]
        candidates_with_overall.sort(key=_overall_sort_key)
        needed = MIN_PICKS_TARGET - len(buy_picks)
        for p in candidates_with_overall[:needed * 2]:
            bear = p.get("bear_verification") or {}
            if bear.get("is_this_trade_a_trap"):
                continue
            fallback_picks.append(p)
            if len(fallback_picks) >= needed:
                break

    picked = []
    sector_counts = {}
    for p in buy_picks + fallback_picks:
        bucket = _sector_bucket(p.get("sector"))
        cap = SECTOR_CAPS.get(bucket, 1) * 2
        if sector_counts.get(bucket, 0) >= cap:
            continue
        picked.append(p)
        sector_counts[bucket] = sector_counts.get(bucket, 0) + 1
        if len(picked) >= 12:
            break

    top_picks = picked
    picks_out = [_build_pick(p, i + 1) for i, p in enumerate(top_picks)]

    filtered_out_count = len(all_tier_picks) - len(buy_picks)
    fallback_used_count = len(fallback_picks)

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
        fallback_used_count=fallback_used_count,
    )

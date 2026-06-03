from datetime import datetime
from jinja2 import Template

try:
    from src.catalyst.live_option_picker import find_best_call, find_best_put, project_outcomes, build_trade_line, build_kelly_line
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
    {{ scan_day_label }} · {{ picks|length }} pick{% if picks|length != 1 %}s{% endif %} surfaced
  </div>

  <div style="background:#1a1a1a; color:#fff; padding:12px 16px; border-radius:8px; margin:14px 0; font-size:12px; line-height:1.7;">
    <div style="display:flex; flex-wrap:wrap; gap:14px;">
      <span><strong style="color:{% if at_glance.regime == 'STRONG_BULL' %}#86efac{% elif at_glance.regime == 'BULL' %}#a7f3d0{% elif at_glance.regime == 'MIXED' %}#fde68a{% elif at_glance.regime == 'BEAR' %}#fca5a5{% elif at_glance.regime == 'STRONG_BEAR' %}#ef4444{% else %}#d1d5db{% endif %};">{{ at_glance.regime }}</strong> regime</span>
      <span>VIX <strong>{{ at_glance.vix }}</strong></span>
      <span>FOMC in <strong>{{ at_glance.fomc_days }}d</strong></span>
      <span>CPI in <strong>{{ at_glance.cpi_days }}d</strong></span>
      <span>Account <strong>£{{ at_glance.account_gbp }}</strong>{% if at_glance.drawdown_pct > 0 %} ({{ at_glance.drawdown_pct }}% off peak){% endif %}</span>
      <span>Open <strong>{{ at_glance.open_positions }}/{{ at_glance.max_positions }}</strong></span>
      <span>Pace to £20k: <strong style="color:{% if at_glance.on_pace %}#86efac{% else %}#fca5a5{% endif %};">{% if at_glance.on_pace %}ON TRACK{% else %}BEHIND{% endif %}</strong> ({{ at_glance.weeks_left }}w left, need {{ at_glance.required_weekly }}%/wk)</span>
    </div>
  </div>

  {% if review_mode %}
  <div style="padding:16px 18px; margin:14px 0; background:#fef2f2; border:2px solid #b91c1c; border-radius:8px;">
    <div style="font-weight:800; color:#b91c1c; font-size:15px; margin-bottom:6px;">REVIEW MODE - circuit breaker triggered</div>
    {% for t in review_triggers %}
    <div style="font-size:12px; color:#7f1d1d; line-height:1.5; margin-bottom:3px;">- {{ t.message }}</div>
    {% endfor %}
    <div style="font-size:11px; color:#7f1d1d; margin-top:8px; font-style:italic;">Picks below are still shown but require a manual thesis review before you enter. Do not auto-trade.</div>
  </div>
  {% endif %}

  {% if drift_alerts %}
  <hr class="section-rule">
  <div class="section-label" style="color:#b91c1c;">EXIT WARNINGS · Open positions losing conviction</div>
  {% for a in drift_alerts %}
  <div style="padding:12px 16px; margin:8px 0; background:{{ '#fef2f2' if a.severity == 'HIGH' else '#fefce8' }}; border-left:4px solid {{ '#b91c1c' if a.severity == 'HIGH' else '#a16207' }}; border-radius:6px;">
    <div style="font-weight:800; color:{{ '#b91c1c' if a.severity == 'HIGH' else '#a16207' }}; font-size:14px;">
      [{{ a.severity }}] {{ a.ticker }} — {{ a.alert_type|replace('_', ' ') }}
    </div>
    <div style="font-size:13px; color:#374151; margin-top:6px; line-height:1.5;">{{ a.message }}</div>
    <div style="font-size:11px; color:#6b7280; margin-top:6px;">
      Opened {{ a.entry_scan_date }} as {{ a.entry_side }}{% if a.entry_price and a.current_price %} · Price ${{ '%.2f'|format(a.entry_price) }} → ${{ '%.2f'|format(a.current_price) }}{% endif %}
    </div>
  </div>
  {% endfor %}
  {% endif %}

  {% if position_intel %}
  <hr class="section-rule">
  <div class="section-label">POSITION INTELLIGENCE · Your live trades — daily HOLD/TRIM/SELL verdict</div>
  {% for pos in position_intel %}
  <div style="padding:14px 16px; margin:10px 0; background:{% if pos.verdict == 'SELL' %}#fef2f2{% elif pos.verdict == 'TRIM' %}#fefce8{% else %}#ecfdf5{% endif %}; border-left:4px solid {% if pos.verdict == 'SELL' %}#b91c1c{% elif pos.verdict == 'TRIM' %}#a16207{% else %}#15803d{% endif %}; border-radius:6px;">
    <div style="font-weight:800; font-size:14px; color:{% if pos.verdict == 'SELL' %}#b91c1c{% elif pos.verdict == 'TRIM' %}#a16207{% else %}#15803d{% endif %};">
      {{ pos.ticker }} — {{ pos.verdict }} ({{ pos.confidence }}) — {{ pos.pass_count }}/7 factors confirm
    </div>
    <div style="font-size:12px; color:#374151; margin-top:6px; line-height:1.5;">{{ pos.plain_english }}</div>
    <div style="font-size:11px; color:#4b5563; margin-top:8px; line-height:1.6;">
      {% for fk, fv in pos.factors.items() %}
      <div>
        <span style="display:inline-block; width:14px; color:{% if fv.pass == true %}#15803d{% elif fv.pass == false %}#b91c1c{% else %}#6b7280{% endif %}; font-weight:800;">{% if fv.pass == true %}+{% elif fv.pass == false %}-{% else %}?{% endif %}</span>
        <span style="font-weight:600; text-transform:capitalize;">{{ fk|replace('_', ' ') }}:</span>
        {{ fv.detail }}
      </div>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
  {% endif %}

  {% if sit_out_today %}
  <hr class="section-rule">
  <div style="padding:24px 20px; background:#f9fafb; border:2px solid #6b7280; border-radius:10px; text-align:center; margin:18px 0;">
    <div style="font-size:18px; font-weight:800; color:#374151; margin-bottom:8px;">Sit out today</div>
    <div style="font-size:13px; color:#6b7280; line-height:1.5;">No setup clears the TAKE-grade bar. The system would rather show you nothing than push borderline picks. Cash is a position. Come back tomorrow.</div>
  </div>
  {% endif %}

  {% if bidirectional and (bidirectional.summary.n_calls > 0 or bidirectional.summary.n_puts > 0) %}
  <hr class="section-rule">
  <div class="section-label">Positioning Signal — Bidirectional</div>
  <div style="padding:14px 18px; background:#f9fafb; border:2px solid #1f2937; border-radius:10px; margin:12px 0; font-size:13px;">
    <div style="font-weight:800; color:#1f2937; margin-bottom:6px;">{{ bidirectional.summary.thesis_summary }}</div>
    <div style="color:#6b7280; font-size:12px;">Macro regime: <strong>{{ bidirectional.summary.macro_regime }}</strong>  ·  {{ bidirectional.summary.n_calls }} CALL ({{ bidirectional.summary.elite_calls }} elite), {{ bidirectional.summary.n_puts }} PUT ({{ bidirectional.summary.elite_puts }} elite)</div>
  </div>
  <table style="width:100%; border-collapse:separate; border-spacing:8px 0; margin:8px 0;">
    <tr style="vertical-align:top;">
      <td style="width:55%; padding:0;">
        <div style="background:#ecfdf5; border:2px solid #15803d; border-radius:8px; padding:14px 16px;">
          <div style="font-size:11px; letter-spacing:1.5px; color:#15803d; font-weight:800; margin-bottom:8px;">CALL CANDIDATES (LONG)</div>
          {% if bidirectional.calls %}
            {% for c in bidirectional.calls[:8] %}
            <div style="padding:8px 0; border-bottom:1px solid #d1fae5; font-size:12.5px; color:#064e3b;">
              <strong style="font-size:14px; font-family:Menlo, Consolas, monospace;">{{ c.ticker }}</strong>
              <span style="display:inline-block; padding:1px 8px; border-radius:8px; font-size:10px; font-weight:800; background:#15803d; color:#fff; margin-left:6px;">{{ c._positioning_first.conviction_tier }} {{ c._positioning_first.score }}</span>
              {% if c._positioning_first.recommended_size_pct > 0 %}<span style="font-size:11px; color:#065f46;"> · size {{ c._positioning_first.recommended_size_pct }}%</span>{% endif %}
              <div style="font-size:11px; color:#047857; margin-top:3px; line-height:1.5;">
                {% for s in c._positioning_first.positioning_signals[:3] %}{{ s.label }}{% if not loop.last %}; {% endif %}{% endfor %}
              </div>
            </div>
            {% endfor %}
          {% else %}
            <div style="color:#6b7280; font-size:12px; padding:8px 0;">No CALL candidates from positioning extremes.</div>
          {% endif %}
        </div>
      </td>
      <td style="width:45%; padding:0;">
        <div style="background:#fef2f2; border:2px solid #b91c1c; border-radius:8px; padding:14px 16px;">
          <div style="font-size:11px; letter-spacing:1.5px; color:#b91c1c; font-weight:800; margin-bottom:8px;">PUT CANDIDATES (SHORT)</div>
          {% if bidirectional.puts %}
            {% for c in bidirectional.puts[:5] %}
            <div style="padding:8px 0; border-bottom:1px solid #fecaca; font-size:12.5px; color:#7f1d1d;">
              <strong style="font-size:14px; font-family:Menlo, Consolas, monospace;">{{ c.ticker }}</strong>
              <span style="display:inline-block; padding:1px 8px; border-radius:8px; font-size:10px; font-weight:800; background:#b91c1c; color:#fff; margin-left:6px;">{{ c._positioning_first.conviction_tier }} {{ c._positioning_first.score }}</span>
              {% if c._positioning_first.recommended_size_pct > 0 %}<span style="font-size:11px; color:#7f1d1d;"> · size {{ c._positioning_first.recommended_size_pct }}%</span>{% endif %}
              <div style="font-size:11px; color:#991b1b; margin-top:3px; line-height:1.5;">
                {% for s in c._positioning_first.positioning_signals[:3] %}{{ s.label }}{% if not loop.last %}; {% endif %}{% endfor %}
              </div>
            </div>
            {% endfor %}
          {% else %}
            <div style="color:#6b7280; font-size:12px; padding:8px 0;">No PUT candidates from positioning extremes.</div>
          {% endif %}
        </div>
      </td>
    </tr>
  </table>
  {% endif %}

  {% if picks %}
  <hr class="section-rule">
  <div class="section-label">The Picks</div>

  {% for p in picks %}
  <div class="pick">
    <div class="pick-header">
      <span class="pick-rank">#{{ loop.index }}</span>
      <span class="pick-ticker">{{ p.ticker }}</span>
      <span class="pick-name">{{ p.name }}{% if p.sector %} · {{ p.sector }}{% endif %}</span>
      <span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:#065f46; color:#fff;">TAKE {{ p.conviction.score }}</span>
      {% if p.forward_catalyst_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.forward_catalyst_badge.color }}; color:#fff;" title="{{ p.forward_catalyst_badge.date }}">{{ p.forward_catalyst_badge.label }}</span>{% endif %}
      {% if p.vcp_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.vcp_badge.color }}; color:#fff;">{{ p.vcp_badge.label }}</span>{% endif %}
      {% if p.iv_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.iv_badge.color }}; color:#fff;">{{ p.iv_badge.label }}</span>{% endif %}
      {% if p.confluence_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.confluence_badge.color }}; color:#fff;">{{ p.confluence_badge.label }}</span>{% endif %}
      {% if p.activist_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.activist_badge.color }}; color:#fff;">{{ p.activist_badge.label }}</span>{% endif %}
      {% if p.mtf_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.mtf_badge.color }}; color:#fff;">{{ p.mtf_badge.label }}</span>{% endif %}
      {% if p.pocket_pivot_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.pocket_pivot_badge.color }}; color:#fff;">{{ p.pocket_pivot_badge.label }}</span>{% endif %}
      {% if p.index_rebalance_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.index_rebalance_badge.color }}; color:#fff;">{{ p.index_rebalance_badge.label }}</span>{% endif %}
      {% if p.live_action_badge %}<span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:800; background:{{ p.live_action_badge.color }}; color:#fff;">{{ p.live_action_badge.label }}</span>{% endif %}
      <span class="pick-price">${{ p.price_fmt }}{% if p.move_pct_fmt %} <span class="{{ p.move_class }}">{{ p.move_pct_fmt }}</span>{% endif %}</span>
    </div>

    {% if p.live_chain %}
    <div style="padding:8px 12px; background:#f0f9ff; border-left:3px solid #0369a1; border-radius:5px; margin:8px 0; font-size:11.5px; color:#0c4a6e; line-height:1.5; font-family:Menlo, Consolas, monospace;">
      <strong>LIVE chain @ {{ p.live_chain.fetched_at[:16] }}Z:</strong>
      {% if p.live_chain.atm_call_iv_pct %}call ${{ p.live_chain.atm_call_strike }} IV {{ p.live_chain.atm_call_iv_pct }}% d{{ p.live_chain.atm_call_delta }}{% endif %}
      {% if p.live_chain.atm_put_iv_pct %} · put ${{ p.live_chain.atm_put_strike }} IV {{ p.live_chain.atm_put_iv_pct }}% d{{ p.live_chain.atm_put_delta }}{% endif %}
    </div>
    {% endif %}

    {% if p.thesis_plain %}
    <div style="padding:12px 14px; background:#f9fafb; border-left:3px solid #374151; border-radius:5px; margin:10px 0; font-size:13px; color:#1f2937; line-height:1.55;">
      <strong style="display:block; margin-bottom:4px; color:#374151; font-size:11px; letter-spacing:0.8px;">WHY THIS MATTERS</strong>
      {{ p.thesis_plain }}
    </div>
    {% endif %}

    {% if p.robinhood_order %}
    <div style="margin:14px 0; padding:16px 18px; background:#0f172a; color:#fff; border-radius:8px;">
      <div style="font-size:11px; font-weight:800; color:#86efac; letter-spacing:1.2px; margin-bottom:8px;">ROBINHOOD ORDER</div>
      <div style="font-size:15px; font-weight:700; line-height:1.5; font-family:Menlo, Consolas, monospace;">
        Buy {{ p.robinhood_order.contracts }}x &nbsp;{{ p.ticker }}&nbsp; {{ p.robinhood_order.expiry_label }}&nbsp; <strong>${{ p.robinhood_order.strike }} {{ p.robinhood_order.right }}</strong>
      </div>
      <div style="font-size:13px; line-height:1.7; margin-top:8px; font-family:Menlo, Consolas, monospace;">
        Limit price: <strong>${{ p.robinhood_order.limit_price }}</strong> (mid)<br>
        Total cost: <strong>£{{ p.robinhood_order.total_cost_gbp }}</strong> ({{ p.robinhood_order.account_pct }}% of account)<br>
        Stop if option drops below: <strong>${{ p.robinhood_order.stop_price }}</strong> (~{{ p.robinhood_order.stop_loss_pct }}% loss)<br>
        Exit target: <strong>${{ p.robinhood_order.target_price }}</strong> (~+{{ p.robinhood_order.target_gain_pct }}%) or {{ p.robinhood_order.exit_by_date }}
      </div>
    </div>
    {% elif p.size_rationale %}
    <div style="padding:10px 14px; background:#fef2f2; border-left:3px solid #b91c1c; border-radius:5px; margin:10px 0; font-size:12px; color:#7f1d1d;">
      <strong>No order shown:</strong> {{ p.size_rationale }}
    </div>
    {% endif %}

    {% if p.confirming %}
    <div style="padding:10px 14px; background:#ecfdf5; border-left:3px solid #15803d; border-radius:5px; margin:10px 0; font-size:12px; color:#065f46; line-height:1.55;">
      <strong>Confirming signals:</strong> {{ p.confirming }}
    </div>
    {% endif %}

    {% if p.earnings_history_line %}
    <div style="padding:10px 14px; background:#f0f9ff; border-left:3px solid #0369a1; border-radius:5px; margin:10px 0; font-size:12px; color:#0c4a6e; line-height:1.55;">
      <strong>Earnings reaction history:</strong> {{ p.earnings_history_line }}
    </div>
    {% endif %}

    {% if p.what_kills %}
    <div style="padding:10px 14px; background:#fef2f2; border-left:3px solid #b91c1c; border-radius:5px; margin:10px 0; font-size:12px; color:#7f1d1d; line-height:1.55;">
      <strong>What kills this trade:</strong> {{ p.what_kills }}
    </div>
    {% endif %}
  </div>
  {% endfor %}
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
    Win rate (30d): <strong>{{ win_rate_display }}</strong><br>
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

    direction = pick.get("_direction") or {}
    side = direction.get("side", "CALL")

    if LIVE_OPTIONS_AVAILABLE and price and ticker:
        try:
            if side == "PUT":
                option = find_best_put(ticker, price)
            else:
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


def _signal_agreement(pick):
    """Confidence badge: how many independent signals agree on the direction?"""
    direction = pick.get("_direction") or {}
    side = direction.get("side") or "CALL"
    conv = (pick.get("_conviction") or {}).get("components") or {}
    agreeing = 0
    if side == "CALL":
        if (conv.get("insider") or 50) >= 60:
            agreeing += 1
        if (conv.get("pead") or 50) >= 60:
            agreeing += 1
        if (conv.get("buyback_guidance") or 50) >= 60:
            agreeing += 1
        if (conv.get("stage2") or 50) >= 60:
            agreeing += 1
        if (conv.get("analyst") or 50) >= 65:
            agreeing += 1
        if (conv.get("options_flow") or 50) >= 60:
            agreeing += 1
        if (conv.get("whisper") or 50) >= 60:
            agreeing += 1
        if (conv.get("whalewisdom") or 50) >= 60:
            agreeing += 1
        haiku = pick.get("haiku_synthesis") or {}
        if haiku.get("verdict") in ("STRONG_BUY", "BUY"):
            agreeing += 1
    else:
        bsig = pick.get("_bearish_signals") or {}
        if bsig.get("stage_4_zone"):
            agreeing += 1
        if bsig.get("insider_selling_cluster"):
            agreeing += 1
        if bsig.get("dilution"):
            agreeing += 1
        if bsig.get("going_concern"):
            agreeing += 1
        if bsig.get("earnings_miss_drift"):
            agreeing += 1
        if bsig.get("downgrade_cluster"):
            agreeing += 1
        macro = pick.get("_macro_put")
        if macro:
            agreeing += 2
    if agreeing >= 5:
        return ("HIGH", "#15803d", f"{agreeing} signals agree")
    if agreeing >= 3:
        return ("MED", "#a16207", f"{agreeing} signals agree")
    if agreeing >= 1:
        return ("LOW", "#6b7280", f"{agreeing} signal{'s' if agreeing != 1 else ''} agree")
    return ("THIN", "#b91c1c", "0 confirming signals - score driven by 1 component")


def _trend_arrow(pick):
    trend = pick.get("_conviction_trend") or {}
    label = trend.get("label")
    if not label or label == "FLAT":
        return None
    delta = trend.get("delta")
    if label == "NEW":
        return {"arrow": "NEW", "color": "#0ea5e9", "tooltip": "First appearance"}
    if label == "FLIP":
        prior_side = trend.get("prior_side") or ""
        return {"arrow": "FLIP", "color": "#b91c1c", "tooltip": f"Side flipped from {prior_side}"}
    if label == "UP":
        return {"arrow": f"+{abs(delta):.0f}", "color": "#15803d", "tooltip": f"Conviction up {abs(delta):.0f} pts vs prior"}
    if label == "DOWN":
        return {"arrow": f"-{abs(delta):.0f}", "color": "#b91c1c", "tooltip": f"Conviction down {abs(delta):.0f} pts vs prior"}
    return None


def _humanize_signal(key):
    return {
        "insider": "Insider buying cluster",
        "pead": "Post-earnings drift setup",
        "stage2": "Stage 2 uptrend confirmed",
        "buyback_guidance": "Buyback / guidance raise",
        "options_flow": "Options flow positive",
        "analyst": "Analyst upgrades",
        "whisper": "Earnings whisper bullish",
        "trends": "Search interest rising",
        "whalewisdom": "Institutional accumulation",
        "llm_and_overall": "LLM bull thesis",
    }.get(key, key.replace("_", " ").title())


def _build_thesis_plain(pick):
    """One-sentence plain-English why-this-trade. Synthesises from haiku + catalyst."""
    haiku = pick.get("haiku_synthesis") or {}
    bull = (haiku.get("bull_thesis") or "").strip()
    if bull:
        return bull
    cats = pick.get("catalysts") or []
    if cats:
        labels = [c.get("label", "") for c in cats[:2] if isinstance(c, dict) and c.get("label")]
        if labels:
            return f"Setup driven by {' and '.join(labels)}."
    return "Setup met multiple TAKE-grade conviction signals."


def _build_confirming_signals(pick):
    conv = (pick.get("_conviction") or {}).get("components") or {}
    strong = []
    for k in ("insider", "pead", "stage2", "buyback_guidance", "llm_and_overall"):
        if (conv.get(k) or 0) >= 70:
            strong.append(_humanize_signal(k))
    return " · ".join(strong[:4]) if strong else None


def _build_what_kills(pick):
    haiku = pick.get("haiku_synthesis") or {}
    kt = haiku.get("what_kills_this_trade")
    if kt:
        return kt
    bear = pick.get("bear_verification") or {}
    killer = bear.get("killer_thesis")
    if killer and killer.strip().lower() != "no specific bear case found":
        return killer
    return None


def _build_live_action_badge(pick):
    """Surface live-refresh chase risk + gap as a header badge."""
    la = pick.get("_live_action") or {}
    flag = la.get("flag")
    gap = la.get("gap_pct")
    if flag == "DO_NOT_CHASE":
        return {"label": f"DO NOT CHASE +{gap:.1f}%", "color": "#b91c1c"}
    if flag == "THESIS_BROKEN":
        return {"label": f"THESIS BROKEN {gap:+.1f}%", "color": "#7f1d1d"}
    if flag == "GAP_NOTABLE" and gap is not None:
        if gap > 0:
            return {"label": f"LIVE +{gap:.1f}%", "color": "#15803d"}
        else:
            return {"label": f"LIVE {gap:.1f}%", "color": "#9a3412"}
    return None


def _build_robinhood_order(pick, guardrail_state):
    """Build the exact Robinhood-typeable order from live_option + guardrails."""
    live_option = pick.get("_live_option")
    if not live_option or not guardrail_state:
        return None, "no live options chain attached - manual entry needed"

    try:
        from src.catalyst.guardrails import position_size_for_pick
        mid = float(live_option.get("mid") or 0)
        confluence = pick.get("_confluence")
        contracts, total_gbp, fail = position_size_for_pick(guardrail_state, mid, confluence=confluence)
        if fail:
            return None, fail

        config = guardrail_state["config"]
        account_gbp = guardrail_state["current_account_gbp"]
        account_pct = round((total_gbp / account_gbp) * 100, 1) if account_gbp > 0 else 0

        strike = float(live_option.get("strike") or 0)
        expiry = live_option.get("expiration") or ""
        right = (live_option.get("right") or "call").lower()
        right_display = "CALL" if right == "call" else "PUT"

        try:
            exp_dt = datetime.strptime(expiry, "%Y-%m-%d")
            expiry_label = exp_dt.strftime("%b %d").upper()
        except Exception:
            expiry_label = expiry

        stop_pct = 40
        stop_price = round(mid * (1 - stop_pct / 100), 2)
        target_pct = 80
        target_price = round(mid * (1 + target_pct / 100), 2)

        try:
            exp_dt = datetime.strptime(expiry, "%Y-%m-%d").date()
            exit_by = (exp_dt.replace(day=max(1, exp_dt.day - 3))).strftime("%b %d")
        except Exception:
            exit_by = "3 days before expiry"

        return {
            "contracts": contracts,
            "strike": f"{strike:.2f}".rstrip("0").rstrip(".") if strike < 1000 else f"{strike:.0f}",
            "expiry_label": expiry_label,
            "right": right_display,
            "limit_price": f"{mid:.2f}",
            "total_cost_gbp": int(round(total_gbp)),
            "account_pct": account_pct,
            "stop_price": f"{stop_price:.2f}",
            "stop_loss_pct": stop_pct,
            "target_price": f"{target_price:.2f}",
            "target_gain_pct": target_pct,
            "exit_by_date": exit_by,
        }, None
    except Exception as e:
        return None, f"order build failed: {type(e).__name__}: {e}"


def _build_pick(pick, rank, guardrail_state=None):
    tier = pick.get("_aa_tier", "A")
    price_raw = pick.get("live_spot") or pick.get("price")
    move_pct = pick.get("today_pct_change") or pick.get("intraday_pct_change")
    confidence_label, confidence_color, confidence_detail = _signal_agreement(pick)
    trend_badge = _trend_arrow(pick)
    thesis_plain = _build_thesis_plain(pick)
    confirming = _build_confirming_signals(pick)
    what_kills = _build_what_kills(pick)
    robinhood_order, ro_fail_reason = _build_robinhood_order(pick, guardrail_state)
    fc = pick.get("_forward_catalyst")
    forward_catalyst_badge = None
    if fc and fc.get("days_until") is not None:
        days = fc["days_until"]
        if days <= 21 and days >= 2:
            label = f"{fc['type'].upper().replace('_', ' ')} IN {days}d"
            color = "#15803d" if 5 <= days <= 21 else "#a16207"
            forward_catalyst_badge = {"label": label, "color": color, "date": fc.get("date")}
        elif days < 2:
            forward_catalyst_badge = {"label": f"{fc['type'].upper().replace('_', ' ')} IN {days}d - IV CRUSH RISK", "color": "#b91c1c", "date": fc.get("date")}

    vcp = pick.get("_vcp_setup") or {}
    vcp_badge = None
    if vcp.get("badge_label"):
        vcp_badge = {
            "label": vcp["badge_label"],
            "color": "#7c2d12" if vcp.get("verdict") == "PRIME_BREAKOUT" else "#9a3412",
        }

    ivw = pick.get("_iv_window") or {}
    iv_badge = None
    if ivw.get("badge_label"):
        iv_badge = {
            "label": ivw["badge_label"],
            "color": "#0c4a6e" if ivw.get("verdict") == "IV_CHEAP_WINDOW" else "#6b21a8",
        }

    conf = pick.get("_confluence") or {}
    confluence_badge = None
    if conf.get("sizing_tier") in ("ELITE", "STRONG", "MODERATE"):
        tier = conf["sizing_tier"]
        count = conf.get("confluence_count", 0)
        breadth = conf.get("category_breadth", 0)
        color = {"ELITE": "#7f1d1d", "STRONG": "#15803d", "MODERATE": "#a16207"}[tier]
        confluence_badge = {
            "label": f"{tier} {count}/15 signals ({breadth} categories)",
            "color": color,
        }

    a13d = pick.get("_activist_13d") or {}
    activist_badge = None
    if a13d.get("fires") and a13d.get("name"):
        activist_badge = {
            "label": f"ACTIVIST: {a13d['name']}",
            "color": "#581c87",
        }

    eh = pick.get("_earnings_history") or {}
    earnings_history_line = None
    if eh.get("summary_string"):
        pattern = eh.get("pattern", "")
        pattern_label = {
            "BEAT_AND_RIP": "beat-and-rip pattern",
            "SELL_THE_NEWS": "sell-the-news pattern",
            "POSITIVE_LEAN": "lean bullish historically",
            "VOLATILE": "volatile reactions",
            "MIXED": "mixed history",
        }.get(pattern, "")
        earnings_history_line = f"{eh['summary_string']} ({pattern_label})"

    mtf = pick.get("_mtf_trend") or {}
    mtf_badge = None
    if mtf.get("aligned_up"):
        mtf_badge = {"label": "D+W+M ALIGNED", "color": "#0f766e"}
    elif mtf.get("aligned_down"):
        mtf_badge = {"label": "D+W+M DOWN", "color": "#7f1d1d"}

    pp = pick.get("_pocket_pivot") or {}
    pocket_pivot_badge = None
    if pp.get("fires"):
        pocket_pivot_badge = {"label": "POCKET PIVOT", "color": "#1e40af"}

    ir_list = pick.get("_index_rebalance") or []
    index_rebalance_badge = None
    if ir_list:
        m = ir_list[0]
        if m.get("days_until") is not None and m["days_until"] <= 45:
            index_rebalance_badge = {
                "label": f"{m['label']} {m['days_until']}d",
                "color": "#0e7490",
            }

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

    conv_raw = pick.get("_conviction") or {}
    if not conv_raw:
        try:
            from src.catalyst.conviction_score import compute_conviction_score
            conv_raw = compute_conviction_score(pick)
        except Exception:
            conv_raw = {"score": overall.get("score", 50), "tier": "WATCH", "components": {}, "weights": {}}

    c_score = conv_raw.get("score", 50)
    c_tier = conv_raw.get("tier", "WATCH")
    if c_score >= 80:
        c_verdict, c_class, c_plain = "TAKE HIGH-CONVICTION", "overall-strong", "Strong cross-signal alignment. Multiple independent signals confirming."
    elif c_score >= 70:
        c_verdict, c_class, c_plain = "TAKE", "overall-good", "Solid setup. Worth a normal-sized position."
    elif c_score >= 60:
        c_verdict, c_class, c_plain = "WATCH", "overall-borderline", "Borderline edge. Wait for confirmation or size down."
    elif c_score >= 45:
        c_verdict, c_class, c_plain = "SKIP", "overall-watch", "Weak signal stack. Not actionable."
    else:
        c_verdict, c_class, c_plain = "AVOID", "overall-avoid", "No edge or active red flags."

    comps = conv_raw.get("components") or {}
    component_labels = {
        "llm_and_overall": "LLM/Overall",
        "insider": "Insider cluster",
        "pead": "PEAD beat",
        "buyback_guidance": "Buyback/Guidance",
        "options_flow": "Options flow",
        "stage2": "Stage 2 entry",
        "analyst": "Analyst upgrades",
        "whisper": "Whisper EPS",
        "whalewisdom": "13F accumulation",
        "trends": "Retail buzz",
    }
    strong_signals = [component_labels.get(k, k) for k, v in comps.items() if v >= 75]
    weak_signals = [component_labels.get(k, k) for k, v in comps.items() if v <= 25]

    conviction = {
        "score": c_score,
        "verdict": c_verdict,
        "verdict_class": c_class,
        "plain_english": c_plain,
        "strong_signals": strong_signals[:4],
        "weak_signals": weak_signals[:3],
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

    size_rationale = None
    if size_contracts is None and live_option and contract_cost:
        survival = pick.get("_survival_score") or {}
        size_mult = survival.get("size_multiplier", 1.0)
        if overall.get("verdict") in ("AVOID", "WAIT FOR BETTER"):
            size_contracts = 0
            size_rationale = "verdict avoid - skip"
        else:
            conv_score = (conviction or {}).get("score") if isinstance(conviction, dict) else None
            if conv_score is None:
                conv_score = overall.get("score") or 0
            try:
                conv_score = float(conv_score)
            except (TypeError, ValueError):
                conv_score = 0
            if conv_score >= 80:
                pct_account = 0.025
                tier_label = "high conviction (80+)"
            elif conv_score >= 70:
                pct_account = 0.015
                tier_label = "take grade (70-79)"
            elif conv_score >= 60:
                pct_account = 0.008
                tier_label = "watch grade (60-69)"
            elif conv_score >= 55:
                pct_account = 0.005
                tier_label = "weak watch (55-59)"
            else:
                pct_account = 0.0
                tier_label = "below watch threshold"
            base_dollars = ACCOUNT_SIZE_USD * pct_account * (size_mult if size_mult else 1.0)
            if base_dollars < contract_cost * 0.6:
                size_contracts = 0
                size_rationale = f"pass - {tier_label} sizing ${base_dollars:.0f} below 60% of one contract (${contract_cost})"
            else:
                size_contracts = max(1, int(round(base_dollars / max(1, contract_cost))))
                actual_pct = (size_contracts * contract_cost) / ACCOUNT_SIZE_USD * 100
                size_rationale = f"{tier_label}: {pct_account*100:.1f}% target -> {size_contracts}x @ ${contract_cost} = ${size_contracts * contract_cost} ({actual_pct:.1f}% of ${int(ACCOUNT_SIZE_USD)})"

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
        "conviction": conviction,
        "target_return_pct": target_return_pct,
        "target_label": target_label,
        "contract_cost": contract_cost,
        "size_contracts": size_contracts,
        "size_rationale": size_rationale or ro_fail_reason,
        "confidence_label": confidence_label,
        "confidence_color": confidence_color,
        "confidence_detail": confidence_detail,
        "trend_badge": trend_badge,
        "why": why,
        "catalyst_lines": catalyst_lines,
        "risks": risks,
        "thesis_plain": thesis_plain,
        "confirming": confirming,
        "what_kills": what_kills,
        "robinhood_order": robinhood_order,
        "forward_catalyst_badge": forward_catalyst_badge,
        "vcp_badge": vcp_badge,
        "iv_badge": iv_badge,
        "confluence_badge": confluence_badge,
        "activist_badge": activist_badge,
        "earnings_history_line": earnings_history_line,
        "mtf_badge": mtf_badge,
        "pocket_pivot_badge": pocket_pivot_badge,
        "index_rebalance_badge": index_rebalance_badge,
        "live_action_badge": _build_live_action_badge(pick),
        "live_chain": pick.get("_live_chain"),
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


def render_unified_email(scan, aa_results, aa_picks, aa_rejections, regime_info=None, execution_ctx=None, drift_alerts=None, guardrail_state=None, position_intel=None):
    scan_date = scan.get("scan_date") or datetime.utcnow().date().isoformat()
    if drift_alerts is None:
        drift_alerts = scan.get("conviction_drift_alerts") or []
    drift_alerts = [a for a in drift_alerts if a.get("is_live")]
    if guardrail_state is None:
        guardrail_state = scan.get("guardrail_state")
    if guardrail_state is None:
        try:
            from src.catalyst.guardrails import evaluate as evaluate_guardrails
            guardrail_state = evaluate_guardrails(verbose=False)
        except Exception:
            guardrail_state = None
    if position_intel is None:
        position_intel = scan.get("position_intelligence") or []
    if not position_intel:
        try:
            from src.catalyst.position_intelligence import analyze_all_live_positions
            position_intel = analyze_all_live_positions(verbose=False)
        except Exception:
            position_intel = []
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
        c = (p.get("_conviction") or {}).get("score")
        if c is not None:
            try:
                return float(c)
            except (TypeError, ValueError):
                pass
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

    def _is_take_only(pick):
        if compute_action is None:
            return _is_buy_signal(pick)
        action = pick.get("_action_signal") or compute_action(pick)
        return action.get("action") == "TAKE"

    buy_picks = [p for p in all_tier_picks if _is_take_only(p) and not is_speculative_only(p)]
    buy_picks.sort(key=_overall_sort_key)

    picked = []
    sector_counts = {}
    for p in buy_picks:
        bucket = _sector_bucket(p.get("sector"))
        cap = SECTOR_CAPS.get(bucket, 1) * 2
        if sector_counts.get(bucket, 0) >= cap:
            continue
        picked.append(p)
        sector_counts[bucket] = sector_counts.get(bucket, 0) + 1
        if len(picked) >= 5:
            break

    top_picks = picked
    picks_out = [_build_pick(p, i + 1, guardrail_state=guardrail_state) for i, p in enumerate(top_picks)]

    filtered_out_count = len(all_tier_picks) - len(buy_picks)
    fallback_used_count = 0
    sit_out_today = len(top_picks) == 0

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

    wr_pct = win_rate_stats.get("win_rate_pct")
    wr_n = win_rate_stats.get("n")
    if wr_pct is None or wr_n in (None, "?"):
        win_rate_display = "no data yet"
    else:
        win_rate_display = f"{wr_pct}% on {wr_n} paper trades"

    macro_block = (scan.get("macro") or {})
    macro_regime_block = macro_block.get("macro_regime") or {}
    macro_regime_label = (macro_regime_block.get("regime") or macro_block.get("regime") or regime_label or "UNKNOWN")
    macro_regime_label = str(macro_regime_label).upper()
    vix_val = (macro_block.get("vix") or macro_regime_block.get("components", {}).get("vix")) if macro_block else None
    try:
        vix_display = f"{float(vix_val):.1f}" if vix_val is not None else "n/a"
    except Exception:
        vix_display = "n/a"

    fomc_days = macro_block.get("days_to_next_fomc")
    cpi_days = macro_block.get("days_to_next_cpi")
    if fomc_days is None or cpi_days is None:
        try:
            from src.catalyst.calendar_signals import next_fomc_days, next_cpi_days
            if fomc_days is None:
                fomc_days = next_fomc_days()
            if cpi_days is None:
                cpi_days = next_cpi_days()
        except Exception:
            pass

    gs = guardrail_state or {}
    pace = gs.get("pace") or {}
    at_glance = {
        "regime": macro_regime_label,
        "vix": vix_display,
        "fomc_days": fomc_days if fomc_days is not None else "?",
        "cpi_days": cpi_days if cpi_days is not None else "?",
        "account_gbp": int(round(gs.get("current_account_gbp", 4000))),
        "drawdown_pct": gs.get("drawdown_pct", 0),
        "open_positions": gs.get("open_positions", 0),
        "max_positions": gs.get("max_positions", 2),
        "on_pace": pace.get("on_pace", True),
        "weeks_left": pace.get("weeks_left", "?"),
        "required_weekly": pace.get("required_weekly_growth_pct", "?"),
    }
    review_mode = gs.get("mode") == "REVIEW_MODE"
    review_triggers = [t for t in (gs.get("triggers") or []) if t.get("severity") == "HIGH"]

    bidirectional = scan.get("bidirectional") if isinstance(scan, dict) else None

    template = Template(EMAIL_TEMPLATE)
    return template.render(
        scan_date=scan_date,
        scan_day_label=scan_day_label,
        a_pp_count=a_pp_count,
        a_p_count=a_p_count,
        a_count=a_count,
        regime_label=regime_label,
        position_mult=position_mult,
        win_rate_display=win_rate_display,
        open_slots=at_glance["open_positions"],
        max_slots=at_glance["max_positions"],
        picks=picks_out,
        sit_out_today=sit_out_today,
        pre_earnings_lead_up=pre_earnings_lead_up,
        pre_earnings_imminent=pre_earnings_imminent,
        pre_earnings_count=pre_earnings_count,
        skip_list=skip_list,
        filtered_out_count=filtered_out_count,
        fallback_used_count=fallback_used_count,
        drift_alerts=drift_alerts,
        at_glance=at_glance,
        review_mode=review_mode,
        review_triggers=review_triggers,
        position_intel=position_intel,
        bidirectional=bidirectional,
    )

from jinja2 import Template

EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; color:#222; }
  .wrap { max-width:1000px; margin:0 auto; background:#fff; padding:28px 32px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
  h1 { font-size:22px; margin:0 0 6px; }
  .meta { color:#666; font-size:13px; margin-bottom:18px; }
  .intro { background:#fffbe8; border-left:4px solid #f0d969; padding:12px 16px; border-radius:4px; margin:0 0 18px; font-size:12px; color:#444; line-height:1.5; }
  h2 { font-size:16px; margin:24px 0 10px; border-bottom:2px solid #eee; padding-bottom:6px; }
  .empty { text-align:center; color:#666; font-style:italic; padding:24px; background:#fafafa; border-radius:6px; }
  .card { border:1px solid #e5e5e5; border-radius:8px; padding:14px 16px; margin-bottom:12px; background:#fdfdfd; }
  .card.strong { border-left:6px solid #0d7b34; background:#f7fcf8; }
  .card.watch { border-left:6px solid #4a90e2; background:#f7fbff; }
  .card-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px; }
  .card-head-left { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .ticker { font-weight:700; font-size:17px; color:#111; }
  .name { color:#666; font-size:12px; }
  .tier-badge { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px; color:#fff; letter-spacing:0.4px; }
  .tier-S { background:#0d7b34; }
  .tier-A { background:#1a9850; }
  .tier-B { background:#4a90e2; }
  .tier-C { background:#999; }
  .tier-D { background:#c94545; }
  .conf-badge { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px; letter-spacing:0.4px; }
  .conf-HIGH { background:#0d7b34; color:#fff; }
  .conf-MEDIUM { background:#f0ad4e; color:#fff; }
  .conf-LOW { background:#999; color:#fff; }
  .extended-badge { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px; background:#c94545; color:#fff; letter-spacing:0.4px; }
  .priced-badge { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px; background:#e67e22; color:#fff; letter-spacing:0.4px; }
  .closed-badge { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px; background:#7c2d12; color:#fff; letter-spacing:0.4px; }
  .ideal-badge { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px; background:#0d7b34; color:#fff; letter-spacing:0.4px; box-shadow:0 0 8px rgba(13,123,52,0.4); }
  .skip-chase-badge { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px; background:#b91c1c; color:#fff; letter-spacing:0.4px; }
  .signal-box { display:flex; flex-direction:column; align-items:center; padding:8px 12px; border-radius:6px; margin:0 0 0 8px; min-width:90px; color:#fff; }
  .signal-action { font-weight:700; font-size:14px; letter-spacing:0.6px; }
  .signal-prob { font-size:10px; opacity:0.9; margin-top:2px; }
  .trade-row { display:flex; flex-wrap:wrap; gap:14px; padding:8px 12px; background:#fafafa; border-radius:4px; margin-top:8px; font-size:11px; color:#444; }
  .trade-row strong { color:#222; }
  .risk-row { margin-top:8px; padding:6px 10px; background:#fef2f2; border-left:3px solid #c94545; border-radius:3px; font-size:11px; color:#7f1d1d; }
  .risk-chip { display:inline-block; padding:1px 6px; margin:1px 3px 1px 0; border-radius:10px; font-size:10px; background:#fee; border:1px solid #fcc; color:#a02c2c; }
  .risk-chip.high { background:#fcc; border-color:#f99; color:#7f1d1d; font-weight:700; }
  .insider-row { margin-top:6px; padding:5px 10px; background:#f0fdf4; border-left:3px solid #16a34a; border-radius:3px; font-size:11px; color:#166534; }
  .options-row { margin-top:6px; padding:5px 10px; background:#fefce8; border-left:3px solid #ca8a04; border-radius:3px; font-size:11px; color:#713f12; }
  .deep-box { margin-top:10px; padding:10px 12px; background:#eff6ff; border-left:3px solid #1d4ed8; border-radius:4px; font-size:12px; color:#1e3a8a; line-height:1.5; }
  .deep-box .verdict-tag { display:inline-block; padding:2px 8px; border-radius:3px; font-weight:700; font-size:10px; color:#fff; margin-right:6px; letter-spacing:0.4px; }
  .verdict-STRONG-BUY { background:#0d7b34; }
  .verdict-BUY { background:#1a9850; }
  .verdict-HOLD { background:#999; }
  .verdict-SKIP { background:#c94545; }
  .score-box { background:#0052cc; color:#fff; padding:6px 12px; border-radius:6px; font-weight:700; font-size:14px; }
  .score-box.strong { background:#0d7b34; }
  .score-box.watch { background:#4a90e2; }
  .pctile { font-size:9px; color:rgba(255,255,255,0.85); }
  .sector-badge { display:inline-block; padding:2px 8px; border-radius:3px; font-size:10px; font-weight:600; background:#eef2f7; color:#384766; text-transform:uppercase; letter-spacing:0.3px; }
  .price-row { font-size:12px; color:#444; margin:6px 0 8px; }
  .price-row strong { color:#0052cc; font-size:13px; }
  .price-row span { margin-right:14px; }
  .catalyst-line { font-size:12px; margin:6px 0; padding:6px 10px; background:#f0f7ff; border-left:3px solid #4a90e2; border-radius:3px; }
  .catalyst-line strong { color:#0052cc; }
  .breakdown { display:grid; grid-template-columns: repeat(3, 1fr); gap:6px 14px; margin-top:8px; padding:8px 10px; background:#fafafa; border-radius:4px; font-size:10px; }
  .bd-item { display:flex; justify-content:space-between; }
  .bd-label { color:#888; }
  .bd-pts { font-weight:600; color:#333; font-variant-numeric:tabular-nums; }
  .bd-pts.pos { color:#0d7b34; }
  .bd-pts.neg { color:#c94545; }
  .llm-box { margin-top:8px; padding:8px 10px; background:#f5f3ff; border-left:3px solid #8b5cf6; border-radius:3px; font-size:11px; color:#444; }
  .llm-box strong { color:#5b21b6; }
  .news-box { margin-top:8px; padding:6px 10px; background:#f9f9f9; border-radius:3px; font-size:10px; color:#666; }
  .news-headline { padding:2px 0; }
  .source-row { font-size:10px; color:#888; margin-top:6px; }
  .legend { background:#f7f9fc; border:1px solid #e0e6ef; border-radius:8px; padding:14px 16px; margin:18px 0 22px; font-size:11px; }
  .legend h3 { margin:0 0 10px; font-size:13px; color:#384766; }
  .legend-grid { display:grid; grid-template-columns:repeat(2, 1fr); gap:14px 20px; }
  .legend-block { background:#fff; border:1px solid #e5e9f0; border-radius:6px; padding:10px 12px; }
  .legend-title { font-weight:700; color:#0052cc; font-size:11px; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.4px; }
  .legend-row { font-size:11px; color:#444; line-height:1.5; padding:2px 0; }
  .footer { margin-top:30px; font-size:11px; color:#999; text-align:center; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Catalyst Watchlist &mdash; {{ scan_date }}</h1>
  <div class="meta">{{ strong|length }} STRONG &middot; {{ watch|length }} WATCH &middot; LLM-graded {{ llm_graded }} &middot; Universe {{ candidates_total }}</div>

  <div class="intro" style="background:#dbeafe; border-color:#4a90e2;">
    <strong>Top {{ [strong|length, 3]|min }} BUYs:</strong>
    {% set buys = [] %}{% for c in strong %}{% if c.buy_signal and c.buy_signal.signal == 'BUY' and buys|length < 3 %}{% set _ = buys.append(c) %}{% endif %}{% endfor %}
    {% if buys %}
      {% for c in buys %}<strong>{{ c.ticker }}</strong> ({{ c.buy_signal.probability_pct }}%){% if not loop.last %} &middot; {% endif %}{% endfor %}
    {% else %}
      <em>No BUY-tier setups today. WATCH list below.</em>
    {% endif %}
  </div>

  {% if strong %}
    <h2 style="color:#0d7b34;">STRONG &mdash; Top 5% by multi-source score ({{ strong|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">Highest conviction. Multiple independent signals confirming the setup. Position at today's close.</div>
    {% for c in strong %}
      <div class="card strong">
        <div class="card-head">
          <div class="card-head-left">
            <span class="ticker">{{ c.ticker }}</span>
            <span class="name">{{ (c.name or c.company)[:50] }}</span>
            {% if c.sector %}<span class="sector-badge">{{ c.sector }}</span>{% endif %}
            <span class="tier-badge tier-{{ c.catalyst_tier }}">Tier {{ c.catalyst_tier }}</span>
            <span class="conf-badge conf-{{ c.confidence }}">{{ c.confidence }}</span>
            {% if c.ideal_setup %}<span class="ideal-badge">PRIME ENTRY &mdash; overnight catalyst on flat stock</span>{% endif %}
            {% if c.components.drift.skip_chase %}<span class="skip-chase-badge">CATALYST IN MOTION &mdash; do not chase</span>{% endif %}
            {% if c.deal_closed %}<span class="closed-badge">DEAL CLOSED &mdash; do not trade</span>{% endif %}
            {% if c.components.drift.extended %}<span class="extended-badge">EXTENDED &mdash; already moved</span>{% endif %}
            {% if c.components.drift.pre_priced %}<span class="priced-badge">PRE-PRICED &mdash; sell-the-news risk</span>{% endif %}
          </div>
          <div style="display:flex; align-items:center;">
            <div class="score-box strong">
              {{ "%.0f"|format(c.score) }}
              <div class="pctile">top {{ "%.0f"|format(100 - c.percentile) }}%</div>
            </div>
            {% if c.buy_signal %}
            <div class="signal-box" style="background:{{ c.buy_signal.signal_color }};">
              <div class="signal-action">{{ c.buy_signal.signal }}</div>
              <div class="signal-prob">{{ c.buy_signal.probability_pct }}% prob</div>
            </div>
            {% endif %}
          </div>
        </div>
        <div class="price-row">
          <span>Price <strong>${{ "%.2f"|format(c.price) if c.price else "n/a" }}</strong></span>
          {% if c.live_spot %}
            {% set lc = '#0d7b34' if c.live_change_pct >= 1 else ('#c94545' if c.live_change_pct <= -1 else '#666') %}
            {% set lbg = '#e7f5ec' if c.live_change_pct >= 1 else ('#fdecec' if c.live_change_pct <= -1 else '#f0f0f0') %}
            {% set big = c.live_change_pct >= 3 or c.live_change_pct <= -3 %}
            <span style="padding:2px 8px; border-radius:3px; background:{{ lbg }}; color:{{ lc }}; font-weight:700; {% if big %}border:2px solid {{ lc }};{% endif %}">
              LIVE ${{ "%.2f"|format(c.live_spot) }} ({{ "%+.2f"|format(c.live_change_pct) }}%)
              {% if big %}&middot; verify before entry{% endif %}
            </span>
          {% endif %}
          {% if c.market_cap %}<span>Mcap ${{ "%.2f"|format(c.market_cap/1e9) }}B</span>{% endif %}
          {% if c.dollar_volume_20d %}<span>$Vol ${{ "%.1f"|format(c.dollar_volume_20d/1e6) }}M</span>{% endif %}
          {% if c.short_pct_float %}<span>SI {{ "%.0f"|format(c.short_pct_float) }}%</span>{% endif %}
        </div>
        {% for cat in c.catalysts[:3] %}
          <div class="catalyst-line">
            <strong>{{ cat.label }}</strong> &middot; {{ cat.details }}
          </div>
        {% endfor %}
        {% if c.deep_research %}
          <div class="deep-box">
            <span class="verdict-tag verdict-{{ c.deep_research.verdict|replace(' ', '-') }}">{{ c.deep_research.verdict }}</span>
            <strong>Deep research ({{ c.deep_research.confidence_pct }}% conf):</strong>

            {% if c.deep_research.catalyst_status and c.deep_research.catalyst_status.status %}
              {% set cs = c.deep_research.catalyst_status %}
              {% set status_color = '#0d7b34' if cs.status == 'HAPPENED' else '#1a9850' if cs.status == 'SCHEDULED' else '#e67e22' if cs.status == 'EXPECTED' else '#888' %}
              <div style="margin:6px 0; padding:8px 10px; background:#fff; border:2px solid {{ status_color }}; border-radius:6px;">
                <span style="display:inline-block; padding:3px 10px; border-radius:3px; background:{{ status_color }}; color:#fff; font-size:12px; font-weight:700;">{{ cs.status }}</span>
                {% if cs.countdown_label %}<strong style="margin-left:8px;">{{ cs.countdown_label }}</strong>{% endif %}
                {% if cs.event_date and cs.event_date != 'null' %}<span style="margin-left:6px; color:#666;">({{ cs.event_date }})</span>{% endif %}
                {% if cs.verified_via %}<br><span style="font-size:10px; color:#888;">verified via {{ cs.verified_via }}</span>{% endif %}
              </div>
            {% endif %}

            {% if c.deep_research.outcome_prediction and c.deep_research.outcome_prediction.expected_outcome %}
              <div style="margin:6px 0; padding:6px 10px; background:#dbeafe; border-radius:4px;">
                <strong>Expected outcome:</strong> {{ c.deep_research.outcome_prediction.expected_outcome }}
                ({{ c.deep_research.outcome_prediction.outcome_probability_pct }}% probability)
                {% if c.deep_research.outcome_prediction.consensus_data %}<br><strong>Consensus:</strong> {{ c.deep_research.outcome_prediction.consensus_data }}{% endif %}
                {% if c.deep_research.outcome_prediction.outcome_reasoning %}<br><strong>Why:</strong> {{ c.deep_research.outcome_prediction.outcome_reasoning }}{% endif %}
              </div>
            {% endif %}

            {% if c.deep_research.expected_move and c.deep_research.expected_move.if_positive_pct %}
              <div style="margin:4px 0;">
                <strong>Expected move:</strong> +{{ c.deep_research.expected_move.if_positive_pct }}% if positive
                / {{ c.deep_research.expected_move.if_negative_pct }}% if negative
                {% if c.deep_research.expected_move.expected_value_pct %} &middot; <strong>EV:</strong> {{ c.deep_research.expected_move.expected_value_pct }}{% endif %}
              </div>
            {% endif %}

            {% if c.deep_research.analog_precedent and c.deep_research.analog_precedent.similar_setups %}
              {% set ap = c.deep_research.analog_precedent %}
              <div style="margin:8px 0; padding:8px 10px; background:#f5f3ff; border-left:3px solid #8b5cf6; border-radius:4px;">
                <strong>Analog precedents</strong>
                {% if ap.win_rate_pct is defined %} &middot; win rate <strong>{{ ap.win_rate_pct }}%</strong>{% endif %}
                {% if ap.median_next_day_pct is defined %} &middot; median next-day <strong>{{ ap.median_next_day_pct }}%</strong>{% endif %}
                <table style="width:100%; font-size:10px; margin-top:4px; border-collapse:collapse;">
                  <thead><tr style="background:#ede9fe;"><th align="left" style="padding:3px 6px;">Ticker</th><th align="left" style="padding:3px 6px;">Date</th><th align="left" style="padding:3px 6px;">Catalyst</th><th align="right" style="padding:3px 6px;">Next-day</th><th align="right" style="padding:3px 6px;">1-week</th></tr></thead>
                  <tbody>
                  {% for a in ap.similar_setups[:3] %}
                    <tr style="border-bottom:1px solid #e9d5ff;">
                      <td style="padding:3px 6px; font-weight:600;">{{ a.ticker }}</td>
                      <td style="padding:3px 6px; color:#666;">{{ a.date }}</td>
                      <td style="padding:3px 6px; color:#444;">{{ a.catalyst }}</td>
                      <td align="right" style="padding:3px 6px; color:{% if a.next_day_pct >= 0 %}#0d7b34{% else %}#c94545{% endif %}; font-weight:600;">{{ "%+.1f"|format(a.next_day_pct) }}%</td>
                      <td align="right" style="padding:3px 6px; color:{% if a.one_week_pct >= 0 %}#0d7b34{% else %}#c94545{% endif %};">{{ "%+.1f"|format(a.one_week_pct) }}%</td>
                    </tr>
                  {% endfor %}
                  </tbody>
                </table>
                {% if ap.summary %}<div style="margin-top:4px; font-style:italic; color:#5a3690;">{{ ap.summary }}</div>{% endif %}
              </div>
            {% endif %}

            {% if c.deep_research.stacking_analysis and c.deep_research.stacking_analysis.compounding_effect %}
              {% set sa = c.deep_research.stacking_analysis %}
              <div style="margin:8px 0; padding:8px 10px; background:#fef3c7; border-left:3px solid #d97706; border-radius:4px; font-size:11px;">
                <strong>Catalyst stacking</strong>
                {% if sa.amplification_factor %} &middot; amp <strong>{{ sa.amplification_factor }}x</strong>{% endif %}
                {% if sa.stacked_catalysts %}<br><span style="color:#444;">{{ sa.stacked_catalysts|join(' + ') }}</span>{% endif %}
                <br>{{ sa.compounding_effect }}
              </div>
            {% endif %}

            {% if c.deep_research.lottery_thesis and c.deep_research.lottery_thesis.thesis_paragraph %}
              {% set lt = c.deep_research.lottery_thesis %}
              <div style="margin:8px 0; padding:10px 12px; background:#fefce8; border:2px solid #eab308; border-radius:6px;">
                <strong style="color:#854d0e;">Lottery thesis</strong>
                {% if lt.best_strike_otm_pct %} &middot; <strong>{{ lt.best_strike_otm_pct }}% OTM</strong>{% endif %}
                {% if lt.best_dte_days %} &middot; <strong>{{ lt.best_dte_days }} DTE</strong>{% endif %}
                {% if lt.expected_premium_500pct_target_move_pct %} &middot; needs <strong>+{{ lt.expected_premium_500pct_target_move_pct }}% stock move</strong> for 500%{% endif %}
                <div style="margin-top:4px; color:#1f2937;">{{ lt.thesis_paragraph }}</div>
              </div>
            {% endif %}

            <div style="margin-top:6px;">{{ c.deep_research.research_note }}</div>
            {% if c.deep_research.reason_to_buy %}<br><strong>Bull case:</strong> {{ c.deep_research.reason_to_buy }}{% endif %}
            {% if c.deep_research.reason_to_avoid %}<br><strong>Bear case:</strong> {{ c.deep_research.reason_to_avoid }}{% endif %}
            {% if c.deep_research.red_flags_found %}<br><strong>Risks found:</strong> {{ c.deep_research.red_flags_found|join(' &middot; ') }}{% endif %}
          </div>
        {% endif %}
        {% if c.risk_audit and c.risk_audit.flags %}
          <div class="risk-row">
            <strong>Risk flags:</strong>
            {% for flag in c.risk_audit.flags %}
              <span class="risk-chip {{ 'high' if flag.severity == 'HIGH' else '' }}">{{ flag.label }}</span>
            {% endfor %}
          </div>
        {% endif %}
        {% if c.insider_depth and c.insider_depth.signals %}
          <div class="insider-row">
            <strong>Insider:</strong> {{ c.insider_depth.signals|join(' &middot; ') }}
          </div>
        {% endif %}
        {% if c.options_check and c.options_check.implied_move_1d_pct %}
          <div class="options-row">
            <strong>Options:</strong> {{ c.options_check.label }}
          </div>
        {% endif %}
        {% if c.components.llm.reasoning %}
          <div class="llm-box">
            <strong>LLM read:</strong> {{ c.components.llm.reasoning }}
            {% if c.components.llm.key_signal %}<br><strong>Key signal:</strong> {{ c.components.llm.key_signal }}{% endif %}
          </div>
        {% endif %}
        {% if c.news and c.news.headlines %}
          <div class="news-box">
            {% for h in c.news.headlines[:3] %}
              <div class="news-headline">[{{ h.date }}] {{ h.title }}</div>
            {% endfor %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  {% if watch %}
    <h2 style="color:#4a90e2;">WATCH &mdash; Top 5-15% by multi-source score ({{ watch|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">Solid setup with fewer corroborating signals. Smaller size, wait for confirmation move on open.</div>
    {% for c in watch %}
      <div class="card watch">
        <div class="card-head">
          <div class="card-head-left">
            <span class="ticker">{{ c.ticker }}</span>
            <span class="name">{{ (c.name or c.company)[:50] }}</span>
            {% if c.sector %}<span class="sector-badge">{{ c.sector }}</span>{% endif %}
            <span class="tier-badge tier-{{ c.catalyst_tier }}">Tier {{ c.catalyst_tier }}</span>
            <span class="conf-badge conf-{{ c.confidence }}">{{ c.confidence }}</span>
            {% if c.ideal_setup %}<span class="ideal-badge">PRIME ENTRY &mdash; overnight catalyst on flat stock</span>{% endif %}
            {% if c.components.drift.skip_chase %}<span class="skip-chase-badge">CATALYST IN MOTION &mdash; do not chase</span>{% endif %}
            {% if c.deal_closed %}<span class="closed-badge">DEAL CLOSED &mdash; do not trade</span>{% endif %}
            {% if c.components.drift.extended %}<span class="extended-badge">EXTENDED &mdash; already moved</span>{% endif %}
            {% if c.components.drift.pre_priced %}<span class="priced-badge">PRE-PRICED &mdash; sell-the-news risk</span>{% endif %}
          </div>
          <div style="display:flex; align-items:center;">
            <div class="score-box watch">
              {{ "%.0f"|format(c.score) }}
              <div class="pctile">top {{ "%.0f"|format(100 - c.percentile) }}%</div>
            </div>
            {% if c.buy_signal %}
            <div class="signal-box" style="background:{{ c.buy_signal.signal_color }};">
              <div class="signal-action">{{ c.buy_signal.signal }}</div>
              <div class="signal-prob">{{ c.buy_signal.probability_pct }}% prob</div>
            </div>
            {% endif %}
          </div>
        </div>
        <div class="price-row">
          <span>Price <strong>${{ "%.2f"|format(c.price) if c.price else "n/a" }}</strong></span>
          {% if c.live_spot %}
            {% set lc = '#0d7b34' if c.live_change_pct >= 1 else ('#c94545' if c.live_change_pct <= -1 else '#666') %}
            {% set lbg = '#e7f5ec' if c.live_change_pct >= 1 else ('#fdecec' if c.live_change_pct <= -1 else '#f0f0f0') %}
            {% set big = c.live_change_pct >= 3 or c.live_change_pct <= -3 %}
            <span style="padding:2px 8px; border-radius:3px; background:{{ lbg }}; color:{{ lc }}; font-weight:700; {% if big %}border:2px solid {{ lc }};{% endif %}">
              LIVE ${{ "%.2f"|format(c.live_spot) }} ({{ "%+.2f"|format(c.live_change_pct) }}%)
              {% if big %}&middot; verify before entry{% endif %}
            </span>
          {% endif %}
          {% if c.market_cap %}<span>Mcap ${{ "%.2f"|format(c.market_cap/1e9) }}B</span>{% endif %}
          {% if c.dollar_volume_20d %}<span>$Vol ${{ "%.1f"|format(c.dollar_volume_20d/1e6) }}M</span>{% endif %}
          {% if c.short_pct_float %}<span>SI {{ "%.0f"|format(c.short_pct_float) }}%</span>{% endif %}
        </div>
        {% for cat in c.catalysts[:2] %}
          <div class="catalyst-line">
            <strong>{{ cat.label }}</strong> &middot; {{ cat.details }}
          </div>
        {% endfor %}
        {% if c.risk_audit and c.risk_audit.flags %}
          <div class="risk-row">
            <strong>Risk:</strong>
            {% for flag in c.risk_audit.flags %}
              <span class="risk-chip {{ 'high' if flag.severity == 'HIGH' else '' }}">{{ flag.label }}</span>
            {% endfor %}
          </div>
        {% endif %}
        {% if c.insider_depth and c.insider_depth.signals %}
          <div class="insider-row">
            <strong>Insider:</strong> {{ c.insider_depth.signals|join(' &middot; ') }}
          </div>
        {% endif %}
        {% if c.options_check and c.options_check.implied_move_1d_pct %}
          <div class="options-row">
            <strong>Options:</strong> {{ c.options_check.label }}
          </div>
        {% endif %}
        {% if c.components.llm.reasoning %}
          <div class="llm-box">
            <strong>LLM:</strong> {{ c.components.llm.reasoning }}
          </div>
        {% endif %}
        <div class="breakdown">
        </div>
      </div>
    {% endfor %}
  {% endif %}

  {% if not strong and not watch %}
    <div class="empty">No catalysts ranked above the percentile thresholds today. {{ scored_total }} candidates evaluated.</div>
  {% endif %}


  {% if bear_picks %}
    <h2 style="margin-top:30px; padding-top:18px; border-top:3px solid #c94545; color:#7f1d1d;">Bearish Catalyst Plays</h2>
    <div style="font-size:12px; color:#555; margin-bottom:14px;">
      Negative catalyst names: going concern flags, missed-and-guided-down earnings, FDA rejections, dilutive offerings, lawsuits, exec departures. These are PUT-SIDE plays (sell short or buy puts). Same risk-management discipline applies.
    </div>
    {% for c in bear_picks %}
      <div style="border:2px solid #c94545; border-left-width:6px; background:#fef9f9; border-radius:6px; padding:12px 16px; margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
          <div>
            <span style="font-size:15px; font-weight:700;">{{ c.ticker }}</span>
            <span style="font-size:11px; color:#555;">{{ (c.name or c.company)[:35] }}</span>
            <span style="font-size:10px; padding:2px 8px; border-radius:3px; background:#c94545; color:#fff; font-weight:700;">BEAR &middot; T{{ c.catalyst_tier }} &middot; SCORE {{ "%.0f"|format(c.score) }}</span>
          </div>
          <div style="font-size:11px; color:#666;">{{ c.sector or '' }}</div>
        </div>
        <div style="font-size:11px; color:#444; margin-bottom:4px;">
          Price ${{ "%.2f"|format(c.price) if c.price else "n/a" }}
          {% if c.live_spot %}
            {% set lc = '#0d7b34' if c.live_change_pct >= 1 else ('#c94545' if c.live_change_pct <= -1 else '#666') %}
            &middot; <span style="color:{{ lc }}; font-weight:600;">LIVE ${{ "%.2f"|format(c.live_spot) }} ({{ "%+.2f"|format(c.live_change_pct) }}%)</span>
          {% endif %}
          {% if c.market_cap %} &middot; Mcap ${{ "%.2f"|format(c.market_cap/1e9) }}B{% endif %}
          {% if c.short_pct_float %} &middot; SI {{ "%.0f"|format(c.short_pct_float) }}%{% endif %}
        </div>
        {% for cat in c.catalysts[:3] %}
          <div style="font-size:11px; color:#7f1d1d; margin:3px 0;">
            <strong>{{ cat.label }}</strong> &middot; {{ cat.details }}
          </div>
        {% endfor %}
        {% if c.short_pct_float and c.short_pct_float >= 25 %}
          <div style="margin-top:6px; padding:6px 10px; background:#fef2f2; border-left:3px solid #c94545; border-radius:3px; font-size:11px; color:#7f1d1d;">
            <strong>WARNING:</strong> SI {{ "%.0f"|format(c.short_pct_float) }}% is squeeze risk - puts may not work even on bad news
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  <div class="footer">catalyst-watchlist v2 &middot; multi-source scoring &middot; LLM-read of actual filings &middot; bull + bear catalysts</div>
</div>
</body>
</html>"""


def render_catalyst_email(scan, max_strong=20, max_watch=20):
    candidates = scan.get("candidates", [])
    strong_all = sorted(
        [c for c in candidates if c.get("bucket") == "STRONG"],
        key=lambda c: c["score"], reverse=True,
    )
    watch_all = sorted(
        [c for c in candidates if c.get("bucket") == "WATCH"],
        key=lambda c: c["score"], reverse=True,
    )
    strong = [c for c in strong_all if c.get("direction", "bull") == "bull"][:max_strong]
    watch = [c for c in watch_all if c.get("direction", "bull") == "bull"][:max_watch]
    bear_strong = [c for c in strong_all if c.get("direction") == "bear"][:max_strong]
    bear_watch = [c for c in watch_all if c.get("direction") == "bear"][:max_watch]
    bear_picks = (bear_strong + bear_watch)[:max_strong]

    try:
        from src.live_spot import enrich_with_live_spots
        enrich_with_live_spots(strong + watch + bear_picks)
    except Exception as e:
        print(f"  catalyst live_spot: failed: {type(e).__name__}: {e}")

    tmpl = Template(EMAIL_TEMPLATE)
    return tmpl.render(
        scan_date=scan.get("scan_date"),
        candidates_total=scan.get("candidates_total", 0),
        enriched_total=scan.get("enriched_total", 0),
        scored_total=scan.get("scored_total", 0),
        passed_cutoff=scan.get("passed_cutoff", 0),
        llm_graded=scan.get("llm_graded", 0),
        eodhd_calls=scan.get("eodhd_calls", 0),
        edgar_calls=scan.get("edgar_calls", 0),
        tracker_stats=scan.get("tracker_stats"),
        paper_stats=scan.get("paper_stats"),
        strong=strong,
        watch=watch,
        bear_picks=bear_picks,
    )

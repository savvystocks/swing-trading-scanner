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
  <h1>Catalyst Watchlist v2 &mdash; {{ scan_date }}</h1>
  <div class="meta">Pre-close scan for tomorrow's overnight catalysts &middot; Multi-source scoring &middot; Universe: {{ candidates_total }} candidates &middot; Enriched: {{ enriched_total }} &middot; LLM-graded: {{ llm_graded }} &middot; STRONG: {{ strong|length }} &middot; WATCH: {{ watch|length }} &middot; EODHD: {{ eodhd_calls }} &middot; EDGAR: {{ edgar_calls }}</div>

  <div class="intro">
    <strong>How to use this email.</strong> The system is now strictly tuned for ONE play: <strong>buy at today's US close → catch tomorrow's overnight gap on a fresh catalyst</strong>. BUY signals require a SCHEDULED OVERNIGHT catalyst (earnings tomorrow / FDA decision tomorrow) on a stock that hasn't already run. Names with red CATALYST IN MOTION badge mean the move already started today — do not chase. PRIME ENTRY badge = overnight catalyst on a flat stock (the ideal setup).
    <br><br><em style="color:#866;">Probability is heuristic, not backtested. Real measured hit-rates build up in the tracker section as the system runs.</em>
  </div>

  {% if paper_stats and paper_stats.n > 0 %}
  <div class="legend" style="background:#f0fdf4; border-color:#86efac;">
    <h3 style="color:#14532d;">Paper trading P&amp;L (${{ "%.0f"|format(paper_stats.position_size_usd) }}/ticker, last {{ paper_stats.lookback_days }}d, n={{ paper_stats.n }} trades)</h3>
    <div class="legend-grid">
      <div class="legend-block">
        <div class="legend-title">Total P&amp;L</div>
        <div class="legend-row" style="font-size:18px; font-weight:700; color:{% if paper_stats.total_pnl_usd >= 0 %}#0d7b34{% else %}#c94545{% endif %};">${{ "%+.2f"|format(paper_stats.total_pnl_usd) }}</div>
        <div class="legend-row">ROI: <strong>{{ "%+.2f"|format(paper_stats.roi_pct) }}%</strong> on ${{ "%.0f"|format(paper_stats.capital_deployed_usd) }} deployed</div>
        <div class="legend-row">Fees deducted: ${{ "%.2f"|format(paper_stats.total_fees_usd) }} (FX 0.5% round trip assumed)</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Win rate &amp; sizing</div>
        <div class="legend-row"><strong>Wins:</strong> {{ paper_stats.wins }} ({{ paper_stats.win_rate_pct }}%) &middot; <strong>Losses:</strong> {{ paper_stats.losses }}</div>
        <div class="legend-row"><strong>Avg win:</strong> {{ "%+.2f"|format(paper_stats.avg_win_pct) }}% &middot; <strong>Avg loss:</strong> {{ "%+.2f"|format(paper_stats.avg_loss_pct) }}%</div>
        <div class="legend-row"><strong>Biggest win:</strong> ${{ "%+.2f"|format(paper_stats.biggest_win_usd) }} &middot; <strong>Biggest loss:</strong> ${{ "%+.2f"|format(paper_stats.biggest_loss_usd) }}</div>
      </div>
    </div>
    <div style="font-size:10px; color:#555; margin-top:8px;"><em>Simulated $100 entry per BUY signal at close, exit half at T1 / rest at T2 / stop / next-day close. Assumes Trading 212-style 0% commissions + 0.5% FX spread round trip. Real broker fees may differ.</em></div>
  </div>
  {% endif %}

  {% if tracker_stats and tracker_stats.BUY and tracker_stats.BUY.n > 0 %}
  <div class="legend" style="background:#f0fdf4; border-color:#bbf7d0;">
    <h3 style="color:#166534;">Real-money tracker (last {{ tracker_stats.lookback_days }}d, n={{ tracker_stats.total_measured }})</h3>
    <div class="legend-grid">
      {% if tracker_stats.BUY %}
      <div class="legend-block">
        <div class="legend-title" style="color:#0d7b34;">BUY signal outcomes (n={{ tracker_stats.BUY.n }})</div>
        <div class="legend-row"><strong>Hit T1:</strong> {{ tracker_stats.BUY.hit_t1_pct }}% &middot; <strong>Hit T2:</strong> {{ tracker_stats.BUY.hit_t2_pct }}% &middot; <strong>Hit stop:</strong> {{ tracker_stats.BUY.hit_stop_pct }}%</div>
        <div class="legend-row"><strong>Gap up next day:</strong> {{ tracker_stats.BUY.gap_up_pct }}% &middot; <strong>Avg high:</strong> {{ "%+.2f"|format(tracker_stats.BUY.avg_next_high_pct) }}% &middot; <strong>Avg close:</strong> {{ "%+.2f"|format(tracker_stats.BUY.avg_next_close_pct) }}%</div>
      </div>
      {% endif %}
      {% if tracker_stats.WATCH %}
      <div class="legend-block">
        <div class="legend-title" style="color:#0052cc;">WATCH signal outcomes (n={{ tracker_stats.WATCH.n }})</div>
        <div class="legend-row"><strong>Hit T1:</strong> {{ tracker_stats.WATCH.hit_t1_pct }}% &middot; <strong>Hit T2:</strong> {{ tracker_stats.WATCH.hit_t2_pct }}% &middot; <strong>Hit stop:</strong> {{ tracker_stats.WATCH.hit_stop_pct }}%</div>
        <div class="legend-row"><strong>Gap up next day:</strong> {{ tracker_stats.WATCH.gap_up_pct }}% &middot; <strong>Avg high:</strong> {{ "%+.2f"|format(tracker_stats.WATCH.avg_next_high_pct) }}% &middot; <strong>Avg close:</strong> {{ "%+.2f"|format(tracker_stats.WATCH.avg_next_close_pct) }}%</div>
      </div>
      {% endif %}
    </div>
  </div>
  {% else %}
  <div class="intro" style="background:#f0f7ff; border-color:#93c5fd;">
    <strong>Tracker building up.</strong> Real-money outcome stats appear here once the scanner has accumulated measured next-day results from prior BUY/WATCH signals. Today's predictions are saved and will be measured tomorrow.
  </div>
  {% endif %}

  <div class="legend">
    <h3>Score components reference (each ticker is graded across all of these)</h3>
    <div class="legend-grid">
      <div class="legend-block">
        <div class="legend-title">Catalyst Quality (max ~40pts)</div>
        <div class="legend-row">Primary catalyst tier × 8 + secondary stack at 25%. S = exceptional, A = strong, B = moderate, C = lower-prob, D = speculative.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">LLM Grade (max 30pts)</div>
        <div class="legend-row">Claude reads the actual catalyst content + recent news, grades 0-10 for next-day bullish strength. Considers deal size, premium, dilution, surprise factor.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Liquidity Setup (max 25pts)</div>
        <div class="legend-row">Dollar volume, market cap sweet spot ($200M-$5B), trend vs 200dMA, institutional ownership, short interest squeeze fuel.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">News Sentiment (max 15pts)</div>
        <div class="legend-row">Tone of last 7 days of headlines via keyword scoring. Positive = beat / approval / win / surge. Negative = miss / lawsuit / dilution / delay.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Pre-event Drift (range -15 to +10pts)</div>
        <div class="legend-row">5-day price ROC. For SCHEDULED events with drift &lt;15% = positive flow, +10pts. Drift 15-25% = PRE-PRICED warning (-5pts, sell-the-news risk). Drift &gt;25% = -10pts. For POST-EVENT catalysts already filed: drift &gt;8% = EXTENDED warning, -8 to -15pts.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Historical Reaction (max 10pts)</div>
        <div class="legend-row">For earnings catalysts: median next-day move of last 4 earnings reports. Companies with consistent positive reactions are more reliable.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Catalyst Freshness (max 5pts)</div>
        <div class="legend-row">Hours since the 8-K was filed. Fresh = more alpha left. Older filings may have already been priced in.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Peer Confirmation (max 5pts)</div>
        <div class="legend-row">3+ peers in same sector also have catalysts = sector wave. Confirms the play is not isolated noise.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Confidence label</div>
        <div class="legend-row"><strong>HIGH</strong> = 5+ components positive. <strong>MEDIUM</strong> = 3-4. <strong>LOW</strong> = 1-2. The label indicates how many independent sources agree on the bullish call.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Red Flags (deductions)</div>
        <div class="legend-row">Going-concern language (-8), recent S-3 shelf / dilution (-4). Names with red flags can still score if other signals are strong, but will be downgraded.</div>
      </div>
    </div>
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
        {% if c.buy_signal and c.buy_signal.entry_price %}
          <div class="trade-row">
            <span>Entry <strong>${{ "%.2f"|format(c.buy_signal.entry_price) }}</strong></span>
            {% if c.buy_signal.stop_price %}<span>Stop <strong>${{ "%.2f"|format(c.buy_signal.stop_price) }}</strong> ({{ "%.1f"|format(c.buy_signal.stop_pct) }}%)</span>{% endif %}
            {% if c.buy_signal.target_1_price %}<span>T1 <strong>${{ "%.2f"|format(c.buy_signal.target_1_price) }}</strong> (+{{ "%.1f"|format(c.buy_signal.expected_move_low_pct) }}%)</span>{% endif %}
            {% if c.buy_signal.target_2_price %}<span>T2 <strong>${{ "%.2f"|format(c.buy_signal.target_2_price) }}</strong> (+{{ "%.1f"|format(c.buy_signal.expected_move_high_pct) }}%)</span>{% endif %}
            {% if c.buy_signal.atr_pct %}<span style="color:#888;">ATR {{ "%.1f"|format(c.buy_signal.atr_pct) }}%</span>{% endif %}
          </div>
        {% endif %}
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
        <div class="breakdown">
          <div class="bd-item"><span class="bd-label">Catalyst tier</span><span class="bd-pts pos">+{{ "%.0f"|format(c.components.catalyst_quality.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">LLM grade</span><span class="bd-pts {% if c.components.llm.points > 0 %}pos{% elif c.components.llm.points < 0 %}neg{% endif %}">{{ "%+.0f"|format(c.components.llm.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Liquidity</span><span class="bd-pts {% if c.components.liquidity_setup.points > 0 %}pos{% elif c.components.liquidity_setup.points < 0 %}neg{% endif %}">{{ "%+.0f"|format(c.components.liquidity_setup.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">News</span><span class="bd-pts {% if c.components.news.points > 0 %}pos{% endif %}">{{ "%+.1f"|format(c.components.news.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Drift 5d</span><span class="bd-pts {% if c.components.drift.points > 0 %}pos{% elif c.components.drift.points < 0 %}neg{% endif %}">{{ "%+.1f"|format(c.components.drift.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">History</span><span class="bd-pts {% if c.components.historical.points > 0 %}pos{% elif c.components.historical.points < 0 %}neg{% endif %}">{{ "%+.1f"|format(c.components.historical.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Freshness</span><span class="bd-pts {% if c.components.freshness.points > 0 %}pos{% endif %}">{{ "%+.1f"|format(c.components.freshness.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Peers</span><span class="bd-pts {% if c.components.peer.points > 0 %}pos{% endif %}">{{ "%+.1f"|format(c.components.peer.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Timing</span><span class="bd-pts {% if c.components.timing and c.components.timing.points > 0 %}pos{% elif c.components.timing and c.components.timing.points < 0 %}neg{% endif %}">{{ "%+.1f"|format(c.components.timing.points if c.components.timing else 0) }}</span></div>
          <div class="bd-item"><span class="bd-label">Red flags</span><span class="bd-pts {% if c.components.red_flags.points < 0 %}neg{% endif %}">{{ "%+.0f"|format(c.components.red_flags.points) }}</span></div>
        </div>
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
        {% if c.buy_signal and c.buy_signal.entry_price %}
          <div class="trade-row">
            <span>Entry <strong>${{ "%.2f"|format(c.buy_signal.entry_price) }}</strong></span>
            {% if c.buy_signal.stop_price %}<span>Stop <strong>${{ "%.2f"|format(c.buy_signal.stop_price) }}</strong></span>{% endif %}
            {% if c.buy_signal.target_1_price %}<span>T1 <strong>${{ "%.2f"|format(c.buy_signal.target_1_price) }}</strong></span>{% endif %}
            {% if c.buy_signal.target_2_price %}<span>T2 <strong>${{ "%.2f"|format(c.buy_signal.target_2_price) }}</strong></span>{% endif %}
          </div>
        {% endif %}
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
          <div class="bd-item"><span class="bd-label">Catalyst</span><span class="bd-pts pos">+{{ "%.0f"|format(c.components.catalyst_quality.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">LLM</span><span class="bd-pts {% if c.components.llm.points > 0 %}pos{% endif %}">{{ "%+.0f"|format(c.components.llm.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Liquidity</span><span class="bd-pts {% if c.components.liquidity_setup.points > 0 %}pos{% elif c.components.liquidity_setup.points < 0 %}neg{% endif %}">{{ "%+.0f"|format(c.components.liquidity_setup.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">News</span><span class="bd-pts {% if c.components.news.points > 0 %}pos{% endif %}">{{ "%+.1f"|format(c.components.news.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Drift</span><span class="bd-pts {% if c.components.drift.points > 0 %}pos{% elif c.components.drift.points < 0 %}neg{% endif %}">{{ "%+.1f"|format(c.components.drift.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">History</span><span class="bd-pts {% if c.components.historical.points > 0 %}pos{% elif c.components.historical.points < 0 %}neg{% endif %}">{{ "%+.1f"|format(c.components.historical.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Fresh</span><span class="bd-pts {% if c.components.freshness.points > 0 %}pos{% endif %}">{{ "%+.1f"|format(c.components.freshness.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Peers</span><span class="bd-pts {% if c.components.peer.points > 0 %}pos{% endif %}">{{ "%+.1f"|format(c.components.peer.points) }}</span></div>
          <div class="bd-item"><span class="bd-label">Timing</span><span class="bd-pts {% if c.components.timing and c.components.timing.points > 0 %}pos{% elif c.components.timing and c.components.timing.points < 0 %}neg{% endif %}">{{ "%+.1f"|format(c.components.timing.points if c.components.timing else 0) }}</span></div>
          <div class="bd-item"><span class="bd-label">Red flags</span><span class="bd-pts {% if c.components.red_flags.points < 0 %}neg{% endif %}">{{ "%+.0f"|format(c.components.red_flags.points) }}</span></div>
        </div>
      </div>
    {% endfor %}
  {% endif %}

  {% if not strong and not watch %}
    <div class="empty">No catalysts ranked above the percentile thresholds today. {{ scored_total }} candidates evaluated.</div>
  {% endif %}

  {% if long_term_holds %}
    <h2 style="margin-top:32px; padding-top:18px; border-top:3px solid #0d7b34; color:#14532d;">Long-Term Hold Watchlist (Top 20 1-Year Performers)</h2>
    <div style="font-size:12px; color:#555; margin-bottom:14px;">
      The 20 highest 1-year total return names (May 2025 - May 2026), riding ongoing themes — AI infrastructure / data center power / memory & storage / semicap / cycle plays. Always tracked daily for fresh signals even when no other catalyst fires. These are core long-term holds; trim only on theme exhaustion or single-stock fundamental break, not on weekly noise.
    </div>
    <table style="width:100%; font-size:11px; border-collapse:collapse; margin-bottom:18px;">
      <thead><tr style="background:#dcfce7;">
        <th align="left" style="padding:6px 8px;">Ticker</th>
        <th align="left" style="padding:6px 8px;">Name</th>
        <th align="right" style="padding:6px 8px;">Price</th>
        <th align="right" style="padding:6px 8px;">vs scan</th>
        <th align="left" style="padding:6px 8px;">Sector</th>
        <th align="left" style="padding:6px 8px;">Active catalysts</th>
        <th align="right" style="padding:6px 8px;">Score</th>
        <th align="left" style="padding:6px 8px;">Bucket</th>
      </tr></thead>
      <tbody>
      {% for h in long_term_holds %}
        <tr style="border-bottom:1px solid #d1fae5;">
          <td style="padding:5px 8px; font-weight:700;">{{ h.ticker }}</td>
          <td style="padding:5px 8px; color:#444;">{{ (h.name or '')[:24] }}</td>
          <td align="right" style="padding:5px 8px;">{% if h.live_spot %}<strong>${{ "%.2f"|format(h.live_spot) }}</strong>{% elif h.price %}${{ "%.2f"|format(h.price) }}{% else %}-{% endif %}</td>
          <td align="right" style="padding:5px 8px; color:{% if h.live_change_pct and h.live_change_pct >= 0 %}#0d7b34{% elif h.live_change_pct %}#c94545{% else %}#888{% endif %};">{% if h.live_change_pct is defined and h.live_change_pct is not none %}{{ "%+.2f"|format(h.live_change_pct) }}%{% else %}-{% endif %}</td>
          <td style="padding:5px 8px; color:#666; font-size:10px;">{{ (h.sector or '')[:18] }}</td>
          <td style="padding:5px 8px; color:#5a3690; font-size:10px;">{% for c in h.catalysts[:3] %}<span style="display:inline-block; padding:1px 5px; margin:1px 2px 0 0; background:#f3f0fa; border-radius:3px;">{{ c.key }}</span>{% endfor %}{% if not h.catalysts %}<span style="color:#999;">-</span>{% endif %}</td>
          <td align="right" style="padding:5px 8px; font-weight:600;">{{ "%.0f"|format(h.score or 0) }}</td>
          <td style="padding:5px 8px; font-size:10px;"><span style="padding:1px 6px; border-radius:3px; background:{% if h.bucket == 'STRONG' %}#0d7b34{% elif h.bucket == 'WATCH' %}#4a90e2{% else %}#888{% endif %}; color:#fff;">{{ h.bucket or 'TRACK' }}</span></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
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


TOP_20_LONG_TERM_HOLDS = (
    "SNDK", "LITE", "WDC", "STX", "CIEN", "MU", "SATS", "INTC", "COHR", "TER",
    "FIX", "AMD", "GLW", "LRCX", "VRT", "ALB", "WBD", "CAT", "GEV", "AMAT",
)


def render_catalyst_email(scan, max_strong=20, max_watch=20):
    candidates = scan.get("candidates", [])
    all_scored = scan.get("all_scored", [])
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

    by_ticker = {c.get("ticker"): c for c in all_scored if c.get("ticker")}
    long_term_holds = []
    for tk in TOP_20_LONG_TERM_HOLDS:
        c = by_ticker.get(tk)
        if c:
            long_term_holds.append(c)
        else:
            long_term_holds.append({"ticker": tk, "name": "", "sector": "", "price": None, "catalysts": [], "score": 0, "bucket": "TRACK"})

    try:
        from src.live_spot import enrich_with_live_spots
        enrich_with_live_spots(strong + watch + bear_picks + long_term_holds)
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
        long_term_holds=long_term_holds,
    )

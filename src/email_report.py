import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; color:#222; }
  .wrap { max-width:960px; margin:0 auto; background:#fff; padding:28px 32px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
  h1 { font-size:22px; margin:0 0 6px; }
  .meta { color:#666; font-size:13px; margin-bottom:20px; }
  .regime { background:#e8f1ff; padding:10px 14px; border-radius:6px; margin-bottom:18px; font-size:13px; }
  .regime strong { color:#0052cc; }
  h2 { font-size:16px; margin:28px 0 10px; border-bottom:2px solid #eee; padding-bottom:6px; }
  .card { border:1px solid #e5e5e5; border-radius:8px; padding:16px 18px; margin-bottom:14px; background:#fdfdfd; }
  .card.tier5 { border-left:6px solid #0d7b34; }
  .card.tier4 { border-left:6px solid #1a9850; }
  .card.tier3 { border-left:6px solid #4a90e2; }
  .card.tier0 { border-left:6px solid #c94545; background:#fef7f7; }
  .card-head { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px; }
  .card-head-left { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .sector-badge { display:inline-block; padding:2px 8px; border-radius:3px; font-size:10px; font-weight:600; background:#eef2f7; color:#384766; text-transform:uppercase; letter-spacing:0.3px; }
  .description { font-size:12px; color:#555; line-height:1.4; margin:6px 0 10px; padding:8px 10px; background:#fafafa; border-left:3px solid #e0e0e0; }
  .sector-summary { margin:16px 0 22px; padding:14px 16px; background:#f7f9fc; border-radius:6px; font-size:12px; }
  .sector-summary h3 { margin:0 0 8px; font-size:13px; color:#384766; }
  .sector-summary-grid { display:flex; flex-wrap:wrap; gap:6px 10px; }
  .sector-chip { background:#fff; padding:4px 10px; border-radius:12px; border:1px solid #e0e0e0; font-size:11px; }
  .sector-chip strong { color:#0052cc; margin-right:4px; }
  .sector-perf { margin:16px 0 22px; }
  .sector-perf h3 { margin:0 0 8px; font-size:13px; color:#384766; }
  table.sectors { width:100%; border-collapse:collapse; font-size:11px; background:#fff; border-radius:6px; overflow:hidden; border:1px solid #e5e5e5; }
  table.sectors th { background:#f4f6fa; text-align:left; padding:7px 8px; border-bottom:1px solid #ddd; font-weight:600; color:#384766; }
  table.sectors td { padding:6px 8px; border-bottom:1px solid #f0f0f0; }
  table.sectors td.num { text-align:right; font-variant-numeric:tabular-nums; }
  .pos { color:#0d7b34; }
  .neg { color:#c94545; }
  .outlook { display:inline-block; padding:2px 7px; border-radius:3px; font-weight:600; font-size:10px; }
  .o-LEADING { background:#0d7b34; color:#fff; }
  .o-STRONG { background:#1a9850; color:#fff; }
  .o-NEUTRAL { background:#999; color:#fff; }
  .o-LAGGING { background:#e67e22; color:#fff; }
  .o-WEAK { background:#c94545; color:#fff; }
  .conv-box { display:inline-flex; align-items:center; gap:8px; padding:3px 10px; border-radius:4px; background:#f0f5ff; border:1px solid #c5d8ff; font-size:11px; }
  .conv-box .score { font-weight:700; color:#0052cc; font-size:13px; }
  .stress-dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:3px; vertical-align:middle; }
  .stress-PASS { background:#1a9850; }
  .stress-WARN { background:#f0ad4e; }
  .stress-FAIL { background:#c94545; }
  .stress-UNKNOWN { background:#ccc; }
  .conv-pick-card { border:2px solid #0052cc; background:linear-gradient(180deg, #fafcff 0%, #fff 100%); border-radius:8px; padding:14px 18px; margin-bottom:12px; }
  .conv-pick-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; font-size:13px; }
  .conv-pick-head .ticker { font-size:16px; font-weight:700; }
  .conv-pick-breakdown { display:grid; grid-template-columns:repeat(4, 1fr); gap:4px 12px; font-size:10px; color:#555; margin-top:6px; }
  .conv-pick-breakdown .k { color:#888; }
  .conv-pick-breakdown .v { font-weight:600; color:#333; }
  .stress-row { font-size:11px; color:#555; margin-top:6px; padding-top:6px; border-top:1px dashed #e5e5e5; }
  .options-box { margin-top:10px; padding:10px 12px; background:#fffbe8; border:1px solid #f0d969; border-radius:6px; font-size:12px; }
  .options-box h4 { margin:0 0 6px; font-size:12px; color:#6a5300; text-transform:uppercase; letter-spacing:0.5px; }
  .options-box .row1 { font-weight:600; color:#444; margin-bottom:3px; }
  .options-box .row2 { color:#555; margin-bottom:3px; }
  .options-box .payoff { color:#0d7b34; font-weight:600; margin-top:4px; }
  .tier-badge { display:inline-block; padding:3px 10px; border-radius:4px; font-weight:600; font-size:11px; color:#fff; }
  .t5 { background:#0d7b34; }
  .t4 { background:#1a9850; }
  .t3 { background:#4a90e2; }
  .t2 { background:#999; }
  .t0 { background:#c94545; }
  .ticker { font-weight:700; font-size:17px; color:#111; }
  .name { color:#666; font-size:13px; }
  .price-row { font-size:13px; color:#333; margin-bottom:12px; }
  .price-row strong { color:#0052cc; font-size:15px; }
  .price-row span { margin-right:14px; }
  .pillar-grid { display:grid; grid-template-columns:repeat(2, 1fr); gap:6px 20px; font-size:12px; margin-top:10px; }
  .pillar-row { display:flex; align-items:flex-start; gap:8px; padding:3px 0; }
  .verdict { display:inline-block; width:52px; font-weight:600; font-size:10px; padding:2px 6px; border-radius:3px; text-align:center; flex-shrink:0; }
  .v-PASS, .v-PASS_BONUS { background:#d4edda; color:#155724; }
  .v-PARTIAL { background:#fff3cd; color:#856404; }
  .v-FAIL { background:#f8d7da; color:#721c24; }
  .v-UNAVAILABLE { background:#e0e0e0; color:#555; }
  .pillar-label { font-weight:600; color:#333; min-width:36px; }
  .pillar-summary { color:#666; font-size:11px; }
  .gate-row { font-size:11px; color:#555; margin-top:6px; padding-top:8px; border-top:1px dashed #e5e5e5; }
  .gate-row strong { color:#333; }
  table.summary { width:100%; border-collapse:collapse; font-size:12px; margin-top:6px; }
  table.summary th { background:#f8f8f8; text-align:left; padding:6px 8px; border-bottom:1px solid #ddd; font-weight:600; font-size:11px; }
  table.summary td { padding:6px 8px; border-bottom:1px solid #f0f0f0; }
  .empty { text-align:center; color:#666; font-style:italic; padding:24px; background:#fafafa; border-radius:6px; }
  .footer { margin-top:30px; font-size:11px; color:#999; text-align:center; }
  .legend { background:#f7f9fc; border:1px solid #e0e6ef; border-radius:8px; padding:14px 16px; margin:18px 0 22px; font-size:11px; }
  .legend h3 { margin:0 0 10px; font-size:13px; color:#384766; }
  .legend-grid { display:grid; grid-template-columns:repeat(2, 1fr); gap:14px 20px; }
  .legend-block { background:#fff; border:1px solid #e5e9f0; border-radius:6px; padding:10px 12px; }
  .legend-title { font-weight:700; color:#0052cc; font-size:11px; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.4px; }
  .legend-row { font-size:11px; color:#444; line-height:1.5; padding:2px 0; }
  .lg-swatch { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:middle; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Swing Trading Scan — {{ scan_date }}</h1>
  <div class="meta">Universe: {{ universe_size }} &middot; Fast-filter survivors: {{ fast_survivors }} &middot; Fully scored: {{ scored_total }} &middot; API calls: {{ api_calls }}</div>

  <div class="regime">
    Market Regime: <strong>{{ regime }}</strong> &middot; VIX {{ vix }}
    {% if breadth %} &middot; Breadth: <strong>{{ breadth.regime|upper }}</strong> ({{ breadth.pct_above_200 }}% above 200d, {{ breadth.pct_above_50 }}% above 50d){% endif %}
  </div>

  {% if sector_performance %}
    <div class="sector-perf">
      <h3>Sector Performance &amp; Outlook</h3>
      <table class="sectors">
        <thead>
          <tr>
            <th>Sector</th>
            <th class="num">1D</th>
            <th class="num">5D</th>
            <th class="num">1M</th>
            <th class="num">3M</th>
            <th class="num">vs SPY (1M)</th>
            <th>Outlook</th>
          </tr>
        </thead>
        <tbody>
          {% for s in sector_performance %}
            <tr>
              <td><strong>{{ s.sector }}</strong></td>
              <td class="num {% if s.ret_1d and s.ret_1d > 0 %}pos{% elif s.ret_1d and s.ret_1d < 0 %}neg{% endif %}">{% if s.ret_1d is not none %}{{ "%+.1f"|format(s.ret_1d) }}%{% else %}-{% endif %}</td>
              <td class="num {% if s.ret_5d and s.ret_5d > 0 %}pos{% elif s.ret_5d and s.ret_5d < 0 %}neg{% endif %}">{% if s.ret_5d is not none %}{{ "%+.1f"|format(s.ret_5d) }}%{% else %}-{% endif %}</td>
              <td class="num {% if s.ret_1m and s.ret_1m > 0 %}pos{% elif s.ret_1m and s.ret_1m < 0 %}neg{% endif %}">{% if s.ret_1m is not none %}{{ "%+.1f"|format(s.ret_1m) }}%{% else %}-{% endif %}</td>
              <td class="num {% if s.ret_3m and s.ret_3m > 0 %}pos{% elif s.ret_3m and s.ret_3m < 0 %}neg{% endif %}">{% if s.ret_3m is not none %}{{ "%+.1f"|format(s.ret_3m) }}%{% else %}-{% endif %}</td>
              <td class="num {% if s.rs_vs_spy and s.rs_vs_spy > 0 %}pos{% elif s.rs_vs_spy and s.rs_vs_spy < 0 %}neg{% endif %}">{% if s.rs_vs_spy is not none %}{{ "%+.1f"|format(s.rs_vs_spy) }}%{% else %}-{% endif %}</td>
              <td><span class="outlook o-{{ s.outlook }}">{{ s.outlook }}</span></td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% endif %}

  <div class="legend">
    <h3>How to read this email — priority guide</h3>
    <div class="legend-grid">
      <div class="legend-block">
        <div class="legend-title">Lane priority</div>
        <div class="legend-row"><span class="lg-swatch" style="background:#0d7b34;"></span><strong>Lane A — Run With It:</strong> high-tier + high conviction. Liquid mega/large cap. Hold weeks-months, size up.</div>
        <div class="legend-row"><span class="lg-swatch" style="background:#0052cc;"></span><strong>Lane B — Catch It Early:</strong> early-stage signals firing before price moves. Smaller caps. Hold months, best option leverage.</div>
        <div class="legend-row"><span class="lg-swatch" style="background:#c94545;"></span><strong>Lane C — Catalyst Today:</strong> post-earnings momentum play. Short horizon 0-5 days.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Stress dot (next to conviction)</div>
        <div class="legend-row"><span class="stress-dot stress-PASS"></span><strong>Green = PASS:</strong> clean tape, low beta, few gaps, shallow historical drawdowns. Stops will hold.</div>
        <div class="legend-row"><span class="stress-dot stress-WARN"></span><strong>Amber = WARN:</strong> borderline on beta/gaps/drawdown. Tape can be twitchy, stops may slip.</div>
        <div class="legend-row"><span class="stress-dot stress-FAIL"></span><strong>Red = FAIL:</strong> high gap frequency or big historical drawdowns. Expect stops to get skipped overnight.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Scores</div>
        <div class="legend-row"><strong>OPP (Opportunity, 0-100):</strong> master ranker. Combines tier (35) + conviction (30) + early signals (25) + stress (10) + sector maturity adj.</div>
        <div class="legend-row"><strong>CONV (Conviction, 0-100):</strong> RS %ile, up/down vol, earnings accel, sector leadership, pivot proximity, analyst upside, weekly trend, FCF quality.</div>
        <div class="legend-row"><strong>Tier (T0-T5):</strong> pillars passed. T5 = full setup, T4 = near-full, T0 = hard gate failed (no trade).</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Early signals (Lane B detectors)</div>
        <div class="legend-row"><strong>Pocket Pivot:</strong> up-day volume beats largest down-vol in 10 days. Stealth institutional accumulation.</div>
        <div class="legend-row"><strong>Base Quality X/10:</strong> depth + tightness + volume dry-up + proximity to high. 7+ is textbook Minervini.</div>
        <div class="legend-row"><strong>Insider Cluster:</strong> 2+ unique insider buyers in last 30 days (US only).</div>
        <div class="legend-row"><strong>Rev Accel:</strong> revenue QoQ ≥8% AND YoY ≥15% AND ≥1.5× prior 3Q average.</div>
        <div class="legend-row"><strong>Earnings Turn:</strong> last quarter beat estimates after prior quarter missed &lt;-5%.</div>
        <div class="legend-row"><strong>Peer Lag:</strong> laggard inside a hot sub-industry — rotation target.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Sector maturity tag</div>
        <div class="legend-row"><span style="font-size:9px; padding:2px 5px; border-radius:3px; background:#0d7b34; color:#fff;">EARLY</span> <strong>Best entries</strong> — sector is leading but not extended.</div>
        <div class="legend-row"><span style="font-size:9px; padding:2px 5px; border-radius:3px; background:#f0ad4e; color:#fff;">MID</span> Still tradeable — some extension.</div>
        <div class="legend-row"><span style="font-size:9px; padding:2px 5px; border-radius:3px; background:#e67e22; color:#fff;">LATE</span> <strong>Caution</strong> — sector is ≥20% over 200d or up ≥50% 6m. Reversion risk.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Options plays (sent as separate email)</div>
        <div class="legend-row">You now receive <strong>two emails</strong> each scan: (1) this main scan report, (2) an options-only email with 9 priority plays bucketed by market cap.</div>
        <div class="legend-row">Bucket split: <strong>1 Mega</strong> (&gt;$200B) + <strong>3 Large</strong> ($10B-$200B) + <strong>4 Mid</strong> ($2B-$10B, sweet spot) + <strong>1 Early</strong> (&lt;$2B with Lane B signals).</div>
        <div class="legend-row">Chain source: Alpaca. Window: 14-50 DTE, delta 0.30-0.70, spread &lt; 40%.</div>
        <div class="legend-row"><strong>vol CHEAP:</strong> realized vol in bottom 30% of 1yr range — options undervalued, buy calls.</div>
        <div class="legend-row"><strong>vol FAIR/EXPENSIVE:</strong> mid-range / top 30% — premium rich, consider debit spreads.</div>
        <div class="legend-row"><strong>Skew bullish:</strong> calls more bid than puts — market positioning aligns with trade.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Pillar verdicts</div>
        <div class="legend-row"><span class="verdict v-PASS">PASS</span> Clean pillar.</div>
        <div class="legend-row"><span class="verdict v-PARTIAL">PARTIAL</span> Partial credit.</div>
        <div class="legend-row"><span class="verdict v-FAIL">FAIL</span> Pillar broken — but scoring still fine unless it's P1.</div>
        <div class="legend-row"><span class="verdict v-UNAVAILABLE">UNAVAIL</span> Data missing (e.g. P7 on LSE names).</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Action priority order</div>
        <div class="legend-row"><strong>1.</strong> Priority Options — 3 Big Cap + 3 Early at top of email, options yellow box.</div>
        <div class="legend-row"><strong>2.</strong> Lane A stock plays — high-tier, high-conviction core holdings. Green-dot first.</div>
        <div class="legend-row"><strong>3.</strong> Lane B stock plays — early signals firing, smaller size, longer hold.</div>
        <div class="legend-row"><strong>4.</strong> Lane C only on strong open/close and if earnings gap held overnight.</div>
        <div class="legend-row"><strong>5.</strong> Squeeze Watchlist — set buy-stops above upper band, trigger only on breakout.</div>
      </div>
    </div>
  </div>

  {% if sector_summary %}
    <div class="sector-summary">
      <h3>Actionable candidates by sector (Tier 4+)</h3>
      <div class="sector-summary-grid">
        {% for sec, count in sector_summary %}
          <span class="sector-chip"><strong>{{ count }}</strong>{{ sec }}</span>
        {% endfor %}
      </div>
    </div>
  {% endif %}

  {% if theme_summary %}
    <div class="sector-summary">
      <h3>Themes across Lane A &amp; B picks</h3>
      <div class="sector-summary-grid">
        {% for sec, tickers in theme_summary %}
          <span class="sector-chip"><strong>{{ tickers|length }}</strong>{{ sec }} <span style="color:#999; font-size:10px;">{{ tickers[:5]|join(', ') }}{% if tickers|length > 5 %}+{{ tickers|length - 5 }}{% endif %}</span></span>
        {% endfor %}
      </div>
    </div>
  {% endif %}

  {% if lane_a %}
    <h2 style="color:#0d7b34;">Lane A — Run With It ({{ lane_a|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">High-tier setups with strong conviction. Hold weeks to months. Size up.</div>
    {% for t in lane_a %}
      <div class="conv-pick-card">
        <div class="conv-pick-head">
          <div style="display:flex; align-items:center; gap:10px;">
            <span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">T{{ t.tier }}</span>
            <span class="ticker">{{ t.ticker }}</span>
            <span style="color:#555;">{{ t.name[:32] }}</span>
            {% if t.sector %}<span class="sector-badge">{{ t.sector }}</span>{% endif %}
            {% if t.sector_maturity and t.sector_maturity != 'N/A' %}<span style="font-size:9px; padding:2px 5px; border-radius:3px; background:{% if t.sector_maturity == 'LATE' %}#e67e22{% elif t.sector_maturity == 'MID' %}#f0ad4e{% else %}#0d7b34{% endif %}; color:#fff;">{{ t.sector_maturity }}</span>{% endif %}
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
            <span style="font-size:10px; color:#888;">OPP</span><span style="font-size:15px; font-weight:700; color:#0052cc;">{{ t.opportunity.score }}</span>
            {% if t.conviction %}<span style="font-size:10px; color:#888;">CONV</span><span style="font-size:13px; font-weight:600;">{{ t.conviction.score }}</span>{% endif %}
            {% if t.stress %}<span class="stress-dot stress-{{ t.stress.overall }}"></span>{% endif %}
          </div>
        </div>
        <div style="font-size:12px; color:#333; margin-bottom:4px;">
          Entry ${{ "%.2f"|format(t.price) }} &middot; Stop ${{ "%.2f"|format(t.stop_loss) }} &middot; Phase 1 ${{ "%.2f"|format(t.phase1_target) }} &middot; Runner ${{ "%.2f"|format(t.runner_target) }} &middot; R/R {{ t.risk_reward }}
        </div>
        {% if t.live_spot %}
          {% set live_color = '#0d7b34' if t.live_change_pct >= 1 else ('#c94545' if t.live_change_pct <= -1 else '#666') %}
          {% set live_bg = '#e7f5ec' if t.live_change_pct >= 1 else ('#fdecec' if t.live_change_pct <= -1 else '#f0f0f0') %}
          {% set big_move = t.live_change_pct >= 3 or t.live_change_pct <= -3 %}
          {% set chase = t.live_change_pct >= 5 %}
          <div style="font-size:11px; color:{{ live_color }}; margin:4px 0; padding:4px 8px; background:{{ live_bg }}; border-radius:4px; display:inline-block; {% if big_move %}border:2px solid {{ live_color }};{% endif %}">
            <strong>LIVE:</strong> ${{ "%.2f"|format(t.live_spot) }}
            {% if t.live_bid and t.live_ask %}(bid ${{ "%.2f"|format(t.live_bid) }}/ask ${{ "%.2f"|format(t.live_ask) }}){% endif %}
            ({{ "%+.2f"|format(t.live_change_pct) }}% vs scan close ${{ "%.2f"|format(t.price) }})
            {% if t.live_session %}&middot; <span style="font-size:10px; padding:1px 6px; border-radius:3px; background:#fff; color:#555;">{{ t.live_session }}{% if t.live_age_min and t.live_age_min > 30 %} - {{ "%.0f"|format(t.live_age_min) }}min ago{% endif %}</span>{% endif %}
            {% if chase %}<br><strong style="color:#7c2d12;">CHASE RISK: stock already up {{ "%+.1f"|format(t.live_change_pct) }}% - half size or wait for pullback</strong>
            {% elif big_move %}<br><strong>BIG MOVE - verify before entering</strong>{% endif %}
          </div>
          {% if t.options_trade and t.options_trade.breakeven_pct_from_live %}
            <div style="font-size:11px; color:#444; margin:2px 0 4px; padding:3px 8px; background:#f8f8f8; border-radius:3px; display:inline-block;">
              Breakeven from LIVE ${{ "%.2f"|format(t.options_trade.breakeven) }}: <strong>{{ "%+.2f"|format(t.options_trade.breakeven_pct_from_live) }}%</strong> needed (vs {{ "%+.2f"|format(t.options_trade.breakeven_pct_move) }}% from scan close)
            </div>
          {% endif %}
        {% endif %}
        {% if t.lane_b_signal_count and t.lane_b_signal_count > 0 %}
          <div style="font-size:11px; color:#0d7b34; margin-top:4px;">Early signals firing:
          {% if t.lane_b.pocket_pivot.fired %}[Pocket Pivot] {% endif %}
          {% if t.lane_b.base_quality.fired %}[Base Quality {{ t.lane_b.base_quality.score }}/10] {% endif %}
          {% if t.lane_b.insider_cluster.fired %}[Insider Cluster {{ t.lane_b.insider_cluster.buyer_count }}x] {% endif %}
          {% if t.lane_b.revenue_acceleration.fired %}[Rev Accel {{ t.lane_b.revenue_acceleration.latest_qoq_pct }}% QoQ] {% endif %}
          {% if t.lane_b.earnings_turn.fired %}[Earnings Turn] {% endif %}
          {% if t.lane_b.peer_pack.fired %}[Peer Pack Laggard] {% endif %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  {% if lane_b %}
    <h2 style="color:#0052cc;">Lane B — Catch It Early ({{ lane_b|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">Early-stage opportunities — institutional footprints present but price hasn't moved yet. These are the setups BEFORE they become Lane A. Hold months.</div>
    <table class="summary">
      <thead><tr><th>Ticker</th><th>Name</th><th>T</th><th>Opp</th><th>Sector</th><th>Maturity</th><th>Signals firing</th><th>Entry</th></tr></thead>
      <tbody>
        {% for t in lane_b %}
          <tr>
            <td><strong>{{ t.ticker }}</strong></td>
            <td>{{ t.name[:22] }}</td>
            <td><span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">T{{ t.tier }}</span></td>
            <td><strong style="color:#0052cc;">{{ t.opportunity.score }}</strong></td>
            <td style="font-size:10px;">{{ (t.sector or '-')[:16] }}</td>
            <td style="font-size:10px;">{{ t.sector_maturity or '-' }}</td>
            <td style="font-size:10px;">
              {% if t.lane_b.pocket_pivot.fired %}Pocket-Pivot {% endif %}
              {% if t.lane_b.base_quality.fired %}Base({{ t.lane_b.base_quality.score }}) {% endif %}
              {% if t.lane_b.insider_cluster.fired %}Insider({{ t.lane_b.insider_cluster.buyer_count }}) {% endif %}
              {% if t.lane_b.revenue_acceleration.fired %}RevAccel {% endif %}
              {% if t.lane_b.earnings_turn.fired %}EarnTurn {% endif %}
              {% if t.lane_b.peer_pack.fired %}PeerLag {% endif %}
            </td>
            <td>${{ "%.2f"|format(t.price) }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}

  {% if lane_c %}
    <h2 style="color:#c94545;">Lane C — Catalyst Today ({{ lane_c|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">Names reporting a recent earnings catalyst with post-gap momentum holding. Short-horizon plays (0-5 days).</div>
    <table class="summary">
      <thead><tr><th>Ticker</th><th>Name</th><th>T</th><th>Opp</th><th>Entry</th><th>Post-Earnings Info</th></tr></thead>
      <tbody>
        {% for t in lane_c %}
          <tr>
            <td><strong>{{ t.ticker }}</strong></td>
            <td>{{ t.name[:22] }}</td>
            <td><span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">T{{ t.tier }}</span></td>
            <td><strong>{{ t.opportunity.score }}</strong></td>
            <td>${{ "%.2f"|format(t.price) }}</td>
            <td style="font-size:10px;">{{ t.gates.g7.summary }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}

  {% if conviction_picks %}
    <h2>Top Conviction Picks ({{ conviction_picks|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">Highest-conviction ranked subset. Score combines IBD composite RS, up/down volume, earnings acceleration, sector leadership, pivot proximity, analyst upside, multi-timeframe trend, and FCF quality.</div>
    {% for t in conviction_picks %}
      <div class="conv-pick-card">
        <div class="conv-pick-head">
          <div style="display:flex; align-items:center; gap:10px;">
            <span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">T{{ t.tier }}</span>
            <span class="ticker">{{ t.ticker }}</span>
            <span style="color:#555;">{{ t.name[:35] }}</span>
            {% if t.sector %}<span class="sector-badge">{{ t.sector }}</span>{% endif %}
          </div>
          <div class="conv-box">
            <span>Conviction</span><span class="score">{{ t.conviction.score }}</span><span style="color:#888;">/100</span>
            {% if t.stress %}<span class="stress-dot stress-{{ t.stress.overall }}" title="Stress: {{ t.stress.overall }}"></span>{% endif %}
          </div>
        </div>
        <div style="font-size:12px; color:#333; margin-bottom:4px;">
          Entry ${{ "%.2f"|format(t.price) }} &middot; Stop ${{ "%.2f"|format(t.stop_loss) }} &middot; Phase 1 ${{ "%.2f"|format(t.phase1_target) }} &middot; Runner ${{ "%.2f"|format(t.runner_target) }} &middot; R/R {{ t.risk_reward }}
        </div>
        <div class="conv-pick-breakdown">
          {% for key, label in [('composite_rs','RS %ile'),('up_down_vol','U/D Vol'),('earnings_accel','E. Accel'),('sector_lead','Sector'),('pivot_proximity','Pivot'),('analyst_upside','Upside'),('multi_tf_trend','Weekly'),('fcf_quality','FCF')] %}
            {% set b = t.conviction.breakdown[key] %}
            <div><span class="k">{{ label }}:</span> <span class="v">{{ b.points }}/{{ b.max }}</span> <span class="k">({{ b.value if b.value is not none else 'n/a' }})</span></div>
          {% endfor %}
        </div>
        {% if t.stress %}
          <div class="stress-row">
            Stress: <strong>{{ t.stress.overall }}</strong> &nbsp;
            {% for key, label in [('drawdown_1y','DD 1Y'),('spy_correlation','Corr'),('beta','Beta'),('gap_frequency_1y','Gaps')] %}
              <span class="stress-dot stress-{{ t.stress.tests[key].label }}"></span>{{ label }} {{ t.stress.tests[key].value }} &nbsp;
            {% endfor %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  {% if top_tickets %}
    <h2>All Actionable Candidates ({{ top_tickets|length }})</h2>
    {% for t in top_tickets %}
      <div class="card tier{{ (t.tier|int) if t.tier is number else 0 }}">
        <div class="card-head">
          <div class="card-head-left">
            <span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">TIER {{ t.tier }}</span>
            <span class="ticker">{{ t.ticker }}</span>
            <span class="name">{{ t.name[:40] }}</span>
            {% if t.sector %}<span class="sector-badge">{{ t.sector }}{% if t.industry %} / {{ t.industry }}{% endif %}</span>{% endif %}
          </div>
          <div style="font-size:12px; color:#666;">
            {% if t.conviction %}<span class="conv-box"><span class="score">{{ t.conviction.score }}</span>/100 {% if t.stress %}<span class="stress-dot stress-{{ t.stress.overall }}"></span>{% endif %}</span> &middot; {% endif %}
            {{ t.pillars_passed }}/{{ t.applicable_pillars }} pillars
          </div>
        </div>

        {% if t.description %}<div class="description">{{ t.description }}</div>{% endif %}

        <div class="price-row">
          <span>Entry <strong>${{ "%.2f"|format(t.price) }}</strong></span>
          <span>Stop ${{ "%.2f"|format(t.stop_loss) }} ({{ "%.0f"|format(t.stop_pct) }}%)</span>
          <span>Phase 1 ${{ "%.2f"|format(t.phase1_target) }} (+50%)</span>
          <span>Runner ${{ "%.2f"|format(t.runner_target) }} (+80%)</span>
          <span>R/R {{ t.risk_reward }}</span>
        </div>

        <div class="pillar-grid">
          {% for key, label in [('p1','P1 Trend'), ('p2','P2 Vol Squeeze'), ('p3','P3 Growth'), ('p4','P4 RS'), ('p5','P5 Macro'), ('p6','P6 Revisions'), ('p7','P7 Short Sq.')] %}
            <div class="pillar-row">
              <span class="verdict v-{{ t.pillars[key].verdict }}">{{ t.pillars[key].verdict }}</span>
              <span class="pillar-label">{{ label }}</span>
              <span class="pillar-summary">{{ t.pillars[key].summary }}</span>
            </div>
          {% endfor %}
        </div>

        <div class="gate-row">
          {% for key, label in [('g3','RVOL'), ('g4','Catalyst'), ('g6','Liquidity'), ('g7','Earnings')] %}
            <strong>{{ label }}:</strong> <span class="verdict v-{{ t.gates[key].verdict }}">{{ t.gates[key].verdict }}</span> {{ t.gates[key].summary }} &nbsp;
          {% endfor %}
        </div>
      </div>
    {% endfor %}
  {% else %}
    <div class="empty">No candidates passed all gates today. Patience is a position.</div>
  {% endif %}

  {% if squeeze_watchlist %}
    <h2>Squeeze Watchlist ({{ squeeze_watchlist|length }}) — coiled setups that could break out next</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">Bollinger Bands compressed to ≤20th percentile of the last 120 days, P1 trend and P4 RS both clean, no hard-gate fails, upper band not yet pierced. These are the setups <em>before</em> they fire. Consider a buy-stop above the upper band.</div>
    <table class="summary">
      <thead><tr><th>Ticker</th><th>Name</th><th>Tier</th><th>Squeeze %ile</th><th>Entry</th><th>Sector</th></tr></thead>
      <tbody>
        {% for t in squeeze_watchlist %}
          <tr>
            <td><strong>{{ t.ticker }}</strong></td>
            <td>{{ t.name[:28] }}</td>
            <td>{% if t.tier %}<span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">T{{ t.tier }}</span>{% else %}-{% endif %}</td>
            <td>{{ "%.0f"|format(t.pillars.p2.squeeze_pct) }}</td>
            <td>${{ "%.2f"|format(t.price) }}</td>
            <td>{{ t.sector or '-' }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}

  {% if watchlist_tickets %}
    <h2>Watchlist ({{ watchlist_tickets|length }}) — below Tier 3 threshold</h2>
    <table class="summary">
      <thead><tr><th>Ticker</th><th>Name</th><th>Pillars</th><th>P1</th><th>P2</th><th>P3</th><th>P4</th><th>P5</th><th>P6</th><th>P7</th></tr></thead>
      <tbody>
        {% for t in watchlist_tickets %}
          <tr>
            <td><strong>{{ t.ticker }}</strong></td>
            <td>{{ t.name[:25] }}</td>
            <td>{{ t.pillars_passed }}/{{ t.applicable_pillars }}</td>
            {% for k in ['p1','p2','p3','p4','p5','p6','p7'] %}
              <td><span class="verdict v-{{ t.pillars[k].verdict }}">{{ t.pillars[k].verdict }}</span></td>
            {% endfor %}
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}

  {% if rejected_tickets %}
    <h2>Rejected at Gate ({{ rejected_tickets|length }})</h2>
    <table class="summary">
      <thead><tr><th>Ticker</th><th>Name</th><th>Failed Gates</th></tr></thead>
      <tbody>
        {% for t in rejected_tickets %}
          <tr>
            <td><strong>{{ t.ticker }}</strong></td>
            <td>{{ t.name[:25] }}</td>
            <td>{{ t.hard_gate_fails|join(', ') }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}

  {% if short_watchlist %}
    <h2 style="margin-top:32px; padding-top:18px; border-top:2px solid #eee;">Stage 4 Shorts &mdash; Watchlist</h2>
    <div style="font-size:12px; color:#555; margin-bottom:12px;">
      Names breaking down: Stage 4 trend, distribution days clustering, weak relative strength, or breakdown through 50d MA. Score 0-100 (qualified at 50+). Top 8 candidates get auto-checked for put-trade viability (disqualifiers: high SI = squeeze risk, earnings in 14d = IV crush risk, oversold RSI = bounce risk, mega-cap).
    </div>
    <table style="width:100%; border-collapse:collapse; font-size:11px;">
      <thead><tr style="background:#f4f4f4;">
        <th align="left" style="padding:5px 8px;">Ticker</th>
        <th align="left" style="padding:5px 8px;">Name</th>
        <th align="left" style="padding:5px 8px;">Sector</th>
        <th align="right" style="padding:5px 8px;">Last</th>
        <th align="right" style="padding:5px 8px;">vs 52w high</th>
        <th align="right" style="padding:5px 8px;">RS 20d</th>
        <th align="right" style="padding:5px 8px;">Dist/Acc 25d</th>
        <th align="right" style="padding:5px 8px;">Score</th>
        <th align="left" style="padding:5px 8px;">Why</th>
      </tr></thead>
      <tbody>
      {% for s in short_watchlist %}
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:5px 8px; font-weight:600;">{{ s.ticker }}</td>
          <td style="padding:5px 8px;">{{ s.name[:24] }}</td>
          <td style="padding:5px 8px; color:#555;">{{ (s.sector_hint or '')[:18] }}</td>
          <td align="right" style="padding:5px 8px;">${{ "%.2f"|format(s.last_close or 0) }}</td>
          <td align="right" style="padding:5px 8px; color:#c94545;">{% if s.pct_from_high is not none %}{{ "%.0f"|format(s.pct_from_high) }}%{% endif %}</td>
          <td align="right" style="padding:5px 8px; color:{% if s.inverse_rs_20d and s.inverse_rs_20d < -10 %}#c94545{% else %}#888{% endif %};">{% if s.inverse_rs_20d is not none %}{{ "%+.1f"|format(s.inverse_rs_20d) }}%{% endif %}</td>
          <td align="right" style="padding:5px 8px;"><span style="color:#c94545; font-weight:600;">{{ s.distribution_count_25d }}</span>/<span style="color:#888;">{{ s.accumulation_count_25d }}</span></td>
          <td align="right" style="padding:5px 8px; font-weight:700; color:{% if s.score >= 70 %}#c94545{% elif s.score >= 60 %}#e67e22{% else %}#888{% endif %};">{{ s.score }}</td>
          <td style="padding:5px 8px; color:#555; font-size:10px;">{{ s.reasons|join(' &middot; ') }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>

    {% set put_plays = short_watchlist|selectattr('put_trade')|list %}
    {% if put_plays %}
      <h2 style="margin-top:24px; padding-top:16px; border-top:2px solid #eee;">Priority Put Plays</h2>
      <div style="font-size:12px; color:#555; margin-bottom:12px;">
        Stage 4 candidates with a put contract that passed the disqualifier gates. Each is a potential bear-side options trade. Same risk-management rules as long calls: hard stop at -50% premium, exit before earnings if any, scale out at +100%/+200%.
      </div>
      {% for s in put_plays %}
        {% set p = s.put_trade %}
        <div style="border:2px solid #c94545; border-left-width:6px; background:#fef9f9; border-radius:6px; padding:12px 16px; margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
            <div>
              <span style="font-size:15px; font-weight:700;">{{ s.ticker }} PUT</span>
              <span style="font-size:11px; color:#555;">{{ s.name[:25] }}</span>
              <span style="font-size:10px; padding:2px 8px; border-radius:3px; background:#c94545; color:#fff; font-weight:700;">SHORT SCORE {{ s.score }}</span>
            </div>
            <div style="font-size:11px; color:#666;">{{ s.sector_hint or '' }}</div>
          </div>
          <div style="font-size:11px; color:#444; margin-bottom:4px;">
            Spot ${{ "%.2f"|format(s.last_close) }} &middot; from 52w high {{ "%.0f"|format(s.pct_from_high or 0) }}% &middot; RS 20d {{ "%+.1f"|format(s.inverse_rs_20d or 0) }}% &middot; Dist/Acc 25d {{ s.distribution_count_25d }}/{{ s.accumulation_count_25d }}
          </div>
          <div style="margin-top:8px; padding:10px 12px; background:#fffbf5; border:1px solid #f0d969; border-radius:4px; font-size:12px;">
            <div style="font-weight:700; color:#6a5300; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Put Trade Suggestion</div>
            <div style="font-weight:600;">${{ "%.0f"|format(p.strike) }} PUT &middot; exp {{ p.expiration }} ({{ p.dte }}d) &middot; Premium ${{ "%.2f"|format(p.premium_mid) }} (cost ${{ "%.0f"|format(p.cost_per_contract) }}/contract)</div>
            <div style="color:#555; font-size:11px; margin-top:3px;">Delta {{ p.delta }} &middot; Theta {{ p.theta }} &middot; IV {{ p.iv_pct }}% &middot; Spread {{ p.spread_pct }}% &middot; OI {{ p.open_interest or 'n/a' }}</div>
            <div style="color:#555; font-size:11px;">Breakeven ${{ "%.2f"|format(p.breakeven) }} ({{ "%+.1f"|format(p.breakeven_pct_move) }}% move)</div>
            <div style="color:#0d7b34; font-weight:600; margin-top:4px;">If stock drops to target ${{ "%.2f"|format(p.downside_target) }}: contract ~${{ "%.2f"|format(p.projected_value_at_target) }} ({{ "%+.0f"|format(p.projected_roi_pct) }}% on premium)</div>
          </div>
          <div style="font-size:11px; color:#8e44ad; margin-top:6px;">{{ s.reasons|join(' &middot; ') }}</div>
        </div>
      {% endfor %}
    {% endif %}

  {% endif %}

  <div class="footer">swing-trading-scanner &middot; v3.1 spec &middot; long + short detection &middot; put-trades on Stage 4 watchlist</div>
</div>
</body>
</html>"""


OPTIONS_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; color:#222; }
  .wrap { max-width:960px; margin:0 auto; background:#fff; padding:28px 32px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
  h1 { font-size:22px; margin:0 0 6px; }
  .meta { color:#666; font-size:13px; margin-bottom:20px; }
  h2 { font-size:16px; margin:22px 0 10px; }
  .intro { background:#fffbe8; border-left:4px solid #f0d969; padding:12px 16px; border-radius:4px; margin:0 0 18px; font-size:12px; color:#444; line-height:1.5; }
  .bucket-legend { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 16px; font-size:11px; }
  .bucket-chip { padding:4px 10px; border-radius:14px; color:#fff; font-weight:600; }
  .conv-pick-card { border:2px solid #e0e0e0; background:linear-gradient(180deg, #fafcff 0%, #fff 100%); border-radius:8px; padding:14px 18px; margin-bottom:12px; }
  .conv-pick-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; font-size:13px; flex-wrap:wrap; gap:6px; }
  .conv-pick-head .ticker { font-size:16px; font-weight:700; }
  .tier-badge { display:inline-block; padding:3px 10px; border-radius:4px; font-weight:600; font-size:11px; color:#fff; }
  .t5 { background:#0d7b34; } .t4 { background:#1a9850; } .t3 { background:#4a90e2; } .t2 { background:#999; } .t0 { background:#c94545; }
  .sector-badge { display:inline-block; padding:2px 8px; border-radius:3px; font-size:10px; font-weight:600; background:#eef2f7; color:#384766; text-transform:uppercase; letter-spacing:0.3px; }
  .stress-dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:3px; vertical-align:middle; }
  .stress-PASS { background:#1a9850; } .stress-WARN { background:#f0ad4e; } .stress-FAIL { background:#c94545; } .stress-UNKNOWN { background:#ccc; }
  .options-box { margin-top:10px; padding:10px 12px; background:#fffbe8; border:1px solid #f0d969; border-radius:6px; font-size:12px; }
  .options-box h4 { margin:0 0 6px; font-size:12px; color:#6a5300; text-transform:uppercase; letter-spacing:0.5px; }
  .options-box .row1 { font-weight:600; color:#444; margin-bottom:3px; }
  .options-box .row2 { color:#555; margin-bottom:3px; }
  .options-box .payoff { color:#0d7b34; font-weight:600; margin-top:4px; }
  .footer { margin-top:30px; font-size:11px; color:#999; text-align:center; }
  .empty { text-align:center; color:#666; font-style:italic; padding:24px; background:#fafafa; border-radius:6px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Priority Options Plays — {{ scan_date }}</h1>
  <div class="meta">Companion email to the main swing scan. Universe: {{ universe_size }} &middot; Regime: {{ regime }} &middot; VIX {{ vix }}</div>

  <div class="intro">
    <strong>9 options trades — Options Hunter Lane.</strong> Selected using the validated pre-move signature from 295 past 50%+ movers: 2x weight on P7 short squeeze, 2x P6 earnings revisions, earnings sweet-spot (11-21d), proximity to 52w high, sector tilt toward semis / networking / biotech / energy.
    <br>Each card shows a <strong>Hunter score</strong> (0-100), an <strong>anticipated move ETA</strong>, and the triggering signals. Bucketed 1 MEGA / 3 LARGE / 4 MID / 1 EARLY. Chain from Alpaca (14-50 DTE, delta 0.30-0.70, spread &lt;40%).
  </div>

  <div class="bucket-legend">
    <span class="bucket-chip" style="background:#0d7b34;">MEGA &gt; $200B — 1 slot</span>
    <span class="bucket-chip" style="background:#1a9850;">LARGE $10B-$200B — 3 slots</span>
    <span class="bucket-chip" style="background:#0052cc;">MID $2B-$10B — 4 slots</span>
    <span class="bucket-chip" style="background:#8e44ad;">EARLY &lt;$2B with signals — 1 slot</span>
  </div>

  {% if lottery_picks %}
    <h2 style="margin-top:24px; padding-top:14px; border-top:3px solid #f59e0b; color:#92400e;">PRIME LOTTERY SETUPS &mdash; targeting 500% in a week</h2>
    <div style="font-size:12px; color:#666; margin-bottom:12px; padding:10px 14px; background:#fffbeb; border-left:4px solid #f59e0b; border-radius:4px;">
      <strong>Reality check:</strong> These contracts can return 500%+ in a week IF the catalyst hits the way it's set up. They can also expire worthless (they expire in 7-14 days). Win rate ~10-25%. Treat as lottery tickets &mdash; size SMALL ($200-500 per trade max), expect to lose 70%+ of the time, but the wins can be life-changing.
      <br><strong>Setup:</strong> Imminent binary catalyst (earnings/FDA/M&amp;A) + squeeze fuel (high SI) + tight float + hot cohort. Picks must score 50+ on lottery scorer to qualify.
    </div>
    {% for t in lottery_picks %}
      {% set ls = t.lottery_score %}
      {% set lc = t.lottery_contract %}
      {% set tier_color = '#0d7b34' if ls.tier == 'PRIME' else '#1a9850' if ls.tier == 'STRONG' else '#4a90e2' %}
      <div style="border:3px solid {{ tier_color }}; background:linear-gradient(180deg,#fffbeb 0%,#fff 100%); border-radius:8px; padding:14px 18px; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
          <div>
            <span style="font-size:18px; font-weight:700;">{{ t.ticker }}</span>
            <span style="font-size:11px; color:#666;">{{ (t.name or '')[:28] }}</span>
            <span style="display:inline-block; padding:3px 10px; border-radius:4px; background:{{ tier_color }}; color:#fff; font-size:11px; font-weight:700; letter-spacing:0.5px;">LOTTERY {{ ls.tier }}</span>
            <span style="display:inline-block; padding:3px 10px; border-radius:4px; background:#f59e0b; color:#fff; font-size:11px; font-weight:700;">SCORE {{ ls.score }}</span>
          </div>
          <div style="text-align:right;">
            {% if t.live_spot %}
              <span style="font-size:13px; font-weight:700;">${{ "%.2f"|format(t.live_spot) }}</span>
              <span style="font-size:11px; color:{{ '#0d7b34' if t.live_change_pct >= 0 else '#c94545' }};">({{ "%+.2f"|format(t.live_change_pct) }}%)</span>
            {% else %}
              <span style="font-size:13px; font-weight:700;">${{ "%.2f"|format(t.price) }}</span>
            {% endif %}
          </div>
        </div>
        <div style="margin-top:8px; padding:12px 14px; background:#fff; border:2px solid #f59e0b; border-radius:6px; font-size:13px;">
          <div style="font-weight:700; color:#92400e; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Lottery Contract</div>
          <div style="font-size:14px; font-weight:700; color:#111;">${{ "%.0f"|format(lc.strike) }} CALL exp {{ lc.expiration }} ({{ lc.dte }} DTE)</div>
          <div style="margin-top:4px; color:#444;">Premium <strong>${{ "%.2f"|format(lc.mid) }}</strong> &middot; bid ${{ "%.2f"|format(lc.bid) }} / ask ${{ "%.2f"|format(lc.ask) }} &middot; spread {{ lc.spread_pct }}%</div>
          <div style="color:#444;">Delta {{ lc.delta }} &middot; IV {{ lc.iv_pct }}% &middot; cost <strong>${{ "%.0f"|format(lc.cost_per_contract) }}/contract</strong></div>
          <div style="margin-top:6px; padding:6px 10px; background:#fef3c7; border-radius:4px; font-size:12px; color:#92400e;">
            <strong>For 500% ROI:</strong> need stock to ${{ "%.2f"|format(lc.target_stock_price) }} ({{ "%+.1f"|format(lc.required_move_pct) }}%) within {{ lc.dte }} days
          </div>
        </div>
        <div style="margin-top:8px; font-size:11px; color:#555;">
          <strong style="color:#92400e;">Why this is a lottery candidate:</strong>
          <ul style="margin:4px 0 0; padding-left:18px;">
          {% for r in ls.reasons %}<li>{{ r }}</li>{% endfor %}
          </ul>
        </div>
        <div style="margin-top:6px; padding:5px 10px; background:#fee2e2; border-left:3px solid #c94545; border-radius:3px; font-size:10px; color:#7f1d1d;">
          <strong>RISK:</strong> ~70-85% chance of -100% (full premium loss). Size for "I can lose this without flinching" tolerance.
        </div>
      </div>
    {% endfor %}
  {% endif %}

  {% if priority_options %}
    {% set bucket_colors = {'MEGA':'#0d7b34', 'LARGE':'#1a9850', 'MID':'#0052cc', 'EARLY':'#8e44ad'} %}
    {% set bucket_labels = {'MEGA':'MEGA CAP', 'LARGE':'LARGE CAP', 'MID':'MID CAP', 'EARLY':'EARLY'} %}
    {% for t in priority_options %}
      <div class="conv-pick-card" style="border-color:{{ bucket_colors[t.priority_bucket] }};">
        <div class="conv-pick-head">
          <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <span style="font-size:10px; padding:3px 8px; border-radius:3px; background:{{ bucket_colors[t.priority_bucket] }}; color:#fff; font-weight:700; letter-spacing:0.4px;">{{ bucket_labels[t.priority_bucket] }}</span>
            <span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">T{{ t.tier }}</span>
            <span class="ticker">{{ t.ticker }}</span>
            <span style="color:#555;">{{ t.name[:28] }}</span>
            {% if t.sector %}<span class="sector-badge">{{ t.sector }}</span>{% endif %}
            {% if t.market_cap %}<span style="font-size:10px; color:#666;">${{ "%.1f"|format(t.market_cap / 1e9) }}B mcap</span>{% endif %}
            {% if t.sector_maturity and t.sector_maturity != 'N/A' %}<span style="font-size:9px; padding:2px 5px; border-radius:3px; background:{% if t.sector_maturity == 'LATE' %}#e67e22{% elif t.sector_maturity == 'MID' %}#f0ad4e{% else %}#0d7b34{% endif %}; color:#fff;">{{ t.sector_maturity }}</span>{% endif %}
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
            {% if t.hunter %}<span style="font-size:10px; color:#888;">HUNT</span><span style="font-size:15px; font-weight:700; color:#8e44ad;">{{ t.hunter.score }}</span>{% endif %}
            <span style="font-size:10px; color:#888;">OPP</span><span style="font-size:13px; font-weight:600; color:#0052cc;">{{ t.opportunity.score if t.opportunity else '-' }}</span>
            {% if t.conviction %}<span style="font-size:10px; color:#888;">CONV</span><span style="font-size:12px; font-weight:600;">{{ t.conviction.score }}</span>{% endif %}
            {% if t.stress %}<span class="stress-dot stress-{{ t.stress.overall }}"></span>{% endif %}
          </div>
        </div>
        {% if t.hunter and t.hunter.eta_label %}
          <div style="font-size:11px; color:#8e44ad; margin:4px 0 6px; padding:4px 8px; background:#faf5ff; border-radius:4px; display:inline-block;">
            <strong>Move ETA:</strong> {{ t.hunter.eta_label }}
            {% if t.hunter.reasons %} &middot; <span style="color:#555;">{{ t.hunter.reasons|join(' &middot; ') }}</span>{% endif %}
          </div>
        {% endif %}
        <div style="font-size:12px; color:#333; margin-bottom:4px;">
          Entry ${{ "%.2f"|format(t.price) }} &middot; Stop ${{ "%.2f"|format(t.stop_loss) }} &middot; Phase 1 ${{ "%.2f"|format(t.phase1_target) }} &middot; Runner ${{ "%.2f"|format(t.runner_target) }} &middot; R/R {{ t.risk_reward }}
        </div>
        {% if t.live_spot %}
          {% set live_color = '#0d7b34' if t.live_change_pct >= 1 else ('#c94545' if t.live_change_pct <= -1 else '#666') %}
          {% set live_bg = '#e7f5ec' if t.live_change_pct >= 1 else ('#fdecec' if t.live_change_pct <= -1 else '#f0f0f0') %}
          {% set big_move = t.live_change_pct >= 3 or t.live_change_pct <= -3 %}
          {% set chase = t.live_change_pct >= 5 %}
          <div style="font-size:11px; color:{{ live_color }}; margin:4px 0; padding:4px 8px; background:{{ live_bg }}; border-radius:4px; display:inline-block; {% if big_move %}border:2px solid {{ live_color }};{% endif %}">
            <strong>LIVE:</strong> ${{ "%.2f"|format(t.live_spot) }}
            {% if t.live_bid and t.live_ask %}(bid ${{ "%.2f"|format(t.live_bid) }}/ask ${{ "%.2f"|format(t.live_ask) }}){% endif %}
            ({{ "%+.2f"|format(t.live_change_pct) }}% vs scan close ${{ "%.2f"|format(t.price) }})
            {% if t.live_session %}&middot; <span style="font-size:10px; padding:1px 6px; border-radius:3px; background:#fff; color:#555;">{{ t.live_session }}{% if t.live_age_min and t.live_age_min > 30 %} - {{ "%.0f"|format(t.live_age_min) }}min ago{% endif %}</span>{% endif %}
            {% if chase %}<br><strong style="color:#7c2d12;">CHASE RISK: stock already up {{ "%+.1f"|format(t.live_change_pct) }}% - half size or wait for pullback</strong>
            {% elif big_move %}<br><strong>BIG MOVE - verify before entering</strong>{% endif %}
          </div>
          {% if t.options_trade and t.options_trade.breakeven_pct_from_live %}
            <div style="font-size:11px; color:#444; margin:2px 0 4px; padding:3px 8px; background:#f8f8f8; border-radius:3px; display:inline-block;">
              Breakeven from LIVE ${{ "%.2f"|format(t.options_trade.breakeven) }}: <strong>{{ "%+.2f"|format(t.options_trade.breakeven_pct_from_live) }}%</strong> needed (vs {{ "%+.2f"|format(t.options_trade.breakeven_pct_move) }}% from scan close)
            </div>
          {% endif %}
        {% endif %}
        {% if t.lane_b_signal_count and t.lane_b_signal_count > 0 %}
          <div style="font-size:11px; color:#0d7b34; margin-top:4px;">Early signals firing:
          {% if t.lane_b.pocket_pivot.fired %}[Pocket Pivot] {% endif %}
          {% if t.lane_b.base_quality.fired %}[Base Quality {{ t.lane_b.base_quality.score }}/10] {% endif %}
          {% if t.lane_b.insider_cluster.fired %}[Insider Cluster {{ t.lane_b.insider_cluster.buyer_count }}x] {% endif %}
          {% if t.lane_b.revenue_acceleration.fired %}[Rev Accel {{ t.lane_b.revenue_acceleration.latest_qoq_pct }}% QoQ] {% endif %}
          {% if t.lane_b.earnings_turn.fired %}[Earnings Turn] {% endif %}
          {% if t.lane_b.peer_pack.fired %}[Peer Pack Laggard] {% endif %}
          </div>
        {% endif %}
        {% if t.options_trade %}
          <div class="options-box">
            <h4>Options Swing Trade
            {% if t.options_trade.vol_interpretation %}
              <span style="float:right; font-size:10px; padding:1px 6px; border-radius:3px; background:{% if t.options_trade.vol_interpretation == 'CHEAP' %}#0d7b34{% elif t.options_trade.vol_interpretation == 'FAIR' %}#1a9850{% elif t.options_trade.vol_interpretation == 'EXPENSIVE' %}#e67e22{% else %}#c94545{% endif %}; color:#fff;">vol {{ t.options_trade.vol_interpretation }}</span>
            {% endif %}
            </h4>
            <div class="row1">{{ "%.0f"|format(t.options_trade.strike) }} Call &middot; exp {{ t.options_trade.expiration }} ({{ t.options_trade.dte }}d) &middot; Premium ${{ "%.2f"|format(t.options_trade.premium_mid) }} (cost ${{ "%.0f"|format(t.options_trade.cost_per_contract) }}/contract)</div>
            <div class="row2">Delta {{ t.options_trade.delta }} &middot; Theta {{ t.options_trade.theta }} &middot; IV {{ t.options_trade.iv_pct }}% &middot; Spread {{ t.options_trade.spread_pct }}%
            {% if t.options_trade.iv_skew and t.options_trade.iv_skew.skew_bias %}&middot; Skew {{ t.options_trade.iv_skew.skew_bias }}{% endif %}
            </div>
            <div class="row2">Breakeven ${{ "%.2f"|format(t.options_trade.breakeven) }} ({{ "%+.1f"|format(t.options_trade.breakeven_pct_move) }}% move)</div>
            <div class="payoff">If stock hits Phase 1 target: contract ~${{ "%.2f"|format(t.options_trade.projected_value_at_target) }} ({{ "%+.0f"|format(t.options_trade.projected_roi_pct) }}% return on premium)</div>
          </div>
        {% endif %}
        {% if t.options_spread %}
          {% set sp = t.options_spread %}
          <div style="margin-top:8px; padding:10px 12px; background:#f0f8ff; border:1px solid #4a90e2; border-radius:6px; font-size:11px;">
            <div style="font-weight:700; color:#1a4d7c; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">
              Alternative: Bull Call Spread
              <span style="float:right; font-weight:400; color:#666; font-size:10px;">lower cost / capped upside / less theta</span>
            </div>
            <div style="font-weight:600;">{{ "%.0f"|format(sp.long_leg.strike) }}/{{ "%.0f"|format(sp.short_leg.strike) }}C ({{ sp.width }}-wide) &middot; exp {{ sp.expiration }} ({{ sp.dte }}d)</div>
            <div style="color:#555; margin-top:2px;">
              Buy {{ "%.0f"|format(sp.long_leg.strike) }}C @ ${{ "%.2f"|format(sp.long_leg.mid) }} (Δ {{ sp.long_leg.delta }})
              &middot; Sell {{ "%.0f"|format(sp.short_leg.strike) }}C @ ${{ "%.2f"|format(sp.short_leg.mid) }} (Δ {{ sp.short_leg.delta }})
            </div>
            <div style="color:#555;">Net debit ${{ "%.2f"|format(sp.net_debit) }} = <strong>${{ "%.0f"|format(sp.cost_per_spread) }}/spread</strong> &middot; Max profit ${{ "%.0f"|format(sp.max_profit_per_spread) }} &middot; R/R {{ sp.risk_reward_ratio }}</div>
            <div style="color:#555;">Breakeven ${{ "%.2f"|format(sp.breakeven) }} ({{ "%+.1f"|format(sp.breakeven_pct_move) }}% move)</div>
            <div style="color:#0d7b34; font-weight:600; margin-top:3px;">If stock hits ${{ "%.2f"|format(t.phase1_target) }} target: ${{ "%.0f"|format(sp.profit_at_target) }} ({{ "%+.0f"|format(sp.roi_at_target_pct) }}%)</div>
          </div>
        {% endif %}
        {% if t.llm_thesis %}
          {% set _rating_colors = {
            'A+':'#0d7b34','A':'#0d7b34','A-':'#1a9850',
            'B+':'#4a90e2','B':'#4a90e2','B-':'#7aa9d4',
            'C+':'#e67e22','C':'#e67e22',
            'D':'#c94545'
          } %}
          {% set _rating_color = _rating_colors.get(t.llm_rating, '#888') %}
          <div style="margin-top:10px; padding:10px 12px; background:#f5f0fa; border-left:3px solid #8e44ad; border-radius:4px; font-size:12px; line-height:1.5;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <div style="font-size:10px; font-weight:700; color:#8e44ad; letter-spacing:0.5px; text-transform:uppercase;">Analyst note &middot; Claude Sonnet</div>
              {% if t.llm_rating %}
                <span style="display:inline-block; padding:3px 10px; border-radius:4px; background:{{ _rating_color }}; color:#fff; font-size:13px; font-weight:700; letter-spacing:0.5px;">{{ t.llm_rating }}</span>
              {% endif %}
            </div>
            <div style="color:#333;">{{ t.llm_thesis }}</div>
            {% if t.llm_risk %}
              <div style="margin-top:6px; color:#a8431a; font-size:11px;"><strong>Risk:</strong> {{ t.llm_risk }}</div>
            {% endif %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% else %}
    <div class="empty">No options plays passed filters today. Main scan still ran — check the companion email for stock setups.</div>
  {% endif %}

  {% if paper and paper.summary %}
    <h2 style="margin-top:32px; padding-top:18px; border-top:2px solid #eee;">Paper Trade Book</h2>
    <div style="font-size:12px; color:#555; margin-bottom:12px;">
      Hypothetical positions auto-opened from Hunter picks. Exit rules: -50% stop, +100% trim half, +200% trim to runner, +300% close, 21 DTE theta cliff, day before earnings, 50d SMA break.
      &middot; <strong>Open</strong>: {{ paper.summary.open_count }}
      &middot; <strong>Closed</strong>: {{ paper.summary.closed_count }}
      &middot; <strong>Unrealized</strong>: <span style="color:{% if paper.summary.total_unrealized_pnl_usd >= 0 %}#0d7b34{% else %}#c94545{% endif %};">${{ "%+.0f"|format(paper.summary.total_unrealized_pnl_usd) }}</span>
      &middot; <strong>Realized</strong>: <span style="color:{% if paper.summary.total_realized_pnl_usd >= 0 %}#0d7b34{% else %}#c94545{% endif %};">${{ "%+.0f"|format(paper.summary.total_realized_pnl_usd) }}</span>
      &middot; <strong>Total P&amp;L</strong>: <span style="font-weight:700; color:{% if paper.summary.total_pnl_usd >= 0 %}#0d7b34{% else %}#c94545{% endif %};">${{ "%+.0f"|format(paper.summary.total_pnl_usd) }}</span>
    </div>

    {% if paper.events %}
      <h3 style="font-size:13px; margin:14px 0 6px;">Today's Events</h3>
      <table style="width:100%; border-collapse:collapse; font-size:11px;">
        <thead><tr style="background:#f4f4f4;"><th align="left" style="padding:4px 8px;">Action</th><th align="left" style="padding:4px 8px;">Ticker</th><th align="left" style="padding:4px 8px;">Reason</th><th align="right" style="padding:4px 8px;">P&amp;L</th></tr></thead>
        <tbody>
        {% for ev in paper.events %}
          <tr style="border-bottom:1px solid #eee;">
            <td style="padding:4px 8px; font-weight:600; color:{% if ev.action == 'OPEN' %}#0052cc{% elif ev.action == 'CLOSE_ALL' %}{% if ev.pnl_pct and ev.pnl_pct > 0 %}#0d7b34{% else %}#c94545{% endif %}{% elif 'TRIM' in ev.action %}#e67e22{% else %}#888{% endif %};">{{ ev.action }}</td>
            <td style="padding:4px 8px;">{{ ev.ticker }}</td>
            <td style="padding:4px 8px; color:#555;">{{ ev.reason }}</td>
            <td align="right" style="padding:4px 8px;">{% if ev.pnl_pct is not none %}{{ "%+.0f"|format(ev.pnl_pct) }}%{% endif %}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% endif %}

    {% if paper.positions %}
      <h3 style="font-size:13px; margin:18px 0 6px;">Open Positions</h3>
      <table style="width:100%; border-collapse:collapse; font-size:11px;">
        <thead><tr style="background:#f4f4f4;">
          <th align="left" style="padding:4px 8px;">Ticker</th>
          <th align="right" style="padding:4px 8px;">Strike/Exp</th>
          <th align="right" style="padding:4px 8px;">Spot</th>
          <th align="right" style="padding:4px 8px;">Entry</th>
          <th align="right" style="padding:4px 8px;">Mark</th>
          <th align="right" style="padding:4px 8px;">P&amp;L %</th>
          <th align="right" style="padding:4px 8px;">P&amp;L $</th>
          <th align="right" style="padding:4px 8px;">Hunter</th>
          <th align="left" style="padding:4px 8px;">Opened</th>
        </tr></thead>
        <tbody>
        {% for p in paper.positions %}
          <tr style="border-bottom:1px solid #eee;">
            <td style="padding:4px 8px; font-weight:600;">{{ p.ticker }}</td>
            <td align="right" style="padding:4px 8px;">{{ "%.0f"|format(p.contract.strike) }}C {{ p.contract.expiration }}</td>
            <td align="right" style="padding:4px 8px;">{% if p.current_spot %}${{ "%.2f"|format(p.current_spot) }}{% else %}-{% endif %}</td>
            <td align="right" style="padding:4px 8px;">${{ "%.2f"|format(p.entry_mid) }}</td>
            <td align="right" style="padding:4px 8px;">${{ "%.2f"|format(p.current_mid) }}</td>
            <td align="right" style="padding:4px 8px; font-weight:600; color:{% if p.current_pnl_pct >= 0 %}#0d7b34{% else %}#c94545{% endif %};">{{ "%+.0f"|format(p.current_pnl_pct) }}%</td>
            <td align="right" style="padding:4px 8px; font-weight:600; color:{% if p.current_pnl_usd >= 0 %}#0d7b34{% else %}#c94545{% endif %};">${{ "%+.0f"|format(p.current_pnl_usd) }}</td>
            <td align="right" style="padding:4px 8px; color:#8e44ad;">{{ p.hunter_snapshot.score }}</td>
            <td style="padding:4px 8px; color:#555;">{{ p.opened_at }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% endif %}
  {% endif %}

  <div class="footer">swing-trading-scanner &middot; options companion &middot; Alpaca chain data</div>
</div>
</body>
</html>"""


MEGA_CAP_THR = 200_000_000_000
LARGE_CAP_THR = 10_000_000_000
MID_CAP_THR = 2_000_000_000


def _classify_cap_bucket(mcap):
    if not mcap:
        return "EARLY"
    if mcap >= MEGA_CAP_THR:
        return "MEGA"
    if mcap >= LARGE_CAP_THR:
        return "LARGE"
    if mcap >= MID_CAP_THR:
        return "MID"
    return "EARLY"


def build_priority_options(tickets, slot_plan=None):
    if slot_plan is None:
        slot_plan = [("MEGA", 1), ("LARGE", 3), ("MID", 4), ("EARLY", 1)]

    hunter_qualified = [
        t for t in tickets
        if t.get("hunter") and t["hunter"].get("qualified") and t.get("options_trade")
    ]
    if hunter_qualified:
        hunter_qualified.sort(key=lambda t: t["hunter"].get("score", 0), reverse=True)
        picks = []
        used = set()
        for t in hunter_qualified:
            bucket = t.get("priority_bucket") or _classify_cap_bucket(t.get("market_cap"))
            t["priority_bucket"] = bucket
            picks.append(t)
            used.add(t["ticker"])
        slot_cap = sum(s for _, s in slot_plan)
        return picks[:slot_cap]

    all_with_options = [t for t in tickets if t.get("options_trade") and t.get("opportunity")]
    buckets = {"MEGA": [], "LARGE": [], "MID": [], "EARLY": []}
    for t in all_with_options:
        buckets[_classify_cap_bucket(t.get("market_cap"))].append(t)
    for k in buckets:
        buckets[k].sort(key=lambda t: t["opportunity"].get("score", 0), reverse=True)
    picks = []
    used = set()
    for bucket_name, slots in slot_plan:
        taken = 0
        for t in buckets[bucket_name]:
            if taken >= slots:
                break
            if t["ticker"] in used:
                continue
            t["priority_bucket"] = bucket_name
            picks.append(t)
            used.add(t["ticker"])
            taken += 1
    remaining = sum(s for _, s in slot_plan) - len(picks)
    if remaining > 0:
        leftover = sorted(
            [t for t in all_with_options if t["ticker"] not in used],
            key=lambda t: t["opportunity"].get("score", 0),
            reverse=True,
        )
        for t in leftover[:remaining]:
            t["priority_bucket"] = _classify_cap_bucket(t.get("market_cap"))
            picks.append(t)
            used.add(t["ticker"])
    return picks


def render_options_email(scan):
    tickets = scan.get("tickets") or [r["ticket"] for r in scan.get("results", [])]
    priority_options = build_priority_options(tickets)
    try:
        from src.live_spot import enrich_with_live_spots
        enrich_with_live_spots(priority_options)
    except Exception as e:
        print(f"  live_spot: failed: {type(e).__name__}: {e}")
    try:
        from src.llm_commentary import add_commentary
        add_commentary(priority_options, top_n=5)
    except Exception as e:
        print(f"  llm_commentary: import/run failed: {type(e).__name__}: {e}")

    lottery_picks = sorted(
        [t for t in priority_options if t.get("lottery_score", {}).get("qualified") and t.get("lottery_contract")],
        key=lambda t: t["lottery_score"]["score"],
        reverse=True,
    )[:5]
    regime = scan.get("vix_regime") or {}
    vix_val = regime.get("vix")
    paper = scan.get("paper_trader") or {}
    tmpl = Template(OPTIONS_EMAIL_TEMPLATE)
    return tmpl.render(
        scan_date=scan["scan_date"],
        universe_size=scan.get("universe_size", 0),
        regime=regime.get("regime", "unknown"),
        vix=round(vix_val, 2) if vix_val is not None else "n/a",
        priority_options=priority_options,
        lottery_picks=lottery_picks,
        paper=paper,
    )


def render_email(scan):
    tickets = scan.get("tickets") or [r["ticket"] for r in scan.get("results", [])]

    lane_a = sorted(
        [t for t in tickets if t.get("lane") == "A"],
        key=lambda t: t.get("opportunity", {}).get("score", 0),
        reverse=True,
    )[:20]
    lane_b = sorted(
        [t for t in tickets if t.get("lane") == "B"],
        key=lambda t: t.get("opportunity", {}).get("score", 0),
        reverse=True,
    )[:20]
    lane_c = sorted(
        [t for t in tickets if t.get("lane") == "C"],
        key=lambda t: t.get("opportunity", {}).get("score", 0),
        reverse=True,
    )[:15]

    actionable = [t for t in tickets if t.get("tier") and t["tier"] >= 4]
    scored_with_conviction = [t for t in tickets if t.get("tier") and t["tier"] >= 4 and t.get("conviction")]
    conviction_picks = sorted(scored_with_conviction, key=lambda t: t["conviction"]["score"], reverse=True)[:10]
    top = actionable[:30]
    watchlist = []
    rejected = [t for t in tickets if not t.get("tier") or t["tier"] == 0][:15]

    enrich_set = list({id(t): t for t in (top + lane_a + lane_b + lane_c + conviction_picks)}.values())
    try:
        from src.live_spot import enrich_with_live_spots
        enrich_with_live_spots(enrich_set)
    except Exception as e:
        print(f"  live_spot: failed in render_email: {type(e).__name__}: {e}")

    theme_buckets = {}
    for t in (lane_a + lane_b):
        s = t.get("sector") or "Unknown"
        theme_buckets.setdefault(s, []).append(t["ticker"])
    theme_summary = sorted(theme_buckets.items(), key=lambda x: -len(x[1]))


    def _is_coiled(t):
        p = (t.get("pillars") or {}).get("p2") or {}
        sq = p.get("squeeze_pct")
        if sq is None or sq > 20:
            return False
        if p.get("upper_break"):
            return False
        p1 = (t.get("pillars") or {}).get("p1") or {}
        p4 = (t.get("pillars") or {}).get("p4") or {}
        if p1.get("verdict") == "FAIL" or p4.get("verdict") == "FAIL":
            return False
        if t.get("hard_gate_fails"):
            return False
        return True

    squeeze_watchlist = sorted(
        [t for t in tickets if _is_coiled(t)],
        key=lambda t: (t.get("pillars") or {}).get("p2", {}).get("squeeze_pct") or 100,
    )[:15]
    regime = scan["vix_regime"]
    vix_val = regime.get("vix")

    sector_counts = {}
    for t in actionable:
        s = t.get("sector") or "Unknown"
        sector_counts[s] = sector_counts.get(s, 0) + 1
    sector_summary = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)

    tmpl = Template(EMAIL_TEMPLATE)
    return tmpl.render(
        scan_date=scan["scan_date"],
        universe_size=scan["universe_size"],
        fast_survivors=scan["fast_filter_survivors"],
        scored_total=scan["scored_total"],
        api_calls=scan["api_calls"],
        regime=regime.get("regime", "unknown"),
        vix=round(vix_val, 2) if vix_val is not None else "n/a",
        top_tickets=top,
        watchlist_tickets=watchlist,
        rejected_tickets=rejected,
        sector_summary=sector_summary,
        sector_performance=scan.get("sector_performance", []),
        breadth=scan.get("breadth"),
        conviction_picks=conviction_picks,
        squeeze_watchlist=squeeze_watchlist,
        lane_a=lane_a,
        lane_b=lane_b,
        lane_c=lane_c,
        theme_summary=theme_summary,
        short_watchlist=scan.get("short_watchlist", []),
    )


def send_email(html, scan_date, recipient=None, subject=None):
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = recipient or gmail_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject or f"Swing Scan {scan_date}"
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient, msg.as_string())
    return True

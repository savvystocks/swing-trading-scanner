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
        {% if t.options_trade %}
          <div class="options-box">
            <h4>Options Swing Trade</h4>
            <div class="row1">
              {{ "%.0f"|format(t.options_trade.strike) }} Call &middot; exp {{ t.options_trade.expiration }} ({{ t.options_trade.dte }}d) &middot;
              Premium ${{ "%.2f"|format(t.options_trade.premium_mid) }}
              (cost ${{ "%.0f"|format(t.options_trade.cost_per_contract) }}/contract)
            </div>
            <div class="row2">
              Delta {{ t.options_trade.delta }} &middot;
              Theta {{ t.options_trade.theta }} &middot;
              IV {{ t.options_trade.iv_pct }}% &middot;
              OI {{ t.options_trade.open_interest }} &middot;
              Spread {{ t.options_trade.spread_pct }}%
            </div>
            <div class="row2">
              Breakeven ${{ "%.2f"|format(t.options_trade.breakeven) }} ({{ "%+.1f"|format(t.options_trade.breakeven_pct_move) }}% move from spot)
            </div>
            <div class="payoff">
              If stock hits Phase 1 target: contract ~${{ "%.2f"|format(t.options_trade.projected_value_at_target) }}
              ({{ "%+.0f"|format(t.options_trade.projected_roi_pct) }}% return on premium)
            </div>
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
          {% for key, label in [('p1','P1 Trend'), ('p2','P2 Squeeze'), ('p3','P3 Growth'), ('p4','P4 RS'), ('p5','P5 Macro'), ('p6','P6 Revisions'), ('p7','P7 Squeeze')] %}
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

  <div class="footer">swing-trading-scanner &middot; v3.1 spec &middot; long equity only, 1-3 month horizon</div>
</div>
</body>
</html>"""


def render_email(scan):
    tickets = scan.get("tickets") or [r["ticket"] for r in scan.get("results", [])]
    actionable = [t for t in tickets if t.get("tier") and t["tier"] >= 4]
    scored_with_conviction = [t for t in tickets if t.get("tier") and t["tier"] >= 4 and t.get("conviction")]
    conviction_picks = sorted(scored_with_conviction, key=lambda t: t["conviction"]["score"], reverse=True)[:10]
    top = actionable[:30]
    watchlist = []
    rejected = [t for t in tickets if not t.get("tier") or t["tier"] == 0][:15]
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
    )


def send_email(html, scan_date, recipient=None):
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = recipient or gmail_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Swing Scan {scan_date}"
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient, msg.as_string())
    return True

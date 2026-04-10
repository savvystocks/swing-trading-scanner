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
  .card-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
  .card-head-left { display:flex; align-items:center; gap:10px; }
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
  </div>

  {% if top_tickets %}
    <h2>Actionable Candidates ({{ top_tickets|length }})</h2>
    {% for t in top_tickets %}
      <div class="card tier{{ (t.tier|int) if t.tier is number else 0 }}">
        <div class="card-head">
          <div class="card-head-left">
            <span class="tier-badge t{{ (t.tier|int) if t.tier is number else 0 }}">TIER {{ t.tier }}</span>
            <span class="ticker">{{ t.ticker }}</span>
            <span class="name">{{ t.name[:40] }}</span>
          </div>
          <div style="font-size:12px; color:#666;">{{ t.pillars_passed }}/{{ t.applicable_pillars }} pillars</div>
        </div>

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
    top = [t for t in tickets if t.get("tier") and t["tier"] >= 3][:30]
    watchlist = [t for t in tickets if t.get("tier") == 2][:20]
    rejected = [t for t in tickets if not t.get("tier") or t["tier"] == 0][:15]
    regime = scan["vix_regime"]
    vix_val = regime.get("vix")
    t = Template(EMAIL_TEMPLATE)
    return t.render(
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

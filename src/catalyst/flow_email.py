"""Email renderer for the flow-first scan output."""

from datetime import datetime
from jinja2 import Template


TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 760px; margin: 0 auto; padding: 18px; color: #1f2937; background: #ffffff; }
h1 { font-size: 22px; margin-bottom: 4px; }
.subtitle { color: #6b7280; font-size: 13px; margin-bottom: 22px; }
.macro-bar { background: #1f2937; color: #f9fafb; padding: 12px 16px; border-radius: 10px; font-size: 13px; margin-bottom: 18px; }
.macro-bar strong { color: #fbbf24; }
.section { margin-top: 28px; }
.section-title { font-size: 13px; letter-spacing: 1.5px; font-weight: 800; margin-bottom: 12px; }
.section-title.calls { color: #15803d; }
.section-title.puts { color: #b91c1c; }
.tier-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 800; color: white; margin-right: 6px; }
.tier-MAX_CONVICTION { background: #581c87; }
.tier-ELITE { background: #7f1d1d; }
.tier-STRONG { background: #15803d; }
.tier-MODERATE { background: #a16207; }
.tier-GAMMA_BOMB { background: #be185d; }
.pick { border: 2px solid #e5e7eb; border-radius: 10px; padding: 16px 18px; margin-bottom: 14px; }
.pick.call { border-left: 6px solid #15803d; }
.pick.put { border-left: 6px solid #b91c1c; }
.pick-header { display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 800; margin-bottom: 8px; }
.ticker { font-family: Menlo, Consolas, monospace; font-size: 22px; }
.thesis { font-size: 13px; color: #374151; line-height: 1.5; margin-bottom: 10px; }
.size-target { display: flex; gap: 14px; font-size: 12px; color: #6b7280; margin-bottom: 10px; }
.size-target strong { color: #1f2937; }
.patterns { background: #f9fafb; padding: 10px 12px; border-radius: 6px; font-size: 11px; color: #4b5563; line-height: 1.6; }
.patterns .pat { display: block; margin: 2px 0; }
.patterns .pat-fired { color: #047857; }
.uw-flow { display: inline-block; font-size: 11px; color: #6b7280; }
.trade-ticket { background: #111827; color: #f9fafb; padding: 12px 16px; border-radius: 8px; margin: 10px 0; font-family: Menlo, Consolas, monospace; }
.trade-ticket .order { font-size: 16px; font-weight: 700; color: #fbbf24; margin-bottom: 4px; }
.trade-ticket .meta { font-size: 11px; color: #9ca3af; }
.sit-out { background: #f9fafb; border: 2px solid #6b7280; border-radius: 10px; padding: 20px; text-align: center; font-size: 14px; color: #4b5563; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 22px 0; }
</style></head><body>

<h1>FLOW SCAN — {{ scan_date }}</h1>
<div class="subtitle">Universe driven by Unusual Whales institutional flow. {{ universe_size }} tickers screened. {{ uw_calls_made }} API calls used.</div>

<div class="macro-bar">
  <strong>MACRO REGIME:</strong> {{ macro_regime }}  ·  <strong>{{ regime_label }}</strong>
</div>

{% if not calls and not puts %}
<div class="sit-out">
  <strong>SIT OUT TODAY.</strong> No setup cleared the MODERATE confluence threshold.<br>
  Cash is a position. Come back tomorrow.
</div>
{% endif %}

{% if calls %}
<div class="section">
  <div class="section-title calls">CALL CANDIDATES (LONG OPTIONS)</div>
  {% for p in calls %}
  <div class="pick call">
    <div class="pick-header">
      <span class="tier-badge tier-{{ p.tier }}">{{ p.tier }}</span>
      <span class="ticker">{{ p.ticker }}</span>
      <span style="font-size:14px;color:#6b7280;">score {{ p.score }} / 200</span>
    </div>
    <div class="thesis">{{ p.thesis }}</div>
    {% if p.trade_ticket %}
    <div class="trade-ticket">
      <div class="order">{{ p.trade_ticket.ticker }} {{ p.trade_ticket.side }} ${{ p.trade_ticket.strike }} exp {{ p.trade_ticket.expiry }} ({{ p.trade_ticket.dte }}d){% if p.trade_ticket.mid %}  @ ${{ "%.2f"|format(p.trade_ticket.mid) }} mid{% endif %}</div>
      <div class="meta">{{ p.trade_ticket.occ_symbol }}{% if p.trade_ticket.quote %}  ·  bid ${{ p.trade_ticket.quote.bid }} / ask ${{ p.trade_ticket.quote.ask }}{% if p.trade_ticket.quote.delta %}  ·  delta {{ "%.2f"|format(p.trade_ticket.quote.delta) }}{% endif %}{% if p.trade_ticket.quote.iv %}  ·  IV {{ "%.0f"|format(p.trade_ticket.quote.iv * 100) }}%{% endif %}{% endif %}</div>
    </div>
    {% endif %}
    <div class="size-target">
      <span>Size: <strong>{{ p.size_pct }}%</strong></span>
      <span>Vehicle: <strong>{{ p.vehicle }}</strong></span>
      <span>Target: <strong>+{{ p.target_pct }}%</strong></span>
      <span>Stop: <strong>{{ p.stop_pct }}%</strong></span>
      <span>Max hold: <strong>{{ p.max_hold_days }}d</strong></span>
    </div>
    <div class="patterns">
      {% for pat in p.patterns_fired %}
      <span class="pat pat-fired">+{{ pat.score }} pts · {{ pat.key }}: {{ pat.label }}</span>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}

{% if puts %}
<div class="section">
  <div class="section-title puts">PUT CANDIDATES (SHORT OPTIONS)</div>
  {% for p in puts %}
  <div class="pick put">
    <div class="pick-header">
      <span class="tier-badge tier-{{ p.tier }}">{{ p.tier }}</span>
      <span class="ticker">{{ p.ticker }}</span>
      <span style="font-size:14px;color:#6b7280;">score {{ p.score }} / 200</span>
    </div>
    <div class="thesis">{{ p.thesis }}</div>
    {% if p.trade_ticket %}
    <div class="trade-ticket">
      <div class="order">{{ p.trade_ticket.ticker }} {{ p.trade_ticket.side }} ${{ p.trade_ticket.strike }} exp {{ p.trade_ticket.expiry }} ({{ p.trade_ticket.dte }}d){% if p.trade_ticket.mid %}  @ ${{ "%.2f"|format(p.trade_ticket.mid) }} mid{% endif %}</div>
      <div class="meta">{{ p.trade_ticket.occ_symbol }}{% if p.trade_ticket.quote %}  ·  bid ${{ p.trade_ticket.quote.bid }} / ask ${{ p.trade_ticket.quote.ask }}{% if p.trade_ticket.quote.delta %}  ·  delta {{ "%.2f"|format(p.trade_ticket.quote.delta) }}{% endif %}{% if p.trade_ticket.quote.iv %}  ·  IV {{ "%.0f"|format(p.trade_ticket.quote.iv * 100) }}%{% endif %}{% endif %}</div>
    </div>
    {% endif %}
    <div class="size-target">
      <span>Size: <strong>{{ p.size_pct }}%</strong></span>
      <span>Vehicle: <strong>{{ p.vehicle }}</strong></span>
      <span>Target: <strong>+{{ p.target_pct }}%</strong></span>
      <span>Stop: <strong>{{ p.stop_pct }}%</strong></span>
      <span>Max hold: <strong>{{ p.max_hold_days }}d</strong></span>
    </div>
    <div class="patterns">
      {% for pat in p.patterns_fired %}
      <span class="pat pat-fired">+{{ pat.score }} pts · {{ pat.key }}: {{ pat.label }}</span>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}

<hr>
<div style="font-size:11px;color:#9ca3af;line-height:1.5;">
  Tiers and sizing: GAMMA_BOMB 15% (0-3DTE far OTM, asymmetric) · MAX_CONVICTION 40% (0.5 ITM, 21-30d) · ELITE 30% (ATM, 21-30d) · STRONG 20% (ATM, 21-30d) · MODERATE 10% (debit spread, 21-30d). Confluence threshold: score must be 50+ to qualify. Exits: target hit, -50% stop, DTE=7, GEX flip, macro shift, news break.
</div>

</body></html>
"""


def _build_pick_row(p):
    c = p.get("_confluence") or {}
    flow = p.get("_uw_flow_initial") or {}
    return {
        "ticker": p.get("ticker"),
        "tier": c.get("tier", "PASS"),
        "score": c.get("score", 0),
        "side": c.get("side", "NEUTRAL"),
        "thesis": c.get("thesis", ""),
        "size_pct": c.get("size_pct", 0),
        "vehicle": c.get("vehicle", ""),
        "target_pct": c.get("target_pct", 0),
        "stop_pct": c.get("stop_pct", 0),
        "max_hold_days": c.get("max_hold_days", 0),
        "patterns_fired": c.get("patterns_fired", []),
        "flow_premium": flow.get("total_premium", 0),
        "flow_calls": flow.get("calls", 0),
        "flow_puts": flow.get("puts", 0),
        "trade_ticket": c.get("trade_ticket"),
    }


def render_flow_email(scan):
    if not scan:
        return "<html><body>No scan data</body></html>"

    calls = [_build_pick_row(p) for p in scan.get("calls", [])]
    puts = [_build_pick_row(p) for p in scan.get("puts", [])]

    macro = scan.get("macro") or {}
    meta = macro.get("meta_regime") or {}
    regime_label = meta.get("regime", "UNKNOWN")
    label = meta.get("label") or "regime classification unavailable"
    sub_votes = meta.get("sub_votes") or []
    notes = "; ".join(v.get("label", "") for v in sub_votes[:3])

    template = Template(TEMPLATE)
    return template.render(
        scan_date=scan.get("scan_date", ""),
        universe_size=scan.get("universe_size", 0),
        uw_calls_made=scan.get("uw_calls_made", 0),
        macro_regime=regime_label,
        regime_label=notes or label,
        calls=calls,
        puts=puts,
    )

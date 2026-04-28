from jinja2 import Template

EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; color:#222; }
  .wrap { max-width:980px; margin:0 auto; background:#fff; padding:28px 32px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
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
  .score-box { background:#0052cc; color:#fff; padding:6px 12px; border-radius:6px; font-weight:700; font-size:14px; }
  .score-box.strong { background:#0d7b34; }
  .score-box.watch { background:#4a90e2; }
  .sector-badge { display:inline-block; padding:2px 8px; border-radius:3px; font-size:10px; font-weight:600; background:#eef2f7; color:#384766; text-transform:uppercase; letter-spacing:0.3px; }
  .price-row { font-size:12px; color:#444; margin:6px 0 8px; }
  .price-row strong { color:#0052cc; font-size:13px; }
  .price-row span { margin-right:14px; }
  .catalyst-line { font-size:12px; margin:6px 0; padding:6px 10px; background:#f0f7ff; border-left:3px solid #4a90e2; border-radius:3px; }
  .catalyst-line strong { color:#0052cc; }
  .factors-list { display:flex; flex-wrap:wrap; gap:5px; margin-top:6px; }
  .factor-chip { font-size:10px; padding:2px 7px; border-radius:11px; background:#e8f5e9; color:#1a6e2c; border:1px solid #c8e6c9; }
  .factor-chip.neg { background:#fdecea; color:#a02c2c; border-color:#f5b7b1; }
  .factor-chip.neutral { background:#eef2f7; color:#555; border-color:#dce4ed; }
  .source-row { font-size:10px; color:#888; margin-top:6px; }
  .legend { background:#f7f9fc; border:1px solid #e0e6ef; border-radius:8px; padding:14px 16px; margin:18px 0 22px; font-size:11px; }
  .legend h3 { margin:0 0 10px; font-size:13px; color:#384766; }
  .legend-grid { display:grid; grid-template-columns:repeat(2, 1fr); gap:14px 20px; }
  .legend-block { background:#fff; border:1px solid #e5e9f0; border-radius:6px; padding:10px 12px; }
  .legend-title { font-weight:700; color:#0052cc; font-size:11px; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.4px; }
  .legend-row { font-size:11px; color:#444; line-height:1.5; padding:2px 0; }
  .footer { margin-top:30px; font-size:11px; color:#999; text-align:center; }
  table.cohorts { width:100%; border-collapse:collapse; font-size:11px; margin-top:8px; }
  table.cohorts th { background:#f4f6fa; text-align:left; padding:6px 8px; border-bottom:1px solid #ddd; }
  table.cohorts td { padding:5px 8px; border-bottom:1px solid #f0f0f0; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Catalyst Watchlist &mdash; {{ scan_date }}</h1>
  <div class="meta">Pre-close scan for tomorrow's overnight catalysts &middot; Universe: {{ candidates_total }} candidates &middot; Enriched: {{ enriched_total }} &middot; Scored: {{ scored_total }} &middot; Passed >= {{ "%.1f"|format(score_cutoff) }}: {{ passed_cutoff }} &middot; EODHD: {{ eodhd_calls }} &middot; EDGAR: {{ edgar_calls }}</div>

  <div class="intro">
    <strong>How to use this email.</strong> Every name below has a known or filed catalyst expected to move the stock overnight or pre-market tomorrow. Buy at today's close (or in late session) to capture the gap. Score &ge; 8 = STRONG. Score 6-7.9 = WATCH (smaller size, confirmation buy). Tier S/A = highest-conviction catalyst type. Quality modifiers (green chips = positive, red = negative) tell you whether the surrounding setup supports the move.
  </div>

  <div class="legend">
    <h3>Catalyst tier reference</h3>
    <div class="legend-grid">
      <div class="legend-block">
        <div class="legend-title"><span class="tier-badge tier-S">S</span> &nbsp; Highest-conviction catalysts</div>
        <div class="legend-row">FDA PDUFA decision, cash buyout, earnings BMO with established beat streak, major contract win &gt; $100M.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title"><span class="tier-badge tier-A">A</span> &nbsp; High-probability event-driven</div>
        <div class="legend-row">Earnings BMO tomorrow, asset purchase agreement, merger agreement, Phase 1/2/3 milestone, FDA event filed, material definitive agreement.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title"><span class="tier-badge tier-B">B</span> &nbsp; Moderate setups</div>
        <div class="legend-row">Private placement, covenant relief, strategic partnership, contract or tender award, activist 13D stake.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title"><span class="tier-badge tier-C">C</span> &nbsp; Lower-prob signals</div>
        <div class="legend-row">Form 4 insider cluster, Lazar Capital cohort, crypto-treasury cohort, biotech binary cohort, prediction market cohort, buyback announcement.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title"><span class="tier-badge tier-D">D</span> &nbsp; Speculative cohort-only</div>
        <div class="legend-row">Cannabis basket, AI rebrand cohort, name change, small-cap China ADR. Trade only when paired with another higher-tier signal.</div>
      </div>
      <div class="legend-block">
        <div class="legend-title">Quality modifiers (cap &plusmn;3)</div>
        <div class="legend-row">Liquidity (&plusmn;2), mcap sweet-spot (&plusmn;1), trend vs 200dMA (&plusmn;1), institutional held (&plusmn;0.5), short interest 15-30% (&plusmn;1), going concern (&minus;2), recent dilution (&minus;1), sector tailwind (+0.5), multi-cohort stack (+1).</div>
      </div>
    </div>
  </div>

  {% if strong %}
    <h2 style="color:#0d7b34;">STRONG &mdash; Score &ge; 8 ({{ strong|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">High-conviction catalyst + clean quality setup. Position at today's close.</div>
    {% for c in strong %}
      <div class="card strong">
        <div class="card-head">
          <div class="card-head-left">
            <span class="ticker">{{ c.ticker }}</span>
            <span class="name">{{ (c.name or c.company)[:50] }}</span>
            {% if c.sector %}<span class="sector-badge">{{ c.sector }}</span>{% endif %}
            <span class="tier-badge tier-{{ c.catalyst_tier }}">Tier {{ c.catalyst_tier }}</span>
          </div>
          <div class="score-box strong">{{ "%.1f"|format(c.score) }}/10</div>
        </div>
        <div class="price-row">
          <span>Price <strong>${{ "%.2f"|format(c.price) if c.price else "n/a" }}</strong></span>
          {% if c.market_cap %}<span>Mcap ${{ "%.2f"|format(c.market_cap/1e9) }}B</span>{% endif %}
          {% if c.dollar_volume_20d %}<span>$Vol ${{ "%.1f"|format(c.dollar_volume_20d/1e6) }}M</span>{% endif %}
          {% if c.short_pct_float %}<span>SI {{ "%.0f"|format(c.short_pct_float) }}%</span>{% endif %}
        </div>
        {% for cat in c.catalysts %}
          <div class="catalyst-line">
            <strong>{{ cat.label }}</strong> &middot; {{ cat.details }}
          </div>
        {% endfor %}
        <div class="factors-list">
          {% for f in c.factors %}
            <span class="factor-chip {% if f.points < 0 %}neg{% elif f.points == 0 %}neutral{% endif %}">{{ "%+.1f"|format(f.points) }} {{ f.label }}</span>
          {% endfor %}
        </div>
        {% if c.sources %}
          <div class="source-row">Sources: {{ c.sources|unique|join(', ') }}</div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  {% if watch %}
    <h2 style="color:#4a90e2;">WATCH &mdash; Score 6.0 - 7.9 ({{ watch|length }})</h2>
    <div style="font-size:11px; color:#666; margin:-4px 0 12px;">Catalyst present but quality setup mixed. Smaller size, wait for confirmation move on open.</div>
    {% for c in watch %}
      <div class="card watch">
        <div class="card-head">
          <div class="card-head-left">
            <span class="ticker">{{ c.ticker }}</span>
            <span class="name">{{ (c.name or c.company)[:50] }}</span>
            {% if c.sector %}<span class="sector-badge">{{ c.sector }}</span>{% endif %}
            <span class="tier-badge tier-{{ c.catalyst_tier }}">Tier {{ c.catalyst_tier }}</span>
          </div>
          <div class="score-box watch">{{ "%.1f"|format(c.score) }}/10</div>
        </div>
        <div class="price-row">
          <span>Price <strong>${{ "%.2f"|format(c.price) if c.price else "n/a" }}</strong></span>
          {% if c.market_cap %}<span>Mcap ${{ "%.2f"|format(c.market_cap/1e9) }}B</span>{% endif %}
          {% if c.dollar_volume_20d %}<span>$Vol ${{ "%.1f"|format(c.dollar_volume_20d/1e6) }}M</span>{% endif %}
          {% if c.short_pct_float %}<span>SI {{ "%.0f"|format(c.short_pct_float) }}%</span>{% endif %}
        </div>
        {% for cat in c.catalysts %}
          <div class="catalyst-line">
            <strong>{{ cat.label }}</strong> &middot; {{ cat.details }}
          </div>
        {% endfor %}
        <div class="factors-list">
          {% for f in c.factors %}
            <span class="factor-chip {% if f.points < 0 %}neg{% elif f.points == 0 %}neutral{% endif %}">{{ "%+.1f"|format(f.points) }} {{ f.label }}</span>
          {% endfor %}
        </div>
        {% if c.sources %}
          <div class="source-row">Sources: {{ c.sources|unique|join(', ') }}</div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}

  {% if not strong and not watch %}
    <div class="empty">No catalysts scored above {{ "%.1f"|format(score_cutoff) }} today. {{ scored_total }} candidates evaluated. Check back tomorrow.</div>
  {% endif %}

  <div class="footer">catalyst-watchlist &middot; pre-close scan &middot; aim: capture overnight gap on tomorrow's catalyst</div>
</div>
</body>
</html>"""


def render_catalyst_email(scan, max_strong=30, max_watch=30):
    candidates = scan.get("candidates", [])
    strong = sorted(
        [c for c in candidates if c["bucket"] == "STRONG"],
        key=lambda c: c["score"], reverse=True,
    )[:max_strong]
    watch = sorted(
        [c for c in candidates if c["bucket"] == "WATCH"],
        key=lambda c: c["score"], reverse=True,
    )[:max_watch]

    tmpl = Template(EMAIL_TEMPLATE)
    return tmpl.render(
        scan_date=scan.get("scan_date"),
        candidates_total=scan.get("candidates_total", 0),
        enriched_total=scan.get("enriched_total", 0),
        scored_total=scan.get("scored_total", 0),
        passed_cutoff=scan.get("passed_cutoff", 0),
        score_cutoff=scan.get("score_cutoff", 6.0),
        eodhd_calls=scan.get("eodhd_calls", 0),
        edgar_calls=scan.get("edgar_calls", 0),
        strong=strong,
        watch=watch,
    )

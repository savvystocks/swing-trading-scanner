UNIFIED_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background:#f4f4f4; margin:0; padding:18px; color:#222; }
  .wrap { max-width:980px; margin:0 auto; background:#fff; padding:24px 28px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
  h1 { font-size:22px; margin:0 0 4px; }
  h2 { font-size:16px; margin:22px 0 10px; padding-bottom:6px; border-bottom:2px solid #eee; }
  h3 { font-size:14px; margin:12px 0 8px; }
  .meta { color:#666; font-size:12px; margin-bottom:14px; }
  .strip { padding:8px 12px; margin-bottom:8px; border-radius:6px; font-size:11px; }
  .strip strong { color:#222; }
  .macro { background:#f0f9ff; border:1px solid #4a90e2; }
  .portfolio { background:#fefce8; border:1px solid #eab308; }
  .winrate { background:#f5f3ff; border:1px solid #8b5cf6; }
  .forward { background:#ecfdf5; border:1px solid #10b981; }
  .macro-play { background:#fef2f2; border:1px solid #c94545; padding:10px 12px; margin-bottom:14px; border-radius:6px; }
  .empty { text-align:center; padding:36px; background:#fafafa; border-radius:8px; color:#666; }
  .empty strong { color:#c94545; font-size:14px; display:block; margin-bottom:8px; }
  .card { border:2px solid; border-radius:8px; padding:14px 16px; margin-bottom:12px; }
  .card-app { border-color:#0d7b34; background:#f7fcf8; }
  .card-ap { border-color:#1a9850; background:#f9fdfa; }
  .card-a { border-color:#4a90e2; background:#f7fbff; }
  .card-head { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px; }
  .ticker { font-weight:800; font-size:18px; color:#111; }
  .tier-badge { display:inline-block; padding:3px 10px; border-radius:4px; font-weight:800; font-size:12px; color:#fff; }
  .tier-app { background:#0d7b34; }
  .tier-ap { background:#1a9850; }
  .tier-a { background:#4a90e2; }
  .bracket-badge { display:inline-block; padding:2px 8px; border-radius:3px; font-weight:700; font-size:10px; background:#384766; color:#fff; }
  .price-row { font-size:12px; color:#444; margin:6px 0; }
  .price-row strong { color:#0052cc; }
  .prime { display:inline-block; padding:2px 8px; border-radius:3px; font-weight:700; font-size:10px; background:#0d7b34; color:#fff; box-shadow:0 0 6px rgba(13,123,52,0.4); }
  .section { padding:8px 12px; margin:6px 0; border-radius:4px; }
  .section-bull { background:#f0fdf4; border-left:3px solid #16a34a; }
  .section-bear { background:#fef2f2; border-left:3px solid #c94545; }
  .section-analog { background:#f5f3ff; border-left:3px solid #8b5cf6; }
  .section-iv { background:#fefce8; border-left:3px solid #eab308; }
  .section-trade { background:#eff6ff; border-left:3px solid #1d4ed8; }
  .section-premortem { background:#fff7ed; border-left:3px solid #f97316; }
  .analog-table { width:100%; font-size:11px; border-collapse:collapse; margin-top:4px; }
  .analog-table th { background:#ede9fe; padding:3px 6px; text-align:left; }
  .analog-table td { padding:3px 6px; border-bottom:1px solid #f0f0f0; }
  .badge-good { background:#d1fae5; color:#065f46; padding:1px 6px; border-radius:3px; font-weight:700; font-size:10px; }
  .badge-warn { background:#fef3c7; color:#854d0e; padding:1px 6px; border-radius:3px; font-weight:700; font-size:10px; }
  .badge-bad { background:#fee2e2; color:#7f1d1d; padding:1px 6px; border-radius:3px; font-weight:700; font-size:10px; }
  .skip-noise { background:#f9fafb; border:1px solid #e5e7eb; border-radius:6px; padding:10px 12px; margin-top:18px; font-size:11px; color:#555; }
  .footer { margin-top:24px; padding-top:12px; border-top:1px solid #eee; font-size:10px; color:#999; text-align:center; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Micro &middot; Small &middot; Mid Cap Setups &mdash; {{ scan_date }}</h1>
  <div class="meta">{{ total_picks }} A-grade picks across brackets (A++ {{ a_plus_plus_count }} &middot; A+ {{ a_plus_count }} &middot; A {{ a_count }}) &middot; {{ rejected_count }} rejected by gates &middot; universe {{ universe_size }}</div>

  {% if macro %}
    <div class="strip macro">
      <strong>Macro regime:</strong>
      <span class="tier-badge" style="background:{% if macro.regime == 'low_vol' %}#0d7b34{% elif macro.regime == 'normal' %}#4a90e2{% elif macro.regime == 'elevated' %}#e67e22{% else %}#c94545{% endif %};">{{ macro.regime|upper }}</span>
      {% if macro.vix %}&middot; VIX <strong>{{ "%.1f"|format(macro.vix) }}</strong>{% endif %}
      {% if vol_regime and vol_regime.tier_cap %}&middot; max tier this regime: <strong>{{ vol_regime.tier_cap }}</strong>{% endif %}
      {% if vol_regime and vol_regime.position_multiplier != 1.0 %}&middot; position sizing × <strong>{{ vol_regime.position_multiplier }}</strong>{% endif %}
      {% if macro.flags %}<br>{% for f in macro.flags[:3] %}{{ f }}{% if not loop.last %} &middot; {% endif %}{% endfor %}{% endif %}
    </div>
  {% endif %}

  {% if portfolio_summary %}
    {% set ps = portfolio_summary %}
    <div class="strip portfolio">
      <strong>Portfolio:</strong>
      <span class="tier-badge" style="background:{% if ps.n_free >= 2 %}#0d7b34{% elif ps.n_free == 1 %}#e67e22{% else %}#c94545{% endif %};">{{ ps.n_open }}/{{ ps.max_concurrent }}</span>
      {% if ps.n_free > 0 %}{{ ps.n_free }} slot(s) free{% else %}FULL{% endif %}
      {% if ps.tickers %}&middot; held: {{ ps.tickers|join(', ') }}{% endif %}
      {% if ps.open_pnl_usd is defined %}&middot; MTM PnL <strong style="color:{% if ps.open_pnl_usd >= 0 %}#0d7b34{% else %}#c94545{% endif %};">${{ "%+.0f"|format(ps.open_pnl_usd) }}</strong>{% endif %}
    </div>
  {% endif %}

  {% if win_rate_stats %}
    {% set ws = win_rate_stats %}
    <div class="strip winrate">
      <strong>Last 30d:</strong> {{ ws.win_rate_pct }}% win &middot; {{ ws.n_wins }}W / {{ ws.n_losses }}L of {{ ws.n_trades }} &middot; avg {{ "%+.2f"|format(ws.avg_pnl_pct) }}% &middot; best <span class="badge-good">{{ "%+.1f"|format(ws.best_pct) }}%</span> &middot; worst <span class="badge-bad">{{ "%+.1f"|format(ws.worst_pct) }}%</span>
    </div>
  {% endif %}

  {% if forward_calendar %}
    {% set fc = forward_calendar %}
    {% set ec = fc.earnings or {} %}
    <div class="strip forward">
      <strong>This week:</strong> {{ ec.total_earnings or 0 }} earnings ({{ ec.on_watchlist_count or 0 }} watched)
      {% if fc.macro_events %}&middot; {% for m in fc.macro_events %}{{ m.label }} ({{ m.days_until }}d){% if not loop.last %}, {% endif %}{% endfor %}{% endif %}
    </div>
    {% if fc.macro_trade_suggestions %}
      <div class="macro-play">
        <strong style="color:#7f1d1d; text-transform:uppercase; font-size:11px;">Macro lottery plays this week</strong>
        {% for m in fc.macro_trade_suggestions[:2] %}
          <div style="margin-top:6px; padding:6px 10px; background:#fff; border-radius:4px; font-size:11px;">
            <strong>{{ m.event }}</strong> in <strong>{{ m.days_until }}d</strong> &middot; <strong>Play:</strong> {{ m.vehicles|join(' / ') }} {{ m.structure }} &middot; <strong>DTE:</strong> {{ m.dte_target }}
            <div style="margin-top:2px; color:#555;">{{ m.specific_strikes }}</div>
          </div>
        {% endfor %}
      </div>
    {% endif %}
  {% endif %}

  {% if execution_context %}
    <div class="strip" style="background:#fff7ed; border:1px solid #f97316;">
      <strong>Execution context:</strong>
      {{ execution_context.day_of_week }} {{ execution_context.time_window.label }} &middot; expected slippage ~{{ execution_context.time_window.expected_slippage_pct }}%
      {% if execution_context.guidance %}<br>{% for g in execution_context.guidance %}{{ g }}{% if not loop.last %} &middot; {% endif %}{% endfor %}{% endif %}
    </div>
  {% endif %}

  {% if total_picks == 0 %}
    <div class="empty">
      <strong>NO QUALIFYING SETUPS TODAY</strong>
      The discipline is in not trading B-grade. Most days the system will be quiet. Today none of the candidates passed all gates.
      {% if rejection_summary %}
        <div style="text-align:left; margin-top:20px; padding:14px 16px; background:#fff; border:1px solid #ddd; border-radius:6px; font-style:normal;">
          <strong style="color:#222;">Closest 3 names + why they were rejected:</strong>
          {% for r in rejection_summary[:3] %}
            <div style="margin-top:8px;"><strong>{{ r.ticker }}</strong> ({{ r.bracket }}): {{ r.reason }}</div>
          {% endfor %}
        </div>
      {% endif %}
    </div>
  {% else %}
    {% for bracket in ['micro', 'small', 'mid'] %}
      {% set bracket_picks = picks_by_bracket.get(bracket) or [] %}
      {% if bracket_picks %}
        <h2>{{ bracket_label(bracket) }}</h2>
        {% for c in bracket_picks %}
          {% set tier_class = 'card-app' if c._aa_tier == 'A++' else 'card-ap' if c._aa_tier == 'A+' else 'card-a' %}
          <div class="card {{ tier_class }}">
            <div class="card-head">
              <div>
                <span class="ticker">{{ c.ticker }}</span>
                {% set tier_css = 'tier-app' if c._aa_tier == 'A++' else 'tier-ap' if c._aa_tier == 'A+' else 'tier-a' %}
                <span class="tier-badge {{ tier_css }}">{{ c._aa_tier }}</span>
                <span class="bracket-badge">{{ bracket|upper }}</span>
                {% if c._extension_check and c._extension_check.red_count == 0 and c._extension_check.yellow_count == 0 %}<span class="prime">PRIME ENTRY</span>{% endif %}
                <span style="color:#666; font-size:11px;">{{ (c.name or '')[:36] }}</span>
              </div>
              <div style="text-align:right; font-size:11px; color:#444;">
                Score {{ "%.0f"|format(c._stacked_score or c.score or 0) }} &middot; {{ c._category_count }} cats &middot; ${{ "%.1f"|format((c.market_cap or 0)/1e9) }}B
              </div>
            </div>

            <div class="price-row">
              <strong>${{ "%.2f"|format(c.price) if c.price else "n/a" }}</strong>
              {% if c.live_spot %}&middot; LIVE ${{ "%.2f"|format(c.live_spot) }} ({{ "%+.2f"|format(c.live_change_pct or 0) }}%){% endif %}
              {% if c.sector %}&middot; {{ c.sector }}{% endif %}
              {% if c.short_pct_float %}&middot; SI {{ "%.0f"|format(c.short_pct_float) }}%{% endif %}
              {% if c.iv_percentile_analysis %}&middot; IV percentile <strong>{{ c.iv_percentile_analysis.iv_percentile }}</strong> ({{ c.iv_percentile_analysis.interpretation.regime if c.iv_percentile_analysis.interpretation else '' }}){% endif %}
            </div>

            {% if c._smart_money_signals %}
              <div style="font-size:11px; margin:4px 0;"><strong>Smart money:</strong> {% for s in c._smart_money_signals %}<span class="badge-good">{{ s|replace('_', ' ') }}</span> {% endfor %}</div>
            {% endif %}

            {% if c.catalysts %}
              <div style="font-size:11px; margin:6px 0;">
                <strong>Catalysts:</strong> {% for cat in c.catalysts[:3] %}<span style="display:inline-block; padding:1px 6px; margin:1px 2px 0 0; background:#dbeafe; border-radius:3px; font-size:10px;">[{{ cat.tier }}] {{ cat.label }}</span>{% endfor %}
              </div>
            {% endif %}

            {% if c.deep_research and c.deep_research.research_note %}
              <div class="section section-bull">
                <strong>BULL:</strong> {{ c.deep_research.research_note[:400] }}
              </div>
            {% endif %}

            {% if c.counter_thesis %}
              <div class="section section-bear">
                <strong>BEAR ({{ c.counter_thesis.bear_score or '?' }}/100):</strong> {{ c.counter_thesis.bear_thesis }}
                {% if c.counter_thesis.what_kills_this_trade %}<br><em>Kill scenario:</em> {{ c.counter_thesis.what_kills_this_trade }}{% endif %}
              </div>
            {% endif %}

            {% if c.analog_set and c.analog_set.statistics %}
              {% set stats = c.analog_set.statistics %}
              <div class="section section-analog">
                <strong>ANALOGS ({{ stats.n_analogs }} found):</strong> win rate <strong>{{ stats.win_rate_next_day_pct }}%</strong> &middot; median next-day <strong>{{ stats.median_next_day_pct }}%</strong> &middot; worst <strong>{{ stats.worst_outcome_pct }}%</strong>
                {% if c.analog_set.analogs %}
                  <table class="analog-table">
                    <thead><tr><th>Ticker</th><th>Date</th><th>Catalyst</th><th>Next-day</th><th>1-week</th></tr></thead>
                    {% for a in c.analog_set.analogs[:5] %}
                      <tr><td><strong>{{ a.ticker }}</strong></td><td>{{ a.date }}</td><td>{{ (a.catalyst or '')[:40] }}</td><td><span class="{% if a.next_day_pct >= 0 %}badge-good{% else %}badge-bad{% endif %}">{{ "%+.1f"|format(a.next_day_pct) }}%</span></td><td>{{ "%+.1f"|format(a.one_week_pct or 0) }}%</td></tr>
                    {% endfor %}
                  </table>
                {% endif %}
                {% if c.analog_set.summary %}<div style="margin-top:4px; font-style:italic;">{{ c.analog_set.summary }}</div>{% endif %}
              </div>
            {% endif %}

            {% if c._options_market_read %}
              {% set om = c._options_market_read %}
              <div class="section section-iv">
                <strong>OPTIONS MARKET:</strong>
                {% if om.implied_move_pct %}implied {{ "%.1f"|format(om.implied_move_pct) }}%{% endif %}
                {% if om.analog_median_move_pct %} vs analog {{ "%.1f"|format(om.analog_median_move_pct) }}%{% endif %}
                {% if om.edge_label %}&middot; <span class="{% if om.edge_label == 'MARKET_UNDERPRICING' %}badge-good{% elif om.edge_label == 'MARKET_OVERPRICING' %}badge-bad{% else %}badge-warn{% endif %}">{{ om.edge_label|replace('_', ' ') }}</span>{% endif %}
                {% if om.cp_signal %}<br>{{ om.cp_signal }}{% endif %}
                {% if om.skew_signal %}<br>{{ om.skew_signal|replace('_', ' ') }}{% endif %}
                {% if om.block_summary %}<br><strong>Block trades:</strong> {{ om.block_summary }}{% endif %}
              </div>
            {% endif %}

            {% if c.trade_ticket %}
              <div class="section section-trade">
                <strong>TRADE TICKET:</strong>
                {{ c.trade_ticket.contract_label }} &middot; <strong>{{ c.trade_ticket.position_size_usd }} ({{ c.trade_ticket.position_pct }}% of account)</strong>
                <br>Stop -{{ c.trade_ticket.stop_pct }}% &middot; T1 +{{ c.trade_ticket.t1_pct }}% trim {{ c.trade_ticket.t1_trim_pct }}% &middot; T2 +{{ c.trade_ticket.t2_pct }}% trim {{ c.trade_ticket.t2_trim_pct }}% &middot; runner past +{{ c.trade_ticket.runner_pct }}%
                <br><strong>EV:</strong> {{ "%+.1f"|format(c.trade_ticket.ev_pct) }}% per trade
              </div>
            {% endif %}

            {% if c.pre_mortem %}
              <div class="section section-premortem">
                <strong>PRE-MORTEM:</strong> {{ c.pre_mortem.most_likely_failure }}
                <br><strong>Warning signs:</strong> {{ c.pre_mortem.warning_signs[:2]|join(' &middot; ') }}
              </div>
            {% endif %}

            {% if c.peer_benchmark %}
              <div style="font-size:10px; color:#666; margin-top:6px;">
                Peer rank ({{ c.peer_benchmark.peer_count }} peers): growth pctile <strong>{{ c.peer_benchmark.growth_percentile_avg }}</strong>, quality pctile <strong>{{ c.peer_benchmark.quality_percentile_avg }}</strong>
              </div>
            {% endif %}

            {% if c._aa_reason %}
              <div style="font-size:10px; color:#888; margin-top:4px; font-style:italic;">tier reasoning: {{ c._aa_reason }}</div>
            {% endif %}
          </div>
        {% endfor %}
      {% endif %}
    {% endfor %}
  {% endif %}

  {% if rejection_summary %}
    <div class="skip-noise">
      <strong style="color:#222;">Skip the noise — 5 rejected names + why:</strong>
      {% for r in rejection_summary[:5] %}
        <div style="margin-top:5px;"><strong>{{ r.ticker }}</strong> ({{ r.bracket }}): {{ r.reason }}</div>
      {% endfor %}
    </div>
  {% endif %}

  <div class="footer">micro/small/mid bracket scanner &middot; A-grade only &middot; live Alpaca chain &middot; Sonnet+web on top pick &middot; {{ scan_date }}</div>
</div>
</body>
</html>"""


def build_trade_ticket(candidate, regime_info=None):
    bracket = candidate.get("bracket") or "small"
    tier = candidate.get("_aa_tier") or "A"
    sizing = {
        ("micro", "A++"): (12, 50),
        ("micro", "A+"): (6, 50),
        ("micro", "A"): (4, 50),
        ("small", "A++"): (22, 40),
        ("small", "A+"): (12, 40),
        ("small", "A"): (8, 40),
        ("mid", "A++"): (30, 35),
        ("mid", "A+"): (17, 35),
        ("mid", "A"): (12, 35),
    }
    pos_pct, stop_pct = sizing.get((bracket, tier), (10, 40))
    if regime_info and regime_info.get("position_multiplier"):
        pos_pct = round(pos_pct * regime_info["position_multiplier"], 1)
        stop_pct = round(stop_pct * regime_info.get("stop_multiplier", 1.0), 0)
    analog = (candidate.get("analog_set") or {}).get("statistics") or {}
    win_rate = analog.get("win_rate_next_day_pct") or 50
    median_move = analog.get("median_next_day_pct") or 10
    avg_win_pct = max(median_move * 8, 150)
    ev = win_rate / 100 * avg_win_pct - (1 - win_rate / 100) * stop_pct
    return {
        "contract_label": "ATM-ish call (live chain at send-time)",
        "position_pct": pos_pct,
        "position_size_usd": "calculated at send",
        "stop_pct": stop_pct,
        "t1_pct": 50,
        "t1_trim_pct": 25,
        "t2_pct": 100,
        "t2_trim_pct": 33,
        "t3_pct": 200,
        "t3_trim_pct": 50,
        "runner_pct": 400,
        "ev_pct": round(ev, 1),
    }


def render_unified_email(scan, tier_results, picks_by_bracket, rejection_log, regime_info=None, execution_ctx=None):
    from jinja2 import Environment, BaseLoader
    from src.catalyst.humanize import register_jinja_filters
    from src.catalyst.bracket_router import bracket_label
    env = Environment(loader=BaseLoader())
    register_jinja_filters(env)
    env.globals["bracket_label"] = bracket_label
    tmpl = env.from_string(UNIFIED_EMAIL_TEMPLATE)

    a_plus_plus = tier_results.get("A++", [])
    a_plus = tier_results.get("A+", [])
    a = tier_results.get("A", [])
    total = sum(len(picks_by_bracket.get(b, [])) for b in ("micro", "small", "mid"))

    for bracket in ("micro", "small", "mid"):
        for c in picks_by_bracket.get(bracket, []):
            if not c.get("trade_ticket"):
                c["trade_ticket"] = build_trade_ticket(c, regime_info)

    portfolio_summary = scan.get("portfolio_summary")
    win_rate_stats = scan.get("win_rate_stats")
    try:
        from src.catalyst.portfolio_context import get_position_summary, get_recent_paper_trade_stats
        if not portfolio_summary:
            portfolio_summary = get_position_summary()
        if not win_rate_stats:
            win_rate_stats = get_recent_paper_trade_stats(lookback_days=30)
    except Exception:
        pass

    return tmpl.render(
        scan_date=scan.get("scan_date"),
        universe_size=scan.get("candidates_total", 0),
        total_picks=total,
        a_plus_plus_count=len(a_plus_plus),
        a_plus_count=len(a_plus),
        a_count=len(a),
        rejected_count=len(tier_results.get("REJECT", [])),
        picks_by_bracket=picks_by_bracket,
        rejection_summary=rejection_log,
        macro=scan.get("macro"),
        portfolio_summary=portfolio_summary,
        win_rate_stats=win_rate_stats,
        forward_calendar=scan.get("forward_calendar"),
        vol_regime=regime_info,
        execution_context=execution_ctx,
    )

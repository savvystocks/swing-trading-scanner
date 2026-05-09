from jinja2 import Template

from src.catalyst.lottery import build_lottery_ticket, get_account_settings
from src.catalyst.option_grader import grade_option_picks


CATALYST_OPTIONS_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,Helvetica,sans-serif; background:#fafafa; margin:0; padding:0;">
<div style="max-width:920px; margin:0 auto; background:#fff; padding:24px;">
  <h1 style="font-size:18px; margin:0 0 4px;">Catalyst Options Plays — {{ scan_date }}</h1>
  <div style="color:#666; font-size:11px; margin-bottom:16px;">
    Account ${{ "%.0f"|format(settings.account_size_usd) }} &middot;
    {{ settings.position_size_pct|round(0)|int }}% per trade &middot;
    Stop -{{ settings.stop_loss_pct|round(0)|int }}% &middot;
    Max {{ settings.max_concurrent }} concurrent &middot;
    Target {{ settings.target_return_pct|round(0)|int }}% in {{ settings.target_days }}d
  </div>

  {% if picks %}
    <div style="background:#fffbeb; border:1px solid #f59e0b; border-radius:6px; padding:10px 12px; margin-bottom:16px; font-size:11px; color:#92400e;">
      <strong>Lottery framework:</strong>
      Each pick is a defined-risk asymmetric bet. Premium decays. -50% premium stop activates if catalyst thesis breaks (support broken, vol crushed without move, or 50% of DTE elapsed without progress). Position size capped at {{ settings.position_size_pct|round(0)|int }}% of account per trade.
    </div>
  {% endif %}

  {% if skipped_tickers %}
    <div style="background:#fee2e2; border:1px solid #fca5a5; border-radius:6px; padding:10px 12px; margin-bottom:16px; font-size:11px; color:#7f1d1d;">
      <strong>LLM rated SKIP today (not shown):</strong>
      {% for tk in skipped_tickers %}{{ tk }}{% if not loop.last %}, {% endif %}{% endfor %}
      &middot; <em>IV/strike/spread misaligned for 500% target. Spread alternatives may still work — see Top Factors Options email.</em>
    </div>
  {% endif %}

  {% if not picks and not skipped_tickers %}
    <div style="padding:30px; text-align:center; color:#888;">No qualifying lottery setups today.</div>
  {% elif not picks %}
    <div style="padding:30px; text-align:center; color:#666;">All lottery picks today rated SKIP by LLM grader. See above for tickers and Top Factors Options email for tradeable alternatives.</div>
  {% endif %}

  {% if picks %}
    {% for p in picks %}
      {% set t = p.ticket %}
      {% set lt = p.lottery %}
      {% set live = p.live %}
      {% set conv = p.conviction_label %}
      <div style="border:2px solid {% if conv == 'HIGH' %}#0d7b34{% elif conv == 'MEDIUM' %}#1a9850{% else %}#4a90e2{% endif %}; border-radius:8px; padding:14px 16px; margin-bottom:14px; background:#fff;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:6px; margin-bottom:8px;">
          <div>
            <span style="font-size:18px; font-weight:700;">{{ t.ticker }}</span>
            <span style="font-size:11px; color:#555;">{{ (t.name or '')[:32] }}</span>
            <span style="display:inline-block; padding:2px 8px; border-radius:3px; background:{% if t.catalyst_tier == 'S' %}#0d7b34{% elif t.catalyst_tier == 'A' %}#1a9850{% elif t.catalyst_tier == 'B' %}#4a90e2{% else %}#888{% endif %}; color:#fff; font-size:11px; font-weight:700;">Tier {{ t.catalyst_tier }}</span>
            <span style="display:inline-block; padding:2px 8px; border-radius:3px; background:{% if conv == 'HIGH' %}#0d7b34{% elif conv == 'MEDIUM' %}#4a90e2{% else %}#888{% endif %}; color:#fff; font-size:11px; font-weight:700;">{{ conv }} CONV</span>
            {% if t.sector %}<span style="font-size:10px; color:#888; padding:2px 6px; background:#f0f0f0; border-radius:3px;">{{ t.sector }}</span>{% endif %}
            {% if t.market_cap %}<span style="font-size:10px; color:#666;">${{ "%.1f"|format(t.market_cap / 1e9) }}B mcap</span>{% endif %}
          </div>
          <div style="text-align:right;">
            {% if live and live.spot %}
              <span style="font-size:14px; font-weight:700;">${{ "%.2f"|format(live.spot) }}</span>
              <span style="font-size:11px; color:{% if live.change_pct >= 0 %}#0d7b34{% else %}#c94545{% endif %};">({{ "%+.2f"|format(live.change_pct) }}%)</span>
              <div style="font-size:10px; color:#888;">{{ live.session }}{% if live.age_min and live.age_min > 30 %} {{ "%.0f"|format(live.age_min) }}m old{% endif %}</div>
            {% else %}
              <span style="font-size:14px; font-weight:700;">${{ "%.2f"|format(t.price) }}</span>
              <div style="font-size:10px; color:#888;">EOD close</div>
            {% endif %}
          </div>
        </div>

        {% if t.catalysts %}
          <div style="font-size:11px; color:#444; margin-bottom:8px;">
          <strong>Catalysts firing:</strong>
          {% for c in t.catalysts[:5] %}
            <span style="display:inline-block; padding:1px 6px; margin:2px 2px 0 0; background:#f3f0fa; color:#5a3690; border-radius:3px; font-size:10px;">[{{ c.tier }}] {{ c.label }}{% if c.details %} — {{ c.details }}{% endif %}</span>
          {% endfor %}
          </div>
        {% endif %}

        {% if lt and lt.qualified %}
          {% set c = lt.contract %}
          {% set pos = lt.position %}
          {% set lo = lt.likely_outcome %}
          <div style="background:#fefce8; border:2px solid #eab308; border-radius:6px; padding:12px; margin-top:8px;">
            <div style="font-weight:700; color:#854d0e; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Lottery Contract — {{ "%.0f"|format(lt.settings.target_return_pct) }}% target</div>
            <div style="font-size:14px; font-weight:700; color:#111;">${{ "%.0f"|format(c.strike) }} CALL exp {{ c.expiration }} ({{ c.dte }} DTE)</div>
            <div style="font-size:12px; color:#444; margin-top:4px;">
              Premium <strong>${{ "%.2f"|format(c.mid) }}</strong>
              (bid ${{ "%.2f"|format(c.bid) }} / ask ${{ "%.2f"|format(c.ask) }} &middot; spread {{ c.spread_pct }}%)
              &middot; Δ {{ c.delta }} &middot; IV {{ c.iv_pct }}%
              &middot; <strong>${{ "%.0f"|format(c.cost_per_contract) }}/contract</strong>
            </div>
            {% if c.iv_crush_estimated_pct and c.iv_crush_estimated_pct > 0 %}
              <div style="margin-top:6px; padding:6px 10px; background:#fee2e2; border:1px solid #c94545; border-radius:4px; font-size:11px; color:#7f1d1d;">
                <strong>IV CRUSH adjustment:</strong> est {{ c.iv_crush_estimated_pct }}% IV drop post-event.
                True required move = <strong>{{ "%+.1f"|format(c.required_move_pct_iv_adjusted) }}%</strong> (stock to ${{ "%.2f"|format(c.target_stock_price_iv_adjusted) }})
                — premium also loses {{ c.iv_crush_estimated_pct }}% to vega alone, regardless of stock move.
              </div>
            {% endif %}
            <div style="margin-top:6px; padding:6px 10px; background:#fff; border-radius:4px; font-size:12px;">
              <strong>Position:</strong> {{ pos.contracts }} contract(s) = <strong>${{ "%.0f"|format(pos.total_cost_usd) }}</strong> ({{ pos.pct_of_account }}% of account)
              &middot; Stop @ ${{ "%.2f"|format(lt.stop_premium) }} (-{{ "%.0f"|format(lt.settings.stop_loss_pct) }}%) &rarr; max loss ${{ "%.0f"|format(lt.stop_dollars) }}
            </div>
            <div style="margin-top:6px; padding:6px 10px; background:#dcfce7; border-radius:4px; font-size:12px; color:#14532d;">
              <strong>500% target:</strong> stock to ${{ "%.2f"|format(c.target_stock_price) }} ({{ "%+.1f"|format(c.required_move_pct) }}%)
              &middot; Breakeven ${{ "%.2f"|format(c.breakeven) }} ({{ "%+.1f"|format(c.breakeven_pct_move) }}%)
            </div>
            <div style="margin-top:6px; padding:6px 10px; background:#f0f9ff; border-radius:4px; font-size:11px;">
              <strong>Profit Probability:</strong> {{ lt.profit_probability_pct }}%
              &middot; <strong>Expected Value:</strong> {{ "%+.1f"|format(lt.expected_value_pct) }}% per trade
              &middot; <strong>Likely:</strong>
              {{ lo.p_win_pct }}% chance +{{ lo.win_move_pct }}% to ${{ "%.2f"|format(lo.win_price) }}
              / {{ lo.p_loss_pct }}% stop triggered (-${{ "%.0f"|format(lt.stop_dollars) }})
            </div>
            {% if lt.spread_alternative %}
              {% set sp = lt.spread_alternative %}
              <div style="margin-top:8px; padding:8px 10px; background:#f0f8ff; border:1px solid #4a90e2; border-radius:4px; font-size:11px;">
                <div style="font-weight:700; color:#1a4d7c; font-size:11px; text-transform:uppercase; margin-bottom:3px;">Spread Alternative — defined-risk</div>
                <div>{{ "%.0f"|format(sp.long_leg.strike) }}/{{ "%.0f"|format(sp.short_leg.strike) }}C ({{ sp.width }}-wide) exp {{ sp.expiration }} ({{ sp.dte }}d)</div>
                <div style="color:#555;">Net debit ${{ "%.2f"|format(sp.net_debit) }} = <strong>${{ "%.0f"|format(sp.cost_per_spread) }}/spread</strong> &middot; Max profit ${{ "%.0f"|format(sp.max_profit_per_spread) }} &middot; R/R {{ sp.risk_reward_ratio }}</div>
                <div style="color:#555;">Breakeven ${{ "%.2f"|format(sp.breakeven) }} ({{ "%+.1f"|format(sp.breakeven_pct_move) }}%)</div>
              </div>
            {% endif %}

            {% if lt.llm_option_grade %}
              {% set og = lt.llm_option_grade %}
              {% set v_color = '#0d7b34' if og.verdict == 'BUY_AS_IS' else '#1a9850' if og.verdict == 'GO_CLOSER_ATM' or og.verdict == 'GO_FURTHER_OTM' else '#e67e22' if og.verdict == 'PREFER_SPREAD' else '#c94545' %}
              <div style="margin-top:10px; padding:10px 12px; background:#fef2f2; border:2px solid {{ v_color }}; border-radius:6px; font-size:11px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <div>
                    <strong style="color:#7c2d12; font-size:11px; text-transform:uppercase;">LLM option grade</strong>
                    <span style="display:inline-block; padding:2px 8px; margin-left:6px; border-radius:3px; background:{{ v_color }}; color:#fff; font-size:11px; font-weight:700;">{{ og.verdict | humanize_verdict }}</span>
                  </div>
                  {% if og.buy_score is defined %}<span style="font-size:14px; font-weight:700; color:{{ v_color }};">{{ og.buy_score }}/100</span>{% endif %}
                </div>
                <div style="color:#1f2937; margin-bottom:6px;">{{ og.verdict_reasoning }}</div>
                {% if og.suggested_alternative %}
                  <div style="margin-bottom:6px; padding:4px 8px; background:#fff7ed; border-left:3px solid #d97706; border-radius:3px; color:#7c2d12;">
                    <strong>Alternative:</strong> {{ og.suggested_alternative }}
                  </div>
                {% endif %}
                <table style="width:100%; font-size:10px; margin-top:4px; border-collapse:collapse;">
                  <tbody>
                    {% if og.iv_assessment %}
                      <tr style="border-bottom:1px solid #fecaca;"><td style="padding:3px 6px; font-weight:600;">IV</td>
                      <td style="padding:3px 6px;"><span style="padding:1px 6px; border-radius:3px; background:{% if og.iv_assessment.level == 'COMPRESSED' %}#0d7b34{% elif og.iv_assessment.level == 'FAIR' %}#4a90e2{% else %}#c94545{% endif %}; color:#fff;">{{ og.iv_assessment.level }}</span> {{ og.iv_assessment.iv_pct }}%</td>
                      <td style="padding:3px 6px; color:#444;">{{ og.iv_assessment.interpretation }}</td></tr>
                    {% endif %}
                    {% if og.iv_crush_risk %}
                      <tr style="border-bottom:1px solid #fecaca;"><td style="padding:3px 6px; font-weight:600;">IV crush</td>
                      <td style="padding:3px 6px;"><span style="padding:1px 6px; border-radius:3px; background:{% if og.iv_crush_risk.concern_level == 'LOW' %}#0d7b34{% elif og.iv_crush_risk.concern_level == 'MEDIUM' %}#e67e22{% else %}#c94545{% endif %}; color:#fff;">{{ og.iv_crush_risk.concern_level }}</span></td>
                      <td style="padding:3px 6px; color:#444;">est crush {{ og.iv_crush_risk.estimated_crush_pct }}% &middot; premium loss {{ og.iv_crush_risk.post_event_premium_loss_pct }}%</td></tr>
                    {% endif %}
                    {% if og.strike_efficiency %}
                      <tr style="border-bottom:1px solid #fecaca;"><td style="padding:3px 6px; font-weight:600;">Strike</td>
                      <td style="padding:3px 6px;"><span style="padding:1px 6px; border-radius:3px; background:{% if og.strike_efficiency.rating == 'GOOD' %}#0d7b34{% elif og.strike_efficiency.rating == 'OK' %}#4a90e2{% else %}#c94545{% endif %}; color:#fff;">{{ og.strike_efficiency.rating }}</span> Δ {{ og.strike_efficiency.delta }}</td>
                      <td style="padding:3px 6px; color:#444;">{{ og.strike_efficiency.comment }}</td></tr>
                    {% endif %}
                    {% if og.spread_quality %}
                      <tr style="border-bottom:1px solid #fecaca;"><td style="padding:3px 6px; font-weight:600;">Spread</td>
                      <td style="padding:3px 6px;"><span style="padding:1px 6px; border-radius:3px; background:{% if og.spread_quality.rating == 'TIGHT' %}#0d7b34{% elif og.spread_quality.rating == 'FAIR' %}#4a90e2{% else %}#c94545{% endif %}; color:#fff;">{{ og.spread_quality.rating }}</span> {{ og.spread_quality.spread_pct }}%</td>
                      <td style="padding:3px 6px; color:#444;">round-trip {{ og.spread_quality.round_trip_slippage_pct }}%</td></tr>
                    {% endif %}
                    {% if og.theta_burn %}
                      <tr><td style="padding:3px 6px; font-weight:600;">Theta</td>
                      <td style="padding:3px 6px;">{{ og.theta_burn.per_day_pct }}%/day</td>
                      <td style="padding:3px 6px; color:#444;">{{ og.theta_burn.warning }}</td></tr>
                    {% endif %}
                  </tbody>
                </table>
              </div>
            {% endif %}
          </div>
        {% else %}
          <div style="background:#fee2e2; border:1px solid #fca5a5; border-radius:6px; padding:8px 10px; margin-top:6px; font-size:11px; color:#7f1d1d;">
            No qualifying lottery contract: {{ lt.reason if lt else 'no chain' }}
          </div>
        {% endif %}

        {% if p.deep_research %}
          {% set dr = p.deep_research %}
          {% if dr.catalyst_status and dr.catalyst_status.status %}
            {% set cs = dr.catalyst_status %}
            {% set status_color = '#0d7b34' if cs.status == 'HAPPENED' else '#1a9850' if cs.status == 'SCHEDULED' else '#e67e22' if cs.status == 'EXPECTED' else '#888' %}
            <div style="margin-top:8px; padding:6px 10px; background:#fff; border:2px solid {{ status_color }}; border-radius:4px; font-size:11px;">
              <span style="display:inline-block; padding:2px 8px; border-radius:3px; background:{{ status_color }}; color:#fff; font-size:10px; font-weight:700;">{{ cs.status }}</span>
              {% if cs.countdown_label %}<strong style="margin-left:6px;">{{ cs.countdown_label }}</strong>{% endif %}
              {% if cs.event_date and cs.event_date != 'null' %}<span style="margin-left:6px; color:#666;">({{ cs.event_date }})</span>{% endif %}
            </div>
          {% endif %}

          {% if dr.lottery_thesis and dr.lottery_thesis.thesis_paragraph %}
            {% set lth = dr.lottery_thesis %}
            <div style="margin-top:8px; padding:8px 10px; background:#fefce8; border-left:3px solid #eab308; border-radius:4px; font-size:11px;">
              <strong style="color:#854d0e;">Lottery thesis:</strong>
              {% if lth.best_strike_otm_pct %}{{ lth.best_strike_otm_pct }}% OTM, {% endif %}
              {% if lth.best_dte_days %}{{ lth.best_dte_days }} DTE{% endif %}
              <div style="margin-top:3px; color:#1f2937;">{{ lth.thesis_paragraph }}</div>
            </div>
          {% endif %}

          {% if dr.analog_precedent and dr.analog_precedent.similar_setups %}
            {% set ap = dr.analog_precedent %}
            <div style="margin-top:6px; padding:6px 10px; background:#f5f3ff; border-left:3px solid #8b5cf6; border-radius:4px; font-size:10px;">
              <strong style="color:#5a3690;">Analogs</strong>
              {% if ap.win_rate_pct is defined %} &middot; win rate {{ ap.win_rate_pct }}%{% endif %}
              {% if ap.median_next_day_pct is defined %} &middot; median {{ "%+.1f"|format(ap.median_next_day_pct) }}%{% endif %}:
              {% for a in ap.similar_setups[:2] %}
                <span style="margin-left:4px;">{{ a.ticker }} {{ "%+.0f"|format(a.next_day_pct) }}% ({{ a.catalyst[:30] }}){% if not loop.last %},{% endif %}</span>
              {% endfor %}
            </div>
          {% endif %}

          {% if dr.stacking_analysis and dr.stacking_analysis.compounding_effect %}
            <div style="margin-top:6px; padding:6px 10px; background:#fef3c7; border-left:3px solid #d97706; border-radius:4px; font-size:10px;">
              <strong>Stacking:</strong>
              {% if dr.stacking_analysis.amplification_factor %}{{ dr.stacking_analysis.amplification_factor }}x amp &middot; {% endif %}
              {{ dr.stacking_analysis.compounding_effect }}
            </div>
          {% endif %}

        {% endif %}

        {% if false and p.inflection %}
          {% set inf = p.inflection %}
          <div style="margin-top:6px; font-size:10px; color:#555;">
            <strong>Inflection:</strong> {{ inf.label }}
            {% set firing = [] %}
            {% if inf.components.volatility_contraction.fired %}{% set _ = firing.append('vol contraction ' + (inf.components.volatility_contraction.percentile|string) + 'p') %}{% endif %}
            {% if inf.components.base_length.fired %}{% set _ = firing.append('base ' + (inf.components.base_length.weeks_in_base|string) + 'wk') %}{% endif %}
            {% if inf.components.higher_low.fired %}{% set _ = firing.append('higher low') %}{% endif %}
            {% if inf.components.stage_4_turnaround.fired %}{% set _ = firing.append('stage-4 turn ' + (inf.components.stage_4_turnaround.pct_off_low|string) + '% off low') %}{% endif %}
            {% if inf.components.volume_dry_up.fired %}{% set _ = firing.append('vol dry-up') %}{% endif %}
            {% if firing %}— {{ firing|join(', ') }}{% endif %}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% else %}
    <div style="padding:30px; text-align:center; color:#888;">No qualifying lottery setups today.</div>
  {% endif %}

  <div style="margin-top:20px; padding-top:14px; border-top:1px solid #eee; font-size:10px; color:#999;">
    catalyst-options companion email &middot; live Alpaca chain at send-time &middot; {{ scan_date }}
  </div>
</div>
</body>
</html>"""


def conviction_from_score(score, fired_count):
    if fired_count >= 4 or score >= 80:
        return "HIGH"
    if fired_count >= 2 or score >= 50:
        return "MEDIUM"
    return "LOW"


def enrich_with_live_options(picks, verbose=True):
    enriched = 0
    for p in picks:
        t = p.get("ticket") or {}
        ticker = t.get("ticker")
        eodhd_ticker = t.get("eodhd_ticker") or (f"{ticker}.US" if ticker else "")
        symbol = (eodhd_ticker or "").replace(".US", "").replace(".LSE", "")
        if not symbol:
            continue
        if not eodhd_ticker.endswith(".US"):
            continue

        live_price = t.get("live_spot") or t.get("price")
        if not live_price:
            continue

        deep = t.get("deep_research")
        try:
            lottery = build_lottery_ticket(symbol, live_price, deep_research_data=deep)
            p["lottery"] = lottery
            if lottery.get("qualified"):
                enriched += 1
                if verbose:
                    c = lottery["contract"]
                    print(f"  lottery {ticker}: {c['strike']:.0f}C {c['expiration']} @ ${c['mid']:.2f} (P_win {lottery['profit_probability_pct']}%, EV {lottery['expected_value_pct']:+.1f}%)")
            elif verbose:
                print(f"  lottery {ticker}: SKIP — {lottery.get('reason')}")
        except Exception as e:
            if verbose:
                print(f"  lottery {ticker}: error {type(e).__name__}: {e}")
            p["lottery"] = {"qualified": False, "reason": f"{type(e).__name__}"}
    if verbose:
        print(f"  options enrichment: {enriched}/{len(picks)} picks have qualified lottery contract")


def build_picks_for_options_email(scored_results, max_picks=3):
    candidates = [
        s for s in scored_results
        if s.get("buy_signal", {}).get("signal") == "BUY"
        and s.get("direction", "bull") == "bull"
        and not s.get("deal_closed")
    ]
    candidates.sort(key=lambda s: (s.get("score", 0), s.get("buy_signal", {}).get("probability_pct", 0)), reverse=True)
    candidates = candidates[:max_picks]

    picks = []
    for s in candidates:
        thesis = ""
        deep = s.get("deep_research") or {}
        thesis = deep.get("thesis") or deep.get("summary") or ""
        ticket = {
            "ticker": s["ticker"],
            "name": s.get("name") or s.get("company") or "",
            "eodhd_ticker": s.get("eodhd_ticker"),
            "sector": s.get("sector"),
            "market_cap": s.get("market_cap"),
            "price": s.get("price"),
            "live_spot": s.get("live_spot"),
            "live_change_pct": s.get("live_change_pct"),
            "live_session": s.get("live_session"),
            "live_age_min": s.get("live_age_min"),
            "catalyst_tier": s.get("catalyst_tier", "-"),
            "catalysts": s.get("catalysts") or [],
            "deep_research": s.get("deep_research"),
        }
        live = None
        if s.get("live_spot"):
            live = {
                "spot": s.get("live_spot"),
                "change_pct": s.get("live_change_pct") or 0,
                "session": s.get("live_session") or "?",
                "age_min": s.get("live_age_min") or 0,
            }
        fired_count = sum(1 for c in (s.get("components") or {}).values() if c.get("points", 0) > 0)
        picks.append({
            "ticket": ticket,
            "lottery": None,
            "live": live,
            "conviction_label": s.get("confidence", conviction_from_score(s.get("score", 0), fired_count)),
            "thesis": thesis[:280] if thesis else "",
            "inflection": s.get("inflection"),
            "deep_research": s.get("deep_research"),
        })
    return picks


def render_catalyst_options_email(scan):
    scored = scan.get("all_scored") or scan.get("candidates") or []
    picks = build_picks_for_options_email(scored, max_picks=8)
    try:
        from src.live_spot import enrich_with_live_spots
        for p in picks:
            t = p["ticket"]
            t["price"] = t.get("price") or 0
        enrich_with_live_spots([p["ticket"] for p in picks], verbose=True)
        for p in picks:
            t = p["ticket"]
            if t.get("live_spot"):
                p["live"] = {
                    "spot": t["live_spot"],
                    "change_pct": t.get("live_change_pct") or 0,
                    "session": t.get("live_session") or "?",
                    "age_min": t.get("live_age_min") or 0,
                }
    except Exception as e:
        print(f"  live_spot enrichment error: {type(e).__name__}: {e}")

    enrich_with_live_options(picks, verbose=True)

    try:
        grade_option_picks(picks, verbose=True)
    except Exception as e:
        print(f"  option_grader: skipped: {type(e).__name__}: {e}")

    actionable_picks = []
    skipped_tickers = []
    for p in picks:
        lottery = p.get("lottery") or {}
        if not lottery.get("qualified"):
            continue
        grade = lottery.get("llm_option_grade") or {}
        verdict = grade.get("verdict", "")
        if verdict == "SKIP":
            skipped_tickers.append(p.get("ticket", {}).get("ticker"))
        else:
            actionable_picks.append(p)

    settings = get_account_settings()
    from jinja2 import Environment, BaseLoader
    from src.catalyst.humanize import register_jinja_filters
    env = Environment(loader=BaseLoader())
    register_jinja_filters(env)
    tmpl = env.from_string(CATALYST_OPTIONS_TEMPLATE)
    return tmpl.render(
        scan_date=scan.get("scan_date"),
        settings=settings,
        picks=actionable_picks,
        skipped_tickers=skipped_tickers,
    )

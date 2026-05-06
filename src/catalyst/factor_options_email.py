from jinja2 import Template

from src.catalyst.lottery import build_lottery_ticket, get_account_settings
from src.catalyst.option_grader import grade_option_picks
from src.catalyst.factor_screener import screen_lower_caps, FACTOR_DEFINITIONS


TOP_20_FACTOR_TICKERS = (
    "SNDK", "LITE", "WDC", "STX", "CIEN", "MU", "SATS", "INTC", "COHR", "TER",
    "FIX", "AMD", "GLW", "LRCX", "VRT", "ALB", "WBD", "CAT", "GEV", "AMAT",
)


FACTOR_TARGET_RETURN_PCT = 150
FACTOR_DTE_MIN = 30
FACTOR_DTE_MAX = 45
FACTOR_OTM_MIN = 0
FACTOR_OTM_MAX = 10
FACTOR_DELTA_MIN = 0.30
FACTOR_DELTA_MAX = 0.70


FACTOR_OPTIONS_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,Helvetica,sans-serif; background:#fafafa; margin:0; padding:0;">
<div style="max-width:920px; margin:0 auto; background:#fff; padding:24px;">
  <h1 style="font-size:18px; margin:0 0 4px;">Top Factors Options — {{ scan_date }}</h1>
  <div style="color:#666; font-size:11px; margin-bottom:16px;">
    Standard call options on names matching the 20 factors that drove last year's top 20 movers. NOT lottery setups — target {{ target_return_pct }}% in 30-45 days, OTM 0-10%, position sized 20% of ${{ "%.0f"|format(settings.account_size_usd) }} = ${{ "%.0f"|format(position_budget) }} max per trade with -{{ stop_loss_pct }}% premium stop.
  </div>

  <div style="background:#dbeafe; border:1px solid #4a90e2; border-radius:6px; padding:10px 12px; margin-bottom:16px; font-size:11px; color:#1a4d7c;">
    <strong>How this email differs from Catalyst Email:</strong>
    Catalyst email targets binary events (earnings/FDA/M&A) with 500%-target lottery options (1-2 weeks, 5-18% OTM). This email targets ongoing factor exposure with calmer 150%-target options (1-1.5 months, 0-10% OTM). Money is made riding trends, not just betting on binary surprises.
  </div>

  {% if factor_matches %}
    <h2 style="font-size:15px; margin-top:20px; padding-top:12px; border-top:2px solid #5a3690; color:#5a3690;">Lower-Cap Factor Matches ($300M-$5B mcap)</h2>
    <div style="font-size:11px; color:#555; margin-bottom:12px;">
      Lower-cap names matching 2+ of the 20 factors that drove last year's top 20 movers. These are the next generation candidates — businesses sitting in the right themes with smaller market caps where re-rating is still possible. Sorted by factor count.
    </div>
    <table style="width:100%; font-size:11px; border-collapse:collapse; margin-bottom:18px;">
      <thead><tr style="background:#ede9fe;">
        <th align="left" style="padding:6px 8px;">Ticker</th>
        <th align="left" style="padding:6px 8px;">Name</th>
        <th align="right" style="padding:6px 8px;">Mcap</th>
        <th align="right" style="padding:6px 8px;">Price</th>
        <th align="right" style="padding:6px 8px;">Factors</th>
        <th align="left" style="padding:6px 8px;">Matched factors</th>
      </tr></thead>
      <tbody>
      {% for m in factor_matches %}
        <tr style="border-bottom:1px solid #ddd6fe;">
          <td style="padding:5px 8px; font-weight:700;">{{ m.ticker }}</td>
          <td style="padding:5px 8px; color:#444; font-size:10px;">{{ (m.name or '')[:24] }}</td>
          <td align="right" style="padding:5px 8px;">${{ "%.1f"|format((m.market_cap or 0) / 1e9) }}B</td>
          <td align="right" style="padding:5px 8px;">{% if m.live_spot %}<strong>${{ "%.2f"|format(m.live_spot) }}</strong>{% elif m.price %}${{ "%.2f"|format(m.price) }}{% else %}-{% endif %}</td>
          <td align="right" style="padding:5px 8px; font-weight:700; color:#5a3690;">{{ m.factor_count }}</td>
          <td style="padding:5px 8px; font-size:10px; color:#444;">
            {% for f in m.matched_factors[:6] %}
              <span style="display:inline-block; padding:1px 5px; margin:1px 2px 0 0; background:#f5f3ff; border:1px solid #ddd6fe; border-radius:3px;" title="{{ f.evidence|join(', ') }}">{{ f.factor_name|truncate(30) }}</span>
            {% endfor %}
          </td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  {% endif %}

  {% if picks %}
    {% for p in picks %}
      {% set t = p.ticket %}
      {% set lt = p.options %}
      {% set live = p.live %}
      <div style="border:2px solid {% if p.source == 'top_20_mover' %}#0d7b34{% else %}#8b5cf6{% endif %}; border-radius:8px; padding:14px 16px; margin-bottom:14px; background:#fff;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:6px; margin-bottom:8px;">
          <div>
            <span style="font-size:18px; font-weight:700;">{{ t.ticker }}</span>
            <span style="font-size:11px; color:#555;">{{ (t.name or '')[:32] }}</span>
            <span style="display:inline-block; padding:2px 8px; border-radius:3px; background:{% if p.source == 'top_20_mover' %}#0d7b34{% else %}#8b5cf6{% endif %}; color:#fff; font-size:11px; font-weight:700;">{{ p.source_label }}</span>
            {% if t.sector %}<span style="font-size:10px; color:#888; padding:2px 6px; background:#f0f0f0; border-radius:3px;">{{ t.sector }}</span>{% endif %}
            {% if t.market_cap %}<span style="font-size:10px; color:#666;">${{ "%.1f"|format(t.market_cap / 1e9) }}B mcap</span>{% endif %}
          </div>
          <div style="text-align:right;">
            {% if live and live.spot %}
              <span style="font-size:14px; font-weight:700;">${{ "%.2f"|format(live.spot) }}</span>
              <span style="font-size:11px; color:{% if live.change_pct >= 0 %}#0d7b34{% else %}#c94545{% endif %};">({{ "%+.2f"|format(live.change_pct) }}%)</span>
            {% elif t.price %}
              <span style="font-size:14px; font-weight:700;">${{ "%.2f"|format(t.price) }}</span>
              <div style="font-size:10px; color:#888;">EOD</div>
            {% else %}
              <span style="font-size:14px; font-weight:700; color:#888;">no price</span>
            {% endif %}
          </div>
        </div>

        {% if p.theme_note %}
          <div style="font-size:11px; color:#444; margin-bottom:6px; padding:5px 8px; background:#f5f3ff; border-left:3px solid #8b5cf6; border-radius:3px;">
            <strong style="color:#5a3690;">Theme:</strong> {{ p.theme_note }}
          </div>
        {% endif %}

        {% if lt and lt.qualified %}
          {% set c = lt.contract %}
          {% set pos = lt.position %}
          {% set lo = lt.likely_outcome %}
          <div style="background:#eff6ff; border:2px solid #4a90e2; border-radius:6px; padding:12px; margin-top:8px;">
            <div style="font-weight:700; color:#1e3a8a; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Standard Call Option — {{ "%.0f"|format(lt.settings.target_return_pct if lt.settings else target_return_pct) }}% target</div>
            <div style="font-size:14px; font-weight:700; color:#111;">${{ "%.0f"|format(c.strike) }} CALL exp {{ c.expiration }} ({{ c.dte }} DTE)</div>
            <div style="font-size:12px; color:#444; margin-top:4px;">
              Premium <strong>${{ "%.2f"|format(c.mid) }}</strong>
              (bid ${{ "%.2f"|format(c.bid) }} / ask ${{ "%.2f"|format(c.ask) }} &middot; spread {{ c.spread_pct }}%)
              &middot; Δ {{ c.delta }} &middot; IV {{ c.iv_pct }}%
              &middot; <strong>${{ "%.0f"|format(c.cost_per_contract) }}/contract</strong>
            </div>
            <div style="margin-top:6px; padding:6px 10px; background:#fff; border-radius:4px; font-size:12px;">
              <strong>Position:</strong> {{ pos.contracts }} contract(s) = <strong>${{ "%.0f"|format(pos.total_cost_usd) }}</strong> ({{ pos.pct_of_account }}% of account)
              &middot; Stop @ ${{ "%.2f"|format(lt.stop_premium) }} (-{{ "%.0f"|format(lt.settings.stop_loss_pct) }}%) &rarr; max loss ${{ "%.0f"|format(lt.stop_dollars) }}
            </div>
            <div style="margin-top:6px; padding:6px 10px; background:#dcfce7; border-radius:4px; font-size:12px; color:#14532d;">
              <strong>{{ "%.0f"|format(lt.settings.target_return_pct if lt.settings else target_return_pct) }}% target:</strong> stock to ${{ "%.2f"|format(c.target_stock_price) }} ({{ "%+.1f"|format(c.required_move_pct) }}%)
              &middot; Breakeven ${{ "%.2f"|format(c.breakeven) }} ({{ "%+.1f"|format(c.breakeven_pct_move) }}%)
            </div>
            {% if c.iv_crush_estimated_pct and c.iv_crush_estimated_pct > 0 %}
              <div style="margin-top:6px; padding:6px 10px; background:#fee2e2; border:1px solid #c94545; border-radius:4px; font-size:11px; color:#7f1d1d;">
                <strong>IV CRUSH:</strong> est {{ c.iv_crush_estimated_pct }}% drop. True required move = {{ "%+.1f"|format(c.required_move_pct_iv_adjusted) }}%
              </div>
            {% endif %}
            <div style="margin-top:6px; padding:6px 10px; background:#f0f9ff; border-radius:4px; font-size:11px;">
              <strong>Profit Probability:</strong> {{ lt.profit_probability_pct }}%
              &middot; <strong>Expected Value:</strong> {{ "%+.1f"|format(lt.expected_value_pct) }}%
              &middot; If wins: +${{ "%.0f"|format((lo.win_price - c.target_stock_price + (c.target_stock_price - c.strike) * 100 - lt.stop_dollars) | abs) }} ({{ lo.p_win_pct }}%)
              / If stops: -${{ "%.0f"|format(lt.stop_dollars) }} ({{ lo.p_loss_pct }}%)
            </div>
            {% if lt.spread_alternative %}
              {% set sp = lt.spread_alternative %}
              <div style="margin-top:8px; padding:8px 10px; background:#f0f8ff; border:1px solid #4a90e2; border-radius:4px; font-size:11px;">
                <div style="font-weight:700; color:#1a4d7c; font-size:11px; text-transform:uppercase; margin-bottom:3px;">Spread alternative</div>
                <div>{{ "%.0f"|format(sp.long_leg.strike) }}/{{ "%.0f"|format(sp.short_leg.strike) }}C ({{ sp.width }}-wide) exp {{ sp.expiration }}</div>
                <div style="color:#555;">Net debit ${{ "%.2f"|format(sp.net_debit) }} = <strong>${{ "%.0f"|format(sp.cost_per_spread) }}/spread</strong> &middot; Max profit ${{ "%.0f"|format(sp.max_profit_per_spread) }} &middot; R/R {{ sp.risk_reward_ratio }}</div>
              </div>
            {% endif %}

            {% if lt.llm_option_grade %}
              {% set og = lt.llm_option_grade %}
              {% set v_color = '#0d7b34' if og.verdict == 'BUY_AS_IS' else '#1a9850' if og.verdict == 'GO_CLOSER_ATM' or og.verdict == 'GO_FURTHER_OTM' else '#e67e22' if og.verdict == 'PREFER_SPREAD' else '#c94545' %}
              <div style="margin-top:10px; padding:10px 12px; background:#fef2f2; border:2px solid {{ v_color }}; border-radius:6px; font-size:11px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <div>
                    <strong style="color:#7c2d12; font-size:11px; text-transform:uppercase;">LLM option grade</strong>
                    <span style="display:inline-block; padding:2px 8px; margin-left:6px; border-radius:3px; background:{{ v_color }}; color:#fff; font-size:11px; font-weight:700;">{{ og.verdict }}</span>
                  </div>
                  {% if og.buy_score is defined %}<span style="font-size:14px; font-weight:700; color:{{ v_color }};">{{ og.buy_score }}/100</span>{% endif %}
                </div>
                <div style="color:#1f2937; margin-bottom:6px;">{{ og.verdict_reasoning }}</div>
                {% if og.suggested_alternative %}
                  <div style="margin-bottom:6px; padding:4px 8px; background:#fff7ed; border-left:3px solid #d97706; border-radius:3px; color:#7c2d12;">
                    <strong>Alternative:</strong> {{ og.suggested_alternative }}
                  </div>
                {% endif %}
                <table style="width:100%; font-size:10px; border-collapse:collapse;">
                  <tbody>
                    {% if og.iv_assessment %}
                      <tr><td style="padding:3px 6px; font-weight:600;">IV</td><td style="padding:3px 6px;"><span style="padding:1px 6px; border-radius:3px; background:{% if og.iv_assessment.level == 'COMPRESSED' %}#0d7b34{% elif og.iv_assessment.level == 'FAIR' %}#4a90e2{% else %}#c94545{% endif %}; color:#fff;">{{ og.iv_assessment.level }}</span> {{ og.iv_assessment.iv_pct }}%</td><td style="padding:3px 6px; color:#444;">{{ og.iv_assessment.interpretation }}</td></tr>
                    {% endif %}
                    {% if og.strike_efficiency %}
                      <tr><td style="padding:3px 6px; font-weight:600;">Strike</td><td style="padding:3px 6px;"><span style="padding:1px 6px; border-radius:3px; background:{% if og.strike_efficiency.rating == 'GOOD' %}#0d7b34{% elif og.strike_efficiency.rating == 'OK' %}#4a90e2{% else %}#c94545{% endif %}; color:#fff;">{{ og.strike_efficiency.rating }}</span> Δ {{ og.strike_efficiency.delta }}</td><td style="padding:3px 6px; color:#444;">{{ og.strike_efficiency.comment }}</td></tr>
                    {% endif %}
                    {% if og.spread_quality %}
                      <tr><td style="padding:3px 6px; font-weight:600;">Spread</td><td style="padding:3px 6px;"><span style="padding:1px 6px; border-radius:3px; background:{% if og.spread_quality.rating == 'TIGHT' %}#0d7b34{% elif og.spread_quality.rating == 'FAIR' %}#4a90e2{% else %}#c94545{% endif %}; color:#fff;">{{ og.spread_quality.rating }}</span> {{ og.spread_quality.spread_pct }}%</td><td style="padding:3px 6px;"></td></tr>
                    {% endif %}
                  </tbody>
                </table>
              </div>
            {% endif %}
          </div>
        {% else %}
          <div style="background:#fee2e2; border:1px solid #fca5a5; border-radius:6px; padding:8px 10px; margin-top:6px; font-size:11px; color:#7f1d1d;">
            No qualifying options contract: {{ lt.reason if lt else 'no chain' }}
          </div>
        {% endif %}
      </div>
    {% endfor %}
  {% else %}
    <div style="padding:30px; text-align:center; color:#888;">No qualifying factor options today.</div>
  {% endif %}

  <div style="margin-top:20px; padding-top:14px; border-top:1px solid #eee; font-size:10px; color:#999;">
    catalyst-scanner top-factors options &middot; live Alpaca chain at send-time &middot; {{ scan_date }}
  </div>
</div>
</body>
</html>"""


THEME_NOTES = {
    "SNDK": "AI-driven NAND shortage + spinoff pure-play premium. Datacenter rev +645% YoY.",
    "LITE": "NVIDIA $2B strategic stake + 1.6T optical transceiver order book booked into 2028.",
    "WDC": "Hyperscaler nearline HDD demand for AI training data. Capacity sold through 2026.",
    "STX": "Mozaic HAMR drives sold out through 2027. Q4 guide above Street.",
    "CIEN": "WaveLogic 6 winning AI long-haul/DCI builds. Cloud-direct rev +76% YoY.",
    "MU": "HBM3E/HBM4 sold out through 2026 to NVIDIA + AMD. Memory pricing cycle.",
    "SATS": "Spectrum monetization (sold to AT&T + SpaceX). 52M SpaceX shares = IPO proxy.",
    "INTC": "Foundry pipeline LTV >$15B (Microsoft 18A, AWS, Tesla 14A). Turnaround.",
    "COHR": "NVIDIA $2B strategic. Datacom rev +36% YoY. Optical interconnects.",
    "TER": "Magnum EPIC = industry-standard HBM tester. Won share back from Advantest.",
    "FIX": "Mechanical contractor for AI data center construction. Backlog >$11.94B.",
    "AMD": "OpenAI 6 GW MI400/450 deal (~$100B+) + Meta multi-GW. 2nm AI accelerator.",
    "GLW": "$6B Meta optical fiber deal + 2 more hyperscalers at similar scale.",
    "LRCX": "HBM4 ramp + GAA transition. WFE forecast raised to $140B.",
    "VRT": "Liquid cooling for high-density AI racks. Backlog doubled to $15B+.",
    "ALB": "Lithium recovery. EV PHEV +33%, BESS +40% YoY. China cuts tightened market.",
    "WBD": "Paramount Skydance $110.9B takeover bid (Feb 2026). HBO Max growth.",
    "CAT": "Power & Energy data center generators. Backlog $63B record. AIP 2 GW.",
    "GEV": "Gas turbine backlog 100 GW (up from 83 GW). $2.4B Q1 electrification orders.",
    "AMAT": "DRAM equipment for HBM packaging. Semicap >20% growth guide CY26.",
}


def build_factor_options_picks(scored_results, max_picks=8):
    by_ticker = {s.get("ticker"): s for s in scored_results if s.get("ticker")}

    picks = []
    used = set()

    for tk in TOP_20_FACTOR_TICKERS:
        if tk in used:
            continue
        s = by_ticker.get(tk) or {}
        ticket = {
            "ticker": tk,
            "name": s.get("name") or s.get("company") or "",
            "eodhd_ticker": s.get("eodhd_ticker") or f"{tk}.US",
            "sector": s.get("sector"),
            "industry": s.get("industry"),
            "market_cap": s.get("market_cap"),
            "price": s.get("price"),
            "live_spot": s.get("live_spot"),
            "live_change_pct": s.get("live_change_pct"),
            "live_session": s.get("live_session"),
            "live_age_min": s.get("live_age_min"),
            "deep_research": s.get("deep_research"),
        }
        picks.append({
            "ticket": ticket,
            "options": None,
            "live": None,
            "source": "top_20_mover",
            "source_label": "TOP 20 MOVER",
            "theme_note": THEME_NOTES.get(tk, ""),
        })
        used.add(tk)
        if len(picks) >= max_picks:
            break

    if len(picks) < max_picks:
        for s in scored_results:
            tk = s.get("ticker")
            if not tk or tk in used:
                continue
            inf = s.get("inflection") or {}
            if inf.get("label") in ("STAGE_4_TURNAROUND", "COILED_BASE", "TURNING_UP"):
                ticket = {
                    "ticker": tk,
                    "name": s.get("name") or s.get("company") or "",
                    "eodhd_ticker": s.get("eodhd_ticker") or f"{tk}.US",
                    "sector": s.get("sector"),
                    "industry": s.get("industry"),
                    "market_cap": s.get("market_cap"),
                    "price": s.get("price"),
                    "live_spot": s.get("live_spot"),
                    "live_change_pct": s.get("live_change_pct"),
                    "live_session": s.get("live_session"),
                    "live_age_min": s.get("live_age_min"),
                    "deep_research": s.get("deep_research"),
                }
                picks.append({
                    "ticket": ticket,
                    "options": None,
                    "live": None,
                    "source": "inflection",
                    "source_label": f"INFLECTION ({inf['label']})",
                    "theme_note": f"Technical setup: {inf['label']} firing — {inf.get('components_fired', 0)} sub-signals active",
                })
                used.add(tk)
                if len(picks) >= max_picks:
                    break

    return picks


def enrich_with_standard_options(picks, verbose=True):
    enriched = 0
    for p in picks:
        t = p.get("ticket") or {}
        ticker = t.get("ticker")
        eodhd_ticker = t.get("eodhd_ticker") or (f"{ticker}.US" if ticker else "")
        if not eodhd_ticker.endswith(".US"):
            continue
        symbol = eodhd_ticker.replace(".US", "")
        live_price = t.get("live_spot") or t.get("price")
        if not symbol or not live_price:
            continue
        deep = t.get("deep_research")
        try:
            options = build_lottery_ticket(
                symbol,
                live_price,
                deep_research_data=deep,
                dte_min=FACTOR_DTE_MIN,
                dte_max=FACTOR_DTE_MAX,
                otm_pct_min=FACTOR_OTM_MIN,
                otm_pct_max=FACTOR_OTM_MAX,
                target_return_pct=FACTOR_TARGET_RETURN_PCT,
                delta_min=FACTOR_DELTA_MIN,
                delta_max=FACTOR_DELTA_MAX,
            )
            p["options"] = options
            if options.get("qualified"):
                enriched += 1
                if verbose:
                    c = options["contract"]
                    print(f"  factor_opt {ticker}: {c['strike']:.0f}C {c['expiration']} @ ${c['mid']:.2f} (P_win {options['profit_probability_pct']}%, EV {options['expected_value_pct']:+.1f}%)")
            elif verbose:
                print(f"  factor_opt {ticker}: SKIP — {options.get('reason')}")
        except Exception as e:
            if verbose:
                print(f"  factor_opt {ticker}: error {type(e).__name__}: {e}")
            p["options"] = {"qualified": False, "reason": f"{type(e).__name__}"}
    if verbose:
        print(f"  factor options enrichment: {enriched}/{len(picks)} picks have qualified contract")


def grade_factor_options(picks, verbose=True):
    adapted = []
    for p in picks:
        wrapped = {
            "ticket": p["ticket"],
            "lottery": p.get("options"),
            "live": p.get("live"),
        }
        adapted.append(wrapped)
    grade_option_picks(adapted, verbose=verbose)
    for orig, w in zip(picks, adapted):
        if w.get("lottery") and w["lottery"].get("llm_option_grade"):
            orig["options"]["llm_option_grade"] = w["lottery"]["llm_option_grade"]


def _load_universe_factor_screen(scan_date):
    import os, json
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(project_root, "data", "results", f"factor_screen_{scan_date}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("matches") or []
    except Exception:
        return []


def render_factor_options_email(scan):
    scored = scan.get("all_scored") or scan.get("candidates") or []
    picks = build_factor_options_picks(scored, max_picks=8)

    try:
        from src.alpaca_options import get_live_price
        for p in picks:
            t = p["ticket"]
            if t.get("price") and t["price"] > 0:
                continue
            symbol = (t.get("eodhd_ticker") or "").replace(".US", "").replace(".LSE", "")
            if not symbol:
                continue
            live_price = get_live_price(symbol)
            if live_price:
                t["price"] = live_price
                t["live_spot"] = live_price
                t["live_change_pct"] = 0
                t["live_session"] = "fetched"
    except Exception as e:
        print(f"  factor get_live_price seed: {type(e).__name__}: {e}")

    try:
        from src.live_spot import enrich_with_live_spots
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
        print(f"  factor live_spot enrichment error: {type(e).__name__}: {e}")

    enrich_with_standard_options(picks, verbose=True)

    try:
        grade_factor_options(picks, verbose=True)
    except Exception as e:
        print(f"  factor option grader: skipped: {type(e).__name__}: {e}")

    factor_matches = []
    try:
        try:
            from src.eodhd import EODHDClient
            client = EODHDClient()
            small_caps = [s for s in scored if 300_000_000 <= (s.get("market_cap") or 0) <= 5_000_000_000]
            backfilled = 0
            for s in small_caps:
                if s.get("industry") and s.get("description"):
                    continue
                tk = s.get("eodhd_ticker") or (f"{s.get('ticker')}.US" if s.get("ticker") else None)
                if not tk:
                    continue
                try:
                    fund = client.fundamentals(tk)
                    if fund:
                        general = fund.get("General", {}) or {}
                        s["industry"] = s.get("industry") or general.get("Industry", "") or ""
                        s["description"] = s.get("description") or (general.get("Description", "") or "")[:600]
                        backfilled += 1
                except Exception:
                    pass
            print(f"  factor_screener: backfilled industry+description for {backfilled} small-caps")
        except Exception as e:
            print(f"  factor_screener backfill error: {type(e).__name__}: {e}")

        universe_matches = _load_universe_factor_screen(scan.get("scan_date"))
        if universe_matches:
            print(f"  factor_screener: using universe-wide factor screen ({len(universe_matches)} matches)")
            factor_matches = universe_matches[:25]
        else:
            print(f"  factor_screener: no universe screen file found, falling back to catalyst-pipeline names")
            factor_matches = screen_lower_caps(scored, mcap_max=5_000_000_000, mcap_min=300_000_000, min_factor_count=2)
            factor_matches = factor_matches[:20]
        if factor_matches:
            try:
                from src.live_spot import enrich_with_live_spots
                enrich_with_live_spots(factor_matches, verbose=False)
            except Exception as e:
                print(f"  factor_matches live_spot: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  factor screener error: {type(e).__name__}: {e}")

    settings = get_account_settings()
    position_budget = settings["account_size_usd"] * settings["position_size_pct"] / 100
    tmpl = Template(FACTOR_OPTIONS_TEMPLATE)
    return tmpl.render(
        scan_date=scan.get("scan_date"),
        settings=settings,
        position_budget=position_budget,
        stop_loss_pct=int(settings["stop_loss_pct"]),
        target_return_pct=FACTOR_TARGET_RETURN_PCT,
        picks=picks,
        factor_matches=factor_matches,
    )

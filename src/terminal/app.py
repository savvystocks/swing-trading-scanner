import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import streamlit as st
import pandas as pd

from src.terminal import data as D
from src.terminal import formatters as F

try:
    from src.catalyst.humanize import humanize_catalyst_key, humanize_catalyst_list
except ImportError:
    def humanize_catalyst_key(k):
        return (k or "").replace("_", " ").strip()
    def humanize_catalyst_list(cats, max_items=4):
        return [(c.get("key") if isinstance(c, dict) else str(c)) for c in (cats or [])[:max_items]]


st.set_page_config(
    page_title="Swing Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
[data-testid="stAppViewContainer"] { background:#0c1218; }
[data-testid="stSidebar"] { background:#0a0e14; }
h1, h2, h3 { color:#e8eef5; }
.score-strong { background:linear-gradient(135deg, #065f46, #047857); color:#fff; padding:10px 14px; border-radius:10px; font-weight:700; }
.score-good { background:linear-gradient(135deg, #15803d, #16a34a); color:#fff; padding:10px 14px; border-radius:10px; font-weight:700; }
.score-borderline { background:linear-gradient(135deg, #a16207, #ca8a04); color:#fff; padding:10px 14px; border-radius:10px; font-weight:700; }
.score-watch { background:linear-gradient(135deg, #475569, #64748b); color:#fff; padding:10px 14px; border-radius:10px; font-weight:700; }
.score-avoid { background:linear-gradient(135deg, #b91c1c, #dc2626); color:#fff; padding:10px 14px; border-radius:10px; font-weight:700; }
.bull-box { background:#062f1f; border-left:4px solid #15803d; padding:12px 16px; border-radius:6px; color:#a7f3d0; margin:8px 0; }
.bear-box { background:#3f0a0a; border-left:4px solid #b91c1c; padding:12px 16px; border-radius:6px; color:#fca5a5; margin:8px 0; }
.catalyst-box { background:#0f1419; border-left:4px solid #6b7280; padding:10px 14px; border-radius:6px; color:#cbd5e1; margin:8px 0; }
.kpi-card { background:#111827; border:1px solid #1f2937; padding:14px 16px; border-radius:8px; }
.kpi-label { font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.6px; }
.kpi-value { font-size:24px; color:#e8eef5; font-weight:700; margin-top:4px; }
.kpi-value.win { color:#22c55e; }
.kpi-value.lose { color:#ef4444; }
.muted { color:#94a3b8; font-size:13px; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _verdict_class(verdict):
    return {
        "TAKE THIS": "score-strong",
        "GOOD SETUP": "score-good",
        "BORDERLINE": "score-borderline",
        "WAIT FOR BETTER": "score-watch",
        "AVOID": "score-avoid",
    }.get(verdict, "score-watch")


def kpi(label, value, value_class=""):
    cls = f"kpi-value {value_class}".strip()
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="{cls}">{value}</div></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=30)
def _load_scan_cached(date):
    scan = D.load_scan(date)
    if scan is None:
        return None
    return scan


def _fetch_live_premarket(ticker):
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return None
    try:
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        c = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
        q = c.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=[ticker]))
        info = q.get(ticker)
        if not info:
            return None
        bid = float(info.bid_price) if info.bid_price else 0
        ask = float(info.ask_price) if info.ask_price else 0
        mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else (bid or ask)
        return {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_pct": ((ask - bid) / mid * 100) if mid else 0,
            "timestamp": info.timestamp.isoformat() if info.timestamp else "",
        }
    except Exception:
        return None


@st.cache_data(ttl=60)
def _fetch_live_quotes_batch(tickers_tuple):
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return {}
    if not tickers_tuple:
        return {}
    try:
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        c = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
        us_tickers = [t for t in tickers_tuple if t and "." not in t]
        if not us_tickers:
            return {}
        q = c.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=us_tickers))
        out = {}
        for t, info in q.items():
            try:
                bid = float(info.bid_price) if info.bid_price else 0
                ask = float(info.ask_price) if info.ask_price else 0
                mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else (bid or ask)
                out[t] = {"bid": bid, "ask": ask, "mid": mid}
            except Exception:
                continue
        return out
    except Exception:
        return {}


def render_pick_detail(pick):
    d = F.pick_full_detail(pick)
    overall = d.get("overall") or {}
    surv = d.get("survival") or {}
    eq = d.get("earnings_quality") or {}
    forensic = d.get("llm_forensic") or {}
    bear = d.get("bear") or {}
    vol = d.get("vol_micro") or {}
    riv = (vol.get("realized_vs_implied") or {})
    sk = (vol.get("skew") or {})
    multi = d.get("multi_leg") or []
    stage2 = pick.get("_stage2_zone") or {}
    fresh = pick.get("_fresh_context") or {}

    live = _fetch_live_premarket(d.get("ticker", ""))
    live_change_pct = None
    if live and d.get("price"):
        try:
            scan_price = float(d.get("price"))
            if scan_price > 0 and live.get("mid"):
                live_change_pct = (live["mid"] - scan_price) / scan_price * 100
        except (TypeError, ValueError):
            pass

    try:
        from src.catalyst.action_signal import compute_action
        action = compute_action(pick, live_change_pct=live_change_pct)
    except Exception:
        action = {"action": "WATCH", "badge": "🟡 WATCH", "why": "Action signal unavailable"}

    action_color = {
        "TAKE": "#065f46",
        "WATCH": "#a16207",
        "SKIP": "#475569",
        "AVOID": "#b91c1c",
    }.get(action["action"], "#6b7280")
    action_bg = {
        "TAKE": "#ecfdf5",
        "WATCH": "#fefce8",
        "SKIP": "#f9fafb",
        "AVOID": "#fef2f2",
    }.get(action["action"], "#f9fafb")
    st.markdown(
        f'<div style="background:{action_bg};border-left:6px solid {action_color};padding:18px 22px;border-radius:8px;margin:10px 0">'
        f'<div style="font-size:28px;font-weight:800;color:{action_color}">{action["badge"]}</div>'
        f'<div style="font-size:14px;color:#374151;margin-top:6px">{action["why"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if live and d.get("price"):
        try:
            scan_price = float(d.get("price"))
        except (TypeError, ValueError):
            scan_price = 0
        if scan_price > 0 and live.get("mid"):
            change_pct = (live["mid"] - scan_price) / scan_price * 100
            color_tag = "green" if change_pct >= 0 else "red"
            sign = "+" if change_pct >= 0 else ""
            st.markdown(
                f"**{d['ticker']}** · {d.get('name','—')} · ${scan_price:.2f} close → "
                f":{color_tag}[**{sign}{change_pct:.2f}%**] live "
                f"(${live['mid']:.2f}, bid ${live['bid']:.2f}/ask ${live['ask']:.2f})"
            )

    live_option = pick.get("_live_option") or {}
    if live_option and action.get("action") in ("TAKE", "WATCH"):
        strike = live_option.get("strike", "?")
        exp = live_option.get("exp", "?")
        mid = live_option.get("mid", 0)
        bid = live_option.get("bid", 0)
        ask = live_option.get("ask", 0)
        delta = live_option.get("delta", 0)
        iv = live_option.get("iv_pct", 0)
        cost = mid * 100 if mid else 0
        overall_obj_inner = pick.get("_overall_score") or {}
        pop_val = overall_obj_inner.get("probability_of_profit_pct", "—")

        outcome_8 = None
        outcomes_list = []
        try:
            from src.catalyst.live_option_picker import project_outcomes
            live_spot_for_calc = live.get("mid") if (live and live.get("mid")) else float(d.get("price") or 0)
            if live_spot_for_calc:
                outcomes_list, _ = project_outcomes(live_option, live_spot_for_calc)
                outcome_8 = next((o for o in outcomes_list if o.get("underlying_pct") == 8), None)
        except Exception:
            pass

        st.markdown(
            f'<div style="background:#0c1e3a;border-left:6px solid #2563eb;padding:18px 22px;border-radius:8px;margin:10px 0">'
            f'<div style="font-size:12px;font-weight:700;color:#93c5fd;letter-spacing:0.8px">📝 RECOMMENDED OPTION CONTRACT</div>'
            f'<div style="font-size:20px;font-weight:800;color:#e8eef5;margin-top:6px">'
            f'Buy {d["ticker"]} ${strike:.0f} call expiring {exp} at ${mid:.2f} per share'
            f'</div>'
            f'<div style="font-size:14px;color:#cbd5e1;margin-top:8px">'
            f'<b>${cost:.0f}</b> per contract &nbsp;·&nbsp; '
            f'<b>Chance of profit: {pop_val}%</b> &nbsp;·&nbsp; '
            f'If stock +8% → option <b style="color:#22c55e">{("+%.0f" % outcome_8["return_pct"]) if outcome_8 else "?"}%</b>'
            f'</div>'
            f'<div style="font-size:12px;color:#94a3b8;margin-top:6px">'
            f'Bid ${bid:.2f} / Ask ${ask:.2f} &nbsp;·&nbsp; Delta {delta} &nbsp;·&nbsp; IV {iv}%'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    oi = pick.get("_openinsider") or {}
    flow = pick.get("_options_flow_diy") or {}
    analyst = pick.get("_analyst_rating_changes") or {}
    whisper = pick.get("_earnings_whisper") or {}
    congress = pick.get("_congressional_trades") or {}
    wsb = pick.get("_wsb_mentions") or {}
    trends = pick.get("_google_trends") or {}

    smart_signals = []
    if oi and oi.get("buyers_count"):
        ceo_cfo = " 👔 CEO/CFO" if oi.get("ceo_or_cfo_bought") else ""
        recency = oi.get("recency_days")
        rec = f" · {recency}d ago" if recency is not None else ""
        smart_signals.append(
            f"**💰 Insider cluster:** {oi['buyers_count']} buyers spent ${oi['total_value_usd']:,}{ceo_cfo}{rec}"
        )
    if flow and flow.get("verdict") in ("STRONG_FLOW", "MODERATE_FLOW"):
        sig_str = " · ".join(flow.get("signals", [])[:2])
        smart_signals.append(f"**📊 Options flow ({flow['verdict']}):** {sig_str}")
    if analyst and analyst.get("verdict") in ("UPGRADE_CLUSTER", "BULLISH_LEAN"):
        smart_signals.append(
            f"**📈 Analyst lean:** {analyst['upgrades_count']} upgrade signals in recent news"
            + (f" ({analyst['upgrade_examples'][0][:80]}...)" if analyst.get("upgrade_examples") else "")
        )
    if analyst and analyst.get("verdict") in ("DOWNGRADE_CLUSTER", "BEARISH_LEAN"):
        smart_signals.append(
            f"**📉 Analyst lean BEARISH:** {analyst['downgrades_count']} downgrade signals in recent news"
        )
    if whisper and whisper.get("verdict") == "WHISPER_ABOVE_CONSENSUS":
        smart_signals.append(
            f"**🤫 Whisper EPS ${whisper.get('whisper_eps')} vs consensus ${whisper.get('consensus_eps')}** "
            f"(+{whisper.get('delta_pct')}%) — street expects beat"
        )
    if whisper and whisper.get("verdict") == "WHISPER_BELOW_CONSENSUS":
        smart_signals.append(
            f"**🤫 Whisper EPS below consensus by {whisper.get('delta_pct')}%** — street expects miss"
        )
    if congress and congress.get("purchases_60d", 0) > 0:
        smart_signals.append(
            f"**🏛️ Congress activity:** {congress['purchases_60d']} purchases in last 60d "
            f"by {congress.get('unique_members', 0)} member(s)"
        )
    if wsb and wsb.get("verdict") in ("HEAVY_BUZZ", "ELEVATED_BUZZ"):
        smart_signals.append(
            f"**🚀 WSB buzz {wsb['verdict']}:** {wsb['mentions_7d']} mentions in last 7d "
            f"({wsb.get('spike_ratio')}x baseline)"
        )
    if trends and trends.get("verdict") in ("TRENDING_UP", "ELEVATED"):
        smart_signals.append(
            f"**🔥 Google Trends {trends['verdict']}:** retail search volume {trends.get('spike_ratio')}x baseline"
        )

    if smart_signals:
        st.markdown("---")
        st.markdown("**🎯 Smart Money & Buzz Layer**")
        for s in smart_signals:
            st.markdown(s)
        st.markdown("---")

    if d.get("catalysts_human"):
        st.markdown(
            "**Driving this:** " + " · ".join(d["catalysts_human"][:3]),
        )

    if forensic.get("bull"):
        st.markdown(f"**Bull thesis:** {forensic['bull'][:280]}")

    if bear.get("killer") and (bear.get("is_trap") or (bear.get("conviction") or 0) >= 50):
        trap_str = " ⚠️ TRAP" if bear.get("is_trap") else ""
        st.markdown(f"**Bear risk{trap_str}:** {bear['killer'][:240]}")

    with st.expander("📊 Full numbers (Overall, Survival, Quality, Tier, components)", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            kpi("Chance of profit", f"{overall.get('probability_of_profit_pct', '—')}%")
        with c2:
            kpi("Survival score", f"{surv.get('score', '—')}/100")
        with c3:
            kpi("Earnings quality", eq.get("rating", "—"))
        with c4:
            kpi("Catalyst stack", f"{d.get('cat_count', '—')} cats")
        with c5:
            kpi("Tier", d.get("tier", "—"))
        st.markdown(
            f"5d {F.fmt_pct(d.get('ret_5d'))} · 30d {F.fmt_pct(d.get('ret_30d'))} · 90d {F.fmt_pct(d.get('ret_90d'))} · "
            f"Stacked score {d.get('stacked_score','—')} · LLM {forensic.get('verdict','—')} {forensic.get('confidence','—')}% · "
            f"IV pctile {d.get('iv_percentile','—')}"
        )
        components = overall.get("components") or {}
        if components:
            comp_df = pd.DataFrame([
                {"Component": k.replace("_", " ").title(), "Score": v}
                for k, v in components.items()
            ])
            st.dataframe(comp_df, hide_index=True, use_container_width=True, height=240)

    risks_to_show = []
    if surv.get("kill_risks"):
        risks_to_show.extend(surv["kill_risks"][:3])
    if risks_to_show:
        with st.expander(f"⚠️ Survival risks ({len(risks_to_show)})", expanded=False):
            for kr in risks_to_show:
                st.markdown(f"- {kr}")

    if riv.get("note") or sk.get("bias_note") or stage2:
        with st.expander("📈 Setup details (vol, skew, Stage 2 zone)", expanded=False):
            if stage2:
                zone = stage2.get("zone", "?")
                zone_color = {"PRIME_ENTRY": "🟢", "EARLY_CONTINUATION": "🟢", "CONTINUATION": "🟡", "EXTENDED": "🟠", "CLIMAX": "🔴", "NOT_IN_STAGE2": "⚫"}.get(zone, "⚪")
                st.markdown(f"**Stage 2 zone:** {zone_color} {zone} — {stage2.get('note', '')}")
            if riv.get("note"):
                st.write(f"**Vol:** {riv['note']}")
            if sk.get("bias_note"):
                st.write(f"**Skew:** {sk['bias_note']}")

    if multi:
        with st.expander(f"💡 Structure ideas ({len(multi)})", expanded=False):
            for s in multi:
                details = s.get("details", "")
                st.markdown(f"**{s.get('structure', '—')}** — {s.get('rationale', '—')}")
                if details:
                    st.caption(details)

    fc_alpaca = fresh.get("alpaca_news_7d") or []
    fc_eodhd = fresh.get("eodhd_news") or []
    fc_edgar = fresh.get("edgar_filings") or []
    total_news = len(fc_alpaca) + len(fc_eodhd) + len(fc_edgar)
    if total_news:
        with st.expander(f"📰 Fresh news & filings ({total_news} items the LLM saw)", expanded=False):
            for n in fc_alpaca[:6]:
                ts = (n.get("published") or "")[:10]
                st.markdown(f"**[{ts}]** {n.get('headline', '')}")
                if n.get("summary"):
                    st.caption(n["summary"][:160])
            for n in fc_eodhd[:4]:
                st.markdown(f"- {n.get('headline', '')}")
            for f in fc_edgar:
                st.markdown(f"- **{f.get('filed', '')}** {f.get('form_type', '')}: {f.get('match', '')}")


def page_picks():
    dates = D.list_scan_dates()
    date_choice = st.sidebar.selectbox(
        "Scan date",
        options=list(reversed(dates)) if dates else ["—"],
        index=0,
    )
    scan = _load_scan_cached(date_choice if date_choice != "—" else None)
    if not scan:
        st.error("No scan loaded.")
        return

    scan_date = scan.get("_scan_date_resolved") or scan.get("scan_date") or "?"
    from datetime import datetime
    try:
        nice = datetime.strptime(scan_date, "%Y-%m-%d").strftime("%A %d %B %Y")
    except Exception:
        nice = scan_date
    st.subheader(f"Picks for {nice}")
    st.caption(f"Same tickers as the email sent on {scan_date}. If your inbox has a newer date, click 🔄 Refresh from GitHub in the sidebar.")

    view_mode = st.radio(
        "View",
        ["🟢 TAKE only", "🟢🟡 TAKE + WATCH", "📋 Show all"],
        horizontal=True,
        index=0,
        help=(
            "TAKE = LLM confirmed BUY + Overall 65+ + bear cleared + not extended. "
            "WATCH = borderline edge or extended uptrend - wait for cleaner entry. "
            "Show all = every pick including SKIP / AVOID for full context."
        ),
    )

    picks = D.all_picks(scan, sort_by="overall")

    sort_choice = st.sidebar.radio("Sort by", ["overall", "tier", "stacked"], index=0)
    if sort_choice != "overall":
        picks = D.all_picks(scan, sort_by=sort_choice)

    tier_filter = st.sidebar.multiselect("Tier", ["A++", "A+", "A"], default=["A++", "A+", "A"])
    sectors = sorted({(p.get("sector") or "Other") for p in picks})
    sector_filter = st.sidebar.multiselect("Sector", sectors, default=sectors)
    min_score = st.sidebar.slider("Minimum overall score", 0, 100, 0, step=5)
    min_surv = st.sidebar.slider("Minimum survival score", 0, 100, 0, step=5)
    cat_text = st.sidebar.text_input("Catalyst contains", value="")

    try:
        from src.catalyst.catalyst_quality import is_speculative_only
        from src.catalyst.action_signal import compute_action
    except ImportError:
        def is_speculative_only(p):
            return False
        def compute_action(p, live_change_pct=None):
            return {"action": "WATCH", "badge": "—"}

    top_for_live = [p["ticker"] for p in picks[:25] if p.get("ticker")]
    live_quotes = _fetch_live_quotes_batch(tuple(top_for_live))
    for p in picks:
        q = live_quotes.get(p.get("ticker"))
        if q and q.get("mid"):
            try:
                scan_close = float(p.get("price") or 0)
                if scan_close > 0:
                    p["_live_mid"] = q["mid"]
                    p["_live_change_pct"] = (q["mid"] - scan_close) / scan_close * 100
            except (TypeError, ValueError):
                pass

    filtered = []
    speculative_dropped = 0
    for p in picks:
        if is_speculative_only(p):
            speculative_dropped += 1
            continue

        overall = (p.get("_overall_score") or {}) or {}
        score = overall.get("score", 0) or 0

        action = compute_action(p, live_change_pct=p.get("_live_change_pct"))
        action_label = action.get("action", "WATCH")
        p["_action_signal"] = action

        if view_mode == "🟢 TAKE only":
            if action_label != "TAKE":
                continue
        elif view_mode == "🟢🟡 TAKE + WATCH":
            if action_label not in ("TAKE", "WATCH"):
                continue

        if p.get("_aa_tier") not in tier_filter:
            continue
        if (p.get("sector") or "Other") not in sector_filter:
            continue
        if score < min_score:
            continue
        if (p.get("_survival_score") or {}).get("score", 0) < min_surv:
            continue
        if cat_text:
            cats = p.get("catalysts") or []
            if not any(cat_text.lower() in (c.get("key", "") if isinstance(c, dict) else "").lower() for c in cats):
                continue
        filtered.append(p)

    spec_note = f" · {speculative_dropped} speculative picks (FDA/clinical/M&A) removed" if speculative_dropped else ""
    if view_mode == "🟢 TAKE only" and not filtered:
        st.warning(
            f"No TAKE picks today. {len(picks)} candidates passed the Tier A bar but none cleared "
            f"the full action-signal test (LLM-confirmed BUY + Overall 65+ + bear NEUTRAL + not extended).{spec_note} "
            f"Switch to '🟢🟡 TAKE + WATCH' to see borderline names or '📋 Show all' for the full list."
        )
    else:
        st.caption(f"Showing {len(filtered)} of {len(picks)} picks (view: {view_mode}){spec_note}")

    try:
        from src.catalyst.action_signal import compute_action
    except ImportError:
        compute_action = None

    if compute_action:
        action_priority = {"TAKE": 0, "WATCH": 1, "SKIP": 2, "AVOID": 3}
        filtered.sort(key=lambda p: (
            action_priority.get((p.get("_action_signal") or compute_action(p)).get("action"), 9),
            -((p.get("_overall_score") or {}).get("score") or 0),
        ))

    rows = []
    for i, p in enumerate(filtered, 1):
        row = F.pick_summary_row(p)
        action = p.get("_action_signal") or (compute_action(p, live_change_pct=p.get("_live_change_pct")) if compute_action else {"badge": "—"})
        live_mid = p.get("_live_mid")
        live_pct = p.get("_live_change_pct")
        rows.append({
            "#": i,
            "Ticker": row["ticker"],
            "Action": action.get("badge", "—"),
            "Live $": round(live_mid, 2) if live_mid else None,
            "Live %": round(live_pct, 1) if live_pct is not None else None,
            "Overall": row["overall_score"],
            "Verdict": row["overall_verdict"],
            "PoP %": row["probability"],
            "Tier": row["tier"],
            "Survival": row["survival_score"],
            "LLM": row["llm_conf"],
            "Cats": row["cat_count"],
            "Price": row["price"],
            "Sector": row["sector"],
            "Name": row["name"],
        })

    if not rows:
        st.info("No picks match the filters.")
        return

    df = pd.DataFrame(rows)
    selection = st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        height=460,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Overall": st.column_config.ProgressColumn("Overall", min_value=0, max_value=100, format="%d"),
            "PoP %": st.column_config.NumberColumn("PoP %", format="%d%%"),
            "Price": st.column_config.NumberColumn("Close $", format="$%.2f", help="Yesterday's close (scan price)"),
            "Live $": st.column_config.NumberColumn("Live $", format="$%.2f", help="Latest Alpaca quote, refreshes every 60s"),
            "Live %": st.column_config.NumberColumn("Live %", format="%+.1f%%", help="% move from scan close to live"),
        },
    )

    selected_rows = (selection or {}).get("selection", {}).get("rows", []) if isinstance(selection, dict) else []
    if selected_rows:
        idx = selected_rows[0]
        if 0 <= idx < len(filtered):
            st.markdown("---")
            render_pick_detail(filtered[idx])
    else:
        st.info("Click a row above to load full detail.")


def page_positions():
    st.subheader("Open Positions")
    paper_open = D.open_positions()
    live_open = D.live_open_positions()
    all_open = paper_open + live_open
    if not all_open:
        st.info("No open positions.")
        return
    rows = []
    for p in all_open:
        r = F.position_summary_row(p)
        rows.append({
            "Ticker": r["ticker"],
            "Contract": r["contract"],
            "Size": r["size"],
            "Entry mid": r["entry_mid"],
            "Mid now": r["current_mid"],
            "Spot now": r["spot_now"],
            "P&L $": r["pnl_usd"],
            "P&L %": r["pnl_pct"],
            "Opened": r["opened_at"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("Recently Closed")
    closed = sorted(
        D.closed_positions() + D.live_closed_positions(),
        key=lambda c: c.get("closed_at") or "",
        reverse=True,
    )[:25]
    if closed:
        rows = []
        for p in closed:
            r = F.closed_position_row(p)
            rows.append({
                "Ticker": r["ticker"],
                "Contract": r["contract"],
                "Entry": r["entry_mid"],
                "Exit": r["exit_mid"],
                "P&L $": r["pnl_usd"],
                "P&L %": r["pnl_pct"],
                "Days": r["days_held"],
                "Reason": r["exit_reason"],
                "Closed": r["closed_at"],
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("Exit Alerts")
    alerts = D.exit_alerts_for_open()
    if alerts:
        st.dataframe(pd.DataFrame(alerts), hide_index=True, use_container_width=True)
    else:
        st.success("No exit alerts. All positions in normal bands.")


def page_macro():
    st.subheader("Macro Snapshot")
    scan = _load_scan_cached(None)
    if not scan:
        st.error("No scan loaded.")
        return
    macro = scan.get("macro") or {}
    if not macro:
        st.info("No macro data in scan.")
        return
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("VIX", macro.get("vix", "—"))
    with c2:
        kpi("Days to FOMC", macro.get("days_to_next_fomc", "—"))
    with c3:
        kpi("Days to CPI", macro.get("days_to_next_cpi", "—"))
    with c4:
        kpi("Days to NFP", macro.get("days_to_next_nfp", "—"))

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        kpi("Days to OPEX", macro.get("days_to_next_opex", "—"))
    with c6:
        kpi("VIX 5d %", macro.get("vix_5d_change_pct", "—"))
    with c7:
        kpi("10Y 5d bps", macro.get("yield_10y_5d_change_bps", "—"))
    with c8:
        kpi("DXY 5d %", macro.get("dxy_5d_change_pct", "—"))

    if macro.get("correlation_regime"):
        cr = macro["correlation_regime"]
        st.info(f"**Correlation regime: {cr.get('regime', '—')}** · avg corr {cr.get('avg_correlation', '—')}\n\n{cr.get('note', '')}")
    if macro.get("near_term_calendar_risks"):
        st.warning("Near-term calendar risks: " + ", ".join(macro["near_term_calendar_risks"]))
    if macro.get("dow_info"):
        di = macro["dow_info"]
        st.caption(f"{di.get('dow', '—')} · {di.get('note', '')}")


def page_stats():
    st.subheader("Trading Performance")
    window = st.sidebar.slider("Window (days)", 7, 365, 90)
    stats = D.aggregate_win_rate_stats(window_days=window)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Closed trades", stats["n"])
    with c2:
        kpi("Win rate", f"{stats['win_rate_pct']}%")
    with c3:
        cls = "win" if (stats.get("total_pnl_usd") or 0) > 0 else "lose" if (stats.get("total_pnl_usd") or 0) < 0 else ""
        kpi("Total P&L", F.fmt_money(stats["total_pnl_usd"]), cls)
    with c4:
        kpi("Avg trade %", F.fmt_pct(stats["avg_pnl_pct"]))

    st.markdown("---")
    st.subheader("Win rate by catalyst")
    by_cat = D.win_rate_by_catalyst(window_days=window)
    if by_cat:
        rows = []
        for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]["n"]):
            rows.append({
                "Catalyst": humanize_catalyst_key(k),
                "N trades": v["n"],
                "Wins": v["wins"],
                "Win rate %": v.get("win_rate_pct"),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("Not enough closed trades for catalyst breakdown.")


def page_history():
    st.subheader("Scan History")
    dates = D.list_scan_dates()
    if not dates:
        st.info("No scan history.")
        return
    rows = []
    for d in dates[-50:]:
        scan = _load_scan_cached(d)
        if not scan:
            continue
        aa = scan.get("aa_results") or {}
        rows.append({
            "Date": d,
            "A++": len(aa.get("A++", [])),
            "A+": len(aa.get("A+", [])),
            "A": len(aa.get("A", [])),
            "REJECT": len(aa.get("REJECT", [])),
            "Total": sum(len(aa.get(x, [])) for x in ("A++", "A+", "A", "REJECT")),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def page_ask():
    st.subheader("Ask Claude")
    st.caption("Free-text questions about the picks, positions, macro, and recent performance. Roughly 5-15¢ per question.")
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY not set. Without it, Ask mode is disabled. All other tabs work fine.")
        st.code("$env:ANTHROPIC_API_KEY = 'your-key-here'", language="powershell")
        return

    examples = [
        "Why did RDDT score 72?",
        "Show me only biotech picks with survival above 70",
        "Which catalysts have the best win rate in the last 90 days?",
        "Compare the bull and bear case for ALMS",
    ]
    st.write("Examples:")
    for e in examples:
        if st.button(e, key=f"ex_{e}"):
            st.session_state["ask_q"] = e

    q = st.text_area("Question", value=st.session_state.get("ask_q", ""), height=80)
    if st.button("Ask", type="primary"):
        if not q.strip():
            st.warning("Type a question first.")
        else:
            with st.spinner("Asking Claude..."):
                from src.terminal.ask import ask_claude
                answer = ask_claude(q)
                st.markdown("---")
                st.markdown(answer)


def _pull_latest_from_github():
    import subprocess
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase", "--autostash"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        )
        if result.returncode == 0:
            if "Already up to date" in result.stdout:
                return True, "Already on the latest scan"
            return True, f"Pulled new scan from GitHub"
        return False, f"git pull failed: {result.stderr[:120]}"
    except subprocess.TimeoutExpired:
        return False, "git pull timed out"
    except Exception as e:
        return False, f"git pull error: {e}"


def main():
    st.sidebar.title("Swing Trading")

    latest_date = D.latest_scan_date() or "(no scan)"
    st.sidebar.markdown(f"**Latest scan:** {latest_date}")

    if st.sidebar.button("🔄 Refresh from GitHub", use_container_width=True):
        with st.spinner("Pulling latest scan from GitHub..."):
            ok, msg = _pull_latest_from_github()
        if ok:
            st.cache_data.clear()
            st.sidebar.success(msg)
            st.rerun()
        else:
            st.sidebar.error(msg)

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Section", ["Picks", "Positions", "Macro", "Stats", "History", "Ask"], index=0)
    if page == "Picks":
        page_picks()
    elif page == "Positions":
        page_positions()
    elif page == "Macro":
        page_macro()
    elif page == "Stats":
        page_stats()
    elif page == "History":
        page_history()
    elif page == "Ask":
        page_ask()


main()

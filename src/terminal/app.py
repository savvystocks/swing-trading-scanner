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

    cls = _verdict_class(overall.get("verdict", "WATCH"))
    st.markdown(
        f'<div class="{cls}"><span style="font-size:28px">{overall.get("score", "—")}</span> &nbsp; '
        f'{overall.get("verdict", "—")} &nbsp;·&nbsp; '
        f'<span style="font-weight:500">{overall.get("plain_english", "")}</span></div>',
        unsafe_allow_html=True,
    )

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

    st.markdown("---")
    info1, info2 = st.columns([3, 2])
    with info1:
        st.markdown(f"**{d['ticker']}** · {d.get('name','—')} · {d.get('sector','—')} · {d.get('bracket','—')}")
        price = d.get("price")
        st.markdown(
            f"Price **${price}** &nbsp;·&nbsp; "
            f"5d {F.fmt_pct(d.get('ret_5d'))} &nbsp;·&nbsp; "
            f"30d {F.fmt_pct(d.get('ret_30d'))} &nbsp;·&nbsp; "
            f"90d {F.fmt_pct(d.get('ret_90d'))}"
        )
        st.markdown(
            f"Stacked score **{d.get('stacked_score','—')}** · "
            f"LLM verdict **{forensic.get('verdict','—')}** ({forensic.get('confidence','—')}% conf) · "
            f"IV pctile **{d.get('iv_percentile','—')}**"
        )
    with info2:
        components = overall.get("components") or {}
        if components:
            comp_df = pd.DataFrame([
                {"Component": k.replace("_", " ").title(), "Score": v}
                for k, v in components.items()
            ])
            st.dataframe(comp_df, hide_index=True, use_container_width=True, height=240)

    if d.get("catalysts_human"):
        st.markdown('<div class="catalyst-box"><strong>What\'s driving the move:</strong><br>' +
                    "<br>".join(f"· {c}" for c in d["catalysts_human"]) + "</div>", unsafe_allow_html=True)

    if forensic.get("bull"):
        st.markdown(f'<div class="bull-box"><strong>Bull case:</strong><br>{forensic["bull"]}</div>',
                    unsafe_allow_html=True)
    if bear.get("killer"):
        trap_note = " — TRAP FLAGGED" if bear.get("is_trap") else ""
        st.markdown(
            f'<div class="bear-box"><strong>Bear case ({bear.get("conviction", "—")}% conviction){trap_note}:</strong>'
            f'<br>{bear["killer"]}</div>',
            unsafe_allow_html=True,
        )

    if surv.get("kill_risks"):
        st.markdown("**Top survival risks**")
        for kr in surv["kill_risks"]:
            st.markdown(f"- {kr}")

    if riv.get("note") or sk.get("bias_note"):
        st.markdown("**Vol / Skew**")
        if riv.get("note"):
            st.write(f"Vol: {riv['note']}")
        if sk.get("bias_note"):
            st.write(f"Skew: {sk['bias_note']}")

    if multi:
        st.markdown("**Structure suggestions**")
        for s in multi:
            st.write(f"- **{s.get('structure', '—')}** — {s.get('rationale', '—')}")


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
        ["🎯 Tradeable only", "👀 Watch + Tradeable", "📋 Show all"],
        horizontal=True,
        index=0,
        help=(
            "Tradeable = Overall ≥ 65 AND Chance of profit ≥ 65% AND not trap-flagged. "
            "Watch = Overall ≥ 55. Show all = every Tier A pick regardless of LLM verdict."
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
    except ImportError:
        def is_speculative_only(p):
            return False

    filtered = []
    speculative_dropped = 0
    for p in picks:
        if is_speculative_only(p):
            speculative_dropped += 1
            continue

        overall = (p.get("_overall_score") or {}) or {}
        score = overall.get("score", 0) or 0
        pop = overall.get("probability_of_profit_pct", 0) or 0
        bear = p.get("bear_verification") or {}
        is_trap = bool(bear.get("is_this_trade_a_trap"))

        stage2 = p.get("_stage2_zone") or {}
        stage2_tradeable = stage2.get("tradeable", True) if stage2 else True

        if view_mode == "🎯 Tradeable only":
            if score < 65 or pop < 65 or is_trap:
                continue
            if not stage2_tradeable:
                continue
        elif view_mode == "👀 Watch + Tradeable":
            if score < 55 or is_trap:
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
    if view_mode == "🎯 Tradeable only" and not filtered:
        st.warning(
            f"No tradeable picks today. {len(picks)} candidates met the Tier A bar but none cleared "
            f"Overall ≥ 65 + PoP ≥ 65% + bear-test.{spec_note} "
            f"Switch to '👀 Watch + Tradeable' to see borderline ones, or '📋 Show all' to see the full evidence-based list."
        )
    else:
        st.caption(f"Showing {len(filtered)} of {len(picks)} picks (view: {view_mode}){spec_note}")

    rows = []
    for i, p in enumerate(filtered, 1):
        row = F.pick_summary_row(p)
        rows.append({
            "#": i,
            "Ticker": row["ticker"],
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
            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
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

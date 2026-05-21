from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, DataTable, Static, TabbedContent, TabPane, Input
from textual.reactive import reactive
from textual.binding import Binding

from src.terminal import data as D
from src.terminal import formatters as F


def _score_style(score):
    if score is None:
        return ""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return ""
    if s >= 80:
        return "bold #00ff66"
    if s >= 67:
        return "bold #44dd44"
    if s >= 52:
        return "bold #e8c44a"
    if s >= 38:
        return "#bbbbbb"
    return "bold #ff5566"


def _pnl_style(v):
    if v is None:
        return ""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return "bold #44dd44"
    if v < 0:
        return "bold #ff5566"
    return ""


class DetailPane(Static):
    def update_pick(self, p):
        if not p:
            self.update("[dim]Select a pick to see detail.[/dim]")
            return
        d = F.pick_full_detail(p)
        overall = d.get("overall") or {}
        surv = d.get("survival") or {}
        eq = d.get("earnings_quality") or {}
        forensic = d.get("llm_forensic") or {}
        bear = d.get("bear") or {}
        vol = d.get("vol_micro") or {}
        riv = (vol.get("realized_vs_implied") or {})
        sk = (vol.get("skew") or {})

        score_st = _score_style(overall.get("score"))
        lines = []
        lines.append(f"[bold]{d['ticker']}[/bold]  [dim]({d.get('name', '')})[/dim]")
        lines.append(f"[dim]{d.get('sector', '')} · {d.get('bracket', '')} · Tier {d.get('tier', '')}[/dim]")
        lines.append("")
        lines.append(f"Price [bold]${d.get('price')}[/bold]  5d {F.fmt_pct(d.get('ret_5d'))}  30d {F.fmt_pct(d.get('ret_30d'))}  90d {F.fmt_pct(d.get('ret_90d'))}")
        lines.append("")
        lines.append(f"[bold]Overall: [{score_st}]{overall.get('score', '?')}/100  {overall.get('verdict', '?')}[/{score_st}][/bold]")
        if overall.get("plain_english"):
            lines.append(f"[italic]{overall['plain_english']}[/italic]")
        lines.append("")
        lines.append(f"Chance of profit: [cyan]{overall.get('probability_of_profit_pct', '?')}%[/cyan]")
        lines.append(f"Survival: {surv.get('score', '?')}/100 ({surv.get('verdict', '?')})")
        lines.append(f"Quality: {eq.get('rating', '?')}   IV pctile: {d.get('iv_percentile', '?')}")
        lines.append(f"Stack: {d.get('stacked_score', '?')} ({d.get('cat_count', '?')} catalysts)")
        lines.append(f"LLM: {forensic.get('verdict', '?')} {forensic.get('confidence', '?')}%")
        if bear.get("is_trap"):
            lines.append(f"[bold red]BEAR: TRAP FLAGGED ({bear.get('conviction', '?')}%)[/bold red]")
        elif bear.get("verdict"):
            lines.append(f"BEAR: {bear.get('verdict')} ({bear.get('conviction', '?')}%)")

        if d.get("catalysts_human"):
            lines.append("")
            lines.append("[bold]What's driving the move:[/bold]")
            for c in d["catalysts_human"]:
                lines.append(f"  · {c}")

        if forensic.get("bull"):
            lines.append("")
            lines.append("[bold green]Bull case:[/bold green]")
            lines.append(forensic["bull"])

        if bear.get("killer"):
            lines.append("")
            kc = "red" if bear.get("is_trap") else "yellow"
            lines.append(f"[bold {kc}]Bear case ({bear.get('conviction', '?')}% conviction):[/bold {kc}]")
            lines.append(bear["killer"])

        if surv.get("kill_risks"):
            lines.append("")
            lines.append("[bold yellow]Top survival risks:[/bold yellow]")
            for kr in surv["kill_risks"]:
                lines.append(f"  · {kr}")

        if riv.get("note") or sk.get("bias_note"):
            lines.append("")
            if riv.get("note"):
                lines.append(f"[cyan]Vol:[/cyan] {riv['note']}")
            if sk.get("bias_note"):
                lines.append(f"[cyan]Skew:[/cyan] {sk['bias_note']}")

        components = overall.get("components") or {}
        if components:
            lines.append("")
            lines.append("[bold]Overall Score breakdown:[/bold]")
            for k, v in components.items():
                st = _score_style(v)
                lines.append(f"  {k.replace('_', ' ').title():22s} [{st}]{v:3d}[/{st}]")

        self.update("\n".join(lines))


class PositionDetail(Static):
    def update_position(self, p):
        if not p:
            self.update("[dim]Select a position to see detail.[/dim]")
            return
        contract = F._contract_str(p.get("contract"))
        pnl_st = _pnl_style(p.get("current_pnl_pct"))
        lines = []
        lines.append(f"[bold]{p.get('ticker', '?')}[/bold]   {contract}")
        lines.append(f"[dim]{p.get('name', '')} · {p.get('sector', '')}[/dim]")
        lines.append("")
        lines.append(f"Size: {p.get('size_contracts')} contract(s)")
        lines.append(f"Entry mid: ${p.get('entry_mid', '?')} → Now: ${p.get('current_mid', '?')}")
        lines.append(f"Entry spot: ${p.get('opened_at_spot', '?')} → Now: ${p.get('current_spot', '?')}")
        lines.append("")
        lines.append(f"P&L: [{pnl_st}]{F.fmt_pct(p.get('current_pnl_pct'))} = {F.fmt_money(p.get('current_pnl_usd'))}[/{pnl_st}]")
        lines.append(f"Opened: {(p.get('opened_at') or '')[:10]}")
        lines.append(f"Status: {p.get('status', '?')}")
        if p.get("market_regime_at_open"):
            lines.append(f"Market regime at open: {p['market_regime_at_open']}")
        if p.get("trim_levels_hit"):
            lines.append(f"Trim levels hit: {p['trim_levels_hit']}")
        self.update("\n".join(lines))


class SwingTerminal(App):
    CSS = """
    Screen { background: #0a0a0a; }
    Header { background: #1d2025; color: #ffffff; }
    Footer { background: #1d2025; color: #ffffff; }
    DataTable { background: #0f1419; }
    DataTable > .datatable--header { background: #1d2025; color: #88ccff; }
    DataTable > .datatable--cursor { background: #2a3f5f; }
    DataTable > .datatable--hover { background: #1a2530; }
    .pane-label { color: #88ccff; padding: 0 1; height: 1; }
    .detail-pane { background: #0a0e14; padding: 1 2; border: heavy #1d2025; }
    .status-bar { background: #1d2025; color: #88ccff; padding: 0 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("p", "show_tab('picks')", "Picks"),
        Binding("o", "show_tab('positions')", "Open"),
        Binding("c", "show_tab('closed')", "Closed"),
        Binding("e", "show_tab('exits')", "Exits"),
        Binding("h", "show_tab('history')", "History"),
        Binding("m", "show_tab('macro')", "Macro"),
        Binding("s", "show_tab('stats')", "Stats"),
    ]

    current_scan_date = reactive("")
    current_picks = reactive([])

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="picks", id="main_tabs"):
            with TabPane("Picks", id="picks"):
                with Horizontal():
                    with VerticalScroll():
                        yield DataTable(id="picks_table", cursor_type="row", zebra_stripes=True)
                    with VerticalScroll(classes="detail-pane"):
                        yield DetailPane("[dim]Select a pick.[/dim]", id="picks_detail")
            with TabPane("Open Positions", id="positions"):
                with Horizontal():
                    with VerticalScroll():
                        yield DataTable(id="positions_table", cursor_type="row", zebra_stripes=True)
                    with VerticalScroll(classes="detail-pane"):
                        yield PositionDetail("[dim]Select a position.[/dim]", id="positions_detail")
            with TabPane("Closed", id="closed"):
                yield DataTable(id="closed_table", cursor_type="row", zebra_stripes=True)
            with TabPane("Exit Alerts", id="exits"):
                yield DataTable(id="exits_table", cursor_type="row", zebra_stripes=True)
            with TabPane("History", id="history"):
                yield DataTable(id="history_table", cursor_type="row", zebra_stripes=True)
            with TabPane("Macro", id="macro"):
                yield Static("", id="macro_static", classes="detail-pane")
            with TabPane("Stats", id="stats"):
                yield Static("", id="stats_static", classes="detail-pane")
        yield Footer()

    def on_mount(self):
        self.title = "Swing Trading Terminal"
        self.refresh_all()

    def action_refresh(self):
        self.refresh_all()

    def action_show_tab(self, tab_id):
        try:
            tabs = self.query_one("#main_tabs", TabbedContent)
            tabs.active = tab_id
        except Exception:
            pass

    def refresh_all(self):
        scan = D.load_scan()
        if scan:
            self.current_scan_date = scan.get("_scan_date_resolved") or "?"
            picks = D.all_picks(scan, sort_by="overall")
            self.current_picks = picks
            self.populate_picks_table(picks)
            macro = scan.get("macro") or {}
            self.populate_macro(macro, self.current_scan_date)
        else:
            self.current_scan_date = "no scan loaded"
        self.populate_positions_table()
        self.populate_closed_table()
        self.populate_exits_table()
        self.populate_history_table()
        self.populate_stats()
        self.sub_title = f"Scan {self.current_scan_date}"

    def populate_picks_table(self, picks):
        t = self.query_one("#picks_table", DataTable)
        t.clear(columns=True)
        t.add_columns("#", "Ticker", "Overall", "Verdict", "PoP", "Tier", "Surv", "LLM", "Cats", "Price", "Sector", "Name")
        for i, p in enumerate(picks, 1):
            row = F.pick_summary_row(p)
            t.add_row(
                str(i),
                row["ticker"],
                F.fmt_score_or_dash(row["overall_score"]),
                (row["overall_verdict"] or "—")[:12],
                f"{F.fmt_score_or_dash(row['probability'])}%" if row["probability"] is not None else "—",
                row["tier"] or "—",
                F.fmt_score_or_dash(row["survival_score"]),
                F.fmt_score_or_dash(row["llm_conf"]),
                F.fmt_score_or_dash(row["cat_count"]),
                F.fmt_money(row["price"]),
                row["sector"][:16],
                row["name"][:24],
                key=str(i),
            )

    def populate_positions_table(self):
        t = self.query_one("#positions_table", DataTable)
        t.clear(columns=True)
        t.add_columns("Ticker", "Contract", "Size", "Entry", "Mid", "Spot", "P&L %", "P&L $", "Opened")
        positions = D.open_positions() + D.live_open_positions()
        for i, p in enumerate(positions, 1):
            row = F.position_summary_row(p)
            t.add_row(
                row["ticker"],
                row["contract"][:20],
                F.fmt_int_or_dash(row["size"]),
                F.fmt_money(row["entry_mid"]),
                F.fmt_money(row["current_mid"]),
                F.fmt_money(row["spot_now"]),
                F.fmt_pct(row["pnl_pct"]),
                F.fmt_money(row["pnl_usd"]),
                row["opened_at"],
                key=str(i),
            )

    def populate_closed_table(self):
        t = self.query_one("#closed_table", DataTable)
        t.clear(columns=True)
        t.add_columns("Ticker", "Contract", "Entry", "Exit", "P&L %", "P&L $", "Days", "Reason", "Closed")
        closed = D.closed_positions() + D.live_closed_positions()
        closed = sorted(closed, key=lambda c: c.get("closed_at") or "", reverse=True)[:30]
        for i, p in enumerate(closed, 1):
            row = F.closed_position_row(p)
            t.add_row(
                row["ticker"],
                row["contract"][:20],
                F.fmt_money(row["entry_mid"]),
                F.fmt_money(row["exit_mid"]),
                F.fmt_pct(row["pnl_pct"]),
                F.fmt_money(row["pnl_usd"]),
                F.fmt_int_or_dash(row["days_held"]),
                (row["exit_reason"] or "")[:20],
                row["closed_at"],
                key=str(i),
            )

    def populate_exits_table(self):
        t = self.query_one("#exits_table", DataTable)
        t.clear(columns=True)
        t.add_columns("Ticker", "Signal", "P&L %", "P&L $", "Days", "Contract")
        alerts = D.exit_alerts_for_open()
        for i, a in enumerate(alerts, 1):
            t.add_row(
                a["ticker"],
                a["signal"],
                F.fmt_pct(a["pnl_pct"]),
                F.fmt_money(a["pnl_usd"]),
                F.fmt_int_or_dash(a["days_held"]),
                (a["contract"] or "")[:24],
                key=str(i),
            )

    def populate_history_table(self):
        t = self.query_one("#history_table", DataTable)
        t.clear(columns=True)
        t.add_columns("Date", "A++", "A+", "A", "REJECT", "Total")
        for d in D.list_scan_dates()[-25:]:
            scan = D.load_scan(d)
            if not scan:
                continue
            aa = scan.get("aa_results") or {}
            t.add_row(
                d,
                str(len(aa.get("A++", []))),
                str(len(aa.get("A+", []))),
                str(len(aa.get("A", []))),
                str(len(aa.get("REJECT", []))),
                str(sum(len(aa.get(x, [])) for x in ("A++", "A+", "A", "REJECT"))),
                key=d,
            )

    def populate_macro(self, macro, scan_date):
        lines = [f"[bold]Macro Snapshot · {scan_date}[/bold]\n"]
        keys_order = [
            ("VIX", "vix"),
            ("VIX 5d change %", "vix_5d_change_pct"),
            ("10Y yield 5d Δ bps", "yield_10y_5d_change_bps"),
            ("DXY 5d change %", "dxy_5d_change_pct"),
            ("Days to FOMC", "days_to_next_fomc"),
            ("Days to CPI", "days_to_next_cpi"),
            ("Days to NFP", "days_to_next_nfp"),
            ("Days to OPEX", "days_to_next_opex"),
            ("Regime", "regime"),
        ]
        for label, k in keys_order:
            v = macro.get(k)
            if v is not None and v != []:
                lines.append(f"  {label:24s}  [cyan]{v}[/cyan]")
        if macro.get("near_term_calendar_risks"):
            lines.append("\n[yellow]Near-term calendar risks:[/yellow]")
            for r in macro["near_term_calendar_risks"]:
                lines.append(f"  · {r}")
        if macro.get("correlation_regime"):
            cr = macro["correlation_regime"]
            lines.append(f"\n[bold]Correlation regime:[/bold]")
            lines.append(f"  Avg corr: {cr.get('avg_correlation')}  Regime: {cr.get('regime')}")
            if cr.get("note"):
                lines.append(f"  [dim]{cr.get('note')}[/dim]")
        if macro.get("dow_info"):
            di = macro["dow_info"]
            lines.append(f"\nDay of week: [cyan]{di.get('dow')}[/cyan] - {di.get('note')}")
        self.query_one("#macro_static", Static).update("\n".join(lines))

    def populate_stats(self):
        stats = D.aggregate_win_rate_stats(window_days=90)
        by_cat = D.win_rate_by_catalyst(window_days=90)
        try:
            from src.catalyst.humanize import humanize_catalyst_key
        except ImportError:
            humanize_catalyst_key = lambda k: k
        pnl_st = _pnl_style(stats.get("total_pnl_usd"))
        lines = [
            f"[bold]Trading Performance (last 90d)[/bold]\n",
            f"  Closed trades:   {stats['n']}",
            f"  Win rate:        [bold]{stats['win_rate_pct']}%[/bold]",
            f"  Total P&L:       [{pnl_st}]{F.fmt_money(stats['total_pnl_usd'])}[/{pnl_st}]",
            f"  Avg trade P&L %: {F.fmt_pct(stats['avg_pnl_pct'])}",
        ]
        if by_cat:
            lines.append("\n[bold]Win rate by catalyst (last 90d):[/bold]")
            rows = sorted(by_cat.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:15]
            for cat, d in rows:
                color = "#44dd44" if (d.get("win_rate_pct") or 0) >= 50 else "#ff5566"
                lines.append(f"  {humanize_catalyst_key(cat)[:42]:42s}  n={d['n']:2d}  [{color}]{d['win_rate_pct']}%[/{color}]" if d.get("win_rate_pct") is not None else f"  {humanize_catalyst_key(cat):42s}  n={d['n']}  —")
        self.query_one("#stats_static", Static).update("\n".join(lines))

    def _load_detail_for_row(self, table_id, row_key):
        if row_key is None:
            return
        try:
            idx = int(row_key) - 1
        except (ValueError, TypeError):
            return
        if table_id == "picks_table":
            if 0 <= idx < len(self.current_picks):
                self.query_one("#picks_detail", DetailPane).update_pick(self.current_picks[idx])
        elif table_id == "positions_table":
            positions = D.open_positions() + D.live_open_positions()
            if 0 <= idx < len(positions):
                self.query_one("#positions_detail", PositionDetail).update_position(positions[idx])

    def on_data_table_row_selected(self, event):
        try:
            table_id = event.data_table.id
        except Exception:
            return
        key = event.row_key.value if event.row_key else None
        self._load_detail_for_row(table_id, key)

    def on_data_table_row_highlighted(self, event):
        try:
            table_id = event.data_table.id
        except Exception:
            return
        key = event.row_key.value if event.row_key else None
        self._load_detail_for_row(table_id, key)


def main():
    app = SwingTerminal()
    app.run()


if __name__ == "__main__":
    main()

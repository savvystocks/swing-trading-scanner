import argparse
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from src.terminal import data as D
from src.terminal import formatters as F


console = Console()


def _color_for_score(s):
    if s is None:
        return "white"
    try:
        s = float(s)
    except (TypeError, ValueError):
        return "white"
    if s >= 80:
        return "bright_green"
    if s >= 67:
        return "green"
    if s >= 52:
        return "yellow"
    if s >= 38:
        return "white"
    return "red"


def _color_for_pnl(v):
    if v is None:
        return "white"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "white"
    if v > 0:
        return "green"
    if v < 0:
        return "red"
    return "white"


def cmd_picks(args):
    scan = D.load_scan(args.date)
    if not scan:
        console.print(f"[red]No scan found for date={args.date or 'latest'}[/red]")
        return 1
    date = scan.get("_scan_date_resolved") or scan.get("scan_date") or "?"
    picks = D.all_picks(scan, sort_by=args.sort)
    if args.tier:
        picks = [p for p in picks if p.get("_aa_tier") == args.tier]
    if args.sector:
        picks = [p for p in picks if (p.get("sector") or "").lower().find(args.sector.lower()) >= 0]
    if args.catalyst:
        picks = [
            p for p in picks
            if any(
                (c.get("key", "") if isinstance(c, dict) else "").find(args.catalyst.lower()) >= 0
                for c in (p.get("catalysts") or [])
            )
        ]
    if args.min_score is not None:
        picks = [p for p in picks if (p.get("_overall_score") or {}).get("score", 0) >= args.min_score]
    if args.min_survival is not None:
        picks = [p for p in picks if (p.get("_survival_score") or {}).get("score", 0) >= args.min_survival]
    if args.limit:
        picks = picks[:args.limit]

    if not picks:
        console.print(f"[yellow]No picks match filters (scan {date}).[/yellow]")
        return 0

    table = Table(title=f"Swing Trading Picks · {date}  ({len(picks)} matches)", box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Ticker", style="bold")
    table.add_column("Overall", justify="center")
    table.add_column("Verdict", style="bold")
    table.add_column("PoP", justify="right")
    table.add_column("Tier", justify="center")
    table.add_column("Surv", justify="right")
    table.add_column("LLM", justify="right")
    table.add_column("Cats", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Sector", style="dim")
    table.add_column("Name", style="dim")

    for i, p in enumerate(picks, 1):
        row = F.pick_summary_row(p)
        score_color = _color_for_score(row["overall_score"])
        table.add_row(
            str(i),
            row["ticker"],
            f"[{score_color}]{F.fmt_score_or_dash(row['overall_score'])}[/{score_color}]",
            f"[{score_color}]{row['overall_verdict'] or '—'}[/{score_color}]",
            f"{F.fmt_score_or_dash(row['probability'])}%" if row["probability"] is not None else "—",
            row["tier"],
            F.fmt_score_or_dash(row["survival_score"]),
            f"{F.fmt_score_or_dash(row['llm_conf'])}",
            F.fmt_score_or_dash(row["cat_count"]),
            F.fmt_money(row["price"]),
            row["sector"],
            row["name"],
        )
    console.print(table)
    return 0


def cmd_ticker(args):
    scan = D.load_scan(args.date)
    if not scan:
        console.print(f"[red]No scan found for date={args.date or 'latest'}[/red]")
        return 1
    p = D.find_pick(scan, args.ticker)
    if not p:
        console.print(f"[yellow]{args.ticker.upper()} not in scan for {scan.get('_scan_date_resolved')}[/yellow]")
        return 1
    d = F.pick_full_detail(p)
    overall = d.get("overall") or {}
    surv = d.get("survival") or {}
    eq = d.get("earnings_quality") or {}
    forensic = d.get("llm_forensic") or {}
    bear = d.get("bear") or {}
    vol = d.get("vol_micro") or {}
    score_color = _color_for_score(overall.get("score"))

    head = Text()
    head.append(f"{d['ticker']}  ", style="bold white")
    head.append(f"({d.get('name') or '—'})", style="dim")
    head.append(f"\n{d.get('sector') or '—'} · {d.get('bracket') or '—'} · Tier {d.get('tier') or '—'}\n", style="dim")
    head.append(f"Price ${d.get('price')}  ", style="bold")
    head.append(f"5d {F.fmt_pct(d.get('ret_5d'))}  30d {F.fmt_pct(d.get('ret_30d'))}  90d {F.fmt_pct(d.get('ret_90d'))}\n", style="white")
    head.append(f"\nOverall: ", style="dim")
    head.append(f"{overall.get('score', '?')}/100  ", style=f"bold {score_color}")
    head.append(f"{overall.get('verdict', '?')}\n", style=f"bold {score_color}")
    head.append(f"PoP: {overall.get('probability_of_profit_pct', '?')}%  ", style="cyan")
    head.append(f"Survival: {surv.get('score', '?')}/100 ({surv.get('verdict', '?')})\n", style="white")
    head.append(f"Quality: {eq.get('rating', '?')}  ", style="white")
    head.append(f"IV pctile: {d.get('iv_percentile', '?')}  ", style="white")
    head.append(f"Stack: {d.get('stacked_score', '?')} ({d.get('cat_count', '?')} cats)\n", style="white")
    head.append(f"LLM: {forensic.get('verdict', '?')} {forensic.get('confidence', '?')}%  ", style="white")
    if bear.get("is_trap"):
        head.append(f"BEAR: TRAP FLAGGED\n", style="bold red")
    else:
        head.append(f"BEAR: {bear.get('verdict', 'NOT_TESTED')} {bear.get('conviction', '?')}%\n", style="white")
    console.print(Panel(head, title="Pick Detail", border_style=score_color))

    if overall.get("plain_english"):
        console.print(f"  [italic]{overall['plain_english']}[/italic]\n")

    if d.get("catalysts_human"):
        t = Table(title="Catalysts driving the trade", box=box.SIMPLE, show_header=False)
        t.add_column("Catalyst")
        for cat in d["catalysts_human"]:
            t.add_row(f"· {cat}")
        console.print(t)

    if forensic.get("bull"):
        console.print(Panel(Text(forensic["bull"], style="green"), title="Bull case", border_style="green"))
    if forensic.get("kills"):
        console.print(Panel(Text(forensic["kills"], style="yellow"), title="What kills this trade", border_style="yellow"))
    if bear.get("killer"):
        kc = "red" if bear.get("is_trap") else "yellow"
        console.print(Panel(Text(bear["killer"], style=kc), title=f"Bear case ({bear.get('conviction', '?')}% conviction)", border_style=kc))

    components = overall.get("components") or {}
    if components:
        t = Table(title="Overall Score breakdown", box=box.SIMPLE)
        t.add_column("Component")
        t.add_column("Score", justify="right")
        t.add_column("Weight", justify="right")
        weights = overall.get("weights") or {}
        for k, v in components.items():
            w = weights.get(k, 0)
            color = _color_for_score(v)
            t.add_row(k.replace("_", " ").title(), f"[{color}]{v}[/{color}]", f"{int(w*100)}%")
        console.print(t)

    if surv.get("kill_risks"):
        t = Table(title="Top survival risks", box=box.SIMPLE, show_header=False)
        for kr in surv["kill_risks"]:
            t.add_row(f"[red]· {kr}[/red]")
        console.print(t)

    if vol.get("realized_vs_implied") or vol.get("skew"):
        riv = (vol.get("realized_vs_implied") or {})
        sk = (vol.get("skew") or {})
        if riv.get("note"):
            console.print(f"[cyan]Vol:[/cyan] {riv.get('note')}")
        if sk.get("bias_note"):
            console.print(f"[cyan]Skew:[/cyan] {sk.get('bias_note')}")

    multi = d.get("multi_leg") or []
    if multi:
        t = Table(title="Structure suggestions", box=box.SIMPLE)
        t.add_column("Structure")
        t.add_column("Rationale", style="dim")
        for s in multi:
            t.add_row(s.get("structure", "—"), s.get("rationale", "—"))
        console.print(t)

    return 0


def cmd_positions(args):
    open_pos = D.open_positions() if not args.live else D.live_open_positions()
    label = "Live" if args.live else "Paper"
    if not open_pos:
        console.print(f"[yellow]No open {label.lower()} positions.[/yellow]")
        return 0
    table = Table(title=f"{label} Open Positions ({len(open_pos)})", box=box.SIMPLE_HEAD)
    table.add_column("Ticker", style="bold")
    table.add_column("Contract", style="dim")
    table.add_column("Size", justify="right")
    table.add_column("Entry", justify="right")
    table.add_column("Mid now", justify="right")
    table.add_column("Spot now", justify="right")
    table.add_column("P&L $", justify="right")
    table.add_column("P&L %", justify="right")
    table.add_column("Opened", style="dim")

    for p in open_pos:
        r = F.position_summary_row(p, live=args.live)
        pnl_color = _color_for_pnl(r["pnl_pct"])
        table.add_row(
            r["ticker"],
            (r["contract"] or "")[:18],
            F.fmt_int_or_dash(r["size"]),
            F.fmt_money(r["entry_mid"]),
            F.fmt_money(r["current_mid"]),
            F.fmt_money(r["spot_now"]),
            f"[{pnl_color}]{F.fmt_money(r['pnl_usd'])}[/{pnl_color}]",
            f"[{pnl_color}]{F.fmt_pct(r['pnl_pct'])}[/{pnl_color}]",
            r["opened_at"],
        )
    console.print(table)
    return 0


def cmd_closed(args):
    closed = D.closed_positions() if not args.live else D.live_closed_positions()
    if not closed:
        console.print(f"[yellow]No closed positions.[/yellow]")
        return 0
    closed = sorted(closed, key=lambda c: c.get("closed_at") or "", reverse=True)[:args.limit]
    table = Table(title=f"{'Live' if args.live else 'Paper'} Closed Positions (last {len(closed)})", box=box.SIMPLE_HEAD)
    table.add_column("Ticker", style="bold")
    table.add_column("Contract", style="dim")
    table.add_column("Size", justify="right")
    table.add_column("Entry", justify="right")
    table.add_column("Exit", justify="right")
    table.add_column("P&L $", justify="right")
    table.add_column("P&L %", justify="right")
    table.add_column("Days", justify="right")
    table.add_column("Reason", style="dim")
    table.add_column("Closed", style="dim")

    for p in closed:
        r = F.closed_position_row(p, live=args.live)
        pnl_color = _color_for_pnl(r["pnl_pct"])
        table.add_row(
            r["ticker"],
            (r["contract"] or "")[:18],
            F.fmt_int_or_dash(r["size"]),
            F.fmt_money(r["entry_mid"]),
            F.fmt_money(r["exit_mid"]),
            f"[{pnl_color}]{F.fmt_money(r['pnl_usd'])}[/{pnl_color}]",
            f"[{pnl_color}]{F.fmt_pct(r['pnl_pct'])}[/{pnl_color}]",
            F.fmt_int_or_dash(r["days_held"]),
            (r["exit_reason"] or "")[:18],
            r["closed_at"],
        )
    console.print(table)
    return 0


def cmd_exits(args):
    alerts = D.exit_alerts_for_open()
    if not alerts:
        console.print("[green]No exit alerts. All open positions inside normal bands.[/green]")
        return 0
    table = Table(title=f"Exit Alerts ({len(alerts)})", box=box.SIMPLE_HEAD)
    table.add_column("Ticker", style="bold")
    table.add_column("Signal", style="bold")
    table.add_column("P&L %", justify="right")
    table.add_column("P&L $", justify="right")
    table.add_column("Days", justify="right")
    table.add_column("Contract", style="dim")
    for a in alerts:
        c = "red" if a["signal"].startswith("STOP") else "yellow"
        table.add_row(
            a["ticker"], f"[{c}]{a['signal']}[/{c}]",
            F.fmt_pct(a["pnl_pct"]),
            F.fmt_money(a["pnl_usd"]),
            F.fmt_int_or_dash(a["days_held"]),
            (a["contract"] or "")[:20],
        )
    console.print(table)
    return 0


def cmd_history(args):
    dates = D.list_scan_dates()
    if not dates:
        console.print("[yellow]No scan history found.[/yellow]")
        return 0
    dates = dates[-args.limit:] if args.limit else dates
    table = Table(title=f"Scan History ({len(dates)} dates)", box=box.SIMPLE_HEAD)
    table.add_column("Date")
    table.add_column("A++", justify="right")
    table.add_column("A+", justify="right")
    table.add_column("A", justify="right")
    table.add_column("REJECT", justify="right")
    table.add_column("Total", justify="right")
    for d in dates:
        scan = D.load_scan(d)
        if not scan:
            continue
        aa = scan.get("aa_results") or {}
        a_pp = len(aa.get("A++", []))
        a_p = len(aa.get("A+", []))
        a_ = len(aa.get("A", []))
        rej = len(aa.get("REJECT", []))
        total = a_pp + a_p + a_ + rej
        table.add_row(d, str(a_pp), str(a_p), str(a_), str(rej), str(total))
    console.print(table)
    return 0


def cmd_macro(args):
    scan = D.load_scan(args.date)
    if not scan:
        console.print("[red]No scan loaded.[/red]")
        return 1
    macro = scan.get("macro") or {}
    if not macro:
        console.print("[yellow]No macro data in scan.[/yellow]")
        return 0
    t = Table(title=f"Macro Snapshot · {scan.get('_scan_date_resolved')}", box=box.SIMPLE, show_header=False)
    t.add_column("Key", style="dim")
    t.add_column("Value", style="bold")
    important_keys = [
        "vix", "vix_5d_change_pct", "yield_10y_5d_change_bps", "dxy_5d_change_pct",
        "days_to_next_fomc", "days_to_next_cpi", "days_to_next_nfp", "days_to_next_opex",
        "near_term_calendar_risks", "regime",
    ]
    for k in important_keys:
        if k in macro:
            v = macro.get(k)
            if isinstance(v, (list, dict)):
                v = str(v)[:60]
            t.add_row(k.replace("_", " "), str(v))
    if macro.get("correlation_regime"):
        cr = macro["correlation_regime"]
        t.add_row("correlation regime", f"{cr.get('regime')} (avg {cr.get('avg_correlation')})")
        if cr.get("note"):
            t.add_row("correlation note", cr.get("note"))
    if macro.get("dow_info"):
        di = macro["dow_info"]
        t.add_row("day of week", f"{di.get('dow')} - {di.get('note')}")
    console.print(t)
    return 0


def cmd_stats(args):
    overall = D.aggregate_win_rate_stats(window_days=args.window)
    console.print(Panel(
        f"Closed trades in last {args.window}d: [bold]{overall['n']}[/bold]\n"
        f"Win rate: [bold]{overall['win_rate_pct']}%[/bold]\n"
        f"Total P&L: [bold]{F.fmt_money(overall['total_pnl_usd'])}[/bold]\n"
        f"Avg trade P&L %: [bold]{F.fmt_pct(overall['avg_pnl_pct'])}[/bold]",
        title="Trading Performance",
        border_style="cyan",
    ))

    by_cat = D.win_rate_by_catalyst(window_days=args.window)
    if by_cat:
        rows = sorted(by_cat.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:15]
        t = Table(title="Win rate by catalyst (top by sample size)", box=box.SIMPLE_HEAD)
        t.add_column("Catalyst", style="bold")
        t.add_column("N", justify="right")
        t.add_column("Wins", justify="right")
        t.add_column("Win %", justify="right")
        try:
            from src.catalyst.humanize import humanize_catalyst_key
        except ImportError:
            humanize_catalyst_key = lambda k: k
        for cat, d in rows:
            color = "green" if (d.get("win_rate_pct") or 0) >= 50 else "red"
            t.add_row(humanize_catalyst_key(cat), str(d["n"]), str(d["wins"]),
                      f"[{color}]{d['win_rate_pct']}%[/{color}]" if d.get("win_rate_pct") is not None else "—")
        console.print(t)
    return 0


def cmd_ask(args):
    from src.terminal.ask import ask_claude
    question = " ".join(args.question)
    if not question.strip():
        console.print("[red]No question provided.[/red]")
        return 1
    console.print(f"[dim]Asking Claude: {question}[/dim]")
    answer = ask_claude(question, scan_date=args.date)
    console.print(Panel(answer, title="Answer", border_style="cyan"))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="swing", description="Swing Trading Scanner Terminal")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("picks", help="Show ranked picks for a scan date")
    pp.add_argument("--date", help="Scan date YYYY-MM-DD (default: latest)")
    pp.add_argument("--tier", choices=["A++", "A+", "A"], help="Filter to single tier")
    pp.add_argument("--sector", help="Filter by sector substring")
    pp.add_argument("--catalyst", help="Filter by catalyst-key substring")
    pp.add_argument("--min-score", type=int, help="Minimum overall score")
    pp.add_argument("--min-survival", type=int, help="Minimum survival score")
    pp.add_argument("--limit", type=int, default=20, help="Max rows (default 20)")
    pp.add_argument("--sort", choices=["overall", "tier", "stacked"], default="overall",
                    help="Sort key: overall score (default), tier-then-overall, or raw stacked score")

    pt = sub.add_parser("ticker", help="Full detail on one ticker")
    pt.add_argument("ticker", help="Ticker symbol (e.g. MRVL)")
    pt.add_argument("--date", help="Scan date YYYY-MM-DD (default: latest)")

    pos = sub.add_parser("positions", help="Show open paper or live positions")
    pos.add_argument("--live", action="store_true", help="Show live trades instead of paper")

    cl = sub.add_parser("closed", help="Show recently closed positions")
    cl.add_argument("--live", action="store_true", help="Show live trades instead of paper")
    cl.add_argument("--limit", type=int, default=15)

    sub.add_parser("exits", help="Exit alerts on open positions")

    his = sub.add_parser("history", help="List historical scan dates with tier counts")
    his.add_argument("--limit", type=int, default=20)

    m = sub.add_parser("macro", help="Show macro snapshot for a scan date")
    m.add_argument("--date", help="Scan date YYYY-MM-DD (default: latest)")

    st = sub.add_parser("stats", help="Trading performance + win rate by catalyst")
    st.add_argument("--window", type=int, default=90, help="Window days (default 90)")

    ask = sub.add_parser("ask", help="Ask Claude a free-text question about the data")
    ask.add_argument("question", nargs="+", help="The question text")
    ask.add_argument("--date", help="Scan date to bind context to (default: latest)")

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "picks": cmd_picks,
        "ticker": cmd_ticker,
        "positions": cmd_positions,
        "closed": cmd_closed,
        "exits": cmd_exits,
        "history": cmd_history,
        "macro": cmd_macro,
        "stats": cmd_stats,
        "ask": cmd_ask,
    }
    fn = dispatch.get(args.cmd)
    if not fn:
        parser.print_help()
        return 2
    return fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())

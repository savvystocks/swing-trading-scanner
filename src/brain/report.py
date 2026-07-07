"""Stage 1 - the weekly edge report on the V10 rules engine (the harness's first customer).

Hard-coded sample-size minimums below which a verdict renders as UNDERPOWERED (n=X of Y needed). The
PBO/DSR sections render N/A until the CPCV minimums are met. Pure numpy/pandas. Imports no execution
module (ev/harness are sibling brain modules)."""
import numpy as np
import pandas as pd

from . import ev as EV
from . import harness as H

MIN_EXECUTED = 30          # below this the engine hit-rate verdict is UNDERPOWERED
MIN_ROWS_EV = 50           # below this the empirical EV thresholds are UNDERPOWERED
MIN_ROWS_CPCV = 1000       # below this PBO/DSR render N/A
MIN_BRAKE_DAYS = 5         # below this the brake-shadow measurement renders UNDERPOWERED

# SPRT parameters (predefined - mirrored into ROADMAP.md item 7 so they cannot be quietly changed):
SPRT_ALPHA, SPRT_BETA = 0.05, 0.20
SPRT_MARGIN = 0.02         # H0 = the empirical cost-inclusive breakeven + this stated margin m
SPRT_MIN_EDGE = 0.05       # H1 = H0 + 5 percentage points
# NOTE: the breakeven already nets cost - H0 adds margin m only (adding cost again would double-count).
# The SPRT clock starts when the week-one Tier B drop lands (owner-decisions integration).


def _fmt(x, nd=4):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}"


def weekly_edge_report(dataset_result, prev_rows=0, runtime_s=None):
    df = dataset_result["df"]
    card = dataset_result["card"]
    n = len(df)
    added = n - prev_rows
    lines = [f"# V12 weekly edge report - {dataset_result['dataset_version']}", ""]
    lines += [f"- snapshot: {card.get('snapshot_id')}  |  live snapshot rows: {card.get('snapshot_row_counts')}",
              f"- dataset rows: {n} (added {added:+d} vs last run)  |  date range: {card.get('date_range')}",
              f"- runtime: {_fmt(runtime_s, 1)}s  |  features: {card.get('n_features')}", ""]

    if card.get("warnings"):
        lines += ["## Data quality WARN", ""] + [f"- {w}" for w in card["warnings"]] + [""]

    lines += ["## Rows by tier / outcome / executed",
              f"- tier: {card.get('rows_by_tier')}",
              f"- outcome: {card.get('rows_by_outcome')}",
              f"- executed: {card.get('rows_by_executed')}", ""]

    summary = {"rows": n, "rows_added": added, "hit_rate": None, "sprt": "UNDERPOWERED", "underpowered": True}

    if n == 0:
        lines += ["## Verdict", "", "UNDERPOWERED - dataset is empty (no resolved, non-censored labels yet).",
                  "Everything below renders once the poller has labelled live sessions."]
        summary["verdict"] = "UNDERPOWERED (empty)"
        return {"markdown": "\n".join(lines), "summary": summary}

    # ---- empirical EV / thresholds (GATE 2) ----
    cost = EV.cost_model(df.get("half_spread", pd.Series(dtype=float)).to_numpy())
    thr = EV.solve_threshold(df["realized_return"].to_numpy(), cost=cost)
    cstats = EV.class_stats(df["realized_return"].to_numpy(), df["outcome"].to_numpy())
    es = EV.expected_shortfall(df["realized_return"].to_numpy())
    ev_underpowered = n < MIN_ROWS_EV
    lines += ["## Empirical EV thresholds (GATE 2)" + (" - UNDERPOWERED" if ev_underpowered else ""),
              f"- n={n} of {MIN_ROWS_EV} needed" if ev_underpowered else f"- n={n}",
              f"- empirical breakeven win-prob: {_fmt(thr['threshold'])}  CI{int(thr['ci_level']*100)}%: "
              f"[{_fmt(thr['ci'][0])}, {_fmt(thr['ci'][1])}]",
              f"- binary sanity floor (0.30/-0.50): {_fmt(thr['binary_floor'])}  "
              f"{'<-- RED FLAG: empirical below floor' if thr['below_floor_red_flag'] else 'ok'}",
              f"- empirical mu_win={_fmt(thr['mu_win'])} mu_loss={_fmt(thr['mu_loss'])} cost={_fmt(cost)}",
              f"- expected shortfall (5% loss tail): {_fmt(es)}",
              f"- gap-through: {cstats['gap_through']}", ""]

    # ---- engine hit rate vs the empirical hurdle (executed trades) ----
    ex = df[df["executed"] == 1]
    n_ex = len(ex)
    hurdle = thr["threshold"] if np.isfinite(thr["threshold"]) else thr["binary_floor"]
    hit_underpowered = n_ex < MIN_EXECUTED
    if n_ex > 0:
        wins = int((ex["label"] == 1).sum())
        hit = wins / n_ex
        lo, hi = EV.wilson_interval(wins, n_ex)
        summary["hit_rate"] = hit
        lines += ["## Engine edge - executed trades" + (" - UNDERPOWERED" if hit_underpowered else ""),
                  f"- n_executed={n_ex}" + (f" of {MIN_EXECUTED} needed" if hit_underpowered else ""),
                  f"- hit rate: {_fmt(hit,4)}  Wilson95: [{_fmt(lo)}, {_fmt(hi)}]",
                  f"- empirical hurdle: {_fmt(hurdle)}  -> {'ABOVE' if hit > hurdle else 'below'} hurdle"
                  + (" (UNDERPOWERED, not a verdict)" if hit_underpowered else ""),
                  f"- expectancy (mean realized_return, executed): {_fmt(float(ex['realized_return'].mean()))}", ""]

        # stratified by source premium (rule_score) - REPORTING ONLY; the SPRT object stays the pooled stream
        if "rule_score" in ex.columns:
            rs = ex["rule_score"]
            strata = [(">=50k", rs >= 50000), ("25-50k", (rs >= 25000) & (rs < 50000))]
            strat_lines = []
            for nm, mask in strata:
                sub = ex[mask.fillna(False)]
                ns = len(sub)
                if ns:
                    w = int((sub["label"] == 1).sum()); h = w / ns
                    slo, shi = EV.wilson_interval(w, ns)
                    strat_lines.append(f"- source premium {nm}: n={ns} hit={_fmt(h,4)} Wilson95=[{_fmt(slo)}, {_fmt(shi)}]")
            if strat_lines:
                lines += ["_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_"] + strat_lines + [""]

        # ---- daily-brake SHADOW measurement (reporting only) ----
        # f.brake_shadow tags each executed trade that fired AFTER the daily brake would have tripped
        # that session (shadow mode does NOT suppress entries). Comparing would-have-blocked vs allowed
        # answers "what did the brake save vs cost?" - our free measurement before it protects real money.
        bs_col = next((c for c in ex.columns if c.split(".")[-1] == "brake_shadow"), None)
        blocked = ex[ex[bs_col].fillna(False).astype(bool)] if bs_col is not None else ex.iloc[0:0]
        if len(blocked):
            allowed = ex[~ex.index.isin(blocked.index)]
            brake_days = int(pd.to_datetime(blocked["signal_ts"], unit="ms", utc=True).dt.date.nunique())
            def _brake_line(nm, sub):
                ns = len(sub)
                if not ns:
                    return f"- {nm}: n=0"
                w = int((sub["label"] == 1).sum()); h = w / ns
                blo, bhi = EV.wilson_interval(w, ns)
                return (f"- {nm}: n={ns} hit={_fmt(h,4)} Wilson95=[{_fmt(blo)}, {_fmt(bhi)}] "
                        f"mean_return={_fmt(float(sub['realized_return'].mean()))} "
                        f"total_return={_fmt(float(sub['realized_return'].sum()),2)}")
            up = brake_days < MIN_BRAKE_DAYS
            lines += ["## Daily brake - SHADOW measurement (reporting only; in shadow the brake does NOT suppress entries)"
                      + (" - UNDERPOWERED" if up else ""),
                      f"- would-have-tripped on {brake_days} day(s)" + (f" of {MIN_BRAKE_DAYS} needed" if up else "")
                      + f"; would-have-blocked {len(blocked)} executed entries",
                      _brake_line("would-have-blocked (brake ACTIVE would remove these)", blocked),
                      _brake_line("allowed (brake ACTIVE would keep these)", allowed),
                      "_blocked worse than allowed -> the brake helps; blocked better -> it costs edge._", ""]
        else:
            lines += ["## Daily brake - SHADOW measurement",
                      "- 0 brake-days recorded yet (UNDERPOWERED); populated once a shadow session hits the trigger.", ""]

        # ---- SPRT on executed trades ----
        p0 = min(max(hurdle + SPRT_MARGIN, 1e-3), 0.99)      # breakeven already nets cost; add margin m only
        p1 = min(p0 + SPRT_MIN_EDGE, 0.999)
        s = EV.sprt(wins, n_ex, p0, p1, SPRT_ALPHA, SPRT_BETA)
        summary["sprt"] = s["decision"]
        lines += ["## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]",
                  f"- H0 win-rate={_fmt(p0,3)} (breakeven+margin {SPRT_MARGIN})  H1={_fmt(p1,3)} (H0+{SPRT_MIN_EDGE})  "
                  f"alpha={SPRT_ALPHA} beta={SPRT_BETA}",
                  f"- wins {wins}/{n_ex}  LLR={_fmt(s['llr'],3)}  bounds[{_fmt(s['lower'],3)}, {_fmt(s['upper'],3)}]",
                  f"- decision: **{s['decision']}**", ""]
    else:
        lines += ["## Engine edge - executed trades - UNDERPOWERED",
                  f"- n_executed=0 of {MIN_EXECUTED} needed", ""]

    # ---- time-to-resolution + MFE/MAE ----
    ttr = df["time_to_resolution_min"].dropna()
    lines += ["## Time-to-resolution (minutes)",
              f"- median={_fmt(float(ttr.median()) if len(ttr) else None,1)} "
              f"p10={_fmt(float(ttr.quantile(.1)) if len(ttr) else None,1)} "
              f"p90={_fmt(float(ttr.quantile(.9)) if len(ttr) else None,1)}", "",
              "## MFE / MAE profile",
              f"- MFE mean={_fmt(float(df['mfe'].dropna().mean()) if df['mfe'].notna().any() else None)} "
              f"MAE mean={_fmt(float(df['mae'].dropna().mean()) if df['mae'].notna().any() else None)}", ""]

    # ---- PBO / DSR ----
    m = H.cpcv_math()
    if n < MIN_ROWS_CPCV:
        lines += ["## PBO / Deflated Sharpe (CPCV)",
                  f"- N/A - CPCV needs >= {MIN_ROWS_CPCV} rows (have {n}). "
                  f"CPCV config: N={m['n_groups']} k={m['k']} -> {m['n_splits']} splits, {m['n_paths']} paths.", ""]
    else:
        lines += ["## PBO / Deflated Sharpe (CPCV)",
                  f"- CPCV ready (N={m['n_groups']} k={m['k']} -> {m['n_splits']} splits, {m['n_paths']} paths); "
                  "populated once a model (Stage 2) produces path performance.", ""]

    summary["underpowered"] = bool(hit_underpowered or n_ex == 0)
    summary["verdict"] = ("UNDERPOWERED" if summary["underpowered"] else
                          ("EDGE-CONFIRMED" if summary["sprt"] == "ACCEPT" else
                           "NO-EDGE" if summary["sprt"] == "REJECT" else "INCONCLUSIVE"))
    lines += ["## Verdict", "", summary["verdict"]]
    return {"markdown": "\n".join(lines), "summary": summary}

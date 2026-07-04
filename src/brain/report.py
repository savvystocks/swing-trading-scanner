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

# SPRT parameters (predefined - mirrored into ROADMAP.md item 7 so they cannot be quietly changed):
SPRT_ALPHA, SPRT_BETA = 0.05, 0.20
SPRT_MIN_EDGE = 0.05       # H1 = empirical hurdle + 5 percentage points


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

        # ---- SPRT on executed trades ----
        p0 = min(max(hurdle + cost, 1e-3), 0.99)
        p1 = min(p0 + SPRT_MIN_EDGE, 0.999)
        s = EV.sprt(wins, n_ex, p0, p1, SPRT_ALPHA, SPRT_BETA)
        summary["sprt"] = s["decision"]
        lines += ["## Sequential edge test (SPRT)",
                  f"- H0 win-rate={_fmt(p0,3)} (hurdle+cost)  H1={_fmt(p1,3)} (hurdle+{SPRT_MIN_EDGE})  "
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

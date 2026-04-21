import pandas as pd
import numpy as np


def max_drawdown_1y(df):
    if len(df) < 252:
        return None
    window = df["close"].iloc[-252:]
    running_max = window.cummax()
    drawdown = (window - running_max) / running_max * 100
    return float(drawdown.min())


def correlation_with_benchmark(candidate_df, benchmark_df, lookback=126):
    if len(candidate_df) < lookback or len(benchmark_df) < lookback:
        return None
    c = candidate_df["close"].iloc[-lookback:].pct_change().dropna()
    b = benchmark_df["close"].iloc[-lookback:].pct_change().dropna()
    merged = pd.concat([c, b], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return None
    corr = merged.iloc[:, 0].corr(merged.iloc[:, 1])
    return float(corr) if not pd.isna(corr) else None


def rolling_beta(candidate_df, benchmark_df, lookback=126):
    if len(candidate_df) < lookback or len(benchmark_df) < lookback:
        return None
    c = candidate_df["close"].iloc[-lookback:].pct_change().dropna()
    b = benchmark_df["close"].iloc[-lookback:].pct_change().dropna()
    merged = pd.concat([c, b], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return None
    cov = merged.iloc[:, 0].cov(merged.iloc[:, 1])
    var = merged.iloc[:, 1].var()
    if var == 0:
        return None
    return float(cov / var)


def gap_frequency(df, lookback=252, threshold_pct=3.0):
    if len(df) < lookback:
        return None
    window = df.iloc[-lookback:]
    prev_close = window["close"].shift(1)
    gap_pct = (window["open"] - prev_close) / prev_close * 100
    big_gaps = (gap_pct.abs() > threshold_pct).sum()
    return int(big_gaps)


def _label(value, thresholds, higher_is_better=False):
    if value is None:
        return "UNKNOWN"
    pass_t, warn_t = thresholds
    if higher_is_better:
        if value >= pass_t:
            return "PASS"
        if value >= warn_t:
            return "WARN"
        return "FAIL"
    if value <= pass_t:
        return "PASS"
    if value <= warn_t:
        return "WARN"
    return "FAIL"


def run_stress_tests(candidate_df, benchmark_df):
    dd = max_drawdown_1y(candidate_df)
    corr = correlation_with_benchmark(candidate_df, benchmark_df)
    beta = rolling_beta(candidate_df, benchmark_df)
    gaps = gap_frequency(candidate_df)

    tests = {
        "drawdown_1y": {
            "value": round(dd, 1) if dd is not None else None,
            "label": _label(abs(dd) if dd is not None else None, (25, 40)),
            "desc": "Worst 1Y drawdown %",
        },
        "spy_correlation": {
            "value": round(corr, 2) if corr is not None else None,
            "label": _label(corr, (0.8, 0.92)) if corr is not None else "UNKNOWN",
            "desc": "6M correlation with benchmark",
        },
        "beta": {
            "value": round(beta, 2) if beta is not None else None,
            "label": _label(beta, (1.8, 2.5)) if beta is not None else "UNKNOWN",
            "desc": "6M beta",
        },
        "gap_frequency_1y": {
            "value": gaps,
            "label": _label(gaps, (5, 10)) if gaps is not None else "UNKNOWN",
            "desc": "Gap events >3% in last year",
        },
    }

    passes = sum(1 for t in tests.values() if t["label"] == "PASS")
    warns = sum(1 for t in tests.values() if t["label"] == "WARN")
    fails = sum(1 for t in tests.values() if t["label"] == "FAIL")

    if fails >= 2:
        overall = "FAIL"
    elif fails == 1 or warns >= 2:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "overall": overall,
        "passes": passes,
        "warns": warns,
        "fails": fails,
        "tests": tests,
    }

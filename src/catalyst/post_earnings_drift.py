from datetime import datetime, timedelta


def detect_post_earnings_drift(scored_results, lookback_days=5):
    today = datetime.utcnow().date()
    out = {}
    for s in scored_results:
        ticker = s.get("ticker")
        if not ticker:
            continue
        earnings_hist = s.get("earnings_history") or []
        last = None
        for e in earnings_hist:
            report_date = e.get("reportDate") or e.get("report_date")
            if not report_date:
                continue
            try:
                rd = datetime.strptime(report_date, "%Y-%m-%d").date()
            except Exception:
                continue
            days_since = (today - rd).days
            if 0 <= days_since <= lookback_days:
                last = {**e, "days_since": days_since, "report_date": report_date}
                break
        if not last:
            continue
        try:
            actual = float(last.get("epsActual") or last.get("eps_actual") or 0)
            estimate = float(last.get("epsEstimate") or last.get("eps_estimate") or 0)
        except (TypeError, ValueError):
            actual = estimate = 0
        beat = actual > estimate and estimate > 0
        if not beat:
            continue
        surprise_pct = ((actual - estimate) / abs(estimate) * 100) if estimate else 0
        price = s.get("price") or 0
        prior_close = s.get("price_5d_ago") or s.get("prior_close_pre_earnings")
        post_print_pct = None
        if price and prior_close:
            post_print_pct = (price - prior_close) / prior_close * 100
        out[ticker] = {
            "key": "post_earnings_drift",
            "days_since_report": last["days_since"],
            "report_date": last["report_date"],
            "surprise_pct": round(surprise_pct, 2),
            "post_print_move_pct": round(post_print_pct, 2) if post_print_pct is not None else None,
            "details": f"beat by {surprise_pct:.1f}% on {last['report_date']} ({last['days_since']}d ago)",
            "direction": "bull",
        }
    return out


def apply_ped_scoring(scored_results, ped_signals):
    for s in scored_results:
        ticker = s.get("ticker")
        if ticker not in ped_signals:
            continue
        ped = ped_signals[ticker]
        components = s.get("components") or {}
        score_delta = 0
        if ped["surprise_pct"] >= 10:
            score_delta = 8
        elif ped["surprise_pct"] >= 5:
            score_delta = 5
        elif ped["surprise_pct"] >= 2:
            score_delta = 3
        if ped.get("post_print_move_pct") and ped["post_print_move_pct"] > 5:
            score_delta += 4
        if score_delta > 0:
            components["post_earnings_drift"] = {
                "points": score_delta,
                "label": f"PED: beat {ped['surprise_pct']:.1f}% on {ped['report_date']}, +{ped.get('post_print_move_pct') or 0:.1f}% since",
            }
            s["components"] = components
            s["score"] = round((s.get("score") or 0) + score_delta, 2)
            s["earnings_blackout_override"] = True
    return scored_results

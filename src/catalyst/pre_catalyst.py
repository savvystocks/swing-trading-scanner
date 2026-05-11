from datetime import datetime, timedelta


CONFERENCE_CALENDAR = [
    {"name": "GTC 2026", "date": "2026-09-09", "category": "AI infrastructure", "themes": ["ai", "semiconductor", "data_center"]},
    {"name": "OFC 2026", "date": "2026-04-13", "category": "Optical networking", "themes": ["optical", "photonic", "interconnect"]},
    {"name": "Hot Chips 2026", "date": "2026-08-25", "category": "Semiconductor", "themes": ["semiconductor", "ai_accelerator"]},
    {"name": "RSA 2026", "date": "2026-04-27", "category": "Cybersecurity", "themes": ["security"]},
    {"name": "JPM Healthcare 2026", "date": "2026-01-13", "category": "Biotech", "themes": ["biotech", "pharma"]},
    {"name": "Russell Reconstitution 2026", "date": "2026-06-26", "category": "Index rebalance", "themes": ["all"]},
]

KNOWN_PDUFA_DATES = {}


def get_upcoming_earnings(client, eodhd_tickers, days_min=1, days_max=45, verbose=False):
    today = datetime.utcnow().date()
    upcoming = {}
    fetched = 0
    for ticker in eodhd_tickers:
        try:
            fund = client.fundamentals(ticker)
            fetched += 1
            if not fund:
                continue
            earnings = (fund.get("Earnings") or {}).get("History") or {}
            future_dates = []
            for row in earnings.values():
                if not isinstance(row, dict):
                    continue
                report_date = row.get("reportDate")
                if not report_date or row.get("epsActual") is not None:
                    continue
                try:
                    d = datetime.strptime(report_date, "%Y-%m-%d").date()
                    if d >= today:
                        future_dates.append((d, row))
                except Exception:
                    pass
            if not future_dates:
                continue
            future_dates.sort(key=lambda x: x[0])
            next_date, row = future_dates[0]
            days_until = (next_date - today).days
            if days_min <= days_until <= days_max:
                upcoming[ticker] = {
                    "catalyst_type": "earnings",
                    "event_date": next_date.strftime("%Y-%m-%d"),
                    "days_until": days_until,
                    "before_after_market": row.get("beforeAfterMarket", ""),
                }
        except Exception:
            continue
    if verbose:
        print(f"  pre_catalyst: fetched fundamentals for {fetched} candidates, found {len(upcoming)} earnings in {days_min}-{days_max}d window")
    return upcoming


def get_upcoming_conferences(days_max=45):
    today = datetime.utcnow().date()
    out = []
    for c in CONFERENCE_CALENDAR:
        try:
            d = datetime.strptime(c["date"], "%Y-%m-%d").date()
            days_until = (d - today).days
            if 0 <= days_until <= days_max:
                out.append({**c, "days_until": days_until})
        except Exception:
            pass
    return sorted(out, key=lambda x: x["days_until"])


def pre_catalyst_signal_score(scored, upcoming_event):
    catalysts = scored.get("catalysts") or []
    catalysts_count = len(catalysts)

    pre_event_signal_keys = {
        "revision_spike", "insider_cluster", "capex_echo", "backlog_surge",
        "strategic_investment", "spinoff_catalyst", "activist_stake",
    }
    detectors_firing = sum(1 for c in catalysts if c.get("key") in pre_event_signal_keys)

    score = 0
    flags = []

    if detectors_firing >= 3:
        score += 7
        flags.append(f"{detectors_firing} pre-event signals firing (strong stack)")
    elif detectors_firing >= 2:
        score += 4
        flags.append(f"{detectors_firing} pre-event signals firing")
    elif detectors_firing >= 1:
        score += 2

    options_flow = scored.get("options_flow") or {}
    if options_flow.get("sentiment") == "BULLISH":
        score += 4
        flags.append(f"bullish options flow ({len(options_flow.get('bullish_signals') or [])} signals)")
    elif options_flow.get("sentiment") == "BEARISH":
        score -= 3
        flags.append("bearish options flow (warning)")

    insider_depth = scored.get("insider_depth") or {}
    insider_pts = insider_depth.get("points", 0) if isinstance(insider_depth, dict) else 0
    if insider_pts >= 7:
        score += 4
        flags.append("strong insider buying (CEO/CFO cluster)")
    elif insider_pts >= 3:
        score += 2
        flags.append("insider buying activity")

    drift = (scored.get("components") or {}).get("drift") or {}
    drift_pts = drift.get("points", 0)
    if drift_pts >= 8:
        score -= 2
        flags.append(f"pre-priced ({drift_pts} drift pts) — sell-the-news risk")
    elif drift_pts >= 3:
        score += 2
        flags.append(f"positive drift +{drift_pts}")

    if catalysts_count >= 4:
        score += 4
        flags.append(f"{catalysts_count} catalysts stacked overall")
    elif catalysts_count >= 3:
        score += 2

    days_until = upcoming_event.get("days_until", 999)
    if 5 <= days_until <= 21:
        score += 1
    elif days_until > 30:
        score -= 1

    if score >= 14:
        verdict = "HIGH_CONVICTION"
    elif score >= 9:
        verdict = "STRONG"
    elif score >= 5:
        verdict = "MODERATE"
    elif score >= 2:
        verdict = "WATCH"
    else:
        verdict = "LOW"

    return {
        "score": score,
        "verdict": verdict,
        "flags": flags,
        "detectors_firing": detectors_firing,
        "catalysts_count": catalysts_count,
    }


def build_pre_catalyst_watchlist(client, scored_results, cohort_tickers,
                                  days_min=1, days_max=45, verbose=False):
    by_ticker = {s.get("ticker"): s for s in scored_results}

    candidate_tickers = set(cohort_tickers or [])
    for s in scored_results:
        if s.get("bucket") in ("STRONG", "WATCH"):
            candidate_tickers.add(s.get("ticker"))
        for c in (s.get("catalysts") or []):
            if c.get("key", "").startswith("cohort_high_momentum"):
                candidate_tickers.add(s.get("ticker"))

    candidate_tickers = {t for t in candidate_tickers if t}
    eodhd_tickers = []
    for tk in candidate_tickers:
        if "." in tk:
            eodhd_tickers.append(tk)
        else:
            eodhd_tickers.append(f"{tk}.US")

    upcoming_earnings = get_upcoming_earnings(client, eodhd_tickers, days_min, days_max, verbose=verbose)

    watchlist = []
    for eodhd_tk, event in upcoming_earnings.items():
        ticker = eodhd_tk.split(".")[0]
        scored = by_ticker.get(ticker) or {"ticker": ticker, "catalysts": [], "score": 0}
        signal = pre_catalyst_signal_score(scored, event)
        watchlist.append({
            "ticker": ticker,
            "name": scored.get("name", ""),
            "sector": scored.get("sector", ""),
            "industry": scored.get("industry", ""),
            "market_cap": scored.get("market_cap"),
            "price": scored.get("price"),
            "live_spot": scored.get("live_spot"),
            "live_change_pct": scored.get("live_change_pct"),
            "eodhd_ticker": eodhd_tk,
            "event_type": event["catalyst_type"],
            "event_date": event["event_date"],
            "days_until": event["days_until"],
            "before_after_market": event.get("before_after_market", ""),
            "pre_catalyst_score": signal["score"],
            "pre_catalyst_verdict": signal["verdict"],
            "pre_catalyst_flags": signal["flags"],
            "detectors_firing": signal["detectors_firing"],
            "catalysts_count": signal["catalysts_count"],
            "current_signals": [c.get("key") for c in (scored.get("catalysts") or [])],
            "scan_score": scored.get("score", 0),
            "scored_data": scored,
        })

    watchlist.sort(key=lambda w: (-(w["pre_catalyst_score"] or 0), w["days_until"]))
    return watchlist


def get_high_momentum_tickers():
    import json
    import pathlib
    cohorts_path = pathlib.Path(__file__).parent.parent.parent / "data" / "catalyst" / "cohorts.json"
    try:
        with open(cohorts_path) as f:
            cohorts = json.load(f)
        return cohorts.get("high_momentum_runners", {}).get("tickers", [])
    except Exception:
        return []

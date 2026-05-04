def compute_drift(df, lookback_5d=5, lookback_10d=10):
    if df is None or len(df) < lookback_10d + 1:
        return None
    last_close = float(df["close"].iloc[-1])
    close_5d_ago = float(df["close"].iloc[-1 - lookback_5d]) if len(df) > lookback_5d else None
    close_10d_ago = float(df["close"].iloc[-1 - lookback_10d]) if len(df) > lookback_10d else None
    close_1d_ago = float(df["close"].iloc[-2]) if len(df) > 1 else None
    if close_5d_ago is None or close_5d_ago == 0:
        return None
    roc_5d = (last_close - close_5d_ago) / close_5d_ago * 100
    roc_10d = (last_close - close_10d_ago) / close_10d_ago * 100 if close_10d_ago else None
    roc_1d = (last_close - close_1d_ago) / close_1d_ago * 100 if close_1d_ago else None
    return {
        "roc_1d": round(roc_1d, 2) if roc_1d is not None else None,
        "roc_5d": round(roc_5d, 2),
        "roc_10d": round(roc_10d, 2) if roc_10d is not None else None,
        "last_close": round(last_close, 2),
    }


SCHEDULED_OVERNIGHT_KEYS = {
    "earnings_bmo_tomorrow", "earnings_amc_today",
    "earnings_bmo_with_beat_streak", "fda_pdufa_tomorrow",
}

POST_EVENT_KEYS = {
    "definitive_agreement", "asset_sale", "merger", "fda_event",
    "clinical_milestone", "private_placement", "covenant_relief",
    "strategic_partnership", "contract_win", "activist_stake",
    "insider_cluster", "buyback", "rebrand", "merger_cash_buyout",
    "major_contract_win",
}


def drift_score(drift, signals=None, points_max=10.0):
    if not drift:
        return {"points": 0.0, "label": "no drift data", "extended": False, "pre_priced": False, "skip_chase": False}

    roc_5d = drift.get("roc_5d") or 0
    roc_1d = drift.get("roc_1d") or 0

    is_scheduled = False
    is_post_event = False
    if signals:
        for s in signals:
            key = s.get("key", "")
            if key in SCHEDULED_OVERNIGHT_KEYS:
                is_scheduled = True
            if key in POST_EVENT_KEYS:
                is_post_event = True

    treat_as_post = is_post_event and not is_scheduled

    if roc_1d >= 7:
        return {
            "points": -25.0,
            "label": f"BREAKING TODAY +{roc_1d:.1f}% — catalyst already priced in",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": True, "pre_priced": True, "skip_chase": True,
        }

    if roc_5d >= 15:
        return {
            "points": -25.0,
            "label": f"OVER-EXTENDED +{roc_5d:.1f}% in 5d — chasing the tail",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": True, "pre_priced": True, "skip_chase": True,
        }

    if treat_as_post and roc_5d >= 8:
        return {
            "points": -18.0,
            "label": f"EXTENDED +{roc_5d:.1f}% post-event chase",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": True, "pre_priced": False, "skip_chase": True,
        }

    if treat_as_post and roc_5d >= 5:
        return {
            "points": -10.0,
            "label": f"already moved +{roc_5d:.1f}% post-event",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": True, "pre_priced": False, "skip_chase": False,
        }

    if is_scheduled and roc_5d >= 10:
        return {
            "points": -10.0,
            "label": f"PRE-PRICED +{roc_5d:.1f}% into event (sell-the-news risk)",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": False, "pre_priced": True, "skip_chase": False,
        }

    if is_scheduled and roc_5d >= 6:
        return {
            "points": -3.0,
            "label": f"some pre-event run +{roc_5d:.1f}%",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": False, "pre_priced": True, "skip_chase": False,
        }

    if -3 <= roc_5d <= 4:
        return {
            "points": points_max,
            "label": f"clean flat setup {roc_5d:+.1f}% 5d (ideal entry)",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": False, "pre_priced": False, "skip_chase": False,
        }

    if -6 <= roc_5d < -3:
        return {
            "points": points_max * 0.7,
            "label": f"oversold bounce setup {roc_5d:+.1f}%",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": False, "pre_priced": False, "skip_chase": False,
        }

    if 4 < roc_5d < 6:
        return {
            "points": points_max * 0.5,
            "label": f"mild run +{roc_5d:.1f}% (acceptable)",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": False, "pre_priced": False, "skip_chase": False,
        }

    if roc_5d < -6:
        return {
            "points": -5.0,
            "label": f"weak trend {roc_5d:+.1f}%",
            "roc_5d": roc_5d, "roc_1d": roc_1d,
            "extended": False, "pre_priced": False, "skip_chase": False,
        }

    return {
        "points": 0.0, "label": f"neutral {roc_5d:+.1f}%",
        "roc_5d": roc_5d, "roc_1d": roc_1d,
        "extended": False, "pre_priced": False, "skip_chase": False,
    }


def timing_bonus(catalysts, drift):
    has_scheduled = any(c.get("event_timing") == "scheduled_overnight" for c in catalysts or [])
    has_fresh = any(c.get("event_timing") == "fresh_breaking" for c in catalysts or [])
    has_post = any(c.get("event_timing") == "post_event" for c in catalysts or [])

    roc_5d = (drift or {}).get("roc_5d") or 0
    is_flat = -3 <= roc_5d <= 4

    if has_scheduled and is_flat:
        return {"points": 15.0, "label": "OVERNIGHT CATALYST + FLAT ENTRY (ideal)", "ideal_setup": True}
    if has_scheduled and roc_5d < 6:
        return {"points": 8.0, "label": "scheduled overnight catalyst, mild drift", "ideal_setup": False}
    if has_scheduled:
        return {"points": -3.0, "label": "scheduled catalyst but stock has run", "ideal_setup": False}
    if has_fresh and is_flat:
        return {"points": 6.0, "label": "fresh breaking news on flat stock", "ideal_setup": False}
    if has_post and not has_scheduled and not has_fresh:
        return {"points": -8.0, "label": "post-event only — catalyst already absorbed", "ideal_setup": False}
    return {"points": 0.0, "label": "no clear timing edge", "ideal_setup": False}

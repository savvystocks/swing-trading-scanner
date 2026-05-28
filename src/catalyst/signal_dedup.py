"""Signal deduplication - run BEFORE conviction_score to stop triple-counting.

Two modules can independently detect the same real-world event (e.g. an analyst
upgrade hits via news_sentiment, analyst_rating_news, AND StreetInsider).
Without dedup, a single event adds points to multiple components and inflates
conviction by 8-15 pts.

Rule of thumb: when two sources agree, keep the higher-fidelity source and
suppress the others. We never DELETE the raw data - we add a `_deduped_to`
field for traceability and zero out the score-contributing flag.
"""


PRIMARY_BUYBACK = "_edgar_buyback"
PRIMARY_GUIDANCE = "_edgar_guidance_raise"
PRIMARY_ANALYST = "_analyst_rating_changes"


def _has_edgar_buyback(pick):
    bb = pick.get(PRIMARY_BUYBACK) or {}
    return bb.get("verdict") == "BUYBACK_ANNOUNCED"


def _has_edgar_guidance(pick):
    gr = pick.get(PRIMARY_GUIDANCE) or {}
    return gr.get("verdict") == "GUIDANCE_RAISED"


def _has_analyst_signal(pick):
    a = pick.get(PRIMARY_ANALYST) or {}
    v = a.get("verdict")
    return v in ("UPGRADE_CLUSTER", "BULLISH_LEAN", "BEARISH_LEAN", "DOWNGRADE_CLUSTER")


def _dedup_streetinsider(pick):
    si = pick.get("_streetinsider")
    if not si:
        return []
    suppressed = []
    if si.get("buyback") and _has_edgar_buyback(pick):
        si["buyback"] = False
        suppressed.append("streetinsider.buyback (covered by edgar_buyback)")
    if si.get("guidance_change") and _has_edgar_guidance(pick):
        si["guidance_change"] = False
        suppressed.append("streetinsider.guidance_change (covered by edgar_guidance_raise)")
    if (si.get("upgrade") or si.get("downgrade")) and _has_analyst_signal(pick):
        if si.get("upgrade"):
            si["upgrade"] = False
            suppressed.append("streetinsider.upgrade (covered by analyst_rating_changes)")
        if si.get("downgrade"):
            si["downgrade"] = False
            suppressed.append("streetinsider.downgrade (covered by analyst_rating_changes)")
    return suppressed


def _dedup_news_sentiment_analyst(pick):
    """If analyst_rating_news already classified this as upgrade/downgrade cluster,
    don't double-count news_sentiment's analyst-headline points."""
    ns = pick.get("_news_sentiment")
    if not ns:
        return []
    if not _has_analyst_signal(pick):
        return []
    suppressed = []
    # news_sentiment commonly carries an analyst-event flag we don't want
    # to score on top of the dedicated analyst_rating_changes module.
    if ns.get("analyst_upgrade_count", 0) > 0:
        ns["_dedup_original_analyst_upgrade_count"] = ns.get("analyst_upgrade_count")
        ns["analyst_upgrade_count"] = 0
        suppressed.append("news_sentiment.analyst_upgrade_count (covered by analyst_rating_changes)")
    if ns.get("analyst_downgrade_count", 0) > 0:
        ns["_dedup_original_analyst_downgrade_count"] = ns.get("analyst_downgrade_count")
        ns["analyst_downgrade_count"] = 0
        suppressed.append("news_sentiment.analyst_downgrade_count (covered by analyst_rating_changes)")
    return suppressed


def _dedup_catalyst_buyback(pick):
    """If we already have a hard EDGAR buyback signal, demote any catalyst key
    that's the lower-fidelity news-derived version of the same event."""
    if not _has_edgar_buyback(pick):
        return []
    suppressed = []
    cats = pick.get("catalysts") or []
    # The catalyst module's news-derived 'buyback_authorization' is the duplicate
    # of EDGAR's primary 8-K buyback announcement.
    keep = []
    for c in cats:
        if isinstance(c, dict) and c.get("key") == "buyback_authorization":
            suppressed.append(f"catalyst.buyback_authorization (covered by edgar_buyback)")
            c["_deduped_to"] = "edgar_buyback"
            c["_dedup_zeroed_points"] = c.get("points", 0)
            c["points"] = 0
        keep.append(c)
    if keep:
        pick["catalysts"] = keep
    return suppressed


def dedup_pick(pick):
    if not isinstance(pick, dict):
        return []
    all_suppressed = []
    all_suppressed.extend(_dedup_streetinsider(pick))
    all_suppressed.extend(_dedup_news_sentiment_analyst(pick))
    all_suppressed.extend(_dedup_catalyst_buyback(pick))
    if all_suppressed:
        pick["_signal_dedup"] = all_suppressed
    return all_suppressed


def apply_signal_dedup(picks, verbose=False):
    if not picks:
        return picks
    total_suppressions = 0
    affected = 0
    for p in picks:
        s = dedup_pick(p)
        if s:
            affected += 1
            total_suppressions += len(s)
    if verbose:
        print(f"  signal_dedup: {affected} picks had duplicate signals, {total_suppressions} suppressions total")
    return picks

VERDICT_LABELS = {
    "BUY_AS_IS": "Take as-is",
    "PREFER_SPREAD": "Use spread instead",
    "GO_FURTHER_OTM": "Cheaper strike",
    "GO_CLOSER_ATM": "Tighter strike",
    "SKIP": "Skip",
    "STRONG BUY": "Strong buy",
    "BUY": "Buy",
    "HOLD": "Hold",
    "WATCH": "Watch",
}

BUCKET_LABELS = {
    "STRONG": "Top picks",
    "WATCH": "Worth watching",
    "SPECULATIVE": "Speculative",
    "BELOW_THRESHOLD": "Below threshold",
    "TRACK": "Tracking",
}

CONVICTION_LABELS = {
    "HIGH_CONVICTION": "Strong setup",
    "STRONG": "Strong",
    "MODERATE": "Moderate",
    "WATCH": "On watch",
    "LOW": "Weak signal",
    "HIGH": "High conviction",
    "SINGLE": "Single signal",
    "NONE": "No conviction",
}

CATALYST_KEY_LABELS = {
    "earnings_bmo_tomorrow": "Reports earnings tomorrow morning",
    "earnings_amc_today": "Reports earnings tonight after close",
    "earnings_bmo_with_beat_streak": "Earnings imminent + has beaten last 4 quarters",
    "earnings_imminent_5_9d": "Earnings in 5-9 days (IV expansion zone)",
    "earnings_lead_up_10_15d": "Earnings in 10-15 days (entry sweet spot)",
    "earnings_peak_iv_3_4d": "Earnings in 3-4 days (peak option premium)",
    "fda_pdufa_tomorrow": "FDA decision due tomorrow",
    "fda_event": "FDA decision or filing scheduled",
    "fda_rejection": "FDA rejection just announced",
    "merger_cash_buyout": "Cash buyout offer on the table",
    "merger": "Merger filed",
    "merger_terminated": "Merger fell through",
    "asset_sale": "Selling assets to unlock value",
    "definitive_agreement": "Material agreement just signed",
    "clinical_milestone": "Clinical trial data coming",
    "private_placement": "Private placement deal",
    "covenant_relief": "Negotiated debt covenant relief",
    "strategic_partnership": "Strategic partnership announced",
    "contract_win": "Won a new customer contract",
    "major_contract_win": "Landed a major customer contract",
    "activist_stake": "Activist investor took a stake",
    "insider_cluster": "Multiple insiders buying in a cluster",
    "buyback": "Share buyback authorised",
    "rebrand": "Company rebrand / name change",
    "going_concern": "Auditor going-concern warning",
    "earnings_miss_with_guide_down": "Missed earnings + cut forward guidance",
    "dilutive_offering": "Issuing more shares (dilution risk)",
    "reverse_stock_split": "Reverse stock split (red flag)",
    "lawsuit_material": "Material lawsuit filed",
    "downgrade_cluster": "Multiple analysts downgrading",
    "auditor_change": "Auditor just resigned",
    "delisting_warning": "Stock at risk of delisting",
    "restatement": "Restating prior financials",
    "executive_departure": "CEO or CFO leaving",
    "insider_selling_cluster": "Heavy insider selling cluster",
    "capex_echo": "Hyperscaler announced spending plans (supplier benefits)",
    "backlog_surge": "Record-breaking customer order backlog",
    "revision_spike": "Wall Street raising EPS estimates",
    "strategic_investment": "Hyperscaler made a strategic investment",
    "spinoff_catalyst": "Spinning off a business unit",
    "post_earnings_beat": "Beat earnings and stock holding gains",
    "post_earnings_drift": "Post-earnings drift still active",
    "bank_post_earnings_drift": "Bank post-earnings drift active",
    "ai_deal_announcement": "AI deal or partnership announced",
    "semis_capex_signal": "Semiconductor capex signal benefits this name",
    "defense_contract_award": "Won a defense contract",
    "13d": "Activist 13D filed",
    "13d_a": "Activist amended 13D filed",
    "ipo_lockup_expiry": "IPO lockup expiring (insider sell pressure)",
    "secondary_offering": "Secondary share offering",
    "guidance_raise": "Raised forward guidance",
    "preliminary_results": "Pre-announced strong results",
    "ratings_upgrade": "Credit rating upgrade",
    "ratings_downgrade": "Credit rating downgrade",
    "index_inclusion": "Being added to an index (forced buying)",
    "index_exit": "Being removed from an index (forced selling)",
    "cohort_high_momentum_runners": "On the high-momentum mid-cap watchlist",
    "cohort_lazar_plays": "Held by Lazar Capital (smart-money cohort)",
    "cohort_crypto_treasury": "Holds crypto on balance sheet",
    "cohort_prediction_markets": "Prediction market play",
    "cohort_biotech_binary": "Biotech with binary catalyst",
    "cohort_ai_rebrand": "Recently rebranded around AI",
    "cohort_cannabis_basket": "Cannabis sector cohort",
    "cohort_small_cap_china_adr": "China small-cap ADR cohort",
}

STATUS_LABELS = {
    "HAPPENED": "Already happened",
    "SCHEDULED": "Scheduled",
    "EXPECTED": "Expected",
    "RUMORED": "Rumored",
}

IV_ASSESSMENT_LABELS = {
    "ELEVATED": "High (event premium baked in)",
    "FAIR": "Fair",
    "COMPRESSED": "Low (cheap)",
}

IV_CRUSH_LABELS = {
    "HIGH": "High risk of premium drop after event",
    "MEDIUM": "Some volatility-drop risk",
    "LOW": "Low volatility-drop risk",
}

STRIKE_RATING_LABELS = {
    "GOOD": "Good fit",
    "OK": "Acceptable",
    "POOR": "Poor fit for the move needed",
}

SPREAD_RATING_LABELS = {
    "TIGHT": "Tight bid-ask",
    "FAIR": "Fair bid-ask",
    "WIDE": "Wide bid-ask (slippage)",
}


def humanize_verdict(label):
    return VERDICT_LABELS.get(label, label)


def humanize_bucket(label):
    return BUCKET_LABELS.get(label, label)


def humanize_conviction(label):
    return CONVICTION_LABELS.get(label, label)


def humanize_catalyst_key(key):
    if not key:
        return ""
    if key in CATALYST_KEY_LABELS:
        return CATALYST_KEY_LABELS[key]
    fallback = key.replace("_", " ").strip()
    return fallback[0].upper() + fallback[1:] if fallback else key


def humanize_catalyst_list(catalysts, max_items=4):
    if not catalysts:
        return []
    out = []
    seen = set()
    for c in catalysts:
        if isinstance(c, dict):
            key = c.get("key") or ""
        else:
            key = str(c)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(humanize_catalyst_key(key))
        if len(out) >= max_items:
            break
    return out


def humanize_status(label):
    return STATUS_LABELS.get(label, label)


def humanize_iv(label):
    return IV_ASSESSMENT_LABELS.get(label, label)


def humanize_iv_crush(label):
    return IV_CRUSH_LABELS.get(label, label)


def humanize_strike(label):
    return STRIKE_RATING_LABELS.get(label, label)


def humanize_spread(label):
    return SPREAD_RATING_LABELS.get(label, label)


def register_jinja_filters(env):
    env.filters["humanize_verdict"] = humanize_verdict
    env.filters["humanize_bucket"] = humanize_bucket
    env.filters["humanize_conviction"] = humanize_conviction
    env.filters["humanize_catalyst"] = humanize_catalyst_key
    env.filters["humanize_status"] = humanize_status
    env.filters["humanize_iv"] = humanize_iv
    env.filters["humanize_iv_crush"] = humanize_iv_crush
    env.filters["humanize_strike"] = humanize_strike
    env.filters["humanize_spread"] = humanize_spread

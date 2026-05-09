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
    "earnings_bmo_tomorrow": "Earnings tomorrow morning",
    "earnings_amc_today": "Earnings tonight after close",
    "earnings_bmo_with_beat_streak": "Earnings + beat streak",
    "fda_pdufa_tomorrow": "FDA decision tomorrow",
    "fda_event": "FDA filing",
    "fda_rejection": "FDA rejection",
    "merger_cash_buyout": "Cash buyout offered",
    "merger": "Merger filed",
    "merger_terminated": "Merger killed",
    "asset_sale": "Asset sale agreement",
    "definitive_agreement": "Material agreement",
    "clinical_milestone": "Clinical trial milestone",
    "private_placement": "Private placement",
    "covenant_relief": "Covenant relief / forbearance",
    "strategic_partnership": "Strategic partnership",
    "contract_win": "Contract win",
    "major_contract_win": "Major contract win",
    "activist_stake": "Activist takes stake",
    "insider_cluster": "Insider buying cluster",
    "buyback": "Buyback announced",
    "rebrand": "Company rebrand",
    "going_concern": "Going-concern flag",
    "earnings_miss_with_guide_down": "Earnings miss + guidance cut",
    "dilutive_offering": "Dilutive offering",
    "reverse_stock_split": "Reverse stock split",
    "lawsuit_material": "Material lawsuit",
    "downgrade_cluster": "Multiple downgrades",
    "auditor_change": "Auditor resigned",
    "delisting_warning": "Delisting risk",
    "restatement": "Financial restatement",
    "executive_departure": "CEO/CFO leaving",
    "insider_selling_cluster": "Heavy insider selling",
    "capex_echo": "Hyperscaler capex echo",
    "backlog_surge": "Order backlog surge",
    "revision_spike": "EPS estimate raises",
    "strategic_investment": "Strategic investment from hyperscaler",
    "spinoff_catalyst": "Spinoff / separation",
    "cohort_high_momentum_runners": "High-momentum mid-cap watchlist",
    "cohort_lazar_plays": "Lazar Capital portfolio",
    "cohort_crypto_treasury": "Crypto treasury name",
    "cohort_prediction_markets": "Prediction market name",
    "cohort_biotech_binary": "Biotech binary catalyst",
    "cohort_ai_rebrand": "AI rebrand cohort",
    "cohort_cannabis_basket": "Cannabis basket",
    "cohort_small_cap_china_adr": "China small-cap ADR",
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
    return CATALYST_KEY_LABELS.get(key, key)


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

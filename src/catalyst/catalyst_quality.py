"""Catalyst quality classification.

Splits catalyst types into evidence-based (demonstrated statistical edge for retail
swing trades) and speculative (binary outcomes, no information edge, lottery
tickets). Speculative picks are filtered out of the email and dashboard.
"""


SPECULATIVE_CATALYST_KEYS = {
    "fda_event",
    "fda_pdufa_tomorrow",
    "fda_rejection",
    "clinical_milestone",
    "cohort_biotech_binary",
    "merger",
    "merger_cash_buyout",
    "merger_terminated",
    "cohort_ai_rebrand",
    "cohort_cannabis_basket",
    "cohort_small_cap_china_adr",
    "cohort_crypto_treasury",
    "cohort_prediction_markets",
}


EVIDENCE_CATALYST_KEYS = {
    "earnings_bmo_tomorrow",
    "earnings_amc_today",
    "earnings_bmo_with_beat_streak",
    "earnings_imminent_5_9d",
    "earnings_lead_up_10_15d",
    "earnings_peak_iv_3_4d",
    "post_earnings_beat",
    "post_earnings_drift",
    "bank_post_earnings_drift",
    "insider_cluster",
    "activist_stake",
    "13d",
    "13d_a",
    "contract_win",
    "major_contract_win",
    "strategic_partnership",
    "strategic_investment",
    "buyback",
    "guidance_raise",
    "preliminary_results",
    "ratings_upgrade",
    "revision_spike",
    "backlog_surge",
    "index_inclusion",
    "definitive_agreement",
    "asset_sale",
    "spinoff_catalyst",
    "ai_deal_announcement",
    "semis_capex_signal",
    "defense_contract_award",
    "cohort_high_momentum_runners",
    "cohort_lazar_plays",
    "covenant_relief",
    "capex_echo",
}


NEGATIVE_CATALYST_KEYS = {
    "going_concern",
    "dilutive_offering",
    "reverse_stock_split",
    "lawsuit_material",
    "downgrade_cluster",
    "auditor_change",
    "delisting_warning",
    "restatement",
    "executive_departure",
    "insider_selling_cluster",
    "earnings_miss_with_guide_down",
    "private_placement",
}


def catalyst_keys_of(pick):
    keys = []
    for c in (pick.get("catalysts") or []):
        if isinstance(c, dict):
            k = c.get("key") or ""
        else:
            k = str(c)
        if k:
            keys.append(k)
    return keys


def is_speculative_only(pick):
    """True if this pick has no evidence-based catalyst — only speculative ones."""
    keys = catalyst_keys_of(pick)
    if not keys:
        return False
    evidence_present = any(k in EVIDENCE_CATALYST_KEYS for k in keys)
    return not evidence_present


def has_speculative(pick):
    """True if any catalyst is speculative (regardless of whether evidence-based is also present)."""
    return any(k in SPECULATIVE_CATALYST_KEYS for k in catalyst_keys_of(pick))


def evidence_catalyst_count(pick):
    return sum(1 for k in catalyst_keys_of(pick) if k in EVIDENCE_CATALYST_KEYS)

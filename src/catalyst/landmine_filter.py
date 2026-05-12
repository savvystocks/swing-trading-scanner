from datetime import datetime, timedelta


def scan_landmines(candidate):
    flags = []
    raw = candidate.get("_raw_fundamentals") or {}
    general = raw.get("General") or {}
    highlights = raw.get("Highlights") or {}
    description = (general.get("Description") or "").lower()
    catalysts = candidate.get("catalysts") or []
    catalyst_keys = {c.get("key") for c in catalysts if isinstance(c, dict)}
    news_headlines = (candidate.get("news") or {}).get("headlines") or []
    headlines_text = " ".join((h.get("title") or "").lower() for h in news_headlines)
    risk_audit = candidate.get("risk_audit") or {}
    audit_flags = risk_audit.get("flags") or []

    if any("going concern" in description for _ in [1]) or any(f.get("label", "").lower().find("going concern") >= 0 for f in audit_flags):
        flags.append({"code": "going_concern", "severity": "RED", "label": "Going concern disclosure"})

    if "atm offering" in headlines_text or "shelf registration" in headlines_text or "secondary offering" in headlines_text or "pipe financing" in headlines_text:
        flags.append({"code": "dilution_recent", "severity": "RED", "label": "Recent ATM/S-3/PIPE dilution"})

    if "s-3" in catalyst_keys or "424b5" in catalyst_keys or "424B5" in headlines_text.upper():
        flags.append({"code": "shelf_filed", "severity": "RED", "label": "Active shelf registration"})

    if "class action" in headlines_text or "securities lawsuit" in headlines_text or "shareholder lawsuit" in headlines_text:
        flags.append({"code": "litigation", "severity": "YELLOW", "label": "Active class action / lawsuit"})

    if "sec investigation" in headlines_text or "doj investigation" in headlines_text or "subpoena" in headlines_text or "ftc complaint" in headlines_text:
        flags.append({"code": "regulatory_investigation", "severity": "RED", "label": "DOJ/SEC/FTC investigation"})

    if "cfo resign" in headlines_text or "cfo depart" in headlines_text or "chief financial officer resign" in headlines_text or "auditor change" in headlines_text or "audit change" in headlines_text:
        flags.append({"code": "exec_or_auditor_turmoil", "severity": "RED", "label": "CFO departure or auditor change"})

    if "nt 10-k" in headlines_text or "nt 10-q" in headlines_text or "filing delay" in headlines_text or "filing extension" in headlines_text:
        flags.append({"code": "filing_delay", "severity": "RED", "label": "NT 10-K / 10-Q filing delay"})

    pct_off_low = candidate.get("pct_off_52w_low")
    if pct_off_low is not None and pct_off_low < 10:
        flags.append({"code": "near_52w_low", "severity": "YELLOW", "label": f"Within {pct_off_low:.0f}% of 52w low"})

    insider_sells = (candidate.get("insider_depth") or {}).get("recent_sells_count")
    if insider_sells and insider_sells >= 3:
        flags.append({"code": "insider_sell_cluster", "severity": "YELLOW", "label": f"{insider_sells} insider sellers in last 60d"})

    if "deal_closed" in catalyst_keys or candidate.get("deal_closed"):
        flags.append({"code": "deal_closed", "severity": "RED", "label": "M&A deal already closed - no trade"})

    if "crl" in headlines_text or "complete response letter" in headlines_text or "fda rejection" in headlines_text:
        flags.append({"code": "fda_crl", "severity": "RED", "label": "FDA CRL or rejection"})

    if "goodwill impairment" in headlines_text or "impairment charge" in headlines_text:
        flags.append({"code": "goodwill_impairment", "severity": "YELLOW", "label": "Recent goodwill impairment"})

    return flags


def passes_landmine_filter(candidate):
    flags = scan_landmines(candidate)
    candidate["_landmine_flags"] = flags
    red_count = sum(1 for f in flags if f["severity"] == "RED")
    yellow_count = sum(1 for f in flags if f["severity"] == "YELLOW")
    candidate["_landmine_red"] = red_count
    candidate["_landmine_yellow"] = yellow_count
    return red_count == 0 and yellow_count < 2


def filter_landmines(candidates, verbose=False):
    passed = []
    rejected = []
    for s in candidates:
        if passes_landmine_filter(s):
            passed.append(s)
        else:
            rejected.append(s)
    if verbose:
        print(f"  landmine filter: {len(passed)} passed, {len(rejected)} rejected")
    return passed, rejected

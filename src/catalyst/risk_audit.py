import re
from datetime import datetime, timedelta

CLASS_ACTION_PATTERNS = [
    r"\bclass action\b", r"\bsecurities fraud\b", r"\bsecurities litigation\b",
    r"\bshareholder lawsuit\b", r"\binvestor lawsuit\b",
    r"\bROSEN\b", r"\bFaruqi\b", r"\bGlancy Prongay\b",
]
SEC_ENFORCEMENT_PATTERNS = [
    r"\bSEC investigation\b", r"\bSEC subpoena\b", r"\bSEC enforcement\b",
    r"\bSEC charges\b", r"\bDOJ investigation\b",
]
AUDIT_FLAG_PATTERNS = [
    r"\bauditor resignation\b", r"\bchange.*auditor\b", r"\binternal control.*material weakness\b",
    r"\brestatement\b", r"\bgoing concern\b", r"\bsubstantial doubt\b",
]
REVERSE_SPLIT_PATTERNS = [
    r"\breverse stock split\b", r"\breverse split\b",
    r"\b1-for-(\d+)\b", r"\b(\d+)-for-1 reverse\b",
]
HFCAA_PATTERNS = [
    r"\bHFCAA\b", r"\bHolding Foreign Companies Accountable\b",
    r"\bPCAOB.*denied\b", r"\bdelisting risk\b",
]

DEAL_CLOSED_PATTERNS = [
    r"\bcompletion of (the )?acquisition\b",
    r"\bacquisition (has )?closed\b",
    r"\bmerger (has )?closed\b",
    r"\btransaction (has )?closed\b",
    r"\bdeal (has )?closed\b",
    r"\bclosing of (the )?merger\b",
    r"\bclosing of (the )?acquisition\b",
    r"\bclosing of (the )?transaction\b",
    r"\bsuccessfully completed\b",
    r"\bdeal completion\b",
    r"\bclosed today\b",
]


M_AND_A_CATALYST_KEYS = {"merger", "asset_sale", "definitive_agreement", "merger_cash_buyout"}


def detect_deal_closed(signals, atr_pct, news_headlines):
    has_ma_catalyst = False
    if signals:
        for s in signals:
            if s.get("key") in M_AND_A_CATALYST_KEYS:
                has_ma_catalyst = True
                break

    if not has_ma_catalyst:
        return None

    headline_blob = " ".join(
        f"{h.get('title','')} {h.get('content','')}"
        for h in (news_headlines or [])
    )
    headline_match = _scan_text(headline_blob, DEAL_CLOSED_PATTERNS)

    atr_locked = atr_pct is not None and atr_pct < 0.7

    if headline_match and atr_locked:
        return {
            "deal_closed": True,
            "reason": f"M&A catalyst + locked ATR {atr_pct:.2f}% + news mentions completion",
            "severity": "HIGH",
        }
    if atr_locked:
        return {
            "deal_closed": True,
            "reason": f"M&A catalyst + locked ATR {atr_pct:.2f}% (price frozen at deal close price)",
            "severity": "HIGH",
        }
    if headline_match:
        return {
            "deal_closed": True,
            "reason": "M&A catalyst + news mentions deal completion",
            "severity": "MEDIUM",
        }
    return None


def _scan_text(text, patterns):
    if not text:
        return False
    text_lower = text.lower()
    for p in patterns:
        if re.search(p, text_lower, re.IGNORECASE):
            return True
    return False


def audit_risks(fundamentals, news_headlines, signals=None):
    flags = []
    severity = 0

    general = (fundamentals or {}).get("General") or {}
    description = (general.get("Description") or "")
    if _scan_text(description, AUDIT_FLAG_PATTERNS):
        if "going concern" in description.lower() or "substantial doubt" in description.lower():
            flags.append({"key": "going_concern", "severity": "HIGH", "label": "Going-concern language in filings"})
            severity += 8
        else:
            flags.append({"key": "audit_concern", "severity": "MEDIUM", "label": "Auditor / restatement issue mentioned"})
            severity += 4

    filings = (fundamentals or {}).get("Filings", {}).get("Last_Filings") or []
    if isinstance(filings, list):
        cutoff = datetime.utcnow().date() - timedelta(days=90)
        for f in filings:
            form = (f.get("type") or "").upper()
            date_str = f.get("date") or ""
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if d >= cutoff and form in ("S-3", "S-3/A", "424B5", "424B3"):
                flags.append({"key": "recent_shelf", "severity": "MEDIUM", "label": f"Recent shelf/offering ({form} on {date_str})"})
                severity += 4
                break

    headline_blob = " ".join(
        f"{h.get('title','')} {h.get('content','')}"
        for h in (news_headlines or [])
    )

    if _scan_text(headline_blob, CLASS_ACTION_PATTERNS):
        flags.append({"key": "class_action", "severity": "HIGH", "label": "Securities class action / lawsuit"})
        severity += 6
    if _scan_text(headline_blob, SEC_ENFORCEMENT_PATTERNS):
        flags.append({"key": "sec_action", "severity": "HIGH", "label": "SEC / DOJ action mentioned"})
        severity += 8
    if _scan_text(headline_blob, REVERSE_SPLIT_PATTERNS):
        flags.append({"key": "reverse_split", "severity": "HIGH", "label": "Reverse split (often pre-dilution)"})
        severity += 6
    if _scan_text(headline_blob, HFCAA_PATTERNS):
        flags.append({"key": "hfcaa", "severity": "HIGH", "label": "HFCAA / PCAOB delisting risk"})
        severity += 6

    address = general.get("AddressData") or {}
    country = (address.get("Country") or general.get("CountryName") or "").lower()
    if "china" in country or "hong kong" in country or "hk" in country:
        flags.append({"key": "china_jurisdiction", "severity": "LOW", "label": "China-based issuer (regulatory tail risk)"})
        severity += 2

    market_cap = (fundamentals or {}).get("Highlights", {}).get("MarketCapitalization")
    if market_cap and market_cap < 30_000_000:
        flags.append({"key": "ultra_micro_cap", "severity": "MEDIUM", "label": f"Ultra micro-cap (${market_cap/1e6:.0f}M)"})
        severity += 3

    severity = min(severity, 20)
    return {
        "flags": flags,
        "severity_score": severity,
        "penalty_points": -severity,
        "high_severity_count": sum(1 for f in flags if f["severity"] == "HIGH"),
    }

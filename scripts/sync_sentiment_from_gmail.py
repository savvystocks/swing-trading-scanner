"""Sync AAII / NAAIM / Investors Intelligence sentiment from Gmail subscription emails.

How to use:

1. Subscribe to the free weekly emails:
   - AAII: https://www.aaii.com/free (the AAII Sentiment Survey email)
   - NAAIM: https://www.naaim.org/ (subscribe to NAAIM Exposure Index updates)

2. Set up a Gmail filter (Settings -> Filters and Blocked Addresses -> Create a new filter):
   - From: contains "@aaii.com OR @naaim.org"
   - Apply label: "sentiment-data"

3. Set env vars (same Gmail account as scan emails):
   - GMAIL_USER = savvastgeorgiou@gmail.com
   - GMAIL_APP_PASSWORD = (same app password used by send_email)

4. Run weekly via cron or manually:
   python scripts/sync_sentiment_from_gmail.py

The script polls the "sentiment-data" label, parses AAII bull/bear/neutral percentages
and NAAIM exposure index values, then writes data/sentiment/aaii_naaim.json. The
sentiment_stack module reads this JSON automatically on the next scan.

If running fails, the scanner falls back to the existing JSON sidecar (whatever was
last written successfully), so this script is non-blocking.
"""

import os
import sys
import json
import imaplib
import email
import re
import pathlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from email.header import decode_header


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
SIDECAR_PATH = PROJECT_ROOT / "data" / "sentiment" / "aaii_naaim.json"
SIDECAR_PATH.parent.mkdir(parents=True, exist_ok=True)

GMAIL_HOST = "imap.gmail.com"
GMAIL_PORT = 993
SENTIMENT_LABEL = "sentiment-data"


def _decode(s):
    if isinstance(s, bytes):
        try:
            return s.decode("utf-8", errors="replace")
        except Exception:
            return s.decode("latin-1", errors="replace")
    return s


def _connect():
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD must be set")
    imap = imaplib.IMAP4_SSL(GMAIL_HOST, GMAIL_PORT)
    imap.login(user, pw)
    return imap


def _get_message_body(msg):
    """Return plain-text and html body parts as a single string."""
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(_decode(payload))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            parts.append(_decode(payload))
    return "\n\n".join(parts)


def _parse_aaii(subject, body):
    """Extract bullish/bearish/neutral percentages from AAII email body."""
    text = (subject or "") + "\n" + (body or "")

    bull_m = re.search(r"Bullish[^0-9%]*?([0-9]+\.?[0-9]*)\s*%", text, re.IGNORECASE)
    bear_m = re.search(r"Bearish[^0-9%]*?([0-9]+\.?[0-9]*)\s*%", text, re.IGNORECASE)
    neut_m = re.search(r"Neutral[^0-9%]*?([0-9]+\.?[0-9]*)\s*%", text, re.IGNORECASE)

    if not (bull_m and bear_m):
        return None

    try:
        bull = float(bull_m.group(1))
        bear = float(bear_m.group(1))
        neut = float(neut_m.group(1)) if neut_m else round(100 - bull - bear, 1)
    except (TypeError, ValueError):
        return None

    if not (0 <= bull <= 100 and 0 <= bear <= 100):
        return None

    week_m = re.search(r"week\s+end(?:ing|ed)[^0-9]*?([A-Za-z]+\s+[0-9]{1,2},?\s*[0-9]{4})", text, re.IGNORECASE)
    week_ending = None
    if week_m:
        try:
            week_ending = datetime.strptime(week_m.group(1).replace(",", ""), "%B %d %Y").date().isoformat()
        except Exception:
            week_ending = None

    return {
        "bullish": bull,
        "bearish": bear,
        "neutral": neut,
        "week_ending": week_ending,
    }


def _parse_naaim(subject, body):
    """Extract NAAIM exposure index value from email body."""
    text = (subject or "") + "\n" + (body or "")
    m = re.search(r"(?:exposure\s+index|naaim[^\n]*?index)[^0-9]*?([0-9]+\.?[0-9]*)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"reading[^0-9]*?([0-9]+\.?[0-9]*)", text, re.IGNORECASE)
    if m:
        try:
            value = float(m.group(1))
            if 0 <= value <= 200:
                week_m = re.search(r"week[^0-9]*?([A-Za-z]+\s+[0-9]{1,2},?\s*[0-9]{4})", text, re.IGNORECASE)
                week_ending = None
                if week_m:
                    try:
                        week_ending = datetime.strptime(week_m.group(1).replace(",", ""), "%B %d %Y").date().isoformat()
                    except Exception:
                        pass
                return {"exposure_pct": value, "week_ending": week_ending}
        except (TypeError, ValueError):
            pass
    return None


def _parse_ii(subject, body):
    """Extract Investors Intelligence bull/bear percentages."""
    text = (subject or "") + "\n" + (body or "")
    bull_m = re.search(r"bull(?:s|ish)?[^0-9%]*?([0-9]+\.?[0-9]*)\s*%", text, re.IGNORECASE)
    bear_m = re.search(r"bear(?:s|ish)?[^0-9%]*?([0-9]+\.?[0-9]*)\s*%", text, re.IGNORECASE)
    if bull_m and bear_m:
        try:
            return {
                "bull_pct": float(bull_m.group(1)),
                "bear_pct": float(bear_m.group(1)),
                "week_ending": None,
            }
        except (TypeError, ValueError):
            pass
    return None


def sync(verbose=True):
    aaii_data = None
    naaim_data = None
    ii_data = None

    try:
        imap = _connect()
    except Exception as e:
        if verbose:
            print(f"  gmail connect failed: {type(e).__name__}: {e}")
        return False

    try:
        try:
            imap.select(f'"{SENTIMENT_LABEL}"')
        except Exception:
            imap.select("INBOX")

        # Pull last 60 days of relevant senders
        typ, data = imap.search(None, '(SINCE "01-Apr-2026" FROM "aaii.com")')
        aaii_ids = data[0].split() if typ == "OK" else []

        typ, data = imap.search(None, '(SINCE "01-Apr-2026" FROM "naaim.org")')
        naaim_ids = data[0].split() if typ == "OK" else []

        typ, data = imap.search(None, '(SINCE "01-Apr-2026" SUBJECT "Investors Intelligence")')
        ii_ids = data[0].split() if typ == "OK" else []

        aaii_ids.sort(reverse=True)
        naaim_ids.sort(reverse=True)
        ii_ids.sort(reverse=True)

        for mid in aaii_ids[:5]:
            typ, msg_data = imap.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subj = _decode(decode_header(msg.get("Subject") or "")[0][0])
            body = _get_message_body(msg)
            parsed = _parse_aaii(subj, body)
            if parsed:
                aaii_data = parsed
                if verbose:
                    print(f"  AAII parsed from email: bull {parsed['bullish']}% bear {parsed['bearish']}% week {parsed.get('week_ending')}")
                break

        for mid in naaim_ids[:5]:
            typ, msg_data = imap.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subj = _decode(decode_header(msg.get("Subject") or "")[0][0])
            body = _get_message_body(msg)
            parsed = _parse_naaim(subj, body)
            if parsed:
                naaim_data = parsed
                if verbose:
                    print(f"  NAAIM parsed from email: exposure {parsed['exposure_pct']}% week {parsed.get('week_ending')}")
                break

        for mid in ii_ids[:5]:
            typ, msg_data = imap.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subj = _decode(decode_header(msg.get("Subject") or "")[0][0])
            body = _get_message_body(msg)
            parsed = _parse_ii(subj, body)
            if parsed:
                ii_data = parsed
                if verbose:
                    print(f"  II parsed from email: bull {parsed['bull_pct']}% bear {parsed['bear_pct']}%")
                break

    finally:
        try:
            imap.logout()
        except Exception:
            pass

    # Merge with existing sidecar (preserve last known if not in new fetch)
    existing = {}
    if SIDECAR_PATH.exists():
        try:
            with open(SIDECAR_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    out = dict(existing) if isinstance(existing, dict) else {}
    if aaii_data:
        out["aaii"] = aaii_data
    if naaim_data:
        out["naaim"] = naaim_data
    if ii_data:
        out["investors_intelligence"] = ii_data
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    out["source"] = "gmail_filter"

    with open(SIDECAR_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    if verbose:
        print(f"  sidecar updated: {SIDECAR_PATH}")
        print(f"    aaii: {'OK' if aaii_data else 'missing (kept previous)'}")
        print(f"    naaim: {'OK' if naaim_data else 'missing (kept previous)'}")
        print(f"    ii: {'OK' if ii_data else 'missing (kept previous)'}")

    return bool(aaii_data or naaim_data or ii_data)


if __name__ == "__main__":
    ok = sync(verbose=True)
    sys.exit(0 if ok else 1)

"""Sync real Robinhood option fills from confirmation emails into the truth file.

Reads "Option order executed" emails from Gmail (same account + app password the
scanner already uses), parses each fill, and reconciles it into
data/paper_trades/live_positions.json so the monitor, email panel, and P&L are
backed by what actually filled - not what was hand-typed.

No Robinhood login, no credentials beyond Gmail read access. Runs anywhere the
GMAIL_APP_PASSWORD is available (locally or in CI).

  Dry run (parse + report, write nothing):
    python scripts/sync_robinhood_fills.py --dry

  Real run (updates the truth files):
    python scripts/sync_robinhood_fills.py

Dedup is by email Message-ID in data/paper_trades/processed_fills.json, so it is
safe to run repeatedly.
"""

import os
import sys
import json
import imaplib
import email
import pathlib
from datetime import datetime, timezone, timedelta
from email.header import decode_header

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.fills_ledger import parse_fill_email, apply_fill


PROJECT_ROOT = pathlib.Path(__file__).parent.parent
LIVE_PATH = PROJECT_ROOT / "data" / "paper_trades" / "live_positions.json"
ARCHIVE_PATH = PROJECT_ROOT / "data" / "paper_trades" / "closed_positions.json"
PROCESSED_PATH = PROJECT_ROOT / "data" / "paper_trades" / "processed_fills.json"

GMAIL_HOST = "imap.gmail.com"
GMAIL_PORT = 993
LOOKBACK_DAYS = int(os.environ.get("RH_FILL_LOOKBACK_DAYS", "90"))


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
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(_decode(payload))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            parts.append(_decode(payload))
    return "\n\n".join(parts)


def _load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def fetch_fills(verbose=True):
    imap = _connect()
    fills = []
    try:
        imap.select("INBOX")
        since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%d-%b-%Y")
        typ, data = imap.search(None, f'(SINCE "{since}" FROM "robinhood")')
        ids = data[0].split() if typ == "OK" else []
        if verbose:
            print(f"  {len(ids)} Robinhood emails since {since}")
        for mid in ids:
            typ, msg_data = imap.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subj = _decode(decode_header(msg.get("Subject") or "")[0][0])
            body = _get_message_body(msg)
            fill = parse_fill_email(subj + "\n" + body)
            if not fill:
                continue
            fill["message_id"] = (msg.get("Message-ID") or "").strip() or f"noid-{mid.decode()}"
            fills.append(fill)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    fills.sort(key=lambda f: (f.get("filled_date") or "", f.get("filled_time") or ""))
    return fills


def main():
    dry = "--dry" in sys.argv[1:] or os.environ.get("DRY_RUN") == "1"
    seed = "--seed" in sys.argv[1:] or os.environ.get("SEED") == "1"
    tag = "[DRY RUN] " if dry else ""
    mode = "seed (mark existing as done)" if seed else "sync"
    print(f"{tag}Robinhood fill {mode} (lookback {LOOKBACK_DAYS}d)")

    try:
        fills = fetch_fills(verbose=True)
    except Exception as e:
        print(f"  gmail/fetch failed: {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"  {len(fills)} option fills parsed")

    positions = _load(LIVE_PATH, [])
    archive = _load(ARCHIVE_PATH, [])
    state = _load(PROCESSED_PATH, {})
    processed = set(state.get("processed") or [])
    unmatched = list(state.get("unmatched") or [])

    if seed:
        new_ids = [f["message_id"] for f in fills if f["message_id"] not in processed]
        for f in fills:
            processed.add(f["message_id"])
        print(f"  seeding {len(new_ids)} existing fills as already-processed (no backfill)")
        if dry:
            print("\n[DRY RUN] nothing written.")
            return
        _save(PROCESSED_PATH, {
            "processed": sorted(processed),
            "unmatched": unmatched,
            "last_run": datetime.now(timezone.utc).isoformat(),
            "seeded_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"\n  wrote {PROCESSED_PATH.name} - only new fills from here will be logged")
        return

    applied = 0
    for f in fills:
        if f["message_id"] in processed:
            continue
        positions, archive, msg = apply_fill(positions, archive, f)
        print(f"  {f.get('filled_date')} {f['action']:4} {msg}")
        if msg.startswith("UNMATCHED"):
            unmatched.append({**f, "noted_at": datetime.now(timezone.utc).isoformat()})
        processed.add(f["message_id"])
        applied += 1

    open_pos = [p for p in positions if p.get("status") == "OPEN"]
    print(f"\n  {applied} new fills applied. Open positions now: {len(open_pos)}")
    for p in open_pos:
        print(f"    {p['ticker']:6} {p['side']:4} ${p.get('strike')} x{p.get('contracts')} @ ${p.get('entry_price')}")

    if dry:
        print("\n[DRY RUN] nothing written. Re-run without --dry to commit.")
        return

    _save(LIVE_PATH, positions)
    _save(ARCHIVE_PATH, archive)
    _save(PROCESSED_PATH, {
        "processed": sorted(processed),
        "unmatched": unmatched,
        "last_run": datetime.now(timezone.utc).isoformat(),
    })
    print(f"\n  wrote {LIVE_PATH.name}, {ARCHIVE_PATH.name}, {PROCESSED_PATH.name}")


if __name__ == "__main__":
    main()

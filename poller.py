import os
import sys
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone

import harvest_db as db
from harvest_labeler import label_path

CHUNK = 100
STALE_MS = 15 * 60 * 1000
CENSOR_GRACE_MS = 24 * 60 * 60 * 1000


def _now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _paper_creds():
    return os.environ.get("ALPACA_PAPER_API_KEY"), os.environ.get("ALPACA_PAPER_SECRET_KEY")


def _market_open_today():
    try:
        import pandas_market_calendars as mcal
        d = datetime.now(timezone.utc).date().isoformat()
        sched = mcal.get_calendar("XNYS").schedule(start_date=d, end_date=d)
        return not sched.empty
    except Exception:
        return datetime.now(timezone.utc).weekday() < 5


def _fetch_alpaca(symbols, creds):
    out = {}
    if not all(creds) or not symbols:
        return out
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionLatestQuoteRequest
        cli = OptionHistoricalDataClient(creds[0], creds[1])
    except Exception:
        return out
    now = _now_ms()
    for i in range(0, len(symbols), CHUNK):
        chunk = symbols[i:i + CHUNK]
        for attempt in range(3):
            try:
                q = cli.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=chunk))
                for sym, quote in (q or {}).items():
                    ts = getattr(quote, "timestamp", None)
                    qms = int(ts.timestamp() * 1000) if ts else now
                    out[sym] = {"bid": getattr(quote, "bid_price", None), "ask": getattr(quote, "ask_price", None),
                                "quote_ts": qms, "stale": (now - qms) > STALE_MS}
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                break
    return out


def _fetch_uw(symbols):
    out = {}
    try:
        from src.unusual_whales_api import UnusualWhalesClient
        uw = UnusualWhalesClient()
        if not getattr(uw, "enabled", False):
            return out
        now = _now_ms()
        tickers = set()
        for s in symbols:
            i = 0
            while i < len(s) and not s[i].isdigit():
                i += 1
            tickers.add(s[:i])
        for tk in tickers:
            rows = (uw.flow_alerts(ticker=tk, limit=200) or {}).get("data") or []
            for r in rows:
                from harvest_logger import _occ_symbol, _f
                occ = _occ_symbol(r.get("ticker"), r.get("expiry"), r.get("strike"),
                                  "call" if str(r.get("type") or "").lower().startswith("c") else "put")
                if occ in symbols and occ not in out:
                    out[occ] = {"bid": _f(r.get("bid")), "ask": _f(r.get("ask")),
                                "quote_ts": now, "stale": False}
    except Exception:
        return out
    return out


def _poll_now(cand, now):
    tier = cand.get("poll_tier")
    if tier == "none":
        return False
    if tier == "reduced":
        return datetime.now(timezone.utc).minute < 15
    return True


def run_once():
    if not _market_open_today():
        print("market closed today (holiday/weekend) - no polling")
        return
    con = db.init_db()
    new, skipped = db.ingest_inbox(con)
    print(f"ingest: {new} new candidates, {skipped} already present")
    db.backup(keep=14)

    now = _now_ms()
    creds = _paper_creds()
    opens = db.open_candidates(con)
    due = [c for c in opens if _poll_now(c, now)]
    print(f"open candidates: {len(opens)} ({len(due)} due this run)")
    if not due:
        _maybe_email(con)
        return

    symbols = sorted({c["occ_symbol"] for c in due})
    quotes = _fetch_alpaca(symbols, creds)
    missing = [s for s in symbols if s not in quotes]
    if missing:
        quotes.update(_fetch_uw(missing))
    print(f"quotes: {len(quotes)}/{len(symbols)} resolved ({'alpaca+uw' if missing else 'alpaca'})")

    resolved = {"up": 0, "down": 0, "vertical": 0, "censored": 0, "open": 0}
    for c in due:
        occ = c["occ_symbol"]
        q = quotes.get(occ)
        if q is None:
            db.append_bid_path(con, c["candidate_id"], now, None, None, None, True)
        else:
            db.append_bid_path(con, c["candidate_id"], now, q["bid"], q["ask"], q["quote_ts"], q["stale"])
        path = db.get_path(con, c["candidate_id"])
        res = label_path(c["entry_ref"], c["barrier_up_pct"], c["barrier_down_pct"],
                         c["vertical_barrier_ts"], c["signal_ts_utc"], path)
        cadence = 15.0 if c["poll_tier"] == "standard" else 60.0
        if res["outcome"] != "open":
            db.upsert_label(con, c["candidate_id"], res, poll_cadence_min=cadence)
            resolved[res["outcome"]] += 1
        elif now > c["vertical_barrier_ts"] + CENSOR_GRACE_MS:
            reason = "no_fresh_quote_at_vertical" if res["n_stale"] else "unresolved_past_vertical"
            db.upsert_label(con, c["candidate_id"], {**res, "outcome": "censored", "label": None},
                            poll_cadence_min=cadence, censored_reason=reason)
            resolved["censored"] += 1
        else:
            resolved["open"] += 1
    print(f"resolved: {resolved}")
    _maybe_email(con, resolved)


def _maybe_email(con, resolved=None):
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        return
    try:
        row = con.execute("SELECT COUNT(*) FROM candidates c LEFT JOIN labels l ON c.candidate_id=l.candidate_id "
                          "WHERE l.candidate_id IS NULL AND c.poll_tier!='none'").fetchone()
        labeled = con.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
        stale_rows = con.execute("SELECT COALESCE(SUM(stale),0), COUNT(*) FROM bid_path").fetchone()
        stale_rate = round((stale_rows[0] or 0) / stale_rows[1] * 100, 1) if stale_rows[1] else 0.0
        body = (f"Harvest poller summary {datetime.now(timezone.utc).isoformat()}\n"
                f"open candidates: {row[0]}\nlabeled total: {labeled}\n"
                f"this run: {resolved}\nstale-quote rate: {stale_rate}%")
        msg = MIMEText(body)
        msg["Subject"] = "Harvest poller daily summary"
        msg["From"] = user
        msg["To"] = user
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pw)
            s.sendmail(user, [user], msg.as_string())
    except Exception:
        pass


if __name__ == "__main__":
    if "--once" in sys.argv or len(sys.argv) == 1:
        run_once()
    else:
        print("usage: poller.py --once")

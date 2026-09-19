"""XSP QUOTE LOG (owner order 2026-09-19). PASSIVE: reads quotes, places nothing, touches no record.

WHY. CREDIT_SPREAD_W trades XSP, but every backtest ever made for it - the shipped +$2,302 and the
2026-09-17 executable-NBBO rebuild - priced SPY. XSP is SPX/10, the same price level as SPY, so a
spread is the same notional; what differs is how wide XSP quotes are. The book never closes, so the
only friction it pays is at ENTRY: it sells the short put at the bid and buys the long put at the ask.

WHAT. Twice a weekday (15:05 UTC, the book's own entry window, and 19:50 UTC) it builds the legs the
book WOULD trade today - same spot source, same strike arithmetic, same expiry rule, same
`fivek_probes._quote` call and therefore the same INDICATIVE feed the engine sees - for XSP and for
the matched SPY strikes at the same instant, and logs bid/ask on all four legs. If a CREDIT_SPREAD_W
record is OPEN it also logs that record's own two legs (what a unit close would cost now).

DECISION RULE, fixed before any row exists. Per snapshot:
    friction = credit at mid - credit executable (short bid - long ask), in dollars per spread
    excess   = XSP friction - SPY friction
The SPY-basis expectation for this book is about $20-26 a week per spread. After four weeks, on the
median ENTRY-WINDOW excess, with weeks (not snapshots) as the unit of evidence:
    excess <= $5   the SPY backtests transfer to XSP; the instrument is not the problem
    $5 to $20      haircut the expectation by that much; the book is thinner than its backtest
    excess >= $20  XSP's own spread consumes the edge; the book is not alive on this instrument
Caveat carried in every row: the feed is Alpaca `indicative`, not OPRA NBBO. It is what the engine
acts on; it is not proof of where a real order would fill.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
DURABLE = os.path.expanduser("~/xsp_quotes.jsonl")      # outside the tree: the 15-minute reset cannot take it
TRACKED = os.path.join("reports", "research", "xsp_quotes.jsonl")


def _last(sym):
    import yfinance as yf
    s = yf.download(sym, period="5d", progress=False, auto_adjust=True)["Close"].dropna()
    s = s.iloc[:, 0] if hasattr(s, "columns") else s
    return float(s.iloc[-1])


def _side(root, exp, k, quote, creds):
    occ = f"{root}{exp.strftime('%y%m%d')}P{int(round(k * 1000)):08d}"
    bid, ask = quote(occ, creds)
    return {"occ": occ, "k": k, "bid": bid, "ask": ask}


def _spread(short, long_):
    sb, sa, lb, la = short["bid"], short["ask"], long_["bid"], long_["ask"]
    if None in (sb, sa, lb, la) or sa <= 0 or la <= 0:
        return {"credit_exec": None, "credit_mid": None, "friction_usd": None}
    ex = sb - la
    mid = (sb + sa) / 2.0 - (lb + la) / 2.0
    return {"credit_exec": round(ex, 4), "credit_mid": round(mid, 4), "friction_usd": round((mid - ex) * 100, 2)}


def snapshot(kind, creds, quote, cfg, now=None, last=_last):
    now = now or datetime.now(timezone.utc)
    exp = now.date() + timedelta(days=(4 - now.date().weekday()) % 7)     # fivek_probes._enter, verbatim
    if exp <= now.date():
        exp += timedelta(days=7)
    o_s, o_l = cfg.get("otm_short", 2.0), cfg.get("otm_long", 4.0)
    row = {"ts_utc": now.isoformat(), "kind": kind, "feed": "indicative", "expiry": exp.isoformat(),
           "otm_short": o_s, "otm_long": o_l}
    for root, sym in (("XSP", "^XSP"), ("SPY", "SPY")):
        try:
            spot = last(sym)
            sh = _side(root, exp, round(spot * (1 - o_s / 100)), quote, creds)
            lg = _side(root, exp, round(spot * (1 - o_l / 100)), quote, creds)
            row[root.lower()] = {"spot": round(spot, 2), "short": sh, "long": lg, **_spread(sh, lg)}
        except Exception as e:
            row[root.lower()] = {"error": f"{type(e).__name__}: {e}"[:120]}
    fx, fs = (row.get("xsp") or {}).get("friction_usd"), (row.get("spy") or {}).get("friction_usd")
    row["excess_friction_usd"] = round(fx - fs, 2) if fx is not None and fs is not None else None
    return row


def held_legs(creds, quote):
    """The OPEN credit spread's own legs, read-only from the record book the poller mirrors."""
    try:
        log = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
        recs = log if isinstance(log, list) else log.get("records", [])
        r = [x for x in recs if x.get("probe_strategy") == "CREDIT_SPREAD_W" and x.get("status") == "OPEN"][-1]
        st = r["structure"]
        out = {"entry_credit": r.get("net_credit"), "expiry": r.get("expiry")}
        for name in ("short", "long"):
            occ = st[name][0]["occ"]
            b, a = quote(occ, creds)
            out[name] = {"occ": occ, "entry_prem": st[name][0]["prem"], "bid": b, "ask": a}
        sa, lb = out["short"]["ask"], out["long"]["bid"]
        out["unit_close_cost"] = round(sa - lb, 4) if sa is not None and lb is not None else None
        return out
    except Exception:
        return None


def _publish():
    try:
        os.makedirs(os.path.dirname(TRACKED), exist_ok=True)
        with open(DURABLE, encoding="utf-8") as src, open(TRACKED, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        subprocess.run(f"git add -f {TRACKED} && git commit -qm 'xsp quote log [skip ci]' && "
                       "(git pull -q --rebase --autostash -X ours || (sleep 20 && git pull -q --rebase --autostash -X ours)) "
                       "&& git push -q", shell=True, timeout=180)
    except Exception as e:
        print(f"publish failed open: {type(e).__name__}: {e}")


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else "entry_window"
    dry = "--dry" in sys.argv
    creds = (os.environ.get("ALPACA_PAPER_API_KEY", ""), os.environ.get("ALPACA_PAPER_SECRET_KEY", ""))
    if not all(creds):
        print("xsp quote log: no Alpaca creds in the environment - nothing logged")
        return
    import fivek_probes
    cfg = (fivek_probes._cfg().get("credit_spread") or {})
    row = snapshot(kind, creds, fivek_probes._quote, cfg)
    row["held"] = held_legs(creds, fivek_probes._quote)
    line = json.dumps(row)
    if dry:
        print(json.dumps(row, indent=1))
        return
    with open(DURABLE, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    x, s_ = row.get("xsp") or {}, row.get("spy") or {}
    print(f"{row['ts_utc'][:16]} {kind}: XSP friction ${x.get('friction_usd')} on credit {x.get('credit_exec')} | "
          f"SPY friction ${s_.get('friction_usd')} on credit {s_.get('credit_exec')} | excess ${row['excess_friction_usd']}")
    _publish()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                     # a measurement job never pages and never raises
        print(f"xsp quote log failed open: {type(e).__name__}: {e}")

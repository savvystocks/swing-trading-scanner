"""WHAT THE CREDIT SPREAD REALLY COLLECTED. The book records the quote it AIMED at (`net_credit`, from the indicative
feed); the broker knows the price it GOT. Read-only: for every CREDIT_SPREAD_W record, fetch each leg's filled order
from the paper account and write quoted-vs-filled credit to reports/research/cs_live_fills.json. `fill_vs_quote_usd`
is per spread and POSITIVE when the broker paid more credit than the quote aimed at. These are PAPER fills: the
simulator fills at or inside the quote, so this bounds the book-keeping error, not what a live market would pay. Never
places, cancels or changes an order; never touches the engine's records. Off the trade path entirely."""
import json
import os
import subprocess
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
DURABLE = os.path.expanduser("~/cs_live_fills.json")
TRACKED = "reports/research/cs_live_fills.json"
BASE = "https://paper-api.alpaca.markets/v2/orders?status=closed&limit=50&direction=desc&symbols="


def closed_orders(occ, creds):
    h = {"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]}
    with urllib.request.urlopen(urllib.request.Request(BASE + occ, headers=h), timeout=20) as r:
        return json.loads(r.read())


def entry_fill(orders, side, entry_ts):
    """The filled order on the opening side closest to the record's entry time; None when the broker has none."""
    day = (entry_ts or "")[:10]
    hits = [o for o in orders if o.get("side") == side and o.get("filled_avg_price") and float(o.get("filled_qty") or 0) > 0
            and (not day or (o.get("filled_at") or "")[:10] == day)]
    if not hits:
        return None
    o = hits[-1]
    return {"limit": float(o["limit_price"]) if o.get("limit_price") else None, "filled": float(o["filled_avg_price"]),
            "qty": float(o["filled_qty"]), "filled_at": (o.get("filled_at") or "")[:19]}


def measure(rec, fetch):
    st = rec.get("structure") or {}
    legs, ok = [], True
    for side, key in (("sell", "short"), ("buy", "long")):
        for leg in st.get(key) or []:
            f = entry_fill(fetch(leg["occ"]), side, rec.get("entry_ts_utc"))
            ok = ok and f is not None
            legs.append({"occ": leg["occ"], "side": side, "quoted": leg.get("prem"), "fill": f})
    row = {"trade_set_id": rec.get("trade_set_id"), "entry_ts_utc": rec.get("entry_ts_utc"), "expiry": rec.get("expiry"),
           "status": rec.get("status"), "quoted_credit": rec.get("net_credit"), "legs": legs, "filled_credit": None, "fill_vs_quote_usd": None}
    if ok and legs:
        got = sum(l["fill"]["filled"] * (1 if l["side"] == "sell" else -1) for l in legs)
        row["filled_credit"] = round(got, 4)
        if rec.get("net_credit") is not None:
            row["fill_vs_quote_usd"] = round((got - float(rec["net_credit"])) * 100, 2)
    pnl = (rec.get("settle") or {}).get("pnl_usd")
    if pnl is not None and row["fill_vs_quote_usd"] is not None:
        row["booked_pnl_usd"], row["true_pnl_usd"] = pnl, round(pnl + row["fill_vs_quote_usd"], 2)
    return row


def _publish():
    try:
        subprocess.run(f"git add -f {TRACKED} && git commit -qm 'cs live fills [skip ci]' && "
                       "(git pull -q --rebase --autostash -X ours || (sleep 20 && git pull -q --rebase --autostash -X ours)) "
                       "&& git push -q", shell=True, timeout=180)
    except Exception as e:
        print(f"publish failed open: {type(e).__name__}: {e}")


def main():
    import sys
    creds = (os.environ.get("ALPACA_PAPER_API_KEY", ""), os.environ.get("ALPACA_PAPER_SECRET_KEY", ""))
    if not all(creds):
        print("cs live fills: no Alpaca creds in the environment - nothing read")
        return
    log = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
    recs = [r for r in (log if isinstance(log, list) else log.get("records", [])) if r.get("probe_strategy") == "CREDIT_SPREAD_W"]
    rows = [measure(r, lambda occ: closed_orders(occ, creds)) for r in recs]
    seen = [r for r in rows if r["fill_vs_quote_usd"] is not None]
    out = {"ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "records": len(rows), "with_fills": len(seen),
           "mean_fill_vs_quote_usd": round(sum(r["fill_vs_quote_usd"] for r in seen) / len(seen), 2) if seen else None, "rows": rows}
    for r in rows:
        print(f"  {r['expiry']} {r['status']:<7} quoted {r['quoted_credit']} filled {r['filled_credit']} fill vs quote ${r['fill_vs_quote_usd']}")
    print(f"{out['ts_utc'][:16]} cs live fills: {len(seen)}/{len(rows)} records with both fills; mean fill vs quote ${out['mean_fill_vs_quote_usd']} per spread")
    if "--dry" in sys.argv:
        return
    os.makedirs(os.path.dirname(TRACKED), exist_ok=True)
    for path in (DURABLE, TRACKED):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    if "--no-publish" not in sys.argv:
        _publish()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                              # a measurement job never pages and never raises
        print(f"cs live fills failed open: {type(e).__name__}: {e}")

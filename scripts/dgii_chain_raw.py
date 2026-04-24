import os
import re
import subprocess
from datetime import datetime, timedelta

def load_user_env(name):
    r = subprocess.run(
        ["powershell", "-Command", f'[Environment]::GetEnvironmentVariable("{name}","User")'],
        capture_output=True, text=True,
    )
    return (r.stdout or "").strip()

for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
    if not os.environ.get(k):
        v = load_user_env(k)
        if v:
            os.environ[k] = v

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest

SYMBOL = "DGII"
current_price = 55.80

client = OptionHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
today = datetime.now()
min_exp = (today + timedelta(days=14)).strftime("%Y-%m-%d")
max_exp = (today + timedelta(days=70)).strftime("%Y-%m-%d")

req = OptionChainRequest(
    underlying_symbol=SYMBOL,
    expiration_date_gte=min_exp,
    expiration_date_lte=max_exp,
    strike_price_gte=str(round(current_price * 0.80, 2)),
    strike_price_lte=str(round(current_price * 1.25, 2)),
    type="call",
)
snaps = client.get_option_chain(req)
print(f"Chain size: {len(snaps)} contracts, exp window {min_exp} to {max_exp}")

rows = []
for sym, s in snaps.items():
    try:
        m = re.match(r"([A-Z]+)(\d{6})([CP])(\d+)", sym if isinstance(sym, str) else str(sym))
        if not m:
            continue
        exp_raw = m.group(2)
        strike_raw = m.group(4)
        expiration = f"20{exp_raw[:2]}-{exp_raw[2:4]}-{exp_raw[4:6]}"
        strike = int(strike_raw) / 1000
        dte = (datetime.strptime(expiration, "%Y-%m-%d") - datetime.now()).days

        g = s.greeks
        q = s.latest_quote
        t = s.latest_trade

        delta = abs(float(g.delta)) if g and g.delta else None
        theta = float(g.theta) if g and g.theta else None
        iv_val = getattr(s, "implied_volatility", None) or (getattr(g, "implied_volatility", None) if g else None)
        iv = float(iv_val) if iv_val else None

        bid = float(q.bid_price) if q and q.bid_price else 0
        ask = float(q.ask_price) if q and q.ask_price else 0
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
        spread_pct = ((ask - bid) / mid * 100) if mid > 0 else None

        vol = int(t.size) if t and getattr(t, "size", None) else 0

        rows.append({
            "strike": strike, "expiration": expiration, "dte": dte,
            "delta": round(delta, 3) if delta else None,
            "theta": round(theta, 4) if theta else None,
            "iv_pct": round(iv*100, 1) if iv else None,
            "bid": bid, "ask": ask, "mid": round(mid, 2),
            "spread_pct": round(spread_pct, 1) if spread_pct else None,
            "vol_today": vol,
        })
    except Exception as e:
        print(f"  parse fail {sym}: {e}")

rows.sort(key=lambda r: (r["expiration"], r["strike"]))
print(f"\nAll {len(rows)} contracts:")
print(f"{'EXP':12s} {'STRIKE':>7s} {'DTE':>4s} {'DELTA':>6s} {'IV%':>6s} {'BID':>6s} {'ASK':>6s} {'MID':>6s} {'SPR%':>6s} {'VOL':>5s}")
for r in rows:
    print(f"{r['expiration']:12s} {r['strike']:>7.2f} {r['dte']:>4d} "
          f"{(r['delta'] or 0):>6.3f} {(r['iv_pct'] or 0):>6.1f} "
          f"{r['bid']:>6.2f} {r['ask']:>6.2f} {r['mid']:>6.2f} "
          f"{(r['spread_pct'] or 999):>6.1f} {r['vol_today']:>5d}")

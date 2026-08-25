"""REGIME PLAYBOOK (owner order 2026-08-25: separate simulation per market - bull/mild/bear -
best strategies for each, all data, and: are we missing strategies that fit a 5k account?).

Covers what the mega sweep did NOT: the STRUCTURAL (non-flow) strategy families, regime-split,
priced from REAL SPY option quotes in our own 2y archive (nbbo bid/ask, executable convention:
sell at bid, buy at ask), settled against SPY's real close at expiry.

Structures tested per entry-day regime (SPY vs 50d SMA: bull>+2 / bear<-2 / mild between),
one lot, ~weekly expiry (4-6 DTE), all defined-risk and affordable at $1k-$1.5k max loss:
  PUT_CREDIT   short put ~2% OTM / long 4% OTM   (the live CREDIT_SPREAD_W shape)
  CALL_CREDIT  short call ~2% OTM / long 4% OTM  (the MISSING bear-income candidate)
  IRON_CONDOR  both wings
  PUT_DEBIT    long put ~1% OTM / short ~3% OTM  (defined-risk bear direction)
  CALL_DEBIT   long call ~1% OTM / short ~3% OTM (defined-risk bull direction)
Plus SHARES overnight (close->next open) and turn-of-month (25th->4th) per regime from SPY bars.
Flow strategies are NOT recomputed - the mega sweep already mapped them (fade=bear only).

Output: reports/research/regime_playbook_2026-08-25.md
"""
import json
import math
import os
import sqlite3
import time
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}


def spy_bars():
    u = ("https://data.alpaca.markets/v2/stocks/bars?symbols=SPY&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-25&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                return (json.loads(r.read()).get("bars") or {}).get("SPY") or []
        except Exception:
            time.sleep(3)
    return []


def tstat(v):
    n = len(v)
    if n < 6:
        return 0.0
    mu = sum(v) / n
    sd = (sum((x - mu) ** 2 for x in v) / (n - 1)) ** 0.5
    return mu / (sd / math.sqrt(n)) if sd > 0 else 0.0


def fmt(v):
    if not v:
        return "no trades"
    mu = sum(v) / len(v)
    wins = sum(1 for x in v if x > 0) / len(v)
    return f"${mu:+,.0f}/wk t{tstat(v):+.1f} win {wins:.0%} worst ${min(v):+,.0f} (n={len(v)})"


def main():
    bars = spy_bars()
    closes = {b["t"][:10]: b["c"] for b in bars}
    opens = {b["t"][:10]: b["o"] for b in bars}
    days = sorted(closes)
    sma50, buf, regime = {}, [], {}
    for d in days:
        buf.append(closes[d])
        s = sum(buf[-50:]) / min(len(buf), 50)
        dist = (closes[d] / s - 1) * 100
        sma50[d] = dist
        regime[d] = "BEAR" if dist < -2 else ("BULL" if dist > 2 else "MILD")
    print(f"SPY days {len(days)}; regime counts:",
          {r: sum(1 for d in days if regime[d] == r) for r in ("BULL", "MILD", "BEAR")}, flush=True)

    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    # SPY option chain per day from the archive: strike/expiry parsed from OCC symbol
    chain = defaultdict(dict)          # day -> (expiry, right, strike) -> (bid, ask)
    for occ, day, bid, ask in con.execute(
            "select option_symbol, day, nbbo_bid, nbbo_ask from contracts_daily "
            "where ticker='SPY' and nbbo_bid is not null and nbbo_ask is not null and nbbo_ask>0"):
        try:
            exp = "20" + occ[3:9]
            right = occ[9]
            k = int(occ[10:]) / 1000.0
        except Exception:
            continue
        chain[day][(exp, right, k)] = (bid, ask)
    print(f"chain days {len(chain)}", flush=True)

    def q(day, exp, right, target, side):
        """Nearest-strike quote within $3 of target. side='sell'->bid, 'buy'->ask."""
        best, bq = None, None
        for (e, r, k), (b, a) in chain.get(day, {}).items():
            if e != exp or r != right:
                continue
            if best is None or abs(k - target) < abs(best - target):
                best, bq = k, (b, a)
        if best is None or abs(best - target) > 3.0:
            return None, None
        return best, (bq[0] if side == "sell" else bq[1])

    res = defaultdict(lambda: defaultdict(list))     # strat -> regime -> [weekly $]
    for i, d in enumerate(days):
        if date.fromisoformat(d).weekday() != 0:     # enter Mondays
            continue
        # target expiry: the Friday of this week
        exp = (date.fromisoformat(d) + timedelta(days=4)).strftime("%Y%m%d")
        if d not in chain:
            continue
        S = closes[d]
        rg = regime[d]
        expd = (date.fromisoformat(d) + timedelta(days=4)).isoformat()
        ST = closes.get(expd)
        if ST is None:                                # holiday Friday -> nearest close after
            later = [x for x in days if x > d][:6]
            for x in later:
                if x >= expd:
                    ST = closes[x]; break
        if ST is None:
            continue

        def leg(right, otm_pct, side):
            tgt = round(S * (1 + otm_pct / 100.0) * (1 if right == "C" else 1))
            k, px = q(d, exp, right, S * (1 + otm_pct / 100.0), side)
            return k, px

        def settle_short_put(k):  return -max(0.0, k - ST) * 100
        def settle_long_put(k):   return  max(0.0, k - ST) * 100
        def settle_short_call(k): return -max(0.0, ST - k) * 100
        def settle_long_call(k):  return  max(0.0, ST - k) * 100

        # PUT_CREDIT: sell put -2%, buy put -4%
        ks, ps = leg("P", -2.0, "sell")
        kl, pl = leg("P", -4.0, "buy")
        if ps and pl and ks and kl and ks > kl:
            res["PUT_CREDIT"][rg].append((ps - pl) * 100 + settle_short_put(ks) + settle_long_put(kl))
        # CALL_CREDIT: sell call +2%, buy call +4%
        ks2, ps2 = leg("C", 2.0, "sell")
        kl2, pl2 = leg("C", 4.0, "buy")
        if ps2 and pl2 and ks2 and kl2 and ks2 < kl2:
            res["CALL_CREDIT"][rg].append((ps2 - pl2) * 100 + settle_short_call(ks2) + settle_long_call(kl2))
        # IRON_CONDOR: both
        if (ps and pl and ks and kl and ks > kl) and (ps2 and pl2 and ks2 and kl2 and ks2 < kl2):
            res["IRON_CONDOR"][rg].append((ps - pl + ps2 - pl2) * 100
                                          + settle_short_put(ks) + settle_long_put(kl)
                                          + settle_short_call(ks2) + settle_long_call(kl2))
        # PUT_DEBIT: buy put -1%, sell put -3%
        kb, pb = leg("P", -1.0, "buy")
        ks3, ps3 = leg("P", -3.0, "sell")
        if pb and ps3 and kb and ks3 and kb > ks3:
            res["PUT_DEBIT"][rg].append(-(pb - ps3) * 100 + settle_long_put(kb) + settle_short_put(ks3))
        # CALL_DEBIT: buy call +1%, sell call +3%
        kb2, pb2 = leg("C", 1.0, "buy")
        ks4, ps4 = leg("C", 3.0, "sell")
        if pb2 and ps4 and kb2 and ks4 and kb2 < ks4:
            res["CALL_DEBIT"][rg].append(-(pb2 - ps4) * 100 + settle_long_call(kb2) + settle_short_call(ks4))

    # shares effects per regime ($1k notional)
    for i in range(len(days) - 1):
        d, nd = days[i], days[i + 1]
        rg = regime[d]
        ovn = (opens[nd] / closes[d] - 1) * 1000
        res["SHARES_OVERNIGHT"][rg].append(ovn)
        dom = date.fromisoformat(d).day
        if dom >= 25 or dom <= 3:
            res["SHARES_TURN_OF_MONTH"][rg].append((closes[nd] / closes[d] - 1) * 1000)

    L = ["# REGIME PLAYBOOK - 2026-08-25", "",
         "Structural strategies regime-split over the archive (real SPY option nbbo, sell-at-bid/",
         "buy-at-ask, settled vs real SPY close). One lot, weekly, all affordable at $1k-1.5k max",
         "loss. Shares rows are $1k notional per day. Flow strategies: see mega_sweep (fade=bear only).",
         f"Regime day counts: BULL {sum(1 for d in days if regime[d]=='BULL')} / "
         f"MILD {sum(1 for d in days if regime[d]=='MILD')} / "
         f"BEAR {sum(1 for d in days if regime[d]=='BEAR')}", "",
         "| strategy | BULL | MILD | BEAR |", "|---|---|---|---|"]
    for st in ("PUT_CREDIT", "CALL_CREDIT", "IRON_CONDOR", "PUT_DEBIT", "CALL_DEBIT",
               "SHARES_OVERNIGHT", "SHARES_TURN_OF_MONTH"):
        L.append(f"| {st} | " + " | ".join(fmt(res[st].get(r, [])) for r in ("BULL", "MILD", "BEAR")) + " |")
    open("reports/research/regime_playbook_2026-08-25.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("PLAYBOOK COMPLETE", flush=True)


if __name__ == "__main__":
    main()

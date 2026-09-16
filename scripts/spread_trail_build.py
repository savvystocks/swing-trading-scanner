"""TRAILING THE TOP END OF A DEBIT SPREAD (research, read-only).

Owner question 2026-09-16 03:50 BST: the short leg caps the winners - can the cap be trailed?
Measured cost of the cap (spread_access_v2, 25,749 paired trades): nothing on small moves, 22% on
trades that doubled, 23% on the 655 trades that tripled. Those 2.5% of trades are where the money
is, so the cap is the structure's one real weakness.

Four arms, PAIRED - the same qualifying-print contract-day, same entry, same exit rule:

  SINGLE    buy the trigger contract outright
  HOLD      buy it, sell the furthest strike that fits the budget, hold the pair to the exit
  BUYBACK   as HOLD, but once the position is +TRIG% up, pay the short leg's ASK to close it and
            run the long leg alone, uncapped, on the same rules
  ROLL      as HOLD, but at +TRIG% buy the short back and sell the next strike further out,
            raising the ceiling for part of the cost

Accounting is in DOLLARS against the ORIGINAL debit, so the arms stay comparable: closing the short
leg ADDS to what the trade has cost you, selling a new one subtracts. Every leg is priced where it
could actually trade - you sell at the bid and buy at the ask, never the mid - so the buyback is
charged at the ask exactly when it has become expensive, which is the honest cost of the idea.

Exit: BASE -50 / +50 / 0.20 on the return against the original debit. Close-to-close basis, daily
resolution, same as spread_access_v2 and NOT comparable to a v3 cell; the arms share it, so the
comparison is the result.
"""
import json
import os
import random
import sqlite3
from collections import defaultdict
from datetime import date

REPO = os.path.expanduser("~/swing-trading-scanner")
os.chdir(REPO)
UW = "data/uw_history.db"
OUT = "reports/research/spread_trail_v1.jsonl"
QUAL_PREM = 50000.0
BUDGET = 1000.0
HORIZON = 21
STOP, TRIG_EXIT, GIVE = -50.0, 50.0, 0.20
TRIGGERS = [50.0, 100.0]          # trail the cap once the position is this far up
PER_DAY = 150
SEED = 23


def parse_occ(occ):
    i = len(occ) - 15
    if i < 1:
        return None
    try:
        return (occ[:i], f"20{occ[i:i+2]}-{occ[i+2:i+4]}-{occ[i+4:i+6]}", occ[i+6], int(occ[i+7:]) / 1000.0)
    except Exception:
        return None


def occ_with_strike(occ, k):
    return occ[:len(occ) - 8] + f"{int(round(k * 1000)):08d}"


class Pos:
    """One arm of one trade. P&L always in dollars against the ORIGINAL debit."""
    __slots__ = ("arm", "long", "short", "debit0", "cash", "peak", "armed", "done", "ret", "why",
                 "days", "trig", "trailed")

    def __init__(self, arm, long_occ, short_occ, debit0, trig):
        self.arm, self.long, self.short = arm, long_occ, short_occ
        self.debit0 = debit0
        self.cash = debit0                 # total paid so far, per share
        self.peak, self.armed, self.done = 0.0, False, False
        self.ret, self.why, self.days, self.trailed = None, None, 0, False
        self.trig = trig

    def step(self, quote, chain):
        if self.done:
            return
        self.days += 1
        lb, la = quote.get(self.long, (None, None))
        if lb is None:
            return
        if self.short:
            sb, sa = quote.get(self.short, (None, None))
            if sa is None:
                return
            val = lb - sa
        else:
            val = lb
        r = (val - self.cash) / self.debit0 * 100.0
        # --- trail the cap, before the exit test, once the trade is clearly working
        if self.trig is not None and self.short and not self.trailed and r >= self.trig:
            sb, sa = quote.get(self.short, (None, None))
            if sa is not None:
                if self.arm == "buyback":
                    self.cash += sa                       # pay the ask to close the short leg
                    self.short = None
                    self.trailed = True
                elif self.arm == "roll":
                    p = parse_occ(self.long)
                    ps = parse_occ(self.short)
                    if p and ps:
                        further = [(k, b) for k, b in chain
                                   if (k > ps[3] if p[2] == "C" else k < ps[3]) and b and b > 0]
                        further.sort(key=lambda x: abs(x[0] - ps[3]))
                        if further:
                            k, b = further[0]
                            self.cash += sa - b           # close the old, sell the next one out
                            self.short = occ_with_strike(self.long, k)
                            self.trailed = True
                # recompute after the change
                lb2, _ = quote.get(self.long, (None, None))
                if lb2 is not None:
                    if self.short:
                        _, sa2 = quote.get(self.short, (None, None))
                        val = (lb2 - sa2) if sa2 is not None else val
                    else:
                        val = lb2
                    r = (val - self.cash) / self.debit0 * 100.0
        if r <= STOP:
            self.ret, self.why, self.done = STOP, "stop", True
            return
        self.peak = max(self.peak, r)
        if self.peak >= TRIG_EXIT:
            self.armed = True
        if self.armed and r <= self.peak * (1.0 - GIVE):
            self.ret, self.why, self.done = r, "trail", True
            return
        self.ret = r

    def finish(self):
        if not self.done:
            self.why = self.why or "horizon"
            self.done = True


def main():
    random.seed(SEED)
    uw = sqlite3.connect(UW)
    uw.execute("pragma cache_size=-40000")
    print("pass 1: qualifying prints", flush=True)
    ent = defaultdict(list)
    key = None
    cum = ask_p = bid_p = 0.0
    for occ, day, ts, prem, ask, side in uw.execute(
            "select occ, day, executed_at, premium, nbbo_ask, side_hint from flow_prints order by day, occ, executed_at"):
        if (occ, day) != key:
            key, cum, ask_p, bid_p = (occ, day), 0.0, 0.0, 0.0
        if cum >= QUAL_PREM:
            continue
        p = prem or 0.0
        cum += p
        if side == "ask":
            ask_p += p
        elif side == "bid":
            bid_p += p
        if cum >= QUAL_PREM and ask_p > bid_p:
            ent[day].append(occ)
    days_all = [r[0] for r in uw.execute("select distinct day from contracts_daily order by day")]
    dpos = {d: i for i, d in enumerate(days_all)}
    sampled = defaultdict(list)
    for d, lst in ent.items():
        if d in dpos:
            for occ in (random.sample(lst, PER_DAY) if len(lst) > PER_DAY else lst):
                sampled[d].append(occ)
    print(f"  sampled {sum(len(v) for v in sampled.values()):,} contract-days", flush=True)

    out = open(OUT, "w", encoding="utf-8")
    out.write(json.dumps({"_meta": "spread trail v1", "budget": BUDGET, "triggers": TRIGGERS,
                          "arms": ["single", "hold", "buyback", "roll"], "rule": [STOP, TRIG_EXIT, GIVE],
                          "horizon": HORIZON, "per_day": PER_DAY, "seed": SEED,
                          "accounting": "dollars vs the ORIGINAL debit; short closed at ASK, new short sold at BID",
                          "basis": "close_to_close"}) + "\n")
    live = []          # (meta, [Pos...])
    n = 0
    for di, d in enumerate(days_all):
        rows = uw.execute("select option_symbol, nbbo_bid, nbbo_ask, ticker from contracts_daily where day=?", (d,)).fetchall()
        quote = {o: (b, a) for o, b, a, t in rows}
        by_tk_exp = defaultdict(list)
        for o, b, a, t in rows:
            p = parse_occ(o)
            if p and b and b > 0:
                by_tk_exp[(p[0], p[1], p[2])].append((p[3], b))
        # advance
        still = []
        for meta, poss in live:
            chain = by_tk_exp.get(meta["ck"], [])
            for ps in poss:
                ps.step(quote, chain)
            if all(p.done for p in poss) or len(poss) == 0 or meta["n"] + 1 >= HORIZON or meta["expiry"] <= d:
                for ps in poss:
                    ps.finish()
                rec = {k: meta[k] for k in ("day", "occ", "t", "side", "dte", "long_ask", "debit0")}
                for ps in poss:
                    tag = ps.arm if ps.trig is None else f"{ps.arm}{int(ps.trig)}"
                    rec[tag] = None if ps.ret is None else round(ps.ret, 2)
                    rec[tag + "_why"] = ps.why
                    if ps.arm in ("buyback", "roll"):
                        rec[tag + "_fired"] = ps.trailed
                out.write(json.dumps(rec) + "\n")
                n += 1
            else:
                meta["n"] += 1
                still.append((meta, poss))
        live = still
        # new entries
        for occ in sampled.get(d, []):
            p = parse_occ(occ)
            if not p:
                continue
            tk, exp, side, strike = p
            lb, la = quote.get(occ, (None, None))
            if not la or la <= 0 or exp <= d:
                continue
            chain = by_tk_exp.get((tk, exp, side), [])
            cands = [(k, b) for k, b in chain if (k > strike if side == "C" else k < strike)]
            cands.sort(key=lambda x: -abs(x[0] - strike))
            pick = next(((k, b) for k, b in cands if (la - b) > 0 and (la - b) * 100 <= BUDGET), None)
            if not pick or la * 100 > BUDGET * 3:
                continue
            k, b = pick
            debit = la - b
            short_occ = occ_with_strike(occ, k)
            meta = {"day": d, "occ": occ, "t": tk, "side": side, "expiry": exp, "n": 0,
                    "dte": (date.fromisoformat(exp) - date.fromisoformat(d)).days,
                    "long_ask": round(la, 2), "debit0": round(debit, 2), "ck": (tk, exp, side)}
            poss = [Pos("hold", occ, short_occ, debit, None)]
            if la * 100 <= BUDGET:
                poss.append(Pos("single", occ, None, la, None))
            for tg in TRIGGERS:
                poss.append(Pos("buyback", occ, short_occ, debit, tg))
                poss.append(Pos("roll", occ, short_occ, debit, tg))
            live.append((meta, poss))
        if di % 60 == 0:
            print(f"    {d} live {len(live):,} written {n:,}", flush=True)
    for meta, poss in live:
        for ps in poss:
            ps.finish()
        rec = {k: meta[k] for k in ("day", "occ", "t", "side", "dte", "long_ask", "debit0")}
        for ps in poss:
            tag = ps.arm if ps.trig is None else f"{ps.arm}{int(ps.trig)}"
            rec[tag] = None if ps.ret is None else round(ps.ret, 2)
            rec[tag + "_fired"] = ps.trailed if ps.arm in ("buyback", "roll") else None
        out.write(json.dumps(rec) + "\n")
        n += 1
    out.close()
    print(f"DONE {n:,} paired trades -> {OUT}", flush=True)


if __name__ == "__main__":
    main()

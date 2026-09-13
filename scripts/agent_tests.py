"""TRADING-AGENT TESTS (owner order 2026-09-14 00:40: "test them all first"). Three candidate agents
that would act on trades, each tested on data we already hold, each against a bar written here
BEFORE the run. Report only; nothing here touches the trade path.

A. EXIT AGENT - fine exit corpus (reports/research/glide_fine_rows_v3.jsonl: every archive trade
   under 210 stop x trigger x give-back configs, v3 basis). For the pool and each fixed strategy:
   BASE (-50/+50/0.20) vs a WALK-FORWARD exit chosen per quarter as the config with the best
   per-trade mean on all PRIOR quarters (>= 200 prior rows, else BASE), and a per-REGIME walk-
   forward variant. Scored as day means; paired t of (chosen - BASE) over days. The in-sample
   best is printed only as the ceiling it is.
   BAR: walk-forward beats BASE with paired t >= 2.0 on the pool AND on at least two strategies.
B. ALLOCATION AGENT - same corpus, BASE exit. Regime by prior-close SPY 50d distance (BEAR < -2,
   BULL > +2, else MILD). ROSTER = what the roster does now: every strategy that fires on a day
   contributes its day mean, equally. WALK-FORWARD ALLOCATION = per quarter, per regime, fund only
   the strategy with the best prior-quarters day mean in that regime (>= 10 prior days), else cash.
   VETO = the roster minus any strategy whose prior day mean in that regime is negative.
   BAR: allocation beats ROSTER with paired t >= 2.0 over all days AND a positive second half.
C. EXECUTION AGENT - the fill ledger (harvest.db fills, entry_fill events) joined to the book's
   decision quotes (legs[..].execution_cost) by order id: fill rate by terminal state, price band
   and spread; slippage of the fill against the decision ask and the limit; time to fill; and, on
   contracts with hourly bars, whether a limit at the decision MID would have filled within two
   bars and what it would have saved, against the realized return of the trades it would have missed.
   BAR: a mid-limit fills >= 70% of the time within two bars with a saving >= 3% of premium, and
   the missed trades' realized return is not the winners (mean of missed <= mean of filled).
Output: reports/research/agent_tests_<date>.md"""
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import numpy as np

FINE = "reports/research/glide_fine_rows_v3.jsonl"
STOPS = [-45.0, -50.0, -55.0, -60.0, -65.0, -70.0, -75.0]
TRIGS = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0]
GIVES = [0.15, 0.20, 0.25, 0.30, 0.35]
GRID = [(s, t, g) for s in STOPS for t in TRIGS for g in GIVES]
GIX = {c: i for i, c in enumerate(GRID)}
BASE = GIX[(-50.0, 50.0, 0.20)]
FILT = {
    "POOL": lambda r: True,
    "FOLLOW_CALLS": lambda r: r["side"] == "C",
    "BULL_DIP": lambda r: r["side"] == "C" and r["reg"] > 2 and r["smd"] < 0,
    "DIP_CONF_MILD": lambda r: r["side"] == "C" and -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0,
    "DIP_CONVEXITY": lambda r: r["side"] == "C" and r["reg"] < -2,
}


def qkey(d):
    return f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"


def regime(reg):
    return "BEAR" if reg < -2 else ("BULL" if reg > 2 else "MILD")


def paired_t(a, b):
    d = np.asarray(a) - np.asarray(b)
    if len(d) < 3 or d.std(ddof=1) == 0:
        return 0.0
    return float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d))))


def halves(v):
    h = len(v) // 2
    return (float(np.mean(v[:h])) if h else float("nan"), float(np.mean(v[h:])) if len(v) - h else float("nan"))


def cfg_s(j):
    s, t, g = GRID[j]
    return f"{s:.0f}/+{t:.0f}/{g:.2f}"


def load_fine():
    rows = []; R = []
    for l in open(FINE, encoding="utf-8"):
        try:
            j = json.loads(l)
        except Exception:
            continue
        r = j.get("rets")
        if not r or len(r) != 210:
            continue
        rows.append({"day": j["day"], "side": j["side"], "reg": j["reg"], "smd": j["smd"], "sp": j["sp"], "occ": j["occ"]})
        R.append([0.0 if v is None else v for v in r])
    return rows, np.asarray(R, dtype=np.float32)


def daymeans(vals, days):
    d = defaultdict(list)
    for v, dd in zip(vals, days):
        d[dd].append(float(v))
    return {k: sum(v) / len(v) for k, v in d.items()}


def exit_test(rows, R):
    days_all = np.array([r["day"] for r in rows])
    q_all = np.array([qkey(d) for d in days_all])
    reg_all = np.array([regime(r["reg"]) for r in rows])
    L = ["## A. Exit agent - walk-forward exit choice vs BASE (day means, v3 basis)", "",
         "| book | rows | days | BASE %/day | WALK-FORWARD %/day | diff | paired t | WF halves | per-REGIME WF %/day | paired t | in-sample ceiling %/day | chosen (last 4 quarters) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    passes = {}
    for name, f in FILT.items():
        m = np.array([f(r) for r in rows])
        if m.sum() < 300:
            L.append(f"| {name} | {int(m.sum())} | - | too few rows | | | | | | | | |"); continue
        Rm, dm, qm, rgm = R[m], days_all[m], q_all[m], reg_all[m]
        qs = sorted(set(qm))
        wf = np.zeros(len(Rm), dtype=np.float32); chosen = []
        prg = np.zeros(len(Rm), dtype=np.float32)
        for qi, q in enumerate(qs):
            prior = np.isin(qm, qs[:qi]); cur = qm == q
            j = BASE if prior.sum() < 200 else int(np.argmax(Rm[prior].mean(axis=0)))
            wf[cur] = Rm[cur, j]; chosen.append(f"{q}:{cfg_s(j)}")
            for rg in ("BEAR", "BULL", "MILD"):
                pm = prior & (rgm == rg); cm = cur & (rgm == rg)
                jj = j if pm.sum() < 200 else int(np.argmax(Rm[pm].mean(axis=0)))
                prg[cm] = Rm[cm, jj]
        base_dm = daymeans(Rm[:, BASE], dm); wf_dm = daymeans(wf, dm); prg_dm = daymeans(prg, dm)
        ds = sorted(base_dm)
        b = [base_dm[d] for d in ds]; w = [wf_dm[d] for d in ds]; p = [prg_dm[d] for d in ds]
        t_wf = paired_t(w, b); t_prg = paired_t(p, b)
        ceiling = float(Rm.mean(axis=0).max())
        ceil_dm = daymeans(Rm[:, int(np.argmax(Rm.mean(axis=0)))], dm)
        h1, h2 = halves(w)
        passes[name] = t_wf >= 2.0 and np.mean(w) > np.mean(b)
        L.append(f"| {name} | {len(Rm)} | {len(ds)} | {np.mean(b):+.2f} | {np.mean(w):+.2f} | {np.mean(w) - np.mean(b):+.2f} | {t_wf:+.2f} | "
                 f"{h1:+.1f}/{h2:+.1f} | {np.mean(p):+.2f} | {t_prg:+.2f} | {np.mean([ceil_dm[d] for d in ds]):+.2f} | {', '.join(chosen[-4:])} |")
    strat_pass = sum(1 for k, v in passes.items() if k != "POOL" and v)
    verdict = "PASS" if (passes.get("POOL") and strat_pass >= 2) else "FAIL"
    L += ["", f"Exit agent bar (paired t >= 2.0 on the pool AND on >= 2 strategies): {verdict} "
              f"(pool {'yes' if passes.get('POOL') else 'no'}, strategies passing {strat_pass}/4)."]
    return L, verdict


def allocation_test(rows, R):
    base = R[:, BASE]
    days_all = np.array([r["day"] for r in rows])
    reg_by_day = {}
    for r in rows:
        reg_by_day[r["day"]] = regime(r["reg"])
    strats = [k for k in FILT if k != "POOL"]
    sdm = {}
    for s in strats:
        m = np.array([FILT[s](r) for r in rows])
        sdm[s] = daymeans(base[m], days_all[m])
    days = sorted(set(days_all))
    qs = sorted({qkey(d) for d in days})
    roster = []; alloc = []; veto = []; pool = []
    pool_dm = daymeans(base, days_all)
    chosen_log = []
    for d in days:
        q = qkey(d); rg = reg_by_day[d]
        firing = [s for s in strats if d in sdm[s]]
        roster.append(float(np.mean([sdm[s][d] for s in firing])) if firing else 0.0)
        pool.append(pool_dm[d])
        prior_days = [dd for dd in days if qkey(dd) < q and reg_by_day[dd] == rg]
        best, best_v = None, -1e9; vetoed = set()
        for s in strats:
            pv = [sdm[s][dd] for dd in prior_days if dd in sdm[s]]
            if len(pv) >= 10:
                mv = float(np.mean(pv))
                if mv > best_v:
                    best, best_v = s, mv
                if mv < 0:
                    vetoed.add(s)
        alloc.append(sdm[best][d] if (best and best_v > 0 and d in sdm[best]) else 0.0)
        keep = [s for s in firing if s not in vetoed]
        veto.append(float(np.mean([sdm[s][d] for s in keep])) if keep else 0.0)
        if d == days[-1] or (chosen_log and chosen_log[-1][0] != q):
            pass
        chosen_log.append((q, rg, best, round(best_v, 2) if best else None))
    last_q = {}
    for q, rg, best, v in chosen_log:
        last_q[(q, rg)] = (best, v)
    tail = sorted(last_q.items())[-6:]
    L = ["## B. Allocation agent - regime-aware budget vs the roster as it is (day means, BASE exit)", "",
         "| policy | days | %/day | halves | paired t vs ROSTER | active days |", "|---|---|---|---|---|---|"]
    for name, v in (("POOL (every trigger)", pool), ("ROSTER (every firing strategy, equal)", roster),
                    ("VETO (roster minus negative-prior strategies)", veto), ("WALK-FORWARD ALLOCATION (best prior strategy per regime, else cash)", alloc)):
        h1, h2 = halves(v)
        L.append(f"| {name} | {len(v)} | {np.mean(v):+.2f} | {h1:+.1f}/{h2:+.1f} | {paired_t(v, roster):+.2f} | {sum(1 for x in v if x != 0)} |")
    t_alloc = paired_t(alloc, roster); h2 = halves(alloc)[1]
    verdict = "PASS" if (t_alloc >= 2.0 and h2 > 0) else "FAIL"
    L += ["", "last choices (quarter, regime -> strategy, prior %/day): " + "; ".join(f"{q} {rg} -> {b} ({v})" for (q, rg), (b, v) in tail),
          "", f"Allocation agent bar (paired t >= 2.0 vs ROSTER and positive second half): {verdict} (t {t_alloc:+.2f}, second half {h2:+.2f})."]
    return L, verdict


def execution_test():
    L = ["## C. Execution agent - what our fills actually cost, and what a mid-price limit would have done", ""]
    book = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
    by_order = {}
    for r in book:
        for ln, o in (r.get("orders") or {}).items():
            if o.get("order_id"):
                lg = (r.get("legs") or {}).get(ln) or {}
                ret = ((r.get("leg_exits") or {}).get(ln) or {}).get("return_pct")
                by_order[o["order_id"]] = {"rec": r, "leg": lg, "ret": ret, "ln": ln}
    con = sqlite3.connect("file:data/harvest.db?mode=ro", uri=True)
    fills = []
    for (payload,) in con.execute("select payload from fills where kind='entry_fill'"):
        try:
            fills.append(json.loads(payload))
        except Exception:
            pass
    joined = []
    for f in fills:
        j = by_order.get(f.get("order_id"))
        if not j:
            continue
        ec = j["leg"].get("execution_cost") or {}
        joined.append({"state": f.get("terminal_state"), "fill": f.get("filled_avg_price"), "qty": f.get("filled_qty"),
                       "oq": f.get("ordered_qty"), "limit": f.get("limit_price") or j["leg"].get("limit_price"),
                       "ask": ec.get("ask"), "bid": ec.get("bid"), "mid": ec.get("mid"), "sp": ec.get("bid_ask_spread_pct"),
                       "delay_ms": f.get("signal_to_fill_ms"), "ret": j["ret"], "book": j["rec"].get("book"),
                       "occ": j["leg"].get("occ_symbol"), "day": (j["rec"].get("entry_ts_utc") or "")[:10],
                       "ts": j["rec"].get("entry_ts_utc") or ""})
    n = len(joined)
    if not n:
        return L + ["no fills joined to records"], "FAIL"
    states = defaultdict(int)
    for x in joined:
        states[x["state"]] += 1
    L.append(f"{len(fills)} entry-fill events, {n} joined to a book record with a decision quote; terminal states: {dict(states)}")
    filled = [x for x in joined if x["state"] == "filled" and x["fill"] and x["ask"]]
    slip_ask = [(x["fill"] - x["ask"]) / x["ask"] * 100 for x in filled]
    slip_lim = [(x["fill"] - x["limit"]) / x["limit"] * 100 for x in filled if x["limit"]]
    delays = [x["delay_ms"] / 1000.0 for x in filled if isinstance(x["delay_ms"], (int, float))]
    partial = sum(1 for x in filled if x["qty"] and x["oq"] and x["qty"] < x["oq"])
    L += ["", "| measure | n | mean | median | p90 |", "|---|---|---|---|---|"]
    for name, v in (("fill vs decision ask, % of ask", slip_ask), ("fill vs limit, %", slip_lim), ("signal to fill, seconds", delays)):
        if v:
            a = np.array(v); L.append(f"| {name} | {len(a)} | {a.mean():+.2f} | {np.median(a):+.2f} | {np.percentile(a, 90):+.2f} |")
    L.append(f"| partial fills | {partial} of {len(filled)} | | | |")
    # fill rate by price band and by spread
    L += ["", "| decision-ask band | orders | filled | cancelled/expired | fill rate | mean slip vs ask % |", "|---|---|---|---|---|---|"]
    bands = [(0, 1), (1, 4), (4, 10), (10, 1e9)]
    for lo, hi in bands:
        xs = [x for x in joined if x["ask"] and lo <= x["ask"] < hi]
        if not xs:
            continue
        fl = [x for x in xs if x["state"] == "filled"]
        sl = [(x["fill"] - x["ask"]) / x["ask"] * 100 for x in fl if x["fill"]]
        L.append(f"| ${lo:g}-{hi if hi < 1e9 else 'up':} | {len(xs)} | {len(fl)} | {len(xs) - len(fl)} | {len(fl) / len(xs):.0%} | {np.mean(sl) if sl else float('nan'):+.2f} |")
    L += ["", "| decision spread band | orders | fill rate | mean slip vs ask % |", "|---|---|---|---|"]
    for lo, hi in ((0, 1), (1, 2), (2, 5), (5, 1e9)):
        xs = [x for x in joined if isinstance(x["sp"], (int, float)) and lo <= x["sp"] < hi]
        if not xs:
            continue
        fl = [x for x in xs if x["state"] == "filled"]
        sl = [(x["fill"] - x["ask"]) / x["ask"] * 100 for x in fl if x["fill"] and x["ask"]]
        L.append(f"| {lo:g}-{hi if hi < 1e9 else 'up':}% | {len(xs)} | {len(fl) / len(xs):.0%} | {np.mean(sl) if sl else float('nan'):+.2f} |")
    # mid-limit simulation on contracts with hourly bars
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True)
    sim = []
    for x in filled:
        if not (x["mid"] and x["occ"] and x["ts"]):
            continue
        bars = lib.execute("select ts, o, h, l, c from bars where occ=? and ts >= ? order by ts limit 3", (x["occ"], x["ts"][:13])).fetchall()
        if len(bars) < 2:
            continue
        lows = [b[3] for b in bars[:2]]
        hit = min(lows) <= x["mid"]
        sim.append({"hit": hit, "save_pct": (x["ask"] - x["mid"]) / x["ask"] * 100, "ret": x["ret"], "fill": x["fill"], "ask": x["ask"]})
    if sim:
        hits = [s for s in sim if s["hit"]]; miss = [s for s in sim if not s["hit"]]
        p_fill = len(hits) / len(sim)
        save = float(np.mean([s["save_pct"] for s in sim]))
        r_hit = [s["ret"] for s in hits if s["ret"] is not None]; r_miss = [s["ret"] for s in miss if s["ret"] is not None]
        L += ["", f"Mid-limit simulation on {len(sim)} filled orders whose contracts have hourly bars: a limit at the decision mid "
                  f"would have filled within two bars {p_fill:.0%} of the time, saving {save:.1f}% of premium on average; the trades it would "
                  f"have MISSED realized {np.mean(r_miss) if r_miss else float('nan'):+.1f}% (n {len(r_miss)}) vs {np.mean(r_hit) if r_hit else float('nan'):+.1f}% "
                  f"for the ones it would have caught (n {len(r_hit)})."]
        verdict = "PASS" if (p_fill >= 0.7 and save >= 3.0 and (not r_miss or not r_hit or np.mean(r_miss) <= np.mean(r_hit))) else "FAIL"
        L.append(f"Execution agent bar (mid-limit fills >= 70% within two bars, saving >= 3%, missed trades not the winners): {verdict}.")
    else:
        verdict = "FAIL"
        L.append("Mid-limit simulation: no filled orders with hourly bars - the bar cannot be tested on this data (FAIL by absence).")
    L += ["", "Reading: paper fills are a FLOOR on real costs (fill ledger header). The decision ask is the quote the engine priced "
              "its limit on; a positive slip means the fill printed above it."]
    return L, verdict


def main():
    t0 = datetime.now()
    rows, R = load_fine()
    print(f"fine rows {len(rows)} x {R.shape[1]} configs loaded in {(datetime.now() - t0).seconds}s", flush=True)
    A, va = exit_test(rows, R)
    B, vb = allocation_test(rows, R)
    C, vc = execution_test()
    L = [f"# TRADING-AGENT TESTS - {date.today().isoformat()}", "",
         f"Bars were written in the script header before the run. Fine corpus {len(rows)} rows (v3 basis), BASE exit for anything not about exits.", ""]
    L += A + [""] + B + [""] + C + ["", "## Verdicts", "", f"- Exit agent: {va}", f"- Allocation agent: {vb}", f"- Execution agent: {vc}",
          "", "A PASS means the agent is worth building and taking through the panel, the drill and the gate; a FAIL means the data we hold "
              "does not support it on the pre-registered bar, whatever a weaker bar would say."]
    out = f"reports/research/agent_tests_{date.today().isoformat()}.md"
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print(f"written {out}", flush=True)


if __name__ == "__main__":
    main()

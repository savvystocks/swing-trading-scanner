"""RETURNS LEDGER (owner order 2026-09-13 23:50: "do this but for performance on returns").

One script that recomputes every strategy's performance from the two sources of truth and writes
one machine-readable ledger the performance map must agree with:
  LIVE   - proactive_sandbox_logs.json, built EXACTLY as the Friday court builds it
           (scripts/sunday_boundary.py): book PROBE, entry day, the first leg's return_pct, a
           settled weekly structure as pnl_usd / $1,000, STUDENT_* pooled into STUDENT_FAMILY;
           then per-trade mean and win rate, day means, days shared with the control, the court's
           symmetric-trim t against the control, own halves, the mean with the single best trade
           removed, realized dollars, open count.
  ARCHIVE - reports/research/probe_tuner_rows_v3.jsonl (executable basis) with the tuner's own
           strategy filters, on the exit the roster runs (spec probe.tuning.<name>.exit snapped to
           the tuner's exit list, else BASE): %/day, the pool on the same days, t vs pool, halves.
           Strategies with no honest cell say so instead of carrying a stale number.
  COURT  - the last standing line per strategy from the Friday court log.
  CAPTURE - live day-mean over archive %/day, only with >= 20 live days (else the reason).
Writes reports/performance/ledger.json and ledger.md; --update-map rewrites every
[[KEY = value]] token in docs/performance_map/*.md from the ledger so the map can never quote a
number the ledger does not hold. Research/ops tier: reads only, never touches the trade path.
"""
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

BOOK = "proactive_sandbox_logs.json"
CORPUS = "reports/research/probe_tuner_rows_v3.jsonl"
COURT_LOG = os.path.expanduser("~/sunday_boundary.log")
OUT_JSON = "reports/performance/ledger.json"
OUT_MD = "reports/performance/ledger.md"
MAP = "docs/performance_map"
ACTIVE = ["EXEC_BASELINE", "FOLLOW_CALLS", "BULL_DIP", "DIP_CONF_MILD", "DIP_CONVEXITY",
          "WINNER_PROFILE", "CREDIT_SPREAD_W", "STUDENT_FAMILY"]
EXITS = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
         (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]
ARCHIVE_FILTER = {
    "EXEC_BASELINE": ("POOL: every archive trigger (the control's universe)", lambda r: True),
    "FOLLOW_CALLS": ("calls, all regimes", lambda r: r["side"] == "C"),
    "BULL_DIP": ("calls, SPY 50d > +2, ticker below its 20d", lambda r: r["side"] == "C" and r["reg"] > 2 and r["smd"] < 0),
    "DIP_CONF_MILD": ("calls, SPY 50d within +-2, ticker below 20d, SPY below 20d", lambda r: r["side"] == "C" and -2 <= r["reg"] <= 2 and r["smd"] < 0 and r["sp"] < 0),
    "DIP_CONVEXITY": ("calls, SPY 50d < -2", lambda r: r["side"] == "C" and r["reg"] < -2),
    "WINNER_PROFILE": ("PARTIAL: premium > 73.2k only (the corpus has no IV column for the second leg)", lambda r: r["prem"] > 73200),
}


def tstat(x):
    n = len(x)
    if n < 3:
        return 0.0
    m = sum(x) / n
    sd = (sum((v - m) ** 2 for v in x) / (n - 1)) ** 0.5
    return (m / (sd / math.sqrt(n))) if sd > 0 else 0.0


def week_key(d):
    y, w, _ = date.fromisoformat(d).isocalendar()
    return f"{y}-W{w:02d}"


def live_side(book, spec):
    by = defaultdict(lambda: defaultdict(list))      # strat -> day -> [ret]
    trades = defaultdict(list)                        # strat -> [(day, ret, usd, tsid, ticker)]
    open_n = defaultdict(int)
    for r in book:
        st = r.get("probe_strategy")
        if r.get("book") != "PROBE" or not st:
            continue
        if r.get("status") == "OPEN":
            open_n[st] += 1
        day = (r.get("entry_ts_utc") or "")[:10]
        ret = None; usd = None
        for ln, le in (r.get("leg_exits") or {}).items():
            if le.get("return_pct") is not None:
                ret = le["return_pct"]
                lg = (r.get("legs") or {}).get(ln) or {}
                try:
                    usd = lg["entry_premium"] * lg["contracts"] * 100.0 * ret / 100.0
                except Exception:
                    usd = None
                break
        if r.get("settle") and r["settle"].get("pnl_usd") is not None:
            ret = (r["settle"]["pnl_usd"] / 1000.0) * 100
            usd = float(r["settle"]["pnl_usd"])
        if day and ret is not None:
            by[st][day].append(ret)
            trades[st].append((day, ret, usd, r.get("trade_set_id"), r.get("ticker")))
    for sn in list(by):
        if sn.startswith("STUDENT_") and sn != "STUDENT_FAMILY":
            for d, v in by[sn].items():
                by["STUDENT_FAMILY"][d].extend(v)
            trades["STUDENT_FAMILY"].extend(trades[sn])
            open_n["STUDENT_FAMILY"] += open_n.get(sn, 0)
    dm = {s: {d: sum(v) / len(v) for d, v in dd.items()} for s, dd in by.items()}
    ctrl = dm.get("EXEC_BASELINE", {})
    tuning = (spec.get("probe") or {}).get("tuning") or {}
    out = {}
    for s in set(list(dm) + list(open_n) + ACTIVE):
        d = dm.get(s, {})
        ap = (tuning.get(s) or {}).get("applied") or ""
        d_clock = {k: v for k, v in d.items() if k > ap} if ap else dict(d)
        unit = "weeks" if s.endswith("_W") else "days"     # the court's rule (decision 37: the family on DAYS)
        if unit == "weeks":
            def wm(x):
                w = defaultdict(list)
                for k, v in x.items():
                    w[week_key(k)].append(v)
                return {k: sum(v) / len(v) for k, v in w.items()}
            own_u, ctrl_u = wm(d_clock), wm(ctrl)
        else:
            own_u, ctrl_u = d_clock, ctrl
        shared = sorted(k for k in own_u if k in ctrl_u)
        diffs = [own_u[k] - ctrl_u[k] for k in shared]
        tdiffs = sorted(diffs)[1:-1] if len(diffs) >= 8 else diffs
        own_vals = [own_u[k] for k in sorted(own_u)]
        h = len(own_vals) // 2
        tr = trades.get(s, [])
        rets = [t[1] for t in tr]
        usd = [t[2] for t in tr if t[2] is not None]
        best_i = max(range(len(rets)), key=lambda i: rets[i]) if rets else None
        best_removed = ([v for i, v in enumerate(rets) if i != best_i]) if len(rets) > 1 else []
        out[s] = {
            "n_closed": len(rets), "per_trade": round(sum(rets) / len(rets), 1) if rets else None,
            "win": round(sum(1 for v in rets if v > 0) / len(rets), 3) if rets else None,
            "best_trade": round(max(rets), 1) if rets else None,
            "best_removed_per_trade": round(sum(best_removed) / len(best_removed), 1) if best_removed else None,
            "total_usd": round(sum(usd)) if usd else None, "usd_known_for": len(usd),
            "unit": unit, "units": len(own_vals), "unit_mean": round(sum(own_vals) / len(own_vals), 2) if own_vals else None,
            "h1": round(sum(own_vals[:h]) / h, 2) if h else None,
            "h2": round(sum(own_vals[h:]) / (len(own_vals) - h), 2) if len(own_vals) - h > 0 else None,
            "shared_units": len(shared), "t_vs_control": round(tstat(tdiffs), 2) if len(tdiffs) >= 3 else None,
            "mean_diff_vs_control": round(sum(tdiffs) / len(tdiffs), 2) if tdiffs else None,
            "clock": ap or None, "open": open_n.get(s, 0),
            "first_day": min((t[0] for t in tr), default=None), "last_close_day": max((t[0] for t in tr), default=None),
            "trades": [{"day": t[0], "ticker": t[4], "ret": round(t[1], 1), "usd": (round(t[2]) if t[2] is not None else None), "id": t[3]} for t in sorted(tr)],
        }
    return out


def archive_side(spec):
    if not os.path.exists(CORPUS):
        return {}, {"rows": 0, "note": "corpus missing"}
    rows = [json.loads(l) for l in open(CORPUS, encoding="utf-8")]
    rows = [r for r in rows if r.get("basis") == "ask_at_qualifying_print"]
    tuning = (spec.get("probe") or {}).get("tuning") or {}

    def exit_idx(name):
        ex = (tuning.get(name) or {}).get("exit") or {}
        try:
            cfg = (float(ex.get("stop")), float(ex.get("trigger", ex.get("trig"))), float(ex.get("giveback", ex.get("give"))))
            best = min(range(len(EXITS)), key=lambda i: sum(abs(a - b) for a, b in zip(EXITS[i], cfg)))
            return best, EXITS[best], "spec probe.tuning.exit snapped to the tuner exit list"
        except Exception:
            return 0, EXITS[0], "BASE (-50 / +50 / 0.20)"

    def daymeans(pred, ei):
        d = defaultdict(list)
        for r in rows:
            v = r["rets"][ei] if ei < len(r["rets"]) else None
            if v is not None and pred(r):
                d[r["day"]].append(v)
        return {k: sum(v) / len(v) for k, v in d.items()}, sum(len(v) for v in d.values())

    out = {}
    pool_cache = {}
    for name, (label, pred) in ARCHIVE_FILTER.items():
        ei, cfg, how = exit_idx(name)
        if ei not in pool_cache:
            pool_cache[ei] = daymeans(lambda r: True, ei)[0]
        pool = pool_cache[ei]
        dm, n = daymeans(pred, ei)
        days = sorted(dm)
        if not days:
            out[name] = {"cell": label, "note": "no rows"}; continue
        v = [dm[d] for d in days]
        diffs = [dm[d] - pool[d] for d in days if d in pool]
        h = len(v) // 2
        out[name] = {"cell": label, "exit": list(cfg), "exit_source": how, "basis": "v3 ask_at_qualifying_print, bid-side exits",
                     "trades": n, "days": len(days), "per_day": round(sum(v) / len(v), 2),
                     "pool_per_day_same_days": round(sum(pool[d] for d in days if d in pool) / max(1, len(diffs)), 2),
                     "t_vs_pool": round(tstat(diffs), 2) if name != "EXEC_BASELINE" else None,
                     "h1": round(sum(v[:h]) / h, 2) if h else None, "h2": round(sum(v[h:]) / (len(v) - h), 2) if len(v) - h else None,
                     "first_day": days[0], "last_day": days[-1]}
    out["CREDIT_SPREAD_W"] = {"cell": "not in the options corpus (XSP put spread); the 2.5-year backtest lives in scripts/fivek_backtests.py and is on the superseded basis",
                              "per_day": None, "note": "no honest-basis archive cell; the live weekly record is the evidence"}
    # STUDENT_FAMILY: the live pickers' executed slice from their exported model files
    st = (spec.get("probe") or {}).get("student") or {}
    fam = {"cell": "walk-forward executed slice under exec_max_ask, from the live pickers' model files", "pickers": {}}
    for pn, pc in sorted((st.get("probes") or {}).items()):
        mf = pc.get("model")
        if not (pc.get("live") and mf and os.path.exists(mf)):
            continue
        try:
            m = json.load(open(mf, encoding="utf-8"))
            es = m.get("walk_forward_executed_slice") or {}
            fam["pickers"][pn] = {"model": os.path.basename(mf), "trades": es.get("trades"), "weeks": es.get("weeks"),
                                  "per_trade": es.get("per_trade"), "win": es.get("win"), "wk_t": es.get("wk_t"),
                                  "pos_weeks": es.get("pos_weeks"), "total_usd": es.get("total")}
        except Exception as e:
            fam["pickers"][pn] = {"error": type(e).__name__}
    if fam["pickers"]:
        a = next(iter(fam["pickers"].values()))
        fam.update({"per_trade": a.get("per_trade"), "wk_t": a.get("wk_t"), "trades": a.get("trades"), "weeks": a.get("weeks")})
    else:
        fam["note"] = "no live picker"
    out["STUDENT_FAMILY"] = fam
    meta = {"rows": len(rows), "last_day": max((r["day"] for r in rows), default=None), "basis": "ask_at_qualifying_print / d1_close"}
    return out, meta


def court_side():
    out = {}
    try:
        for line in open(COURT_LOG, encoding="utf-8", errors="ignore"):
            m = re.match(r".*?PROBE ([A-Z_]+): (.*)$", line.strip())
            if m:
                out[m.group(1)] = m.group(2).strip()[:160]
    except Exception:
        pass
    return out


def fmt(key, v):
    if v is None:
        return "n/a"
    k = key.split(".")[-1]
    if k in ("win", "pos_weeks"):
        return f"{v:.0%}"
    if k in ("total_usd",):
        return f"{v:+,.0f}"
    if k in ("t_vs_control", "t_vs_pool", "wk_t", "mean_diff_vs_control"):
        return f"{v:+.2f}"
    if k in ("per_trade", "per_day", "pool_per_day_same_days", "h1", "h2", "unit_mean", "best_trade", "best_removed_per_trade"):
        return f"{v:+.1f}"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def lookup(led, key):
    cur = led
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None, False
    return cur, True


def update_map(led):
    tok = re.compile(r"\[\[([A-Za-z0-9_.]+) = ([^\]]*)\]\]")
    changed = 0; missing = []
    if not os.path.isdir(MAP):
        return 0, ["map dir missing"]
    for name in sorted(os.listdir(MAP)):
        if not name.endswith(".md"):
            continue
        p = os.path.join(MAP, name)
        txt = open(p, encoding="utf-8").read()

        def rep(m):
            nonlocal changed
            key = m.group(1)
            v, ok = lookup(led, key)
            if not ok:
                missing.append(f"{name}: {key}"); return m.group(0)
            new = fmt(key, v)
            if new != m.group(2):
                changed += 1
            return f"[[{key} = {new}]]"
        out = tok.sub(rep, txt)
        if out != txt:
            open(p, "w", encoding="utf-8").write(out)
    return changed, missing


def main():
    spec = json.load(open("fade_book_spec.json", encoding="utf-8"))
    book = json.load(open(BOOK, encoding="utf-8"))
    live = live_side(book, spec)
    arch, cmeta = archive_side(spec)
    court = court_side()
    led = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "corpus": cmeta, "book_records": len(book), "active": ACTIVE, "strategies": {}}
    for s in sorted(set(list(live) + list(arch))):
        lv = live.get(s) or {}
        ar = arch.get(s) or {}
        cap = None; cap_note = None
        if lv.get("units", 0) >= 20 and isinstance(ar.get("per_day"), (int, float)) and ar["per_day"] > 0 and lv.get("unit") == "days":
            cap = round(lv["unit_mean"] / ar["per_day"], 2)
        else:
            cap_note = ("needs >= 20 live days" if lv.get("units", 0) < 20 else "no positive archive cell to capture")
        led["strategies"][s] = {"active": s in ACTIVE, "live": lv, "archive": ar,
                                "court": {"standing": court.get(s)}, "capture": {"ratio": cap, "note": cap_note}}
    os.makedirs("reports/performance", exist_ok=True)
    json.dump(led, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    L = [f"# RETURNS LEDGER - {led['generated_at']}", "",
         f"live from {BOOK} ({len(book)} records, the court's construction); archive from {CORPUS} "
         f"({cmeta.get('rows')} rows, last day {cmeta.get('last_day')}, {cmeta.get('basis')}).", "",
         "| strategy | live n | %/trade | win | best removed | unit | units | own mean | shared | t vs control | halves | $ | archive %/day (pool) | t vs pool | archive halves | court |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = ACTIVE + sorted(s for s in led["strategies"] if s not in ACTIVE)
    for s in order:
        if s not in led["strategies"]:
            continue
        x = led["strategies"][s]; lv, ar = x["live"], x["archive"]
        L.append(f"| {s}{'' if x['active'] else ' (retired)'} | {lv.get('n_closed', 0)} | {fmt('per_trade', lv.get('per_trade'))} | "
                 f"{fmt('win', lv.get('win'))} | {fmt('best_removed_per_trade', lv.get('best_removed_per_trade'))} | {lv.get('unit', '-')} | "
                 f"{lv.get('units', 0)} | {fmt('unit_mean', lv.get('unit_mean'))} | {lv.get('shared_units', 0)} | "
                 f"{fmt('t_vs_control', lv.get('t_vs_control'))} | {fmt('h1', lv.get('h1'))}/{fmt('h2', lv.get('h2'))} | "
                 f"{fmt('total_usd', lv.get('total_usd'))} | {fmt('per_day', ar.get('per_day'))} ({fmt('per_day', ar.get('pool_per_day_same_days'))}) | "
                 f"{fmt('t_vs_pool', ar.get('t_vs_pool'))} | {fmt('h1', ar.get('h1'))}/{fmt('h2', ar.get('h2'))} | {x['court'].get('standing') or '-'} |")
    L += ["", "Reading the table: live units are the court's units (days, or weeks for the weekly structures and the student family); "
              "t vs control uses the court's symmetric trim once 8 units are shared; 'best removed' is the per-trade mean without the "
              "single best trade; archive cells are on the executable basis and are day means over the cell's own days with the pool "
              "on those same days beside them. A number without its n is not evidence; every row carries both."]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:4] + L[6:6 + len(order)]))
    if "--update-map" in sys.argv:
        ch, miss = update_map(led)
        print(f"map update: {ch} value(s) refreshed" + (f"; UNRESOLVED keys: {miss}" if miss else ""))
    print(f"written {OUT_JSON} and {OUT_MD}")


if __name__ == "__main__":
    main()

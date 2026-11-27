"""Paper lab (owner, 2026-11-27: trade several strategies on the practice account and log every setup in full).
Two books beside the S26 book, each on its own instruments, every setup and result journaled under reports/paper_lab/
with a chart and sent to Telegram. Pre-registered in reports/paper_lab/PREREGISTRATION.md.
S26X: the S26 rule (fx_s26_alerts.Market, unchanged) on seven USD pairs; model record plus OANDA PRACTICE orders
through the risk engine (0.5% risk, broker stop, 2R take-profit, 10-trading-day exit), tagged lab_s26x.
DIP: the idx_gold_2026-11 R1 rule (Wilder RSI(2) < 10 and close above its 200-day average at the 16:00 New York close;
buy at the ask open of the 16:00 bar; sell at the bid open of the 16:00 bar after the first later close above the 5-day
average; no stop) on SPX500_USD and NAS100_USD, MODEL record only: this practice account lists currencies only."""
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import fx_s26_alerts as s26

S26X_PAIRS = ("GBP_USD", "AUD_USD", "NZD_USD", "USD_CHF", "USD_CAD", "USD_NOK", "USD_SEK")
S26X_SLIP = {"GBP_USD": 0.00019, "AUD_USD": 0.00013, "NZD_USD": 0.00015, "USD_CHF": 0.00015, "USD_CAD": 0.00018,
             "USD_NOK": 0.00397, "USD_SEK": 0.00368}
DIP_INST = ("SPX500_USD", "NAS100_USD")
START = "2026-11-27"
DIP_NOTIONAL = 25_000.0
DIP_FIN = {"SPX500_USD": 1.768 / 7229.0, "NAS100_USD": 6.436 / 26242.0}
TAG = "lab_s26x"
RISK_FRAC = 0.005
H = 3600 * 10**9
NYZ = "America/New_York"
LAB = os.environ.get("LAB_DIR", "reports/paper_lab")
STATE = os.path.join(LAB, "state.json")
EVENTS = os.path.join(LAB, "events.jsonl")
JDIR = os.path.join(LAB, "journal")
DRY = os.environ.get("DRY_RUN", "") == "1"
PLACE = os.environ.get("PLACE_ORDERS", "") == "1" and not DRY
if DRY and os.environ.get("LAB_START"):
    START = os.environ["LAB_START"]
DIP_START = S26X_START = START
DIP_NOTE = "model paper trade at live OANDA prices (this practice account cannot trade index CFDs, so no order is placed)"

s26.PIP.update({p: 1e-4 for p in S26X_PAIRS})
s26.SLIP.update(S26X_SLIP)


def tg(text, png=None):
    s26.tg_send(text, png)


def event(kind, d):
    os.makedirs(LAB, exist_ok=True)
    with open(EVENTS, "a") as f:
        f.write(json.dumps({"event": kind, **d, "logged_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}) + "\n")


def load():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"scanned": {}, "dip_done": {}, "trades": [], "guard": {}, "weekly": ""}


def ny_ns(days, hh):
    d = pd.DatetimeIndex(days) + pd.Timedelta(hours=hh)
    return d.tz_localize(NYZ).tz_convert("UTC").as_unit("ns").asi8.astype(np.int64)


def wilder_value(ag, al):
    return 100.0 - 100.0 / (1.0 + ag / al) if al > 0 else 100.0


def rsi2(c):
    out = np.full(len(c), np.nan)
    if len(c) < 3:
        return out
    dlt = np.diff(c)
    g, l = np.clip(dlt, 0, None), np.clip(-dlt, 0, None)
    ag, al = (g[0] + g[1]) / 2, (l[0] + l[1]) / 2
    out[2] = wilder_value(ag, al)
    for k in range(2, len(dlt)):
        ag, al = (ag + g[k]) / 2, (al + l[k]) / 2
        out[k + 1] = wilder_value(ag, al)
    return out


class Dip:
    """Daily closes at the 16:00 New York clock from H1 bid/ask, as idx_gold_2026-11 code/common.py Inst._daily."""

    def __init__(self, h1):
        df = h1.sort_values("t").drop_duplicates("t").reset_index(drop=True)
        ny = pd.DatetimeIndex(pd.to_datetime(df["t"].to_numpy(np.int64), unit="ns", utc=True)).tz_convert(NYZ)
        dow, hr = ny.dayofweek, ny.hour
        drop = np.asarray(((dow == 4) & (hr >= 17)) | (dow == 5) | ((dow == 6) & (hr < 17)))
        df = df[~drop].reset_index(drop=True)
        self.t = df["t"].to_numpy(np.int64)
        for c in ("bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"):
            setattr(self, c, df[c].to_numpy(float))
        n = self.n = len(self.t)
        self.stale = (self.bid_o == self.bid_h) & (self.bid_h == self.bid_l) & (self.bid_l == self.bid_c)
        nxt = np.full(n + 1, n, dtype=np.int64)
        for j in range(n - 1, -1, -1):
            nxt[j] = j if not self.stale[j] else nxt[j + 1]
        mid_c = (self.bid_c + self.ask_c) / 2
        loc = pd.DatetimeIndex(pd.to_datetime(self.t, unit="ns", utc=True)).tz_convert(NYZ).tz_localize(None)
        self.days = pd.bdate_range(loc[0].normalize(), loc[-1].normalize())
        nd = len(self.days)
        self.day_str = [str(d.date()) for d in self.days]
        self.idx = {s: i for i, s in enumerate(self.day_str)}
        self.t15, self.t16 = ny_ns(self.days, 15), ny_ns(self.days, 16)
        prev = pd.DatetimeIndex(np.r_[self.days[0] - pd.offsets.BDay(1), self.days[:-1]])
        win0 = ny_ns(prev, 16)
        j15 = np.searchsorted(self.t, self.t15)
        has15 = (j15 < n) & (self.t[np.minimum(j15, n - 1)] == self.t15)
        stale15 = np.zeros(nd, bool)
        stale15[has15] = self.stale[j15[has15]]
        nbars = np.searchsorted(self.t, self.t16) - np.searchsorted(self.t, win0)
        real = has15 & ~stale15 & (nbars >= 4)
        close = np.full(nd, np.nan)
        close[real] = mid_c[j15[real]]
        first_real = int(np.argmax(real)) if real.any() else nd
        s = pd.Series(close)
        s.iloc[first_real:] = s.iloc[first_real:].ffill()
        self.close, self.real = s.to_numpy(), real
        self.rsi = np.full(nd, np.nan)
        if nd - first_real >= 3:
            self.rsi[first_real:] = rsi2(self.close[first_real:])
        self.sma200 = s.rolling(200, min_periods=200).mean().to_numpy()
        self.sma5 = s.rolling(5, min_periods=5).mean().to_numpy()
        valid = real & np.isfinite(self.sma200) & np.isfinite(self.rsi)
        self.entry = valid & (self.rsi < 10) & (self.close > self.sma200)
        self.exit = real & np.isfinite(self.sma5) & (self.close > self.sma5)
        j16 = np.searchsorted(self.t, self.t16)
        self.fill = np.where(j16 < n, nxt[np.minimum(j16, n)], n)
        self.fill[self.fill >= n] = -1
        self.nights = np.where(self.days.dayofweek.to_numpy() == 4, 3, 1)


def uk(t_ns):
    return s26.uk(int(t_ns))


def journal(tr, png=None):
    os.makedirs(JDIR, exist_ok=True)
    if png:
        with open(os.path.join(JDIR, tr["id"] + ".png"), "wb") as f:
            f.write(png)
    L = [f"# {tr['id']}", "", f"Book: {tr['book']}  |  status: {tr['status']}", ""]
    if tr["book"] == "DIP":
        L += ["Setup (16:00 New York close, mid prices):"] + [f"- {k}: {v}" for k, v in tr["setup"].items()]
        L += ["", f"Note: {DIP_NOTE}.", ""]
        if "fill" in tr:
            L += [f"Entry: bought at the ask {tr['fill']:.2f} at {uk(tr['fill_t'])} UK (spread {tr['spread_in']:.2f})."]
        if "exit_setup" in tr:
            L += ["Exit signal:"] + [f"- {k}: {v}" for k, v in tr["exit_setup"].items()]
        if tr["status"] == "closed":
            L += [f"Exit: sold at the bid {tr['exit']:.2f} at {uk(tr['exit_t'])} UK.",
                  f"Result: {100 * tr['ret']:+.3f}% before financing, est. financing {100 * tr['fin']:.3f}% over {tr['nights_held']} nights,"
                  f" net {100 * tr['net']:+.3f}%, {tr['usd']:+,.2f} USD on {DIP_NOTIONAL:,.0f} notional.",
                  f"Worst point {100 * tr['mae']:+.2f}%, best point {100 * tr['mfe']:+.2f}% (bid, while held)."]
    else:
        L += ["Setup (daily bar, mid prices):"] + [f"- {k}: {v}" for k, v in tr["setup"].items()]
        L += ["", "Model record (fill at the 18:00 New York open, stop first, 2R target, 10-day exit, excl. commission and financing):"]
        for k in ("fill", "D", "spread_in", "target", "exit_kind", "exit", "R", "mae_R", "mfe_R", "reason"):
            if k in tr:
                L.append(f"- {k}: {tr[k]}")
        b = tr.get("broker")
        if b:
            L += ["", "OANDA practice order:"] + [f"- {k}: {v}" for k, v in b.items()]
    with open(os.path.join(JDIR, tr["id"] + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def excursion(mk, tr):
    k0 = int(np.searchsorted(mk.t, tr["fill_t"]))
    k1 = int(np.searchsorted(mk.t, tr["exit_t"]))
    if tr["dir"] == 1:
        lo, hi = mk.bid_l[k0:k1 + 1].min(), mk.bid_h[k0:k1 + 1].max()
        return round((lo - tr["fill"]) / tr["D"], 3), round((hi - tr["fill"]) / tr["D"], 3)
    lo, hi = mk.ask_l[k0:k1 + 1].min(), mk.ask_h[k0:k1 + 1].max()
    return round((tr["fill"] - hi) / tr["D"], 3), round((tr["fill"] - lo) / tr["D"], 3)


def s26x_scan(st, pair, mk, now):
    for tr in [x for x in st["trades"] if x["book"] == "S26X" and x["pair"] == pair and x["status"] in ("pending", "open")]:
        prev = tr["status"]
        res = mk.update(tr)
        if not res:
            if tr["status"] != prev:
                event("model_filled", tr)
                journal(tr)
            continue
        if res == "closed":
            tr["mae_R"], tr["mfe_R"] = excursion(mk, tr)
            tg(f"LAB S26X model trade closed: {pair} {'long' if tr['dir'] == 1 else 'short'} {tr['exit_kind']} at "
               f"{s26.fmt(pair, tr['exit'])}, {tr['R']:+.2f} R (model, excl. commission and financing).")
        elif res == "skipped":
            tg(f"LAB S26X {pair}: model entry skipped ({tr['reason']}).")
        event(res, tr)
        journal(tr)
    closed = np.flatnonzero(mk.d_end <= now)
    if not len(closed):
        return
    last = st["scanned"].get(pair, "")
    todo = [int(t) for t in closed if str(mk.d_date[t]) >= S26X_START and str(mk.d_date[t]) > last]
    for t in (todo[-10:] if last else todo):
        td = str(mk.d_date[t])
        st["scanned"][pair] = td
        s = mk.signal(t)
        if not s:
            event("scan", {"book": "S26X", "pair": pair, "td": td, "signal": False})
            continue
        if any(x["book"] == "S26X" and x["pair"] == pair and (x["status"] in ("pending", "open") or
               (x["status"] == "closed" and x["exit_t"] > s["sig_t"])) for x in st["trades"]):
            event("signal_ignored_one_open", {"book": "S26X", "pair": pair, **s})
            continue
        entry_t = mk.entry_time(td)
        last_c = mk.ask_c[-1] if s["dir"] == 1 else mk.bid_c[-1]
        D_est = (last_c - s["stop"]) * s["dir"]
        late = now > entry_t + 2 * H
        setup = {"signal day": td, "pattern": s["kind"], "direction": "LONG" if s["dir"] == 1 else "SHORT",
                 "swing level": s26.fmt(pair, s["level"]), "stop (signal bar extreme)": s26.fmt(pair, s["stop"]),
                 "signal bar O/H/L/C": " / ".join(s26.fmt(pair, s[k]) for k in ("o", "h", "l", "c")),
                 "daily ATR(14)": s26.fmt(pair, s["atrd"]), "level tolerance (0.25 ATR)": s26.fmt(pair, 0.25 * s["atrd"]),
                 "close beyond level (ATR)": round((s["c"] - s["level"]) * s["dir"] / s["atrd"], 2),
                 "last price at alert": s26.fmt(pair, last_c), "stop distance est. (pips)": round(D_est / 1e-4, 1),
                 "planned entry": f"{uk(entry_t)} UK (18:00 New York)", "order deadline": f"{uk(entry_t + 2 * H)} UK",
                 "seen late (model record only)": late}
        tr = {"id": f"S26X_{pair}_{td}", "book": "S26X", "pair": pair, "dir": s["dir"], "stop": s["stop"], "level": s["level"],
              "kind": s["kind"], "signal_td": td, "sig_t": s["sig_t"], "entry_t": entry_t, "status": "pending", "setup": setup}
        st["trades"].append(tr)
        png = s26.chart(mk, pair, s, last_c)
        journal(tr, png)
        event("alert", tr)
        tg(f"LAB S26X SETUP - {pair} {'BUY' if s['dir'] == 1 else 'SELL'} (paper, OANDA practice)\n"
           f"{s['kind']} at daily {'support' if s['dir'] == 1 else 'resistance'} {s26.fmt(pair, s['level'])}, signal day {td}.\n"
           f"Stop {s26.fmt(pair, s['stop'])} (about {D_est / 1e-4:.0f} pips), target 2 x the stop distance, 10-day time exit.\n"
           + (f"Practice order at {uk(entry_t)} UK (18:00 New York)." if not late else "Seen too late to order: model record only.")
           + "\nLive forward test; this rule family showed no edge on 2005-2014 history.", png)
        if mk.update(tr) == "closed":
            tr["mae_R"], tr["mfe_R"] = excursion(mk, tr)
        if tr["status"] != "pending":
            event(tr["status"], tr)
            journal(tr)


def s26x_broker(st, now):
    import fx_oanda_orders as O
    import fx_risk_engine as risk
    br = O.Practice()
    acct = br.summary()
    closed_now = []
    for tr in st["trades"]:
        b = tr.get("broker")
        if tr["book"] != "S26X" or not b or b.get("status") != "open":
            continue
        x = br.trade(b["trade_id"])
        if x["state"] == "OPEN" and now >= b["time_exit_t"]:
            br.close(b["trade_id"])
            x = br.trade(b["trade_id"])
            b["closed_by"] = "time exit (10 trading days)"
        if x["state"] == "CLOSED":
            pl = float(x.get("realizedPL", 0) or 0)
            b.update({"status": "closed", "close_time": x.get("closeTime"), "close_price": float(x.get("averageClosePrice", 0) or 0),
                      "realized_pl": pl, "financing": float(x.get("financing", 0) or 0),
                      "R": round(pl / b["risk_usd"], 3) if b.get("risk_usd") else None})
            closed_now.append((pd.Timestamp(b["close_time"]).value, pl))
            event("broker_closed", {"id": tr["id"], **b})
            journal(tr)
            tg(f"LAB S26X practice trade closed: {tr['pair']} {'long' if tr['dir'] == 1 else 'short'} at "
               f"{s26.fmt(tr['pair'], b['close_price'])}, P&L {pl:+,.2f} USD ({b['R']:+.2f} R incl. spread and financing)"
               f"{' - ' + b['closed_by'] if b.get('closed_by') else ''}.")
    bal, nav = float(acct["balance"]), float(acct["NAV"])
    st["guard"] = g = risk.refresh(st.get("guard", {}), bal, nav, now, closed_now)
    for tr in st["trades"]:
        if tr["book"] != "S26X" or tr.get("broker") or tr["status"] not in ("pending", "open") or now < tr["entry_t"]:
            continue
        pair, sg = tr["pair"], tr["dir"]
        frac, why = 0.0, "job ran more than 2 hours after 18:00 New York"
        if now <= tr["entry_t"] + 2 * H:
            held = [{"instrument": o["pair"], "direction": o["dir"], "risk_usd": o["broker"]["risk_usd"]}
                    for o in st["trades"] if o["book"] == "S26X" and (o.get("broker") or {}).get("status") == "open"]
            frac, why = risk.assess({"nav": nav, "start": g["B0"], "paused": g.get("paused", False), "open": held},
                                    g["prague_ref"], {"instrument": pair, "direction": sg, "risk_usd": RISK_FRAC * bal})
        if frac > 0:
            bid, ask, tradeable = br.price(pair)
            px, sp = (ask if sg == 1 else bid), ask - bid
            D = (px - tr["stop"]) * sg
            if not tradeable or D <= 0 or D < 8 * sp:
                frac, why = 0.0, ("market not tradeable" if not tradeable else
                                  "price already through the stop" if D <= 0 else "stop distance below 8 x spread")
            else:
                per_unit = D if pair.endswith("_USD") else D / px
                units = int(frac * RISK_FRAC * bal / per_unit)
                f = br.market(pair, units * sg, tr["stop"], tr["id"], tag=TAG)
                if not f["filled"]:
                    frac, why = 0.0, f"order not filled: {f['reason']}"
                else:
                    Df = (f["fill"] - tr["stop"]) * sg
                    tp = f["fill"] + 2 * Df * sg
                    br.set_tp(pair, f["trade_id"], tp)
                    tr["broker"] = {"status": "open", "trade_id": f["trade_id"], "fill": f["fill"], "fill_time": f["time"],
                                    "units": f["units"], "stop": tr["stop"], "tp": tp, "D": Df, "spread_at_order": sp,
                                    "risk_usd": abs(f["units"]) * (Df if pair.endswith("_USD") else Df / f["fill"]),
                                    "commission": f["commission"],
                                    "time_exit_t": s26.Market.time_exit_t(None, pd.Timestamp(f["time"]).value),
                                    **({"size_fraction": frac, "size_cut": why} if frac < 1 else {})}
                    event("broker_filled", {"id": tr["id"], **tr["broker"]})
                    journal(tr)
                    tg(f"LAB S26X practice order FILLED: {pair} {'BUY' if sg == 1 else 'SELL'} {abs(f['units']):,} units at "
                       f"{s26.fmt(pair, f['fill'])}; stop {s26.fmt(pair, tr['stop'])}, target {s26.fmt(pair, tp)} "
                       f"({Df / 1e-4:.0f} pips risk, {100 * frac * RISK_FRAC:g}% of the balance). "
                       f"Time exit {uk(tr['broker']['time_exit_t'])} UK.")
                    continue
        tr["broker"] = {"status": "not_placed", "reason": why}
        event("broker_not_placed", {"id": tr["id"], **tr["broker"]})
        journal(tr)
        tg(f"LAB S26X {pair}: practice order NOT placed - {why}.")


def dip_chart(dp, inst, d):
    import io

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a = max(0, d - 119)
    x = np.arange(d - a + 1)
    fig, (ax, ar) = plt.subplots(2, 1, figsize=(9, 6), dpi=110, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    ax.plot(x, dp.close[a:d + 1], color="black", linewidth=1, label="16:00 NY close")
    ax.plot(x, dp.sma200[a:d + 1], color="#1565c0", linewidth=1, label="200-day average")
    ax.plot(x, dp.sma5[a:d + 1], color="#ef6c00", linewidth=1, label="5-day average (exit line)")
    ax.scatter([d - a], [dp.close[d]], color="#2e7d32", zorder=5, label="signal close")
    ax.set_title(f"{inst} - RSI(2) dip-buy signal {dp.day_str[d]}")
    ax.legend(loc="best", fontsize=8)
    ar.plot(x, dp.rsi[a:d + 1], color="#6a1b9a", linewidth=1)
    ar.axhline(10, color="#c62828", linewidth=0.8, linestyle="--")
    ar.set_ylim(0, 100)
    ar.set_ylabel("RSI(2)")
    ar.set_xticks([0, d - a])
    ar.set_xticklabels([dp.day_str[a], dp.day_str[d]])
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def dip_resolve(tr, dp):
    if tr["status"] == "pending":
        d = dp.idx.get(tr["sig_day"])
        k = dp.fill[d] if d is not None else -1
        if k < 0:
            return False
        tr.update({"status": "open", "fill": float(dp.ask_o[k]), "fill_t": int(dp.t[k]),
                   "spread_in": float(dp.ask_o[k] - dp.bid_o[k])})
        event("dip_filled", tr)
        journal(tr)
        tg(f"LAB DIP model entry: {tr['inst']} bought at the ask {tr['fill']:.2f} at {uk(tr['fill_t'])} UK "
           f"({DIP_NOTIONAL:,.0f} USD notional). Exit at the first 16:00 New York close above the 5-day average.")
        return True
    if tr["status"] == "exit_pending":
        d = dp.idx.get(tr["exit_day"])
        k = dp.fill[d] if d is not None else -1
        if k < 0:
            return False
        k0 = int(np.searchsorted(dp.t, tr["fill_t"]))
        d0 = dp.idx[tr["sig_day"]]
        nights = int(dp.nights[d0:d].sum())
        ex = float(dp.bid_o[k])
        ret = ex / tr["fill"] - 1
        fin = DIP_FIN[tr["inst"]] * nights
        tr.update({"status": "closed", "exit": ex, "exit_t": int(dp.t[k]), "ret": ret, "nights_held": nights, "fin": fin,
                   "net": ret - fin, "usd": round(DIP_NOTIONAL * (ret - fin), 2),
                   "mae": float(dp.bid_l[k0:k + 1].min() / tr["fill"] - 1), "mfe": float(dp.bid_h[k0:k + 1].max() / tr["fill"] - 1)})
        event("dip_closed", tr)
        journal(tr)
        tg(f"LAB DIP model trade closed: {tr['inst']} sold at the bid {ex:.2f}, {100 * ret:+.2f}% "
           f"(net of est. financing {100 * tr['net']:+.2f}%, {tr['usd']:+,.2f} USD on {DIP_NOTIONAL:,.0f}). {DIP_NOTE}.")
        return True
    return True


def dip_scan(st, inst, dp, now):
    def current():
        return next((x for x in st["trades"] if x["book"] == "DIP" and x["inst"] == inst and x["status"] != "closed"), None)
    tr = current()
    if tr and not dip_resolve(tr, dp):
        return
    done = st["dip_done"].get(inst, "")
    for d, day in enumerate(dp.day_str):
        if day < DIP_START or day <= done or dp.t16[d] + 5 * 60 * 10**9 > now:
            continue
        tr = current()
        if tr and tr["status"] != "open":
            break
        if tr and dp.exit[d] and dp.t16[d] > tr["fill_t"]:
            tr.update({"status": "exit_pending", "exit_day": day,
                       "exit_setup": {"exit day": day, "close": round(float(dp.close[d]), 2),
                                      "5-day average": round(float(dp.sma5[d]), 2), "RSI(2)": round(float(dp.rsi[d]), 2)}})
            event("dip_exit_signal", tr)
            journal(tr)
            st["dip_done"][inst] = day
            if not dip_resolve(tr, dp):
                break
            continue
        if tr is None and dp.entry[d]:
            other = any(x["book"] == "DIP" and x["inst"] != inst and x["status"] != "closed" for x in st["trades"])
            setup = {"signal day": day, "close": round(float(dp.close[d]), 2), "RSI(2)": round(float(dp.rsi[d]), 2),
                     "200-day average": round(float(dp.sma200[d]), 2),
                     "close above 200-day": f"{100 * (dp.close[d] / dp.sma200[d] - 1):+.2f}%",
                     "5-day average": round(float(dp.sma5[d]), 2),
                     "last 5 closes": ", ".join(f"{v:.2f}" for v in dp.close[max(0, d - 4):d + 1]),
                     "other index already held (a one-slot book would skip this)": other}
            tr = {"id": f"DIP_{inst}_{day}", "book": "DIP", "inst": inst, "sig_day": day, "status": "pending", "setup": setup}
            st["trades"].append(tr)
            png = dip_chart(dp, inst, d)
            journal(tr, png)
            event("dip_signal", tr)
            tg(f"LAB DIP SETUP - {inst} BUY (paper model)\nRSI(2) {setup['RSI(2)']} below 10 with the close "
               f"{setup['close above 200-day']} above its 200-day average, signal close {day}.\n"
               f"Model buys at the 16:00 New York open, sells at the first close above the 5-day average; no stop.\n"
               f"{DIP_NOTE}.", png)
            st["dip_done"][inst] = day
            if not dip_resolve(tr, dp):
                break
            continue
        st["dip_done"][inst] = day


def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 2 or x.std(ddof=1) == 0:
        return None
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def scoreboard(st, now):
    tr = st["trades"]
    m = [x["R"] for x in tr if x["book"] == "S26X" and x["status"] == "closed"]
    b = [x["broker"] for x in tr if x["book"] == "S26X" and (x.get("broker") or {}).get("status") == "closed"]
    dpx = [x for x in tr if x["book"] == "DIP" and x["status"] == "closed"]
    t1, t3 = tstat(m), tstat([x["net"] for x in dpx])
    L = ["# Paper lab scoreboard (OANDA practice, paper only)", "", f"Updated {uk(now)} UK.", "",
         "S26X (pin bar / engulfing at daily support or resistance, seven USD pairs):",
         f"- model trades closed: {len(m)}, wins {sum(r > 0 for r in m)}, mean {np.mean(m) if m else 0:+.3f} R, "
         f"total {sum(m):+.2f} R, t {t1:.2f}" if t1 is not None else
         f"- model trades closed: {len(m)}, total {sum(m):+.2f} R",
         f"- practice trades closed: {len(b)}, P&L {sum(x['realized_pl'] for x in b):+,.2f} USD",
         f"- judged once, at 100 closed model trades (PREREGISTRATION.md): pass only if mean R > 0 with t >= 2.0", "",
         "DIP (RSI(2) dip-buy, US500 and US100, model only):",
         f"- trades closed: {len(dpx)}, wins {sum(x['net'] > 0 for x in dpx)}, mean net "
         f"{100 * np.mean([x['net'] for x in dpx]) if dpx else 0:+.3f}%, total {sum(x['usd'] for x in dpx):+,.2f} USD"
         + (f", t {t3:.2f}" if t3 is not None else ""),
         "- implementation check only: no edge claim from this record (PREREGISTRATION.md)", "", "Open or pending:"]
    for x in tr:
        if x["status"] in ("pending", "open", "exit_pending"):
            L.append(f"- {x['id']}: {x['status']}" + (f", practice order {x['broker']['status']}" if x.get("broker") else ""))
    return "\n".join(L) + "\n"


def run():
    os.makedirs(LAB, exist_ok=True)
    st = load()
    now = pd.Timestamp.now(tz="UTC").value
    for pair in S26X_PAIRS:
        try:
            mk = s26.Market(s26.fetch_h1(pair))
            s26x_scan(st, pair, mk, now)
        except Exception as e:
            event("scan_error", {"book": "S26X", "pair": pair, "error": f"{type(e).__name__}: {str(e)[:300]}"})
            print(pair, "error:", e)
    for inst in DIP_INST:
        try:
            dip_scan(st, inst, Dip(s26.fetch_h1(inst)), now)
        except Exception as e:
            event("scan_error", {"book": "DIP", "inst": inst, "error": f"{type(e).__name__}: {str(e)[:300]}"})
            print(inst, "error:", e)
    if PLACE:
        try:
            s26x_broker(st, now)
        except Exception as e:
            event("broker_error", {"error": str(e)[:500]})
            tg(f"LAB practice order job ERROR: {str(e)[:300]}. Open practice trades keep their broker stops.")
            print("broker error:", e)
    sb = scoreboard(st, now)
    with open(os.path.join(LAB, "SCOREBOARD.md"), "w", encoding="utf-8") as f:
        f.write(sb)
    wk = pd.Timestamp(now, tz="UTC")
    tag = f"{wk.isocalendar().year}-W{wk.isocalendar().week:02d}"
    if ((wk.dayofweek == 4 and wk.hour >= 22) or wk.dayofweek >= 5) and st.get("weekly") != tag:
        st["weekly"] = tag
        tg("PAPER LAB weekly\n" + sb.split("\n", 4)[-1][:3500])
    if not DRY:
        with open(STATE, "w") as f:
            json.dump(st, f, indent=1)
    else:
        print(sb)


if __name__ == "__main__":
    run()

"""S26 paper alerts: pin bar / engulfing at a daily swing support or resistance (fx_chart_screen_2026-11 v2 base rule),
EUR_USD and USD_JPY, OANDA practice data read-only. Sends a Telegram alert with a chart; the owner places the trade by hand.
Keeps the model paper record in reports/fx_alerts/. Places no orders."""
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

PAIRS = ("EUR_USD", "USD_JPY")
PIP = {"EUR_USD": 1e-4, "USD_JPY": 1e-2}
SLIP = {"EUR_USD": 0.00005, "USD_JPY": 0.005}
NYZ = "America/New_York"
UKZ = "Europe/London"
TIME_DAYS = 10
RISK_FRAC = 0.005
HOST = "https://api-fxpractice.oanda.com"
STATE_DIR = os.environ.get("ALERT_DIR", "reports/fx_alerts")
STATE = os.path.join(STATE_DIR, "s26_state.json")
EVENTS = os.path.join(STATE_DIR, "s26_events.jsonl")
DRY = os.environ.get("DRY_RUN", "") == "1"
PLACE = os.environ.get("PLACE_ORDERS", "") == "1" and not DRY


def atr_wilder(h, l, c, n=14):
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    a = tr[:n].mean()
    out[n] = a
    for i in range(n + 1, len(c)):
        a = (a * (n - 1) + tr[i - 1]) / n
        out[i] = a
    return out


def bull_pin(o, h, l, c):
    rng = h - l
    lw = min(o, c) - l
    return lw >= 2 * abs(c - o) and lw >= 0.6 * rng and c >= l + (2.0 / 3.0) * rng


def bear_pin(o, h, l, c):
    rng = h - l
    uw = h - max(o, c)
    return uw >= 2 * abs(c - o) and uw >= 0.6 * rng and c <= h - (2.0 / 3.0) * rng


def bull_engulf(o1, c1, o, c):
    return c1 < o1 and c > o and o <= c1 and c >= o1


def bear_engulf(o1, c1, o, c):
    return c1 > o1 and c < o and o >= c1 and c <= o1


def swings(x, low):
    n = len(x)
    out = np.zeros(n, bool)
    for i in range(2, n - 2):
        if low:
            out[i] = x[i] < x[i - 2] and x[i] < x[i - 1] and x[i] < x[i + 1] and x[i] < x[i + 2]
        else:
            out[i] = x[i] > x[i - 2] and x[i] > x[i - 1] and x[i] > x[i + 1] and x[i] > x[i + 2]
    return out


def ns_from_local(naive_local):
    idx = pd.DatetimeIndex(naive_local).tz_localize(NYZ, ambiguous="raise", nonexistent="raise").tz_convert("UTC")
    return idx.as_unit("ns").asi8.astype(np.int64)


class Market:
    def __init__(self, h1):
        h1 = h1.sort_values("t").reset_index(drop=True)
        t = h1["t"].to_numpy(np.int64)
        loc = pd.DatetimeIndex(pd.to_datetime(t, unit="ns", utc=True)).tz_convert(NYZ).tz_localize(None).as_unit("ns")
        td = (loc + pd.Timedelta(hours=7)).normalize().values.astype("datetime64[D]")
        keep = np.is_busday(td)
        h1, t, loc, td = h1[keep].reset_index(drop=True), t[keep], loc[keep], td[keep]
        self.t, self.loc, self.td, self.n = t, loc, td, len(t)
        for c in ("bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"):
            setattr(self, c, h1[c].to_numpy(float))
        mo, mh = (self.bid_o + self.ask_o) / 2, (self.bid_h + self.ask_h) / 2
        ml, mc = (self.bid_l + self.ask_l) / 2, (self.bid_c + self.ask_c) / 2
        self.ny_hour = loc.hour.values.astype(np.int64)
        st = np.flatnonzero(np.r_[True, td[1:] != td[:-1]])
        last = np.r_[st[1:] - 1, self.n - 1]
        self.d_first, self.d_last = st, last
        self.d_o, self.d_c = mo[st], mc[last]
        self.d_h, self.d_l = np.maximum.reduceat(mh, st), np.minimum.reduceat(ml, st)
        self.d_date = td[st]
        self.d_end = ns_from_local(pd.DatetimeIndex(self.d_date.astype("datetime64[ns]")) + pd.Timedelta(hours=17))
        self.d_atr = atr_wilder(self.d_h, self.d_l, self.d_c)
        self.il = np.flatnonzero(swings(self.d_l, True))
        self.ih = np.flatnonzero(swings(self.d_h, False))

    def signal(self, t):
        a = self.d_atr[t - 1] if t >= 1 else np.nan
        if not np.isfinite(a):
            return None
        tol = 0.25 * a
        o, h, l, c = self.d_o[t], self.d_h[t], self.d_l[t], self.d_c[t]
        o1, c1 = self.d_o[t - 1], self.d_c[t - 1]
        sigs = []
        bp, be = bull_pin(o, h, l, c), bull_engulf(o1, c1, o, c)
        if bp or be:
            lv = self.il[(self.il >= t - 60) & (self.il <= t - 3)]
            lev = self.d_l[lv]
            ok = (np.abs(l - lev) <= tol) & (c > lev)
            if ok.any():
                sigs.append({"dir": 1, "stop": float(l), "kind": "pin bar" if bp else "engulfing",
                             "level": float(lev[ok][np.argmin(np.abs(l - lev[ok]))])})
        sp, se = bear_pin(o, h, l, c), bear_engulf(o1, c1, o, c)
        if sp or se:
            lv = self.ih[(self.ih >= t - 60) & (self.ih <= t - 3)]
            lev = self.d_h[lv]
            ok = (np.abs(h - lev) <= tol) & (c < lev)
            if ok.any():
                sigs.append({"dir": -1, "stop": float(h), "kind": "pin bar" if sp else "engulfing",
                             "level": float(lev[ok][np.argmin(np.abs(h - lev[ok]))])})
        if len(sigs) != 1:
            return None
        s = sigs[0]
        s.update({"t": int(t), "td": str(self.d_date[t]), "sig_t": int(self.d_end[t]), "atrd": float(a),
                  "o": float(o), "h": float(h), "l": float(l), "c": float(c)})
        return s

    def entry_time(self, td):
        nxt = np.busday_offset(np.datetime64(td, "D"), 1, roll="raise")
        return int(ns_from_local([pd.Timestamp(nxt) - pd.Timedelta(days=1) + pd.Timedelta(hours=18)])[0])

    def fill_bar(self, entry_t):
        k = int(np.searchsorted(self.t, entry_t, side="left"))
        while k < self.n and 16 <= self.ny_hour[k] < 18:
            k += 1
        return k

    def time_exit_t(self, t_in):
        loc = pd.DatetimeIndex(pd.to_datetime([t_in], unit="ns", utc=True)).tz_convert(NYZ).tz_localize(None)
        td = (loc + pd.Timedelta(hours=7)).normalize().values.astype("datetime64[D]")
        shift = int((np.busday_offset(td, TIME_DAYS, roll="forward") - td).astype("timedelta64[D]").astype(np.int64)[0])
        return int(ns_from_local(loc + pd.Timedelta(days=shift))[0])

    def update(self, tr):
        """Advance one model trade on completed H1 bars: fill at the 18:00 NY open, then stop first, 2R target, 10-day exit."""
        sg = tr["dir"]
        if tr["status"] == "pending":
            k0 = self.fill_bar(tr["entry_t"])
            if k0 >= self.n:
                return None
            fill = self.ask_o[k0] if sg == 1 else self.bid_o[k0]
            sp = self.ask_o[k0] - self.bid_o[k0]
            D = (fill - tr["stop"]) * sg
            tr.update({"fill_t": int(self.t[k0]), "fill": float(fill), "D": float(D), "spread_in": float(sp)})
            if D <= 0 or D < 8 * sp:
                tr.update({"status": "skipped", "reason": "stop distance below 8 x spread" if D > 0 else "price already through the stop"})
                return "skipped"
            tr.update({"status": "open", "target": float(fill + 2 * D * sg), "time_exit_t": self.time_exit_t(int(self.t[k0]))})
        k0 = int(np.searchsorted(self.t, tr["fill_t"], side="left"))
        stop, tgt, kx = tr["stop"], tr["target"], int(np.searchsorted(self.t, tr["time_exit_t"], side="left"))
        op, lo, hi = (self.bid_o, self.bid_l, self.bid_h) if sg == 1 else (self.ask_o, self.ask_l, self.ask_h)
        for k in range(k0, min(kx, self.n)):
            st_open = op[k] <= stop if sg == 1 else op[k] >= stop
            tg_open = op[k] >= tgt if sg == 1 else op[k] <= tgt
            st_in = lo[k] <= stop if sg == 1 else hi[k] >= stop
            tg_in = hi[k] >= tgt if sg == 1 else lo[k] <= tgt
            if k == k0:
                st_open = tg_open = False
            if st_open:
                return self._close(tr, k, "stop", float(op[k]) - SLIP[tr["pair"]] * sg)
            if tg_open:
                return self._close(tr, k, "target", float(op[k]))
            if st_in:
                return self._close(tr, k, "stop", float(stop) - SLIP[tr["pair"]] * sg)
            if tg_in:
                return self._close(tr, k, "target", float(tgt))
        if kx < self.n:
            if (sg == 1 and op[kx] <= stop) or (sg == -1 and op[kx] >= stop):
                return self._close(tr, kx, "stop", float(op[kx]) - SLIP[tr["pair"]] * sg)
            return self._close(tr, kx, "time", float(op[kx]))
        return None

    def _close(self, tr, k, kind, px):
        tr.update({"status": "closed", "exit_kind": kind, "exit_t": int(self.t[k]), "exit": px,
                   "R": round((px - tr["fill"]) * tr["dir"] / tr["D"], 3)})
        return "closed"


def oanda_get(path):
    import requests
    r = requests.get(HOST + path, headers={"Authorization": "Bearer " + os.environ["OANDA_API_TOKEN"]}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_h1(pair, days=460):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rows, frm = [], start.strftime("%Y-%m-%dT%H:%M:%SZ")
    while True:
        c = oanda_get(f"/v3/instruments/{pair}/candles?granularity=H1&price=BA&count=5000&from={frm}")["candles"]
        for x in c:
            if not x["complete"]:
                continue
            b, a = x["bid"], x["ask"]
            rows.append((pd.Timestamp(x["time"]).value, float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"]),
                         float(a["o"]), float(a["h"]), float(a["l"]), float(a["c"])))
        if len(c) < 5000:
            break
        frm = c[-1]["time"]
    df = pd.DataFrame(rows, columns=["t", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"])
    df["t"] = df["t"].astype("int64")
    return df.drop_duplicates("t")


def uk(t_ns):
    return pd.Timestamp(t_ns, tz="UTC").tz_convert(UKZ).strftime("%a %d %b %H:%M")


def fmt(pair, x):
    return f"{x:.3f}" if pair == "USD_JPY" else f"{x:.5f}"


def chart(mk, pair, s, est_fill):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = s["t"]
    a = max(0, t - 59)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=110)
    for j, i in enumerate(range(a, t + 1)):
        o, h, l, c = mk.d_o[i], mk.d_h[i], mk.d_l[i], mk.d_c[i]
        col = "#2e7d32" if c >= o else "#c62828"
        ax.vlines(j, l, h, color=col, linewidth=0.8)
        ax.add_patch(plt.Rectangle((j - 0.35, min(o, c)), 0.7, max(abs(c - o), 1e-9), color=col,
                                   ec="black" if i == t else col, linewidth=1.2 if i == t else 0))
    D = (est_fill - s["stop"]) * s["dir"]
    tgt = est_fill + 2 * D * s["dir"]
    ax.axhline(s["level"], color="#1565c0", linestyle="--", linewidth=1, label=f"level {fmt(pair, s['level'])}")
    ax.axhline(s["stop"], color="#c62828", linewidth=1, label=f"stop {fmt(pair, s['stop'])}")
    ax.axhline(tgt, color="#2e7d32", linewidth=1, label=f"target ~{fmt(pair, tgt)}")
    ax.set_title(f"{pair} daily - {'LONG' if s['dir'] == 1 else 'SHORT'} - {s['kind']} at {'support' if s['dir'] == 1 else 'resistance'}")
    ax.set_xticks([0, t - a])
    ax.set_xticklabels([str(mk.d_date[a]), str(mk.d_date[t])])
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def tg_send(text, png=None):
    if DRY:
        print("[dry-run telegram]\n" + text)
        return
    import requests
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not tok or not chat:
        print("telegram secrets missing; message not sent")
        return
    if png:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendPhoto", data={"chat_id": chat, "caption": text[:1000]},
                          files={"photo": ("s26.png", png, "image/png")}, timeout=30)
    else:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": text}, timeout=30)
    print("telegram", r.status_code)


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"scanned": {}, "trades": []}


def log_event(ev):
    ev["logged_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(EVENTS, "a") as f:
        f.write(json.dumps(ev) + "\n")


def run_live():
    os.makedirs(STATE_DIR, exist_ok=True)
    st = load_state()
    now = pd.Timestamp.now(tz="UTC").value
    bal = None
    try:
        acct = os.environ.get("OANDA_ACCOUNT_ID", "")
        bal = float(oanda_get(f"/v3/accounts/{acct}/summary")["account"]["balance"]) if acct else None
    except Exception as e:
        print("balance read failed:", e)
    for pair in PAIRS:
        mk = Market(fetch_h1(pair))
        print(f"{pair}: {mk.n} H1 bars, last {pd.Timestamp(int(mk.t[-1]), tz='UTC')}")
        for tr in st["trades"]:
            if tr["pair"] == pair and tr["status"] in ("pending", "open"):
                res = mk.update(tr)
                if res:
                    log_event({"event": res, **tr})
                    if res == "closed":
                        tg_send(f"S26 model trade closed: {pair} {'long' if tr['dir'] == 1 else 'short'} "
                                f"{tr['exit_kind']} at {fmt(pair, tr['exit'])}, {tr['R']:+.2f} R (paper, excl. commission/financing).")
                    elif res == "skipped":
                        tg_send(f"S26 {pair}: model entry skipped ({tr['reason']}). Cancel the trade if you have not placed it.")
        closed = np.flatnonzero(mk.d_end <= now)
        if not len(closed):
            continue
        t = int(closed[-1])
        td = str(mk.d_date[t])
        if st["scanned"].get(pair, "") >= td:
            continue
        st["scanned"][pair] = td
        s = mk.signal(t)
        if not s:
            log_event({"event": "scan", "pair": pair, "td": td, "signal": False})
            continue
        entry_t = mk.entry_time(td)
        if any(x["pair"] == pair and x["status"] in ("pending", "open") for x in st["trades"]):
            log_event({"event": "signal_ignored_one_open", "pair": pair, **s})
            continue
        if now > entry_t + 2 * 3600 * 10**9:
            log_event({"event": "signal_missed_late_run", "pair": pair, **s})
            continue
        last_c = (mk.ask_c[-1] if s["dir"] == 1 else mk.bid_c[-1])
        D_est = (last_c - s["stop"]) * s["dir"]
        tr = {"id": f"{pair}_{td}", "pair": pair, "dir": s["dir"], "stop": s["stop"], "level": s["level"], "kind": s["kind"],
              "signal_td": td, "sig_t": s["sig_t"], "entry_t": entry_t, "status": "pending"}
        st["trades"].append(tr)
        log_event({"event": "alert", **tr, "atrd": s["atrd"], "D_est": D_est})
        side = "BUY" if s["dir"] == 1 else "SELL"
        units = ""
        if bal and D_est > 0:
            per_unit = D_est if pair == "EUR_USD" else D_est / last_c
            units = f"\nSize at 0.5% risk of the practice balance ({bal:,.0f}): about {int(RISK_FRAC * bal / per_unit):,} units."
        how = (f"Entry: the system places a market order on the OANDA practice account at {uk(entry_t)} UK time (18:00 New York); "
               f"you do not need to act.\n") if PLACE else \
              (f"Entry: market order at {uk(entry_t)} UK time (18:00 New York) or as soon after as you can; "
               f"do not enter after {uk(entry_t + 2 * 3600 * 10**9)}.\n")
        text = (f"S26 SETUP - {pair} {side} (paper, OANDA practice)\n"
                f"{s['kind']} at daily {'support' if s['dir'] == 1 else 'resistance'} {fmt(pair, s['level'])}, signal day {td}.\n"
                f"{how}"
                f"Stop: {fmt(pair, s['stop'])} (about {D_est / PIP[pair]:.0f} pips from the last price).\n"
                f"Target: 2 x your stop distance from your fill (about {fmt(pair, last_c + 2 * D_est * s['dir'])}).\n"
                f"Exit by time if neither is hit after 10 trading days.{units}\n"
                f"Skip it if a major release is due within 15 minutes of your entry, or if the stop is closer than 8 x the spread.\n"
                f"Not evidence of an edge yet: screen pass on 2005-2014 only.")
        tg_send(text, chart(mk, pair, s, last_c))
    if PLACE:
        try:
            broker_step(st, now)
        except Exception as e:
            log_event({"event": "broker_error", "error": str(e)[:500]})
            tg_send(f"S26 practice order job ERROR: {str(e)[:300]}. Open practice trades keep their broker stops.")
            print("broker error:", e)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1)


def broker_step(st, now):
    import fx_risk_engine as risk
    from fx_oanda_orders import Practice
    br = Practice()
    acct = br.summary()
    closed_now = []
    for tr in st["trades"]:
        b = tr.get("broker")
        if not b or b.get("status") != "open":
            continue
        x = br.trade(b["trade_id"])
        if x["state"] == "OPEN" and now >= b["time_exit_t"]:
            br.close(b["trade_id"])
            x = br.trade(b["trade_id"])
            b["closed_by"] = "time exit (10 trading days)"
        if x["state"] == "CLOSED":
            pl = float(x.get("realizedPL", 0))
            b.update({"status": "closed", "close_time": x.get("closeTime"), "close_price": float(x.get("averageClosePrice", 0) or 0),
                      "realized_pl": pl, "financing": float(x.get("financing", 0) or 0),
                      "R": round(pl / b["risk_usd"], 3) if b.get("risk_usd") else None})
            closed_now.append((pd.Timestamp(b["close_time"]).value, pl))
            log_event({"event": "broker_closed", "id": tr["id"], **b})
            tg_send(f"S26 practice trade closed: {tr['pair']} {'long' if tr['dir'] == 1 else 'short'} at "
                    f"{fmt(tr['pair'], b['close_price'])}, P&L {pl:+,.2f} USD ({b['R']:+.2f} R incl. spread, financing)"
                    f"{' - ' + b['closed_by'] if b.get('closed_by') else ''}.")
    bal, nav = float(acct["balance"]), float(acct["NAV"])
    st["guard"] = g = risk.refresh(st.get("guard", {}), bal, nav, now, closed_now)
    for tr in st["trades"]:
        if tr.get("broker") or tr["status"] not in ("pending", "open") or now < tr["entry_t"]:
            continue
        pair, sg = tr["pair"], tr["dir"]
        frac, why = 0.0, "job ran more than 2 hours after 18:00 New York"
        if now <= tr["entry_t"] + 2 * 3600 * 10**9:
            held = [{"instrument": o["pair"], "direction": o["dir"], "risk_usd": o["broker"]["risk_usd"]}
                    for o in st["trades"] if (o.get("broker") or {}).get("status") == "open"]
            frac, why = risk.assess({"nav": nav, "start": g["B0"], "paused": g.get("paused", False), "open": held},
                                    g["prague_ref"], {"instrument": pair, "direction": sg, "risk_usd": RISK_FRAC * bal})
        if frac <= 0:
            tr["broker"] = {"status": "not_placed", "reason": why}
        else:
            bid, ask, tradeable = br.price(pair)
            px, sp = (ask if sg == 1 else bid), ask - bid
            D = (px - tr["stop"]) * sg
            if not tradeable or D <= 0 or D < 8 * sp:
                tr["broker"] = {"status": "not_placed", "reason": "market not tradeable" if not tradeable else
                                ("price already through the stop" if D <= 0 else "stop distance below 8 x spread")}
            else:
                per_unit = D if pair == "EUR_USD" else D / px
                units = int(frac * RISK_FRAC * bal / per_unit)
                f = br.market(pair, units * sg, tr["stop"], tr["id"])
                if not f["filled"]:
                    tr["broker"] = {"status": "not_placed", "reason": f"order not filled: {f['reason']}"}
                else:
                    Df = (f["fill"] - tr["stop"]) * sg
                    tp = f["fill"] + 2 * Df * sg
                    br.set_tp(pair, f["trade_id"], tp)
                    t_fill = pd.Timestamp(f["time"]).value
                    tr["broker"] = {"status": "open", "trade_id": f["trade_id"], "fill": f["fill"], "fill_time": f["time"],
                                    "units": f["units"], "stop": tr["stop"], "tp": tp, "D": Df, "spread_at_order": sp,
                                    "risk_usd": abs(f["units"]) * (Df if pair == "EUR_USD" else Df / f["fill"]),
                                    "commission": f["commission"], "time_exit_t": Market.time_exit_t(None, t_fill),
                                    **({"size_fraction": frac, "size_cut": why} if frac < 1 else {})}
                    log_event({"event": "broker_filled", "id": tr["id"], **tr["broker"]})
                    tg_send(f"S26 practice order FILLED: {pair} {'BUY' if sg == 1 else 'SELL'} {abs(f['units']):,} units at "
                            f"{fmt(pair, f['fill'])}; stop {fmt(pair, tr['stop'])}, target {fmt(pair, tp)} "
                            f"({Df / PIP[pair]:.0f} pips risk, {100 * frac * RISK_FRAC:g}% of the balance{'; ' + why if frac < 1 else ''}). "
                            f"Time exit {uk(tr['broker']['time_exit_t'])} UK.")
                    continue
        log_event({"event": "broker_not_placed", "id": tr["id"], **tr["broker"]})
        tg_send(f"S26 {pair}: practice order NOT placed - {tr['broker']['reason']}.")


def order_test():
    from fx_oanda_orders import Practice
    br = Practice()
    bid, ask, tradeable = br.price("EUR_USD")
    print(f"EUR_USD bid {bid} ask {ask} tradeable {tradeable}")
    f = br.market("EUR_USD", 1, bid - 0.0100, "s26_order_test")
    print("order:", {k: f[k] for k in f if k != "raw"} if f["filled"] else f)
    if f["filled"]:
        br.set_tp("EUR_USD", f["trade_id"], f["fill"] + 0.0100)
        x = br.trade(f["trade_id"])
        print("trade state", x["state"], "stop", (x.get("stopLossOrder") or {}).get("price"),
              "tp", (x.get("takeProfitOrder") or {}).get("price"))
        br.close(f["trade_id"])
        x = br.trade(f["trade_id"])
        print("after close:", x["state"], "realizedPL", x.get("realizedPL"))
    print("ORDER TEST DONE")


def replay(parquet_by_pair):
    """Validation: every S26 signal on stored H1 bid/ask data, for comparison with the backtest's trade table."""
    out = []
    for pair, path in parquet_by_pair.items():
        mk = Market(pd.read_parquet(path))
        for t in range(1, len(mk.d_c)):
            s = mk.signal(t)
            if s:
                k = mk.fill_bar(mk.entry_time(s["td"]))
                tr = {"pair": pair, "dir": s["dir"], "stop": s["stop"], "entry_t": mk.entry_time(s["td"]), "status": "pending"}
                res = mk.update(tr)
                out.append({"pair": pair, "sig_t": s["sig_t"], "dir": s["dir"], "stop": s["stop"], "kind": s["kind"],
                            "fill_t": int(mk.t[k]) if k < mk.n else -1, "status": tr["status"], "res": res,
                            "exit_kind": tr.get("exit_kind"), "exit_t": tr.get("exit_t"), "R_model": tr.get("R")})
    return pd.DataFrame(out)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--replay":
        df = replay({"EUR_USD": sys.argv[2], "USD_JPY": sys.argv[3]})
        df.to_csv(sys.argv[4], index=False)
        print(f"{len(df)} signals written to {sys.argv[4]}")
    elif os.environ.get("ORDER_TEST", "") == "1":
        order_test()
    else:
        run_live()

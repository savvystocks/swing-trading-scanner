"""S26 paper veto in shadow (NORTH_STAR v1.10, decision V1): the signal dossier, built by code only when the S26 book
sends a new alert, written once to reports/fx_alerts/veto/<signal id>.dossier.json for the veto job
(scripts/fx_veto_run.py). The order path never reads anything the veto writes."""
import json
import os

import numpy as np
import pandas as pd

PIP = {"EUR_USD": 1e-4, "USD_JPY": 1e-2}
DIGITS = {"EUR_USD": 5, "USD_JPY": 3}
H = 3600 * 10**9


def iso(t_ns):
    return pd.Timestamp(int(t_ns), tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def local(t_ns, zone):
    return pd.Timestamp(int(t_ns), tz="UTC").tz_convert(zone).strftime("%a %Y-%m-%d %H:%M")


def r(x, n=2):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def spread_block(mk, pair):
    pip = PIP[pair]
    close_sp = (mk.ask_c - mk.bid_c) / pip
    open_sp = (mk.ask_o - mk.bid_o) / pip
    days = np.unique(mk.td)
    recent = mk.td >= days[-20] if len(days) >= 20 else np.ones(mk.n, bool)
    hour = int(mk.ny_hour[-1])
    same, entry = recent & (mk.ny_hour == hour), recent & (mk.ny_hour == 18)
    med_same = float(np.median(close_sp[same]))
    return {"unit": "pips", "window": f"last {min(20, len(days))} trading days of H1 bid/ask bars",
            "last_h1_bar_open_utc": iso(mk.t[-1]), "last_h1_bar_new_york_hour": hour,
            "last_close_spread": r(close_sp[-1]), "median_same_new_york_hour": r(med_same),
            "ratio_last_to_same_hour_median": r(close_sp[-1] / med_same) if med_same > 0 else None,
            "median_all_hours": r(np.median(close_sp[recent])),
            "median_at_the_18_new_york_entry_open": r(np.median(open_sp[entry])) if entry.any() else None}


def daily_block(mk, pair, t, atrd):
    a, nd = max(0, t - 59), DIGITS[pair]
    c, o, h, l = mk.d_c, mk.d_o, mk.d_h, mk.d_l
    moves = np.abs(np.diff(c[a:t + 1])) / atrd
    gaps = np.abs(o[a + 1:t + 1] - c[a:t]) / atrd
    hi, lo = float(h[a:t + 1].max()), float(l[a:t + 1].min())
    atr_then = mk.d_atr[t - 21] if t >= 21 else np.nan

    def chg(k):
        return r((c[t] - c[t - k]) / atrd) if t - k >= a else None

    summary = {"bars": t - a + 1, "first": str(mk.d_date[a]), "last": str(mk.d_date[t]), "prices": "mid",
               "atrd": round(atrd, nd + 1), "atrd_pips": r(atrd / PIP[pair], 1),
               "atrd_ratio_to_20_bars_earlier": r(mk.d_atr[t - 1] / atr_then) if t >= 21 else None,
               "close_change_in_atrd": {"5_bars": chg(5), "20_bars": chg(20), "59_bars": chg(59)},
               "high": round(hi, nd), "low": round(lo, nd),
               "close_position_in_range": r((c[t] - lo) / (hi - lo)) if hi > lo else None,
               "signal_day_range_in_atrd": r((h[t] - l[t]) / atrd)}
    if len(moves):
        k, g = int(np.argmax(moves)), int(np.argmax(gaps))
        summary.update({"largest_close_to_close_move_in_atrd": r(moves[k]), "largest_move_on": str(mk.d_date[a + k + 1]),
                        "largest_open_gap_in_atrd": r(gaps[g]), "largest_gap_on": str(mk.d_date[a + g + 1])})
    bars = [[str(mk.d_date[i]), round(float(o[i]), nd), round(float(h[i]), nd), round(float(l[i]), nd),
             round(float(c[i]), nd)] for i in range(a, t + 1)]
    return {"summary": summary, "columns": ["date", "open", "high", "low", "close"], "bars": bars}


def account_block(st, bal, nav, now):
    if bal is None or nav is None:
        return "account not available (the practice balance read failed)"
    import fx_risk_engine as risk
    g = risk.refresh(st.get("guard", {}), bal, nav, now)
    pl = nav - g["prague_ref"]
    return {"balance": round(bal, 2), "nav": round(nav, 2), "start_balance": round(g["B0"], 2),
            "prague_day": g["prague_day"], "prague_midnight_balance": round(g["prague_ref"], 2),
            "today_pl_usd": round(pl, 2), "today_pl_pct_of_start": round(100 * pl / g["B0"], 3),
            "paused": bool(g.get("paused", False))}


def positions(st, own_id):
    broker, model = [], []
    for x in st["trades"]:
        b = x.get("broker") or {}
        side = "long" if x["dir"] == 1 else "short"
        if b.get("status") == "open":
            broker.append({"id": x["id"], "pair": x["pair"], "direction": side, "units": b.get("units"),
                           "fill": b.get("fill"), "stop": b.get("stop"), "take_profit": b.get("tp"),
                           "risk_usd": r(b.get("risk_usd")), "opened_utc": b.get("fill_time")})
        if x["id"] != own_id and x["status"] in ("pending", "open"):
            model.append({"id": x["id"], "pair": x["pair"], "direction": side, "status": x["status"]})
    return broker, model


def build(mk, pair, s, tr, st, bal, nav, now):
    sg, pip = s["dir"], PIP[pair]
    last = float(mk.ask_c[-1] if sg == 1 else mk.bid_c[-1])
    D = (last - s["stop"]) * sg
    broker, model = positions(st, tr["id"])
    e = tr["entry_t"]
    return {"schema": "s26_veto_dossier_v1", "signal_id": tr["id"], "book": "S26 (OANDA practice, paper)",
            "created_utc": iso(now), "order_deadline_utc": iso(e),
            "signal": {"pair": pair, "direction": "long" if sg == 1 else "short", "signal_type": s["kind"],
                       "signal_day": s["td"], "level": s["level"], "stop": s["stop"],
                       "level_role": "support" if sg == 1 else "resistance",
                       "last_price": round(last, DIGITS[pair]), "last_price_side": "ask" if sg == 1 else "bid",
                       "stop_distance_pips": r(D / pip, 1), "stop_distance_in_atrd": r(D / s["atrd"]),
                       "target": "2 x the stop distance from the fill", "time_exit": "10 trading days"},
            "planned_entry": {"utc": iso(e), "new_york": local(e, "America/New_York"),
                              "london": local(e, "Europe/London"), "tokyo": local(e, "Asia/Tokyo"),
                              "hold_window_start_utc": [iso(e), iso(e + 24 * H)]},
            "spread": spread_block(mk, pair),
            "daily_bars_60": daily_block(mk, pair, s["t"], s["atrd"]),
            "calendar": "calendar not available",
            "account": account_block(st, bal, nav, now),
            "open_practice_positions": broker, "other_model_trades_pending_or_open": model}


def write(state_dir, mk, pair, s, tr, st, bal, nav, now):
    d = os.path.join(state_dir, "veto")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{tr['id']}.dossier.json")
    if os.path.exists(path):
        return path
    doc = build(mk, pair, s, tr, st, bal, nav, now)
    with open(path, "x") as f:
        json.dump(doc, f, indent=1)
    return path

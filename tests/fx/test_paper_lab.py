import os
import tempfile

import fxtest

os.environ["ALERT_DIR"] = tempfile.mkdtemp(prefix="lab_s26_test_")
os.environ["LAB_DIR"] = tempfile.mkdtemp(prefix="lab_test_")
os.environ["DRY_RUN"] = "1"
import numpy as np
import pandas as pd

import fx_oanda_orders as O
import paper_lab as L

NY = "America/New_York"
H = 3600 * 10**9
SENT = []
L.tg = lambda text, png=None: SENT.append(text)
L.dip_chart = lambda dp, inst, d: b"png"


def utc(s):
    return pd.Timestamp(s, tz="UTC").value


def dip_frame(prices, start="2025-01-06", cut_after=None, drop15=()):
    """Hourly bid/ask bars; every bar belongs to the New York day whose 16:00 close follows it; bid o/h/l/c = p-0.01,
    p+0.02, p-0.02, p; ask = bid + 0.5."""
    days = pd.bdate_range(start, periods=len(prices))
    rows = []
    for i, (d, p) in enumerate(zip(days, prices)):
        prev = days[i - 1] if i else d - pd.offsets.BDay(1)
        t0 = (pd.Timestamp(prev) + pd.Timedelta(hours=16)).tz_localize(NY)
        t1 = (pd.Timestamp(d) + pd.Timedelta(hours=16)).tz_localize(NY)
        t = t0
        while t < t1:
            if not (i in drop15 and t.hour == 15):
                b = (p - 0.01, p + 0.02, p - 0.02, p)
                rows.append((t.tz_convert("UTC").value,) + b + tuple(x + 0.5 for x in b))
            t += pd.Timedelta(hours=1)
    df = pd.DataFrame(rows, columns=["t", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"])
    if cut_after is not None:
        df = df[df["t"] <= cut_after]
    return df.reset_index(drop=True), days


def dip_prices():
    p = [100 + 0.1 * k for k in range(250)]
    p += [p[-1] - 3, p[-1] - 6, p[-1] - 1, p[-1] - 0.5, p[-1]]
    return p


def test_rsi2_wilder_hand_case():
    r = L.rsi2(np.array([10.0, 11.0, 10.5, 10.0]))
    assert np.isnan(r[0]) and np.isnan(r[1])
    assert fxtest.near(r[2], 100 - 100 / 3, 1e-9) and fxtest.near(r[3], 40.0, 1e-9)


def test_dip_close_is_the_mid_of_the_15_new_york_bar():
    df, days = dip_frame([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    dp = L.Dip(df)
    i = dp.idx[str(days[3].date())]
    assert dp.real[i] and fxtest.near(dp.close[i], 103.25)


def test_dip_missing_15_bar_is_carried_not_real():
    df, days = dip_frame([100.0, 101.0, 102.0, 103.0, 104.0, 105.0], drop15=(3,))
    dp = L.Dip(df)
    i = dp.idx[str(days[3].date())]
    assert not dp.real[i] and fxtest.near(dp.close[i], 102.25)


def run_dip(df, now, inst="SPX500_USD", st=None):
    st = st or {"dip_done": {}, "trades": []}
    L.DIP_START = "2025-01-01"
    L.dip_scan(st, inst, L.Dip(df), now)
    return st


def test_dip_full_trade_matches_the_rule():
    SENT.clear()
    p = dip_prices()
    df, days = dip_frame(p)
    st = run_dip(df, utc("2030-01-01"))
    tr = [x for x in st["trades"]]
    assert len(tr) == 1 and tr[0]["status"] == "closed"
    t = tr[0]
    assert t["sig_day"] == str(days[250].date()) and t["setup"]["RSI(2)"] < 10
    assert fxtest.near(t["fill"], p[251] - 0.01 + 0.5, 1e-9)
    assert t["fill_t"] == pd.Timestamp(days[250] + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC").value
    assert t["exit_day"] == str(days[252].date())
    assert fxtest.near(t["exit"], p[253] - 0.01, 1e-9)
    assert fxtest.near(t["ret"], t["exit"] / t["fill"] - 1, 1e-12)
    nights = sum(3 if d.dayofweek == 4 else 1 for d in days[250:252])
    assert t["nights_held"] == nights and fxtest.near(t["fin"], L.DIP_FIN["SPX500_USD"] * nights, 1e-12)
    assert fxtest.near(t["usd"], round(L.DIP_NOTIONAL * (t["ret"] - t["fin"]), 2), 1e-9)
    assert any("SETUP" in s for s in SENT) and any("closed" in s for s in SENT)


def test_dip_waits_for_the_16_bar_before_filling():
    p = dip_prices()
    full, days = dip_frame(p)
    t16 = pd.Timestamp(days[250] + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC").value
    part = full[full["t"] < t16].reset_index(drop=True)
    st = run_dip(part, t16 + 10 * 60 * 10**9)
    assert len(st["trades"]) == 1 and st["trades"][0]["status"] == "pending"
    st = run_dip(full, utc("2030-01-01"), st=st)
    assert st["trades"][0]["status"] == "closed" and len(st["trades"]) == 1


def test_dip_ignores_days_before_the_start_and_unfinished_days():
    p = dip_prices()
    df, days = dip_frame(p)
    t16 = pd.Timestamp(days[250] + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC").value
    st = run_dip(df, t16 + 60 * 10**9)
    assert st["trades"] == []
    L.DIP_START = str(days[251].date())
    st = {"dip_done": {}, "trades": []}
    L.dip_scan(st, "SPX500_USD", L.Dip(df), utc("2030-01-01"))
    assert all(x["sig_day"] >= L.DIP_START for x in st["trades"])


def test_dip_journal_file_written():
    p = dip_prices()
    df, days = dip_frame(p)
    run_dip(df, utc("2030-01-01"), inst="NAS100_USD")
    f = os.path.join(L.JDIR, f"DIP_NAS100_USD_{days[250].date()}.md")
    txt = open(f, encoding="utf-8").read()
    assert "RSI(2)" in txt and "Result:" in txt and "cannot trade index CFDs" in txt


class Fake:
    nav = bal = 100_000.0
    quotes = {}
    fill_ok = True

    def __init__(self):
        pass

    def summary(self):
        return {"NAV": str(Fake.nav), "balance": str(Fake.bal)}

    def price(self, pair):
        return Fake.quotes[pair]

    def market(self, pair, units, stop, cid, tag="s26"):
        CALLS.append((pair, units, stop, tag))
        if not Fake.fill_ok:
            return {"filled": False, "reason": "INSUFFICIENT_LIQUIDITY", "raw": {}}
        tid = str(len(BROKER) + 1)
        bid, ask, _ = Fake.quotes[pair]
        BROKER[tid] = {"state": "OPEN"}
        return {"filled": True, "trade_id": tid, "fill": ask if units > 0 else bid, "time": "2026-11-30T23:03:00Z",
                "units": units, "commission": 0.0}

    def set_tp(self, pair, tid, tp):
        BROKER[tid]["tp"] = tp

    def trade(self, tid):
        return BROKER[tid]

    def close(self, tid):
        BROKER[tid].update(state="CLOSED", realizedPL="-250", averageClosePrice="1.2600",
                           closeTime="2026-12-14T23:04:00Z", financing="-3")


BROKER, CALLS = {}, []
O.Practice = Fake
T_ENTRY = utc("2026-11-30 23:00")
T_RUN = utc("2026-11-30 23:05")


def reset():
    BROKER.clear()
    CALLS.clear()
    SENT.clear()
    Fake.nav = Fake.bal = 100_000.0
    Fake.fill_ok = True
    Fake.quotes = {"GBP_USD": (1.26000, 1.26019, True), "USD_CHF": (0.88000, 0.88015, True),
                   "AUD_USD": (0.65000, 0.65013, True), "USD_NOK": (10.50000, 10.50397, True)}


def lab(*specs):
    return {"scanned": {}, "dip_done": {}, "guard": {}, "trades": [
        {"id": f"S26X_{p}_x", "book": "S26X", "pair": p, "dir": d, "stop": s, "status": "pending", "entry_t": T_ENTRY,
         "setup": {}} for p, d, s in specs]}


def s26_daily(days, start="2025-01-06", spread=0.0001):
    rows = []
    for td, (o, h, l, c) in zip(pd.bdate_range(start, periods=len(days)), days):
        t0 = pd.Timestamp(td) - pd.Timedelta(hours=7)
        path = [(o, o, l, l), (l, h, l, h)] + [(c, c, c, c)] * 22
        for k, (mo, mh, ml, mc) in enumerate(path):
            t = (t0 + pd.Timedelta(hours=k)).tz_localize(NY).tz_convert("UTC").value
            rows.append((t,) + tuple(x - spread / 2 for x in (mo, mh, ml, mc)) + tuple(x + spread / 2 for x in (mo, mh, ml, mc)))
    df = pd.DataFrame(rows, columns=["t", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"])
    return L.s26.Market(df)


def test_s26x_counts_only_closes_from_its_start_date():
    SENT.clear()
    L.s26.chart = lambda mk, pair, s, est: b"png"
    base = (1.1000, 1.1030, 1.0970, 1.1005)
    days = [base] * 50
    days[20] = (1.1000, 1.1030, 1.0900, 1.1005)
    days[30] = (1.0990, 1.1005, 1.0905, 1.1000)
    mk = s26_daily(days)
    L.S26X_START = "2025-02-18"
    st = {"scanned": {}, "trades": []}
    L.s26x_scan(st, "GBP_USD", mk, utc("2030-01-01"))
    assert st["trades"] == [] and st["scanned"]["GBP_USD"] == str(mk.d_date[-1])
    L.S26X_START = "2025-02-01"
    st = {"scanned": {}, "trades": []}
    L.s26x_scan(st, "GBP_USD", mk, utc("2030-01-01"))
    assert len(st["trades"]) == 1 and st["trades"][0]["signal_td"] == "2025-02-17" and st["trades"][0]["status"] != "pending"
    assert any("LAB S26X SETUP - GBP_USD BUY" in s for s in SENT)


def test_order_module_knows_the_seven_pairs():
    assert all(p in O.DECIMALS for p in L.S26X_PAIRS)
    assert all(p in L.s26.SLIP and p in L.s26.PIP for p in L.S26X_PAIRS)


def test_broker_gbp_usd_long_sizes_on_the_stop_distance_and_tags_the_order():
    reset()
    st = lab(("GBP_USD", 1, 1.25500))
    L.s26x_broker(st, T_RUN)
    b = st["trades"][0]["broker"]
    D = 1.26019 - 1.25500
    assert b["status"] == "open" and b["units"] == int(0.005 * 100_000 / D)
    assert CALLS[0][3] == "lab_s26x" and fxtest.near(b["tp"], 1.26019 + 2 * D, 1e-9)
    assert fxtest.near(b["risk_usd"], b["units"] * D, 1e-6) and b["risk_usd"] <= 500


def test_broker_usd_chf_short_sizes_in_dollars():
    reset()
    st = lab(("USD_CHF", -1, 0.88600))
    L.s26x_broker(st, T_RUN)
    b = st["trades"][0]["broker"]
    D = 0.88600 - 0.88000
    assert b["status"] == "open" and b["units"] == -int(0.005 * 100_000 / (D / 0.88000))
    assert fxtest.near(b["risk_usd"], abs(b["units"]) * D / 0.88000, 1e-6)


def test_broker_blocks_a_second_same_direction_dollar_bet():
    reset()
    st = lab(("GBP_USD", 1, 1.25500), ("USD_CHF", -1, 0.88600))
    L.s26x_broker(st, T_RUN)
    assert st["trades"][0]["broker"]["status"] == "open"
    b = st["trades"][1]["broker"]
    assert b["status"] == "not_placed" and "dollar bet" in b["reason"]


def test_broker_skips_a_stop_inside_eight_spreads():
    reset()
    st = lab(("USD_NOK", 1, 10.48000))
    L.s26x_broker(st, T_RUN)
    assert st["trades"][0]["broker"]["reason"] == "stop distance below 8 x spread" and not CALLS


def test_broker_too_late_after_two_hours():
    reset()
    st = lab(("GBP_USD", 1, 1.25500))
    L.s26x_broker(st, T_ENTRY + 2 * H + 60 * 10**9)
    assert st["trades"][0]["broker"]["status"] == "not_placed" and "2 hours" in st["trades"][0]["broker"]["reason"]


def test_broker_time_exit_closes_and_records_r():
    reset()
    st = lab(("GBP_USD", 1, 1.25500))
    L.s26x_broker(st, T_RUN)
    b = st["trades"][0]["broker"]
    L.s26x_broker(st, b["time_exit_t"] + 60 * 10**9)
    assert b["status"] == "closed" and b["closed_by"].startswith("time exit")
    assert fxtest.near(b["R"], round(-250 / b["risk_usd"], 3), 1e-9)


def test_broker_ignores_dip_trades():
    reset()
    st = lab()
    st["trades"].append({"id": "DIP_x", "book": "DIP", "inst": "SPX500_USD", "status": "pending", "setup": {}})
    L.s26x_broker(st, T_RUN)
    assert not CALLS and "broker" not in st["trades"][0]


def test_scoreboard_counts_closed_trades():
    st = lab()
    st["trades"] += [{"id": "a", "book": "S26X", "status": "closed", "R": 2.0},
                     {"id": "b", "book": "S26X", "status": "closed", "R": -1.0},
                     {"id": "c", "book": "DIP", "status": "closed", "net": 0.01, "usd": 250.0}]
    sb = L.scoreboard(st, T_RUN)
    assert "model trades closed: 2" in sb and "trades closed: 1" in sb and "+250.00 USD" in sb


if __name__ == "__main__":
    fxtest.run(dict(globals()))

import os
import tempfile

import fxtest

os.environ["ALERT_DIR"] = tempfile.mkdtemp(prefix="fx_s26_test_")
os.environ["DRY_RUN"] = "1"
import numpy as np
import pandas as pd

import fx_oanda_orders as O
import fx_s26_alerts as A

NY = "America/New_York"
H = 3600 * 10**9
SENT = []
A.tg_send = lambda text, png=None: SENT.append(text)


def ny(s):
    return pd.Timestamp(s).tz_localize(NY).tz_convert("UTC").value


def utc(s):
    return pd.Timestamp(s, tz="UTC").value


def frame(rows):
    df = pd.DataFrame(rows, columns=["t", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c"])
    df["t"] = df["t"].astype("int64")
    return df


def daily_market(days, start="2025-01-06", spread=0.0001):
    rows = []
    for td, (o, h, l, c) in zip(pd.bdate_range(start, periods=len(days)), days):
        t0 = pd.Timestamp(td) - pd.Timedelta(hours=7)
        path = [(o, o, l, l), (l, h, l, h)] + [(c, c, c, c)] * 22
        for k, (mo, mh, ml, mc) in enumerate(path):
            t = (t0 + pd.Timedelta(hours=k)).tz_localize(NY).tz_convert("UTC").value
            rows.append((t,) + tuple(x - spread / 2 for x in (mo, mh, ml, mc)) + tuple(x + spread / 2 for x in (mo, mh, ml, mc)))
    return A.Market(frame(rows))


BASE = (1.1000, 1.1030, 1.0970, 1.1005)


def test_bull_pin_at_swing_support_signals():
    days = [BASE] * 40
    days[20] = (1.1000, 1.1030, 1.0900, 1.1005)
    days[30] = (1.0990, 1.1005, 1.0905, 1.1000)
    s = daily_market(days).signal(30)
    assert s and s["dir"] == 1 and s["kind"] == "pin bar"
    assert fxtest.near(s["stop"], 1.0905, 1e-9) and fxtest.near(s["level"], 1.0900, 1e-9)
    assert s["td"] == "2025-02-17"


def test_pin_away_from_any_level_is_ignored():
    days = [BASE] * 40
    days[20] = (1.1000, 1.1030, 1.0900, 1.1005)
    days[30] = (1.0990, 1.1005, 1.0950, 1.1000)
    assert A.bull_pin(*days[30])
    assert daily_market(days).signal(30) is None


def test_bear_pin_at_swing_resistance_signals():
    days = [BASE] * 40
    days[20] = (1.1000, 1.1100, 1.0970, 1.1005)
    days[30] = (1.1010, 1.1095, 1.0995, 1.1000)
    s = daily_market(days).signal(30)
    assert s and s["dir"] == -1 and s["kind"] == "pin bar"
    assert fxtest.near(s["stop"], 1.1095, 1e-9) and fxtest.near(s["level"], 1.1100, 1e-9)


def test_bull_engulfing_at_support_signals():
    days = [BASE] * 40
    days[20] = (1.1000, 1.1030, 1.0900, 1.1005)
    days[29] = (1.0990, 1.1000, 1.0960, 1.0965)
    days[30] = (1.0962, 1.1010, 1.0904, 1.0995)
    s = daily_market(days).signal(30)
    assert s and s["dir"] == 1 and s["kind"] == "engulfing"


def test_no_signal_before_atr_exists():
    early, ready = [BASE] * 40, [BASE] * 40
    early[5] = ready[5] = (1.1000, 1.1030, 1.0900, 1.1005)
    early[14] = ready[15] = (1.0990, 1.1005, 1.0905, 1.1000)
    assert daily_market(early).signal(14) is None
    assert daily_market(ready).signal(15)["dir"] == 1


def test_entry_is_18_new_york_before_the_next_session():
    mk = daily_market([BASE] * 3)
    assert mk.entry_time("2025-01-06") == utc("2025-01-06 23:00")
    assert mk.entry_time("2025-01-10") == utc("2025-01-12 23:00")


def hourly(start_utc, n, mid=1.1000, spread=0.0001, edits=None, skip=()):
    rows = []
    t0 = pd.Timestamp(start_utc, tz="UTC")
    for k in range(n):
        if k in skip:
            continue
        o = h = l = c = mid
        if edits and k in edits:
            o, h, l, c = edits[k]
        t = (t0 + pd.Timedelta(hours=k)).value
        rows.append((t, o - spread / 2, h - spread / 2, l - spread / 2, c - spread / 2,
                     o + spread / 2, h + spread / 2, l + spread / 2, c + spread / 2))
    return A.Market(frame(rows))


def test_fill_bar_defers_through_the_new_york_rollover():
    mk = hourly("2025-01-06 19:00", 8)
    k = mk.fill_bar(ny("2025-01-06 16:00"))
    assert mk.t[k] == ny("2025-01-06 18:00")
    k = mk.fill_bar(ny("2025-01-06 16:30"))
    assert mk.t[k] == ny("2025-01-06 18:00")
    assert mk.t[mk.fill_bar(ny("2025-01-06 18:00"))] == ny("2025-01-06 18:00")


def test_fill_bar_takes_the_next_bar_when_18_is_missing():
    mk = hourly("2025-01-06 19:00", 8, skip=(4,))
    assert mk.t[mk.fill_bar(ny("2025-01-06 18:00"))] == ny("2025-01-06 19:00")


def test_time_exit_is_ten_trading_days():
    mk = daily_market([BASE] * 3)
    assert mk.time_exit_t(utc("2025-01-06 23:00")) == utc("2025-01-20 23:00")
    assert mk.time_exit_t(utc("2025-01-12 23:00")) == utc("2025-01-26 23:00")


def test_time_exit_keeps_new_york_wall_clock_across_dst():
    mk = daily_market([BASE] * 3)
    assert mk.time_exit_t(utc("2025-03-03 23:00")) == utc("2025-03-17 22:00")


ENTRY = utc("2025-01-06 23:00")
START = "2025-01-06 20:00"
K0 = 3


def pending(stop, d=1):
    return {"pair": "EUR_USD", "dir": d, "stop": stop, "entry_t": ENTRY, "status": "pending"}


def test_update_fills_long_at_the_ask_open():
    mk = hourly(START, 10)
    tr = pending(1.0950)
    assert mk.update(tr) is None
    assert tr["status"] == "open" and tr["fill_t"] == ENTRY
    assert fxtest.near(tr["fill"], 1.10005) and fxtest.near(tr["D"], 0.00505) and fxtest.near(tr["spread_in"], 0.0001)
    assert fxtest.near(tr["target"], 1.10005 + 2 * 0.00505)
    assert tr["time_exit_t"] == utc("2025-01-20 23:00")


def test_update_stop_first_when_both_inside_one_bar():
    mk = hourly(START, 40, edits={K0 + 5: (1.1000, 1.1200, 1.0940, 1.1000)})
    tr = pending(1.0950)
    assert mk.update(tr) == "closed"
    assert tr["exit_kind"] == "stop" and fxtest.near(tr["exit"], 1.0950 - A.SLIP["EUR_USD"]) and tr["R"] == -1.01


def test_update_gap_through_stop_books_the_open():
    mk = hourly(START, 40, edits={K0 + 5: (1.0900, 1.0905, 1.0895, 1.0900)})
    tr = pending(1.0950)
    assert mk.update(tr) == "closed"
    assert tr["exit_kind"] == "stop" and fxtest.near(tr["exit"], 1.08995 - A.SLIP["EUR_USD"]) and tr["R"] == -2.01


def test_update_two_r_target():
    mk = hourly(START, 40, edits={K0 + 5: (1.1000, 1.1110, 1.0990, 1.1100)})
    tr = pending(1.0950)
    assert mk.update(tr) == "closed"
    assert tr["exit_kind"] == "target" and fxtest.near(tr["exit"], tr["target"]) and tr["R"] == 2.0


def test_update_short_target_on_the_ask():
    mk = hourly(START, 40, edits={K0 + 5: (1.1000, 1.1010, 1.0890, 1.0900)})
    tr = pending(1.1050, -1)
    assert mk.update(tr) == "closed"
    assert fxtest.near(tr["fill"], 1.09995) and tr["exit_kind"] == "target" and tr["R"] == 2.0


def test_update_time_exit_at_the_bid_open():
    mk = hourly(START, 24 * 16)
    tr = pending(1.0950)
    assert mk.update(tr) == "closed"
    assert tr["exit_kind"] == "time" and tr["exit_t"] == utc("2025-01-20 23:00") and fxtest.near(tr["exit"], 1.09995)
    assert tr["R"] == round(-0.0001 / 0.00505, 3)


def test_update_stays_open_without_enough_bars():
    mk = hourly(START, 40)
    tr = pending(1.0950)
    assert mk.update(tr) is None and mk.update(tr) is None and tr["status"] == "open"


def test_update_skips_a_stop_inside_eight_spreads():
    mk = hourly(START, 10)
    tr = pending(1.0996)
    assert mk.update(tr) == "skipped" and tr["reason"] == "stop distance below 8 x spread"


def test_update_skips_when_price_is_through_the_stop():
    mk = hourly(START, 10)
    tr = pending(1.1001)
    assert mk.update(tr) == "skipped" and tr["reason"] == "price already through the stop"


def test_update_waits_for_the_fill_bar():
    mk = hourly(START, 2)
    tr = pending(1.0950)
    assert mk.update(tr) is None and tr["status"] == "pending"


class Fake:
    nav = bal = 100_000.0
    quotes = {"EUR_USD": (1.05000, 1.05012, True), "USD_JPY": (150.000, 150.015, True)}
    fill_ok = True
    close_pl = "-12.5"

    def __init__(self):
        self.trades, self.calls = {}, []

    def summary(self):
        return {"NAV": str(Fake.nav), "balance": str(Fake.bal)}

    def price(self, pair):
        return Fake.quotes[pair]

    def market(self, pair, units, stop, cid):
        self.calls.append(("market", pair, units, stop))
        if not Fake.fill_ok:
            return {"filled": False, "reason": "INSUFFICIENT_LIQUIDITY", "raw": {}}
        tid = str(len(BROKER) + 1)
        bid, ask, _ = Fake.quotes[pair]
        BROKER[tid] = {"state": "OPEN"}
        return {"filled": True, "trade_id": tid, "fill": ask if units > 0 else bid, "time": FILL_TIME,
                "units": units, "commission": 0.0}

    def set_tp(self, pair, tid, tp):
        BROKER[tid]["tp"] = tp

    def trade(self, tid):
        return BROKER[tid]

    def close(self, tid):
        BROKER[tid].update(state="CLOSED", realizedPL=Fake.close_pl, averageClosePrice="1.049",
                           closeTime="2026-12-09T23:04:00Z", financing="-1")


BROKER = {}
FILL_TIME = "2026-11-25T23:03:00Z"
O.Practice = Fake
T_ENTRY = utc("2026-11-25 23:00")
T_RUN = utc("2026-11-25 23:05")


def reset(nav=100_000.0, bal=None):
    BROKER.clear()
    SENT.clear()
    Fake.nav, Fake.bal = nav, nav if bal is None else bal
    Fake.quotes = {"EUR_USD": (1.05000, 1.05012, True), "USD_JPY": (150.000, 150.015, True)}
    Fake.fill_ok = True


def book(*specs):
    return {"scanned": {}, "trades": [{"id": f"{p}_x", "pair": p, "dir": d, "stop": s, "status": "pending",
                                       "entry_t": T_ENTRY} for p, d, s in specs]}


def test_broker_fills_at_half_percent_risk_with_a_two_r_take_profit():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_RUN)
    b = st["trades"][0]["broker"]
    assert b["status"] == "open" and b["units"] == int(A.RISK_FRAC * 100_000.0 / (1.05012 - 1.04500))
    assert fxtest.near(b["D"], 0.00512)
    assert fxtest.near(b["tp"], 1.05012 + 2 * 0.00512) and fxtest.near(BROKER[b["trade_id"]]["tp"], b["tp"])
    assert fxtest.near(b["risk_usd"], b["units"] * 0.00512, 1e-6) and b["risk_usd"] <= 500
    assert b["time_exit_t"] == A.Market.time_exit_t(None, pd.Timestamp(FILL_TIME).value)
    assert "FILLED" in SENT[-1]


def test_broker_usd_jpy_short_sizes_in_dollars():
    reset()
    st = book(("USD_JPY", -1, 151.20))
    A.broker_step(st, T_RUN)
    b = st["trades"][0]["broker"]
    assert b["status"] == "open" and b["units"] == -int(A.RISK_FRAC * 100_000.0 / ((151.20 - 150.0) / 150.0))
    assert fxtest.near(b["tp"], 150.0 - 2 * 1.2) and fxtest.near(b["risk_usd"], abs(b["units"]) * 1.2 / 150.0, 1e-6)


def test_broker_blocks_a_second_same_direction_dollar_bet():
    reset()
    st = book(("EUR_USD", 1, 1.04500), ("USD_JPY", -1, 151.20))
    A.broker_step(st, T_RUN)
    assert st["trades"][0]["broker"]["status"] == "open"
    b = st["trades"][1]["broker"]
    assert b["status"] == "not_placed" and "dollar bet" in b["reason"]


def test_broker_allows_the_opposite_dollar_direction():
    reset()
    st = book(("EUR_USD", 1, 1.04500), ("USD_JPY", 1, 148.80))
    A.broker_step(st, T_RUN)
    assert [t["broker"]["status"] for t in st["trades"]] == ["open", "open"]


def test_broker_skips_a_stop_inside_eight_spreads():
    reset()
    Fake.quotes["EUR_USD"] = (1.05000, 1.05080, True)
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_RUN)
    b = st["trades"][0]["broker"]
    assert b["status"] == "not_placed" and b["reason"] == "stop distance below 8 x spread" and not BROKER


def test_broker_skips_an_untradeable_market():
    reset()
    Fake.quotes["EUR_USD"] = (1.05000, 1.05012, False)
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_RUN)
    assert st["trades"][0]["broker"]["reason"] == "market not tradeable"


def test_broker_records_an_unfilled_order():
    reset()
    Fake.fill_ok = False
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_RUN)
    assert st["trades"][0]["broker"]["reason"] == "order not filled: INSUFFICIENT_LIQUIDITY"


def test_broker_too_late_after_two_hours():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_ENTRY + 2 * H + 1)
    b = st["trades"][0]["broker"]
    assert b["status"] == "not_placed" and b["reason"] == "job ran more than 2 hours after 18:00 New York" and not BROKER


def test_broker_waits_before_the_entry_time():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_ENTRY - 1)
    assert "broker" not in st["trades"][0] and not BROKER


def test_broker_time_exit_closes_after_ten_trading_days():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_RUN)
    b = st["trades"][0]["broker"]
    A.broker_step(st, b["time_exit_t"] - 1)
    assert b["status"] == "open" and BROKER[b["trade_id"]]["state"] == "OPEN"
    A.broker_step(st, b["time_exit_t"] + 1)
    assert b["status"] == "closed" and b["closed_by"] == "time exit (10 trading days)"
    assert b["realized_pl"] == -12.5 and b["R"] == round(-12.5 / b["risk_usd"], 3)


def test_broker_records_a_broker_side_close():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    A.broker_step(st, T_RUN)
    b = st["trades"][0]["broker"]
    BROKER[b["trade_id"]].update(state="CLOSED", realizedPL="1000.0", averageClosePrice="1.06036",
                                 closeTime="2026-11-27T10:00:00Z", financing="-2")
    A.broker_step(st, utc("2026-11-27 21:12"))
    assert b["status"] == "closed" and "closed_by" not in b and b["R"] == round(1000.0 / b["risk_usd"], 3)


def test_broker_day_stop_blocks_new_trades():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    st["trades"][0]["entry_t"] = utc("2026-11-27 21:00")
    A.broker_step(st, utc("2026-11-26 23:05"))
    Fake.nav, Fake.bal = 97_500.0, 100_000.0
    A.broker_step(st, utc("2026-11-27 21:05"))
    b = st["trades"][0]["broker"]
    assert b["status"] == "not_placed" and b["reason"].startswith("day stop") and not BROKER


def test_broker_pause_at_six_percent_is_terminal():
    reset()
    st = book()
    A.broker_step(st, utc("2026-11-25 23:05"))
    Fake.nav = Fake.bal = 94_000.0
    A.broker_step(st, utc("2026-11-26 23:05"))
    Fake.nav = Fake.bal = 101_000.0
    st["trades"].append({"id": "EUR_USD_y", "pair": "EUR_USD", "dir": 1, "stop": 1.045, "status": "pending",
                         "entry_t": utc("2026-11-30 23:00")})
    A.broker_step(st, utc("2026-11-30 23:05"))
    b = st["trades"][0]["broker"]
    assert b["status"] == "not_placed" and b["reason"].startswith("PAUSED") and st["guard"]["paused"]


def test_broker_day_reference_is_prague_midnight_not_new_york():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    st["trades"][0]["entry_t"] = utc("2026-03-17 22:00")
    A.broker_step(st, utc("2026-03-16 23:03"))
    Fake.nav = Fake.bal = 97_400.0
    A.broker_step(st, utc("2026-03-17 21:12"))
    A.broker_step(st, utc("2026-03-17 22:03"))
    b = st["trades"][0]["broker"]
    assert b["status"] == "not_placed" and b["reason"].startswith("day stop") and st["guard"]["prague_ref"] == 100_000.0


def test_broker_loss_closed_after_prague_midnight_counts_today():
    reset()
    st = book(("EUR_USD", 1, 1.04500), ("USD_JPY", 1, 148.80))
    st["trades"][1]["entry_t"] = utc("2026-12-01 23:00")
    A.broker_step(st, utc("2026-11-25 23:05"))
    A.broker_step(st, utc("2026-12-01 22:03"))
    b = st["trades"][0]["broker"]
    BROKER[b["trade_id"]].update(state="CLOSED", realizedPL="-2600.0", averageClosePrice="1.0", closeTime="2026-12-01T23:01:00Z")
    Fake.nav = Fake.bal = 97_400.0
    A.broker_step(st, utc("2026-12-01 23:03"))
    assert b["status"] == "closed" and st["guard"]["prague_ref"] == 100_000.0
    assert st["trades"][1]["broker"]["reason"].startswith("day stop")


def test_broker_cut_trade_records_its_fraction():
    reset()
    st = book(("EUR_USD", 1, 1.04500))
    st["trades"].append({"id": "GBP_USD_x", "pair": "GBP_USD", "dir": 1, "stop": 1.25, "status": "open",
                         "broker": {"status": "open", "trade_id": "9", "risk_usd": 300.0, "time_exit_t": utc("2027-01-01")}})
    BROKER["9"] = {"state": "OPEN"}
    A.broker_step(st, T_RUN)
    b = st["trades"][0]["broker"]
    assert b["status"] == "open" and fxtest.near(b["size_fraction"], 0.4) and "dollar bet" in b["size_cut"]
    assert b["units"] == int(0.4 * A.RISK_FRAC * 100_000.0 / (1.05012 - 1.04500)) and "0.2% of the balance" in SENT[-1]


if __name__ == "__main__":
    fxtest.run(globals())

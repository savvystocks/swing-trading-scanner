import copy

import pandas as pd

import fxtest
import fx_risk_engine as R

B0 = 100_000.0


def utc(s):
    return pd.Timestamp(s, tz="UTC").value


def acct(nav=B0, held=(), paused=False, start=B0):
    return {"nav": nav, "start": start, "paused": paused,
            "open": [{"instrument": i, "direction": d, "risk_usd": r} for i, d, r in held]}


def trade(instrument="EUR_JPY", direction=1, risk=500.0):
    return {"instrument": instrument, "direction": direction, "risk_usd": risk}


def test_prague_midnight_in_winter_is_23_utc():
    assert R.prague_midnight_ns(utc("2026-11-26 10:00")) == utc("2026-11-25 23:00")
    assert R.prague_day(utc("2026-11-25 22:59")) == "2026-11-25" and R.prague_day(utc("2026-11-25 23:00")) == "2026-11-26"


def test_prague_midnight_in_summer_is_22_utc():
    assert R.prague_midnight_ns(utc("2026-07-07 10:00")) == utc("2026-07-06 22:00")
    assert R.prague_day(utc("2026-07-06 21:59")) == "2026-07-06" and R.prague_day(utc("2026-07-06 22:00")) == "2026-07-07"


def test_prague_midnight_on_the_spring_forward_day():
    assert R.prague_day(utc("2026-03-28 23:30")) == "2026-03-29"
    assert R.prague_midnight_ns(utc("2026-03-28 23:30")) == utc("2026-03-28 23:00")
    assert R.prague_day(utc("2026-03-29 21:59")) == "2026-03-29"
    assert R.prague_day(utc("2026-03-29 22:01")) == "2026-03-30"
    assert R.prague_midnight_ns(utc("2026-03-29 22:01")) == utc("2026-03-29 22:00")


def test_prague_midnight_on_the_fall_back_day():
    assert R.prague_midnight_ns(utc("2026-10-24 22:30")) == utc("2026-10-24 22:00")
    assert R.prague_day(utc("2026-10-25 22:30")) == "2026-10-25"
    assert R.prague_midnight_ns(utc("2026-10-25 22:30")) == utc("2026-10-24 22:00")
    assert R.prague_day(utc("2026-10-25 23:00")) == "2026-10-26"
    assert R.prague_midnight_ns(utc("2026-10-26 01:30")) == utc("2026-10-25 23:00")


def test_first_run_sets_start_and_prague_reference():
    g = R.refresh({}, B0, B0, utc("2026-11-26 10:00"))
    assert g == {"B0": B0, "prague_day": "2026-11-26", "prague_ref": B0}
    assert R.assess(acct(), g["prague_ref"], trade()) == (1.0, "")


def test_refresh_is_pure():
    g0 = {"B0": B0, "prague_day": "2026-11-25", "prague_ref": B0}
    keep = copy.deepcopy(g0)
    R.refresh(g0, 90_000.0, 90_000.0, utc("2026-11-26 10:00"))
    assert g0 == keep


def test_day_stop_at_two_and_a_half_percent_of_start():
    frac, why = R.assess(acct(97_500.0), B0, trade())
    assert frac == 0.0 and why.startswith("day stop") and "Prague-midnight balance" in why
    assert R.assess(acct(97_501.0), B0, trade())[0] == 1.0
    assert R.assess(acct(102_400.0, start=B0), 104_900.0, trade())[0] == 0.0


def test_day_stop_counts_floating_losses():
    g = R.refresh({}, B0, B0, utc("2026-11-26 10:00"))
    g = R.refresh(g, B0, 97_400.0, utc("2026-11-26 15:00"))
    assert g["prague_ref"] == B0 and R.assess(acct(97_400.0), g["prague_ref"], trade())[0] == 0.0


def test_reference_resets_on_a_new_prague_day():
    g = R.refresh({}, B0, B0, utc("2026-11-26 10:00"))
    g = R.refresh(g, 97_400.0, 97_400.0, utc("2026-11-26 22:59"))
    assert g["prague_ref"] == B0
    g = R.refresh(g, 97_400.0, 97_400.0, utc("2026-11-26 23:03"))
    assert g["prague_day"] == "2026-11-27" and g["prague_ref"] == 97_400.0
    assert R.assess(acct(97_400.0), g["prague_ref"], trade())[0] == 1.0


def test_reference_ignores_the_new_york_day_roll():
    g = R.refresh({}, B0, B0, utc("2026-03-16 23:03"))
    g = R.refresh(g, 97_400.0, 97_400.0, utc("2026-03-17 21:12"))
    g = R.refresh(g, 97_400.0, 97_400.0, utc("2026-03-17 22:03"))
    assert g["prague_day"] == "2026-03-17" and g["prague_ref"] == B0
    assert R.assess(acct(97_400.0), g["prague_ref"], trade())[0] == 0.0


def test_reference_backs_out_trades_closed_after_midnight():
    g0 = {"B0": B0, "prague_day": "2026-11-25", "prague_ref": B0}
    loss = R.refresh(g0, 97_400.0, 97_400.0, utc("2026-11-25 23:30"), [(utc("2026-11-25 23:01"), -2_600.0)])
    assert loss["prague_ref"] == B0
    gain = R.refresh(g0, 101_000.0, 101_000.0, utc("2026-11-25 23:30"), [(utc("2026-11-25 23:00"), 1_000.0)])
    assert gain["prague_ref"] == B0
    before = R.refresh(g0, 97_400.0, 97_400.0, utc("2026-11-25 23:30"), [(utc("2026-11-25 22:59"), -2_600.0)])
    assert before["prague_ref"] == 97_400.0


def test_closes_do_not_move_a_reference_already_set_today():
    g = {"B0": B0, "prague_day": "2026-11-26", "prague_ref": B0}
    g = R.refresh(g, 99_000.0, 99_000.0, utc("2026-11-26 12:00"), [(utc("2026-11-26 11:00"), -1_000.0)])
    assert g["prague_ref"] == B0


def test_pause_at_six_percent_is_terminal():
    g = R.refresh({}, B0, B0, utc("2026-11-25 10:00"))
    g = R.refresh(g, 94_000.0, 94_000.0, utc("2026-11-26 10:00"))
    assert g["paused"] is True
    g = R.refresh(g, 101_000.0, 101_000.0, utc("2026-11-30 10:00"))
    frac, why = R.assess(acct(101_000.0, paused=g["paused"]), g["prague_ref"], trade())
    assert g["paused"] is True and frac == 0.0 and why.startswith("PAUSED")


def test_pause_measured_from_the_start_balance():
    assert R.assess(acct(94_000.0), 94_000.0, trade())[1].startswith("PAUSED")
    assert R.assess(acct(94_001.0), 94_001.0, trade())[0] == 1.0


def test_pause_outranks_the_day_stop():
    assert R.assess(acct(93_000.0), B0, trade())[1].startswith("PAUSED")


def test_open_risk_cap_cuts_to_the_room_left():
    held = (("EUR_USD", 1, 1_000.0), ("USD_JPY", 1, 1_000.0))
    frac, why = R.assess(acct(held=held), B0, trade("EUR_JPY", 1, 1_000.0))
    assert frac == 0.5 and why.startswith("open-risk cap") and "cut to 50%" in why


def test_open_risk_cap_skips_below_a_quarter():
    held = (("EUR_USD", 1, 1_300.0), ("USD_JPY", 1, 1_000.0))
    frac, why = R.assess(acct(held=held), B0, trade("EUR_JPY", 1, 1_000.0))
    assert frac == 0.0 and "skipped" in why


def test_usd_cluster_blocks_a_second_dollar_short():
    held = (("EUR_USD", 1, 500.0),)
    for inst, d in (("GBP_USD", 1), ("AUD_USD", 1), ("NZD_USD", 1), ("USD_CHF", -1), ("USD_JPY", -1), ("USD_CAD", -1)):
        frac, why = R.assess(acct(held=held), B0, trade(inst, d, 500.0))
        assert frac == 0.0 and "dollar bet" in why and "USD short cluster" in why, inst


def test_usd_cluster_blocks_a_second_dollar_long():
    held = (("USD_JPY", 1, 500.0),)
    for inst, d in (("USD_CHF", 1), ("USD_CAD", 1), ("EUR_USD", -1), ("GBP_USD", -1)):
        assert R.assess(acct(held=held), B0, trade(inst, d, 500.0))[0] == 0.0, inst


def test_opposite_dollar_directions_are_separate_bets():
    held = (("EUR_USD", 1, 500.0),)
    assert R.assess(acct(held=held), B0, trade("USD_JPY", 1, 500.0)) == (1.0, "")
    assert R.assess(acct(held=held), B0, trade("AUD_USD", -1, 500.0)) == (1.0, "")


def test_cluster_cuts_a_larger_second_signal_to_the_room():
    frac, why = R.assess(acct(held=(("EUR_USD", 1, 500.0),)), B0, trade("GBP_USD", 1, 1_000.0))
    assert frac == 0.5 and "cut to 50%" in why


def test_cluster_room_of_exactly_a_quarter_is_taken():
    assert R.assess(acct(held=(("EUR_USD", 1, 750.0),)), B0, trade("GBP_USD", 1, 1_000.0))[0] == 0.25
    assert R.assess(acct(held=(("EUR_USD", 1, 800.0),)), B0, trade("GBP_USD", 1, 1_000.0))[0] == 0.0


def test_equity_index_longs_are_one_cluster():
    held = (("US500.cash", 1, 500.0),)
    for inst in ("US100.cash", "US30", "US2000", "GER40.cash", "UK100", "JP225.cash", "EU50", "NAS100_USD", "DE30_EUR"):
        frac, why = R.assess(acct(held=held), B0, trade(inst, 1, 500.0))
        assert frac == 0.0 and "equity index long cluster" in why, inst
    assert R.assess(acct(held=held), B0, trade("US100.cash", -1, 500.0)) == (1.0, "")
    assert R.assess(acct(held=held), B0, trade("EUR_USD", 1, 500.0)) == (1.0, "")


def test_cluster_map():
    assert R.cluster("EUR_USD", 1) == R.cluster("GBPUSD", 1) == R.cluster("USD_JPY", -1) == "USD short"
    assert R.cluster("USD_CAD", 1) == R.cluster("NZD/USD", -1) == "USD long"
    assert R.cluster("EUR_JPY", 1) is None and R.cluster("XAU_USD", 1) is None and R.cluster("XAUUSD", -1) is None
    assert R.cluster("SPX500_USD", 1) == "equity index long" and R.cluster("SPX500_USD", -1) is None


def test_tighter_of_cap_and_cluster_wins():
    held = (("EUR_USD", 1, 600.0), ("USD_JPY", 1, 1_400.0))
    frac, why = R.assess(acct(held=held), B0, trade("GBP_USD", 1, 1_000.0))
    assert frac == 0.4 and "dollar bet" in why
    held = (("EUR_USD", 1, 200.0), ("USD_JPY", 1, 1_900.0))
    frac, why = R.assess(acct(held=held), B0, trade("GBP_USD", 1, 1_000.0))
    assert fxtest.near(frac, 0.4) and why.startswith("open-risk cap")


def test_cushion_allows_a_trade_landing_exactly_on_four_percent():
    held = (("EUR_USD", 1, 1_500.0),)
    assert R.assess(acct(98_000.0, held=held), B0, trade("EUR_JPY", 1, 500.0)) == (1.0, "")


def test_cushion_refuses_a_trade_just_above_four_percent():
    held = (("EUR_USD", 1, 1_500.0),)
    frac, why = R.assess(acct(97_999.99, held=held), B0, trade("EUR_JPY", 1, 500.0))
    assert frac == 0.0 and why.startswith("4% cushion") and "today's loss 2,000.01" in why and why.endswith("(refused)")


def test_cushion_refuses_rather_than_cutting():
    held = (("EUR_USD", 1, 1_500.0),)
    frac, why = R.assess(acct(97_600.0, held=held), B0, trade("EUR_JPY", 1, 500.0))
    assert frac == 0.0 and "plus this trade's 500.00 would pass 4,000.00 USD (refused)" in why


def test_cushion_binds_where_the_open_risk_cap_does_not():
    held = (("EUR_USD", 1, 1_000.0),)
    frac, why = R.assess(acct(97_800.0, held=held), B0, trade("EUR_JPY", 1, 1_000.0))
    assert frac == 0.0 and why.startswith("4% cushion")
    assert R.assess(acct(B0, held=held), B0, trade("EUR_JPY", 1, 1_000.0)) == (1.0, "")


def test_cushion_checks_the_trade_at_its_cut_size():
    held = (("EUR_USD", 1, 2_000.0),)
    frac, why = R.assess(acct(98_500.0, held=held), B0, trade("EUR_JPY", 1, 1_000.0))
    assert frac == 0.5 and why.startswith("open-risk cap")
    frac, why = R.assess(acct(98_400.0, held=held), B0, trade("EUR_JPY", 1, 1_000.0))
    assert frac == 0.0 and why.startswith("4% cushion") and "this trade's 500.00" in why


def test_cushion_counts_floating_losses():
    g = R.refresh({}, B0, B0, utc("2026-11-26 10:00"))
    g = R.refresh(g, B0, 97_600.0, utc("2026-11-26 15:00"))
    held = (("EUR_USD", 1, 1_500.0),)
    frac, why = R.assess(acct(97_600.0, held=held), g["prague_ref"], trade("EUR_JPY", 1, 500.0))
    assert frac == 0.0 and why.startswith("4% cushion")


def test_assess_is_pure():
    a, t = acct(held=(("EUR_USD", 1, 500.0),)), trade("GBP_USD", 1, 1_000.0)
    keep = copy.deepcopy((a, t))
    R.assess(a, B0, t)
    assert (a, t) == keep


if __name__ == "__main__":
    fxtest.run(globals())

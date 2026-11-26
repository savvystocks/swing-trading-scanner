from datetime import datetime
from zoneinfo import ZoneInfo

import fxtest
import costs as C

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def ny(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=NY)


def test_long_buys_the_ask_and_sells_the_bid():
    assert C.entry_price(1, 1.1000, 1.1001) == 1.1001 and C.exit_price(1, 1.1000, 1.1001) == 1.1000


def test_short_sells_the_bid_and_buys_the_ask():
    assert C.entry_price(-1, 1.1000, 1.1001) == 1.1000 and C.exit_price(-1, 1.1000, 1.1001) == 1.1001


def test_flat_round_trip_costs_the_spread_and_commission():
    e, x = C.entry_price(1, 1.1000, 1.1001), C.exit_price(1, 1.1000, 1.1001)
    t = ny(2025, 1, 6, 10)
    assert fxtest.near(C.trade_pnl_usd("EUR_USD", 1, 100_000, e, x, t, t), -20.0, 1e-6)


def test_long_stop_gapped_through_books_the_open():
    assert C.stop_exit(1, 1.0950, 1.0900, 1.0890) == 1.0900
    assert fxtest.near(C.stop_exit(1, 1.0950, 1.0900, 1.0890, slip=0.00005), 1.08995)


def test_long_stop_touched_inside_the_bar_books_the_stop():
    assert C.stop_exit(1, 1.0950, 1.0990, 1.0940) == 1.0950
    assert C.stop_exit(1, 1.0950, 1.0990, 1.0960) is None


def test_short_stop_gapped_through_books_the_open():
    assert C.stop_exit(-1, 1.1050, 1.1100, 1.1110) == 1.1100
    assert fxtest.near(C.stop_exit(-1, 1.1050, 1.1100, 1.1110, slip=0.00005), 1.11005)
    assert C.stop_exit(-1, 1.1050, 1.1000, 1.1060) == 1.1050 and C.stop_exit(-1, 1.1050, 1.1000, 1.1040) is None


def test_commission_per_side_and_round_turn():
    assert C.commission_usd(100_000) == 10.0 and C.commission_usd(-100_000, "per_side") == 10.0
    assert C.commission_usd(100_000, "round_turn") == 5.0 and C.commission_usd(50_000, "per_side") == 5.0
    try:
        C.commission_usd(100_000, "per_lot")
    except KeyError:
        return
    raise AssertionError("an unknown basis was accepted")


def test_swap_nights_triple_wednesday():
    assert C.swap_nights(ny(2025, 1, 6, 10), ny(2025, 1, 9, 10)) == 5
    assert C.swap_nights(ny(2025, 1, 8, 16, 59), ny(2025, 1, 8, 17, 1)) == 3
    assert C.swap_nights(ny(2025, 1, 6, 18), ny(2025, 1, 6, 20)) == 0


def test_swap_weekend_is_one_friday_night():
    assert C.swap_nights(ny(2025, 1, 10, 10), ny(2025, 1, 13, 10)) == 1
    assert C.swap_nights(ny(2025, 1, 10, 10), ny(2025, 1, 13, 10), triple_weekday=4) == 3


def test_swap_seven_nights_a_week():
    assert C.swap_nights(ny(2025, 1, 6, 12), ny(2025, 2, 3, 12)) == 28


def test_swap_rollover_follows_new_york_dst():
    assert C.swap_nights(datetime(2025, 3, 10, 21, 30, tzinfo=UTC), datetime(2025, 3, 10, 22, 30, tzinfo=UTC)) == 0
    assert C.swap_nights(datetime(2025, 3, 7, 21, 30, tzinfo=UTC), datetime(2025, 3, 7, 22, 30, tzinfo=UTC)) == 1


def test_swap_points_to_money():
    assert fxtest.near(C.swap_quote(-9.21, "EUR_USD", 100_000, 1), -9.21)
    assert fxtest.near(C.swap_quote(-21.10, "USDJPY", -100_000, 1), -2110.0)
    assert fxtest.near(C.to_usd(15_000.0, "USD_JPY", 150.0), 100.0) and C.to_usd(100.0, "EURUSD", 1.1) == 100.0


def test_cross_without_usd_leg_refused():
    try:
        C.to_usd(100.0, "EUR_JPY", 160.0)
    except ValueError:
        return
    raise AssertionError("a cross was converted")


def test_eurusd_long_net_of_swap_and_commission():
    args = ("EUR_USD", 1, 100_000, 1.10005, 1.10500, ny(2025, 1, 6, 10), ny(2025, 1, 9, 10))
    assert fxtest.near(C.trade_pnl_usd(*args), 495.0 - 46.05 - 10.0, 1e-6)
    assert fxtest.near(C.trade_pnl_usd(*args, basis="round_turn"), 495.0 - 46.05 - 5.0, 1e-6)


def test_usdjpy_short_net_in_dollars():
    got = C.trade_pnl_usd("USD_JPY", -1, 100_000, 150.000, 149.000, ny(2025, 1, 10, 10), ny(2025, 1, 13, 10))
    assert fxtest.near(got, (100_000.0 - 2110.0) / 149.0 - 10.0, 1e-6)


if __name__ == "__main__":
    fxtest.run(globals())

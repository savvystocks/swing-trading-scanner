import os

import fxtest

os.environ.setdefault("OANDA_ACCOUNT_ID", "101-000-0000000-001")
os.environ.setdefault("OANDA_API_TOKEN", "test-token")
import fx_oanda_orders as O


def test_practice_host_accepted():
    assert O.HOST == "https://api-fxpractice.oanda.com"
    br = O.Practice()
    assert br.acct == os.environ["OANDA_ACCOUNT_ID"]


def test_live_host_refused():
    old = O.HOST
    try:
        O.HOST = "https://api-fxtrade.oanda.com"
        try:
            O.Practice()
        except RuntimeError as e:
            assert "practice host only" in str(e)
        else:
            raise AssertionError("a live host was accepted")
    finally:
        O.HOST = old


def test_requests_go_to_the_practice_host():
    seen = []

    class R:
        status_code = 200

        def json(self):
            return {"account": {"balance": "100000", "NAV": "100000"}}

    real = O.requests.request
    O.requests.request = lambda method, url, **kw: seen.append(url) or R()
    try:
        O.Practice().summary()
    finally:
        O.requests.request = real
    assert seen and seen[0].startswith("https://api-fxpractice.oanda.com/v3/accounts/")


def test_market_fill_parsed():
    br = O.Practice()
    sent = []
    br._req = lambda m, p, body=None: sent.append(body) or {"orderFillTransaction": {
        "price": "1.05012", "time": "2026-11-25T23:03:00Z", "halfSpreadCost": "0.6", "commission": "0",
        "tradeOpened": {"tradeID": "77", "units": "97656"}}}
    f = br.market("EUR_USD", 97656, 1.045, "EUR_USD_2026-11-25")
    assert f == {"filled": True, "trade_id": "77", "fill": 1.05012, "time": "2026-11-25T23:03:00Z", "units": 97656,
                 "half_spread_cost": 0.6, "commission": 0.0}
    o = sent[0]["order"]
    assert o["type"] == "MARKET" and o["timeInForce"] == "FOK" and o["positionFill"] == "OPEN_ONLY"
    assert o["stopLossOnFill"]["price"] == "1.04500" and o["units"] == "97656"


def test_market_cancel_parsed():
    br = O.Practice()
    br._req = lambda m, p, body=None: {"orderCancelTransaction": {"reason": "MARKET_HALTED"}}
    f = br.market("USD_JPY", -100, 151.2, "x")
    assert f["filled"] is False and f["reason"] == "MARKET_HALTED"


def test_price_decimals():
    br = O.Practice()
    assert br.px("EUR_USD", 1.0451234) == "1.04512" and br.px("USD_JPY", 151.23456) == "151.235"


if __name__ == "__main__":
    fxtest.run(globals())

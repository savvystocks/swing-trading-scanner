"""OANDA PRACTICE order module for the forex paper books. Refuses any host but the practice API.
Market entry with the broker stop attached at the fill, take-profit set from the actual fill, close by trade id,
and the loss guard (2.5% day stop from the New York day-start balance, 6% total pause from the first recorded balance)."""
import os

import requests

HOST = "https://api-fxpractice.oanda.com"
DECIMALS = {"EUR_USD": 5, "USD_JPY": 3}


class Practice:
    def __init__(self):
        assert HOST.startswith("https://api-fxpractice."), "practice host only"
        self.acct = os.environ["OANDA_ACCOUNT_ID"]
        self.h = {"Authorization": "Bearer " + os.environ["OANDA_API_TOKEN"], "Content-Type": "application/json"}

    def _req(self, method, path, body=None):
        r = requests.request(method, f"{HOST}/v3/accounts/{self.acct}{path}", headers=self.h, json=body, timeout=30)
        try:
            j = r.json()
        except ValueError:
            j = {"raw": r.text}
        if r.status_code >= 400:
            raise RuntimeError(f"OANDA {method} {path} -> {r.status_code}: {j}")
        return j

    def summary(self):
        return self._req("GET", "/summary")["account"]

    def price(self, pair):
        p = self._req("GET", f"/pricing?instruments={pair}")["prices"][0]
        return float(p["bids"][0]["price"]), float(p["asks"][0]["price"]), bool(p.get("tradeable", True))

    def px(self, pair, x):
        return f"{x:.{DECIMALS[pair]}f}"

    def market(self, pair, units, stop, client_id):
        body = {"order": {"type": "MARKET", "instrument": pair, "units": str(int(units)), "timeInForce": "FOK",
                          "positionFill": "OPEN_ONLY", "stopLossOnFill": {"price": self.px(pair, stop), "timeInForce": "GTC"},
                          "clientExtensions": {"id": client_id[:120], "tag": "s26"},
                          "tradeClientExtensions": {"id": client_id[:120], "tag": "s26"}}}
        j = self._req("POST", "/orders", body)
        f = j.get("orderFillTransaction")
        if not f or "tradeOpened" not in f:
            c = j.get("orderCancelTransaction") or j.get("orderRejectTransaction") or {}
            return {"filled": False, "reason": c.get("reason", "no fill"), "raw": {k: j[k] for k in j if k.endswith("Transaction")}}
        return {"filled": True, "trade_id": f["tradeOpened"]["tradeID"], "fill": float(f["price"]), "time": f["time"],
                "units": int(float(f["tradeOpened"]["units"])), "half_spread_cost": float(f.get("halfSpreadCost", 0) or 0),
                "commission": float(f.get("commission", 0) or 0)}

    def set_tp(self, pair, trade_id, tp):
        return self._req("PUT", f"/trades/{trade_id}/orders",
                         {"takeProfit": {"price": self.px(pair, tp), "timeInForce": "GTC"}})

    def trade(self, trade_id):
        return self._req("GET", f"/trades/{trade_id}")["trade"]

    def close(self, trade_id):
        return self._req("PUT", f"/trades/{trade_id}/close", {"units": "ALL"})


def guard_ok(st, acct, ny_day):
    """Loss guard. Returns (ok, reason). Day reference = balance at the first run of each New York trading day."""
    nav, bal = float(acct["NAV"]), float(acct["balance"])
    g = st.setdefault("guard", {})
    g.setdefault("B0", bal)
    if g.get("day") != ny_day:
        g["day"], g["day_ref"] = ny_day, bal
    B0 = g["B0"]
    if g.get("paused") or nav <= 0.94 * B0:
        g["paused"] = True
        return False, f"PAUSED: NAV {nav:,.0f} at or below 94% of the start balance {B0:,.0f} (6% total pause, no new trades)"
    if nav <= g["day_ref"] - 0.025 * B0:
        return False, f"day stop: NAV {nav:,.0f} is 2.5% of {B0:,.0f} below today's start {g['day_ref']:,.0f}"
    return True, ""

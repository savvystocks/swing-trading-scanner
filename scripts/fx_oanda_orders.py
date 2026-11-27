"""OANDA PRACTICE order module for the forex paper books. Refuses any host but the practice API.
Market entry with the broker stop attached at the fill, take-profit set from the actual fill, close by trade id.
The loss limits live in scripts/fx_risk_engine.py."""
import os

import requests

HOST = "https://api-fxpractice.oanda.com"
DECIMALS = {"EUR_USD": 5, "USD_JPY": 3, "GBP_USD": 5, "AUD_USD": 5, "NZD_USD": 5, "USD_CHF": 5, "USD_CAD": 5, "USD_NOK": 5,
            "USD_SEK": 5}


class Practice:
    def __init__(self):
        if not HOST.startswith("https://api-fxpractice."):
            raise RuntimeError("practice host only")
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

    def market(self, pair, units, stop, client_id, tag="s26"):
        body = {"order": {"type": "MARKET", "instrument": pair, "units": str(int(units)), "timeInForce": "FOK",
                          "positionFill": "OPEN_ONLY", "stopLossOnFill": {"price": self.px(pair, stop), "timeInForce": "GTC"},
                          "clientExtensions": {"id": client_id[:120], "tag": tag},
                          "tradeClientExtensions": {"id": client_id[:120], "tag": tag}}}
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

import os
import json
import urllib.request
import urllib.error


PAPER_BASE = "https://paper-api.alpaca.markets"


def _key():
    return os.environ.get("ALPACA_PAPER_API_KEY") or os.environ.get("ALPACA_API_KEY", "")


def _secret():
    return os.environ.get("ALPACA_PAPER_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY", "")


def enabled():
    return bool(_key() and _secret())


def _headers():
    return {
        "APCA-API-KEY-ID": _key(),
        "APCA-API-SECRET-KEY": _secret(),
        "Content-Type": "application/json",
    }


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(PAPER_BASE + path, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return (json.loads(raw) if raw else {}), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:200]}"


def account():
    return _req("GET", "/v2/account")


def positions():
    return _req("GET", "/v2/positions")


def size_spread(combo, account_gbp=4000.0, size_pct=25.0, fx=1.26):
    if hasattr(combo, "as_dict"):
        combo = combo.as_dict()
    net_debit = combo.get("net_debit") or 0
    if net_debit > 0:
        per_spread_gbp = net_debit * 100 / fx
    else:
        max_loss = combo.get("max_loss_per_spread") or 0
        per_spread_gbp = max_loss / fx
    if per_spread_gbp <= 0:
        return 0
    budget_gbp = account_gbp * size_pct / 100.0
    return max(0, int(budget_gbp // per_spread_gbp))


def _build_order_body(combo, contracts):
    if hasattr(combo, "as_dict"):
        combo = combo.as_dict()
    legs = combo.get("legs") or []
    order_legs = []
    for lg in legs:
        sym = lg.get("occ_symbol")
        if not sym:
            return None
        qty = lg.get("qty", 1)
        order_legs.append({
            "symbol": sym,
            "ratio_qty": str(abs(int(qty))),
            "side": "buy" if qty > 0 else "sell",
            "position_intent": "buy_to_open" if qty > 0 else "sell_to_open",
        })
    if not order_legs:
        return None
    body = {
        "order_class": "mleg",
        "qty": str(int(contracts)),
        "type": "limit",
        "time_in_force": "day",
        "legs": order_legs,
    }
    net_debit = combo.get("net_debit") or 0
    net_credit = combo.get("net_credit") or 0
    if net_debit > 0:
        body["limit_price"] = str(round(net_debit, 2))
    elif net_credit > 0:
        body["limit_price"] = str(round(net_credit, 2))
    return body


def submit_spread(combo, contracts):
    if not enabled():
        return None, "no alpaca paper credentials"
    if contracts < 1:
        return None, "size below 1 contract"
    body = _build_order_body(combo, contracts)
    if body is None:
        return None, "could not build order legs"
    return _req("POST", "/v2/orders", body)


def account_pnl():
    acct, err = account()
    if err or not acct:
        return {"error": err}
    return {
        "equity": acct.get("equity"),
        "last_equity": acct.get("last_equity"),
        "cash": acct.get("cash"),
        "buying_power": acct.get("buying_power"),
    }

from datetime import datetime, timedelta, timezone


CONTRACT_MULTIPLIER = 100


def _intrinsic(right, strike, spot):
    if right == "call":
        return max(spot - strike, 0.0)
    return max(strike - spot, 0.0)


def _net_cost(legs):
    return sum(lg["qty"] * lg["mid"] for lg in legs)


def _payoff(legs, net_cost, spot):
    total = 0.0
    for lg in legs:
        total += lg["qty"] * _intrinsic(lg["right"], lg["strike"], spot)
    return (total - net_cost) * CONTRACT_MULTIPLIER


def _breakevens(legs, net_cost, breakpoints):
    pts = sorted(set(breakpoints))
    found = []
    for a, b in zip(pts, pts[1:]):
        pa = _payoff(legs, net_cost, a)
        pb = _payoff(legs, net_cost, b)
        if pa == 0.0 and pb == 0.0:
            continue
        if (pa < 0) != (pb < 0):
            if pa == 0.0:
                found.append(a)
            elif pb == 0.0:
                found.append(b)
            else:
                found.append(a + (b - a) * (0 - pa) / (pb - pa))
    out = []
    for x in found:
        if all(abs(x - y) > 1e-4 for y in out):
            out.append(round(x, 2))
    return out


def _leg(right, qty, c):
    return {
        "right": right,
        "qty": qty,
        "strike": float(c["strike"]),
        "mid": float(c["mid"]),
        "delta": c.get("delta"),
        "occ_symbol": c.get("occ_symbol") or c.get("symbol"),
        "dte": c.get("dte"),
        "expiration": c.get("expiration") or c.get("expiry"),
        "iv_pct": c.get("iv_pct"),
    }


class DefinedRiskCombo:
    def __init__(self, structure, underlying, legs, expiration=None, direction=None, note=None):
        self.structure = structure
        self.underlying = underlying
        self.legs = legs
        self.expiration = expiration
        self.direction = direction
        self.note = note
        self.multi_expiry = len({lg.get("expiration") for lg in legs if lg.get("expiration")}) > 1
        self._compute()

    def _compute(self):
        self.net_cost = round(_net_cost(self.legs), 4)
        self.net_debit = round(self.net_cost, 2) if self.net_cost > 0 else 0.0
        self.net_credit = round(-self.net_cost, 2) if self.net_cost < 0 else 0.0

        net_call_qty = sum(lg["qty"] for lg in self.legs if lg["right"] == "call")
        self.uncapped_upside = net_call_qty > 0
        undefined = net_call_qty < 0

        if self.multi_expiry:
            self.approx = True
            self.defined_risk = self.net_cost > 0
            self.max_loss = round(self.net_cost * CONTRACT_MULTIPLIER, 2) if self.net_cost > 0 else None
            self.max_profit = None
            self.breakevens = []
            self.risk_reward_ratio = None
            return

        self.approx = False
        strikes = sorted({lg["strike"] for lg in self.legs})
        breakpoints = [0.0] + strikes + [strikes[-1] * 3 + 10]
        payoffs = [_payoff(self.legs, self.net_cost, s) for s in breakpoints]
        worst = min(payoffs)
        best = max(payoffs)

        if undefined:
            self.defined_risk = False
            self.max_loss = None
        else:
            self.defined_risk = True
            self.max_loss = round(-worst, 2) if worst < 0 else 0.0

        self.max_profit = None if self.uncapped_upside else (round(best, 2) if best > 0 else 0.0)
        self.breakevens = _breakevens(self.legs, self.net_cost, breakpoints)
        if self.max_profit is not None and self.max_loss:
            self.risk_reward_ratio = round(self.max_profit / self.max_loss, 2)
        else:
            self.risk_reward_ratio = None

    def order_text(self):
        if self.net_debit > 0:
            return f"BUY_TO_OPEN net debit {self.net_debit}"
        if self.net_credit > 0:
            return f"SELL_TO_OPEN net credit {self.net_credit}"
        return "OPEN at even"

    def as_dict(self):
        return {
            "structure": self.structure,
            "underlying": self.underlying,
            "direction": self.direction,
            "expiration": self.expiration,
            "legs": self.legs,
            "net_debit": self.net_debit,
            "net_credit": self.net_credit,
            "limit_price": self.net_debit if self.net_debit > 0 else self.net_credit,
            "order": self.order_text(),
            "max_loss_per_spread": self.max_loss,
            "max_profit_per_spread": self.max_profit,
            "uncapped_upside": self.uncapped_upside,
            "breakevens": self.breakevens,
            "risk_reward_ratio": self.risk_reward_ratio,
            "defined_risk": self.defined_risk,
            "approx": self.approx,
            "note": self.note,
        }


def bull_call_debit_spread(underlying, long_call, short_call, expiration=None):
    legs = [_leg("call", 1, long_call), _leg("call", -1, short_call)]
    return DefinedRiskCombo("bull_call_debit_spread", underlying, legs,
                            expiration or long_call.get("expiration"), "BULLISH")


def bear_put_debit_spread(underlying, long_put, short_put, expiration=None):
    legs = [_leg("put", 1, long_put), _leg("put", -1, short_put)]
    return DefinedRiskCombo("bear_put_debit_spread", underlying, legs,
                            expiration or long_put.get("expiration"), "BEARISH")


def bull_put_credit_spread(underlying, short_put, long_put, expiration=None):
    legs = [_leg("put", -1, short_put), _leg("put", 1, long_put)]
    return DefinedRiskCombo("bull_put_credit_spread", underlying, legs,
                            expiration or short_put.get("expiration"), "BULLISH")


def bear_call_credit_spread(underlying, short_call, long_call, expiration=None):
    legs = [_leg("call", -1, short_call), _leg("call", 1, long_call)]
    return DefinedRiskCombo("bear_call_credit_spread", underlying, legs,
                            expiration or short_call.get("expiration"), "BEARISH")


def iron_condor(underlying, short_put, long_put, short_call, long_call, expiration=None):
    legs = [
        _leg("put", -1, short_put), _leg("put", 1, long_put),
        _leg("call", -1, short_call), _leg("call", 1, long_call),
    ]
    return DefinedRiskCombo("iron_condor", underlying, legs,
                            expiration or short_put.get("expiration"), "NEUTRAL")


def calendar_spread(underlying, right, short_front, long_back):
    legs = [_leg(right, -1, short_front), _leg(right, 1, long_back)]
    return DefinedRiskCombo("calendar_spread", underlying, legs,
                            long_back.get("expiration"), "VOL_EXPANSION",
                            note="back-month value at front expiry needs a vol model; max loss = net debit")


def put_ratio_backspread(underlying, short_put, long_put, ratio=2, expiration=None):
    legs = [_leg("put", -1, short_put), _leg("put", ratio, long_put)]
    return DefinedRiskCombo("put_ratio_backspread", underlying, legs,
                            expiration or short_put.get("expiration"), "BEARISH_CONVEX")


def call_ratio_backspread(underlying, short_call, long_call, ratio=2, expiration=None):
    legs = [_leg("call", -1, short_call), _leg("call", ratio, long_call)]
    return DefinedRiskCombo("call_ratio_backspread", underlying, legs,
                            expiration or short_call.get("expiration"), "BULLISH_CONVEX")


def broken_wing_butterfly(underlying, right, long_near, short_mid, long_far, expiration=None):
    legs = [_leg(right, 1, long_near), _leg(right, -2, short_mid), _leg(right, 1, long_far)]
    return DefinedRiskCombo("broken_wing_butterfly", underlying, legs,
                            expiration or short_mid.get("expiration"), "NEUTRAL_SKEW")


def deep_itm_vertical(underlying, right, long_deep, short_otm, expiration=None):
    direction = "BULLISH" if right == "call" else "BEARISH"
    legs = [_leg(right, 1, long_deep), _leg(right, -1, short_otm)]
    return DefinedRiskCombo("deep_itm_vertical", underlying, legs,
                            expiration or long_deep.get("expiration"), direction,
                            note="notional-capped synthetic replacement")


def scale_out_plan(combo):
    if isinstance(combo, DefinedRiskCombo):
        combo = combo.as_dict()
    net_debit = combo.get("net_debit") or 0
    net_credit = combo.get("net_credit") or 0
    if net_debit > 0:
        return {
            "family": "debit",
            "entry_premium": round(net_debit, 2),
            "tiers": [
                {"tier": 1, "premium_gain_pct": 100, "premium_price": round(net_debit * 2, 2),
                 "action": "Sell 1/3 -> removes initial capital risk"},
                {"tier": 2, "premium_gain_pct": 200, "premium_price": round(net_debit * 3, 2),
                 "action": "Sell 1/3 -> bank compounding growth"},
                {"tier": 3, "premium_gain_pct": 300, "premium_price": round(net_debit * 4, 2),
                 "action": "Hold final 1/3 runner with a 20% trailing stop"},
            ],
            "runner_trail_pct": 20,
        }
    if net_credit > 0:
        return {
            "family": "credit",
            "entry_premium": round(net_credit, 2),
            "profit_take": {"pct_of_max_credit": 50, "buyback_price": round(net_credit * 0.5, 2),
                            "action": "Buy to close at 50% of max credit"},
            "time_exit_dte": 21,
            "note": "capped-profit structure: thirds matrix N/A; manage at 50% credit or 21 DTE",
        }
    return None


def notional_cap(contract, tranche_gbp, fx=1.26, cap_pct=10, delta_floor=0.85):
    mid = float(contract.get("mid") or 0)
    delta = abs(contract.get("delta") or 0)
    cash_gbp = mid * CONTRACT_MULTIPLIER / fx if fx else 0.0
    cap_gbp = tranche_gbp * cap_pct / 100.0
    breach = cash_gbp > cap_gbp
    return {
        "single_contract_gbp": round(cash_gbp, 2),
        "cap_gbp": round(cap_gbp, 2),
        "cap_pct": cap_pct,
        "is_synthetic_replacement": delta >= delta_floor,
        "breach": breach,
        "directive": "restructure_to_deep_itm_vertical" if breach else "single_contract_ok",
        "restructure_note": "Sell a ~0.60 delta OTM leg against the deep-ITM long to bound out-of-pocket cash"
        if breach else None,
    }


def pin_risk_warning(expiration_iso, now_utc=None):
    try:
        exp = datetime.strptime(str(expiration_iso)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    now_et = now_utc
    try:
        from zoneinfo import ZoneInfo
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        pass
    pin_day = exp - timedelta(days=(exp.weekday() - 3) % 7)
    if now_et.date() == pin_day and (now_et.hour, now_et.minute) >= (15, 0):
        return {
            "warn": True,
            "expiration": exp.isoformat(),
            "pin_day": pin_day.isoformat(),
            "message": f"PIN-RISK 15:00 EST on {pin_day.isoformat()} (Thu of {exp.isoformat()} expiry week): "
                       f"liquidate all outstanding spreads to remove weekend assignment risk.",
        }
    return None

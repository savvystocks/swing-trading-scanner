import os
import math
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_SIZE_USD = 4000
DEFAULT_POSITION_SIZE_PCT = 20
DEFAULT_STOP_LOSS_PCT = 50
DEFAULT_MAX_CONCURRENT = 4
DEFAULT_LOTTERY_TARGET_RETURN_PCT = 500
DEFAULT_LOTTERY_TARGET_DAYS = 14
DEFAULT_DTE_MIN = 7
DEFAULT_DTE_MAX = 21
DEFAULT_OTM_PCT_MIN = 5
DEFAULT_OTM_PCT_MAX = 18


def _env_int(name, default):
    try:
        v = os.environ.get(name, "")
        return int(v) if v else default
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        v = os.environ.get(name, "")
        return float(v) if v else default
    except (TypeError, ValueError):
        return default


def _parse_pct_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"-?\d+(?:\.\d+)?", value)
        if m:
            try:
                return float(m.group(0))
            except (TypeError, ValueError):
                return None
    return None


def get_account_settings():
    return {
        "account_size_usd": _env_float("ACCOUNT_SIZE_USD", DEFAULT_ACCOUNT_SIZE_USD),
        "position_size_pct": _env_float("POSITION_SIZE_PCT", DEFAULT_POSITION_SIZE_PCT),
        "stop_loss_pct": _env_float("STOP_LOSS_PCT", DEFAULT_STOP_LOSS_PCT),
        "max_concurrent": _env_int("MAX_CONCURRENT_LOTTERY", DEFAULT_MAX_CONCURRENT),
        "target_return_pct": _env_float("LOTTERY_TARGET_RETURN_PCT", DEFAULT_LOTTERY_TARGET_RETURN_PCT),
        "target_days": _env_int("LOTTERY_TARGET_DAYS", DEFAULT_LOTTERY_TARGET_DAYS),
    }


def fetch_lottery_chain(symbol, current_price, dte_min=DEFAULT_DTE_MIN, dte_max=DEFAULT_DTE_MAX,
                        otm_pct_min=DEFAULT_OTM_PCT_MIN, otm_pct_max=DEFAULT_OTM_PCT_MAX,
                        direction="call"):
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        return None, "no Alpaca keys"
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None, "alpaca-py not importable"

    today = datetime.now()
    min_exp = (today + timedelta(days=dte_min)).strftime("%Y-%m-%d")
    max_exp = (today + timedelta(days=dte_max)).strftime("%Y-%m-%d")

    if direction == "call":
        strike_lo = current_price * (1 + otm_pct_min / 100)
        strike_hi = current_price * (1 + otm_pct_max / 100)
    else:
        strike_lo = current_price * (1 - otm_pct_max / 100)
        strike_hi = current_price * (1 - otm_pct_min / 100)

    try:
        client = OptionHistoricalDataClient(api_key, api_secret)
        request = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(strike_lo, 2)),
            strike_price_lte=str(round(strike_hi, 2)),
            type=direction,
        )
        snapshots = client.get_option_chain(request)
    except Exception as e:
        return None, f"Alpaca chain fetch error: {type(e).__name__}: {e}"

    if not snapshots:
        return None, "empty chain"
    return snapshots, None


def parse_contract(contract_symbol, snapshot):
    sym_str = contract_symbol if isinstance(contract_symbol, str) else str(contract_symbol)
    m = re.match(r"([A-Z]+)(\d{6})([CP])(\d+)", sym_str)
    if not m:
        return None
    exp_raw = m.group(2)
    contract_right = m.group(3)
    strike_raw = m.group(4)
    expiration = f"20{exp_raw[:2]}-{exp_raw[2:4]}-{exp_raw[4:6]}"
    strike = int(strike_raw) / 1000
    dte = (datetime.strptime(expiration, "%Y-%m-%d") - datetime.now()).days

    quote = getattr(snapshot, "latest_quote", None)
    greeks = getattr(snapshot, "greeks", None)
    trade = getattr(snapshot, "latest_trade", None)
    if not quote or not greeks:
        return None

    bid = float(quote.bid_price) if quote.bid_price else 0
    ask = float(quote.ask_price) if quote.ask_price else 0
    if bid <= 0 or ask <= 0:
        return None
    mid = (bid + ask) / 2
    if mid <= 0.05:
        return None
    spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 100
    delta = float(greeks.delta) if greeks.delta else None
    if delta is None:
        return None

    iv_raw = getattr(snapshot, "implied_volatility", None)
    if iv_raw is None:
        iv_raw = getattr(greeks, "implied_volatility", 0) or 0
    try:
        iv = float(iv_raw) if iv_raw else 0.0
    except (TypeError, ValueError):
        iv = 0.0
    iv_pct = iv * 100 if iv and iv < 5 else iv

    vol = int(trade.size) if trade and getattr(trade, "size", None) else 0

    return {
        "symbol": sym_str,
        "strike": strike,
        "expiration": expiration,
        "dte": dte,
        "right": contract_right,
        "bid": bid,
        "ask": ask,
        "mid": round(mid, 2),
        "spread_pct": round(spread_pct, 1),
        "delta": round(delta, 3),
        "gamma": round(abs(float(greeks.gamma)), 4) if greeks.gamma else 0,
        "theta": round(float(greeks.theta), 4) if greeks.theta else 0,
        "vega": round(float(greeks.vega), 4) if greeks.vega else 0,
        "iv_pct": round(iv_pct, 1),
        "volume": vol,
        "cost_per_contract": round(mid * 100, 0),
    }


BINARY_CATALYST_TYPES = {"earnings", "fda", "ma", "clinical", "data_readout", "pdufa"}


def estimate_iv_crush_pct(iv_pct, days_until_event, dte, catalyst_type=None):
    if iv_pct is None or iv_pct <= 0:
        return 0
    if days_until_event is None or dte is None:
        return 0
    if days_until_event > dte:
        return 0
    is_binary = (catalyst_type or "").lower() in BINARY_CATALYST_TYPES
    if not is_binary and iv_pct < 60:
        return 0
    if iv_pct >= 100:
        base = 50
    elif iv_pct >= 80:
        base = 40
    elif iv_pct >= 60:
        base = 30
    elif iv_pct >= 40:
        base = 20
    else:
        base = 10
    if is_binary:
        return base
    return base // 2


def adjusted_required_move_pct(base_move_pct, iv_crush_pct):
    if iv_crush_pct <= 0:
        return base_move_pct
    factor = 100 / max(50, 100 - iv_crush_pct)
    return base_move_pct * factor


def required_stock_price_for_target_roi(strike, premium, target_roi_pct=500):
    target_premium = premium * (1 + target_roi_pct / 100)
    return strike + target_premium


def required_move_pct(current_price, target_stock_price):
    if current_price <= 0:
        return None
    return (target_stock_price - current_price) / current_price * 100


def breakeven(strike, premium):
    return strike + premium


def select_best_lottery_contract(snapshots, current_price, target_roi_pct=500,
                                  max_cost_per_contract_usd=None, max_pct_of_budget=1.0,
                                  position_budget_usd=None):
    if not snapshots:
        return None, "empty"
    if max_cost_per_contract_usd is None and position_budget_usd:
        max_cost_per_contract_usd = position_budget_usd * max_pct_of_budget
    if max_cost_per_contract_usd is None:
        max_cost_per_contract_usd = 400
    candidates = []
    rejects = {"parse": 0, "delta": 0, "spread": 0, "cost": 0, "spread_too_wide": 0}
    for sym, snap in snapshots.items():
        c = parse_contract(sym, snap)
        if not c:
            rejects["parse"] += 1
            continue
        abs_delta = abs(c["delta"])
        if abs_delta < 0.08 or abs_delta > 0.50:
            rejects["delta"] += 1
            continue
        if c["cost_per_contract"] > max_cost_per_contract_usd:
            rejects["cost"] += 1
            continue
        if c["spread_pct"] > 30:
            rejects["spread_too_wide"] += 1
            continue
        target_stock = required_stock_price_for_target_roi(c["strike"], c["mid"], target_roi_pct)
        rmove = required_move_pct(current_price, target_stock)
        if rmove is None:
            continue
        c["target_stock_price"] = round(target_stock, 2)
        c["required_move_pct"] = round(rmove, 1)
        c["breakeven"] = round(breakeven(c["strike"], c["mid"]), 2)
        c["breakeven_pct_move"] = round((c["breakeven"] - current_price) / current_price * 100, 1)
        score = (
            abs_delta * 50
            - c["spread_pct"]
            - c["dte"] * 0.5
            - max(0, rmove - 18) * 0.8
        )
        c["_score"] = score
        candidates.append(c)
    if not candidates:
        total = sum(rejects.values())
        if rejects.get("parse") == total:
            reason = f"chain too thin ({total} contracts, none parseable)"
        elif rejects.get("cost") == total:
            reason = f"all {total} contracts above ${max_cost_per_contract_usd:.0f} budget"
        elif rejects.get("delta") + rejects.get("parse") == total:
            reason = f"no contracts in delta 0.08-0.50 range (extended OTM or deep ITM only)"
        elif rejects.get("spread_too_wide") + rejects.get("parse") == total:
            reason = f"all contracts spread >30% (illiquid name)"
        else:
            reason = f"no contracts passed: parse={rejects['parse']} delta={rejects['delta']} cost={rejects['cost']} spread={rejects['spread_too_wide']}"
        return None, reason
    candidates.sort(key=lambda c: c["_score"], reverse=True)
    best = candidates[0]
    best.pop("_score", None)
    return best, None


def profit_probability(required_move_pct_, dte, expected_move_pct=None, p_outcome=0.55, vol_pct=None):
    base = 50.0 if required_move_pct_ <= 5 else \
           30.0 if required_move_pct_ <= 10 else \
           18.0 if required_move_pct_ <= 15 else \
           10.0 if required_move_pct_ <= 22 else \
           5.0 if required_move_pct_ <= 30 else \
           2.0

    if expected_move_pct is not None and expected_move_pct > 0:
        if expected_move_pct >= required_move_pct_ * 1.5:
            base = max(base, 55.0)
        elif expected_move_pct >= required_move_pct_:
            base = max(base, 42.0)
        elif expected_move_pct >= required_move_pct_ * 0.7:
            base = max(base, 28.0)
        else:
            base = base * 0.7

    outcome_mult = 0.6 + (p_outcome * 0.8)
    if dte < 5:
        outcome_mult *= 0.85
    elif dte > 21:
        outcome_mult *= 0.9

    prob = base * outcome_mult
    return round(min(75.0, max(2.0, prob)), 1)


def expected_value_pct(p_win_pct, target_return_pct, p_loss_pct, stop_loss_pct):
    p_w = p_win_pct / 100
    p_l = p_loss_pct / 100
    ev = p_w * target_return_pct - p_l * stop_loss_pct
    return round(ev, 1)


def likely_outcome_lines(current_price, target_stock_price, p_win_pct, stop_loss_pct,
                         expected_move_high_pct=None, expected_move_low_pct=None):
    p_loss = 100 - p_win_pct
    win_move = expected_move_high_pct if expected_move_high_pct else (target_stock_price - current_price) / current_price * 100
    loss_move = expected_move_low_pct if expected_move_low_pct is not None else -10.0
    win_price = current_price * (1 + win_move / 100)
    loss_price = current_price * (1 + loss_move / 100)
    return {
        "p_win_pct": p_win_pct,
        "p_loss_pct": round(p_loss, 1),
        "win_move_pct": round(win_move, 1),
        "win_price": round(win_price, 2),
        "loss_move_pct": round(loss_move, 1),
        "loss_price": round(loss_price, 2),
        "stop_triggers_at_premium_pct": -stop_loss_pct,
    }


def position_size(account_size_usd, position_size_pct, cost_per_contract):
    if cost_per_contract <= 0:
        return None
    target_dollars = account_size_usd * position_size_pct / 100
    contracts = int(target_dollars // cost_per_contract)
    if contracts <= 0:
        return None
    actual_dollars = contracts * cost_per_contract
    return {
        "contracts": contracts,
        "total_cost_usd": round(actual_dollars, 0),
        "pct_of_account": round(actual_dollars / account_size_usd * 100, 1),
    }


def stop_loss_dollar_amount(cost_per_contract, contracts, stop_loss_pct):
    return round(cost_per_contract * contracts * stop_loss_pct / 100, 0)


def select_bull_call_spread(snapshots, current_price, max_cost_usd=400, target_roi_pct=500):
    if not snapshots:
        return None
    parsed = []
    for sym, snap in snapshots.items():
        c = parse_contract(sym, snap)
        if c and abs(c["delta"]) >= 0.20:
            parsed.append(c)
    if len(parsed) < 2:
        return None

    by_exp = {}
    for c in parsed:
        by_exp.setdefault(c["expiration"], []).append(c)

    best_spread = None
    best_score = -1e9
    for exp, group in by_exp.items():
        group.sort(key=lambda c: c["strike"])
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                lng = group[i]
                shr = group[j]
                if abs(lng["delta"]) < 0.30 or abs(lng["delta"]) > 0.65:
                    continue
                width = shr["strike"] - lng["strike"]
                if width <= 0 or width > current_price * 0.20:
                    continue
                debit = lng["mid"] - shr["mid"]
                if debit <= 0.05:
                    continue
                cost = debit * 100
                if cost > max_cost_usd:
                    continue
                max_profit = (width - debit) * 100
                if max_profit <= 0:
                    continue
                rr = max_profit / cost if cost > 0 else 0
                if rr < 0.5:
                    continue
                breakeven_p = lng["strike"] + debit
                be_pct = (breakeven_p - current_price) / current_price * 100
                profit_at_short = max_profit
                score = rr * 10 - be_pct * 0.3 - lng["dte"] * 0.2
                if score > best_score:
                    best_score = score
                    best_spread = {
                        "long_leg": {"strike": lng["strike"], "mid": lng["mid"], "delta": lng["delta"]},
                        "short_leg": {"strike": shr["strike"], "mid": shr["mid"], "delta": shr["delta"]},
                        "expiration": exp,
                        "dte": lng["dte"],
                        "width": round(width, 2),
                        "net_debit": round(debit, 2),
                        "cost_per_spread": round(cost, 0),
                        "max_profit_per_spread": round(max_profit, 0),
                        "risk_reward_ratio": round(rr, 2),
                        "breakeven": round(breakeven_p, 2),
                        "breakeven_pct_move": round(be_pct, 1),
                    }
    return best_spread


def build_lottery_ticket(symbol, current_price, deep_research_data=None,
                          dte_min=DEFAULT_DTE_MIN, dte_max=DEFAULT_DTE_MAX,
                          otm_pct_min=DEFAULT_OTM_PCT_MIN, otm_pct_max=DEFAULT_OTM_PCT_MAX):
    settings = get_account_settings()
    target_roi = settings["target_return_pct"]
    stop_loss = settings["stop_loss_pct"]

    snapshots, fetch_err = fetch_lottery_chain(symbol, current_price, dte_min, dte_max, otm_pct_min, otm_pct_max)
    if not snapshots:
        return {"qualified": False, "reason": fetch_err or "no chain available"}

    position_budget_usd = settings["account_size_usd"] * settings["position_size_pct"] / 100
    contract, sel_err = select_best_lottery_contract(
        snapshots,
        current_price,
        target_roi_pct=target_roi,
        position_budget_usd=position_budget_usd,
    )

    if not contract:
        snapshots_wide, _ = fetch_lottery_chain(symbol, current_price, dte_min, dte_max + 7, 0, 25)
        if snapshots_wide and snapshots_wide is not snapshots:
            contract, sel_err_wide = select_best_lottery_contract(
                snapshots_wide,
                current_price,
                target_roi_pct=target_roi,
                position_budget_usd=position_budget_usd,
            )
            if contract:
                contract["fallback_range_used"] = "0-25% OTM, +7d DTE"

    if not contract:
        return {"qualified": False, "reason": sel_err or "no qualifying contract"}

    p_outcome = 0.55
    expected_high = None
    expected_low = None
    catalyst_type = None
    days_until_event = None
    if deep_research_data:
        op = deep_research_data.get("outcome_prediction") or {}
        em = deep_research_data.get("expected_move") or {}
        cs = deep_research_data.get("catalyst_status") or {}
        prob = _parse_pct_number(op.get("outcome_probability_pct"))
        if prob is not None:
            p_outcome = prob / 100
        expected_high = _parse_pct_number(em.get("if_positive_pct"))
        expected_low = _parse_pct_number(em.get("if_negative_pct"))
        catalyst_type = op.get("catalyst_type")
        days_until_event = cs.get("days_until")
        if isinstance(days_until_event, str):
            try:
                days_until_event = int(days_until_event)
            except (TypeError, ValueError):
                days_until_event = None

    iv_crush = estimate_iv_crush_pct(
        contract.get("iv_pct"),
        days_until_event,
        contract.get("dte"),
        catalyst_type,
    )
    if iv_crush > 0:
        adjusted_move = adjusted_required_move_pct(contract["required_move_pct"], iv_crush)
        contract["iv_crush_estimated_pct"] = iv_crush
        contract["required_move_pct_iv_adjusted"] = round(adjusted_move, 1)
        contract["target_stock_price_iv_adjusted"] = round(
            current_price * (1 + adjusted_move / 100), 2
        )
    else:
        contract["iv_crush_estimated_pct"] = 0
        contract["required_move_pct_iv_adjusted"] = contract["required_move_pct"]
        contract["target_stock_price_iv_adjusted"] = contract["target_stock_price"]

    p_win = profit_probability(
        contract["required_move_pct_iv_adjusted"],
        contract["dte"],
        expected_move_pct=expected_high,
        p_outcome=p_outcome,
    )
    ev = expected_value_pct(p_win, target_roi, 100 - p_win, stop_loss)
    outcome = likely_outcome_lines(
        current_price,
        contract["target_stock_price"],
        p_win,
        stop_loss,
        expected_move_high_pct=expected_high,
        expected_move_low_pct=expected_low,
    )
    pos = position_size(settings["account_size_usd"], settings["position_size_pct"], contract["cost_per_contract"])
    if not pos:
        return {"qualified": False, "reason": f"contract too expensive (${contract['cost_per_contract']}) for account size ${settings['account_size_usd']}"}

    stop_dollars = stop_loss_dollar_amount(contract["cost_per_contract"], pos["contracts"], stop_loss)
    stop_premium = round(contract["mid"] * (1 - stop_loss / 100), 2)

    spread_alt = None
    try:
        spread_alt = select_bull_call_spread(
            snapshots, current_price,
            max_cost_usd=settings["account_size_usd"] * settings["position_size_pct"] / 100,
            target_roi_pct=target_roi,
        )
    except Exception:
        spread_alt = None

    return {
        "qualified": True,
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "settings": settings,
        "contract": contract,
        "stop_premium": stop_premium,
        "stop_dollars": stop_dollars,
        "position": pos,
        "profit_probability_pct": p_win,
        "expected_value_pct": ev,
        "likely_outcome": outcome,
        "spread_alternative": spread_alt,
        "p_outcome_used": round(p_outcome, 2),
    }

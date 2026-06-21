import os


def _env_float(key, default):
    raw = os.environ.get(key, "")
    if isinstance(raw, str):
        raw = raw.strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def get_config():
    return {
        "calendar_ivr_ceiling": _env_float("VAULT_CALENDAR_IVR_CEIL", 25.0),
        "directional_ivr_ceiling": _env_float("VAULT_DIRECTIONAL_IVR_CEIL", 50.0),
        "high_ivr_floor": _env_float("VAULT_HIGH_IVR_FLOOR", 50.0),
        "condor_ivrv_floor": _env_float("VAULT_CONDOR_IVRV_FLOOR", 1.20),
        "calendar_ivrv_ceiling": _env_float("VAULT_CALENDAR_IVRV_CEIL", 1.05),
        "calendar_ts_floor": _env_float("VAULT_CALENDAR_TS_FLOOR", -0.02),
        "backspread_skew_floor": _env_float("VAULT_BACKSPREAD_SKEW_FLOOR", 0.05),
        "condor_adx_ceiling": _env_float("VAULT_CONDOR_ADX_CEIL", 20.0),
    }


_INFO = {
    "DEBIT_VERTICAL": {"family": "debit", "alert": "Directional debit vertical (V7 core): long ~0.40d, short ~0.25d, 30-45 DTE"},
    "IRON_CONDOR": {"family": "credit", "alert": "Delta-neutral income: sell ~16d wings, 30-45 DTE, take 50% credit / 21 DTE"},
    "CALENDAR": {"family": "debit", "alert": "Vol-expansion calendar: sell front / buy back at ATM pin"},
    "RATIO_BACKSPREAD": {"family": "credit", "alert": "Asymmetric convexity: sell 1 near / buy 2 far for ~even, financed by skew"},
    "STAND_DOWN_RICH_DIRECTIONAL": {"family": None, "alert": "Directional edge but IVR rich + no fracture -> long premium too dear, stand down"},
    "NO_TRADE": {"family": None, "alert": "Flat + no harvestable IV state -> no trade"},
}


def route(state, config=None):
    if config is None:
        config = get_config()

    gate = (state.get("gate") or "FLAT").upper()
    ivr = state.get("ivr")
    ivrv = state.get("ivrv")
    ts_pct = state.get("ts_pct")
    adx = state.get("adx")
    in_value_area = bool(state.get("in_value_area"))
    fracture = bool(state.get("fracture"))
    skew = state.get("skew")

    if ivr is None:
        return _result("NO_TRADE", "missing IV rank", state)

    cal_ok = (ivr <= config["calendar_ivr_ceiling"]
              and ts_pct is not None and ts_pct >= config["calendar_ts_floor"]
              and ivrv is not None and ivrv <= config["calendar_ivrv_ceiling"])

    backwardation = bool(state.get("backwardation"))
    if gate in ("LONG", "SHORT"):
        if skew is not None and skew >= config["backspread_skew_floor"] and (
                (fracture and ivr > config["high_ivr_floor"]) or backwardation):
            why = "directional + VIX backwardation + financeable skew" if backwardation \
                else "directional + macro fracture + rich IVR + financeable skew"
            return _result("RATIO_BACKSPREAD", why, state)
        if cal_ok:
            return _result("CALENDAR", "directional but IV crushed + flat term -> own cheap vol", state)
        if config["calendar_ivr_ceiling"] < ivr <= config["directional_ivr_ceiling"]:
            return _result("DEBIT_VERTICAL", "directional edge + low-to-mid IVR", state)
        if ivr <= config["calendar_ivr_ceiling"]:
            return _result("DEBIT_VERTICAL", "directional edge + crushed IVR not calendar-friendly", state)
        return _result("STAND_DOWN_RICH_DIRECTIONAL", "directional edge but IVR>50 with no fracture", state)

    if (adx is not None and adx < config["condor_adx_ceiling"] and in_value_area
            and ivr > config["high_ivr_floor"] and ivrv is not None and ivrv >= config["condor_ivrv_floor"]):
        return _result("IRON_CONDOR", "flat + confirmed chop + rich IVR + positive VRP (IV/RV>=1.20)", state)
    if cal_ok:
        return _result("CALENDAR", "flat + IV crushed + flat term -> vol expansion play", state)
    return _result("NO_TRADE", "flat with no harvestable IV state", state)


def _result(structure, rationale, state):
    info = _INFO[structure]
    return {
        "structure": structure,
        "family": info["family"],
        "alert": info["alert"],
        "rationale": rationale,
        "tradeable": info["family"] is not None,
        "ivr": state.get("ivr"),
        "ivrv": state.get("ivrv"),
        "gate": (state.get("gate") or "FLAT").upper(),
    }

import os
import json
import uuid
import random
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    ET = timezone(timedelta(hours=-4))

import harvest_db as db

FEATURE_SET_VERSION = "v11-37feat"
INDEX_ROOTS = {"SPX", "SPXW", "SPXPM", "NDX", "NDXP", "RUT", "RUTW", "VIX", "VIXW",
               "XSP", "DJX", "OEX", "XEO", "MRUT", "NANOS", "VVIX"}
STATE_PATH = os.path.join(db.DATA_DIR, "harvest_state.json")


def _now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _git_sha():
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:12]
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _run_id():
    return os.environ.get("GITHUB_RUN_ID") or ("local-" + uuid.uuid4().hex[:8])


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _occ_symbol(ticker, expiry, strike, right):
    try:
        d = datetime.strptime(str(expiry), "%Y-%m-%d")
    except Exception:
        return None
    s = _f(strike)
    if s is None:
        return None
    r = "C" if str(right).lower().startswith("c") else "P"
    return "%s%s%s%08d" % (str(ticker).upper(), d.strftime("%y%m%d"), r, int(round(s * 1000)))


_WEEK_LAST_SESSION = {}


def _week_last_session(dt_et):
    monday = (dt_et - timedelta(days=dt_et.weekday())).date()
    if monday in _WEEK_LAST_SESSION:
        return _WEEK_LAST_SESSION[monday]
    friday = monday + timedelta(days=4)
    result = None
    try:
        import pandas_market_calendars as mcal
        sched = mcal.get_calendar("XNYS").schedule(start_date=monday.isoformat(), end_date=friday.isoformat())
        if len(sched.index):
            result = sched.index[-1].date()
    except Exception:
        result = None
    if result is None:
        d = friday
        while d.weekday() > 4:
            d -= timedelta(days=1)
        result = d
    _WEEK_LAST_SESSION[monday] = result
    return result


def _vertical_barrier_ts(signal_ts_ms, expiry_str):
    dt = datetime.fromtimestamp(signal_ts_ms / 1000.0, tz=timezone.utc).astimezone(ET)
    last = _week_last_session(dt)
    vt = datetime(last.year, last.month, last.day, 16, 0, tzinfo=ET)
    if vt < dt:
        nxt = _week_last_session(dt + timedelta(days=7))
        vt = datetime(nxt.year, nxt.month, nxt.day, 16, 0, tzinfo=ET)
    vt_ms = int(vt.astimezone(timezone.utc).timestamp() * 1000)
    exp_ms = None
    if expiry_str:
        try:
            ed = datetime.strptime(str(expiry_str), "%Y-%m-%d").replace(hour=16, minute=0, tzinfo=ET)
            exp_ms = int(ed.astimezone(timezone.utc).timestamp() * 1000)
        except Exception:
            exp_ms = None
    return min(v for v in (vt_ms, exp_ms) if v is not None)


def _load_state():
    st = {}
    if os.path.exists(STATE_PATH):
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            st = {}
    if st.get("date") != _today():
        st = {"date": _today(), "contracts": [], "tickers": {}, "payload_count": 0,
              "topn_count": 0, "random_count": 0}
    st.setdefault("contracts", [])
    st.setdefault("tickers", {})
    st.setdefault("payload_count", 0)
    st.setdefault("topn_count", 0)
    st.setdefault("random_count", 0)
    return st


def _save_state(st):
    try:
        os.makedirs(db.DATA_DIR, exist_ok=True)
        json.dump(st, open(STATE_PATH, "w", encoding="utf-8"), indent=2)
    except Exception:
        pass


def _append_jsonl(row):
    os.makedirs(db.INBOX_DIR, exist_ok=True)
    with open(db.inbox_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_row(row):
    try:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            _append_jsonl(row)
            return
        con = db.init_db()
        db.insert_candidate(con, row)
        con.close()
    except Exception:
        try:
            _append_jsonl(row)
        except Exception:
            pass


def _quote_from_flow(flow):
    bid = _f(flow.get("bid"))
    ask = _f(flow.get("ask"))
    price = _f(flow.get("price"))
    mid = None
    if bid is not None and ask is not None:
        mid = round((bid + ask) / 2.0, 4)
    spread_pct = None
    if bid is not None and ask is not None and ask > 0:
        spread_pct = round((ask - bid) / ask * 100.0, 3)
    return {
        "bid": bid, "ask": ask, "bid_size": _f(flow.get("bid_size")), "ask_size": _f(flow.get("ask_size")),
        "mid": mid, "spread_pct": spread_pct, "last": price, "underlying_last": _f(flow.get("underlying_price")),
        "entry_ref": ask,
    }


def _build_row(flow, params, signal_ts, run_id, sha, executed, skip_reason, sample_tier, features):
    ticker = str(flow.get("ticker") or "").upper()
    right = "call" if str(flow.get("type") or "").lower().startswith("c") else "put"
    occ = _occ_symbol(ticker, flow.get("expiry"), flow.get("strike"), right)
    q = _quote_from_flow(flow)
    pollable = q["entry_ref"] is not None and q["entry_ref"] > 0 and occ is not None
    if not pollable:
        poll_tier = "none"
    elif executed or sample_tier == "topn":
        poll_tier = "standard"
    elif sample_tier == "random":
        poll_tier = "standard"
    else:
        poll_tier = "reduced"
    return {
        "candidate_id": uuid.uuid4().hex,
        "run_id": run_id, "code_version": sha, "feature_set_version": FEATURE_SET_VERSION,
        "signal_ts_utc": signal_ts,
        "ticker": ticker, "occ_symbol": occ, "expiry": flow.get("expiry"),
        "strike": _f(flow.get("strike")), "right": right, "side": "long",
        "bid": q["bid"], "ask": q["ask"], "bid_size": q["bid_size"], "ask_size": q["ask_size"],
        "mid": q["mid"], "spread_pct": q["spread_pct"], "last": q["last"], "underlying_last": q["underlying_last"],
        "entry_ref": q["entry_ref"],
        "features": features, "rule_score": _f(flow.get("total_premium")),
        "executed": 1 if executed else 0, "skip_reason": skip_reason,
        "vertical_barrier_ts": _vertical_barrier_ts(signal_ts, flow.get("expiry")),
        "barrier_up_pct": params.get("scanner_barrier_up", 0.30),
        "barrier_down_pct": params.get("scanner_barrier_down", -0.50),
        "poll_tier": poll_tier, "sample_tier": sample_tier,
    }


def _flow_rows(params):
    try:
        from src.unusual_whales_api import UnusualWhalesClient
        uw = UnusualWhalesClient()
        if not getattr(uw, "enabled", False):
            return []
        limit = params.get("scanner_flow_limit", 600)
        min_prem = params.get("scanner_min_premium", 50000)
        return (uw.flow_alerts(ticker=None, limit=limit, min_premium=min_prem) or {}).get("data") or []
    except Exception:
        return []


def _payload_for(ticker, state, mock):
    key = ticker.upper()
    if key in state["tickers"]:
        return state["tickers"][key], False
    try:
        import sandbox_proactive_lab as lab
        md = lab.collect_metadata(ticker, mock=mock)
    except Exception:
        md = None
    state["tickers"][key] = md
    return md, True


def harvest_scan(params, executed_record=None, mock=False):
    signal_ts = _now_ms()
    run_id = _run_id()
    sha = _git_sha()
    state = _load_state()
    topn = params.get("harvest_topn", 20)
    n_random = params.get("harvest_random", 5)
    cap = params.get("harvest_daily_cap", 300)
    prem_lo = params.get("scanner_premium_min", 0.30)
    prem_hi = params.get("scanner_premium_max", 4.00)

    written = {"executed": 0, "topn": 0, "random": 0, "quota_cap": 0, "prefilter": 0, "skipped_dup": 0}

    executed_occ = set()
    if executed_record:
        md = executed_record.get("metadata")
        cand = executed_record.get("_scan_candidate") or {}
        rule_score = _f(cand.get("total_premium"))
        spot = (md or {}).get("macro", {}).get("spot")
        for name, leg in (executed_record.get("legs") or {}).items():
            occ = leg.get("occ_symbol")
            if not occ:
                continue
            flow = {"ticker": executed_record.get("ticker"), "type": "call" if "call" in name else "put",
                    "strike": leg.get("strike"), "expiry": leg.get("expiry"),
                    "price": leg.get("limit_price"), "bid": leg.get("entry_premium"), "ask": leg.get("limit_price"),
                    "underlying_price": spot, "total_premium": rule_score}
            row = _build_row(flow, params, signal_ts, run_id, sha, True, None, "executed", md)
            row["occ_symbol"] = occ
            _write_row(row)
            executed_occ.add(occ)
            state["contracts"].append(occ)
            written["executed"] += 1

    rows = _flow_rows(params)
    scored = []
    for flow in rows:
        ticker = str(flow.get("ticker") or "").upper()
        if not ticker or ticker in INDEX_ROOTS:
            continue
        occ = _occ_symbol(ticker, flow.get("expiry"), flow.get("strike"),
                          "call" if str(flow.get("type") or "").lower().startswith("c") else "put")
        if occ is None or occ in executed_occ:
            continue
        if occ in state["contracts"]:
            written["skipped_dup"] += 1
            continue
        pc = _f(flow.get("price"))
        in_band = pc is not None and prem_lo <= pc <= prem_hi
        scored.append((flow, occ, in_band))

    in_band_rows = [x for x in scored if x[2]]
    in_band_rows.sort(key=lambda x: _f(x[0].get("total_premium")) or 0.0, reverse=True)
    top_slice = in_band_rows[:topn]
    below = in_band_rows[topn:]
    rand_slice = random.sample(below, min(n_random, len(below))) if below else []

    done = set()
    for flow, occ, _ in top_slice:
        if occ in done:
            continue
        if state["payload_count"] >= cap:
            break
        md, computed = _payload_for(flow.get("ticker"), state, mock)
        if computed:
            state["payload_count"] += 1
        _write_row(_build_row(flow, params, signal_ts, run_id, sha, False, "score_below_threshold", "topn", md))
        done.add(occ)
        state["topn_count"] += 1
        written["topn"] += 1

    for flow, occ, _ in rand_slice:
        if occ in done or state["payload_count"] >= cap:
            continue
        md, computed = _payload_for(flow.get("ticker"), state, mock)
        if computed:
            state["payload_count"] += 1
        _write_row(_build_row(flow, params, signal_ts, run_id, sha, False, "score_below_threshold", "random", md))
        done.add(occ)
        state["random_count"] += 1
        written["random"] += 1

    for flow, occ, in_band in scored:
        if occ in done:
            continue
        skip = "quota_cap" if in_band else "prefilter"
        _write_row(_build_row(flow, params, signal_ts, run_id, sha, False, skip, "none", None))
        done.add(occ)
        written["quota_cap" if in_band else "prefilter"] += 1

    state["contracts"].extend(done)
    _save_state(state)
    return written

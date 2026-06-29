"""V11 Full MOT - offline system-wide matrix test (rigorous edition). Standalone, no live APIs,
no live-code mutation. Every check exercises the REAL function: schema checks feed synthetic
inputs and assert exact computed values; autopsy checks assert winner/loser discrimination,
loser tuning-rule firing, and the full manage_open_positions close+autopsy chain. Run:
  python v11_mot_harness.py
"""

import os
import sys
import tempfile
from types import SimpleNamespace as SN
from datetime import datetime, timezone, timedelta, date

os.environ.setdefault("ALPACA_API_KEY", "MOT_DUMMY")
os.environ.setdefault("ALPACA_SECRET_KEY", "MOT_DUMMY")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sandbox_proactive_lab as lab
import sandbox_v11_sensors as v11
from v10_params import load as load_params

_tmp = tempfile.gettempdir()
lab.LOG_PATH = os.path.join(_tmp, "mot_log.json")
lab.AUTOPSY_MD = os.path.join(_tmp, "mot_autopsy.md")
lab.ADVISORY_MD = os.path.join(_tmp, "mot_advisory.md")
lab.COOLOFF_PATH = os.path.join(_tmp, "mot_cooloff.json")


def _wipe():
    for f in (lab.LOG_PATH, lab.AUTOPSY_MD, lab.ADVISORY_MD, lab.COOLOFF_PATH):
        if os.path.exists(f):
            os.remove(f)


_wipe()
RESULTS = []


def check(dim, label, passed, detail=""):
    RESULTS.append((dim, label, bool(passed), detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))


def approx(a, b, tol=0.01):
    return a is not None and abs(a - b) <= tol


EXPECTED = {
    "macro": ["spot", "sma20", "distance_to_sma20_pct", "source"],
    "iv_term": ["iv_front", "iv_back", "iv_ratio", "structure", "source"],
    "gex": ["net_gex", "zero_gamma_strike", "distance_to_zero_gamma_pct", "regime", "source"],
    "alt_catalyst": ["reddit_mention_delta_pct", "insider_10d_buy_usd", "insider_cluster_flag", "source"],
    "technical": ["atr", "atr_pct", "rvol_10min", "source"],
    "fundamentals": ["sector", "industry", "market_cap", "short_pct_float", "short_ratio", "source"],
    "news": ["headline_count", "latest_age_hours", "vader_compound", "news_type", "top_headline", "source"],
    "regime_stack": ["ticker_dist_pct", "market_spy_dist_pct", "sector_etf", "sector_dist_pct",
                     "sector_vs_market_spread", "source"],
    "skew": ["put_iv_25d", "call_iv_25d", "skew_ratio", "skew_bias", "delta_source", "source"],
    "flow_aggression": ["sweep_aggression_pct", "ask_sweep_prem", "total_flow_prem", "source"],
    "dark_pool": ["distance_to_heaviest_dp_node_pct", "heaviest_node_price", "node_size", "n_prints",
                  "window_start", "window_end", "source"],
    "pemd": ["days_since_earnings", "post_earnings_iv_crush_flag", "iv_rank_1y", "last_earnings_date", "source"],
    "vrp": ["realized_vol_20d", "front_iv", "vrp", "vrp_regime", "source"],
    "flow_persistence": ["net_directional_prem", "flow_persistence_pct", "flow_direction", "closing_accel", "n_ticks", "source"],
    "price_action": ["nvi", "vwma_20", "rsi_5", "rsi_15", "gap_pct", "day_range", "candle_body", "dist_sma50", "source"],
    "macro_context": ["iv_term_skew", "vix_level", "execution_hour", "day_of_week", "sector_vs_spy", "source"],
}
TOP = ["entry_ts_utc", "news_sentiment_score", "sweep_aggression_pct", "distance_to_zero_gamma_pct",
       "distance_to_heaviest_dp_node_pct", "days_since_earnings", "post_earnings_iv_crush_flag", "flow_persistence_pct"]


def missing_tags(md):
    miss = [k for k in TOP if k not in md]
    for b, keys in EXPECTED.items():
        if b not in md or not isinstance(md[b], dict):
            miss.append(b + ".*")
            continue
        miss += [f"{b}.{k}" for k in keys if k not in md[b]]
    return miss


# =====================================================================
print("\n=== DIMENSION 1: INPUT & SCHEMA INTEGRITY (real compute + degradation) ===")

# 1.1 macro_technical REAL math: closes 100..120 -> spot 120, sma20 110.5, dist 8.597, atr 2, atr% 1.67, rvol 1.0
bars = [{"h": (100 + i) + 1, "l": (100 + i) - 1, "c": 100 + i, "v": 1000} for i in range(21)]
_od = lab._alpaca_daily
lab._alpaca_daily = lambda t, days=60: bars
mt = lab.macro_technical("X", mock=False)
lab._alpaca_daily = _od
check(1, "macro_technical computes spot/SMA20/ATR/RVOL from bars",
      mt["spot"] == 120.0 and mt["sma20"] == 110.5 and approx(mt["distance_to_sma20_pct"], 8.597)
      and mt["atr"] == 2.0 and approx(mt["atr_pct"], 1.67) and mt["rvol_10min"] == 1.0 and mt["source"] == "alpaca",
      f"spot={mt['spot']} sma={mt['sma20']} dist={mt['distance_to_sma20_pct']} atr={mt['atr']} atr%={mt['atr_pct']} rvol={mt['rvol_10min']}")

# 1.2 net_gex REAL zero-gamma crossing: cum -100,-200,-50,+50,+100 -> crossing 105, net +100, positive_gamma
rows = {"data": [{"strike": k, "call_gex": g, "put_gex": 0} for k, g in
                 [(90, -100), (95, -100), (100, 150), (105, 100), (110, 50)]]}
import src.unusual_whales_api as _uwmod
_ouw = _uwmod.UnusualWhalesClient
_uwmod.UnusualWhalesClient = type("FUW", (), {"__init__": lambda s: None,
                                              "greek_exposure_by_strike": lambda s, t: rows})
gx = lab.net_gex("X", 103.0, mock=False)
_uwmod.UnusualWhalesClient = _ouw
check(1, "net_gex finds zero-gamma crossing + net + regime",
      gx["zero_gamma_strike"] == 105.0 and gx["net_gex"] == 100.0 and gx["regime"] == "positive_gamma"
      and gx["source"] == "uw" and approx(gx["distance_to_zero_gamma_pct"], -1.942),
      f"zg={gx['zero_gamma_strike']} net={gx['net_gex']} regime={gx['regime']} dist={gx['distance_to_zero_gamma_pct']}")

# 1.3 iv_term_structure REAL ratio: front 80 / back 60 -> 1.333 backwardation
_oiv = lab._alpaca_atm_iv
lab._alpaca_atm_iv = lambda t, s, dmin, dmax, creds: 80.0 if dmin == lab.CAL_FRONT_DTE[0] else 60.0
iv = lab.iv_term_structure("X", 100.0, mock=False, creds=("k", "s"))
lab._alpaca_atm_iv = _oiv
check(1, "iv_term_structure computes ratio + structure",
      iv["iv_front"] == 80.0 and iv["iv_back"] == 60.0 and approx(iv["iv_ratio"], 1.333)
      and iv["structure"] == "backwardation" and iv["source"] == "alpaca",
      f"front={iv['iv_front']} back={iv['iv_back']} ratio={iv['iv_ratio']} {iv['structure']}")

# 1.4 company_profile REAL: shortPercentOfFloat 0.0427 -> 4.27 (x100 scaling)
v11._PROFILE_CACHE.clear()
_oyf = sys.modules.get("yfinance")
sys.modules["yfinance"] = SN(Ticker=lambda b: SN(info={"sector": "Technology", "industry": "Semis",
                              "marketCap": 1000000, "shortPercentOfFloat": 0.0427, "shortRatio": 1.5}))
prof = v11.company_profile("X", mock=False)
if _oyf is not None:
    sys.modules["yfinance"] = _oyf
else:
    sys.modules.pop("yfinance", None)
v11._PROFILE_CACHE.clear()
check(1, "company_profile parses sector/mcap + scales short% (0.0427->4.27)",
      prof["sector"] == "Technology" and prof["market_cap"] == 1000000 and prof["short_pct_float"] == 4.27
      and prof["short_ratio"] == 1.5 and prof["source"] == "yfinance", f"{prof}")

# 1.5 news_context REAL: VADER scores + classifies an earnings headline
import alpaca.data.historical.news as _annews
_onc = _annews.NewsClient
_art = SN(headline="ACME beats earnings, raises full-year guidance", summary="Strong quarter, revenue up",
          created_at=datetime.now(timezone.utc) - timedelta(hours=2))
_annews.NewsClient = type("FNC", (), {"__init__": lambda s, k, sec: None,
                                      "get_news": lambda s, req: SN(data=[_art])})
nc = v11.news_context("X", mock=False)
_annews.NewsClient = _onc
check(1, "news_context VADER score + catalyst-type classify (Earnings)",
      nc["headline_count"] == 1 and nc["news_type"] == "Earnings" and isinstance(nc["vader_compound"], float)
      and nc["source"] == "alpaca_news+vader" and nc["latest_age_hours"] is not None,
      f"count={nc['headline_count']} type={nc['news_type']} vader={nc['vader_compound']} age={nc['latest_age_hours']}")

# 1.6 relative_skew REAL: put 25d IV 30 vs call 25d IV 20 -> ratio 1.5 crash_hedging, delta_source greeks
_ofc = v11._front_chain
v11._front_chain = lambda t, side, dte_lo=21, dte_hi=45: (
    {"C1": SN(implied_volatility=0.20, greeks=SN(delta=0.25))} if side == "call"
    else {"P1": SN(implied_volatility=0.30, greeks=SN(delta=-0.25))})
sk = v11.relative_skew("X", 100.0, 25.0, mock=False)
v11._front_chain = _ofc
check(1, "relative_skew picks 25d IVs -> ratio + bias + delta_source",
      sk["put_iv_25d"] == 30.0 and sk["call_iv_25d"] == 20.0 and sk["skew_ratio"] == 1.5
      and sk["skew_bias"] == "crash_hedging" and sk["delta_source"] == "greeks" and sk["source"] == "alpaca_snapshots",
      f"{sk}")

# 1.7 full schema present (deep, every sub-key) on a real collect_metadata
md = lab.collect_metadata("AMD", mock=True)
mt2 = missing_tags(md)
check(1, "schema complete - every V11 tag present (deep, 0 missing)", not mt2, f"missing={mt2}" if mt2 else "all tags present")

# 1.8 broken CORE feed -> spot null -> enter_proactive_set SKIPS (no fabricated trade)
_ocm = lab.collect_metadata
lab.collect_metadata = lambda t, mock=False: {"entry_ts_utc": lab._now_iso_ms(),
    "macro": {"spot": None, "source": "unavailable"}, "iv_term": {"iv_front": None, "source": "unavailable"}}
recskip = lab.enter_proactive_set("ZZZZ", None, mock=False, dry_run=True)
lab.collect_metadata = _ocm
check(1, "null core (spot=None) -> SKIPPED, no fabricated trade", recskip.get("skipped") is True and recskip["status"] == "SKIPPED")

# 1.9 degradation: a sensor returning MISSING-keys {} and ZEROES must not crash; zero is a valid value
_onews = v11.news_context
v11.news_context = lambda t, m=False, limit=8: {}                       # missing-keys dict
try:
    md_mk = lab.collect_metadata("AMD", mock=True)
    mk_ok = (md_mk.get("news_sentiment_score") is None)               # .get on {} -> None, no crash
except Exception:
    mk_ok = False
v11.news_context = lambda t, m=False, limit=8: dict(headline_count=0, latest_age_hours=None, vader_compound=0.0,
                                                    news_type="Unknown", top_headline=None, source="alpaca_news")
md_zero = lab.collect_metadata("AMD", mock=True)
v11.news_context = _onews
check(1, "missing-key sensor dict does not crash collect_metadata", mk_ok)
check(1, "zero sentiment (0.0) preserved as a value, not dropped to null", md_zero.get("news_sentiment_score") == 0.0)

# 1.10 broken/raising sensors -> core trade STILL BUILDS (real OPEN record with legs)
_wipe()
def _raise(*a, **k):
    raise RuntimeError("broken feed")
_savedsensors = (v11.company_profile, v11.news_context, v11.regime_stack, v11.relative_skew)
v11.company_profile = v11.news_context = v11.regime_stack = v11.relative_skew = _raise
recbuilt = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
v11.company_profile, v11.news_context, v11.regime_stack, v11.relative_skew = _savedsensors
check(1, "broken sensors -> core trade STILL builds (OPEN + >=1 leg)",
      recbuilt.get("status") == "OPEN" and len(recbuilt.get("legs", {})) >= 1, f"legs={list(recbuilt.get('legs', {}).keys())}")

# =====================================================================
print("\n=== DIMENSION 1B: NEW EDGE SENSORS (real compute, fail-open, schema) ===")
_ouw = v11._uw
# Edge 1 - sweep aggression = ask-side SWEEP premium / total premium
v11._uw = lambda: SN(flow_alerts=lambda ticker, limit=100: {"data": [
    {"total_premium": 100000, "total_ask_side_prem": 80000, "has_sweep": True},
    {"total_premium": 100000, "total_ask_side_prem": 50000, "has_sweep": False}]})
fa = v11.flow_aggression("X", mock=False)
v11._uw = _ouw
check(1, "flow_aggression: ask-sweep(80k)/total(200k) = 40%", approx(fa["sweep_aggression_pct"], 40.0), f"{fa}")

# Edge 3 - dark-pool heaviest 0.25%-bin node vs spot
v11._uw = lambda: SN(darkpool_ticker=lambda t, limit=200: {"data": [
    {"price": 99.5, "size": 1000, "executed_at": "2026-06-26T20:00:00Z"},
    {"price": 99.6, "size": 800, "executed_at": "2026-06-26T20:01:00Z"},
    {"price": 99.55, "size": 500, "executed_at": "2026-06-26T20:02:00Z"},
    {"price": 101.0, "size": 200, "executed_at": "2026-06-26T20:03:00Z"}]})
dpn = v11.darkpool_node("X", 100.0, mock=False)
v11._uw = _ouw
check(1, "darkpool_node: heaviest node 99.5, distance 0.5%",
      dpn["heaviest_node_price"] == 99.5 and approx(dpn["distance_to_heaviest_dp_node_pct"], 0.5) and dpn["n_prints"] == 4, f"{dpn}")

# Edge 4 - PEMD: earnings 3d ago + iv_rank 20 (<30) -> crush flag True
import pandas as pd
_today = date.today()
_oyf = sys.modules.get("yfinance")
_idx = pd.DatetimeIndex([pd.Timestamp(_today - timedelta(days=3)), pd.Timestamp(_today + timedelta(days=30))])
sys.modules["yfinance"] = SN(Ticker=lambda b: SN(get_earnings_dates=lambda limit=12: SN(index=_idx)))
v11._uw = lambda: SN(iv_rank=lambda b: {"data": [{"iv_rank_1y": "20.0"}]})
pe = v11.post_earnings_drift("X", mock=False)
v11._uw = _ouw
if _oyf is not None:
    sys.modules["yfinance"] = _oyf
else:
    sys.modules.pop("yfinance", None)
check(1, "PEMD: days_since=3, iv_rank=20, crush_flag=True",
      pe["days_since_earnings"] == 3 and pe["post_earnings_iv_crush_flag"] is True and pe["iv_rank_1y"] == 20.0, f"{pe}")

# Edge 5 - VRP = front IV - 20d annualised realized vol (independent reference)
import math as _m
_cl = [100, 101, 102, 101, 103, 102, 104, 103, 105, 104, 106, 105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
_r = [_m.log(_cl[i] / _cl[i - 1]) for i in range(len(_cl) - 20, len(_cl))]
_mn = sum(_r) / len(_r)
_rv = round(_m.sqrt(sum((x - _mn) ** 2 for x in _r) / (len(_r) - 1)) * _m.sqrt(252) * 100, 2)
_odc = v11._daily_closes
v11._daily_closes = lambda t, days=40: _cl
vr = v11.vrp_sensor("X", 80.0, mock=False)
v11._daily_closes = _odc
check(1, "vrp = front_iv(80) - realized_vol_20d (independent ref)",
      approx(vr["realized_vol_20d"], _rv) and approx(vr["vrp"], 80.0 - _rv) and vr["vrp_regime"] in ("rich", "cheap"),
      f"rv={vr['realized_vol_20d']} vrp={vr['vrp']} ref_rv={_rv}")

# Edge 6 - flow persistence: dirs=[100k,100k,-50k,200k] -> net 350k, |net|/sum|.|=77.78%, bullish
v11._uw = lambda: SN(net_prem_ticks=lambda t: {"data": [
    {"net_call_premium": 100000, "net_put_premium": 0}, {"net_call_premium": 100000, "net_put_premium": 0},
    {"net_call_premium": 0, "net_put_premium": 50000}, {"net_call_premium": 200000, "net_put_premium": 0}]})
fp = v11.flow_persistence("X", mock=False)
v11._uw = _ouw
check(1, "flow_persistence: net 350k, one-sidedness 77.78%, bullish",
      fp["net_directional_prem"] == 350000 and approx(fp["flow_persistence_pct"], 77.78) and fp["flow_direction"] == "bullish",
      f"persist={fp['flow_persistence_pct']} net={fp['net_directional_prem']} dir={fp['flow_direction']} accel={fp['closing_accel']}")

# Sensor 7 - price action: real compute vs independent inline reference
import math as _m7
_seq, _val = [], 100.0
for _i in range(51):
    _val += 1.5 if _i % 3 else -1.0           # mostly up, every 3rd down -> RSI != 100
    _seq.append(round(_val, 2))
_pab = [{"o": round(c - 0.3, 2), "h": round(c + 0.8, 2), "l": round(c - 0.8, 2), "c": c,
         "v": 1200 if i % 2 else 900} for i, c in enumerate(_seq)]
def _ref_rsi(cl, p):
    ds = [cl[k] - cl[k - 1] for k in range(len(cl) - p, len(cl))]
    ag = sum(d for d in ds if d > 0) / p; al = sum(-d for d in ds if d < 0) / p
    return 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 2)
_nvi = 1000.0
for _i in range(1, len(_pab)):
    if _pab[_i]["v"] < _pab[_i - 1]["v"] and _seq[_i - 1] > 0:
        _nvi *= (1 + (_seq[_i] - _seq[_i - 1]) / _seq[_i - 1])
_vw = sum(_seq[k] * _pab[k]["v"] for k in range(len(_seq) - 20, len(_seq))) / sum(b["v"] for b in _pab[-20:])
_sma50 = sum(_seq[-50:]) / 50.0
_lb = _pab[-1]; _rng = _lb["h"] - _lb["l"]
pa = v11.price_action("X", mock=False, bars=_pab)
check(1, "price_action: rsi_5/rsi_15 match independent reference",
      pa["rsi_5"] == _ref_rsi(_seq, 5) and pa["rsi_15"] == _ref_rsi(_seq, 15), f"rsi5={pa['rsi_5']} rsi15={pa['rsi_15']}")
check(1, "price_action: vwma_20 + nvi + dist_sma50 match reference",
      approx(pa["vwma_20"], round(_vw, 2)) and approx(pa["nvi"], round(_nvi, 2))
      and approx(pa["dist_sma50"], round((_seq[-1] - _sma50) / _sma50 * 100, 3)),
      f"vwma={pa['vwma_20']} nvi={pa['nvi']} dist50={pa['dist_sma50']}")
check(1, "price_action: gap/day_range/candle_body exact",
      approx(pa["gap_pct"], round((_lb["o"] - _seq[-2]) / _seq[-2] * 100, 3))
      and approx(pa["day_range"], round(_rng / _seq[-1] * 100, 3))
      and approx(pa["candle_body"], round(abs(_seq[-1] - _lb["o"]) / _rng, 3)),
      f"gap={pa['gap_pct']} range={pa['day_range']} body={pa['candle_body']}")

# Sensor 8 - macro context: iv_term_skew + vix + hour/dow + sector_vs_spy
import pandas as _pd8
_oyf2 = sys.modules.get("yfinance")
sys.modules["yfinance"] = SN(Ticker=lambda b: SN(history=lambda period="5d": _pd8.DataFrame({"Close": [18.0, 19.0, 20.5]})))
_odc2 = v11._daily_closes
v11._daily_closes = lambda t, days=40: ([100, 100, 100, 100, 100, 105] if t == "XLK"
                                        else [100, 100, 100, 100, 100, 102] if t == "SPY" else [])
mc = v11.macro_context("X", 80.0, 60.0, "Technology", mock=False, now=datetime(2026, 6, 29, 14, 30, tzinfo=timezone.utc))
v11._daily_closes = _odc2
if _oyf2 is not None:
    sys.modules["yfinance"] = _oyf2
else:
    sys.modules.pop("yfinance", None)
check(1, "macro_context: iv_term_skew 20, vix 20.5, hour 14, dow 0(Mon), sector_vs_spy 3.0",
      mc["iv_term_skew"] == 20.0 and mc["vix_level"] == 20.5 and mc["execution_hour"] == 14
      and mc["day_of_week"] == 0 and approx(mc["sector_vs_spy"], 3.0), f"{mc}")

# Sensor 8b - per-leg OI day-over-day from UW historic chains
v11._uw = lambda: SN(option_contract_historic=lambda occ: {"chains": [{"open_interest": "1500"}, {"open_interest": "1200"}]})
oc = v11.oi_change("AMD260724C00100000", mock=False)
v11._uw = _ouw
check(1, "oi_change: today 1500 - prev 1200 = +300", oc["oi_change"] == 300 and oc["oi_today"] == 1500 and oc["oi_prev"] == 1200, f"{oc}")

# Edge 2 (already computed) + schema + fail-open + autopsy-safety with the new keys
md_new = lab.collect_metadata("AMD", mock=True)
check(1, "schema complete WITH 4 new edge blocks + 5 flat keys (deep)", not missing_tags(md_new), f"missing={missing_tags(md_new)}")
check(1, "distance_to_zero_gamma_pct flat mirror == md['gex'] value",
      md_new.get("distance_to_zero_gamma_pct") == md_new["gex"]["distance_to_zero_gamma_pct"])
check(1, "new edge sensors fail-open full-keyed null (mock)",
      all(k in md_new["flow_aggression"] for k in EXPECTED["flow_aggression"])
      and all(k in md_new["dark_pool"] for k in EXPECTED["dark_pool"])
      and all(k in md_new["pemd"] for k in EXPECTED["pemd"])
      and all(k in md_new["vrp"] for k in EXPECTED["vrp"]))
recX = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
try:
    rX = lab.run_trade_autopsy(recX, {"bullish_call": -70.0}, exit_reason="t", underlying_move_pct=-6.0)
    _aok = isinstance(rX.get("determining_factor"), str) and bool(rX["determining_factor"])
except Exception:
    _aok = False
check(1, "autopsy parses payload WITH new edge keys (loser, no KeyError)", _aok)

# =====================================================================
print("\n=== DIMENSION 2: ROUTING INTEGRITY (intent -> one structure + structure field) ===")
def mk_md(dist, spy):
    m = lab.collect_metadata("AMD", mock=True)
    m["macro"]["distance_to_sma20_pct"] = dist
    m["regime_stack"]["market_spy_dist_pct"] = spy
    return m
cases = [
    ("BULLISH", {"flow_type": "call"}, mk_md(5.0, 1.0), "bullish_call", "LONG_CALL"),
    ("BEARISH", {"flow_type": "put"}, mk_md(-5.0, -1.0), "bearish_put", "LONG_PUT"),
    ("NEUTRAL", {}, mk_md(0.0, None), "flat_calendar", "CALENDAR_SPREAD"),
]
for want_reg, cand, m, want_leg, want_struct in cases:
    got = lab.classify_regime(m, cand)
    legs = lab.build_legs("AMD", m, got)
    check(2, f"classify_regime -> {want_reg}", got == want_reg, f"got {got}")
    check(2, f"{want_reg}: ONLY {want_leg} (1 leg) with structure {want_struct}",
          list(legs.keys()) == [want_leg] and legs[want_leg]["structure"] == want_struct,
          f"legs={list(legs.keys())} struct={legs.get(want_leg, {}).get('structure')}")

# =====================================================================
print("\n=== DIMENSION 3: EXIT & AUTOPSY INTEGRITY (survivorship) ===")
p = load_params()
ts = lab._now_iso_ms()
def at(h):
    return datetime.now(timezone.utc) + timedelta(hours=h)
dec = [
    ("+35% @ <24h -> HOLD", lab.manage_exit(ts, 35.0, p, now=at(2)), "HOLD"),
    ("+35% @ >24h -> CLOSE_TAKE_PROFIT", lab.manage_exit(ts, 35.0, p, now=at(26)), "CLOSE_TAKE_PROFIT"),
    ("-55% @ <24h -> CLOSE_STOP_LOSS", lab.manage_exit(ts, -55.0, p, now=at(2)), "CLOSE_STOP_LOSS"),
    ("2 DTE -> CLOSE_EXPIRY", lab.manage_exit(ts, -10.0, p, now=at(2), expiry_iso=(date.today() + timedelta(days=2)).isoformat()), "CLOSE_EXPIRY"),
]
for label, d, want in dec:
    check(3, label, d["action"] == want, d["action"])

# 3.5 FULL production chain: manage_open_positions closes a LOSER (stop) + autopsies it
_wipe()
_ocp = lab._close_position
lab._close_position = lambda occ, creds: True
recL = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
occL = recL["legs"]["bullish_call"]["occ_symbol"]
posL = [{"symbol": occL, "avg_entry_price": "10.0", "current_price": "4.0", "unrealized_plpc": "-0.6", "qty": "1"}]
closed, autops = lab.manage_open_positions(("k", "s"), p, positions=posL)
log_after = lab._load_log_list()
recL_now = next((r for r in log_after if r["trade_set_id"] == recL["trade_set_id"]), {})
lab._close_position = _ocp
check(3, "manage_open_positions: LOSER closed via stop (full chain)",
      len(closed) == 1 and closed[0]["action"] == "CLOSE_STOP_LOSS" and approx(closed[0]["return_pct"], -60.0, 0.5),
      f"closed={closed}")
check(3, "manage_open_positions: LOSER autopsied (not skipped, no autopsy_error)",
      len(autops) == 1 and "autopsy_error" not in autops[0] and autops[0].get("factor"),
      f"autopsies={autops}")
check(3, "LOSER log record marked CLOSED with negative return recorded",
      recL_now.get("status") == "CLOSED" and approx((recL_now.get("exit") or {}).get("leg_returns_pct", {}).get("bullish_call"), -60.0, 0.5),
      f"status={recL_now.get('status')} exit={recL_now.get('exit', {}).get('leg_returns_pct')}")

# 3.6 FULL chain: manage_open_positions closes a WINNER (take-profit past 24h)
_wipe()
lab._close_position = lambda occ, creds: True
recW = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
_lg = lab._load_log_list()
_lg[-1]["entry_ts_utc"] = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
lab._save_log_list(_lg)
occW = recW["legs"]["bullish_call"]["occ_symbol"]
posW = [{"symbol": occW, "avg_entry_price": "10.0", "current_price": "14.0", "unrealized_plpc": "0.4", "qty": "1"}]
closedW, autopsW = lab.manage_open_positions(("k", "s"), p, positions=posW)
lab._close_position = _ocp
check(3, "manage_open_positions: WINNER closed via take-profit (full chain)",
      len(closedW) == 1 and closedW[0]["action"] == "CLOSE_TAKE_PROFIT" and approx(closedW[0]["return_pct"], 40.0, 0.5),
      f"closed={closedW}")

# 3.7 winner/loser DISCRIMINATION (multi-leg): winner=highest, loser=lowest
md3 = lab.collect_metadata("AMD", mock=True)
rec3 = {"ticker": "TST", "trade_set_id": "mot3", "entry_ts_utc": ts, "trigger": "t", "metadata": md3,
        "legs": {"bullish_call": {"structure": "LONG_CALL"}, "bearish_put": {"structure": "LONG_PUT"},
                 "flat_calendar": {"structure": "CALENDAR_SPREAD"}}, "status": "OPEN"}
res3 = lab.run_trade_autopsy(rec3, {"bullish_call": 50.0, "bearish_put": -30.0, "flat_calendar": -10.0},
                            exit_reason="test", underlying_move_pct=2.0)
check(3, "autopsy discriminates winner(+50)=bullish_call, loser(-30)=bearish_put",
      res3["winner"] == "bullish_call" and res3["loser"] == "bearish_put", f"winner={res3['winner']} loser={res3['loser']}")

# 3.8 loser TUNING RULES fire on the losing legs (content, not just 'ran')
mdL = lab.collect_metadata("AMD", mock=True)
mdL["macro"]["spot"] = 100.0
mdL["gex"]["zero_gamma_strike"] = 110.0
mdL["iv_term"]["iv_ratio"] = 1.3
recT = {"ticker": "TST2", "trade_set_id": "motL", "entry_ts_utc": ts, "trigger": "t", "metadata": mdL,
        "legs": {"bullish_call": {"structure": "LONG_CALL"}, "flat_calendar": {"structure": "CALENDAR_SPREAD"}},
        "status": "OPEN"}
resT = lab.run_trade_autopsy(recT, {"bullish_call": -55.0, "flat_calendar": -20.0},
                            exit_reason="test", underlying_move_pct=-7.0, entry_slippage_pct=4.0)
gates = {g for g, _ in resT["recommendations"]}
check(3, "loser fires min_gex_distance + max_iv_ratio_for_calendar + max_bid_ask_spread_pct",
      {"min_gex_distance", "max_iv_ratio_for_calendar", "max_bid_ask_spread_pct"} <= gates, f"gates={gates}")

# 3.9 determining factor is WIN/LOSS-AWARE (the fix): a losing call must NOT narrate success
mdF = lab.collect_metadata("AMD", mock=True)
recF = {"ticker": "T", "trade_set_id": "motF", "entry_ts_utc": ts, "trigger": "t", "metadata": mdF,
        "legs": {"bullish_call": {"structure": "LONG_CALL"}}, "status": "OPEN"}
fac_loss = lab.run_trade_autopsy(recF, {"bullish_call": -55.0}, exit_reason="t", underlying_move_pct=-7.0)["determining_factor"]
recF["status"] = "OPEN"
fac_win = lab.run_trade_autopsy(recF, {"bullish_call": 120.0}, exit_reason="t", underlying_move_pct=7.0)["determining_factor"]
check(3, "LOSER factor says FAILED, not 'predicted the bullish expansion'",
      "FAILED" in fac_loss and "predicted the bullish expansion" not in fac_loss, f"'{fac_loss[:70]}'")
check(3, "WINNER factor is a success narrative (no FAILED)", "FAILED" not in fac_win, f"'{fac_win[:70]}'")

# 3.10 null-gex LOSER still autopsies (no KeyError)
mdN = lab.collect_metadata("AMD", mock=True)
mdN["gex"] = {"net_gex": None, "zero_gamma_strike": None, "distance_to_zero_gamma_pct": None, "regime": None, "source": "unavailable"}
recN = {"ticker": "T", "trade_set_id": "motN", "entry_ts_utc": ts, "trigger": "t", "metadata": mdN,
        "legs": {"bullish_call": {"structure": "LONG_CALL"}}, "status": "OPEN"}
try:
    resN = lab.run_trade_autopsy(recN, {"bullish_call": -80.0}, exit_reason="t", underlying_move_pct=-7.0)
    nok = isinstance(resN.get("determining_factor"), str) and bool(resN["determining_factor"])
except Exception as e:
    nok = False
    resN = {"determining_factor": f"CRASH: {e}"}
check(3, "null-gex LOSER autopsies cleanly (no KeyError)", nok, str(resN.get("determining_factor"))[:60])

# MFE/MAE trade-path: accumulates across cycles, then captured by the autopsy
_wipe()
_ocp3 = lab._close_position
lab._close_position = lambda occ, creds: True
recP = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
occP = recP["legs"]["bullish_call"]["occ_symbol"]
def _cycle(plpc, px):
    lab.manage_open_positions(("k", "s"), load_params(),
                              positions=[{"symbol": occP, "avg_entry_price": "10", "current_price": px, "unrealized_plpc": plpc, "qty": "1"}])
_cycle("0.2", "12")      # +20% favorable (HOLD, <24h)
_cycle("-0.15", "8.5")   # -15% adverse (HOLD)
lp = ((next(r for r in lab._load_log_list() if r["trade_set_id"] == recP["trade_set_id"]).get("leg_path") or {})).get("bullish_call") or {}
check(3, "MFE/MAE path accumulates across cycles (mfe 20, mae -15)",
      approx(lp.get("mfe_pct"), 20.0, 0.5) and approx(lp.get("mae_pct"), -15.0, 0.5), f"path={lp}")
_cycle("-0.6", "4")      # -60% -> stop closes -> autopsy captures the path
exP = next(r for r in lab._load_log_list() if r["trade_set_id"] == recP["trade_set_id"]).get("exit") or {}
lab._close_position = _ocp3
check(3, "autopsy exit records MFE/MAE (mfe 20, mae -60)",
      approx(exP.get("mfe_pct"), 20.0, 0.5) and approx(exP.get("mae_pct"), -60.0, 0.5), f"mfe={exP.get('mfe_pct')} mae={exP.get('mae_pct')}")

# =====================================================================
print("\n=== DIMENSION 4: SIZING FLOOR (per-leg bid/ask spread stamped) ===")
import alpaca.data.historical.option as _aopt
_oopt = _aopt.OptionHistoricalDataClient
_aopt.OptionHistoricalDataClient = type("FOC", (), {"__init__": lambda s, k, sec: None,
    "get_option_latest_quote": lambda s, req: {getattr(req, "symbol_or_symbols", "X"): SN(bid_price=1.00, ask_price=1.10)}})
sp = v11.option_spread("AMD260724C00100000")            # mid 1.05 -> (0.10/1.05)*100 = 9.524%
check(4, "option_spread computes bid_ask_spread_pct from a real quote", approx(sp.get("bid_ask_spread_pct"), 9.524),
      f"bid={sp.get('bid')} ask={sp.get('ask')} mid={sp.get('mid')} spread%={sp.get('bid_ask_spread_pct')}")
# directional leg
mdq = lab.collect_metadata("AMD", mock=True)
legs_c = lab.build_legs("AMD", mdq, "BULLISH")
lab._stamp_spreads(legs_c)
ecc = legs_c["bullish_call"].get("execution_cost") or {}
check(4, "spread STAMPED on directional leg.execution_cost", ecc.get("source") == "alpaca_quote" and approx(ecc.get("bid_ask_spread_pct"), 9.524), f"{ecc}")
# calendar leg (stamped via back_occ - no occ_symbol)
legs_cal = lab.build_legs("AMD", mdq, "NEUTRAL")
lab._stamp_spreads(legs_cal)
eccal = legs_cal["flat_calendar"].get("execution_cost") or {}
check(4, "spread STAMPED on CALENDAR leg via back_occ", eccal.get("source") == "alpaca_quote" and approx(eccal.get("bid_ask_spread_pct"), 9.524), f"{eccal}")
_aopt.OptionHistoricalDataClient = _oopt        # restore (no latent contamination)

# =====================================================================
print("\n=== DIMENSION 5: OBSERVABILITY (Telegram alerts + EOD digest) ===")
_wipe()                                          # clear cool-off from the D3 close tests so AMD can re-enter
recB = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
bm = lab._buy_msg(recB)
check(5, "BUY message: ticker+regime+structure+VRP", "AMD" in bm and "BULLISH" in bm and "LONG_CALL" in bm and "VRP" in bm, bm.split(chr(10))[0])
sm = lab._sell_msg({"ticker": "MU", "leg": "bearish_put", "action": "CLOSE_STOP_LOSS", "return_pct": -55.0, "closed_ok": True})
check(5, "SELL message: ticker+leg+action+return", "MU" in sm and "CLOSE_STOP_LOSS" in sm and "-55.0%" in sm, sm)
am = lab._autopsy_msg({"ticker": "PLTR", "winner": "bullish_call", "factor": "Bullish breakout fed the squeeze"})
check(5, "AUTOPSY message: ticker+winner+factor", "PLTR" in am and "bullish_call" in am and "squeeze" in am, am.split(chr(10))[0])

_onote = lab._notify
cap = []
lab._notify = lambda text: (cap.append(text), True)[1]
lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=False)   # live -> BUY fires
buy_fired = any(t.startswith("<b>BUY") for t in cap)
_wipe()
_ocp2 = lab._close_position
lab._close_position = lambda occ, creds: True
recS = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
occS = recS["legs"]["bullish_call"]["occ_symbol"]
cap.clear()
lab.manage_open_positions(("k", "s"), load_params(),
                          positions=[{"symbol": occS, "avg_entry_price": "10", "current_price": "4", "unrealized_plpc": "-0.6", "qty": "1"}])
lab._close_position = _ocp2
sell_fired = any(t.startswith("<b>SELL") for t in cap)
autopsy_fired = any(t.startswith("<b>AUTOPSY") for t in cap)
dg = lab.daily_digest()
lab._notify = _onote
check(5, "BUY alert fires on live entry", buy_fired)
check(5, "SELL + AUTOPSY alerts fire through the close chain", sell_fired and autopsy_fired, f"sell={sell_fired} autopsy={autopsy_fired}")
check(5, "daily_digest builds a summary block", isinstance(dg, str) and "SANDBOX DIGEST" in dg)

# =====================================================================
_wipe()
print("\n" + "=" * 70)
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r[2])
by_dim = {}
for dim, _, ok, _d in RESULTS:
    s = by_dim.setdefault(dim, [0, 0]); s[1] += 1; s[0] += int(ok)
names = {1: "Input & Schema", 2: "Routing", 3: "Exit & Autopsy", 4: "Sizing Floor", 5: "Observability"}
print("V11 FULL MOT (rigorous) - RESULT BY DIMENSION")
for d in sorted(by_dim):
    pa, to = by_dim[d]
    print(f"  Dimension {d} ({names[d]:<16}): {pa}/{to} {'PASS' if pa == to else 'FAIL'}")
print("-" * 70)
print(f"  TOTAL: {passed}/{total} checks passed")
print("=" * 70)
if passed == total:
    print("MOT CERTIFICATE: ALL CHECKS PASS - V11 CLEARED")
    sys.exit(0)
print("MOT FAILED - fix underlying code (see [FAIL] lines)")
sys.exit(1)

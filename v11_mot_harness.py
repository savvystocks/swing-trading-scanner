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
os.environ["FADE_BOOK_FORCE_OFF"] = "1"   # legacy chain checks assert the OFF-state (V10) semantics;
                                          # fade-state behavior is asserted in the dedicated section below
os.environ.setdefault("ALPACA_SECRET_KEY", "MOT_DUMMY")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sandbox_proactive_lab as lab
import sandbox_v11_sensors as v11
from v10_params import load as load_params

_tmp = tempfile.gettempdir()
# 2026-07-29: redirect the fill ledger too - without this, MOT backstop tests leak synthetic
# exit_fill_backstop events into the REAL data/harvest_inbox (caught 07-28 as untracked files;
# never committed, but one `git add -A` away from polluting the pile).
import fill_ledger as _fl
_fl.INBOX_DIR = os.path.join(_tmp, "mot_inbox")
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
    "liquidity_and_slippage": ["equity_spread_pct_of_ask", "bid", "ask", "bid_size", "ask_size", "obi", "source"],
    "relative_momentum": ["rvol_20d", "gap_pct", "source"],
    "float_mechanics": ["short_pct_float", "float_shares", "shares_short", "source"],
    "dealer_greeks": ["net_dex", "net_vanna", "net_charm", "delta_imbalance", "source"],
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

# Mid-cap block 1 - liquidity & slippage: equity top-of-book spread % of ask + depth
import alpaca.data.historical as _ahist
_oqc = _ahist.StockHistoricalDataClient
_ahist.StockHistoricalDataClient = type("FQ", (), {"__init__": lambda s, k, sec: None,
    "get_stock_latest_quote": lambda s, req: {getattr(req, "symbol_or_symbols", "X"): SN(bid_price=10.00, ask_price=10.10, bid_size=500, ask_size=300)}})
ls = v11.liquidity_slippage("X", mock=False)
_ahist.StockHistoricalDataClient = _oqc
check(1, "liquidity_slippage: spread%/ask + depth + OBI (bid 500/ask 300 -> obi 0.25)",
      approx(ls["equity_spread_pct_of_ask"], 0.99) and ls["bid_size"] == 500 and ls["ask_size"] == 300 and approx(ls["obi"], 0.25), f"{ls}")

# Mid-cap block 2 - relative momentum: RVOL vs prior-20d + opening gap
_rmbars = [{"o": 100, "h": 101, "l": 99, "c": 100, "v": 1000} for _ in range(20)] + [{"o": 105, "h": 107, "l": 104, "c": 106, "v": 2000}]
rm = v11.relative_momentum("X", mock=False, bars=_rmbars)   # rvol = 2000 / avg(1000*20) = 2.0 ; gap = (105-100)/100 = 5.0%
check(1, "relative_momentum: rvol_20d 2.0, gap 5.0%", approx(rm["rvol_20d"], 2.0) and approx(rm["gap_pct"], 5.0), f"{rm}")

# Mid-cap block 3 - float mechanics: short% + total float
v11._PROFILE_CACHE.clear()
_oyf3 = sys.modules.get("yfinance")
sys.modules["yfinance"] = SN(Ticker=lambda b: SN(info={"shortPercentOfFloat": 0.085, "floatShares": 50000000, "sharesShort": 4250000}))
fm = v11.float_mechanics("X", mock=False)
if _oyf3 is not None:
    sys.modules["yfinance"] = _oyf3
else:
    sys.modules.pop("yfinance", None)
check(1, "float_mechanics: short% 8.5, float 50M", fm["short_pct_float"] == 8.5 and fm["float_shares"] == 50000000 and fm["shares_short"] == 4250000, f"{fm}")

# Dealer greeks - net DEX / vanna / charm from UW greek_exposure (newest row last)
v11._uw = lambda: SN(greek_exposure=lambda t: {"data": [
    {"call_delta": 1000000, "put_delta": -400000, "call_vanna": 50000, "put_vanna": -10000, "call_charm": -30000, "put_charm": 8000}]})
dg = v11.dealer_greeks("X", mock=False)
v11._uw = _ouw   # net_dex 600k, net_vanna 40k, net_charm -22k, delta_imb 1000000/400000=2.5
check(1, "dealer_greeks: net_dex/vanna/charm + delta_imbalance",
      dg["net_dex"] == 600000 and dg["net_vanna"] == 40000 and dg["net_charm"] == -22000 and approx(dg["delta_imbalance"], 2.5), f"{dg}")

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
    ("+35% @ >24h -> SCALE_OUT_50 (Strategy B tier 1)", lab.manage_exit(ts, 35.0, p, now=at(26)), "SCALE_OUT_50"),
    ("-55% @ <24h -> CLOSE_STOP_LOSS", lab.manage_exit(ts, -55.0, p, now=at(2)), "CLOSE_STOP_LOSS"),
    ("2 DTE -> CLOSE_EXPIRY", lab.manage_exit(ts, -10.0, p, now=at(2), expiry_iso=(date.today() + timedelta(days=2)).isoformat()), "CLOSE_EXPIRY"),
]
for label, d, want in dec:
    check(3, label, d["action"] == want, d["action"])

# 3.5 FULL production chain: manage_open_positions closes a LOSER (stop) + autopsies it
_wipe()
_ocp = lab._close_position
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: True
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
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: True
recW = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
_lg = lab._load_log_list()
_lg[-1]["entry_ts_utc"] = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
lab._save_log_list(_lg)
occW = recW["legs"]["bullish_call"]["occ_symbol"]
posW = [{"symbol": occW, "avg_entry_price": "10.0", "current_price": "14.0", "unrealized_plpc": "0.4", "qty": "1"}]
closedW, autopsW = lab.manage_open_positions(("k", "s"), p, positions=posW)
lab._close_position = _ocp
check(3, "manage_open_positions: WINNER scales out 50% at +40% (Strategy B tier 1)",
      len(closedW) == 1 and closedW[0]["action"] == "SCALE_OUT_50" and approx(closedW[0]["return_pct"], 40.0, 0.5),
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
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: True
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
print("\n=== DIMENSION 3B: STRATEGY B ($800 sizing gate + tiered exit state machine) ===")
pe = load_params()
# Sizing: cheap mock (spot 30, iv 40 -> ~$1.5 premium) affords >=2 contracts
legs_aff = lab.build_legs("AMD", lab.collect_metadata("AMD", mock=True), "BULLISH")
check(3, "$800 sizing: cheap name affords >=2 contracts", (legs_aff["bullish_call"].get("contracts") or 0) >= 2,
      f"contracts={legs_aff['bullish_call'].get('contracts')}")
# Expensive md (spot 300, iv 120) -> 0 contracts (unaffordable)
mde = lab.collect_metadata("AMD", mock=True)
mde["macro"]["spot"] = 300.0; mde["iv_term"]["iv_front"] = 120.0; mde["iv_term"]["iv_back"] = 100.0
legs_exp = lab.build_legs("AMD", mde, "BULLISH")
check(3, "$800 sizing: expensive name -> 0 contracts (skip)", (legs_exp["bullish_call"].get("contracts") or 0) == 0,
      f"contracts={legs_exp['bullish_call'].get('contracts')}")
# Affordability skip gate inside enter_proactive_set
_ocm2 = lab.collect_metadata
lab.collect_metadata = lambda t, mock=False: mde
recX = lab.enter_proactive_set("PRICEY", None, mock=False, candidate={"flow_type": "call"}, dry_run=True)
lab.collect_metadata = _ocm2
check(3, "affordability gate: pricey premium -> SKIPPED (scanner moves on)",
      recX.get("skipped") is True and "too rich" in recX.get("reason", ""), recX.get("reason", "")[:48])
# SAFETY: NEUTRAL/calendar route disabled (naked-leg risk under the directional Strategy B)
recN = lab.enter_proactive_set("ZNEUT", None, mock=True, candidate={}, dry_run=True)   # fresh ticker (no cool-off)
check(3, "NEUTRAL/calendar route disabled -> SKIPPED (no naked-leg)",
      recN.get("skipped") is True and recN.get("regime") == "NEUTRAL" and "calendar" in recN.get("reason", ""),
      f"{recN.get('regime')}/{recN.get('reason', '')[:40]}")

# Tiered exit state machine (manage_exit)
for label, dec, wa, ws in [
    ("initial +35% >24h -> SCALE_OUT_50 (stage->scaled)", lab.manage_exit(ts, 35.0, pe, now=at(26), stage="initial"), "SCALE_OUT_50", "scaled"),
    ("scaled runner -5% -> CLOSE_BREAKEVEN", lab.manage_exit(ts, -5.0, pe, now=at(48), stage="scaled"), "CLOSE_BREAKEVEN", "closed"),
    ("scaled runner +55% -> HOLD, trail armed", lab.manage_exit(ts, 55.0, pe, now=at(48), stage="scaled"), "HOLD", "trailing"),
    ("trailing peak100/ret75 -> CLOSE_TRAIL (<=80)", lab.manage_exit(ts, 75.0, pe, now=at(72), stage="trailing", mfe_pct=100.0), "CLOSE_TRAIL", "closed"),
    ("trailing peak100/ret85 -> HOLD (>80)", lab.manage_exit(ts, 85.0, pe, now=at(72), stage="trailing", mfe_pct=100.0), "HOLD", "trailing"),
]:
    check(3, label, dec["action"] == wa and dec["stage"] == ws, f"action={dec['action']} stage={dec['stage']}")

# Full chain: scale-out (50%) -> trail-arm -> trail-close through manage_open_positions
_wipe()
_ocp4 = lab._close_position
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: True
recR = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
_lg2 = lab._load_log_list()
_lg2[-1]["entry_ts_utc"] = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
lab._save_log_list(_lg2)
occR = recR["legs"]["bullish_call"]["occ_symbol"]
def _pos(plpc):
    return [{"symbol": occR, "avg_entry_price": "10", "current_price": "10", "unrealized_plpc": plpc, "qty": "4"}]
c1, _ = lab.manage_open_positions(("k", "s"), load_params(), positions=_pos("0.35"))   # +35% -> scale out 50%
stage1 = ((next(r for r in lab._load_log_list() if r["trade_set_id"] == recR["trade_set_id"]).get("leg_path") or {}).get("bullish_call") or {}).get("stage")
lab.manage_open_positions(("k", "s"), load_params(), positions=_pos("1.1"))            # +110% -> trail arms (peak 110)
c3, _ = lab.manage_open_positions(("k", "s"), load_params(), positions=_pos("0.8"))    # +80% <= 110*0.8=88 -> CLOSE_TRAIL
recR3 = next(r for r in lab._load_log_list() if r["trade_set_id"] == recR["trade_set_id"])
lab._close_position = _ocp4
check(3, "full chain: +35% fires SCALE_OUT_50, stage->scaled",
      any(x["action"] == "SCALE_OUT_50" for x in c1) and stage1 == "scaled", f"stage={stage1}")
check(3, "full chain: runner trail-closes (CLOSE_TRAIL) + autopsy",
      any(x["action"] == "CLOSE_TRAIL" for x in c3) and recR3.get("status") == "CLOSED",
      f"actions={[x['action'] for x in c3]} status={recR3.get('status')}")

# =====================================================================
print("\n=== DIMENSION 3C: SOURCING FILTER ($0.30-$4.00 band) + FLUSH ===")
import src.unusual_whales_api as _uwmod
_ouwc = _uwmod.UnusualWhalesClient
_uwmod.UnusualWhalesClient = type("FUWC", (), {"__init__": lambda s: None, "enabled": True,
    "flow_alerts": lambda s, ticker=None, limit=100, min_premium=None: {"data": [
        {"ticker": "CHEAP", "price": 2.0, "type": "call", "total_premium": 100000, "underlying_price": 40},
        {"ticker": "PRICEY", "price": 20.0, "type": "call", "total_premium": 500000, "underlying_price": 700},
        {"ticker": "PENNY", "price": 0.10, "type": "put", "total_premium": 60000, "underlying_price": 5},
        {"ticker": "MID", "price": 3.5, "type": "put", "total_premium": 200000, "underlying_price": 55},
        {"ticker": "SPXW", "price": 2.0, "type": "call", "total_premium": 300000, "underlying_price": 7000}]}})
cands = lab.scan_candidates(load_params())
_uwmod.UnusualWhalesClient = _ouwc
ctk = [c["ticker"] for c in cands]
check(3, "scanner keeps only $0.30-$4.00 band, drops pricey/penny/index, ranks by premium",
      ctk == ["MID", "CHEAP"], f"candidates={ctk}")
check(3, "scanner stamps min_contract_premium on affordable candidates",
      all("min_contract_premium" in c for c in cands) and cands[0]["min_contract_premium"] == 3.5, f"{[(c['ticker'], c.get('min_contract_premium')) for c in cands]}")

# flush: closes all positions, clears cool-off, marks OPEN log records FLUSHED
_wipe()
lab._save_log_list([{"trade_set_id": "leg1", "ticker": "IWM", "status": "OPEN", "legs": {}}])
json_dump = __import__("json").dump
json_dump({"IWM": "2026-07-01T00:00:00Z"}, open(lab.COOLOFF_PATH, "w"))
_ogp = lab.get_open_positions
_ocpf = lab._close_position
_omio = lab._market_is_open
lab.get_open_positions = lambda creds=None: [{"symbol": "OCC1"}, {"symbol": "OCC2"}]
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: True
lab._market_is_open = lambda creds=None: True     # market-open branch: real closes
n = lab.flush_positions(("k", "s"))
flushed_status = lab._load_log_list()[0]["status"]
cooloff_gone = not os.path.exists(lab.COOLOFF_PATH)
lab._market_is_open = _omio
lab.get_open_positions = _ogp
lab._close_position = _ocpf
check(3, "flush closes all positions (2), clears cool-off, marks log FLUSHED",
      n == 2 and cooloff_gone and flushed_status == "FLUSHED", f"closed={n} cooloff_gone={cooloff_gone} status={flushed_status}")

# flush SAFETY: on a CLOSED market it is a dry no-op - lists positions, fires zero closes
_ogp2 = lab.get_open_positions
_ocpf2 = lab._close_position
_omio2 = lab._market_is_open
_closes_attempted = []
lab.get_open_positions = lambda creds=None: [{"symbol": "OCC1"}, {"symbol": "OCC2"}]
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: (_closes_attempted.append(occ), True)[1]
lab._market_is_open = lambda creds=None: False
n_dry = lab.flush_positions(("k", "s"))
lab.get_open_positions = _ogp2
lab._close_position = _ocpf2
lab._market_is_open = _omio2
check(3, "flush on CLOSED market is a dry no-op (0 orders, 0 closes)",
      n_dry == 0 and len(_closes_attempted) == 0, f"returned={n_dry} closes_attempted={len(_closes_attempted)}")

# one-time auto-flush sentinel: absent -> skip; pending+closed -> wait (no orders); pending+open -> flush+clear
import tempfile as _tf
_snt = os.path.join(_tf.mkdtemp(), "FLUSH_PENDING")
_ofs, _omio3, _ogp3, _ocpf3 = lab.FLUSH_SENTINEL, lab._market_is_open, lab.get_open_positions, lab._close_position
_flushcalls = []
lab.FLUSH_SENTINEL = _snt
lab.get_open_positions = lambda creds=None: [{"symbol": "OCC1"}]
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: (_flushcalls.append(occ), True)[1]
no_sentinel = lab._maybe_flush_pending(("k", "s"))
open(_snt, "w").write("x")
lab._market_is_open = lambda creds=None: False
pend_closed = lab._maybe_flush_pending(("k", "s")); closed_safe = (len(_flushcalls) == 0 and os.path.exists(_snt))
lab._market_is_open = lambda creds=None: True
pend_open = lab._maybe_flush_pending(("k", "s")); open_flushed = (len(_flushcalls) == 1 and not os.path.exists(_snt))
lab.FLUSH_SENTINEL, lab._market_is_open, lab.get_open_positions, lab._close_position = _ofs, _omio3, _ogp3, _ocpf3
check(3, "auto-flush sentinel: skip when absent, wait when closed (0 orders), flush+clear when open",
      (no_sentinel is False) and pend_closed and closed_safe and pend_open and open_flushed,
      f"absent={no_sentinel} closed_safe={closed_safe} open_flushed={open_flushed}")

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
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: True
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
print("\n=== DIMENSION 6: TIER B GATES (blackout / brake / one-per-underlying / park / backstop) ===")
_wipe()
import harvest_logger as _hl
_params6 = load_params()
_now_iso = lab._now_iso_ms()
_today_iso = _now_iso[:10]

# 6.1 backstop ratchet level math (mirrors manage_exit stages)
lv_i = lab._backstop_level(2.00, "initial", None, _params6)
lv_s = lab._backstop_level(2.00, "scaled", 40.0, _params6)
lv_t = lab._backstop_level(2.00, "trailing", 100.0, _params6)
check(6, "backstop levels: initial -50% / scaled break-even / trailing 20%-off-peak",
      approx(lv_i, 1.00) and approx(lv_s, 2.00) and approx(lv_t, 3.60),
      f"initial={lv_i} scaled={lv_s} trailing={lv_t}")

# 6.2 OCC root boundary: BB never matches BBAI
check(6, "occ root match: BB matches BB2608.., NOT BBAI2608..",
      lab._occ_matches_base("BB260807P00011500", "BB") and not lab._occ_matches_base("BBAI260807C00005000", "BB"))

# 6.3 one-per-underlying: tracked blocks; orphan + PARKED exempt; pending entry blocks
_occA = "AMD260807C00100000"
_recA = {"trade_set_id": "x1", "ticker": "AMD", "status": "OPEN", "legs": {"bullish_call": {"occ_symbol": _occA}}}
_posA = [{"symbol": _occA, "qty": "2"}]
b1, w1 = lab.ticker_blocked("AMD", _posA, _params6, open_orders=[], log=[_recA])
b2, w2 = lab.ticker_blocked("AMD", _posA, _params6, open_orders=[], log=[])                       # orphan: no record
b3, w3 = lab.ticker_blocked("AMD", _posA, _params6, open_orders=[], log=[dict(_recA, status="PARKED")])
b4, w4 = lab.ticker_blocked("AMD", [], _params6, open_orders=[{"symbol": _occA, "side": "buy", "qty": "2"}], log=[])
check(6, "one-per-underlying: tracked position blocks", b1 and "one-per-underlying" in w1, w1)
check(6, "one-per-underlying: ORPHAN (no record) does NOT block", not b2, w2)
check(6, "one-per-underlying: PARKED record does NOT block", not b3, w3)
check(6, "one-per-underlying: pending entry order blocks", b4 and "pending" in w4, w4)

# 6.4 earnings blackout: 2d -> SKIP; 10d -> no blackout skip; None -> fail-open
_oped = v11.post_earnings_drift
for _dte, _want in ((2, True), (10, False), (None, False)):
    v11.post_earnings_drift = (lambda d: (lambda t, m=False, **k: {"days_to_earnings": d, "days_since_earnings": None,
                               "post_earnings_iv_crush_flag": None, "source": "mot"}))(_dte)
    _r = lab.enter_proactive_set("AMD", None, mock=True, candidate={"flow_type": "call"}, dry_run=True)
    _got = bool(_r.get("skipped")) and "earnings blackout" in str(_r.get("reason", ""))
    check(6, f"earnings blackout: days_to_earnings={_dte} -> {'SKIP' if _want else 'no blackout skip'}",
          _got == _want, str(_r.get("reason", "entered"))[:70])
    _wipe()
v11.post_earnings_drift = _oped

# 6.5 daily brake: 3 stop-outs OR 2x-allocation loss; clear otherwise
def _mk_exit(action, ret):
    return {"trade_set_id": "b" + action + str(ret), "ticker": "T", "status": "CLOSED",
            "legs": {"bullish_call": {"occ_symbol": "T260807C00001000", "alloc_usd": 800.0}},
            "leg_exits": {"bullish_call": {"occ": "T260807C00001000", "closed_at": _now_iso,
                                           "return_pct": ret, "action": action, "closed_ok": True}}}
br1 = lab.daily_brake_status(_params6, log=[_mk_exit("CLOSE_STOP_LOSS", -50)] * 3)
br2 = lab.daily_brake_status(_params6, log=[_mk_exit("CLOSE_BREAKEVEN", -100), _mk_exit("CLOSE_TRAIL", -100)])
br3 = lab.daily_brake_status(_params6, log=[_mk_exit("CLOSE_STOP_LOSS", -50)])
check(6, "daily brake: 3 stop-outs trips", br1[0] and "stop-outs" in br1[1], br1[1])
check(6, "daily brake: $1600 realized loss (2x alloc) trips without stop-outs", br2[0] and "2x allocation" in br2[1], br2[1])
check(6, "daily brake: 1 stop-out stays clear", not br3[0], br3[1])

# 6.5b brake MODES (2026-07-08): judgment always evaluates; ACTION (suppress) only in 'active'
_trip = [_mk_exit("CLOSE_STOP_LOSS", -50)] * 3
m_off = lab.brake_decision({**_params6, "brake_mode": "off"}, log=_trip)
m_sh = lab.brake_decision({**_params6, "brake_mode": "shadow"}, log=_trip)
m_ac = lab.brake_decision({**_params6, "brake_mode": "active"}, log=_trip)
m_def = lab.brake_decision(dict(_params6), log=_trip)          # _params6 = load_params() -> default shadow
check(6, "brake mode OFF: not evaluated, never braked", m_off[1] is False and m_off[2] is False, str(m_off[:3]))
check(6, "brake mode SHADOW: judged braked=True but active(suppress)=False", m_sh[1] is True and m_sh[2] is False, str(m_sh[:3]))
check(6, "brake mode ACTIVE: braked=True and active=True (suppresses)", m_ac[1] is True and m_ac[2] is True, str(m_ac[:3]))
check(6, "brake DEFAULT is shadow (unsuppressed) - entries fire", m_def[0] == "shadow" and m_def[1] is True and m_def[2] is False, str(m_def[:3]))

# 6.6 park: N no-bid failures -> PARKED once; a live bid resets the counter
_osp = v11.option_spread
v11.option_spread = lambda occ: {"bid": None}
_recP = {"trade_set_id": "p1", "ticker": "ZZ", "status": "OPEN", "legs": {"bullish_call": {"occ_symbol": "ZZ260807C00001000"}}}
_pathP = {"close_fails": 4}
_capP = []
_onp = lab._notify
lab._notify = lambda text: (_capP.append(text), True)[1]
lab._note_close_failure(_recP, _pathP, "bullish_call", "ZZ260807C00001000", _params6)
parked_ok = _recP["status"] == "PARKED" and len([t for t in _capP if "PARKED" in t]) == 1
v11.option_spread = lambda occ: {"bid": 0.25}
_recP2 = {"trade_set_id": "p2", "ticker": "ZZ", "status": "OPEN", "legs": {}}
_pathP2 = {"close_fails": 4}
lab._note_close_failure(_recP2, _pathP2, "bullish_call", "ZZ260807C00001000", _params6)
reset_ok = _recP2["status"] == "OPEN" and _pathP2["close_fails"] == 0
lab._notify = _onp
v11.option_spread = _osp
check(6, "park: 5th no-bid failure -> PARKED with ONE alert", parked_ok, f"status={_recP['status']} alerts={len(_capP)}")
check(6, "park: live bid resets the fail counter (stays OPEN)", reset_ok, f"fails={_pathP2['close_fails']}")

# 6.7 flush record-flip fix: only successfully-closed records marked FLUSHED
_wipe()
_occF1, _occF2 = "FA260807C00001000", "FB260807C00001000"
lab._save_log_list([
    {"trade_set_id": "f1", "ticker": "FA", "status": "OPEN", "legs": {"bullish_call": {"occ_symbol": _occF1}}},
    {"trade_set_id": "f2", "ticker": "FB", "status": "OPEN", "legs": {"bullish_call": {"occ_symbol": _occF2}}}])
_omio, _ogop, _ocp6, _onp6 = lab._market_is_open, lab.get_open_positions, lab._close_position, lab._notify
lab._market_is_open = lambda creds=None: True
lab.get_open_positions = lambda creds=None: [{"symbol": _occF1, "qty": "1"}, {"symbol": _occF2, "qty": "1"}]
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: occ == _occF1          # FB close FAILS
lab._notify = lambda text: True
lab.flush_positions(("k", "s"))
_lg = lab._load_log_list()
_stF = {r["trade_set_id"]: r["status"] for r in _lg if r.get("trade_set_id")}
lab._market_is_open, lab.get_open_positions, lab._close_position, lab._notify = _omio, _ogop, _ocp6, _onp6
check(6, "flush fix: closed-ok record FLUSHED, failed-close record stays OPEN",
      _stF.get("f1") == "FLUSHED" and _stF.get("f2") == "OPEN", str(_stF))

# 6.8 backstop arming: canary-only, stop/gtc body, qty-sync cancel+resubmit
_wipe()
_occX, _occY = "XA260807C00002000", "YB260807C00002000"
lab._save_log_list([
    {"trade_set_id": "bx", "ticker": "XA", "status": "OPEN", "legs": {"bullish_call": {"occ_symbol": _occX}}},
    {"trade_set_id": "by", "ticker": "YB", "status": "OPEN", "legs": {"bullish_call": {"occ_symbol": _occY}}}])
_pos6 = [{"symbol": _occX, "qty": "2", "avg_entry_price": "2.00"},
         {"symbol": _occY, "qty": "3", "avg_entry_price": "1.00"}]
_subs, _cans = [], []
_ospo, _ogoo, _ocan, _oos8 = lab._submit_paper_order, lab.get_open_orders, lab._cancel_order, lab._order_state
_onp8 = lab._notify; lab._notify = lambda text: True        # arm now _notify's -> stub it like every neighbour
lab._submit_paper_order = lambda body, creds: (_subs.append(body), ("oid" + str(len(_subs)), "accepted", None))[1]
lab.get_open_orders = lambda creds=None: []
lab._cancel_order = lambda oid, creds: (_cans.append(oid), True)[1]
lab._order_state = lambda oid, creds: None                 # no fill on the just-cancelled ratchet order
_p6 = dict(_params6); _p6["backstop_enabled"] = True; _p6["backstop_canary_occ"] = _occX
acts = lab.manage_backstops(("k", "s"), _p6, positions=_pos6)
canary_ok = len(acts) == 1 and acts[0]["occ"] == _occX and len(_subs) == 1
body_ok = _subs and _subs[0]["type"] == "stop" and _subs[0]["time_in_force"] == "gtc" and _subs[0]["stop_price"] == "1.0"
check(6, "backstop canary: only the canary OCC armed", canary_ok, f"acts={[a['occ'] for a in acts]}")
check(6, "backstop order: type=stop tif=gtc stop=entry x 0.50", bool(body_ok), str(_subs[0] if _subs else None))
_subs.clear(); _cans.clear()
_p6["backstop_canary_occ"] = ""
lab.get_open_orders = lambda creds=None: [{"symbol": _occX, "type": "stop", "side": "sell", "id": "old1",
                                           "stop_price": "1.0", "qty": "1"}]    # right level, WRONG qty (2 held)
acts2 = lab.manage_backstops(("k", "s"), _p6, positions=_pos6)
qty_sync = "old1" in _cans and any(b["symbol"] == _occX and b["qty"] == "2" for b in _subs)
fleet = any(b["symbol"] == _occY for b in _subs)
lab._submit_paper_order, lab.get_open_orders, lab._cancel_order, lab._order_state, lab._notify = _ospo, _ogoo, _ocan, _oos8, _onp8
check(6, "backstop qty-sync: wrong-qty stop cancelled + resubmitted at held qty", qty_sync, f"cancels={_cans}")
check(6, "backstop fleet mode: non-canary position armed when canary empty", fleet)

# 6.8b rejected submit (session-review fix): a broker rejection returns a TRUTHY id + terminal status; it
#       must NOT be persisted as the resting stop (else next cycle reads a dead order_id, thinks it is armed,
#       and the real re-arm goes silent). order_id must be None so the re-arm counts as a fresh first-arm.
_wipe()
_occZ = "ZC260807C00002000"
lab._save_log_list([{"trade_set_id": "bz", "ticker": "ZC", "status": "OPEN",
                     "legs": {"bullish_call": {"occ_symbol": _occZ}}}])
_ospoZ, _ogooZ, _oosZ, _onpZ = lab._submit_paper_order, lab.get_open_orders, lab._order_state, lab._notify
lab._submit_paper_order = lambda body, creds: ("deadid", "rejected", None)   # truthy id, TERMINAL status
lab.get_open_orders = lambda creds=None: []
lab._order_state = lambda oid, creds: None
lab._notify = lambda text: True
_pZ = dict(_params6); _pZ["backstop_enabled"] = True; _pZ["backstop_canary_occ"] = _occZ
lab.manage_backstops(("k", "s"), _pZ, positions=[{"symbol": _occZ, "qty": "2", "avg_entry_price": "2.00"}])
_bsZ = ((next((r for r in lab._load_log_list() if r.get("trade_set_id") == "bz"), {})).get("backstop") or {}).get("bullish_call") or {}
lab._submit_paper_order, lab.get_open_orders, lab._order_state, lab._notify = _ospoZ, _ogooZ, _oosZ, _onpZ
check(6, "backstop rejected submit: dead id NOT persisted as the resting stop (real re-arm stays first-arm)",
      _bsZ.get("order_id") is None and _bsZ.get("status") == "rejected", str(_bsZ)[:80])

# 6.9 cancel-before-close + backstop-fill reconciliation + PDT ledger
_wipe()
_occR = "RC260807C00003000"
lab._save_log_list([{"trade_set_id": "r1", "ticker": "RC", "status": "OPEN",
                     "entry_ts_utc": _now_iso, "legs": {"bullish_call": {"occ_symbol": _occR}},
                     "backstop": {"bullish_call": {"order_id": "bs1", "entry_px": 2.0, "stop_price": 1.0}}}])
_calls = []
_ocan2, _ocp7, _onp7, _oos9 = lab._cancel_order, lab._close_position, lab._notify, lab._order_state
lab._cancel_order = lambda oid, creds: (_calls.append(("cancel", oid)), True)[1]
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: (_calls.append(("close", occ)), True)[1]
lab._notify = lambda text: True
lab._order_state = lambda oid, creds: {"status": "canceled", "filled_qty": 0}   # stop confirmed DEAD, no fill
lab.manage_open_positions(("k", "s"), _params6,
                          positions=[{"symbol": _occR, "avg_entry_price": "2.0", "unrealized_plpc": "-0.6", "qty": "2"}])
order_ok = _calls and _calls[0] == ("cancel", "bs1") and ("close", _occR) in _calls
check(6, "exit pass cancels + CONFIRMS the resting backstop BEFORE closing", order_ok, str(_calls))
_wipe()
lab._save_log_list([{"trade_set_id": "r2", "ticker": "RD", "status": "OPEN",
                     "entry_ts_utc": _now_iso, "legs": {"bullish_call": {"occ_symbol": "RD260807C00003000"}},
                     "backstop": {"bullish_call": {"order_id": "bs2", "entry_px": 2.0, "qty": 2, "stop_price": 1.0}}}])
lab._order_state = lambda oid, creds: {"status": "filled", "filled_qty": "2", "filled_avg_price": "1.0", "filled_at": _now_iso}
lab.manage_open_positions(("k", "s"), _params6, positions=[])          # position GONE -> reconcile the stop fill
lab._cancel_order, lab._close_position, lab._notify, lab._order_state = _ocan2, _ocp7, _onp7, _oos9
_lg2 = lab._load_log_list()
_r2 = next((r for r in _lg2 if r.get("trade_set_id") == "r2"), {})
_ex2 = (_r2.get("leg_exits") or {}).get("bullish_call") or {}
_dt2 = [r for r in _lg2 if r.get("type") == "day_trade"]
check(6, "backstop fill reconciled: CLOSE_BACKSTOP exit at -50%", _ex2.get("action") == "CLOSE_BACKSTOP" and approx(_ex2.get("return_pct"), -50.0), str(_ex2)[:90])
check(6, "PDT ledger: same-day backstop fill logged as a day trade", len(_dt2) == 1, f"markers={len(_dt2)}")

# 6.12 CONFIRMED-CANCEL (the CRITICAL fix): an unconfirmable stop cancel must NOT close - retry, not deadlock
_wipe()
_occU = "UF260807C00004000"
lab._save_log_list([{"trade_set_id": "u1", "ticker": "UF", "status": "OPEN", "entry_ts_utc": _now_iso,
                     "legs": {"bullish_call": {"occ_symbol": _occU}},
                     "backstop": {"bullish_call": {"order_id": "us1", "entry_px": 2.0, "qty": 2}}}])
_uc = []
_ocanU, _ocpU, _onpU, _oosU = lab._cancel_order, lab._close_position, lab._notify, lab._order_state
lab._cancel_order = lambda oid, creds: False                          # cancel DELETE not accepted
lab._order_state = lambda oid, creds: {"status": "accepted", "filled_qty": 0}   # stop still LIVE (non-terminal)
lab._close_position = lambda occ, creds, percentage=100, decision_mark=None: (_uc.append(occ), True)[1]
lab._notify = lambda text: True
lab.manage_open_positions(("k", "s"), _params6,
                          positions=[{"symbol": _occU, "avg_entry_price": "2.0", "unrealized_plpc": "-0.6", "qty": "2"}])
_rU = next((r for r in lab._load_log_list() if r.get("trade_set_id") == "u1"), {})
lab._cancel_order, lab._close_position, lab._notify, lab._order_state = _ocanU, _ocpU, _onpU, _oosU
check(6, "confirmed-cancel: live stop -> NO close, leg stays OPEN (retry, not deadlock)",
      len(_uc) == 0 and _rU.get("status") == "OPEN" and "bullish_call" not in (_rU.get("leg_exits") or {}),
      f"closes={len(_uc)} status={_rU.get('status')} exits={list((_rU.get('leg_exits') or {}).keys())}")

# 6.13 reconciliation polls SUPERSEDED order ids (the HIGH fix: a ratchet resubmit must not lose an old fill)
_wipe()
_occP = "PG260807C00005000"
lab._save_log_list([{"trade_set_id": "p3", "ticker": "PG", "status": "OPEN", "entry_ts_utc": _now_iso,
                     "legs": {"bullish_call": {"occ_symbol": _occP}},
                     "backstop": {"bullish_call": {"order_id": "new_id", "prior_order_ids": ["old_id"],
                                                   "entry_px": 2.0, "qty": 2}}}])
_oosP, _onpP = lab._order_state, lab._notify
lab._order_state = lambda oid, creds: ({"status": "filled", "filled_qty": "2", "filled_avg_price": "1.2", "filled_at": _now_iso}
                                       if oid == "old_id" else {"status": "canceled", "filled_qty": 0})
lab._notify = lambda text: True
lab.manage_open_positions(("k", "s"), _params6, positions=[])
_rP = next((r for r in lab._load_log_list() if r.get("trade_set_id") == "p3"), {})
_exP = (_rP.get("leg_exits") or {}).get("bullish_call") or {}
lab._order_state, lab._notify = _oosP, _onpP
check(6, "reconciliation finds a fill on a SUPERSEDED backstop id (-40%)",
      _exP.get("action") == "CLOSE_BACKSTOP" and approx(_exP.get("return_pct"), -40.0), str(_exP)[:80])

# 6.15 partial-fill fix (session-review #1/#5): a live partially_filled stop is NEVER booked (id not
#      burned -> no strand); a TERMINAL partial is audit-only (no leg_exit, not a stop-out) so the leg
#      keeps its remainder for the cron's single exit (no double-count, no permanent re-entry block)
_wipe()
_occPF = "PF260807C00006000"
_oosPF, _onpF = lab._order_state, lab._notify
lab._notify = lambda text: True
lab._order_state = lambda oid, creds: {"status": "partially_filled", "filled_qty": "1",
                                       "filled_avg_price": "1.0", "filled_at": _now_iso}   # STILL LIVE
_live_partial = lab._order_fill("pf_live", ("k", "s"))
_recPF = {"trade_set_id": "pf1", "ticker": "PF", "status": "OPEN", "entry_ts_utc": _now_iso,
          "legs": {"bullish_call": {"occ_symbol": _occPF}},
          "backstop": {"bullish_call": {"order_id": "pf_id", "entry_px": 2.0, "qty": 2}}}
lab._order_state = lambda oid, creds: {"status": "canceled", "filled_qty": "1",
                                       "filled_avg_price": "1.0", "filled_at": _now_iso}    # TERMINAL partial (1 of 2)
_clpf = []
_full = lab._capture_backstop_fill(_recPF, "bullish_call", _occPF, ("k", "s"), [], _clpf)
_bsPF = (_recPF.get("backstop") or {}).get("bullish_call") or {}
lab._order_state, lab._notify = _oosPF, _onpF
check(6, "partial fix: a live partially_filled stop returns no fill (id not burned mid-flight)", _live_partial is None)
check(6, "partial fix: terminal partial books NO leg_exit + reports leg NOT fully-exited",
      _full is False and "bullish_call" not in (_recPF.get("leg_exits") or {}) and len(_clpf) == 0)
check(6, "partial fix: terminal partial recorded to bs['partials'] for audit (1 of 2)",
      len(_bsPF.get("partials") or []) == 1 and (_bsPF.get("partials") or [{}])[0].get("filled_qty") == 1)

# 6.14 orphan adoption (ROADMAP 2b): one-per-underlying reads RECORDS -> an orphan must be ADOPTED to block
_wipe()
_occO = "ORPH260821C00010000"
# before adoption: a held position with NO record does NOT block its ticker (proves it reads records)
_b_before, _ = lab.ticker_blocked("ORPH", [{"symbol": _occO, "qty": "2"}], _params6, open_orders=[], log=[])
_onpO = lab._notify; lab._notify = lambda text: True
_ad = lab.reconcile_orphans(("k", "s"), _params6, positions=[{"symbol": _occO, "qty": "2", "avg_entry_price": "1.20"}], log=[])
_recO = next((r for r in lab._load_log_list() if r.get("adopted")), {})
_occK = "KNWN260821C00010000"                                # a PARKED straggler must NOT be adopted (stays exempt)
_ad2 = lab.reconcile_orphans(("k", "s"), _params6, positions=[{"symbol": _occK, "qty": "1", "avg_entry_price": "0.5"}],
                             log=[{"trade_set_id": "k1", "ticker": "KNWN", "status": "PARKED",
                                   "legs": {"bullish_call": {"occ_symbol": _occK}}}])
lab._notify = _onpO
_b_after, _wA = lab.ticker_blocked("ORPH", [{"symbol": _occO, "qty": "2"}], _params6, open_orders=[],
                                   log=[dict(_recO)] if _recO else [])
check(6, "2b: orphan (no record) does NOT block re-entry (one-per-underlying reads RECORDS)", not _b_before)
check(6, "2b: reconcile_orphans adopts the orphan into an OPEN record",
      _ad == [_occO] and _recO.get("status") == "OPEN" and _recO.get("adopted") is True and _recO.get("ticker") == "ORPH")
check(6, "2b: PARKED straggler is NOT adopted (stays exempt)", _ad2 == [])
check(6, "2b: after adoption the underlying IS blocked", _b_after and "one-per-underlying" in _wA)

# 6.10 adaptive harvest cap: reserve + remainder + 429 halving + ceiling
_opoc = _hl._projected_open_candidates
_hl._projected_open_candidates = lambda: 2600                          # reserve = 26 calls x 26 runs = 676
_pc = {"harvest_daily_cap": 300, "harvest_api_budget_per_day": 1500, "poller_chunk": 100,
       "poller_runs_per_day": 26, "harvest_calls_per_payload": 3}
_st1 = {"backoff_429": False}
cap1 = _hl._adaptive_cap(_pc, _st1)                                     # (1500-676)//3 = 274
_st2 = {"backoff_429": True}
cap2 = _hl._adaptive_cap(_pc, _st2)                                     # 274 // 2 = 137
cap3 = _hl._adaptive_cap({**_pc, "harvest_api_budget_per_day": 60000}, {"backoff_429": False})   # ceiling 300
_hl._projected_open_candidates = _opoc
check(6, "adaptive cap: floats into (budget - poller reserve) / calls-per-payload", cap1 == 274,
      f"cap={cap1} inputs={_st1.get('cap_inputs')}")
check(6, "adaptive cap: any 429 halves the day's cap", cap2 == 137, f"cap={cap2}")
check(6, "adaptive cap: harvest_daily_cap stays the hard ceiling", cap3 == 300, f"cap={cap3}")

# 6.16 SPREAD CAP (governed change 2026-07-25): the real Alpaca spread at OCC resolution now GATES
#      entry; a dead sensor (spread None) never blocks (fail-open)
_wipe()
_ocm, _ocr, _obl, _otb = lab.collect_metadata, lab.classify_regime, lab.build_legs, lab.ticker_blocked
_onp16 = lab._notify; lab._notify = lambda text: True
lab.collect_metadata = lambda t, mock=False: {"macro": {"spot": 100.0, "source": "mock"},
                                              "iv_term": {"iv_front": 0.5, "source": "mock"},
                                              "pemd": {}, "entry_ts_utc": _now_iso}
lab.classify_regime = lambda md, c=None: "BULL_TREND"
lab.ticker_blocked = lambda t, p, prm, open_orders=None, log=None: (False, "")
def _legs_with_spread(sp):
    return {"bullish_call": {"structure": "LONG_CALL", "occ_symbol": "SC260821C00010000",
                             "expiry": "2026-08-21", "strike": 10.0, "entry_premium": 1.0,
                             "limit_price": 1.02, "contracts": 2,
                             "execution_cost": {"bid": 0.9, "ask": 1.02, "bid_ask_spread_pct": sp}}}
lab.build_legs = lambda t, md, r, illiquid=None: _legs_with_spread(12.0)
_r16a = lab.enter_proactive_set("SC", None, mock=True, dry_run=True, resolve_real=False)
lab.build_legs = lambda t, md, r, illiquid=None: _legs_with_spread(3.0)
_r16b = lab.enter_proactive_set("SC", None, mock=True, dry_run=True, resolve_real=False)
lab.build_legs = lambda t, md, r, illiquid=None: _legs_with_spread(None)
_r16c = lab.enter_proactive_set("SC", None, mock=True, dry_run=True, resolve_real=False)
lab.collect_metadata, lab.classify_regime, lab.build_legs, lab.ticker_blocked = _ocm, _ocr, _obl, _otb
lab._notify = _onp16
check(6, "spread cap: real spread 12% > 5% cap -> SKIPPED with spread_cap reason",
      _r16a.get("skipped") and "spread_cap" in _r16a.get("reason", ""), str(_r16a.get("reason"))[:70])
check(6, "spread cap: 3% spread passes the 5% cap (entry proceeds)", not _r16b.get("skipped"))
check(6, "spread cap: missing spread NEVER blocks (fail-open)", not _r16c.get("skipped"))
check(6, "spread cap: skip reason maps to harvest code 'spread_cap'",
      lab._skip_code(_r16a.get("reason", "")) == "spread_cap")

# 6.11 digest renders the scoreboard + alert-reconciliation lines
_dg6 = lab.daily_digest()
check(6, "digest: scoreboard + alert reconciliation lines render",
      "Scoreboard:" in _dg6 and "Alert reconciliation:" in _dg6)

# =====================================================================
_wipe()

# --- Dimension 7: FADE BOOK (2026-08-05 retool) ------------------------------------------------
print("\n--- Dimension 7: FADE book state machine + gates ---")
import fade_book as fb
check(7, "FORCE_OFF honored (this harness runs OFF-state)", fb.active() is False, str(fb.active()))
_env = os.environ.pop("FADE_BOOK_FORCE_OFF")
fb._SPEC = {"status": "LIVE", "entry": {"flow_min": 50000, "flow_max": 250000, "max_spread_pct": 2.0},
            "max_concurrent": 5}
check(7, "spec LIVE -> active()", fb.active() is True)
_mdF = {"macro": {"distance_to_sma20_pct": -2.0}, "regime_stack": {"market_spy_dist_pct": -0.5}}
check(7, "fade shape accepted (call flow, trend+SPY both down)",
      fb.direction(_mdF, {"flow_type": "call"}) == "BULLISH")
_mdN = {"macro": {"distance_to_sma20_pct": +2.0}, "regime_stack": {"market_spy_dist_pct": -0.5}}
check(7, "non-fade shape rejected (trend agrees)", fb.direction(_mdN, {"flow_type": "call"}) is None)
check(7, "flow band filter keeps mid, drops whale+small",
      [c["t"] for c in ({"t": "A", "total_premium": 900000}, {"t": "B", "total_premium": 120000},
                        {"t": "C", "total_premium": 30000}) if c in fb.flow_band([
          {"t": "A", "total_premium": 900000}, {"t": "B", "total_premium": 120000},
          {"t": "C", "total_premium": 30000}])] == ["B"])
check(7, "spread cap override 2.0 when LIVE", fb.spread_cap(5.0) == 2.0)
_fd = lab.manage_exit(ts, 35.0, p, now=at(26), book="FADE")
check(7, "FADE exit: +35% -> HOLD (no scale-out)", _fd["action"] == "HOLD" and _fd["stage"] == "initial", _fd["action"])
_fd2 = lab.manage_exit(ts, 55.0, p, now=at(26), book="FADE")
check(7, "FADE exit: +55% -> trail armed from initial", _fd2["action"] == "HOLD" and _fd2["stage"] == "trailing")
_fd3 = lab.manage_exit(ts, -55.0, p, now=at(2), book="FADE")
check(7, "FADE exit: -55% -> stop", _fd3["action"] == "CLOSE_STOP_LOSS")
fb._SPEC = None
os.environ["FADE_BOOK_FORCE_OFF"] = _env

print("\n" + "=" * 70)
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r[2])
by_dim = {}
for dim, _, ok, _d in RESULTS:
    s = by_dim.setdefault(dim, [0, 0]); s[1] += 1; s[0] += int(ok)
names = {1: "Input & Schema", 2: "Routing", 3: "Exit & Autopsy", 4: "Sizing Floor", 5: "Observability",
         6: "Tier B Gates", 7: "FADE Book"}
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

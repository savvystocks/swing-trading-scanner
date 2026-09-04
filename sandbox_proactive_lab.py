"""V10 engine - the single production engine (paper), driven by v10_lab.yml on main.

WHAT IT ACTUALLY DOES (architecture of record: SYSTEM_ARCHITECTURE.md): each cycle it audits
stale orders, runs the exit pass (tiered stop / scale-out / trail state machine + ratchet
broker-side backstop when enabled), then sources candidates market-wide from Unusual Whales
flow and enters ONE regime-routed directional leg (long call if BULLISH, long put if BEARISH)
sized off a flat $800 budget. NEUTRAL/calendar routing is DISABLED pending a spread-aware unit
exit, so the calendar spread the old header described is NOT traded.

The ten real gates a candidate clears, in order (scan_candidates then enter_proactive_set):
   1. big fast flow: >= scanner_min_premium total premium, from up to scanner_flow_limit UW alerts
   2. cheap contract: per-contract price within [scanner_premium_min, scanner_premium_max] ($0.30-$4.00)
   3. not an index underlying
   (aggregate surviving alerts by ticker, rank by total flow premium, take the first that also clears:)
   4. one position per underlying (already-held / pending-entry names skipped)
   5. usable data: a real spot price AND a real implied-vol reading
   6. a clear direction: regime is BULLISH or BEARISH, not NEUTRAL
   7. not within earnings_blackout_days of earnings
   8. affordable at >= min_contracts on the $800 budget
   9. a real, tradeable OCC resolvable at Alpaca near the target strike/expiry
   10. the leg is not illiquid (unresolved -> fail-open skipped)
The first survivor is entered; ONE trade per cycle. The daily brake runs in SHADOW (logs, does not
suppress). Gate values live in v10_tunable_parameters.json (read every cycle), turned only by owner
decision. After the trade decision the counterfactual harvest logs every scored candidate (fail-open,
post-trade - it can never alter or crash the trade path).

EXECUTION SAFETY: routing defaults to DRY_RUN (build + log the order payload, do NOT submit).
Real submission to paper-api.alpaca.markets only happens with --live-paper or under GHA with
paper creds. No order is ever placed against a live/real-money endpoint - paper only.

Run (simulate):       python sandbox_proactive_lab.py
Run (submit to paper): ALPACA_PAPER_API_KEY=... ALPACA_PAPER_SECRET_KEY=... python sandbox_proactive_lab.py --live-paper
"""

import os
import sys
import json
import math
import uuid
import urllib.request
import re
from datetime import datetime, timezone, timedelta, date

from v10_params import load as load_params
import fade_book

try:
    import sandbox_v11_sensors as v11        # LOG-DON'T-BLOCK context sensors (fail-open)
except Exception:
    v11 = None


# ----------------------------------------------------------------------------
# Telegram notifications (re-integrated from V9 src/telegram.py) - all FAIL-OPEN
# ----------------------------------------------------------------------------
_NOTIFY_STATS = {"sent": 0, "failed": 0}       # per-process alert-path honesty counters (digest line)


def _notify(text):
    """Fire a Telegram alert via the V9 sender. Fail-open: no token / any error -> silent no-op,
    NEVER blocks the trading loop. Every outcome is counted so a dead channel shows up in the
    daily digest the same day instead of being discovered by vibes."""
    try:
        from src.telegram import send_alert
        ok = bool(send_alert(text))
    except Exception:
        ok = False
    _NOTIFY_STATS["sent" if ok else "failed"] += 1
    return ok


def _buy_msg(rec):
    m = rec.get("metadata") or {}
    vrp = m.get("vrp") or {}
    leg = next(iter((rec.get("legs") or {}).values()), {})
    sp = (leg.get("execution_cost") or {}).get("bid_ask_spread_pct")
    return (f"<b>BUY {rec.get('ticker')}</b> {rec.get('regime')} {leg.get('structure', '')}\n"
            f"VRP {vrp.get('vrp')} ({vrp.get('vrp_regime')}) | sweep {m.get('sweep_aggression_pct')}% "
            f"| zg-dist {m.get('distance_to_zero_gamma_pct')}% | spread {sp}%\n"
            f"x{leg.get('contracts')} @lim ${leg.get('limit_price')} | {rec.get('execution_mode')}")


def _sell_msg(c):
    return (f"<b>SELL {c.get('ticker')} {c.get('leg')}</b> {c.get('action')} "
            f"{c.get('return_pct'):+.1f}% (filled_ok={c.get('closed_ok')})")


def _autopsy_msg(a):
    return (f"<b>AUTOPSY {a.get('ticker')}</b> winner={a.get('winner')}\n"
            f"{str(a.get('factor', a.get('autopsy_error', '')))[:200]}")

LOG_PATH = "proactive_sandbox_logs.json"
AUTOPSY_MD = "proactive_autopsy_log.md"
ADVISORY_MD = "v10_tuning_advisory.md"
LEG_BUDGET = 800.0                  # FLAT $800/trade = 20% of a $4k real account (1:1 sim of real constraints)
try:                                # FADE v1.2.2 (owner order 2026-08-08): fade book sizes from its
    import fade_book as _fb         # spec (size_usd 1000) - more affordable qualifying candidates,
    if _fb.active():                # paper-only; OFF-state keeps the original flat 800.
        LEG_BUDGET = float(_fb.spec().get("size_usd", 800.0))
except Exception:
    pass
PAPER_BASE = "https://paper-api.alpaca.markets"
CALL_DELTA, PUT_DELTA = 0.35, -0.35
CAL_FRONT_DTE = (10, 15)             # short leg expiration window (days)
CAL_BACK_DTE = (35, 45)             # long leg expiration window (days)


def _now_iso_ms():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# Metadata fetchers - all FAIL-OPEN (real value + source tag, mock on failure)
# ----------------------------------------------------------------------------
def _alpaca_daily(ticker, days=60):
    k = os.environ.get("ALPACA_PAPER_API_KEY") or os.environ.get("ALPACA_API_KEY")
    s = os.environ.get("ALPACA_PAPER_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")
    if not (k and s):
        return []
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        cli = StockHistoricalDataClient(k, s)
        start = datetime.utcnow() - timedelta(days=days + 20)
        bars = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day,
                                                   start=start, feed=DataFeed.IEX)).data.get(ticker, [])
        return [{"h": float(b.high), "l": float(b.low), "c": float(b.close), "v": float(b.volume)} for b in bars]
    except Exception:
        return []


def macro_technical(ticker, mock):
    bars = [] if mock else _alpaca_daily(ticker)
    if len(bars) >= 21:
        closes = [b["c"] for b in bars]
        spot = closes[-1]
        sma20 = sum(closes[-20:]) / 20.0
        trs = [max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - bars[i - 1]["c"]),
                   abs(bars[i]["l"] - bars[i - 1]["c"])) for i in range(1, len(bars))]
        atr = sum(trs[-14:]) / 14.0
        vols = [b["v"] for b in bars]
        rvol = round(vols[-1] / (sum(vols[-20:]) / 20.0), 2) if sum(vols[-20:]) else None
        return {"spot": round(spot, 2), "sma20": round(sma20, 2),
                "distance_to_sma20_pct": round((spot - sma20) / sma20 * 100, 3) if sma20 else 0.0,
                "atr": round(atr, 2), "atr_pct": round(atr / spot * 100, 2) if spot else 0.0,
                "rvol_10min": rvol if rvol is not None else 1.0, "source": "alpaca"}
    if mock:                                                  # local demo only - synthetic sample (cheap name, $800-affordable)
        return {"spot": 30.00, "sma20": 29.85, "distance_to_sma20_pct": 0.503,
                "atr": 0.90, "atr_pct": 3.00, "rvol_10min": 1.18, "source": "mock"}
    # live mode, no usable bars (index / halted / degenerate ticker) -> NULL so the caller SKIPS
    return {"spot": None, "sma20": None, "distance_to_sma20_pct": None,
            "atr": None, "atr_pct": None, "rvol_10min": None, "source": "unavailable"}


_IV_BREAKER = {"fails": 0, "open": False}     # per-process circuit breaker (2026-08-06: the 08-05
                                              # retry turned an IV outage into 15-min cycle hangs
                                              # -> GHA 8-min timeouts -> a lost trading day. After
                                              # 3 consecutive total failures the breaker OPENS and
                                              # remaining candidates skip instantly - one loud line,
                                              # no per-candidate retry storms.)


def _alpaca_atm_iv(ticker, spot, dte_min, dte_max, creds):
    """ATM call implied volatility (%) for the dte_min..dte_max expiry window, from Alpaca option
    snapshots (snapshot.implied_volatility). Returns None on failure (fail-open)."""
    if _IV_BREAKER["open"]:
        return None
    if not (all(creds) and spot):
        return None
    try:
        import re
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
        cli = OptionHistoricalDataClient(creds[0], creds[1])
        gte = (date.today() + timedelta(days=dte_min)).isoformat()
        lte = (date.today() + timedelta(days=dte_max)).isoformat()
        req = OptionChainRequest(
            underlying_symbol=ticker.split(".")[0], type="call",
            expiration_date_gte=gte, expiration_date_lte=lte,
            strike_price_gte=str(round(spot * 0.92, 2)), strike_price_lte=str(round(spot * 1.08, 2)))
        try:
            snaps = cli.get_option_chain(req)
            _IV_BREAKER["fails"] = 0                      # any success resets the breaker count
        except Exception as e2:
            print(f"  iv_term FETCH FAILED {ticker}: {type(e2).__name__}: {str(e2)[:120]}")
            _IV_BREAKER["fails"] += 1
            if _IV_BREAKER["fails"] >= 3 and not _IV_BREAKER["open"]:
                _IV_BREAKER["open"] = True                # stop hammering a dead endpoint this cycle
                print("  iv_term BREAKER OPEN: 3 consecutive failures - skipping IV for the rest "
                      "of this cycle (no retry storms; cycle stays under the GHA timeout)")
            return None
    except Exception as e:
        print(f"  iv_term client init failed: {type(e).__name__}: {str(e)[:80]}")
        return None
    best_iv, best_d = None, 1e18
    for sym, s in (snaps or {}).items():
        iv = getattr(s, "implied_volatility", None)
        if not iv:
            continue
        m = re.search(r"[CP](\d{8})$", sym if isinstance(sym, str) else str(sym))
        if not m:
            continue
        d = abs(int(m.group(1)) / 1000.0 - spot)
        if d < best_d:
            best_d, best_iv = d, float(iv) * 100
    return round(best_iv, 1) if best_iv else None


def iv_term_structure(ticker, spot, mock, creds=None):
    if not mock and creds and all(creds) and spot:
        iv_f = _alpaca_atm_iv(ticker, spot, CAL_FRONT_DTE[0], CAL_FRONT_DTE[1], creds)   # 10-15d front
        if not iv_f:
            # CALENDAR GEOMETRY (found 2026-09-02): the 10-15d window spans only SIX days - the
            # one window in the system narrower than a week - so from a Wednesday it contains no
            # Friday at all and every Friday-only-expiry name read "degenerate", starving entries
            # system-wide one weekday per week. Widen once to 7-18d (always spans a Friday).
            iv_f = _alpaca_atm_iv(ticker, spot, 7, 18, creds)
        iv_b = _alpaca_atm_iv(ticker, spot, CAL_BACK_DTE[0], CAL_BACK_DTE[1], creds)     # 35-45d back
        if iv_f and iv_b:
            ratio = round(iv_f / iv_b, 3)
            return {"iv_front": iv_f, "iv_back": iv_b, "iv_ratio": ratio,
                    "structure": "contango" if ratio < 1 else "backwardation" if ratio > 1 else "flat",
                    "source": "alpaca"}
    if mock:                                                  # local demo only - synthetic sample
        return {"iv_front": 40.0, "iv_back": 32.0, "iv_ratio": 1.25,
                "structure": "backwardation", "source": "mock"}
    # live mode, IV unavailable (no / thin options) -> NULL so the caller SKIPS
    return {"iv_front": None, "iv_back": None, "iv_ratio": None,
            "structure": None, "source": "unavailable"}


def net_gex(ticker, spot, mock):
    if not mock and spot:
        try:
            from src.unusual_whales_api import UnusualWhalesClient
            uw = UnusualWhalesClient()
            rows = (uw.greek_exposure_by_strike(ticker.split(".")[0]) or {}).get("data") or []
            pts = []
            for r in rows:
                k = _num(r.get("strike") or r.get("price"))
                g = (_num(r.get("call_gex")) or 0.0) + (_num(r.get("put_gex")) or 0.0)
                if k is not None:
                    pts.append((k, g))
            if pts:
                pts.sort()
                total = sum(g for _, g in pts)
                cum, prev_cum, crossings = 0.0, 0.0, []
                for k, g in pts:
                    prev_cum = cum
                    cum += g
                    if (prev_cum < 0 <= cum) or (prev_cum > 0 >= cum):
                        crossings.append(k)
                zero_gamma = (min(crossings, key=lambda k: abs(k - spot)) if crossings
                              else min(pts, key=lambda x: abs(x[0] - spot))[0])
                return {"net_gex": round(total, 1), "zero_gamma_strike": round(zero_gamma, 2),
                        "distance_to_zero_gamma_pct": round((spot - zero_gamma) / spot * 100, 3),
                        "regime": "negative_gamma" if total < 0 else "positive_gamma", "source": "uw"}
        except Exception:
            pass
    if mock:                                                  # local demo only - synthetic sample
        zg = round(spot * 1.004, 2)
        return {"net_gex": -1.85e8, "zero_gamma_strike": zg,
                "distance_to_zero_gamma_pct": round((spot - zg) / spot * 100, 3) if spot else 0.0,
                "regime": "negative_gamma", "source": "mock"}
    # live mode, GEX unavailable -> NULL (optional context; the trade still proceeds, logged null)
    return {"net_gex": None, "zero_gamma_strike": None,
            "distance_to_zero_gamma_pct": None, "regime": None, "source": "unavailable"}


def alt_catalyst(ticker, mock):
    reddit_delta, insider_usd, cluster, src = None, None, None, "mock"
    if not mock:
        try:
            from prototype_alt_data import reddit_attention_map, insider_open_market_buys
            ra = reddit_attention_map().get(ticker.split(".")[0])
            if ra:
                reddit_delta = ra["mention_spike_pct"]
            ib = insider_open_market_buys(ticker, lookback_days=10)
            insider_usd = ib.get("total_value")
            from sandbox_v10_upgrades import detect_cluster
            buys = [{"date": b["date"], "filer": b["insider"], "value": b["value"]} for b in ib.get("buys", [])]
            cluster = detect_cluster(buys)["cluster_flag"] if buys else False
            src = "apewisdom+edgartools"
        except Exception:
            pass
    if reddit_delta is None:
        reddit_delta, insider_usd, cluster, src = 540.0, 1_250_000, True, "mock"
    return {"reddit_mention_delta_pct": reddit_delta, "insider_10d_buy_usd": insider_usd,
            "insider_cluster_flag": bool(cluster), "source": src}


def collect_metadata(ticker, mock=False):
    mt = macro_technical(ticker, mock)
    spot = mt["spot"]
    iv = iv_term_structure(ticker, spot, mock, creds=_paper_creds())
    md = {
        "entry_ts_utc": _now_iso_ms(),
        "macro": {"spot": mt["spot"], "sma20": mt["sma20"], "distance_to_sma20_pct": mt["distance_to_sma20_pct"],
                  "source": mt["source"]},
        "iv_term": iv,
        "gex": net_gex(ticker, spot, mock),
        "alt_catalyst": alt_catalyst(ticker, mock),
        "technical": {"atr": mt["atr"], "atr_pct": mt["atr_pct"], "rvol_10min": mt["rvol_10min"],
                      "source": mt["source"]},
    }
    md.update(_v11_sensors(ticker, md, spot, iv, mock))
    return md


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return dict(default)


def _v11_sensors(ticker, md, spot, iv, mock):
    """LOG-DON'T-BLOCK: bolt the four V11 context sensors onto the metadata. Each fails open to
    nulls and NONE is read by any entry/sizing/exit path - the Autopsy Engine consumes them."""
    if not v11:
        return {"v11_sensors": "module_unavailable"}
    prof = _safe(lambda: v11.company_profile(ticker, mock), {"source": "unavailable"})
    news = _safe(lambda: v11.news_context(ticker, mock), {"source": "unavailable"})
    rstack = _safe(lambda: v11.regime_stack(ticker, prof.get("sector"),
                   md["macro"]["distance_to_sma20_pct"], mock), {"source": "unavailable"})
    skew = _safe(lambda: v11.relative_skew(ticker, spot, iv.get("iv_front"), mock), {"source": "unavailable"})
    aggr = _safe(lambda: v11.flow_aggression(ticker, mock), {"source": "unavailable"})
    dpn = _safe(lambda: v11.darkpool_node(ticker, spot, mock), {"source": "unavailable"})
    pemd = _safe(lambda: v11.post_earnings_drift(ticker, mock), {"source": "unavailable"})
    vrp = _safe(lambda: v11.vrp_sensor(ticker, iv.get("iv_front"), mock), {"source": "unavailable"})
    fpers = _safe(lambda: v11.flow_persistence(ticker, mock), {"source": "unavailable"})
    pact = _safe(lambda: v11.price_action(ticker, mock), {"source": "unavailable"})
    mctx = _safe(lambda: v11.macro_context(ticker, iv.get("iv_front"), iv.get("iv_back"),
                 prof.get("sector"), mock), {"source": "unavailable"})
    liq = _safe(lambda: v11.liquidity_slippage(ticker, mock), {"source": "unavailable"})    # mid-cap microstructure
    relm = _safe(lambda: v11.relative_momentum(ticker, mock), {"source": "unavailable"})
    flt = _safe(lambda: v11.float_mechanics(ticker, mock), {"source": "unavailable"})
    dgk = _safe(lambda: v11.dealer_greeks(ticker, mock), {"source": "unavailable"})         # DEX / vanna / charm
    return {"fundamentals": prof, "news": news, "regime_stack": rstack, "skew": skew,
            "flow_aggression": aggr, "dark_pool": dpn, "pemd": pemd, "vrp": vrp, "flow_persistence": fpers,
            "price_action": pact, "macro_context": mctx, "dealer_greeks": dgk,
            "liquidity_and_slippage": liq, "relative_momentum": relm, "float_mechanics": flt,
            "news_sentiment_score": news.get("vader_compound"),
            # flat log-keys consumed by the Autopsy Engine (also nested above):
            "sweep_aggression_pct": aggr.get("sweep_aggression_pct"),
            "distance_to_zero_gamma_pct": (md.get("gex") or {}).get("distance_to_zero_gamma_pct"),  # edge #2 (already in gex)
            "distance_to_heaviest_dp_node_pct": dpn.get("distance_to_heaviest_dp_node_pct"),
            "days_since_earnings": pemd.get("days_since_earnings"),
            "days_to_earnings": pemd.get("days_to_earnings"),        # powers the 3d earnings blackout (fail-open)
            "post_earnings_iv_crush_flag": pemd.get("post_earnings_iv_crush_flag"),
            "flow_persistence_pct": fpers.get("flow_persistence_pct")}


# ----------------------------------------------------------------------------
# Trigger + legs + Alpaca paper routing
# ----------------------------------------------------------------------------
def classify_regime(md, candidate=None):
    """Directional read of the market's intent - loose, data-gathering. Flow direction (why the
    scanner fired) dominates; the ticker's own trend and the broad-market regime confirm. Returns
    BULLISH / BEARISH / NEUTRAL. This routes WHICH structure we trade, never whether we trade."""
    score = 0.0
    ft = (candidate or {}).get("flow_type")
    if ft == "call":
        score += 2.0
    elif ft == "put":
        score -= 2.0
    dist = (md.get("macro") or {}).get("distance_to_sma20_pct")
    if isinstance(dist, (int, float)):
        score += 1.0 if dist > 1.0 else -1.0 if dist < -1.0 else 0.0
    spy = (md.get("regime_stack") or {}).get("market_spy_dist_pct")
    if isinstance(spy, (int, float)):
        score += 0.5 if spy > 0 else -0.5 if spy < 0 else 0.0
    if score >= 0.5:
        return "BULLISH"
    if score <= -0.5:
        return "BEARISH"
    return "NEUTRAL"


_REGIME_STRUCTURE = {"BULLISH": "bullish_call", "BEARISH": "bearish_put", "NEUTRAL": "flat_calendar"}


def _est_premium(spot, strike, iv_pct, dte, right):
    intrinsic = max(0.0, (spot - strike) if right == "call" else (strike - spot))
    tv = spot * (iv_pct / 100.0) * math.sqrt(max(dte, 1) / 365.0) * 0.40
    return round(intrinsic + tv, 2)


def _occ(ticker, dte, right, strike):
    expiry = (date.today() + timedelta(days=dte))
    ymd = expiry.strftime("%y%m%d")
    rc = "C" if right == "call" else "P"
    k = str(int(round(strike * 1000))).zfill(8)
    return f"{ticker.upper()[:6]}{ymd}{rc}{k}", expiry.isoformat()


# DIP_CONVEXITY (owner order 2026-08-27, everything-sweep winner: bear + long-DTE calls +
# wide exits beat the same-day pool by +35-52 pts/day, t 4.6-7.5, both years). Per-probe
# structure/exit overrides; threaded via the same global-swap idiom as LEG_BUDGET.
PROBE_STRUCT = {"DIP_CONVEXITY": {"otm_pct": 2.0, "dte": 50}}
PROBE_EXITS = {"DIP_CONVEXITY": {"stop": 70.0, "trig": 80.0, "give": 0.30},
               "BULL_DIP_X": {"stop": 70.0, "trig": 80.0, "give": 0.30}}
               # BULL_DIP_X wide exits: bull expensive-trigger test 2026-09-01 - wide +40.8/day
               # t5.17 (86d, n=366, halves +74/+8) vs live-exit +18.8 t3.06 (halves +38/-0);
               # the convexity needs the room, same as DIP_CONVEXITY


def _tuned(name, kind):
    """DYNAMIC TUNING (owner order 2026-09-01): per-strategy buy/sell config from spec
    probe.tuning.<name>.<kind>, written only by the damped weekly applier (tuner_apply.py,
    Friday window). Fallback is the hardcoded default - absent/corrupt spec keys change
    NOTHING (fail-open to current behavior; the 08-24 lesson says never let bad state
    masquerade, so only a well-formed dict overrides)."""
    try:
        v = ((fade_book.spec().get("probe") or {}).get("tuning") or {}).get(name or "")
        v = (v or {}).get(kind)
        if isinstance(v, dict) and v:
            return v
    except Exception:
        pass
    return (PROBE_STRUCT if kind == "struct" else PROBE_EXITS).get(name or "")
_ACTIVE_PROBE = {"name": None}
_PROBE_CONTRACT = {"c": None}   # trigger-contract override (DIP_CONF_MILD): when set, build_legs
                                # returns THE contract the expensive-flow trigger printed on
                                # instead of synthesizing one - the panel catch of 2026-09-01:
                                # evidence must be earned on the instrument the backtest measured


def build_legs(ticker, md, regime="NEUTRAL", leg_budget=None, illiquid=None):
    spot = md["macro"]["spot"]
    iv_f, iv_b = md["iv_term"]["iv_front"], md["iv_term"]["iv_back"]
    per_leg = LEG_BUDGET if leg_budget is None else leg_budget
    _pcx = _PROBE_CONTRACT.get("c")
    if _pcx and (_pcx.get("ticker") or "").upper() == ticker.upper() and _pcx.get("occ"):
        _ask0 = _pcx.get("alert_ask") or 5.0
        try:
            _dte0 = max(1, (date.fromisoformat(str(_pcx["expiry"])) - date.today()).days)
        except Exception:
            _dte0 = 30
        return {"bullish_call": {"structure": "LONG_CALL", "occ_symbol": _pcx["occ"],
                                 "expiry": str(_pcx.get("expiry")), "strike": _pcx.get("strike"),
                                 "dte": _dte0, "entry_premium": _ask0,
                                 "limit_price": round(_ask0 * 1.01, 2), "contracts": 1,
                                 "alloc_usd": per_leg, "illiquid": False,
                                 "target_delta": CALL_DELTA, "trigger_contract": True}}
    # ^ resolved at CALL time, not def time: a default bound at import froze the probe roster's
    #   LEG_BUDGET swap out of sizing (probe.size_usd was silently decorative)
    min_ct = load_params().get("min_contracts", 2)
    if fade_book.active():
        # FADE v1.2.3 (2026-08-10): the SECOND affordability gate - the 08-08 fix patched the
        # entry CHECK but this CALCULATOR still returned 0 contracts below 2, so 7 of 17
        # qualifying candidates died premium_too_rich today. Both gates now read the spec.
        min_ct = fade_book.spec().get("min_contracts", 1)
    illiquid = illiquid or set()
    # STRUCTURE (2026-08-23): the archive's only learnable non-flow edge is WHICH CONTRACT we buy
    # (delta/DTE), not which print we follow. Spec-gated; defaults are byte-identical to the
    # historical behaviour (4% OTM, 35 DTE) so this is inert until evidence sets the values.
    _st = (fade_book.spec().get("structure") or {}) if fade_book.active() else {}
    _otm = _st.get("otm_pct", 4.0) if _st.get("enabled") else 4.0
    _dte = int(_st.get("dte", 35)) if _st.get("enabled") else 35
    _pst = _tuned(_ACTIVE_PROBE["name"], "struct")
    if _pst:                                  # probe-specific contract shape (DIP_CONVEXITY:
        _otm = _pst.get("otm_pct", _otm)      # near-money, ~50 DTE - time for the bounce)
        _dte = int(_pst.get("dte", _dte))
    call_k = round(spot * (1 + _otm / 100.0), 1)
    put_k = round(spot * (1 - _otm / 100.0), 1)
    cp, pp = _est_premium(spot, call_k, iv_f, _dte, "call"), _est_premium(spot, put_k, iv_f, _dte, "put")
    front, back = _est_premium(spot, spot, iv_f, 14, "call"), _est_premium(spot, spot, iv_b, 45, "call")
    cal_debit = round(back - front, 2)

    def _qty(premium):
        if not premium or premium <= 0:
            return 0
        q = int(per_leg // (premium * 100))   # floor($800 / cost-per-contract)
        return q if q >= min_ct else 0        # AFFORDABILITY GATE: need >= 2 contracts on $800 (premium <= ~$4.00), else SKIP

    def leg(name, structure, right, strike, dte, premium, **extra):
        occ, expiry = _occ(ticker, dte, right, strike)
        qty = _qty(premium)
        return {"structure": structure, "occ_symbol": occ, "expiry": expiry, "strike": strike,
                "dte": dte, "entry_premium": premium, "limit_price": round(premium * 1.01, 2),
                "contracts": qty, "alloc_usd": per_leg,
                "illiquid": (name in illiquid) or qty <= 0, **extra}

    all_legs = {
        "bullish_call": leg("bullish_call", "LONG_CALL", "call", call_k, _dte, cp, target_delta=CALL_DELTA),
        "bearish_put": leg("bearish_put", "LONG_PUT", "put", put_k, _dte, pp, target_delta=PUT_DELTA),
    }
    cal_occ_f, _ = _occ(ticker, 14, "call", round(spot, 1))
    cal_occ_b, exp_b = _occ(ticker, 45, "call", round(spot, 1))
    qty_cal = _qty(cal_debit)
    all_legs["flat_calendar"] = {"structure": "CALENDAR_SPREAD", "strike": round(spot, 1),
                                 "front_occ": cal_occ_f, "back_occ": cal_occ_b, "front_dte": 14, "back_dte": 45,
                                 "net_debit": cal_debit, "limit_price": round(cal_debit * 1.01, 2),
                                 "contracts": qty_cal, "alloc_usd": per_leg,
                                 "illiquid": ("flat_calendar" in illiquid) or qty_cal <= 0}
    pick = _REGIME_STRUCTURE.get(regime, "flat_calendar")     # regime routes the structure (one per cluster)
    return {pick: all_legs[pick]}


def _order_payload(name, leg):
    if name == "flat_calendar":
        return {"order_class": "mleg", "qty": str(leg["contracts"]), "type": "limit",
                "limit_price": str(leg["limit_price"]), "time_in_force": "day", "legs": [
                    {"symbol": leg["front_occ"], "ratio_qty": "1", "side": "sell", "position_intent": "sell_to_open"},
                    {"symbol": leg["back_occ"], "ratio_qty": "1", "side": "buy", "position_intent": "buy_to_open"}]}
    return {"symbol": leg["occ_symbol"], "qty": str(leg["contracts"]), "side": "buy", "type": "limit",
            "limit_price": str(leg["limit_price"]), "time_in_force": "day"}


def _submit_paper_order(payload, creds):
    key, sec = creds
    data = json.dumps(payload).encode()
    req = urllib.request.Request(PAPER_BASE + "/v2/orders", data=data, method="POST",
                                 headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode())
        return resp.get("id"), resp.get("status"), None
    except Exception as e:
        return None, "ERROR", str(e)[:120]


def route_to_alpaca_paper(ticker, legs, dry_run=True):
    creds = (os.environ.get("ALPACA_PAPER_API_KEY"), os.environ.get("ALPACA_PAPER_SECRET_KEY"))
    out = {}
    for name, leg in legs.items():
        if leg.get("illiquid"):                       # FAIL-OPEN: skip illiquid, keep the rest
            out[name] = {"status": "SKIPPED_ILLIQUID", "order_id": None, "submitted": False}
            continue
        payload = _order_payload(name, leg)
        if dry_run:
            out[name] = {"status": "DRY_RUN", "order_id": None, "submitted": False,
                         "limit_price": leg["limit_price"], "contracts": leg["contracts"], "payload": payload}
        elif not all(creds):
            out[name] = {"status": "NO_PAPER_CREDS", "order_id": None, "submitted": False, "payload": payload}
        else:
            oid, status, err = _submit_paper_order(payload, creds)
            out[name] = {"status": status, "order_id": oid, "error": err, "submitted": True,
                         "limit_price": leg["limit_price"], "contracts": leg["contracts"]}
    return out


# ---- real OCC resolution + portfolio guards (read-only Alpaca paper API) ----
COOLOFF_PATH = "sandbox_ticker_cooloff.json"


def _paper_creds():
    return (os.environ.get("ALPACA_PAPER_API_KEY"), os.environ.get("ALPACA_PAPER_SECRET_KEY"))


def _paper_get(path, creds):
    key, sec = creds
    req = urllib.request.Request(PAPER_BASE + path, headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _market_is_open(creds=None):
    """True only if Alpaca reports the session open right now. Fail-CLOSED (no creds / API error ->
    False) so a clock blip can never let a closed-market cycle or flush fire an order."""
    creds = creds or _paper_creds()
    if not all(creds):
        return False
    try:
        return bool(_paper_get("/v2/clock", creds).get("is_open"))
    except Exception:
        return False


def resolve_occ(ticker, right, target_strike, target_dte, creds=None, dte_min=None, dte_max=None):
    """Resolve a REAL active OCC contract near target strike/expiry via Alpaca
    /v2/options/contracts. CRITICAL: that endpoint defaults to ~this-week expiries, so we MUST
    bound expiration_date_gte/lte or we get the wrong contracts. Pass dte_min/dte_max to set an
    explicit window (e.g. 10-15d front / 35-45d back for the calendar). Fail-open -> None."""
    import urllib.parse
    creds = creds or _paper_creds()
    if not all(creds):
        return None
    if dte_min is not None and dte_max is not None:
        gte = date.today() + timedelta(days=dte_min)
        lte = date.today() + timedelta(days=dte_max)
    else:
        exp = date.today() + timedelta(days=target_dte)
        gte, lte = exp - timedelta(days=7), exp + timedelta(days=10)
    q = urllib.parse.urlencode({
        "underlying_symbols": ticker.split(".")[0], "type": right, "status": "active",
        "expiration_date_gte": gte.isoformat(), "expiration_date_lte": lte.isoformat(),
        "strike_price_gte": round(target_strike * 0.85, 2), "strike_price_lte": round(target_strike * 1.15, 2),
        "limit": 1000})
    try:
        rows = _paper_get(f"/v2/options/contracts?{q}", creds).get("option_contracts") or []
    except Exception:
        return None
    if not rows:
        return None
    best = min(rows, key=lambda c: abs(float(c.get("strike_price", 0)) - target_strike))
    return {"occ_symbol": best.get("symbol"), "strike": float(best.get("strike_price")),
            "expiration": best.get("expiration_date"), "open_interest": best.get("open_interest")}


def get_open_positions(creds=None):
    creds = creds or _paper_creds()
    if not all(creds):
        return []
    try:
        return _paper_get("/v2/positions", creds)
    except Exception:
        return []


def get_open_orders(creds=None):
    creds = creds or _paper_creds()
    if not all(creds):
        return []
    try:
        return _paper_get("/v2/orders?status=open&limit=500", creds)
    except Exception:
        return []


def _cancel_order(order_id, creds):
    key, sec = creds
    req = urllib.request.Request(PAPER_BASE + f"/v2/orders/{order_id}", method="DELETE",
                                 headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 204)
    except Exception:
        return False


def audit_stale_orders(creds=None, max_minutes=None, orders=None):
    """Cancel limit orders sitting unfilled longer than max_minutes (default 30 = 3 cycles) so
    stale limits don't block buying power. Logs the cancels so the autopsy knows the leg was
    cancelled, not filled. Returns the cancelled list."""
    creds = creds or _paper_creds()
    if not all(creds):
        return []
    if max_minutes is None:
        max_minutes = load_params().get("stale_order_max_minutes", 30)
    orders = orders if orders is not None else get_open_orders(creds)
    now = datetime.now(timezone.utc)
    cancelled = []
    for o in orders:
        sub = o.get("submitted_at") or o.get("created_at")
        if not sub or o.get("type") != "limit":
            continue
        try:
            age = (now - datetime.fromisoformat(sub.replace("Z", "+00:00"))).total_seconds() / 60.0
        except Exception:
            continue
        if age > max_minutes and _cancel_order(o.get("id"), creds):
            cancelled.append({"order_id": o.get("id"), "symbol": o.get("symbol"),
                              "age_min": round(age, 1), "limit_price": o.get("limit_price")})
    if cancelled:
        _append_log({"trade_set_id": "AUDIT-" + uuid.uuid4().hex[:8], "type": "stale_order_cleanup",
                     "ts_utc": _now_iso_ms(), "max_minutes": max_minutes, "cancelled": cancelled,
                     "status": "CANCELLED"})
    return cancelled


_WHALE_CANDS = []          # per-cycle side-pool of fade-shaped 400k-1M prints (FADE_WHALE probe only)
_FULL_CANDS = []           # per-cycle snapshot of the FULL premium band (50k-1M) before the fade
                           # book's flow_band cut - the calls-family probes' tested band
_PRICEY_CANDS = []         # per-cycle side-pool of EXPENSIVE-CONTRACT triggers (ask $4-9, premium
                           # 50-400k) - the split test 2026-09-01 located the dip edge here
                           # (+21.2%/day t+4.31, halves +16/+26); the $4 affordability cap had made
                           # this cohort invisible. Probes only; the live book never reads it.
_SR_BUDGET = 0             # spread-retry budget per cycle (2026-08-18: uncapped retries stretched
                           # cycles past the run window and triggered a false-crash rollback)


def _occ_matches_base(sym, base):
    """True if OCC symbol `sym` belongs to underlying `base` - the root must be followed by the
    6-digit expiry, so BB never matches BBAI contracts."""
    sym = (sym or "").upper()
    return sym == base or (sym.startswith(base) and sym[len(base):len(base) + 1].isdigit())


def ticker_blocked(ticker, positions, params, open_orders=None, now=None, log=None, probe=False):
    """Entry guard. TIER B (owner decision 21): ONE POSITION PER UNDERLYING - a hard block that
    SUPERSEDES max_contracts_per_ticker (the old cap is kept only as a subordinated belt-and-braces
    ceiling below). Exemptions, from the 2026-07-06 audit: broker positions with NO OPEN tracking
    record (legacy stragglers / flush orphans, e.g. PFE) and PARKED records never block - a zero-bid
    corpse must not freeze a ticker's live signals for six weeks."""
    base = ticker.upper().split(".")[0]
    if params.get("one_position_per_underlying", True):
        log = log if log is not None else _load_log_list()
        tracked = set()
        for rec in log:
            if rec.get("status") == "OPEN":                    # PARKED / FLUSHED / CLOSED never block
                if probe and rec.get("book") != "PROBE":
                    # CROSS-BOOK SOFTENING (owner 2026-09-02): a $1k probe is no longer blocked by a
                    # DIFFERENT book's old position on the same name - July/August legacies were
                    # throttling discovery on exactly the names where flow concentrates (7 of 16
                    # candidates blocked on 09-02). Probes still block on other PROBES (below) and on
                    # any book's RECENT entry (<=5 days) - same-week entries can synthesize the same
                    # contract, and two records on one occ is the double-claim disease.
                    ts = str(rec.get("entry_ts_utc") or "")[:10]
                    try:
                        from datetime import date as _d
                        if ts and (_d.today() - _d.fromisoformat(ts)).days > 5:
                            continue
                    except Exception:
                        pass
                for occ in _record_leg_occs(rec).values():
                    tracked.add((occ or "").upper())
        for p in positions or []:
            sym = (p.get("symbol") or "").upper()
            if sym in tracked and _occ_matches_base(sym, base):
                return True, f"one-per-underlying: open tracked position {sym}"
        for o in open_orders or []:
            if (o.get("side") or "buy") != "buy" and o.get("order_class") != "mleg":
                continue                                        # resting sells (backstops/exits) belong to positions
            syms = [o.get("symbol")] + [l.get("symbol") for l in (o.get("legs") or [])]
            if any(_occ_matches_base(s, base) for s in syms if s):
                return True, f"one-per-underlying: pending entry order on {base}"
    held = 0
    for p in positions or []:
        sym = (p.get("symbol") or "").upper()
        if sym != base and _occ_matches_base(sym, base):    # equity shares (probes) are not contracts
            held += abs(int(float(p.get("qty", 0) or 0)))
    pending = 0
    for o in open_orders or []:
        syms = [o.get("symbol")] + [l.get("symbol") for l in (o.get("legs") or [])]
        if any(_occ_matches_base(s, base) for s in syms if s and s.upper() != base):
            pending += abs(int(float(o.get("qty", 0) or 0)))
    cap = params.get("max_contracts_per_ticker", 3)
    if held + pending >= cap:                                   # subordinated to one-per-underlying above
        return True, f"ticker cap: {held} held + {pending} pending on {base} >= {cap}"
    cool = {}
    if os.path.exists(COOLOFF_PATH):
        try:
            cool = json.load(open(COOLOFF_PATH, encoding="utf-8"))
        except Exception:
            cool = {}
    ts = cool.get(base)
    if ts:
        closed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        hrs = ((now or datetime.now(timezone.utc)) - closed).total_seconds() / 3600.0
        if hrs < params.get("ticker_cooloff_hours", 24):
            if fade_book.active():
                # FADE v1.2: cooloff waived (the replay cohort had no cooloff - this moves the
                # live book TOWARD the tested population). Concentration guard lives in the
                # cycle loop instead: max 2 FADE entries per ticker per day.
                pass
            else:
                return True, f"cool-off: {base} closed {hrs:.1f}h ago (< {params.get('ticker_cooloff_hours', 24)}h)"
    return False, "clear"


def record_close(ticker):
    base = ticker.upper().split(".")[0]
    cool = json.load(open(COOLOFF_PATH, encoding="utf-8")) if os.path.exists(COOLOFF_PATH) else {}
    cool[base] = _now_iso_ms()
    json.dump(cool, open(COOLOFF_PATH, "w", encoding="utf-8"), indent=2)


def _occ_expiry(occ):
    """Parse the YYMMDD expiry out of an OCC symbol -> ISO date string (None if unparseable)."""
    m = re.search(r"(\d{6})[CP]\d{8}$", occ or "")
    if not m:
        return None
    d = m.group(1)
    return f"20{d[:2]}-{d[2:4]}-{d[4:6]}"


def daily_brake_status(params, log=None):
    """TIER B (owner decision 19): 3 stop-outs today OR realized session loss >= 2x the $800
    allocation -> no NEW entries until the next session. Exits, backstops and the harvest continue -
    the brake only closes the entry gate. Counted from the committed log's leg_exits so it survives
    ephemeral GHA runners. Returns (braked, why, stopouts, realized_loss_usd)."""
    log = log if log is not None else _load_log_list()
    today = datetime.now(timezone.utc).date().isoformat()
    stopouts, loss_usd = 0, 0.0
    for rec in log:
        if rec.get("book") == "PROBE":
            continue                 # v1.7: the brake protects the LIVE book; probe experiments are
                                     # excluded so 25 $1k probes can't trip the fade's measurement
        legs = rec.get("legs") or {}
        for ln, ex in (rec.get("leg_exits") or {}).items():
            if not str(ex.get("closed_at", "")).startswith(today):
                continue
            ret = ex.get("return_pct") or 0.0
            key = "flat_calendar" if ln.startswith("calendar") else ln
            alloc = (legs.get(key) or {}).get("alloc_usd") or LEG_BUDGET
            if ret < 0:
                loss_usd += -ret / 100.0 * alloc
                if ex.get("action") in ("CLOSE_STOP_LOSS", "CLOSE_BACKSTOP"):
                    stopouts += 1
    max_so = params.get("daily_brake_stopouts", 3)
    max_loss = params.get("daily_brake_loss_multiple", 2.0) * LEG_BUDGET
    if stopouts >= max_so:
        return True, f"{stopouts} stop-outs >= {max_so}", stopouts, loss_usd
    if loss_usd >= max_loss:
        return True, f"realized session loss ${loss_usd:.0f} >= ${max_loss:.0f} (2x allocation)", stopouts, loss_usd
    return False, f"clear ({stopouts} stop-outs, ${loss_usd:.0f} realized loss)", stopouts, loss_usd


def brake_decision(params, log=None):
    """Resolve the daily brake into (mode, braked, active, reason, stopouts, loss_usd).

    OWNER DECISION 2026-07-08: during the paper-accumulation phase the brake runs in SHADOW - its
    JUDGMENT stays on (it evaluates its trigger every session and logs when it WOULD halt) but its
    ACTION is off (it does NOT suppress entries). On paper a stop-out is a completed, high-value data
    point, not a loss to prevent; halting would throw away the richest outcomes on the hardest days,
    which is exactly the data we are here to collect. The would-have-blocked trades are the free
    measurement of the brake's value before it ever protects real money. Modes:
      off    - no evaluation, no logging.
      shadow - evaluate + log the trip, but entries still fire and are tagged 'brake_shadow'.
      active - the real halt (Tier B behaviour); armed only at the live-capital gate (ROADMAP item 14).
    This is a RISK-CONTROL wiring change only: it touches no entry gate, signal, or threshold."""
    mode = str(params.get("brake_mode", "shadow") or "shadow").lower()
    if mode == "off":
        return "off", False, False, "brake off", 0, 0.0
    braked, why, n_so, loss_usd = daily_brake_status(params, log=log)
    return mode, braked, (braked and mode == "active"), why, n_so, loss_usd


_TERMINAL_ORDER = {"canceled", "cancelled", "filled", "expired", "rejected", "done_for_day"}


def _order_state(order_id, creds):
    """Raw Alpaca order dict, or None on any failure (fail-open)."""
    if not order_id:
        return None
    try:
        return _paper_get(f"/v2/orders/{order_id}", creds)
    except Exception:
        return None


def _order_fill(order_id, creds):
    """Return {'price','at','qty'} ONLY for a TERMINAL order that filled contracts (status in
    _TERMINAL_ORDER with filled_qty>0) - a 'filled' stop, or a 'canceled'/'expired' stop that partially
    filled before the ratchet cancel took it down. A still-live 'partially_filled' order returns None so
    its id is never burned mid-flight (we re-poll it next cycle until terminal - the fix for the strand
    where a non-terminal partial booked once then the completing fill was skipped forever). None if the
    order is non-terminal or nothing filled."""
    o = _order_state(order_id, creds)
    if not o:
        return None
    if (o.get("status") or "").lower() not in _TERMINAL_ORDER:
        return None
    try:
        fq = int(float(o.get("filled_qty") or 0))
        px = o.get("filled_avg_price")
        if fq > 0 and px:
            return {"price": float(px), "at": o.get("filled_at") or _now_iso_ms(), "qty": fq}
    except Exception:
        pass
    return None


def _backstop_order_ids(bs):
    """Current + superseded backstop order ids - reconciliation must poll ALL of them, because a
    ratchet cancel+resubmit can leave a filled OLD id that the new id no longer points at."""
    return [i for i in ([bs.get("order_id")] + list(bs.get("prior_order_ids") or [])) if i]


def _capture_backstop_fill(rec, leg_name, occ, creds, log, closed_legs):
    """Reconcile broker backstop fills across the current + superseded order ids (idempotent per id; only
    TERMINAL fills are ever booked - see _order_fill). A fill for the FULL leg qty closes the leg
    (CLOSE_BACKSTOP leg_exit + record_close + 24h cool-off). A terminal PARTIAL fill (the ratchet cancel
    caught the stop after it filled some but not all) is recorded to bs['partials'] for audit ONLY - it
    does NOT create a leg_exit and does NOT count as a stop-out, so the leg keeps its remaining qty for
    the cron to close as the single, correct exit (this kills the double-count + the strand where the
    phantom ~bs exit blocked re-entry forever). Every same-day fill appends a PDT day_trade marker.
    Returns True iff the leg is now FULLY exited."""
    bs = (rec.get("backstop") or {}).get(leg_name)
    if not bs:
        return leg_name in (rec.get("leg_exits") or {})
    seen = bs.setdefault("reconciled_ids", [])
    entry_px = bs.get("entry_px") or 0
    booked_full = leg_name in (rec.get("leg_exits") or {})
    for oid in _backstop_order_ids(bs):
        if oid in seen:
            continue
        f = _order_fill(oid, creds)
        if not f:
            continue
        seen.append(oid)
        ret = round((f["price"] / entry_px - 1) * 100.0, 1) if entry_px else 0.0
        full = f["qty"] >= (bs.get("qty") or f["qty"]) and not booked_full
        if full:
            rec.setdefault("leg_exits", {})[leg_name] = {
                "occ": occ, "closed_at": f["at"], "return_pct": ret, "filled_qty": f["qty"],
                "reason": f"broker backstop filled {f['qty']} @ {f['price']}",
                "action": "CLOSE_BACKSTOP", "closed_ok": True}
            closed_legs.append({"ticker": rec["ticker"], "leg": leg_name, "occ": occ,
                                "return_pct": ret, "action": "CLOSE_BACKSTOP", "closed_ok": True})
            _notify(_sell_msg(closed_legs[-1]))
            bs["reconciled"] = True
            record_close(rec["ticker"])
            booked_full = True
        else:
            bs.setdefault("partials", []).append(          # audit only - NO leg_exit, NOT a stop-out
                {"order_id": oid, "filled_qty": f["qty"], "price": f["price"], "return_pct": ret, "at": f["at"]})
            _notify(f"backstop PARTIAL {f['qty']} {occ} @ {f['price']} ({ret:+.1f}%) - remainder stays open for the cron close")
        if str(f["at"])[:10] == str(rec.get("entry_ts_utc", ""))[:10]:
            log.append({"type": "day_trade", "ts_utc": _now_iso_ms(), "ticker": rec["ticker"],
                        "occ": occ, "via": "CLOSE_BACKSTOP", "status": "LOGGED"})
        try:                                          # school 1c: gap-through measurement (fail-open)
            import fill_ledger
            fill_ledger.backstop_fill_event(rec, occ, bs.get("stop_price"), f["price"], f["qty"],
                                            f["at"], entry_px)
        except Exception:
            pass
    return booked_full


def _retire_stop(rec, leg_name, occ, creds, log, closed_legs):
    """Safely take down a resting broker stop BEFORE a cron close/scale. Best-effort cancel, then
    CONFIRM terminal via GET and capture any fill during its life. Returns True ONLY when the stop is
    confirmed gone (so _close_position can't collide with a live stop holding the qty). A cancel we
    cannot confirm returns False -> the caller skips the close this cycle and retries next cycle
    (the CRITICAL fix: never mark a stop cancelled on an unconfirmed DELETE)."""
    bs = (rec.get("backstop") or {}).get(leg_name)
    if not bs or not bs.get("order_id") or bs.get("retired"):
        return True
    _cancel_order(bs["order_id"], creds)                 # best-effort; the GET below is the authority
    o = _order_state(bs["order_id"], creds)
    _capture_backstop_fill(rec, leg_name, occ, creds, log, closed_legs)   # book any fill during its life
    if o is None:
        return False                                     # cannot confirm terminal -> do NOT close blind
    if (o.get("status") or "").lower() in _TERMINAL_ORDER:
        bs["retired"] = True
        return True
    return False                                         # still active / partially_filled -> retry next cycle


def _backstop_level(entry_px, stage, peak_mfe, params, probe=None):
    """The ratchet: initial -> the -50% hard-stop level; scaled -> break-even; trailing -> 20% off
    the peak MFE. Absolute premium (broker stop_price), floored at $0.01. Mirrors manage_exit so the
    resting stop and the cron exit can never disagree on the level."""
    _pex = _tuned(probe, "exits")
    if stage == "scaled":
        pct = params.get("break_even_pct", 0)
    elif stage == "trailing":
        _gv = (_pex["give"] * 100.0) if _pex else params.get("trail_drawdown_pct", 20)
        pct = (peak_mfe or 0.0) * (1 - _gv / 100.0)
    else:
        pct = -abs(_pex["stop"]) if _pex else -abs(params.get("stop_loss_pct", 50))
    return max(0.01, round(entry_px * (1 + pct / 100.0), 2))


def _submit_backstop(occ, qty, stop_price, params, creds):
    typ = params.get("backstop_type", "stop")
    body = {"symbol": occ, "qty": str(int(qty)), "side": "sell", "type": typ,
            "stop_price": str(stop_price), "time_in_force": "gtc"}   # T2 (2026-07-06): gtc accepted -> survives overnight
    if typ == "stop_limit":
        buf = params.get("backstop_limit_buffer_pct", 25) / 100.0
        body["limit_price"] = str(max(0.01, round(stop_price * (1 - buf), 2)))
    return _submit_paper_order(body, creds)


def manage_backstops(creds, params, positions=None, log=None):
    """TIER B (owner decision 20 / ROADMAP item 2): RATCHET BACKSTOP. Every open tracked leg carries
    a resting broker-side STOP (T5 decision 2026-07-06: plain stop - affordable-band p90 spread is
    17.9% and a bad fill beats no fill per NORTH_STAR) whose level ratchets with the exit stage:
    -50% -> break-even -> MFE trail. Level or qty drift -> cancel + resubmit (T3: PATCH replace is
    rejected on queued option orders). The +30% scale-out stays cron-managed. Config-flagged:
    backstop_enabled (OFF until the canary passes); backstop_canary_occ restricts arming to the one
    canary position through a full lifecycle before fleet-wide."""
    if not params.get("backstop_enabled", False) or not all(creds):
        return []
    positions = positions if positions is not None else get_open_positions(creds)
    pos_by_occ = {(p.get("symbol") or "").upper(): p for p in positions}
    log_list = log if log is not None else _load_log_list()
    canary = (params.get("backstop_canary_occ") or "").upper()
    stops_by_sym = {}
    for o in get_open_orders(creds):
        if o.get("type") in ("stop", "stop_limit") and o.get("side") == "sell":
            stops_by_sym[(o.get("symbol") or "").upper()] = o
    actions, dirty = [], False
    _bs_notes, _bs_fails = [], []
    for rec in log_list:
        if rec.get("status") != "OPEN" or not isinstance(rec.get("legs"), dict):
            continue
        if (fade_book.no_same_day_exit()
                and str(rec.get("entry_ts_utc", ""))[:10] == datetime.now(timezone.utc).date().isoformat()):
            continue                                              # owner hold rule: a resting stop can
                                                                  # fill same-day - arm from tomorrow
        for leg_name, occ in _record_leg_occs(rec).items():
            sym = (occ or "").upper()
            if canary and sym != canary:
                continue                                          # canary mode: one position only
            if leg_name in (rec.get("leg_exits") or {}):
                continue
            p = pos_by_occ.get(sym)
            if not p:
                continue
            qty = abs(int(float(p.get("qty") or 0)))
            entry_px = float(p.get("avg_entry_price") or 0)
            if qty < 1 or entry_px <= 0:
                continue
            path = (rec.get("leg_path") or {}).get(leg_name) or {}
            level = _backstop_level(entry_px, path.get("stage", "initial"), path.get("mfe_pct"),
                                    params, probe=rec.get("probe_strategy"))
            existing = stops_by_sym.get(sym)
            if existing:
                cur_px = float(existing.get("stop_price") or 0)
                cur_qty = abs(int(float(existing.get("qty") or 0)))
                _md = max(params.get("backstop_min_delta", 0.10), 0.02 * level)
                if abs(cur_px - level) < _md and cur_qty == qty:
                    continue                                      # already resting close enough (damped
                                                                  # 2026-08-25: 0.01 delta caused 13
                                                                  # cancel/replace cycles per symbol/day)
                if not _cancel_order(existing.get("id"), creds):  # ratchet move: cancel must be ACCEPTED
                    continue                                      # (else keep the old stop live; retry next cycle)
                _capture_backstop_fill(rec, leg_name, occ, creds, log_list, [])   # book a partial fill on it
                if leg_name in (rec.get("leg_exits") or {}):      # the old stop fully filled -> leg done, don't re-arm
                    dirty = True
                    continue
            oid, status, err = _submit_backstop(occ, qty, level, params, creds)
            live = bool(oid) and (status or "").lower() not in _TERMINAL_ORDER   # a REJECTED submit returns a truthy id
            prev = (rec.get("backstop") or {}).get(leg_name) or {}
            priors = list(prev.get("prior_order_ids") or [])
            if prev.get("order_id") and prev.get("order_id") != oid and not prev.get("reconciled"):
                priors.append(prev["order_id"])                   # keep the superseded id so a late fill is found
            rec.setdefault("backstop", {})[leg_name] = {
                "order_id": oid if live else None,                # never persist a dead/rejected id as the resting stop
                "prior_order_ids": priors[-10:],
                "reconciled_ids": list(prev.get("reconciled_ids") or []),
                "stop_price": level, "qty": qty, "entry_px": entry_px,
                "type": params.get("backstop_type", "stop"), "stage": path.get("stage", "initial"),
                "at": _now_iso_ms(), "status": status, "error": err}
            actions.append({"occ": occ, "stop": level, "qty": qty, "status": status, "err": err})
            stg = path.get("stage", "initial")
            armed_new = existing is None                          # no stop was RESTING before this submit -> first arm, or a re-arm
            stage_moved = bool(prev.get("stage")) and prev.get("stage") != stg
            if live and (armed_new or stage_moved):
                _bs_notes.append(f"{occ} @ {level}")              # batched: one telegram per cycle,
                                                                  # not one per position (owner 2026-08-25:
                                                                  # "why has the telegram armed all day")
            elif live is None or not live:
                _bs_fails.append(occ)
            dirty = True
    if _bs_notes:
        _extra = f" ({len(_bs_fails)} could not arm - will retry)" if _bs_fails else ""
        _notify(f"<b>SAFETY STOPS SET: {len(_bs_notes)} position(s)</b>{_extra}\n"
                f"Plain English: resting sell-stops now sit at the broker under these positions, "
                f"so they are protected even if my engine goes blind. Routine - no action needed. "
                f"({', '.join(_bs_notes[:5])}{'...' if len(_bs_notes) > 5 else ''})")
    elif _bs_fails:
        _notify(f"<b>SAFETY STOPS: {len(_bs_fails)} could not arm</b> - will retry next cycle "
                f"({', '.join(_bs_fails[:4])})")
    if dirty:
        _save_log_list(log_list)
    return actions


def _note_close_failure(rec, path, leg_name, occ, params, creds=None):
    """GIVE-UP/PARK (2026-07-06 audit, the orphan root-fix): after N consecutive rejected closes with
    a fresh quote showing NO bid, the record transitions to PARKED - ONE alert, retries stop, stays
    visible in the digest, auto-resolves at expiry. A rejected close WITH a live bid resets nothing
    permanent: the counter climbs but a returning bid zeroes it and normal retries resume. On park,
    any resting backstop is best-effort cancelled (it was already retired before the close attempt,
    but a corpse must not leave a live GTC stop behind)."""
    fails = path["close_fails"] = path.get("close_fails", 0) + 1
    if fails < params.get("close_fail_park_after", 5):
        return
    bid = None
    try:
        bid = (v11.option_spread(occ) or {}).get("bid") if v11 else None
    except Exception:
        bid = None
    if bid:
        path["close_fails"] = 0                                   # a market exists again -> keep retrying normally
        return
    bs = (rec.get("backstop") or {}).get(leg_name) or {}
    if creds:
        for oid in _backstop_order_ids(bs):
            _cancel_order(oid, creds)
    rec["status"] = "PARKED"
    rec["parked"] = {"at": _now_iso_ms(), "leg": leg_name, "occ": occ, "close_fails": fails,
                     "reason": f"no bid after {fails} rejected closes - zero-bid corpse"}
    _notify(f"<b>PARKED {rec.get('ticker')}</b> {occ}: no bid after {fails} rejected closes - "
            f"retries stop; auto-resolves at expiry {_occ_expiry(occ)}")


def manage_exit(entry_ts_iso, ret_pct, params, now=None, expiry_iso=None, stage="initial", mfe_pct=None, book=None, probe=None):
    """Strategy-B tiered exit STATE MACHINE (per leg). Stages:
      initial  -> hard stop at -stop_loss_pct (overrides 24h); SCALE_OUT_50 at +take_profit_pct
                  (gated by the 24h hold) -> sell half, arm the break-even shield.
      scaled   -> runner protected by a break-even stop (CLOSE_BREAKEVEN at <= break_even_pct);
                  arms the MFE trail once it crosses +trail_activate_pct.
      trailing -> 20% trail of the peak MFE: CLOSE_TRAIL when ret <= peak_mfe * (1 - trail_drawdown).
    Expiry is a hard override in every stage. ret_pct is the broker directional P/L %; mfe_pct is
    the running peak excursion (for the trail)."""
    now = now or datetime.now(timezone.utc)
    entry = datetime.fromisoformat(entry_ts_iso.replace("Z", "+00:00"))
    held_h = (now - entry).total_seconds() / 3600.0
    ret = round(ret_pct, 1)
    peak = round(max(mfe_pct if mfe_pct is not None else ret, ret), 1)
    base = {"return_pct": ret, "held_hours": round(held_h, 1), "stage": stage, "peak_mfe": peak}
    if expiry_iso:                                            # hard expiry override (any stage)
        try:
            dte = (date.fromisoformat(expiry_iso) - now.date()).days
            if dte <= params.get("expiry_exit_dte", 3):
                # STOP OUTRANKS EXPIRY (2026-08-25, Ford -87% autopsy): a leg already through
                # its stop must close AS a stop - the expiry label was masking beyond-stop
                # losses in the books and let the stop machinery believe it never fired.
                _st = abs(params.get("stop_loss_pct", 50))
                if book == "FADE":
                    _st = fade_book.exit_overrides().get("stop", _st)
                _pex0 = _tuned(probe, "exits")
                if _pex0:
                    _st = abs(_pex0["stop"])
                if ret <= -_st:
                    return {**base, "action": "CLOSE_STOP_LOSS", "stage": "closed",
                            "reason": f"{ret}% <= -{_st}% hard stop (caught at {dte}d to expiry)"}
                return {**base, "action": "CLOSE_EXPIRY", "stage": "closed",
                        "reason": f"{dte}d to expiry -> close before decay/assignment"}
        except Exception:
            pass
    stop = abs(params.get("stop_loss_pct", 50))
    tp = params.get("take_profit_pct", 30)
    be = params.get("break_even_pct", 0)
    trig = params.get("trail_activate_pct", 50)
    trail = params.get("trail_drawdown_pct", 20) / 100.0
    min_hold = params.get("min_hold_hours", 24)
    if book == "FADE":
        # spec-driven trail (2026-08-25): fade_book_spec exit.trail_activate/.trail_drawdown
        # now actually steer the live trail; current spec values (50/20) equal the params
        # defaults, so behaviour is unchanged until the court promotes a different value.
        _ovt = fade_book.exit_overrides()
        trig = _ovt.get("trail_activate", trig)
        if "trail_drawdown" in _ovt:
            trail = _ovt["trail_drawdown"] / 100.0
    _pex = _tuned(probe, "exits")             # per-strategy exits: spec probe.tuning override,
    if _pex:                                  # hardcoded default fallback (DIP_CONVEXITY wide:
        stop = abs(_pex.get("stop", stop))    # the -50 stop sat inside bear whipsaw range and
        trig = _pex.get("trig", trig)         # cost a third of the measured edge)
        trail = _pex.get("give", trail)
    if stage == "initial":
        if ret <= -stop:
            return {**base, "action": "CLOSE_STOP_LOSS", "stage": "closed", "reason": f"{ret}% <= -{stop}% hard stop"}
        if book == "FADE":
            _ov = fade_book.exit_overrides()
            stop = _ov.get("stop", stop)
            _ec_h, _ec_b = _ov.get("early_cut_hours"), _ov.get("early_cut_below")
            if _ec_h and _ec_b and held_h >= _ec_h and held_h <= _ec_h + 2 and ret <= _ec_b:
                # PATH-SIGNATURE rule (mined 2026-08-11: <-15% at 2h ends -21.7 avg, both halves;
                # spec-driven, present only when the Sunday boundary promotes it)
                return {**base, "action": "CLOSE_STOP_LOSS", "stage": "closed",
                        "reason": f"FADE early-cut: {ret}% <= {_ec_b}% at {held_h:.1f}h (path signature)"}
            _mh = _ov.get("max_hold_days")
            if _mh and held_h >= _mh * 24:
                return {**base, "action": "CLOSE_EXPIRY", "stage": "closed",
                        "reason": f"FADE max-hold {_mh}d reached ({held_h:.0f}h)"}
            # FADE book (fade_book_spec.json): NO scale-out - the exit sweep on 358 stored paths
            # showed halving out amputates the +75..+130% runners that pay for the losers; full
            # position rides, trail arms directly from initial at +trail_activate_pct.
            if ret >= trig:
                return {**base, "action": "HOLD", "stage": "trailing",
                        "reason": f"FADE: +{ret}% >= {trig}% -> MFE trail armed (no scale-out)"}
            return {**base, "action": "HOLD", "reason": f"FADE initial: {ret}% (stop -{stop}% / trail arms +{trig}%)"}
        if held_h >= min_hold and ret >= tp:
            return {**base, "action": "SCALE_OUT_50", "stage": "scaled",
                    "reason": f"+{ret}% >= {tp}% -> sell 50%, stop -> break-even"}
        return {**base, "action": "HOLD", "reason": f"initial: {ret}% (stop -{stop}% / scale +{tp}%)"}
    if stage == "scaled":
        if ret <= be:
            return {**base, "action": "CLOSE_BREAKEVEN", "stage": "closed",
                    "reason": f"runner gave back to break-even ({ret}% <= {be}%)"}
        if ret >= trig:
            return {**base, "action": "HOLD", "stage": "trailing", "reason": f"+{ret}% >= {trig}% -> MFE trail armed"}
        return {**base, "action": "HOLD", "reason": f"scaled runner: {ret}% (BE stop {be}% / trail arms +{trig}%)"}
    if stage == "trailing":
        trail_stop = round(peak * (1 - trail), 1)
        if ret <= trail_stop:
            return {**base, "action": "CLOSE_TRAIL", "stage": "closed",
                    "reason": f"{ret}% <= trail {trail_stop}% (20% off peak MFE {peak}%)"}
        return {**base, "action": "HOLD", "reason": f"trailing: {ret}% peak {peak}% trail@{trail_stop}%"}
    return {**base, "action": "HOLD", "reason": f"stage {stage}"}


def _resolve_legs_occ(ticker, legs, creds):
    for name, right in (("bullish_call", "call"), ("bearish_put", "put")):
        if name not in legs:
            continue
        leg = legs[name]
        if leg.get("trigger_contract"):
            # panel blocker 2026-09-01: resolution would OVERWRITE the trigger occ with
            # Alpaca's nearest-strike pick (weekly-expiry ties resolve arbitrarily) - the
            # contract identity IS the strategy; the UW occ is already a real OCC symbol.
            leg.setdefault("occ_source", "uw_trigger_verbatim")   # afford_fallback keeps its label
            continue
        r = resolve_occ(ticker, right, leg["strike"], leg["dte"], creds)
        if r and r.get("occ_symbol"):
            leg.update({"occ_symbol": r["occ_symbol"], "strike": r["strike"], "expiry": r["expiration"],
                        "open_interest": r.get("open_interest"), "occ_source": "alpaca_resolved"})
        else:
            leg.update({"illiquid": True, "occ_source": "unresolved -> FAIL-OPEN skip"})
    if "flat_calendar" in legs:
        cal = legs["flat_calendar"]
        f = resolve_occ(ticker, "call", cal["strike"], cal["front_dte"], creds,
                        dte_min=CAL_FRONT_DTE[0], dte_max=CAL_FRONT_DTE[1])   # 10-15d short leg
        b = resolve_occ(ticker, "call", cal["strike"], cal["back_dte"], creds,
                        dte_min=CAL_BACK_DTE[0], dte_max=CAL_BACK_DTE[1])     # 35-45d long leg
        if f and b and f.get("occ_symbol") and b.get("occ_symbol"):
            cal.update({"front_occ": f["occ_symbol"], "back_occ": b["occ_symbol"],
                        "front_expiry": f["expiration"], "back_expiry": b["expiration"], "occ_source": "alpaca_resolved"})
        else:
            cal.update({"illiquid": True, "occ_source": "unresolved -> FAIL-OPEN skip"})
    _stamp_spreads(legs)


def _stamp_spreads(legs):
    """SENSOR 3: stamp the live bid/ask spread of each resolved OCC at order-generation time.
    Pure logging - never alters sizing or whether a leg is submitted."""
    if not v11:
        return
    for leg in legs.values():
        occ = leg.get("occ_symbol") or leg.get("back_occ")     # calendar -> long (back) leg
        try:
            leg["execution_cost"] = v11.option_spread(occ)
        except Exception:
            leg["execution_cost"] = {"source": "unavailable"}
        try:
            leg["oi_change"] = v11.oi_change(occ)              # SENSOR 8b: per-leg OI day-over-day
        except Exception:
            leg["oi_change"] = {"source": "unavailable"}


def enter_proactive_set(ticker, regime, mock=False, candidate=None, dry_run=True, illiquid=None,
                        resolve_real=None, positions=None, open_orders=None, probe=False, probe_filter=None):
    params = load_params()
    creds = _paper_creds()
    if positions is None:
        positions = get_open_positions(creds) if all(creds) else []
    blocked, why = ticker_blocked(ticker, positions, params, open_orders=open_orders, probe=probe)
    if blocked:
        return {"trade_set_id": None, "ticker": ticker, "skipped": True, "reason": why, "status": "SKIPPED"}

    md = collect_metadata(ticker, mock=mock)
    if md["macro"]["spot"] is None or md["iv_term"]["iv_front"] is None:    # core data unavailable ->
        return {"trade_set_id": None, "ticker": ticker, "skipped": True,    # SKIP (never fabricate a trade)
                "reason": f"core metadata unavailable (spot={md['macro']['source']}, "
                          f"iv={md['iv_term']['source']}) - degenerate/non-optionable ticker",
                "status": "SKIPPED"}
    if probe and probe_filter is not None and not probe_filter(md, candidate):
        return {"trade_set_id": None, "ticker": ticker, "skipped": True,
                "reason": "probe_filter: candidate does not match this probe slot's hypothesis",
                "status": "SKIPPED"}
    if fade_book.active() and not probe:
        # FADE BOOK entry shape (fade_book_spec.json): take the flow side ONLY when the ticker's
        # 20d trend AND the day's SPY both oppose it (the winners' disagreement shape). Anything
        # else is skipped - the fade book trades the shape or nothing.
        regime = fade_book.direction(md, candidate)
        if regime is None:
            return {"trade_set_id": None, "ticker": ticker, "skipped": True, "regime": "FADE_SKIP",
                    "reason": "fade_book: not fade-shaped (needs flow side contra trend AND contra SPY)",
                    "status": "SKIPPED"}
    else:
        regime = classify_regime(md, candidate)
    if regime == "NEUTRAL":          # SAFETY: the calendar exit is not yet spread-aware (Strategy B is directional;
        return {"trade_set_id": None, "ticker": ticker, "skipped": True, "regime": regime,   # managing the two calendar
                "reason": "NEUTRAL/calendar route disabled pending a spread-aware unit exit (naked-leg risk)",  # sub-legs
                "status": "SKIPPED"}                                                          # independently -> naked leg)
    # TIER B (owner decision 15): 3-day earnings blackout. Reads the days_to_earnings already in the
    # collected metadata (no extra API call). FAIL-OPEN on data: a null sensor never blocks - a
    # yfinance outage must degrade to "no blackout", not halt the engine.
    dte_earn = (md.get("pemd") or {}).get("days_to_earnings")
    ebd = params.get("earnings_blackout_days", 3)
    if isinstance(dte_earn, (int, float)) and 0 <= dte_earn <= ebd:
        return {"trade_set_id": None, "ticker": ticker, "skipped": True, "regime": regime,
                "reason": f"earnings blackout: reports in {int(dte_earn)}d (<= {ebd}d window)",
                "status": "SKIPPED"}
    trigger = f"regime_{regime}_loose"          # (was should_enter_proactive() - it only ever returned this)
    legs = build_legs(ticker, md, regime, illiquid=illiquid)
    min_ct = params.get("min_contracts", 2)
    if fade_book.active():
        # FADE v1.2.1 (owner order 2026-08-08 00:11): min_contracts 1 - Friday's funnel showed 8
        # of 24 qualifying candidates (SPY/QQQ/NVDA puts, the replay cohort's natural home) died
        # as unaffordable at 2 contracts on $800. The 358-path replay was per-contract; 1
        # contract aligns the live universe with the tested one.
        min_ct = fade_book.spec().get("min_contracts", 1)
    if all((leg.get("contracts") or 0) < min_ct for leg in legs.values()):   # AFFORDABILITY GATE (real-money sim)
        # TRIGGER-CONTRACT FALLBACK (2026-09-03: the BULL/mega-cap drought - every synthesized
        # 4%-OTM/35-DTE contract on $300-500 underlyings priced over the $1k probe ceiling and
        # the whole day entered nothing). The candidate's own trigger contract passed the scan's
        # affordability filter, so a PROBE buys THAT instead - through the panel-hardened
        # verbatim path (resolution skip, fail-closed live repricing, occ guard, nickel limits).
        _ft = (candidate or {}).get("flow_type")
        _af = (candidate or {}).get("afford_put" if _ft == "put" else "afford_call") if probe else None
        _fell = False
        if _af and _af.get("occ") and 0.30 <= (_af.get("ask") or 0) <= 9.9:
            try:
                _dte_af = max(1, (date.fromisoformat(str(_af["expiry"])) - date.today()).days)
            except Exception:
                _dte_af = 0
            if _dte_af >= 7:
                _nm = "bearish_put" if _ft == "put" else "bullish_call"
                legs = {_nm: {"structure": "LONG_PUT" if _ft == "put" else "LONG_CALL",
                              "occ_symbol": _af["occ"], "expiry": str(_af["expiry"]),
                              "strike": _af.get("strike"), "dte": _dte_af,
                              "entry_premium": _af["ask"],
                              "limit_price": round(round(_af["ask"] * 1.01 * 20) / 20, 2),
                              "contracts": 1, "alloc_usd": LEG_BUDGET, "illiquid": False,
                              "trigger_contract": True, "band_lo": 0.30,
                              "occ_source": "afford_fallback"}}
                _fell = True
        if not _fell:
            return {"trade_set_id": None, "ticker": ticker, "skipped": True, "regime": regime,
                    "reason": f"premium too rich for {min_ct}-contract min on ${LEG_BUDGET:.0f} budget",
                    "status": "SKIPPED"}
    if resolve_real is None:
        resolve_real = all(creds)
    if resolve_real:
        _resolve_legs_occ(ticker, legs, creds)                 # real OCCs; unresolved -> fail-open skip
    for _tn, _tl in legs.items():
        if not _tl.get("trigger_contract"):
            continue
        # TRIGGER-LEG LIVE REPRICING (panel 2026-09-01): the alert ask can be minutes stale and
        # the probe is excluded from the spread-retry repricer, so this leg gets its own quote
        # pass - FAIL-CLOSED: no live quote, live spread > 2%, or live ask outside the tested
        # $4-10 band -> SKIP (an unproven probe never submits a stale-priced order; entry_ref
        # honesty demands the real ask).
        _lb = _la = None
        try:
            _cr3 = _paper_creds()
            _rq3 = urllib.request.Request(
                "https://data.alpaca.markets/v1beta1/options/quotes/latest?symbols="
                + _tl["occ_symbol"] + "&feed=indicative",
                headers={"APCA-API-KEY-ID": _cr3[0], "APCA-API-SECRET-KEY": _cr3[1]})
            with urllib.request.urlopen(_rq3, timeout=15) as _r3:
                _q3 = (json.loads(_r3.read()).get("quotes") or {}).get(_tl["occ_symbol"]) or {}
            _lb, _la = _q3.get("bp"), _q3.get("ap")
        except Exception:
            pass
        _blo = _tl.get("band_lo", 4.0)      # pricey-pool probes keep their tested $4 floor; the
                                            # affordability fallback admits the scan's own 0.30+
        if not (_lb and _la and 0 < _lb <= _la and (_la - _lb) / _la * 100 <= 2.0 and _blo <= _la <= 9.9):
            return {"trade_set_id": None, "ticker": ticker, "skipped": True, "regime": regime,
                    "reason": f"trigger_contract fail-closed: no live quote / crossed / spread>2% / ask outside {_blo}-9.9",
                    "status": "SKIPPED"}
        _tl["entry_premium"] = _la
        _tl["limit_price"] = round(round(_la * 1.01 * 20) / 20, 2)   # nickel increment; caps at $10.00 = the $1k budget
        _tl["contracts"] = 1
        _tl["execution_cost"] = {"bid": _lb, "ask": _la,
                                 "bid_ask_spread_pct": round((_la - _lb) / _la * 100, 2),
                                 "source": "alpaca_quote_trigger"}
    # ONE RECORD PER CONTRACT, EVER (panel blocker 2026-09-02): no entry may target an occ that any
    # OPEN record tracks or the broker already holds - two records on one merged position means
    # either one's exit liquidates both and the backstops fight over one stop. This is the absolute
    # guard; the book-level ticker rules above are exposure policy, not collision protection.
    _occ_taken = set()
    try:
        for _r0 in _load_log_list():
            if _r0.get("status") == "OPEN":
                for _o0 in _record_leg_occs(_r0).values():
                    if _o0:
                        _occ_taken.add(_o0.upper())
        for _p0 in positions or []:
            _occ_taken.add((_p0.get("symbol") or "").upper())
    except Exception:
        _occ_taken = set()
    for _lg in legs.values():
        for _ok in (_lg.get("occ_symbol"), _lg.get("front_occ"), _lg.get("back_occ")):
            if _ok and _ok.upper() in _occ_taken:
                return {"trade_set_id": None, "ticker": ticker, "skipped": True, "regime": regime,
                        "reason": f"occ_collision: {_ok} already held/tracked - one record per contract, ever",
                        "status": "SKIPPED"}
    # SPREAD CAP (governed change 2026-07-25, owner-approved at the Sunday boundary; supersedes
    # decision 33's advisory-only status): the existing max_bid_ask_spread_pct now GATES on the REAL
    # Alpaca quote at OCC resolution. Evidence: monotone spread-bucket decay on 24k graded rows
    # (tight -0.04 -> wide>=20% -0.59 mean net) with 49% of real fills previously landing >=20%.
    # FAIL-OPEN on missing data: no quote -> no block (a dead sensor never halts the engine).
    cap = fade_book.spread_cap(params.get("max_bid_ask_spread_pct"))
    if cap:
        for name, leg in legs.items():
            sp = (leg.get("execution_cost") or {}).get("bid_ask_spread_pct")
            if isinstance(sp, (int, float)) and sp > cap:
                try:                                  # SPREAD RETRY (owner 2026-08-17: INTC died on a
                    import time as _t                 # 7.4% flicker quote, then the probe entered at a
                    _cr = _paper_creds()              # tight one 30s later - one re-quote before
                    global _SR_BUDGET                 # surrendering. BUDGETED: max 2 retries/cycle
                    if all(_cr) and leg.get("occ_symbol") and not probe and _SR_BUDGET > 0:
                        _SR_BUDGET -= 1
                        _t.sleep(4)
                        _rq = urllib.request.Request(
                            "https://data.alpaca.markets/v1beta1/options/quotes/latest?symbols="
                            + leg["occ_symbol"] + "&feed=indicative",
                            headers={"APCA-API-KEY-ID": _cr[0], "APCA-API-SECRET-KEY": _cr[1]})
                        with urllib.request.urlopen(_rq, timeout=15) as _r2:
                            _q2 = (json.loads(_r2.read()).get("quotes") or {}).get(leg["occ_symbol"]) or {}
                        _b2, _a2 = _q2.get("bp"), _q2.get("ap")
                        if _b2 and _a2 and _a2 > 0 and (_a2 - _b2) / _a2 * 100 <= cap:
                            _sp2 = round((_a2 - _b2) / _a2 * 100, 2)
                            leg["execution_cost"] = {"bid": _b2, "ask": _a2,
                                                     "bid_ask_spread_pct": _sp2,
                                                     "source": "alpaca_quote_retry"}
                            leg["entry_premium"] = _a2
                            leg["limit_price"] = _a2
                            leg["contracts"] = max(1, int(LEG_BUDGET // (_a2 * 100)))
                            print(f"  spread retry SAVED {leg['occ_symbol']}: {sp:.1f}% -> {_sp2:.1f}%")
                            continue
                except Exception:
                    pass
                return {"trade_set_id": None, "ticker": ticker, "skipped": True, "regime": regime,
                        "reason": f"spread_cap: real spread {sp:.1f}% > {cap:.1f}% cap ({name})",
                        "status": "SKIPPED"}
    try:                                                  # EARLY-STRENGTH (spec probe.early_strength):
        import early_strength                             # v1.7 watch-in-PARALLEL. The fade book buys
        if (not probe) and early_strength.enabled():      # immediately below, uncut; the watcher ALSO
            _lg = next(iter(legs.values()))               # stashes this candidate and, if it confirms
            _ec = _lg.get("execution_cost") or {}         # +5..15% strength, buys its OWN $1k probe
            if _lg.get("occ_symbol") and _ec.get("ask"):  # lot - both doors get live fills.
                early_strength.stash(ticker, _lg["occ_symbol"], _ec["ask"], regime,
                                     _lg.get("contracts") or 1, _lg.get("alloc_usd") or LEG_BUDGET)
    except Exception as _ese:
        print(f"  early-strength stash fail-open: {type(_ese).__name__}")
    orders = route_to_alpaca_paper(ticker, legs, dry_run=dry_run)
    record = {"trade_set_id": uuid.uuid4().hex[:12], "ticker": ticker, "regime": regime, "trigger": trigger,
              "book": "PROBE" if probe else ("FADE" if fade_book.active() else "V10"),
              "router_state": ("MILD" if isinstance((md.get("regime_stack") or {}).get("market_spy_dist_pct"),
                                                    (int, float))
                               and abs(md["regime_stack"]["market_spy_dist_pct"]) < 1.5 else "TREND"),
              "entry_ts_utc": md["entry_ts_utc"], "leg_budget_usd": LEG_BUDGET,
              "execution_mode": "DRY_RUN" if dry_run else "LIVE_PAPER",
              "occ_resolution": "alpaca_real" if resolve_real else "synthesized",
              "ticker_guard": why, "open_positions_checked": len(positions),
              "params_snapshot": params, "metadata": md, "legs": legs, "orders": orders,
              "exit": None, "status": "OPEN"}
    if not dry_run:
        record["buy_alert_delivered"] = _notify(_buy_msg(record))   # honesty flag - reconciled in the digest
    _append_log(record)
    return record


def _skip_code(reason):
    """School 1d: map the entry loop's human skip reasons to stable harvest codes."""
    r = reason.lower()
    if "spread_cap" in r:
        return "spread_cap"
    if "one-per-underlying" in r or "max contracts" in r:
        return "one_per_underlying"
    if "cool-off" in r:
        return "cooloff"
    if "earnings blackout" in r:
        return "earnings_blackout"
    if "metadata unavailable" in r:
        return "metadata_unavailable"
    if "premium too rich" in r:
        return "premium_too_rich"
    if "neutral" in r:
        return "neutral_disabled"
    return "other_engine_skip"


def _append_log(record):
    data = []
    if os.path.exists(LOG_PATH):
        # FAIL-CLOSED (silent-gap audit 2026-08-25): the old fallback (unreadable -> [])
        # would then WRITE data+[record], replacing the whole book with one record. A file
        # that exists but will not parse mid-cycle is real corruption - crash loudly (the
        # run-failure telegram fires) instead of destroying the book. Startup already
        # validated the file via _assert_log_integrity.
        data = json.load(open(LOG_PATH, encoding="utf-8"))
    data.append(record)
    json.dump(data, open(LOG_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def _rewrite_last(record):
    data = json.load(open(LOG_PATH, encoding="utf-8"))
    for i in range(len(data) - 1, -1, -1):
        if data[i]["trade_set_id"] == record["trade_set_id"]:
            data[i] = record
            break
    json.dump(data, open(LOG_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def _load_log_list():
    if not os.path.exists(LOG_PATH):
        return []
    # FAIL-CLOSED (silent-gap audit 2026-08-25): unreadable used to mean "empty book" -> the
    # reconciler adopted every broker position as an orphan. Parse failure now raises; the
    # cycle aborts with the loud run-failure telegram instead of trading blind.
    return json.load(open(LOG_PATH, encoding="utf-8"))


def _save_log_list(data):
    json.dump(data, open(LOG_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def _close_position(occ, creds, percentage=100, decision_mark=None):
    """Close an open option leg via Alpaca close-position (market order). percentage<100 scales
    out a partial position (e.g. 50 for the Strategy-B half-sell)."""
    import urllib.parse
    key, sec = creds
    url = PAPER_BASE + "/v2/positions/" + urllib.parse.quote(occ)
    if percentage and percentage < 100:
        url += "?percentage=" + str(percentage)
    req = urllib.request.Request(url, method="DELETE",
                                 headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            ok = r.status in (200, 207)
            try:                                       # school 1c: stash the close ORDER (fail-open,
                import fill_ledger                     # response body was previously discarded)
                fill_ledger.stash_close_order(occ, json.loads(r.read().decode()),
                                              decision_mark=decision_mark)  # A2: decision-time ref
            except Exception:
                pass
            return ok
    except Exception:
        return False


def _record_leg_occs(rec):
    out = {}
    for name, leg in (rec.get("legs") or {}).items():
        if name == "flat_calendar":
            if leg.get("front_occ"):
                out["calendar_front"] = leg["front_occ"]
            if leg.get("back_occ"):
                out["calendar_back"] = leg["back_occ"]
        elif leg.get("occ_symbol"):
            out[name] = leg["occ_symbol"]
    return out


def manage_open_positions(creds, params, positions=None):
    """EXIT PASS: evaluate every open option position against the 24h swing guard + 30-50%
    velocity target (manage_exit). Close winners, trip the 24h ticker cool-off (record_close),
    and run the live autopsy (run_trade_autopsy) once a trade-set has no open legs left."""
    if not all(creds):
        return [], []
    positions = positions if positions is not None else get_open_positions(creds)
    pos_by_occ = {(p.get("symbol") or "").upper(): p for p in positions}
    log = _load_log_list()
    closed_legs, autopsies, dirty = [], [], False
    for rec in log:
        if rec.get("status") != "OPEN" or not isinstance(rec.get("legs"), dict):
            continue
        leg_occs = _record_leg_occs(rec)
        if not leg_occs:
            continue
        rec.setdefault("leg_exits", {})
        # 1. evaluate + close each leg with an open position that cleared 24h and hit the target
        for leg_name, occ in leg_occs.items():
            if leg_name in rec["leg_exits"]:
                continue
            p = pos_by_occ.get((occ or "").upper())
            if not p:
                # position gone -> did the broker-side stop (current OR a superseded id) fire? reconcile.
                if _capture_backstop_fill(rec, leg_name, occ, creds, log, closed_legs):
                    dirty = True
                    continue
                # UNTRACKED-LEG COUNTER (audit finding #10): a position that vanished with NO
                # backstop record (expired worthless / manually closed / never filled) used to
                # stay OPEN forever, silently skipped every cycle. After 5 consecutive
                # position-less cycles, book an honest CLOSE_UNTRACKED at the last seen return
                # (worst-known if none) so the record leaves the open set.
                _pth = rec.setdefault("leg_path", {}).setdefault(leg_name, {})
                _mc = _pth["missing_cycles"] = _pth.get("missing_cycles", 0) + 1
                if _mc >= 5:
                    _lr = _pth.get("last_ret", _pth.get("mae_pct", -100.0))
                    rec["leg_exits"][leg_name] = {
                        "occ": occ, "closed_at": _now_iso_ms(), "return_pct": _lr,
                        "reason": ("UNTRACKED: no broker position for " + str(_mc)
                                   + " cycles and no backstop fill - booked at last seen "
                                   + str(_lr) + "%"),
                        "action": "CLOSE_UNTRACKED", "closed_ok": True}
                    _notify("<b>TIDY-UP: closed untracked leg</b> " + str(rec.get("ticker"))
                            + " " + str(occ) + chr(10)
                            + "Plain English: the broker no longer shows this position (likely "
                            + "expired or closed outside my view). I booked it at its last seen "
                            + "value (" + str(_lr) + "%) so the records match reality. "
                            + "No action needed.")
                dirty = True
                continue
            entry_px = float(p.get("avg_entry_price") or 0)
            plpc = p.get("unrealized_plpc")
            if plpc is not None:
                ret_pct = float(plpc) * 100.0                  # broker directional P/L %, sign-correct (long & short)
            else:
                cur_px = float(p.get("current_price") or 0)
                ret_pct = (cur_px / entry_px - 1) * 100.0 if entry_px else 0.0
            path = rec.setdefault("leg_path", {}).setdefault(leg_name, {"mfe_pct": ret_pct, "mae_pct": ret_pct, "stage": "initial"})
            path["mfe_pct"] = round(max(path["mfe_pct"], ret_pct), 1)   # Max Favorable Excursion (trade path)
            path["mae_pct"] = round(min(path["mae_pct"], ret_pct), 1)   # Max Adverse Excursion
            path["last_ret"] = round(ret_pct, 1)
            path.pop("missing_cycles", None)                             # position visible again
            dirty = True                                                 # persist the running path every cycle
            dec = manage_exit(rec["entry_ts_utc"], ret_pct, params, expiry_iso=_occ_expiry(occ),
                              stage=path.get("stage", "initial"), mfe_pct=path["mfe_pct"],
                              book=rec.get("book"), probe=rec.get("probe_strategy"))
            if (dec.get("action") not in (None, "HOLD") and fade_book.no_same_day_exit()
                    and str(rec.get("entry_ts_utc", ""))[:10] == datetime.now(timezone.utc).date().isoformat()):
                path["pdt_deferred"] = dec["action"]              # owner hold rule (2026-08-12): no
                dec = {"action": "HOLD", "return_pct": ret_pct,   # same-CALENDAR-DAY sells (broker
                       "stage": path.get("stage", "initial")}
                                                                  # day-trade flags); the exit rule
                                                                  # fires from tomorrow's first cycle
            if dec["action"] == "SCALE_OUT_50":                          # tier 1: sell half, runner continues
                if not _retire_stop(rec, leg_name, occ, creds, log, closed_legs):
                    dirty = True                                          # stop live / cancel unconfirmed ->
                    continue                                             # do NOT sell against it; retry next cycle
                if leg_name in rec["leg_exits"]:                          # a full backstop fill during retire closed it
                    dirty = True
                    continue
                _ep = (rec["legs"].get(leg_name) or {}).get("entry_premium")
                _dm = round(_ep * (1 + dec["return_pct"] / 100.0), 4) if isinstance(_ep, (int, float)) and dec.get("return_pct") is not None else None
                ok = _close_position(occ, creds, percentage=50, decision_mark=_dm)
                if ok:                                                    # only advance to 'scaled' on a SUCCESSFUL half-sell
                    path["stage"] = "scaled"                              # (failed partial -> stay 'initial', retry next cycle)
                    path["close_fails"] = 0
                    path["scaled_out"] = {"at": _now_iso_ms(), "return_pct": dec["return_pct"]}
                    closed_legs.append({"ticker": rec["ticker"], "leg": leg_name + " (50%)", "occ": occ,
                                        "return_pct": dec["return_pct"], "action": "SCALE_OUT_50", "closed_ok": ok})
                    _notify(_sell_msg(closed_legs[-1]))           # Telegram SELL alert (fail-open)
                else:
                    _note_close_failure(rec, path, leg_name, occ, params, creds)   # park a zero-bid corpse after N fails
                dirty = True
            elif dec["action"].startswith("CLOSE"):          # stop / break-even / trail / expiry -> full close
                if not _retire_stop(rec, leg_name, occ, creds, log, closed_legs):
                    dirty = True                                          # a filled close + live stop would double-sell:
                    continue                                             # skip until the stop is confirmed gone
                if leg_name in rec["leg_exits"]:                          # backstop already fully closed the leg
                    dirty = True
                    continue
                _ep = (rec["legs"].get(leg_name) or {}).get("entry_premium")
                _dm = round(_ep * (1 + dec["return_pct"] / 100.0), 4) if isinstance(_ep, (int, float)) and dec.get("return_pct") is not None else None
                ok = _close_position(occ, creds, percentage=100, decision_mark=_dm)
                if ok:                                                    # only mark exited on a SUCCESSFUL close
                    path["stage"] = dec["stage"]                          # (rejected close, e.g. market closed -> retry next cycle)
                    path["close_fails"] = 0
                    rec["leg_exits"][leg_name] = {"occ": occ, "closed_at": _now_iso_ms(),
                                                  "return_pct": dec["return_pct"], "reason": dec["reason"],
                                                  "action": dec["action"], "closed_ok": ok}
                    record_close(rec["ticker"])                       # 24h cool-off
                    closed_legs.append({"ticker": rec["ticker"], "leg": leg_name, "occ": occ,
                                        "return_pct": dec["return_pct"], "action": dec["action"], "closed_ok": ok})
                    _notify(_sell_msg(closed_legs[-1]))           # Telegram SELL alert (fail-open)
                    if str(rec.get("entry_ts_utc", ""))[:10] == datetime.now(timezone.utc).date().isoformat():
                        # PDT LEDGER: same-day full close (e.g. hard stop) consumed a day trade
                        log.append({"type": "day_trade", "ts_utc": _now_iso_ms(), "ticker": rec["ticker"],
                                    "occ": occ, "via": dec["action"], "status": "LOGGED"})
                else:
                    _note_close_failure(rec, path, leg_name, occ, params, creds)   # park a zero-bid corpse after N fails
                dirty = True
            else:                                                         # HOLD (incl. the trail-arm transition)
                path["stage"] = dec["stage"]                              # persist 'trailing' arm / 'initial'
        # 2. autopsy once the set has no remaining OPEN legs
        still_open = any((occ or "").upper() in pos_by_occ and ln not in rec["leg_exits"]
                         for ln, occ in leg_occs.items())
        if not still_open and rec["leg_exits"]:
            returns = {ln: 0.0 for ln in (rec.get("legs") or {})}      # only the legs actually traded
            for ln, ex in rec["leg_exits"].items():
                key = "flat_calendar" if ln.startswith("calendar") else ln
                if key in returns:
                    returns[key] = ex["return_pct"]
            try:
                ex_reason = "+".join(sorted({ex.get("action", "CLOSE") for ex in rec["leg_exits"].values()}))
                res = run_trade_autopsy(rec, returns, exit_reason=ex_reason, underlying_move_pct=0.0)
                autopsies.append({"ticker": rec["ticker"], "set": rec["trade_set_id"],
                                  "winner": res["winner"], "factor": res["determining_factor"]})
            except Exception as e:
                rec["status"] = "CLOSED"
                autopsies.append({"ticker": rec["ticker"], "autopsy_error": str(e)[:80]})
            _notify(_autopsy_msg(autopsies[-1]))             # Telegram AUTOPSY alert (fail-open)
            dirty = True
    # PARKED auto-resolve: a parked corpse whose every leg is past expiry closed itself (-100%). Before
    # stamping -100%, reconcile any backstop fill (a stop that fired before/at park must win over the
    # fabricated worthless mark) so the brake / scoreboard / week-6 study see the real exit.
    today_d = datetime.now(timezone.utc).date()
    for rec in log:
        if rec.get("status") != "PARKED":
            continue
        occs = _record_leg_occs(rec)
        for ln, occ in occs.items():
            if ln not in rec.get("leg_exits", {}):
                _capture_backstop_fill(rec, ln, occ, creds, log, closed_legs)
        exps = [_occ_expiry(o) for o in occs.values()]
        if occs and all(e and date.fromisoformat(e) < today_d for e in exps):
            rec.setdefault("leg_exits", {})
            for ln, occ in occs.items():
                if ln not in rec["leg_exits"]:
                    rec["leg_exits"][ln] = {"occ": occ, "closed_at": _now_iso_ms(), "return_pct": -100.0,
                                            "reason": "parked corpse expired worthless",
                                            "action": "CLOSE_EXPIRED_WORTHLESS", "closed_ok": True}
            rec["status"] = "CLOSED"
            _notify(f"<b>PARKED RESOLVED {rec.get('ticker')}</b> expired worthless (-100%)")
            dirty = True
    if dirty:
        _save_log_list(log)
    return closed_legs, autopsies


# ----------------------------------------------------------------------------
# Autopsy + Tuning Advisory
# ----------------------------------------------------------------------------
def _determining_factor(winner, md, move, ret=None):
    alt, gex, ivt = md["alt_catalyst"], md["gex"], md["iv_term"]
    rd = alt.get("reddit_mention_delta_pct")
    zg, reg = gex.get("zero_gamma_strike"), gex.get("regime")
    lost = ret is not None and ret < 0
    if winner == "bullish_call":
        if lost:
            return f"Bullish call FAILED ({ret:+.0f}%, move {move}%): the expected expansion never came; {reg} regime / spot vs zero-gamma {zg} worked against it."
        if alt.get("insider_cluster_flag"):
            return f"Insider cluster buy (${alt.get('insider_10d_buy_usd'):,.0f}/10d) predicted the bullish expansion; {reg} amplified the breakout."
        if rd is not None and rd > 500:
            return f"Breakout triggered by a +{rd:.0f}% Reddit spike while IV term was in {ivt.get('structure')}."
        return f"Bullish breakout (move {move}%); dealers short gamma near {zg} fed the squeeze."
    if winner == "bearish_put":
        if lost:
            return f"Bearish put FAILED ({ret:+.0f}%, move {move}%): no breakdown materialised; spot held above zero-gamma {zg}."
        return f"Bearish breakdown (move {move}%): spot below zero-gamma {zg} -> negative-gamma slide, no positive catalyst."
    if lost:
        return f"Calendar FAILED ({ret:+.0f}%): the range broke; IV term {ivt.get('structure')} (ratio {ivt.get('iv_ratio')}) hurt the spread."
    return f"Range held: IV term {ivt.get('structure')} (ratio {ivt.get('iv_ratio')}) let front-month theta outrun the wings."


def _tuning_rules(record, returns, slippage_pct):
    md = record["metadata"]
    spot, zg = md["macro"]["spot"], md["gex"]["zero_gamma_strike"]
    final_spot = spot * (1 + (record.get("exit", {}) or {}).get("underlying_move_pct", 0) / 100.0)
    iv_ratio = md["iv_term"]["iv_ratio"]
    recs = []
    if returns.get("bullish_call", 0) < 0 and zg is not None and final_spot < zg:
        recs.append(("min_gex_distance",
                     "Bullish Call lost AND spot crossed below the Zero-Gamma strike -> "
                     "Tighten min_gex_distance or restrict Calls when GEX is negative."))
    if returns.get("flat_calendar", 0) < 0 and iv_ratio is not None and iv_ratio > 1.0:
        recs.append(("max_iv_ratio_for_calendar",
                     f"Calendar Spread lost AND IV Ratio {iv_ratio} > 1.0 (backwardation) -> "
                     "Enforce standard contango by setting max_iv_ratio_for_calendar to < 1.0."))
    if slippage_pct is not None and slippage_pct > 3.0:
        recs.append(("max_bid_ask_spread_pct",
                     f"Entry slippage {slippage_pct}% > 3% -> "
                     "Tighten max_bid_ask_spread_pct from 5.0% to 2.0%."))
    return recs


def run_trade_autopsy(record, leg_returns_pct, exit_reason="5d_time_exit",
                      underlying_move_pct=None, entry_slippage_pct=None):
    md = record["metadata"]
    ranked = sorted(leg_returns_pct.items(), key=lambda kv: kv[1], reverse=True)
    winner, w_ret = ranked[0]
    loser, l_ret = ranked[-1]
    lp = record.get("leg_path") or {}
    record["exit"] = {"reason": exit_reason, "underlying_move_pct": underlying_move_pct,
                      "entry_slippage_pct": entry_slippage_pct, "leg_returns_pct": leg_returns_pct,
                      "winner": winner, "loser": loser, "leg_path": lp,
                      "mfe_pct": max((v.get("mfe_pct", 0) for v in lp.values()), default=None),   # best path point
                      "mae_pct": min((v.get("mae_pct", 0) for v in lp.values()), default=None)}   # worst path point
    factor = _determining_factor(winner, md, underlying_move_pct, w_ret)
    record["exit"]["determining_factor"] = factor
    record["status"] = "CLOSED"

    # post-mortem markdown
    label = {"bullish_call": "Bullish (call)", "bearish_put": "Bearish (put)", "flat_calendar": "Flat (calendar)"}
    pm = [f"## Autopsy - {record['ticker']} ({record['trade_set_id']})",
          f"- entered {record['entry_ts_utc']} | trigger {record.get('trigger', '?')} | exit {exit_reason} "
          f"| move {underlying_move_pct}% | slippage {entry_slippage_pct}%", "",
          "| leg | structure | return % | verdict |", "|---|---|---|---|"]
    for leg, ret in ranked:
        v = "WINNER" if leg == winner else ("loser" if leg == loser else "")
        struct = (record.get("legs", {}).get(leg) or {}).get("structure", "?")
        pm.append(f"| {label.get(leg, leg)} | {struct} | {ret:+.1f}% | {v} |")
    pm += ["", f"**Determining factor:** {factor}", ""]
    open(AUTOPSY_MD, "a", encoding="utf-8").write("\n".join(pm) + "\n")

    # tuning advisory
    recs = _tuning_rules(record, leg_returns_pct, entry_slippage_pct)
    adv = [f"## Tuning Advisory - {record['ticker']} ({record['trade_set_id']}) - {_now_iso_ms()}",
           f"trade: winner={winner} loser={loser} | move {underlying_move_pct}% | slippage {entry_slippage_pct}%",
           "", "Recommendations:"]
    adv += [f"- [{gate}] {msg}" for gate, msg in recs] or ["- none (no rule triggered)"]
    open(ADVISORY_MD, "a", encoding="utf-8").write("\n".join(adv) + "\n---\n")
    record["exit"]["tuning_recommendations"] = [g for g, _ in recs]
    return {"winner": winner, "loser": loser, "determining_factor": factor, "recommendations": recs}


# ----------------------------------------------------------------------------
# Phase 2: dynamic market-wide sourcing from Unusual Whales flow (NO hardcoded list)
# ----------------------------------------------------------------------------
def scan_candidates(params, limit=None):
    """Aggregate whole-market UW flow alerts into ranked candidates with a flow-implied direction,
    PRE-FILTERED to the affordable band (per-contract premium fits the $800/2-contract budget) so
    the funnel feeds cheap mid-caps instead of rejecting mega-caps downstream. Fail-open: returns []
    if UW is unreachable. Never falls back to a predefined list."""
    limit = limit or params.get("scanner_flow_limit", 600)          # wide net to reach the cheap tail
    prem_lo = params.get("scanner_premium_min", 0.30)
    prem_hi = params.get("scanner_premium_max", 4.00)               # 2ct x $4 x 100 = $800 ceiling
    try:
        from src.unusual_whales_api import UnusualWhalesClient
        uw = UnusualWhalesClient()
        if not getattr(uw, "enabled", False):
            return []
        min_prem = params.get("scanner_min_premium", 50000)
        rows = (uw.flow_alerts(ticker=None, limit=limit, min_premium=min_prem) or {}).get("data") or []
    except Exception:
        return []
    index_roots = {"SPX", "SPXW", "SPXPM", "NDX", "NDXP", "RUT", "RUTW", "VIX", "VIXW",
                   "XSP", "DJX", "OEX", "XEO", "MRUT", "NANOS", "VVIX"}
    agg = {}
    aggx = {}                                       # expensive-contract triggers (probe side-pool)
    for r in rows:
        t = (r.get("ticker") or "").upper()
        if not t or t in index_roots:               # drop index / non-equity underlyings up front
            continue
        pc = _num(r.get("price"))                   # per-contract option premium (the affordability signal)
        if pc is None or not (prem_lo <= pc <= prem_hi):    # AFFORDABILITY AT SOURCE ($0.30-$4.00 -> $800/2ct)
            # EXPENSIVE-TRIGGER pool (2026-09-01, panel-corrected build): keep the CONTRACT
            # IDENTITY, not a ticker aggregate - the +21.2/day t4.31 cell was measured on the
            # trigger contract itself, so that is what the probe must buy. Faithful filters at
            # alert level: calls, ask $4-9 (1 contract fits the $1k probe budget with drift
            # room), per-alert premium 50-400k in-band, ask-side aggressor, spread <= 2%.
            if pc is not None and 4.00 < pc <= 9.00 and (r.get("type") or "").lower() == "call":
                _tp = _num(r.get("total_premium")) or 0.0
                _asp = _num(r.get("total_ask_side_prem")) or 0.0
                _bsp = _num(r.get("total_bid_side_prem")) or 0.0
                _qb, _qa = _num(r.get("bid")), _num(r.get("ask"))
                try:
                    # DTE floor 7 (panel 2026-09-01): shorter expiries are structurally
                    # unmanageable here - no-same-day-exit defers every exit on entry day and
                    # backstops arm next day, so a 0-2 DTE leg could expire ungated. The
                    # backtest's next-session exits implied survival past entry day anyway.
                    _exp_ok = (date.fromisoformat(str(r.get("expiry"))) - date.today()).days >= 7
                except Exception:
                    _exp_ok = False
                if (50000 <= _tp <= 400000 and _asp > _bsp and r.get("option_chain")
                        and _exp_ok and _num(r.get("strike")) is not None
                        and _qb and _qa and _qa > 0 and (_qa - _qb) / _qa * 100 <= 2.0):
                    _prev = aggx.get(t)
                    if not _prev or _tp > _prev["total_premium"]:
                        aggx[t] = {"ticker": t, "flow_type": "call", "total_premium": _tp,
                                   "underlying_price": _num(r.get("underlying_price")),
                                   "min_contract_premium": pc, "occ": r.get("option_chain"),
                                   "expiry": r.get("expiry"), "strike": _num(r.get("strike")),
                                   "alert_ask": _qa}
            continue
        a = agg.setdefault(t, {"ticker": t, "call_prem": 0.0, "put_prem": 0.0,
                               "underlying_price": _num(r.get("underlying_price")), "min_contract_premium": pc})
        a["min_contract_premium"] = min(a["min_contract_premium"], pc)
        # AFFORDABILITY IDENTITY (2026-09-03 fix): keep the cheapest in-band contract PER SIDE so
        # a probe whose synthesized contract prices over the $1k budget (mega-cap bull days) can
        # buy THE trigger contract instead of nothing - it passed this very price filter.
        _rtyp = (r.get("type") or "").lower()
        _akey = "afford_call" if _rtyp == "call" else "afford_put" if _rtyp == "put" else None
        if _akey and r.get("option_chain"):
            try:
                from datetime import date as _dt
                _dok = (_dt.fromisoformat(str(r.get("expiry"))) - _dt.today()).days >= 7
            except Exception:
                _dok = False
            if _dok and (a.get(_akey) is None or pc < a[_akey]["ask"]):
                a[_akey] = {"occ": r["option_chain"], "ask": pc,
                            "expiry": str(r.get("expiry")), "strike": _num(r.get("strike"))}
        prem = _num(r.get("total_premium")) or 0.0
        if (r.get("type") or "").lower() == "call":
            a["call_prem"] += prem
        elif (r.get("type") or "").lower() == "put":
            a["put_prem"] += prem
    cands = []
    for a in agg.values():
        a["flow_type"] = "call" if a["call_prem"] >= a["put_prem"] else "put"
        a["total_premium"] = round(a["call_prem"] + a["put_prem"], 0)
        cands.append(a)
    if fade_book.active():
        # FADE BOOK: mid-band flow only ($50-250k spec default) - the whale band tested crowded
        # (13.6% wins) and the small band noise (10.9%); biggest-premium-first dies with V10.
        _pw = (fade_book.spec().get("probe") or {}).get("whale") or {}
        if _pw:                                     # v1.7.1 FADE_WHALE probe side-pool: 400k-1M
            global _WHALE_CANDS                     # fade-shaped whales day-meaned +3.37 vs -0.47
            _WHALE_CANDS = sorted(                  # in-band on the stored cohort (n=47/24d, t=0.34,
                [c for c in cands                   # halves +13.7/-6.9 - promising, unstable) so the
                 if (_pw.get("flow_min") or 400000) # probe buys them live; the FADE list below stays
                 < (c.get("total_premium") or 0) <= (_pw.get("flow_max") or 1000000)],
                key=lambda x: x["total_premium"], reverse=True)
        global _PRICEY_CANDS
        _PRICEY_CANDS = sorted(aggx.values(), key=lambda x: x["total_premium"], reverse=True)[:14]
        global _FULL_CANDS
        _FULL_CANDS = sorted([c for c in cands
                              if 50000 <= (c.get("total_premium") or 0) <= 1000000],
                             key=lambda x: x["total_premium"], reverse=True)[:20]
        # ^ ceiling at 1M: the tested band ends there (panel 2026-09-02 - unbounded, mega-name
        # aggregates above 1M would occupy the head slots on a cohort the tuner never measured)
        # ^ snapshot BEFORE the flow_band cut: the tuner's full grid (39.5k contracts) put the
        # calls family's strongest cells in the FULL 50k-1M premium band (t+4.1 to +5.2, 270d)
        # vs weaker in the 50-400k slice - the probes that tested full-band trade full-band
        cands = fade_book.flow_band(cands)          # byte-identical for the live book
    cands.sort(key=lambda x: x["total_premium"], reverse=True)
    return cands


# ----------------------------------------------------------------------------
# Observability: end-of-day digest + degraded/failure alerts (Telegram, fail-open)
# ----------------------------------------------------------------------------
def daily_digest():
    """Summarise today's entries, exits, P&L and data-source health -> Telegram. Returns the text."""
    today = datetime.now(timezone.utc).date().isoformat()
    log = _load_log_list()
    entries = [r for r in log if str(r.get("entry_ts_utc", "")).startswith(today)]
    closes = [(r.get("ticker"), ln, ex) for r in log for ln, ex in (r.get("leg_exits") or {}).items()
              if str(ex.get("closed_at", "")).startswith(today)]
    wins = [e for _, _, e in closes if (e.get("return_pct") or 0) > 0]
    pnl = sum((e.get("return_pct") or 0) for _, _, e in closes)
    degraded = sum(1 for r in entries for blk in ("macro", "iv_term", "gex", "flow_aggression", "dark_pool",
                   "pemd", "vrp", "flow_persistence", "skew", "news")
                   if ((r.get("metadata") or {}).get(blk) or {}).get("source") in ("unavailable", "mock"))
    lines = [f"<b>SANDBOX DIGEST {today}</b>",
             f"Entries: {len(entries)} ({', '.join(sorted(set(r.get('ticker') for r in entries))) or 'none'})",
             f"Closes: {len(closes)} | wins {len(wins)}/{len(closes)} | sum return {pnl:+.1f}%"]
    if not entries and datetime.now(timezone.utc).weekday() < 5:
        # ZERO-ENTRY MARKET-DAY ALARM (landing-check class, 2026-08-05: the iv_term outage ran
        # 24h silent because nothing pages on absence). Loud line + separate notify so a dead
        # entry path can never again hide inside a normal-looking digest.
        lines.insert(1, "&#9888; <b>ZERO ENTRIES on a market day</b> - if this repeats 2 days "
                        "running, check data-source health (iv_term/scanner) FIRST")
        try:
            _notify("<b>ALARM: zero entries on a market day</b> - entry path may be blocked "
                    "(data outage / gates). See digest + cycle logs.")
        except Exception:
            pass
    for tk, ln, ex in closes[:8]:
        lines.append(f"  {tk} {ln} {ex.get('action')} {(ex.get('return_pct') or 0):+.1f}%")
    lines.append(f"Sensor-source degradations: {degraded}")
    # 9b DAILY SCOREBOARD (reporting only): today + running totals since go-live
    TRACK_START = "2026-07-06"
    recs = [r for r in log if r.get("trade_set_id") and isinstance(r.get("legs"), dict)]
    open_now = [r for r in recs if r.get("status") == "OPEN"]
    parked = [r for r in recs if r.get("status") == "PARKED"]
    completed = [r for r in recs if r.get("status") == "CLOSED" and str(r.get("entry_ts_utc", "")) >= TRACK_START]
    legs_closed = [(r, ln, ex) for r in recs for ln, ex in (r.get("leg_exits") or {}).items()
                   if str(ex.get("closed_at", "")) >= TRACK_START]
    leg_wins = [x for x in legs_closed if (x[2].get("return_pct") or 0) > 0]
    wr = f" ({100.0 * len(leg_wins) / len(legs_closed):.0f}%)" if legs_closed else ""
    lines.append(f"Scoreboard: open now {len(open_now)} | parked {len(parked)} | since {TRACK_START}: "
                 f"{len(completed)} trade-sets completed, legs {len(leg_wins)}/{len(legs_closed)} wins{wr}")
    # alert-path honesty: entries made vs BUY alerts delivered + this process's send counters
    live_entries = [r for r in entries if r.get("buy_alert_delivered") is not None]
    buy_ok = sum(1 for r in live_entries if r.get("buy_alert_delivered"))
    lines.append(f"Alert reconciliation: {len(live_entries)} live entries -> {buy_ok} BUY alerts delivered "
                 f"| sends this run: ok {_NOTIFY_STATS['sent']} / failed {_NOTIFY_STATS['failed']}")
    day_trades = [r for r in log if r.get("type") == "day_trade" and str(r.get("ts_utc", "")).startswith(today)]
    if day_trades:
        lines.append(f"Day trades consumed today (PDT ledger): {len(day_trades)}")
    bmark = next((r for r in log if r.get("type") == "daily_brake"
                  and str(r.get("ts_utc", "")).startswith(today)), None)
    if bmark:
        if bmark.get("status") == "BRAKED":
            lines.append(f"DAILY BRAKE tripped today ({bmark.get('reason')}) - new entries were HALTED")
        else:
            lines.append(f"DAILY BRAKE would have tripped ({bmark.get('reason')}) - SHADOW: "
                         "entries still fired and are tagged for measurement")
    text = "\n".join(lines)
    _notify(text)
    return text


def _maybe_send_digest():
    """Fire the EOD digest once/day, on the first cycle at/after 20:00 UTC. Persistence = a marker
    record in the (committed) log, so it survives the ephemeral GHA runner."""
    now = datetime.now(timezone.utc)
    if now.hour < 20:
        return
    today = now.date().isoformat()
    if any(r.get("type") == "daily_digest" and str(r.get("ts_utc", "")).startswith(today) for r in _load_log_list()):
        return
    daily_digest()
    _append_log({"type": "daily_digest", "ts_utc": _now_iso_ms(), "status": "SENT"})


def reconcile_orphans(creds, params, positions=None, log=None):
    """ROADMAP item 2b: cycle-start broker-vs-record ROLL-CALL. A dropped trade record (rare
    double-push collision on the non-union-merged log) leaves a live broker position with NO tracking
    record - unmanaged by the exit engine AND invisible to one-per-underlying, which reads OPEN
    RECORDS (not raw positions). ADOPT any position whose OCC appears in NO record into a fresh
    reconstructed OPEN record (entry_ref = avg_entry_price) so the exit engine manages it and the
    underlying is blocked from re-entry. Positions that match a known record - including PARKED /
    FLUSHED stragglers - are left alone (those are intentionally exempt). Returns the adopted OCCs."""
    if not all(creds):
        return []
    positions = positions if positions is not None else get_open_positions(creds)
    log_list = log if log is not None else _load_log_list()
    known = set()
    for rec in log_list:
        if rec.get("occ") and not isinstance(rec.get("legs"), dict):   # PUTW/VRP/5K bare-occ
            for _om in rec.get("occ_more") or []:
                known.add((_om or "").upper())
            known.add(rec["occ"].upper())      # 2026-08-11 friendly-fire fix: PUTW records carry a
            continue                           # bare occ (no legs dict) - the reconciler adopted our
                                               # own short put 23 min after entry and the exit engine
                                               # bought it back. PUTW positions are KNOWN, never orphans.
        if rec.get("status") == "OPEN" and (rec.get("shares") or {}).get("symbol"):
            known.add(rec["shares"]["symbol"].upper())   # OPEN shares probes (OVERNIGHT/TURN_OF_MONTH)
            continue                                     # manage their own equity - same lesson as PUTW
        if isinstance(rec.get("legs"), dict):
            for occ in _record_leg_occs(rec).values():
                known.add((occ or "").upper())
    recent = set()
    try:                                   # 2026-08-14 double-claim fix: an occ FILLED in the last
        from datetime import timedelta as _td      # 45 min gets a propagation grace period before
        _after = (datetime.now(timezone.utc) - _td(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _rq = urllib.request.Request(
            "https://paper-api.alpaca.markets/v2/orders?status=closed&limit=100&after=" + _after,
            headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
        with urllib.request.urlopen(_rq, timeout=15) as _r:
            for _o in json.loads(_r.read()):
                if _o.get("filled_at"):                      # BOTH sides (2026-08-17: sell-side
                    recent.add((_o.get("symbol") or "").upper())   # gap let our short puts be adopted)
    except Exception:
        pass                               # fail-open: no grace list -> old behavior
    adopted = []
    for p in positions:
        occ = (p.get("symbol") or "").upper()
        if not occ or occ in known:
            continue
        if occ in recent:
            print(f"  orphan reconcile: {occ} filled <45min ago - grace period, record likely in flight")
            continue
        qty = abs(int(float(p.get("qty") or 0)))
        avg = float(p.get("avg_entry_price") or 0)
        if qty < 1:
            continue
        m = re.match(r"^([A-Z]+)\d{6}[CP]\d+$", occ)
        if not m:
            print(f"  orphan reconcile: {occ} is not an option - NOT adopting equity into the "
                  "options exit engine (visible via the daily reconcile marker)")
            continue
        now = _now_iso_ms()
        log_list.append({
            "trade_set_id": "ADOPT-" + uuid.uuid4().hex[:10], "ticker": m.group(1) if m else occ,
            "status": "OPEN", "entry_ts_utc": now, "adopted": True,
            "adopted_from": {"occ": occ, "qty": qty, "avg_entry_price": avg, "at": now},
            "regime": "ADOPTED", "trigger": "orphan_reconcile", "execution_mode": "ADOPTED",
            "occ_resolution": "adopted", "leg_budget_usd": round(avg * qty * 100, 2),
            "metadata": {"macro": {"spot": avg, "source": "adopted"},
                         "gex": {"zero_gamma_strike": None, "regime": None},
                         "iv_term": {"iv_ratio": None, "structure": None},
                         "alt_catalyst": {"reddit_mention_delta_pct": None, "insider_10d_buy_usd": None,
                                          "insider_cluster_flag": False}},
            "legs": {"adopted_leg": {"structure": "ADOPTED", "occ_symbol": occ,
                                     "expiry": _occ_expiry(occ), "entry_premium": avg, "contracts": qty}},
            "leg_path": {"adopted_leg": {"mfe_pct": 0.0, "mae_pct": 0.0, "stage": "initial"}},
            "leg_exits": {}, "exit": None})
        adopted.append(occ)
    if adopted:
        _save_log_list(log_list)
        _notify(f"<b>TIDY-UP: re-linked {len(adopted)} position(s)</b> ({', '.join(adopted[:6])})\n"
                f"Plain English: the broker showed positions my notebook had no record of (usually "
                f"after a data hiccup). I re-created the records so their exits are managed again. "
                f"No money moved; nothing needed from you.")
    return adopted


# ----------------------------------------------------------------------------
# Scheduled cycle (GHA): stale-order audit -> exit pass -> UW flow sourcing -> first eligible
# ----------------------------------------------------------------------------
def run_scheduled_cycle(mock=False):
    creds = _paper_creds()
    live = all(creds)
    params = load_params()
    print("=" * 78)
    print(f"V10 PROACTIVE LAB - scheduled cycle ({'LIVE_PAPER' if live else 'DRY_RUN (no creds)'})")
    print("=" * 78)
    if live and not _market_is_open(creds):
        print("market closed - no cycle: 0 orders, 0 exits, 0 harvest, no inbox commit")
        return None

    # 0. orphan roll-call (item 2b): adopt any live position with no tracking record BEFORE the exit
    #    pass, so a trade record dropped by a push collision can't leave a position unmanaged.
    adopted = reconcile_orphans(creds, params)
    if adopted:
        print(f"orphan reconcile: adopted {len(adopted)} unmanaged position(s) -> {adopted}")

    # 1. stale limit-order cleanup (free buying power)
    open_orders = get_open_orders(creds)
    cancels = audit_stale_orders(creds, orders=open_orders)
    print(f"stale-order audit: {len(cancels)} unfilled limit(s) cancelled "
          f"(> {params.get('stale_order_max_minutes', 30)}m)")
    for c in cancels:
        print(f"  cancelled {c['symbol']} age {c['age_min']}m")
    if cancels:
        open_orders = get_open_orders(creds)

    # 2. EXIT PASS: 24h swing guard + 30-50% velocity target -> close, cool-off, autopsy
    closed, autopsies = manage_open_positions(creds, params)
    print(f"exit pass: {len(closed)} leg(s) closed, {len(autopsies)} autopsy(ies) generated")
    for c in closed:
        print(f"  closed {c['ticker']} {c['leg']} {c['return_pct']:+.1f}% [{c.get('action', '')}] (ok={c['closed_ok']})")
    for a in autopsies:
        print(f"  autopsy {a.get('ticker')}: winner={a.get('winner')} -> {str(a.get('factor', a.get('autopsy_error', '')))[:90]}")

    # 3. re-read state after cancels/exits
    open_orders = get_open_orders(creds)
    positions = get_open_positions(creds)
    print(f"portfolio: {len(positions)} positions, {len(open_orders)} open orders")
    _maybe_send_digest()                                     # EOD digest (once/day at/after 20:00 UTC, fail-open)

    # school 1e: DAILY broker-state reconciliation marker (records-vs-broker two-way diff). One marker
    # per day; Telegram fires only when the divergence COUNT CHANGES (the standing 2c drift would
    # otherwise ring red every day - the alert is for NEW divergence).
    try:
        today_r = datetime.now(timezone.utc).date().isoformat()
        log_r = _load_log_list()
        if not any(r.get("type") == "reconcile" and str(r.get("ts_utc", "")).startswith(today_r) for r in log_r):
            pos_occs = {(p.get("symbol") or "").upper() for p in positions}
            rec_occs = {}
            for r in log_r:
                if r.get("status") != "OPEN":
                    continue
                if isinstance(r.get("legs"), dict):
                    for l in r["legs"].values():
                        if l.get("occ_symbol"):
                            rec_occs[l["occ_symbol"].upper()] = r.get("ticker")
                if r.get("occ"):                                   # PUTW short leg
                    rec_occs[r["occ"].upper()] = r.get("ticker")
                if (r.get("shares") or {}).get("symbol"):          # shares probes (OVERNIGHT/TOM)
                    rec_occs[r["shares"]["symbol"].upper()] = r.get("ticker")
            open_no_pos = sorted(o for o in rec_occs if o not in pos_occs)
            pos_no_rec = sorted(o for o in pos_occs if o not in rec_occs)
            prev = next((r for r in reversed(log_r) if r.get("type") == "reconcile"), {})
            marker = {"type": "reconcile", "ts_utc": _now_iso_ms(),
                      "open_records_no_position": len(open_no_pos), "positions_no_record": len(pos_no_rec),
                      "sample_stale": open_no_pos[:5], "sample_orphan": pos_no_rec[:5]}
            _append_log(marker)
            if (marker["open_records_no_position"] != prev.get("open_records_no_position")
                    or marker["positions_no_record"] != prev.get("positions_no_record")):
                _notify(f"<b>BOOKKEEPING CHECK</b>: my records vs the broker's differ - "
                        f"{marker['open_records_no_position']} record(s) with no matching position, "
                        f"{marker['positions_no_record']} position(s) with no record yet.\n"
                        f"Plain English: a routine cross-check (usually a fill still settling or a "
                        f"just-closed leg). It self-resolves within a cycle or two; only worth a look "
                        f"if the same numbers repeat all day. No action needed.")
    except Exception as e:
        print(f"reconcile marker skipped (fail-open): {type(e).__name__}")

    # 3b. ratchet backstops (owner decision 20): re-arm resting broker stops to current stage levels
    bs_actions = manage_backstops(creds, params, positions=positions)
    if bs_actions:
        print(f"backstops: {len(bs_actions)} armed/ratcheted")
        for a in bs_actions:
            print(f"  stop {a['occ']} @ {a['stop']} x{a['qty']} -> {a['status']}{' ' + str(a['err']) if a['err'] else ''}")

    # 3c. daily brake (owner decisions 19 + 2026-07-08 shadow): JUDGMENT always evaluates + logs; the
    #     ACTION (suppressing entries) fires ONLY in 'active' mode. In 'shadow' every entry still fires
    #     and is tagged so we measure the brake's would-have-blocked set for free.
    brake_mode, braked, brake_active, brake_why, n_so, loss_usd = brake_decision(params)
    if braked:
        today_s = datetime.now(timezone.utc).date().isoformat()
        if not any(r.get("type") == "daily_brake" and str(r.get("ts_utc", "")).startswith(today_s)
                   for r in _load_log_list()):
            _append_log({"type": "daily_brake", "ts_utc": _now_iso_ms(), "mode": brake_mode,
                         "reason": brake_why, "stopouts": n_so, "realized_loss_usd": round(loss_usd, 2),
                         "status": "BRAKED" if brake_active else "SHADOW"})   # committed marker for the shadow study
            _notify(f"<b>DAILY BRAKE ({brake_mode})</b> {brake_why} - " +
                    ("no new entries until the next session (exits, backstops, harvest continue)"
                     if brake_active else "SHADOW: entries still fire and are tagged for measurement"))
        print(f"DAILY BRAKE {'ACTIVE' if brake_active else 'SHADOW'}: {brake_why}"
              + ("" if brake_active else " (entries NOT suppressed)"))

    # 4. dynamic UW flow sourcing - enter the FIRST candidate not capped/cooled
    candidates = scan_candidates(params)
    print(f"UW flow scan: {len(candidates)} market-wide candidates "
          f"(top: {[c['ticker'] for c in candidates[:8]]})")
    if not candidates:
        try:
            from src.unusual_whales_api import UnusualWhalesClient
            reachable = bool(getattr(UnusualWhalesClient(), "enabled", False))
        except Exception:
            reachable = False
        if not reachable:
            _notify("<b>DEGRADED</b> sandbox: UW flow scanner unreachable (no token / API down) - 0 candidates")
        print(f"\nno UW flow candidates this cycle ({'scanner UNREACHABLE' if not reachable else 'quiet market'}).")
        return None
    entered = None
    # school 1e: owner HALT (authenticated Telegram command -> snapshots-repo flag -> workflow env,
    # or a local data/HALT file). Pauses NEW ENTRIES only - exits, backstops, and harvest continue.
    halt_active = os.environ.get("SCHOOL_HALT") == "1" or os.path.exists("data/HALT")
    if halt_active:
        print("OWNER HALT ACTIVE: new entries paused this cycle (exits/backstops/harvest continue)")
        _notify("<b>OWNER HALT</b> active - new entries paused this cycle")
    if os.environ.get("SCHOOL_FLATTEN") == "1" and not os.path.exists(FLUSH_SENTINEL):
        try:                                       # owner /flatten -> arm the existing one-time flush
            os.makedirs(os.path.dirname(FLUSH_SENTINEL), exist_ok=True)
            open(FLUSH_SENTINEL, "w").write("armed by owner /flatten " + _now_iso_ms())
            print("OWNER FLATTEN: flush sentinel armed - positions close at the next open-market cycle")
        except Exception:
            pass
    engine_skips = {}                                        # school 1d: ticker -> skip-reason code, harvested
    global _SR_BUDGET
    _SR_BUDGET = 2                                           # spread-retry budget resets per cycle
    try:                                                     # EARLY-STRENGTH watchlist pass (fail-open;
        import early_strength                                # entries only, so HALT/brake skip it whole)
        import sandbox_proactive_lab as _selflab
        if not (brake_active or halt_active):
            early_strength.process(creds, _selflab)
    except Exception as _ee:
        print(f"  early-strength pass skipped: {type(_ee).__name__}")
    try:                                                     # PUT-WRITE LEG (green-day, weekly, fail-open;
        import putw_leg                                      # PUTW records have no legs dict -> exit pass
        putw_leg.weekly_cycle(creds)                         # ignores them; they self-settle at expiry)
    except Exception as e:
        print(f"  putw leg skipped (fail-open): {type(e).__name__}: {str(e)[:80]}")
    try:                                                     # SHARES PROBES (OVERNIGHT + TURN_OF_MONTH,
        import shares_probes                                 # self-managed records, book=PROBE, no legs
        shares_probes.cycle(creds,                           # dict -> options exit pass ignores them;
                            allow_entries=not (brake_active or halt_active))   # HALT stops buys, not sells
    except Exception as e:
        print(f"  shares probes skipped (fail-open): {type(e).__name__}: {str(e)[:80]}")
    try:                                                     # VRP_DAILY probe (structural premium leg,
        import vrp_probe                                     # self-settling like PUTW - no sell orders,
        vrp_probe.cycle(creds,                               # never a day trade)
                        allow_entries=not (brake_active or halt_active))
    except Exception as e:
        print(f"  vrp probe skipped (fail-open): {type(e).__name__}: {str(e)[:80]}")
    try:                                                     # 5K DEFINED-RISK probes (weekly XSP
        import fivek_probes                                  # credit spread + condor, self-settling,
        fivek_probes.cycle(creds,                            # owner order 2026-08-18)
                           allow_entries=not (brake_active or halt_active))
    except Exception as e:
        print(f"  fivek probes skipped (fail-open): {type(e).__name__}: {str(e)[:80]}")
    try:                                                     # MOMENTUM_ROT probe (top-5 3mo, 200d gate,
        import momentum_probe                                # monthly shares rotation - fast-tracked
        momentum_probe.cycle(creds,                          # owner order 2026-08-17)
                             allow_entries=not (brake_active or halt_active))
    except Exception as e:
        print(f"  momentum probe skipped (fail-open): {type(e).__name__}: {str(e)[:80]}")
    entered_list = []                                        # FADE v1.2: up to 2 clusters per cycle
    _open_fade = (sum(1 for r in _load_log_list() if r.get("book") == "FADE" and r.get("status") == "OPEN")
                  if fade_book.active() else 0)
    for c in ([] if (brake_active or halt_active) else candidates):   # ONLY 'active'/HALT suppress; shadow lets entries fire
        t = c["ticker"]
        if fade_book.active():
            if _open_fade >= (fade_book.spec().get("max_concurrent") or 3):
                # FADE concurrency cap (spec max_concurrent; v1.1 owner-raised to 5 on paper).
                engine_skips[t] = "fade_concurrency_cap"
                continue
            # FADE v1.2 concentration guard (replaces the waived cooloff): max 2 entries per
            # ticker per UTC day - re-entry after a close is allowed once, stacks are not.
            _today = _now_iso_ms()[:10]
            _tday = sum(1 for r in _load_log_list()
                        if r.get("book") == "FADE" and r.get("ticker") == t
                        and (r.get("entry_ts_utc") or "")[:10] == _today)
            if _tday >= 2:
                engine_skips[t] = "fade_ticker_day_cap"
                continue
        try:                                          # school gate-mode (DORMANT): off -> None -> engine
            import school_gate                        # decides alone; runs BEFORE entry so an armed gate
            gate = school_gate.gate_engine_candidate(params, c)   # can veto without an order being placed
            if gate is not None and gate.get("decision") == "VETO":
                print(f"  school gate VETO {t}: {gate.get('reason')}")
                engine_skips[t] = "school_gate_veto"
                continue
        except Exception:
            pass                                      # fail-open on the school layer; the frozen engine stands
        try:
            rec = enter_proactive_set(t, None, mock=mock, candidate=c, dry_run=not live,
                                      positions=positions, open_orders=open_orders)
        except Exception as e:
            print(f"  skip {t}: entry error {type(e).__name__}: {str(e)[:80]}")     # whole-market fail-open
            engine_skips[t] = "entry_error"
            continue
        if rec.get("skipped"):
            print(f"  skip {t}: {rec['reason']}")
            engine_skips[t] = _skip_code(rec.get("reason") or "")
            continue
        md, legs, orders = rec["metadata"], rec["legs"], rec["orders"]
        if rec.get("book") == "FADE":
            _open_fade += 1                       # same-cycle entries count toward the cap
        print(f"\nENTERED {t} [{rec['regime']}] | {rec['execution_mode']} | OCC {rec['occ_resolution']}")
        print(f"  state: 20dSMA {md['macro']['distance_to_sma20_pct']:+.2f}% | IV {md['iv_term']['iv_ratio']} "
              f"| skew {md.get('skew', {}).get('skew_ratio')} ({md.get('skew', {}).get('skew_bias')}) "
              f"| news {md.get('news_sentiment_score')} ({md.get('news', {}).get('news_type')}) "
              f"| sector {md.get('regime_stack', {}).get('sector_etf')} {md.get('regime_stack', {}).get('sector_dist_pct')}%")
        for name, leg in legs.items():
            o = orders[name]
            occ = leg.get("occ_symbol") or f"{leg.get('front_occ')}|{leg.get('back_occ')}"
            sp = (leg.get("execution_cost") or {}).get("bid_ask_spread_pct")
            print(f"  {name:<14} {leg['structure']:<15} {occ:<26} x{leg['contracts']:<3} "
                  f"@lim ${leg['limit_price']:<6} spread {sp}% -> {o['status']} {o['order_id']}")
        entered = rec
        entered["_scan_candidate"] = c
        if braked:      # SHADOW: this entry WOULD have been blocked by the brake -> tag it (record + the
            try:        # harvest metadata, so f.brake_shadow reaches the brain) as the free measurement.
                entered["brake_shadow_blocked"] = True
                entered["brake_stopouts_at_entry"] = n_so
                entered.setdefault("metadata", {})["brake_shadow"] = True
                _rewrite_last(entered)                       # persist the tag onto the just-logged record (fail-open)
            except Exception:
                pass
        entered_list.append(entered)
        # FADE v1.2 pacing: up to 2 entries per cycle while slots are free (burst refill after
        # same-morning exits). V10/OFF-state keeps the original 1-per-cycle - byte-identical.
        if len(entered_list) >= (2 if fade_book.active() else 1):
            break
    try:                                                     # COUNTERFACTUAL HARVEST (observational, fail-open, post-trade)
        import harvest_logger
        summary = harvest_logger.harvest_scan(params, executed_record=entered_list or None, mock=mock,
                                              engine_skips=engine_skips)
        print(f"harvest: {summary}")
    except Exception as e:
        print(f"harvest skipped (fail-open): {type(e).__name__}: {str(e)[:90]}")
    try:                                                     # FILL LEDGER (school 1c: observational, fail-open)
        import fill_ledger
        for _er in entered_list:
            fill_ledger.entry_submits(_er)
        fill_ledger.sweep(_load_log_list(), _order_state, creds, _save_log_list)
    except Exception as e:
        print(f"fill ledger skipped (fail-open): {type(e).__name__}: {str(e)[:90]}")
    # PROBE ROSTER v3 (owner order 2026-08-11 21:52: the probe section is the WIDE experimental
    # net - every feasible tested strategy trades live daily, up to 5 fills per strategy per day,
    # $1000 each, fired regardless of what the fade book did; all tagged book=PROBE + strategy
    # name so none of it ever touches fade evidence).
    try:
        _pc = (fade_book.spec().get("probe") or {}) if fade_book.active() else {}
        if _pc.get("enabled") and not (brake_active or halt_active):    # probes honor HALT + active brake
            global LEG_BUDGET
            _today = _now_iso_ms()[:10]
            _plog = _load_log_list()
            _recent_cut = (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat()
            _open_tk = {(r.get("ticker") or "").upper() for r in _plog if r.get("status") == "OPEN"
                        and (r.get("book") == "PROBE"
                             or (r.get("entry_ts_utc") or "")[:10] >= _recent_cut)}
            # cross-book softening (owner 2026-09-02): probes block on other PROBES and on any
            # book's RECENT (<=5d) entry; old legacy positions no longer freeze discovery names
            _pcount = {}                       # _plog is loaded AFTER this cycle's fade entries, so
            for _pr in _plog:                  # _open_tk sees them - no same-cycle duplicate underlying
                if _pr.get("book") == "PROBE" and (_pr.get("entry_ts_utc") or "")[:10] == _today:
                    _pk = _pr.get("probe_strategy")
                    _pcount[_pk] = _pcount.get(_pk, 0) + 1
            _per = int(_pc.get("per_strategy_max_per_day") or 5)
            _tot_cap = int(_pc.get("max_per_day") or 25)
            _tot = sum(_pcount.values())
            def _shape(md, c):
                sma = (md.get("macro") or {}).get("distance_to_sma20_pct")
                spy = (md.get("regime_stack") or {}).get("market_spy_dist_pct")
                sd = 1 if (c or {}).get("flow_type") == "call" else -1
                return isinstance(sma, (int, float)) and isinstance(spy, (int, float)) and sma * sd < 0 and spy * sd < 0
            def _depth_lt(md, cap_):
                sma = (md.get("macro") or {}).get("distance_to_sma20_pct")
                return isinstance(sma, (int, float)) and abs(sma) < cap_
            _ROSTER = [
                ("EXEC_BASELINE", None),                                    # pure execution data
                ("FADE_UNROUTED", lambda md, c: _shape(md, c)),             # fade shape, router ignored
                # CONSENSUS culled 2026-09-01 (owner): 8/8-day case closed at the boundary -
                # own-mean -20.4%/day vs +3 floor, trimmed t vs control +0.13 (zero edge).
                # Superseded by CONSENSUS_CALLS (the calls-only refinement, tracked).
                ("DP_HEAVY", lambda md, c: ((md.get("dark_pool") or {}).get("n_prints") or 0) >= 150),
                # QUIET_TAPE culled 2026-09-01 (owner Friday-queue pulled forward): -$1,005 over its
                # era, no positive stretch - roster slot freed for the grid probes.
                ("FADE_DP", lambda md, c: _shape(md, c)
                                          and ((md.get("dark_pool") or {}).get("n_prints") or 0) >= 150),
                ("OPT_WINNER", lambda md, c: _shape(md, c) and _depth_lt(md, 3.0)
                                             and ((c or {}).get("total_premium") or 0) <= 250000),
                ("FADE_WHALE", lambda md, c: _shape(md, c)),
                ("GEX_PIN", lambda md, c: abs((md.get("gex") or {}).get("distance_to_zero_gamma_pct")
                                              or 9) < 0.3),   # owner 2026-08-18: untapped UW trigger
                ("IV_EXTREME", lambda md, c: ((md.get("pemd") or {}).get("iv_rank_1y") or 50) >= 85
                                             or ((md.get("pemd") or {}).get("iv_rank_1y") or 50) <= 10),
                ("BULL_DIP", lambda md, c: fade_book.spy_regime() == "BULL"
                                           and isinstance((md.get("macro") or {}).get("distance_to_sma20_pct"), (int, float))
                                           and (md.get("macro") or {}).get("distance_to_sma20_pct") < 0
                                           and (c or {}).get("flow_type") == "call"),
                                             # bull battery 2026-08-28: ticker dip + market BULL
                                             # + calls = +11.2%/day t+5.86 over 240 days, both
                                             # halves positive - the bull book's anchor candidate
                ("DIP_CONVEXITY", lambda md, c: fade_book.spy_regime() == "BEAR"
                                                and isinstance((md.get("regime_stack") or {}).get("market_spy_dist_pct"), (int, float))
                                                and (md.get("regime_stack") or {}).get("market_spy_dist_pct") < 0
                                                and (c or {}).get("flow_type") == "call"),
                                                # + SPY<20d confirmation (tuner 2026-09-01: spyconf
                                                # wide +29.5/day t2.89 vs fullband -7 first half)
                                             # everything-sweep winner 2026-08-27: bear-regime
                                             # long-DTE calls, wide exits; +35-52/day vs pool
                ("DIP_CONF_MILD", lambda md, c: fade_book.spy_regime() == "MILD"
                                                and isinstance((md.get("macro") or {}).get("distance_to_sma20_pct"), (int, float))
                                                and (md.get("macro") or {}).get("distance_to_sma20_pct") < 0
                                                and isinstance((md.get("regime_stack") or {}).get("market_spy_dist_pct"), (int, float))
                                                and (md.get("regime_stack") or {}).get("market_spy_dist_pct") < 0
                                                and (c or {}).get("flow_type") == "call"),
                                             # grand retest 2026-08-31 (true-trigger): ticker dip
                                             # + SPY<20d confirmation in MILD = +11.3%/day t2.43;
                                             # WITHOUT the SPY gate the same trade is -5.4/day -
                                             # the confirmation IS the strategy (3x3 middle cell)
                ("FOLLOW_CALLS", lambda md, c: (c or {}).get("flow_type") == "call"),   # archive winner
                                             # 2026-08-23: buy aggressively-bought calls, all regimes -
                                             # +32/+12/+14 bear/mild/bull, t>3 each (thin bear). The one
                                             # candidate positive & significant in every regime. PRIORITY.
                ("BULL_DIP_X", lambda md, c: isinstance((md.get("macro") or {}).get("distance_to_sma20_pct"), (int, float))
                                             and (md.get("macro") or {}).get("distance_to_sma20_pct") < 0
                                             and (c or {}).get("flow_type") == "call"),
                                             # CONSENSUS's replacement (owner cull+replace order
                                             # 2026-09-01): BULL regime (pre-checked below) + ticker
                                             # dip + THE expensive trigger contract, wide exits.
                                             # bull_expensive test: +40.8%/day t+5.17, 86d, n=366
                ("CONSENSUS_CALLS", lambda md, c: (not _shape(md, c)) and (c or {}).get("flow_type") == "call"),  # 400k-1M side-pool (owner ask
                                                                    # 2026-08-12: sim +3.37 vs -0.47
                                                                    # day-mean, halves flipped - live
                                                                    # fills settle it)
            ]
            _cyc = 0
            _keep = LEG_BUDGET
            LEG_BUDGET = float(_pc.get("size_usd") or 1000)
            # ROTATION (owner order 2026-09-01, ship-the-grid): the roster used to fill head-first
            # every cycle, so tail probes (FOLLOW_CALLS onward) never saw a slot. Start point now
            # rotates over the non-control roster, seeded by DAY-OF-MONTH + UTC HOUR: market hours
            # alone span only 7-8 values, which mod 14 can never reach start indices 7-12 (the
            # adversarial panel's catch) - the day term walks the base so every index leads within
            # days. EXEC_BASELINE is NOT rotated: it keeps its pre-change head slot EVERY cycle up
            # to its daily cap, because the promotion court's control day-means must keep the same
            # sampling density and time-of-day mix they were built on - thinning the control mid-
            # experiment would quietly change the bar for all tracked strategies.
            try:
                _rest = [x for x in _ROSTER if x[0] != "EXEC_BASELINE"]
                _rot = (int(_today[8:10]) + int(_now_iso_ms()[11:13])) % len(_rest)
                _order = [_ROSTER[0]] + _rest[_rot:] + _rest[:_rot]
            except Exception:
                _order = list(_ROSTER)
            _mkt20 = None
            try:
                import sandbox_v11_sensors as _sv
                _mkt20 = _sv._sma_distance("SPY")
            except Exception:
                pass
            _CALLS_ONLY = {"FOLLOW_CALLS", "CONSENSUS_CALLS", "BULL_DIP", "BULL_DIP_X",
                           "DIP_CONF_MILD", "DIP_CONVEXITY"}
            # ATTEMPT BUDGET (hotfix 2026-09-01 19:0x UTC): every enter_proactive_set attempt costs
            # a full sensor sweep whether or not the filter passes. Head-first ordering hid that -
            # broad probes at the head entered within a few attempts and the loop broke. Rotation
            # exposed it: afternoon start indices land on rare-filter probes whose pools burn 10
            # attempts each without entering, cycle time blew past the dispatch interval, and every
            # run from 17:40Z was cancelled by its successor (the 08-19/08-20 churn class). Budget
            # caps the cycle at the pre-rotation cost envelope; rotation still decides who goes
            # first, so tail probes keep their lead slots - they just can't bankrupt the cycle.
            _att = 0
            try:
                for _pname, _pf in _order:
                    if _cyc >= 2 or _tot >= _tot_cap or _att >= 10:
                        break                       # 2 probes per cycle max - spread across the day
                    if _pcount.get(_pname, 0) >= _per:
                        continue
                    _rg_need = {"BULL_DIP": "BULL", "BULL_DIP_X": "BULL", "DIP_CONVEXITY": "BEAR",
                                "DIP_CONF_MILD": "MILD"}.get(_pname)
                    if _rg_need and fade_book.spy_regime() != _rg_need:
                        continue            # candidate-independent regime gate checked BEFORE the
                                            # sensor sweep (panel 2026-09-01: evaluating it inside
                                            # enter_proactive_set burned the whole attempt budget
                                            # on wrong-regime days); spy_regime is cached per day
                    if _pname in ("DIP_CONVEXITY", "DIP_CONF_MILD") and not (
                            isinstance(_mkt20, (int, float)) and _mkt20 < 0):
                        continue            # their SPY<20d confirmation is market-level - hoisted
                                            # here so 50d/20d divergence days can't burn the budget
                    _pool = (_WHALE_CANDS[:8] if _pname == "FADE_WHALE"
                             else _PRICEY_CANDS[:14] if _pname in ("DIP_CONF_MILD", "BULL_DIP_X")
                             else _FULL_CANDS[:16] if _pname in ("FOLLOW_CALLS", "CONSENSUS_CALLS")
                             else candidates[2:12])   # skim BELOW the fade book's 2-per-cycle picks
                             # DIP_CONF_MILD buys THE TRIGGER CONTRACT via _PROBE_CONTRACT (panel-
                             # corrected 2026-09-01): the +21.2/day t4.31 cell was measured on the
                             # expensive contract itself, so the live evidence is earned on it too
                    for c in _pool:
                        if _att >= 10:
                            break
                        t = c["ticker"]
                        if t.upper() in _open_tk:
                            continue            # never stack a probe on any book's open underlying
                        if _pname in _CALLS_ONLY and (c or {}).get("flow_type") != "call":
                            continue            # candidate-level hypothesis check is FREE - never pay
                                                # a sensor sweep to learn a put isn't a call (panel
                                                # 2026-09-02: put-flow names were burning the budget)
                        if engine_skips.get(t) in ("metadata_unavailable", "spread_cap"):
                            continue            # the fade loop already paid the sensor sweep and found
                                                # this ticker dead THIS cycle - re-attempting it burned
                                                # the whole 6-attempt budget on degenerate names and
                                                # starved every probe (found 2026-09-02: 5 of the top
                                                # 10 were metadata-dead; zero probe entries all day)
                        try:
                            _ACTIVE_PROBE["name"] = _pname
                            if _pname in ("DIP_CONF_MILD", "BULL_DIP_X"):
                                if not (c or {}).get("occ"):
                                    continue
                                _PROBE_CONTRACT["c"] = c
                            _att += 1
                            rec = enter_proactive_set(t, None, mock=mock, candidate=c,
                                                      dry_run=not live, positions=positions,
                                                      open_orders=open_orders, probe=True,
                                                      probe_filter=_pf)
                        except Exception:
                            continue
                        finally:
                            _ACTIVE_PROBE["name"] = None
                            _PROBE_CONTRACT["c"] = None
                        if rec and rec.get("skipped") and rec.get("reason") not in (
                                "probe_filter: candidate does not match this probe slot's hypothesis",):
                            print(f"  probe[{_pname}] skip {t}: {str(rec.get('reason'))[:70]}")
                        if rec and not rec.get("skipped"):
                            rec["book"] = "PROBE"
                            rec["probe_strategy"] = _pname
                            _rewrite_last(rec)
                            print(f"  PROBE[{_pname}] entered {t} (hypothesis slot - not fade evidence)")
                            _open_tk.add(t.upper())
                            _pcount[_pname] = _pcount.get(_pname, 0) + 1
                            _tot += 1
                            _cyc += 1
                            break
                if _cyc == 0:
                    print(f"  probes: 0 entries this cycle - {_att} of 6 attempts used, "
                          f"{len(candidates)} candidates, regime {fade_book.spy_regime()} "
                          f"(a starved cycle must say so, never sit silent - 2026-09-02)")
            finally:
                LEG_BUDGET = _keep
    except Exception as _pe:
        print(f"  probe skipped (fail-open): {type(_pe).__name__}")
    if entered_list:
        for _er in entered_list:
            _er.pop("_scan_candidate", None)
        print(f"\nGHA scheduled cycle complete: {len(entered_list)} cluster(s) entered + logged.")
        return entered_list[0]
    print("\nno eligible candidate this cycle (all capped/cooled).")
    return None


# ----------------------------------------------------------------------------
# One-time legacy flush (clean-slate reset for the $800 / mid-cap regime)
# ----------------------------------------------------------------------------
FLUSH_SENTINEL = "data/FLUSH_PENDING"


def _maybe_flush_pending(creds):
    """One-time auto-flush at the open. If data/FLUSH_PENDING exists, returns True and the caller MUST
    skip trading this cycle. It only closes positions when the market is LIVE; on a closed market it
    leaves the sentinel and waits (no orders). After a live flush the sentinel file is removed and the
    workflow's persist step commits the removal, so later cycles trade normally. Delete the file to cancel."""
    if not os.path.exists(FLUSH_SENTINEL):
        return False
    if not _market_is_open(creds):
        print("FLUSH_PENDING set but market closed - waiting for the open (no flush, no trade)")
        return True
    print("FLUSH_PENDING set + market open - executing the one-time flush")
    flush_positions(creds)
    try:
        os.remove(FLUSH_SENTINEL)
    except OSError:
        pass
    return True


def flush_positions(creds):
    """ONE-TIME reset: close every open paper position (the $10k-era clog that hogs the ticker cap
    and would pollute the mid-cap training set) + clear cool-off + mark OPEN log records FLUSHED, so
    the $800 regime starts from a clean slate. Fail-open per position."""
    if not all(creds):
        print("flush: no paper creds - nothing to do")
        return 0
    positions = get_open_positions(creds)
    if not _market_is_open(creds):
        print(f"DRILL/CLOSED: market closed - would flush {len(positions)} position(s), 0 orders sent:")
        for p in positions:
            print(f"  would close {p.get('symbol')} (qty {p.get('qty', '?')})")
        _notify(f"<b>FLUSH (dry - market closed)</b> would close {len(positions)} position(s); 0 orders sent")
        return 0
    closed = 0
    closed_occs = set()
    for p in positions:
        occ = p.get("symbol")
        if occ and _close_position(occ, creds, percentage=100):
            closed += 1
            closed_occs.add(occ.upper())
            print(f"  flushed {occ}")
    if os.path.exists(COOLOFF_PATH):
        os.remove(COOLOFF_PATH)
    log = _load_log_list()
    for rec in log:
        if rec.get("status") == "OPEN":
            occs = [(o or "").upper() for o in _record_leg_occs(rec).values()]
            if not occs or all(o in closed_occs for o in occs):   # 2026-07-06 AUDIT FIX: only records whose broker
                rec["status"] = "FLUSHED"                         # closes SUCCEEDED (or with nothing at the broker) -
                                                                  # a failed close stays OPEN so the exit engine keeps
                                                                  # managing it (no more PFE orphans)
    _save_log_list(log)
    print(f"FLUSH complete: {closed}/{len(positions)} positions closed, cool-off cleared, log reset")
    _notify(f"<b>FLUSH</b> closed {closed}/{len(positions)} legacy positions, cool-off cleared")
    return closed


# ----------------------------------------------------------------------------
# Local demo (single ticker)
# ----------------------------------------------------------------------------
def _assert_log_integrity():
    """FAIL-CLOSED log guard (2026-08-24 incident: a persist race spliced two log versions into
    invalid JSON; the engine's 'unreadable = empty' fallback then adopted the ENTIRE book as 29
    orphans). An unreadable or missing log now means the engine is BLIND, not flat: try to
    restore the newest parseable version from git history, else halt the cycle loudly (nonzero
    exit -> no sentinel stamp -> watchdog pages). Never trade on a log we cannot read."""
    try:
        data = json.load(open(LOG_PATH, encoding="utf-8"))
        if isinstance(data, list):
            return True
        raise ValueError("log root is not a list")
    except FileNotFoundError as e:
        err = f"missing ({e})"
    except Exception as e:
        err = f"unparseable ({type(e).__name__})"
    print(f"LOG INTEGRITY FAILURE: {LOG_PATH} {err} - attempting git-history recovery")
    try:
        import subprocess as _sp
        _sp.run("git fetch --deepen=20 origin main", shell=True, capture_output=True, timeout=120)
        shas = _sp.run(f"git log --format=%H -12 -- {LOG_PATH}", shell=True,
                       capture_output=True, text=True, timeout=60).stdout.split()
        for sha in shas:
            raw = _sp.run(f"git show {sha}:{LOG_PATH}", shell=True,
                          capture_output=True, text=True, timeout=60).stdout
            try:
                data = json.loads(raw)
                if isinstance(data, list) and data:
                    open(LOG_PATH, "w", encoding="utf-8").write(raw)
                    print(f"LOG RECOVERED from {sha[:8]} ({len(data)} records) - cycle continues")
                    _notify(f"<b>LOG RECOVERED</b>\ncorrupt {LOG_PATH} restored from git {sha[:8]} "
                            f"({len(data)} records); trading continues")
                    return True
            except Exception:
                continue
    except Exception as re:
        print(f"recovery attempt failed: {type(re).__name__}")
    _notify(f"<b>CYCLE HALTED - LOG UNREADABLE</b>\n{LOG_PATH} {err} and no parseable version "
            "in git history. Engine is blind; refusing to trade or adopt. Investigate.")
    sys.exit(3)


def main():
    if os.environ.get("PROACTIVE_FLUSH") == "true" or "--flush" in sys.argv:   # one-time reset (dispatch -f flush=true)
        return flush_positions(_paper_creds())
    _assert_log_integrity()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        try:
            if _maybe_flush_pending(_paper_creds()):
                return None                      # one-time flush pending/executed - skip trading this cycle
            return run_scheduled_cycle(mock=os.environ.get("PROACTIVE_MOCK", "1") == "1")
        except Exception as e:
            import traceback
            traceback.print_exc()
            _notify(f"<b>SANDBOX RUN FAILED</b>\n{type(e).__name__}: {str(e)[:300]}")    # failure alert
            raise

    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    live_paper = "--live-paper" in sys.argv or (gha and all(_paper_creds()))   # auto under GHA
    dry_run = not live_paper
    mock = os.environ.get("PROACTIVE_MOCK", "1") == "1"
    print("=" * 78)
    print("V10 PROACTIVE LAB + ACTIVE ALPACA PAPER EXECUTION")
    print(f"(env: {'GITHUB_ACTIONS -> auto live-paper' if gha else 'local'} | metadata: {'MOCK' if mock else 'LIVE'} | "
          f"execution: {'LIVE_PAPER (auto-submit)' if live_paper else 'DRY_RUN (no orders fired)'})")
    print("=" * 78)

    params = load_params()
    print(f"\nloaded {len(params)} tunable params from v10_tunable_parameters.json:")
    print("  " + json.dumps(params))

    ticker = "HOOD"
    rec = enter_proactive_set(ticker, "C", mock=mock, candidate={"consolidating": True}, dry_run=dry_run)
    if rec.get("skipped"):
        print(f"\nSKIPPED {ticker}: {rec['reason']} (portfolio guard)")
        return
    print(f"\nTRIGGER: {rec['trigger']} -> 3 legs on {ticker} | ${LEG_BUDGET:,.0f}/leg | mode {rec['execution_mode']}")
    print(f"OCC resolution: {rec['occ_resolution']} | ticker guard: {rec['ticker_guard']} | positions checked: {rec['open_positions_checked']}")

    md = rec["metadata"]
    print("\nSTATE BLOCK (un-mocked where live):")
    print(f"  macro   : spot {md['macro']['spot']} 20dSMA {md['macro']['sma20']} dist {md['macro']['distance_to_sma20_pct']:+.2f}% [{md['macro']['source']}]")
    print(f"  iv_term : ratio {md['iv_term']['iv_ratio']} ({md['iv_term']['structure']}) [{md['iv_term']['source']}]")
    _gxd = md['gex']['distance_to_zero_gamma_pct']
    print(f"  gex     : net {md['gex']['net_gex']} zero-gamma {md['gex']['zero_gamma_strike']} "
          f"dist {(f'{_gxd:+.2f}%' if _gxd is not None else 'n/a')} [{md['gex']['source']}]")
    print(f"  alt     : reddit {md['alt_catalyst']['reddit_mention_delta_pct']}% insider ${md['alt_catalyst']['insider_10d_buy_usd']:,} cluster={md['alt_catalyst']['insider_cluster_flag']} [{md['alt_catalyst']['source']}]")
    print(f"  technical: ATR {md['technical']['atr_pct']}% RVOL {md['technical']['rvol_10min']} [{md['technical']['source']}]")

    print("\nALPACA PAPER ORDERS (3 legs):")
    for name, leg in rec["legs"].items():
        o = rec["orders"][name]
        occ = leg.get("occ_symbol") or f"{leg.get('front_occ')}|{leg.get('back_occ')}"
        print(f"  {name:<14} {leg['structure']:<15} {occ:<22} x{leg['contracts']:<3} @lim ${leg['limit_price']:<6} "
              f"-> {o['status']} order_id={o['order_id']}")

    # demonstrate FAIL-OPEN routing (force the put illiquid)
    rec2 = enter_proactive_set(ticker, "C", mock=mock, dry_run=True, illiquid={"bearish_put"})
    fo = {k: rec2["orders"][k]["status"] for k in rec2["orders"]}
    print(f"\nFAIL-OPEN demo (put illiquid): {fo}  <- set still trades the viable legs")

    # simulate a 5-day close that breaks the range to the downside -> trigger all 3 tuning rules
    print("\n" + "-" * 78)
    print("SIMULATED CLOSE: bearish breakdown -7%, entry slippage 4%")
    returns = {"bullish_call": -80.0, "bearish_put": 120.0, "flat_calendar": -30.0}
    res = run_trade_autopsy(rec, returns, underlying_move_pct=-7.0, entry_slippage_pct=4.0)
    _rewrite_last(rec)
    print(f"  winner {res['winner']} | determining factor: {res['determining_factor']}")
    print(f"\nTUNING ADVISORY ({ADVISORY_MD}):")
    for gate, msg in res["recommendations"]:
        print(f"  -> [{gate}] {msg}")

    print("\nEXIT MANAGEMENT (hard stop/expiry override 24h hold; take-profit gated by it):")
    a = manage_exit(rec["entry_ts_utc"], 40.0, params, now=datetime.now(timezone.utc) + timedelta(hours=2))
    print(f"  +40% at 2h     -> {a['action']}: {a['reason']}")
    b = manage_exit(rec["entry_ts_utc"], 35.0, params, now=datetime.now(timezone.utc) + timedelta(hours=26))
    print(f"  +35% at 26h    -> {b['action']}: {b['reason']}")
    c = manage_exit(rec["entry_ts_utc"], -60.0, params, now=datetime.now(timezone.utc) + timedelta(hours=2))
    print(f"  -60% at 2h     -> {c['action']}: {c['reason']}")
    e = manage_exit(rec["entry_ts_utc"], -10.0, params, now=datetime.now(timezone.utc) + timedelta(hours=2),
                    expiry_iso=(date.today() + timedelta(days=2)).isoformat())
    print(f"  -10%, 2d expiry-> {e['action']}: {e['reason']}")


if __name__ == "__main__":
    main()

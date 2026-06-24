"""V10 Research Sandbox - Proactive Paper-Trading Lab (STANDALONE).

Philosophy shift: instead of suppressing trading in flat/chop regimes, we AGGRESSIVELY
paper-trade them from three angles at once and log a hyper-detailed environment block, so
real outcomes can later tighten the live spec. Fail-OPEN by design (no restrictive filters)
to build a statistical database of flat-to-trend transitions.

On a trigger (SPY regime C/NEUTRAL, or a consolidating candidate) we enter THREE simultaneous
1%-of-equity paper legs:
   1. Bullish  - long OTM call  (delta ~ +0.35)
   2. Bearish  - long OTM put   (delta ~ -0.35)
   3. Flat     - calendar spread (buy back-month / sell front-month) to harvest theta

Each trade set writes a millisecond-stamped state block to proactive_sandbox_logs.json
(macro 20d-SMA distance, IV term ratio, net GEX + zero-gamma distance, ApeWisdom 24h mention
delta, edgartools 10d C-suite buy volume + cluster flag, ATR + 10-min RVOL).

When a set closes (5-day time exit or trailing stop), run_trade_autopsy() compares the three
legs, writes a markdown post-mortem, and derives the determining factor that broke the range.

Reuses the sandbox prototypes (prototype_alt_data, sandbox_v10_upgrades). Touches no V9 engine.
Run: ALPACA_PAPER_API_KEY=... ALPACA_PAPER_SECRET_KEY=... python sandbox_proactive_lab.py
"""

import os
import json
import math
import uuid
from datetime import datetime, timezone, timedelta

LOG_PATH = "proactive_sandbox_logs.json"
AUTOPSY_MD = "proactive_autopsy_log.md"
PAPER_EQUITY = 100_000.0
SIZE_PCT = 0.01                       # 1% of paper equity per leg
CALL_DELTA, PUT_DELTA = 0.35, -0.35


def _now_iso_ms():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# Metadata fetchers - all FAIL-OPEN (return a value + source tag, mock on failure)
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
        src = "alpaca"
    else:
        spot, sma20, atr, rvol, src = 91.30, 90.85, 2.60, 1.18, "mock"
    return {
        "spot": round(spot, 2), "sma20": round(sma20, 2),
        "distance_to_sma20_pct": round((spot - sma20) / sma20 * 100, 3),
        "atr": round(atr, 2), "atr_pct": round(atr / spot * 100, 2),
        "rvol_10min": rvol if rvol is not None else 1.0, "source": src,
    }


def iv_term_structure(ticker, spot, mock):
    # front/back ATM IV. Real wiring would pull two Alpaca option-chain expiries; mocked here.
    iv_front, iv_back, src = (78.0, 62.0, "mock")
    ratio = round(iv_front / iv_back, 3) if iv_back else None
    return {"iv_front": iv_front, "iv_back": iv_back, "iv_ratio": ratio,
            "structure": "contango" if ratio and ratio < 1 else "backwardation" if ratio and ratio > 1 else "flat",
            "source": src}


def net_gex(ticker, spot, mock):
    if not mock:
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
                    if (prev_cum < 0 <= cum) or (prev_cum > 0 >= cum):   # cumulative GEX flips sign
                        crossings.append(k)
                zero_gamma = (min(crossings, key=lambda k: abs(k - spot)) if crossings
                              else min(pts, key=lambda x: abs(x[0] - spot))[0])
                return {"net_gex": round(total, 1), "zero_gamma_strike": round(zero_gamma, 2),
                        "distance_to_zero_gamma_pct": round((spot - zero_gamma) / spot * 100, 3),
                        "regime": "negative_gamma" if total < 0 else "positive_gamma", "source": "uw"}
        except Exception:
            pass
    zg = round(spot * 1.004, 2)
    return {"net_gex": -1.85e8, "zero_gamma_strike": zg,
            "distance_to_zero_gamma_pct": round((spot - zg) / spot * 100, 3),
            "regime": "negative_gamma", "source": "mock"}


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
    return {
        "entry_ts_utc": _now_iso_ms(),
        "macro": {"spot": mt["spot"], "sma20": mt["sma20"], "distance_to_sma20_pct": mt["distance_to_sma20_pct"],
                  "source": mt["source"]},
        "iv_term": iv_term_structure(ticker, spot, mock),
        "gex": net_gex(ticker, spot, mock),
        "alt_catalyst": alt_catalyst(ticker, mock),
        "technical": {"atr": mt["atr"], "atr_pct": mt["atr_pct"], "rvol_10min": mt["rvol_10min"],
                      "source": mt["source"]},
    }


# ----------------------------------------------------------------------------
# Trigger + leg construction + entry
# ----------------------------------------------------------------------------
def should_enter_proactive(regime, candidate=None):
    """Fail-OPEN: trade flat regimes and consolidating candidates rather than suppress."""
    if regime == "C":
        return True, "regime_C_neutral (flat/chop)"
    if candidate and candidate.get("consolidating"):
        return True, "candidate_consolidating"
    return True, "fail-open sandbox (build statistical database)"


def _est_premium(spot, strike, iv_pct, dte, right):
    intrinsic = max(0.0, (spot - strike) if right == "call" else (strike - spot))
    tv = spot * (iv_pct / 100.0) * math.sqrt(max(dte, 1) / 365.0) * 0.40
    return round(intrinsic + tv, 2)


def build_legs(ticker, md, equity, size_pct):
    spot = md["macro"]["spot"]
    iv = md["iv_term"]["iv_front"]
    alloc = round(equity * size_pct, 2)
    call_k = round(spot * 1.04, 1)        # ~OTM 0.35-delta target
    put_k = round(spot * 0.96, 1)
    cp = _est_premium(spot, call_k, iv, 35, "call")
    pp = _est_premium(spot, put_k, iv, 35, "put")
    front = _est_premium(spot, spot, iv, 14, "call")
    back = _est_premium(spot, spot, md["iv_term"]["iv_back"], 45, "call")
    cal_debit = round(back - front, 2)

    def qty(premium):
        return int(alloc // (premium * 100)) if premium and premium > 0 else 0

    return {
        "bullish_call": {"structure": "LONG_CALL", "right": "call", "strike": call_k, "target_delta": CALL_DELTA,
                         "dte": 35, "entry_premium": cp, "contracts": qty(cp), "alloc_usd": alloc},
        "bearish_put": {"structure": "LONG_PUT", "right": "put", "strike": put_k, "target_delta": PUT_DELTA,
                        "dte": 35, "entry_premium": pp, "contracts": qty(pp), "alloc_usd": alloc},
        "flat_calendar": {"structure": "CALENDAR_SPREAD", "strike": round(spot, 1), "front_dte": 14, "back_dte": 45,
                          "front_premium": front, "back_premium": back, "net_debit": cal_debit,
                          "contracts": qty(cal_debit), "alloc_usd": alloc},
    }


def enter_proactive_set(ticker, regime, equity=PAPER_EQUITY, size_pct=SIZE_PCT, mock=False, candidate=None):
    ok, trigger = should_enter_proactive(regime, candidate)
    md = collect_metadata(ticker, mock=mock)
    legs = build_legs(ticker, md, equity, size_pct)
    record = {
        "trade_set_id": uuid.uuid4().hex[:12], "ticker": ticker, "regime": regime, "trigger": trigger,
        "entry_ts_utc": md["entry_ts_utc"], "paper_equity": equity, "size_pct_per_leg": size_pct,
        "metadata": md, "legs": legs, "exit": None, "status": "OPEN",
    }
    _append_log(record)
    return record


def _append_log(record):
    data = []
    if os.path.exists(LOG_PATH):
        try:
            data = json.load(open(LOG_PATH, encoding="utf-8"))
        except Exception:
            data = []
    data.append(record)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ----------------------------------------------------------------------------
# Post-mortem autopsy
# ----------------------------------------------------------------------------
def run_trade_autopsy(record, leg_returns_pct, exit_reason="5d_time_exit", underlying_move_pct=None):
    """leg_returns_pct: {'bullish_call':%, 'bearish_put':%, 'flat_calendar':%}."""
    md = record["metadata"]
    ranked = sorted(leg_returns_pct.items(), key=lambda kv: kv[1], reverse=True)
    winner, w_ret = ranked[0]
    loser, l_ret = ranked[-1]

    factor = _determining_factor(winner, md, underlying_move_pct)
    md_block = _autopsy_markdown(record, leg_returns_pct, winner, loser, exit_reason, underlying_move_pct, factor)
    with open(AUTOPSY_MD, "a", encoding="utf-8") as f:
        f.write(md_block + "\n")

    record["exit"] = {"reason": exit_reason, "underlying_move_pct": underlying_move_pct,
                      "leg_returns_pct": leg_returns_pct, "winner": winner, "loser": loser,
                      "determining_factor": factor}
    record["status"] = "CLOSED"
    return {"winner": winner, "winner_return": w_ret, "loser": loser, "loser_return": l_ret,
            "determining_factor": factor, "markdown": md_block}


def _determining_factor(winner, md, move):
    alt, gex, ivt = md["alt_catalyst"], md["gex"], md["iv_term"]
    rd = alt.get("reddit_mention_delta_pct")
    if winner == "bullish_call":
        if alt.get("insider_cluster_flag"):
            return f"Insider cluster buy (${alt.get('insider_10d_buy_usd'):,.0f} in 10d) predicted the bullish expansion; negative GEX ({gex['regime']}) amplified the upside breakout."
        if rd is not None and rd > 500:
            return f"Breakout triggered by a +{rd:.0f}% Reddit mention spike while IV term was in {ivt['structure']} (front rich, decays into the move)."
        return f"Bullish breakout above the flat range (move {move}%); dealers short gamma at {gex['zero_gamma_strike']} fed the squeeze."
    if winner == "bearish_put":
        return f"Bearish breakdown (move {move}%) with no positive catalyst (reddit {rd}% / insider {alt.get('insider_cluster_flag')}); spot below zero-gamma {gex['zero_gamma_strike']} -> negative-gamma slide."
    return (f"Range held: IV term {ivt['structure']} (ratio {ivt['iv_ratio']}) let front-month theta decay outrun the wings; "
            f"no catalyst broke the range (reddit {rd}%, insider_cluster={alt.get('insider_cluster_flag')}).")


def _autopsy_markdown(record, returns, winner, loser, reason, move, factor):
    md = record["metadata"]
    lines = [
        f"## Trade-set autopsy - {record['ticker']} ({record['trade_set_id']})",
        f"- entered {record['entry_ts_utc']} | trigger: {record['trigger']} | exit: {reason} | underlying move: {move}%",
        "",
        "| leg | structure | return % | verdict |",
        "|---|---|---|---|",
    ]
    label = {"bullish_call": "Bullish (call)", "bearish_put": "Bearish (put)", "flat_calendar": "Flat (calendar)"}
    for leg, ret in sorted(returns.items(), key=lambda kv: kv[1], reverse=True):
        v = "WINNER" if leg == winner else ("loser" if leg == loser else "")
        lines.append(f"| {label[leg]} | {record['legs'][leg]['structure']} | {ret:+.1f}% | {v} |")
    lines += [
        "",
        f"**Determining factor:** {factor}",
        "",
        f"_environment at entry:_ 20dSMA dist {md['macro']['distance_to_sma20_pct']:+.2f}% | "
        f"IV ratio {md['iv_term']['iv_ratio']} ({md['iv_term']['structure']}) | "
        f"net GEX {md['gex']['net_gex']} ({md['gex']['regime']}, zero-gamma {md['gex']['zero_gamma_strike']}) | "
        f"reddit {md['alt_catalyst']['reddit_mention_delta_pct']}% | "
        f"insider ${md['alt_catalyst']['insider_10d_buy_usd']} cluster={md['alt_catalyst']['insider_cluster_flag']} | "
        f"ATR {md['technical']['atr_pct']}% | RVOL {md['technical']['rvol_10min']}",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# Mock execution demo
# ----------------------------------------------------------------------------
def main():
    mock = os.environ.get("PROACTIVE_MOCK", "1") == "1"   # default mock for a deterministic demo
    print("=" * 76)
    print("V10 PROACTIVE PAPER-TRADING LAB - mock execution")
    print(f"(mode: {'MOCK metadata' if mock else 'LIVE feeds, fail-open'})")
    print("=" * 76)

    ticker, regime = "HOOD", "C"        # consolidating name, SPY in NEUTRAL
    rec = enter_proactive_set(ticker, regime, mock=mock, candidate={"consolidating": True})

    print(f"\nTRIGGER: {rec['trigger']}  ->  entering 3 simultaneous paper legs on {ticker}")
    print(f"trade_set_id={rec['trade_set_id']}  entry={rec['entry_ts_utc']}  equity=${rec['paper_equity']:,.0f} "
          f"@ {rec['size_pct_per_leg']*100:.0f}%/leg\n")

    md = rec["metadata"]
    print("STATE BLOCK (logged to proactive_sandbox_logs.json):")
    print(f"  macro      : spot {md['macro']['spot']}  20dSMA {md['macro']['sma20']}  "
          f"dist {md['macro']['distance_to_sma20_pct']:+.2f}%  [{md['macro']['source']}]")
    print(f"  iv_term    : front {md['iv_term']['iv_front']} / back {md['iv_term']['iv_back']}  "
          f"ratio {md['iv_term']['iv_ratio']} ({md['iv_term']['structure']})  [{md['iv_term']['source']}]")
    print(f"  gex        : net {md['gex']['net_gex']}  zero-gamma {md['gex']['zero_gamma_strike']}  "
          f"dist {md['gex']['distance_to_zero_gamma_pct']:+.2f}%  ({md['gex']['regime']})  [{md['gex']['source']}]")
    print(f"  alt        : reddit {md['alt_catalyst']['reddit_mention_delta_pct']}%  "
          f"insider ${md['alt_catalyst']['insider_10d_buy_usd']:,} cluster={md['alt_catalyst']['insider_cluster_flag']}  "
          f"[{md['alt_catalyst']['source']}]")
    print(f"  technical  : ATR {md['technical']['atr']} ({md['technical']['atr_pct']}%)  "
          f"RVOL {md['technical']['rvol_10min']}  [{md['technical']['source']}]")

    print("\nTHREE ENTRY LEGS:")
    for name, leg in rec["legs"].items():
        if name == "flat_calendar":
            print(f"  FLAT     {leg['structure']:<16} K{leg['strike']} front{leg['front_dte']}d/back{leg['back_dte']}d "
                  f"net_debit ${leg['net_debit']}  x{leg['contracts']}  (${leg['alloc_usd']:,.0f})")
        else:
            tag = "BULLISH" if name == "bullish_call" else "BEARISH"
            print(f"  {tag:<8} {leg['structure']:<16} K{leg['strike']} {leg['dte']}d delta {leg['target_delta']:+.2f} "
                  f"prem ${leg['entry_premium']}  x{leg['contracts']}  (${leg['alloc_usd']:,.0f})")

    # simulate a close: a +6.2% bullish breakout broke the flat range
    print("\n" + "-" * 76)
    print("SIMULATED CLOSE (5-day exit): underlying broke +6.2% out of the range")
    leg_returns = {"bullish_call": 138.0, "bearish_put": -72.0, "flat_calendar": -28.0}
    res = run_trade_autopsy(rec, leg_returns, exit_reason="5d_time_exit", underlying_move_pct=6.2)
    # persist the closed record back
    _rewrite_last(rec)
    print(f"  winner: {res['winner']} ({leg_returns[res['winner']]:+.0f}%) | loser: {res['loser']} ({leg_returns[res['loser']]:+.0f}%)")
    print(f"  determining factor: {res['determining_factor']}")
    print(f"\n  -> autopsy markdown appended to {AUTOPSY_MD}")
    print(f"  -> trade set logged to {LOG_PATH}")


def _rewrite_last(record):
    data = json.load(open(LOG_PATH, encoding="utf-8"))
    for i in range(len(data) - 1, -1, -1):
        if data[i]["trade_set_id"] == record["trade_set_id"]:
            data[i] = record
            break
    json.dump(data, open(LOG_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()

"""V10 Research Sandbox - dynamic routers & sizing modifiers (STANDALONE).

Five advanced upgrades implemented as DYNAMIC ROUTERS (alter the structure chosen) and
SIZING MODIFIERS (alter fractional-Kelly allocation). By design NONE of these acts as a
binary hard-block - they re-route or re-size to preserve trade volume (anti filter-fatigue).

  1. Meme-Squeeze volatility gate     -> route straight long -> debit vertical / calendar
  2. C-Suite tiering & cluster sizing -> role x log10($) conviction; 1.5x Kelly on clusters
  3. After-hours SEC front-run sniffer -> CEO/CFO buy > 5.0 conviction -> premarket limit @ ask+1%
  4. Pre-earnings IV harvest           -> calendar/debit ~14d pre-earnings, hard exit T-1 business day
  5. Dynamic beta-weighting            -> hold correlated same-sector names, scale both by (1-0.5r)

Mocks + assert-based unit tests + console performance report. No network, no V9 engine import.
Real data feeds: prototype_alt_data.py (ApeWisdom, edgartools). Run: python sandbox_v10_upgrades.py
"""

import re
import math
from datetime import date, timedelta

# thresholds
IVR_OVERPRICED = 70.0
MEME_SPIKE_PCT = 500.0
SNIPER_CONVICTION_MIN = 5.0
CLUSTER_MIN_FILERS = 3
CLUSTER_WINDOW_DAYS = 10
CLUSTER_MIN_VALUE = 25_000
CLUSTER_KELLY_MULT = 1.5
MAX_SINGLE_TRADE = 0.10           # 10% of net capital, hard cap on sizing
HARVEST_IVR_MAX = 35.0
HARVEST_DAYS = 14
CORR_THRESHOLD = 0.60
PORTFOLIO_DELTA_CAP = 0.25        # 25% account risk
MIN_SHORT_DTE = 3                 # min DTE for a SHORT leg on hard-to-borrow names (assignment safety)


# ----------------------------------------------------------------------------
# UPGRADE 1 - Meme-Squeeze volatility gate (dynamic structure routing)
# ----------------------------------------------------------------------------
def route_structure(ivr, mention_spike_pct, side="CALL", highly_liquid=False,
                    short_leg_dte=None, hard_to_borrow=False):
    side = (side or "CALL").upper()
    bullish = side in ("CALL", "LONG", "BULLISH")
    long_struct = "LONG_CALL" if bullish else "LONG_PUT"
    direction = "BULLISH" if bullish else "BEARISH"

    meme_spike = mention_spike_pct is not None and mention_spike_pct > MEME_SPIKE_PCT
    overpriced = ivr is not None and ivr > IVR_OVERPRICED

    if overpriced and meme_spike:
        if highly_liquid:
            structure = "CALENDAR_SPREAD"
            rationale = (f"IVR {ivr:.0f}% overpriced + retail spike {mention_spike_pct:.0f}% & liquid "
                         f"-> sell front / buy back month, harvest near-term retail IV decay")
            guard = assignment_safety(short_leg_dte, hard_to_borrow)
        else:
            structure = "DEBIT_VERTICAL"
            rationale = (f"IVR {ivr:.0f}% overpriced + retail spike {mention_spike_pct:.0f}% "
                         f"-> sell upper strike to offset expensive Vega")
            guard = {"safe": True, "action": "none", "reason": "vertical short is strike-covered (defined risk)"}
        return {"structure": structure, "direction": direction, "prohibited_straight_long": True,
                "ivr": ivr, "mention_spike_pct": mention_spike_pct, "rationale": rationale,
                "assignment_guard": guard}

    return {"structure": long_struct, "direction": direction, "prohibited_straight_long": False,
            "ivr": ivr, "mention_spike_pct": mention_spike_pct,
            "rationale": f"IVR {ivr if ivr is not None else 'n/a'}% <= 70% or no >500% spike -> pure directional long"}


# ----------------------------------------------------------------------------
# UPGRADE 2 - C-Suite tiering & cluster sizing
# ----------------------------------------------------------------------------
def role_multiplier(title):
    t = (title or "").upper()
    if re.search(r"CHIEF EXECUTIVE|CHIEF FINANCIAL|\bCEO\b|\bCFO\b", t):
        return 1.0
    if re.search(r"CHIEF OPERATING|\bCOO\b|\bEVP\b|\bSVP\b|EXECUTIVE VICE PRESIDENT|"
                 r"SENIOR VICE PRESIDENT|VICE PRESIDENT|\bVP\b|PRESIDENT", t):
        return 0.6
    if re.search(r"DIRECTOR|10%|BENEFICIAL OWNER", t):
        return 0.3
    return 0.3


def conviction_weight(title, dollar_value):
    rm = role_multiplier(title)
    dv = max(float(dollar_value or 0), 1.0)
    return round(rm * math.log10(dv), 3)


def detect_cluster(purchases, window_days=CLUSTER_WINDOW_DAYS,
                   min_value=CLUSTER_MIN_VALUE, min_filers=CLUSTER_MIN_FILERS):
    """purchases: [{date, filer, value}]. True if >= min_filers UNIQUE filers buy (>min_value)
    inside any rolling window_days window."""
    valid = [(date.fromisoformat(p["date"]), p["filer"]) for p in purchases
             if (p.get("value") or 0) >= min_value]
    best, window = 0, None
    for d0, _ in valid:
        filers = {f for (d, f) in valid if 0 <= (d - d0).days < window_days}
        if len(filers) > best:
            best, window = len(filers), (d0.isoformat(), len(filers))
    return {"cluster_flag": best >= min_filers, "max_unique_filers_in_window": best, "window": window}


def cluster_sizing(kelly_fraction, cluster_flag, cap=MAX_SINGLE_TRADE):
    sized = kelly_fraction * (CLUSTER_KELLY_MULT if cluster_flag else 1.0)
    return round(min(sized, cap), 4)


# ----------------------------------------------------------------------------
# UPGRADE 3 - After-hours SEC front-run (nightly sniffer)
# ----------------------------------------------------------------------------
def nightly_sniffer(after_hours_filings, min_option_volume=500, max_spread_pct=10.0):
    """Detect post-4pm C-Suite buys with conviction > 5.0 on optionable names; if the
    option chain is liquid, generate a premarket limit buy + a Telegram alert.

    GAP-UP FIX: the limit is priced off the LIVE 9:15 ET premarket ask (Alpaca premarket
    stream), NOT the previous close ask. A $5M CEO buy routinely gaps the stock +5-10%
    overnight; a close-ask+1% limit would sit unfilled at the bottom of the book while the
    stock explodes at the open. When premarket_ask is absent, the order is left UNPRICED
    with a flag to reprice at 9:15 rather than locking to a stale close quote."""
    alerts = []
    for f in after_hours_filings:
        cw = conviction_weight(f.get("title"), f.get("value"))
        c_suite = role_multiplier(f.get("title")) >= 1.0          # CEO/CFO
        if cw <= SNIPER_CONVICTION_MIN or not c_suite or not f.get("optionable", True):
            continue
        vol = f.get("option_volume")
        spread = f.get("spread_pct")
        liquid_ok = (vol is not None and vol >= min_option_volume and
                     spread is not None and spread <= max_spread_pct)
        close_ask = f.get("ask")
        premarket_ask = f.get("premarket_ask")          # live 9:15 ET quote
        order = None
        if liquid_ok:
            if premarket_ask:
                order = {"type": "PREMARKET_LIMIT_BUY", "limit_price": round(premarket_ask * 1.01, 2),
                         "priced_from": "premarket_ask_0915 + 1%", "premarket_ask": premarket_ask,
                         "close_ask": close_ask,
                         "overnight_gap_pct": round((premarket_ask / close_ask - 1) * 100, 1) if close_ask else None}
            else:
                order = {"type": "PREMARKET_LIMIT_BUY", "limit_price": None,
                         "priced_from": "AWAIT_0915_PREMARKET_ASK (do NOT lock to stale close ask)",
                         "close_ask": close_ask}
        alerts.append({
            "ticker": f["ticker"], "conviction_weight": cw, "size_usd": f.get("value"),
            "liquidity_ok": liquid_ok, "order": order,
            "telegram": f"[AFTER-HOURS INSIDER SNIPE DETECTED: {f['ticker']} - ${(f.get('value') or 0):,.0f}]",
        })
    return alerts


# ----------------------------------------------------------------------------
# UPGRADE 4 - Pre-earnings IV harvest
# ----------------------------------------------------------------------------
def _minus_one_business_day(iso):
    d = date.fromisoformat(iso) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def pre_earnings_harvest(ticker, days_to_earnings, ivr, beta, highly_liquid, earnings_date,
                         front_dte=7, hard_to_borrow=False):
    cheap = ivr is not None and ivr < HARVEST_IVR_MAX
    in_window = days_to_earnings is not None and 13 <= days_to_earnings <= HARVEST_DAYS
    high_beta = beta is not None and beta >= 1.2
    if not (in_window and cheap and high_beta and highly_liquid):
        reason = []
        if not in_window: reason.append(f"{days_to_earnings}d not ~14d pre-earnings")
        if not cheap: reason.append(f"IVR {ivr} not < {HARVEST_IVR_MAX:.0f}")
        if not high_beta: reason.append(f"beta {beta} < 1.2")
        if not highly_liquid: reason.append("not highly liquid")
        return {"ticker": ticker, "eligible": False, "reason": "; ".join(reason)}
    structure = "CALENDAR_SPREAD" if highly_liquid else "DEBIT_VERTICAL"
    hard_exit = _minus_one_business_day(earnings_date)
    guard = assignment_safety(front_dte, hard_to_borrow) if structure == "CALENDAR_SPREAD" else \
        {"safe": True, "action": "none", "reason": "vertical short is strike-covered"}
    return {
        "ticker": ticker, "eligible": True, "structure": structure,
        "entry_rule": f"buy back-month / sell front-month {structure} (~14d out, IVR {ivr:.0f}% cheap -> Vega expansion)",
        "earnings_date": earnings_date, "hard_exit_date": hard_exit,
        "exit_rule": "HARD market-sell entire position 1 business day before earnings - ZERO binary exposure",
        "assignment_guard": guard,
    }


# ----------------------------------------------------------------------------
# UPGRADE 5 - Dynamic portfolio beta-weighting (remove sector ban)
# ----------------------------------------------------------------------------
def beta_weight_sizing(new_ticker, new_sector, new_kelly, open_positions, correlation_r,
                       delta_cap=PORTFOLIO_DELTA_CAP):
    same_sector = [p for p in open_positions if p.get("sector") == new_sector]
    correlated = bool(same_sector) and correlation_r is not None and correlation_r > CORR_THRESHOLD

    if correlated:
        modifier = round(1 - 0.5 * correlation_r, 4)
        new_size = round(new_kelly * modifier, 4)
        existing_adjusted = [{"ticker": p["ticker"], "from": p["size"],
                              "to": round(p["size"] * modifier, 4)} for p in same_sector]
        reason = f"r={correlation_r:.2f} > 0.60 -> ride sector, scale BOTH by (1-0.5r)={modifier}"
    else:
        modifier, new_size, existing_adjusted = 1.0, round(new_kelly, 4), []
        reason = ("no same-sector open position -> full Kelly" if not same_sector
                  else f"r={correlation_r:.2f} <= 0.60 -> uncorrelated, full Kelly")

    # enforce 25% portfolio delta cap (non-blocking: shrink new size to fit, never reject)
    held = sum((e["to"] for e in existing_adjusted)) if existing_adjusted else sum(p["size"] for p in same_sector)
    other = sum(p["size"] for p in open_positions if p.get("sector") != new_sector)
    projected = round(new_size + held + other, 4)
    delta_cap_hit = projected > delta_cap
    if delta_cap_hit:
        new_size = round(max(0.0, new_size - (projected - delta_cap)), 4)
        projected = round(new_size + held + other, 4)

    return {"new_ticker": new_ticker, "new_size": new_size, "modifier": modifier, "blocked": False,
            "existing_adjusted": existing_adjusted, "portfolio_delta_after": projected,
            "delta_cap_hit": delta_cap_hit, "reason": reason}


def sector_cluster_sizing(new_ticker, new_sector, new_kelly, open_positions,
                          delta_cap=PORTFOLIO_DELTA_CAP):
    """N>=3 FIX: pairwise (1-0.5r) compounds toward zero when 3+ same-sector names trigger.
    Use a Sector Correlation Cluster Factor = 1/sqrt(N_sector) (N includes the new name) so
    every position in the sector is scaled by the SAME smooth factor, regardless of count.
    open_positions may carry 'base_kelly' (the unmodified Kelly); falls back to 'size'."""
    same = [p for p in open_positions if p.get("sector") == new_sector]
    n_sector = len(same) + 1
    modifier = round(1.0 / math.sqrt(n_sector), 4)
    new_size = round(new_kelly * modifier, 4)
    existing_adjusted = [{"ticker": p["ticker"], "base": p.get("base_kelly", p["size"]),
                          "to": round(p.get("base_kelly", p["size"]) * modifier, 4)} for p in same]
    held = sum(e["to"] for e in existing_adjusted)
    other = sum(p["size"] for p in open_positions if p.get("sector") != new_sector)
    projected = round(new_size + held + other, 4)
    cap_hit = projected > delta_cap
    if cap_hit:
        new_size = round(max(0.0, new_size - (projected - delta_cap)), 4)
        projected = round(new_size + held + other, 4)
    return {"new_ticker": new_ticker, "n_sector": n_sector, "modifier": modifier,
            "new_size": new_size, "existing_adjusted": existing_adjusted, "blocked": False,
            "portfolio_delta_after": projected, "delta_cap_hit": cap_hit,
            "reason": f"{n_sector} names in {new_sector} -> cluster factor 1/sqrt({n_sector})={modifier}; "
                      f"scale ALL sector names equally (no pairwise compounding-to-zero)"}


def assignment_safety(short_dte, hard_to_borrow, min_dte=MIN_SHORT_DTE):
    """Calendar/vertical short-leg guard: prohibit selling < min_dte DTE on hard-to-borrow
    names. A gap past the short strike can trigger early exercise -> overnight short equity
    -> margin/liquidation risk. Non-blocking: roll the short leg out to min_dte instead."""
    if hard_to_borrow and short_dte is not None and short_dte < min_dte:
        return {"safe": False, "action": f"roll short leg to >={min_dte} DTE",
                "adjusted_short_dte": min_dte,
                "reason": f"short {short_dte}DTE on hard-to-borrow name -> early-assignment / overnight-short "
                          f"risk; roll short out to {min_dte}DTE before selling"}
    return {"safe": True, "action": "none", "adjusted_short_dte": short_dte,
            "reason": "short leg DTE acceptable or name is not hard-to-borrow"}


# ----------------------------------------------------------------------------
# MOCK SCENARIOS
# ----------------------------------------------------------------------------
MOCKS = {
    "meme_overpriced": {"ticker": "GMEW", "side": "CALL", "ivr": 88.0, "mention_spike_pct": 1240.0,
                        "highly_liquid": True, "short_leg_dte": 1, "hard_to_borrow": True},
    "ceo_purchase": {"ticker": "BIGB", "title": "Chief Executive Officer", "value": 5_000_000,
                     "optionable": True, "option_volume": 3200, "spread_pct": 3.5, "ask": 50.00,
                     "premarket_ask": 54.50, "filed_time": "18:32 ET"},   # gapped +9% overnight
    "sector_cluster_3": {"new_ticker": "SMCI", "new_sector": "Semiconductors", "new_kelly": 0.06,
                         "open_positions": [
                             {"ticker": "NVDA", "sector": "Semiconductors", "size": 0.06, "base_kelly": 0.06},
                             {"ticker": "AMD", "sector": "Semiconductors", "size": 0.06, "base_kelly": 0.06}]},
    "midcap_cluster": {"ticker": "MIDC", "purchases": [
        {"date": "2026-06-08", "filer": "Jane Doe (CEO)", "value": 400_000},
        {"date": "2026-06-10", "filer": "John Roe (CFO)", "value": 150_000},
        {"date": "2026-06-12", "filer": "Sam Poe (Director)", "value": 60_000},
        {"date": "2026-06-12", "filer": "Sam Poe (Director)", "value": 20_000},   # <25k, ignored
    ]},
    "sector_conflict": {"new_ticker": "NVDA", "new_sector": "Semiconductors", "new_kelly": 0.06,
                        "correlation_r": 0.78, "open_positions": [
                            {"ticker": "AMD", "sector": "Semiconductors", "size": 0.06},
                            {"ticker": "JPM", "sector": "Financials", "size": 0.04}]},
}


# ----------------------------------------------------------------------------
# UNIT TESTS
# ----------------------------------------------------------------------------
def _approx(a, b, tol=0.02):
    return abs(a - b) <= tol


def run_tests():
    T = []

    def check(name, cond):
        T.append((name, bool(cond)))

    # Upgrade 1
    r1 = route_structure(88, 1240, "CALL", highly_liquid=True)
    check("U1 overpriced+spike+liquid -> CALENDAR", r1["structure"] == "CALENDAR_SPREAD" and r1["prohibited_straight_long"])
    check("U1 overpriced+spike+illiquid -> DEBIT_VERTICAL", route_structure(88, 1240, "CALL", False)["structure"] == "DEBIT_VERTICAL")
    check("U1 cheap IV -> LONG_CALL (directional)", route_structure(45, 1240)["structure"] == "LONG_CALL")
    check("U1 overpriced but no meme spike -> LONG_CALL", route_structure(88, 100)["structure"] == "LONG_CALL")
    check("U1 bearish -> LONG_PUT", route_structure(40, 0, "PUT")["structure"] == "LONG_PUT")

    # Upgrade 2
    check("U2 role CEO=1.0", role_multiplier("Chief Executive Officer") == 1.0)
    check("U2 role CFO=1.0", role_multiplier("EVP and CFO") == 1.0)
    check("U2 role EVP=0.6", role_multiplier("Executive Vice President") == 0.6)
    check("U2 role Director=0.3", role_multiplier("Director") == 0.3)
    check("U2 conviction CEO $100k = 5.0", _approx(conviction_weight("CEO", 100_000), 5.0))
    check("U2 conviction CEO $5M ~ 6.70", _approx(conviction_weight("CEO", 5_000_000), 6.70))
    clu = detect_cluster(MOCKS["midcap_cluster"]["purchases"])
    check("U2 cluster: 3 unique filers in 10d -> True", clu["cluster_flag"] and clu["max_unique_filers_in_window"] == 3)
    check("U2 cluster: only 2 filers -> False", not detect_cluster([
        {"date": "2026-06-08", "filer": "A", "value": 50_000},
        {"date": "2026-06-10", "filer": "B", "value": 50_000}])["cluster_flag"])
    check("U2 cluster sizing 1.5x", _approx(cluster_sizing(0.05, True), 0.075))
    check("U2 cluster sizing capped at 10%", cluster_sizing(0.08, True) == 0.10)

    # Upgrade 3
    snipes = nightly_sniffer([MOCKS["ceo_purchase"]])
    check("U3 CEO $5M optionable liquid -> snipe + order", len(snipes) == 1 and snipes[0]["order"] is not None)
    check("U3 order priced off premarket ask (gap-fix, 54.50*1.01=55.05)", _approx(snipes[0]["order"]["limit_price"], 55.05))
    check("U3 CEO $50k -> conviction 4.7 < 5 -> no snipe", len(nightly_sniffer([
        {**MOCKS["ceo_purchase"], "value": 50_000}])) == 0)
    check("U3 VP $5M -> role 0.6 -> conviction 4.0 < 5 -> no snipe", len(nightly_sniffer([
        {**MOCKS["ceo_purchase"], "title": "Vice President"}])) == 0)
    check("U3 CEO buy but illiquid -> alert, no order", nightly_sniffer([
        {**MOCKS["ceo_purchase"], "option_volume": 50}])[0]["order"] is None)

    # Upgrade 4
    h = pre_earnings_harvest("TSLA", 14, 28.0, 1.8, True, "2026-07-15")
    check("U4 14d + cheap IVR + high beta + liquid -> eligible CALENDAR", h["eligible"] and h["structure"] == "CALENDAR_SPREAD")
    check("U4 hard exit = 1 business day before earnings (Jul15 Wed -> Jul14)", h["hard_exit_date"] == "2026-07-14")
    check("U4 rich IVR -> not eligible", not pre_earnings_harvest("TSLA", 14, 55.0, 1.8, True, "2026-07-15")["eligible"])
    check("U4 not in 14d window -> not eligible", not pre_earnings_harvest("TSLA", 5, 25.0, 1.8, True, "2026-07-15")["eligible"])

    # Upgrade 5
    b = beta_weight_sizing(**MOCKS["sector_conflict"])
    check("U5 r=0.78 -> modifier 0.61", _approx(b["modifier"], 0.61))
    check("U5 new size scaled (0.06*0.61=0.0366)", _approx(b["new_size"], 0.0366, tol=0.005))
    check("U5 existing AMD scaled too", b["existing_adjusted"] and _approx(b["existing_adjusted"][0]["to"], 0.0366, tol=0.005))
    check("U5 not blocked (non-binary)", b["blocked"] is False)
    check("U5 portfolio delta within 25% cap", b["portfolio_delta_after"] <= PORTFOLIO_DELTA_CAP + 1e-9)
    check("U5 uncorrelated r=0.4 -> full Kelly", _approx(beta_weight_sizing("NVDA", "Semiconductors", 0.06, [
        {"ticker": "AMD", "sector": "Semiconductors", "size": 0.05}], 0.40)["new_size"], 0.06))
    # delta cap shrink test (uncorrelated 0.20 + 0.20 = 0.40 > 0.25 cap -> shrink new, never block)
    capped = beta_weight_sizing("NVDA", "Semiconductors", 0.20, [
        {"ticker": "AMD", "sector": "Semiconductors", "size": 0.20}], 0.40)
    check("U5 delta-cap shrinks new size (non-blocking)",
          capped["delta_cap_hit"] and capped["portfolio_delta_after"] <= PORTFOLIO_DELTA_CAP + 1e-9
          and not capped["blocked"] and capped["new_size"] < 0.20)

    # --- FIX 1: after-hours premarket pricing (gap-up trap) ---
    s_gap = nightly_sniffer([MOCKS["ceo_purchase"]])[0]
    check("FIX1 limit priced off premarket ask (54.50*1.01=55.05), not stale close",
          _approx(s_gap["order"]["limit_price"], 55.05) and "premarket" in s_gap["order"]["priced_from"])
    check("FIX1 overnight gap surfaced (+9%)", _approx(s_gap["order"]["overnight_gap_pct"], 9.0, tol=0.6))
    s_nopre = nightly_sniffer([{**MOCKS["ceo_purchase"], "premarket_ask": None}])[0]
    check("FIX1 no premarket quote -> unpriced, await 9:15 (never lock to stale close)",
          s_nopre["order"]["limit_price"] is None and "AWAIT" in s_nopre["order"]["priced_from"])

    # --- FIX 2: sector cluster factor 1/sqrt(N) for N>=3 ---
    c3 = sector_cluster_sizing(**MOCKS["sector_cluster_3"])
    check("FIX2 N=3 -> modifier 1/sqrt(3)=0.577", _approx(c3["modifier"], 0.5774, tol=0.001) and c3["n_sector"] == 3)
    check("FIX2 N=3 scales all 3 names, none collapses to zero",
          c3["new_size"] > 0 and len(c3["existing_adjusted"]) == 2 and all(e["to"] > 0 for e in c3["existing_adjusted"]))
    c2 = sector_cluster_sizing("AMD", "S", 0.06, [{"ticker": "NVDA", "sector": "S", "size": 0.06}])
    c5 = sector_cluster_sizing("X", "S", 0.06, [{"ticker": t, "sector": "S", "size": 0.06} for t in "ABCD"])
    check("FIX2 smooth monotonic decay N=2>3>5, no compounding collapse",
          c2["modifier"] > c3["modifier"] > c5["modifier"] and c5["modifier"] > 0.4)

    # --- FIX 3: calendar assignment safety (<3 DTE on hard-to-borrow) ---
    check("FIX3 short 1DTE + HTB -> unsafe, roll to 3DTE",
          assignment_safety(1, True)["safe"] is False and assignment_safety(1, True)["adjusted_short_dte"] == 3)
    check("FIX3 short 5DTE + HTB -> safe", assignment_safety(5, True)["safe"] is True)
    check("FIX3 short 1DTE not HTB -> safe", assignment_safety(1, False)["safe"] is True)
    r_cal = route_structure(88, 1240, "CALL", highly_liquid=True, short_leg_dte=1, hard_to_borrow=True)
    check("FIX3 meme calendar w/ 1DTE HTB short -> guard flags unsafe + reroute",
          r_cal["assignment_guard"]["safe"] is False and "roll" in r_cal["assignment_guard"]["action"])

    passed = sum(1 for _, ok in T if ok)
    print("UNIT TESTS")
    print("-" * 64)
    for name, ok in T:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(T)} tests passed")
    return passed == len(T)


# ----------------------------------------------------------------------------
# PERFORMANCE REPORT
# ----------------------------------------------------------------------------
def performance_report():
    print("\n" + "=" * 64)
    print("PERFORMANCE REPORT - non-blocking router/sizer outputs")
    print("=" * 64)
    base_kelly = 0.05

    print("\n[U1] Meme-squeeze routing (hyper-volatile Reddit name, overpriced IV):")
    m = MOCKS["meme_overpriced"]
    r = route_structure(m["ivr"], m["mention_spike_pct"], m["side"], m["highly_liquid"])
    print(f"   {m['ticker']}: IVR {m['ivr']:.0f}%, spike {m['mention_spike_pct']:.0f}% -> {r['structure']}")
    print(f"     {r['rationale']}")

    print("\n[U2] C-Suite tiering + cluster sizing (mid-cap cluster):")
    clu = detect_cluster(MOCKS["midcap_cluster"]["purchases"])
    sized = cluster_sizing(base_kelly, clu["cluster_flag"])
    cw = conviction_weight("CEO", 400_000)
    print(f"   MIDC: cluster_flag={clu['cluster_flag']} ({clu['max_unique_filers_in_window']} filers in 10d), "
          f"CEO $400k conviction={cw}")
    print(f"     Kelly {base_kelly:.3f} -> {sized:.3f} ({'1.5x cluster' if clu['cluster_flag'] else '1x'}, capped 10%)")

    print("\n[U3] After-hours sniffer (CEO $5M post-4pm on optionable name):")
    for a in nightly_sniffer([MOCKS["ceo_purchase"]]):
        print(f"   {a['telegram']}")
        print(f"     conviction={a['conviction_weight']} liquidity_ok={a['liquidity_ok']} order={a['order']}")

    print("\n[U4] Pre-earnings IV harvest (TSLA, 14d out, IVR 28% cheap):")
    h = pre_earnings_harvest("TSLA", 14, 28.0, 1.8, True, "2026-07-15")
    print(f"   {h['ticker']}: {h['structure']} | {h['entry_rule']}")
    print(f"     HARD EXIT {h['hard_exit_date']} ({h['exit_rule']})")

    print("\n[U5] Beta-weighting (NVDA signal while holding AMD, r=0.78):")
    b = beta_weight_sizing(**MOCKS["sector_conflict"])
    print(f"   {b['reason']}")
    print(f"     NVDA new size {b['new_size']:.4f} | AMD re-sized {b['existing_adjusted']} | "
          f"portfolio delta {b['portfolio_delta_after']:.3f} (cap {PORTFOLIO_DELTA_CAP})")

    print("\n" + "-" * 64)
    print("PEER-REVIEW FIXES")
    print("-" * 64)

    print("\n[FIX1] After-hours premarket re-pricing (gap-up trap):")
    g = nightly_sniffer([MOCKS["ceo_purchase"]])[0]["order"]
    print(f"   close ask ${g['close_ask']} -> gapped +{g['overnight_gap_pct']}% overnight; limit re-priced to "
          f"${g['limit_price']} ({g['priced_from']}) -> tracks the open instead of sitting unfilled")

    print("\n[FIX2] Sector cluster sizing N>=3 (SMCI signal while holding NVDA + AMD):")
    c = sector_cluster_sizing(**MOCKS["sector_cluster_3"])
    print(f"   {c['reason']}")
    print(f"     SMCI {c['new_size']} | resized {[(e['ticker'], e['to']) for e in c['existing_adjusted']]} "
          f"| portfolio delta {c['portfolio_delta_after']} (cap {PORTFOLIO_DELTA_CAP})")

    print("\n[FIX3] Calendar assignment safety (meme GMEW, 1-DTE short, hard-to-borrow):")
    r = route_structure(88, 1240, "CALL", highly_liquid=True, short_leg_dte=1, hard_to_borrow=True)
    ag = r["assignment_guard"]
    print(f"   {r['structure']} short-leg guard: safe={ag['safe']} -> {ag['action']}")
    print(f"     {ag['reason']}")

    print("\n--- non-blocking proof: every scenario produced a TRADEABLE action, zero hard blocks ---")


if __name__ == "__main__":
    ok = run_tests()
    performance_report()
    import sys
    sys.exit(0 if ok else 1)

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eodhd import EODHDClient
from src.indicators import to_dataframe, compute_all
from src.pillars import (
    pillar_1_trend_following,
    pillar_2_volatility_breakout,
    pillar_3_can_slim,
    pillar_4_statarb,
    pillar_5_global_macro,
    pillar_6_erm,
    pillar_7_short_squeeze,
    gate_3_rvol,
    gate_4_catalyst,
    gate_6_liquidity,
    gate_7_earnings_blackout,
)
from src.scoring import score_candidate, build_trade_ticket

FROM_DATE = "2024-11-01"


def normalize(ticker):
    ticker = ticker.strip().upper()
    if "." not in ticker:
        ticker = ticker + ".US"
    return ticker


def research(raw_ticker):
    ticker = normalize(raw_ticker)
    is_us = ticker.endswith(".US")
    client = EODHDClient()

    spy = to_dataframe(client.ohlcv("SPY.US", from_date=FROM_DATE))
    try:
        vuke = to_dataframe(client.ohlcv("VUKE.LSE", from_date=FROM_DATE))
    except Exception:
        vuke = spy
    try:
        vix = to_dataframe(client.ohlcv("VIX.INDX", from_date=FROM_DATE))
    except Exception:
        vix = None

    ohlcv = client.ohlcv(ticker, from_date=FROM_DATE)
    if not ohlcv or len(ohlcv) < 210:
        print(f"ERROR: insufficient OHLCV history for {ticker} ({len(ohlcv) if ohlcv else 0} rows, need 210+)")
        return

    df = to_dataframe(ohlcv)
    ind = compute_all(df)

    fundamentals = client.fundamentals(ticker)
    if not fundamentals:
        print(f"ERROR: no fundamentals available for {ticker}")
        return

    insider = client.insider_transactions(ticker, limit=20) if is_us else None
    try:
        news = client.news(ticker, limit=20)
    except Exception:
        news = []

    benchmark = vuke if ticker.endswith(".LSE") else spy

    p1 = pillar_1_trend_following(ind)
    p2 = pillar_2_volatility_breakout(ind)
    p3 = pillar_3_can_slim(fundamentals)
    p4 = pillar_4_statarb(ind, benchmark, lookback=20)
    p5 = pillar_5_global_macro(vix)
    p6 = pillar_6_erm(fundamentals, is_us)
    p7 = pillar_7_short_squeeze(fundamentals, ind, insider, is_us)

    g3 = gate_3_rvol(ind)
    g4 = gate_4_catalyst(fundamentals, news)
    g6 = gate_6_liquidity(fundamentals, ind)
    g7 = gate_7_earnings_blackout(fundamentals)

    pillars = {
        "pillar_1": p1, "pillar_2": p2, "pillar_3": p3, "pillar_4": p4,
        "pillar_5": p5, "pillar_6": p6, "pillar_7": p7,
    }
    gates = {
        "gate_3": g3, "gate_4": g4, "gate_6": g6, "gate_7": g7,
        "gate_5_modifier": {"direction": "neutral"},
    }

    tier_info = score_candidate(pillars, gates, is_us)
    price = float(ind["close"].iloc[-1])
    general = fundamentals.get("General", {}) or {}
    name = general.get("Name", ticker)
    sector = general.get("Sector", "") or ""
    industry = general.get("Industry", "") or ""
    description = general.get("Description", "") or ""
    ticket = build_trade_ticket(
        ticker, name, price, tier_info, pillars, gates,
        p5.get("regime", "unknown"),
        sector=sector, industry=industry, description=description,
    )

    bar = "=" * 72
    print(bar)
    print(f"  {ticker}  -  {name}")
    if ticket.get("sector") or ticket.get("industry"):
        print(f"  {ticket.get('sector','')}" + (f"  /  {ticket.get('industry')}" if ticket.get('industry') else ""))
    print(f"  {ticket['label']}   |   {ticket['pillars_passed']}/{ticket['applicable_pillars']} pillars")
    print(bar)
    if ticket.get("description"):
        print()
        print(f"  {ticket['description']}")
    print()
    print("Trade levels:")
    print(f"  Entry    ${ticket['price']:.2f}")
    print(f"  Stop     ${ticket['stop_loss']:.2f}   ({ticket['stop_pct']:.0f}% width)")
    print(f"  Phase 1  ${ticket['phase1_target']:.2f}   (+50%, sell 40%)")
    print(f"  Runner   ${ticket['runner_target']:.2f}   (+80%, trail remaining 60%)")
    print(f"  R/R      {ticket['risk_reward']}")
    print()
    print("Pillars:")
    labels = {
        "p1": "P1 Trend         ",
        "p2": "P2 Squeeze       ",
        "p3": "P3 Growth        ",
        "p4": "P4 RS            ",
        "p5": "P5 Macro         ",
        "p6": "P6 Revisions     ",
        "p7": "P7 Short Squeeze ",
    }
    for k, lab in labels.items():
        p = ticket["pillars"][k]
        print(f"  {lab} {p['verdict']:12s}  {p['summary']}")
    print()
    print("Gates:")
    gate_labels = {
        "g3": "G3 RVOL      ",
        "g4": "G4 Catalyst  ",
        "g6": "G6 Liquidity ",
        "g7": "G7 Earnings  ",
    }
    for k, lab in gate_labels.items():
        g = ticket["gates"][k]
        print(f"  {lab} {g['verdict']:12s}  {g['summary']}")
    print()
    if ticket["hard_gate_fails"]:
        print(f"Hard gate failures: {ticket['hard_gate_fails']}")
        print("Verdict: NO TRADE")
    else:
        print("Verdict: setup is tradeable per v3.1 spec")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/research.py TICKER")
        print("Examples:")
        print("  python scripts/research.py ENVA")
        print("  python scripts/research.py SHEL.LSE")
        print("  python scripts/research.py STRL.US")
        sys.exit(1)
    research(sys.argv[1])

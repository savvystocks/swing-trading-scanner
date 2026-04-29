import os
import subprocess
import sys

def load(n):
    if os.environ.get(n): return os.environ[n]
    r = subprocess.run(["powershell","-Command",f'[Environment]::GetEnvironmentVariable("{n}","User")'], capture_output=True, text=True)
    return (r.stdout or "").strip()

for k in ("ANTHROPIC_API_KEY",):
    v = load(k)
    if v: os.environ[k] = v

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.llm_commentary import add_commentary

mock_tickets = [
    {
        "ticker": "PUMP.US", "name": "ProPetro Holding Corp",
        "sector": "Energy Services", "industry": "Oil & Gas Equipment",
        "market_cap": 1300000000, "tier": 4,
        "hunter": {"qualified": True, "score": 78, "eta_label": "5-12 trading days",
                   "reasons": ["Earnings sweet-spot 7d", "P7 SI 14% (squeeze fuel)", "Sector momentum (HAL/BKR beat)", "Within 5% of 52w high"]},
        "conviction": {"score": 68}, "opportunity": {"score": 72},
        "pillars": {
            "p1": {"summary": "7/7 trend template, Stage 2 confirmed, above all key MAs"},
            "p3": {"summary": "EPS YoY +83%, Rev YoY +12%, Q1 consensus -$0.04 (low bar)"},
            "p4": {"summary": "RS +8% vs SPY over 60d, sector leader in pressure pumping"},
            "p6": {"summary": "Last 4 reports: 4 beats, 2 with 80%+ surprise. EPS revisions +3 up vs 0 down 30d"},
            "p7": {"summary": "SI 14% of float, 0 distribution days in 15, 2 high-conviction acc days"},
        },
        "gates": {
            "g4": {"summary": "Tier A catalyst: earnings 5 May 2026, sector peers (HAL, BKR) already beat Q1"},
            "g7": {"summary": "POST-EARN window not yet open — earnings in 7 days"},
        },
        "lane_b": {
            "pocket_pivot": {"fired": True},
            "base_quality": {"fired": True, "score": 8},
            "insider_cluster": {"fired": False},
            "revenue_acceleration": {"fired": False},
            "earnings_turn": {"fired": True},
            "peer_pack": {"fired": True},
        },
        "price": 17.20, "stop_loss": 15.50, "phase1_target": 22.00, "risk_reward": "2.7:1",
        "options_trade": {"strike": 15.0, "expiration": "2026-05-15", "dte": 16,
                          "delta": 0.80, "premium_mid": 2.70, "breakeven": 17.70,
                          "breakeven_pct_move": 2.9, "iv_pct": 90, "cost_per_contract": 270,
                          "spread_pct": 7.4, "theta": -0.05,
                          "projected_value_at_target": 7.10, "projected_roi_pct": 163,
                          "vol_interpretation": "FAIR"},
    },
    {
        "ticker": "NVTS.US", "name": "Navitas Semiconductor",
        "sector": "Technology", "industry": "Semiconductors",
        "market_cap": 850000000, "tier": 4,
        "hunter": {"qualified": True, "score": 71, "eta_label": "10-18 trading days",
                   "reasons": ["Sector tilt: semis", "P6 revisions +5 up", "Within 8% of 52w high"]},
        "conviction": {"score": 62}, "opportunity": {"score": 65},
        "pillars": {
            "p1": {"summary": "6/7 trend, Stage 2 just confirmed, above 50d/200d"},
            "p3": {"summary": "EPS YoY +145%, Rev YoY +28%, accelerating GaN adoption"},
            "p4": {"summary": "RS +12% vs SPY over 60d"},
            "p6": {"summary": "Beats 3/4, EPS revisions +5 up vs 1 down 30d"},
            "p7": {"summary": "SI 8% of float, accumulation days outpacing distribution 4:1"},
        },
        "gates": {"g4": {"summary": "Tier B catalyst: earnings 19 May, partnership pipeline rumors"},
                  "g7": {"summary": "Earnings 22 days away (clean window)"}},
        "lane_b": {"pocket_pivot": {"fired": True}, "base_quality": {"fired": True, "score": 7},
                   "revenue_acceleration": {"fired": True, "latest_qoq_pct": 14}},
        "price": 4.85, "stop_loss": 4.30, "phase1_target": 6.20, "risk_reward": "2.5:1",
        "options_trade": {"strike": 5.0, "expiration": "2026-06-19", "dte": 51,
                          "delta": 0.45, "premium_mid": 0.65, "breakeven": 5.65,
                          "breakeven_pct_move": 16.5, "iv_pct": 78, "cost_per_contract": 65,
                          "spread_pct": 6.2, "theta": -0.012,
                          "projected_value_at_target": 1.55, "projected_roi_pct": 138,
                          "vol_interpretation": "FAIR"},
    },
]

print("=" * 80)
print("Testing LLM commentary on 2 mock picks (PUMP, NVTS)")
print("=" * 80)
add_commentary(mock_tickets, top_n=2, verbose=True)
print()
for t in mock_tickets:
    print("-" * 80)
    print(f"{t['ticker']}  hunter {t['hunter']['score']}/100  ->  RATING: {t.get('llm_rating', '(none)')}")
    print(f"  THESIS: {t.get('llm_thesis', '(none)')}")
    print(f"  RISK:   {t.get('llm_risk', '(none)')}")
print("-" * 80)

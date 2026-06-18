import sys
import os
import json
import pathlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst import leak_lambda, probe_ladder
from src.telegram import send_alert

LOG_DIR = pathlib.Path(__file__).parent.parent / "data" / "ambush_logs"


if __name__ == "__main__":
    leak = leak_lambda.evaluate()
    ladder = probe_ladder.evaluate()
    try:
        from src.catalyst import regime_compass
        regime = regime_compass.evaluate()
    except Exception as e:
        regime = {"regime": "?", "bias": "?", "reason": f"regime unavailable: {type(e).__name__}"}

    state = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "regime": {"regime": regime.get("regime"), "bias": regime.get("bias"), "reason": regime.get("reason")},
        "bayesian": {
            "rung": ladder["rung"],
            "posterior_a": ladder["posterior_a"],
            "posterior_b": ladder["posterior_b"],
            "posterior_mean_p": ladder["posterior_mean_p"],
            "breakeven_p": ladder["breakeven_p"],
            "pr_edge_above_breakeven": ladder["pr_edge_above_breakeven"],
            "realized_r": ladder["realized_r"],
            "size_pct": ladder["size_pct"],
            "active_tranche_gbp": ladder["ratchet"]["active_tranche_gbp"],
            "protected_base_gbp": ladder["ratchet"]["protected_base_gbp"],
            "next_rung": ladder["next_rung"],
        },
        "edge": {
            "n_closed": leak["n_closed"],
            "expectancy_pct": leak["expectancy_pct"],
            "win_rate": leak["win_rate"],
            "breakeven_win": leak["breakeven_win"],
            "mode": leak["mode"],
            "slippage_flag": leak["slippage_flag"],
            "mean_stop_fill_pct": leak["mean_stop_fill_pct"],
        },
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LOG_DIR / f"macro_review_{datetime.utcnow().date().isoformat()}.log"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    nxt = ladder["next_rung"]
    nxt_line = (f"next {nxt['name']}: need {nxt['have_closed']}/{nxt['needs_closed']} trades, "
                f"Pr {nxt['have_pr_edge']}/{nxt['needs_pr_edge']}, R {nxt['have_realized_r']}/{nxt['needs_realized_r']}"
                if nxt else "at MAX rung")
    text = ("<b>V8.5 WEEKLY MACRO REVIEW</b>\n"
            f"Regime {regime.get('regime')} ({regime.get('bias')})\n"
            f"Bayesian: rung {ladder['rung']}, post_p {ladder['posterior_mean_p']}, "
            f"Pr(edge>BE) {ladder['pr_edge_above_breakeven']}, realized R {ladder['realized_r']}\n"
            f"Edge: n={leak['n_closed']} exp={leak['expectancy_pct']}% win={leak['win_rate']} mode={leak['mode']}\n"
            f"Tranche: active £{ladder['ratchet']['active_tranche_gbp']} protected £{ladder['ratchet']['protected_base_gbp']}\n"
            + nxt_line)
    sent = send_alert(text) if "--no-telegram" not in sys.argv else False
    print(f"macro review {'sent' if sent else 'not sent'} | logged {out_path.name}")
    print(json.dumps(state["bayesian"], indent=1))

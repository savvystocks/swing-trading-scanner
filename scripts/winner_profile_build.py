"""WINNER PROFILE BUILDER (owner order 2026-09-09: "look at every single winning trade we
have ever created - all of them - find the median of all the indicators that made it a win,
and create a secondary control of a universal strategy").

Method - CONTRAST, not winner-worship: a feature only enters the profile if winners and
losers genuinely separate on it (per-feature AUC vs the label), because the median of
winners on a non-discriminating feature is just the median of everybody. For each surviving
feature we record the winner median and which side of the pooled median winners sit on.
The live probe (WINNER_PROFILE) scores a candidate by the fraction of profile features on
the winner side; entries require match >= threshold. Profile is FROZEN at build (teacher
freeze) and committed; retrain only by a fresh owner order. Corpus: every labeled candidate
in harvest.db - all strategies, all eras, ~70k rows.
Output: reports/research/winner_profile.json (the live probe reads this) + dated md report."""
import json
import os
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import numpy as np

PATHS = [
    ("macro", "distance_to_sma20_pct"), ("macro", "atr_pct"), ("macro", "rvol_10d"),
    ("regime_stack", "market_spy_dist_pct"), ("regime_stack", "vix"),
    ("iv_term", "iv_front"), ("iv_term", "iv_ratio"),
    ("technical", "rsi_5"), ("technical", "rsi_15"),
    ("gex", "net_gex"), ("gex", "distance_to_zero_gamma_pct"),
    ("dark_pool", "dp_ratio"), ("dark_pool", "dp_volume_pct"),
    ("skew", "skew_25d"), ("vrp", "vrp"),
    ("flow_aggression", "ask_side_pct"), ("flow_persistence", "n_alerts_today"),
    ("dealer_greeks", "vanna"), ("dealer_greeks", "charm"),
]
MIN_AUC_EDGE = 0.535        # per-feature separation bar (|AUC-0.5| >= 0.035)
MATCH_THRESHOLD = 0.70      # candidate must sit winner-side on >= 70% of profile features


def main():
    con = sqlite3.connect("file:data/harvest.db?mode=ro", uri=True)
    rows = con.execute(
        """select c.features, c.right, c.spread_pct, c.rule_score, l.realized_return
           from candidates c join labels l on l.candidate_id = c.candidate_id
           where l.realized_return is not null and c.features != ''""").fetchall()
    print(f"labeled corpus: {len(rows)}", flush=True)
    vals = defaultdict(list)
    wins = []
    for fj, right, spr, score, ret in rows:
        try:
            f = json.loads(fj)
        except Exception:
            continue
        w = 1 if ret > 0 else 0
        wins.append(w)
        for blk, key in PATHS:
            v = (f.get(blk) or {}).get(key)
            vals[f"{blk}.{key}"].append(float(v) if isinstance(v, (int, float)) else np.nan)
        vals["spread_pct"].append(float(spr) if isinstance(spr, (int, float)) else np.nan)
        vals["rule_score"].append(float(score) if isinstance(score, (int, float)) else np.nan)
    y = np.array(wins)
    n = len(y)
    win_rate = y.mean()
    from sklearn.metrics import roc_auc_score
    profile = {}
    audit = []
    for name, arr in vals.items():
        a = np.array(arr)
        k = ~np.isnan(a)
        if k.sum() < n * 0.30 or len(set(y[k])) < 2:
            audit.append((name, None, k.mean(), "insufficient coverage"))
            continue
        auc = roc_auc_score(y[k], a[k])
        edge = abs(auc - 0.5)
        med_w = float(np.median(a[k][y[k] == 1]))
        med_l = float(np.median(a[k][y[k] == 0]))
        med_all = float(np.median(a[k]))
        if edge >= (MIN_AUC_EDGE - 0.5):
            side = "above" if auc > 0.5 else "below"
            profile[name] = {"winner_side": side, "pooled_median": round(med_all, 4),
                             "winner_median": round(med_w, 4), "loser_median": round(med_l, 4),
                             "auc": round(auc, 4), "coverage": round(float(k.mean()), 3)}
            audit.append((name, auc, k.mean(), f"IN - winners {side}"))
        else:
            audit.append((name, auc, k.mean(), "out - no separation"))
    out = {"built": datetime.now(timezone.utc).isoformat()[:16],
           "corpus_n": n, "corpus_win_rate": round(float(win_rate), 4),
           "match_threshold": MATCH_THRESHOLD, "min_auc_edge": MIN_AUC_EDGE,
           "frozen": True, "features": profile,
           "note": "FROZEN at build (teacher freeze). WINNER_PROFILE probe scores candidates "
                   "by fraction of these features on the winner side of pooled_median; "
                   "entry requires match >= match_threshold. Rebuild only by owner order."}
    json.dump(out, open("reports/research/winner_profile.json", "w", encoding="utf-8"), indent=1)
    L = [f"# WINNER PROFILE - built {date.today().isoformat()}",
         f"corpus: {n} labeled trades (all strategies, all eras), base win rate {win_rate:.1%}",
         f"profile features (separation >= {MIN_AUC_EDGE} AUC), winner side vs pooled median:", ""]
    for name, spec in sorted(profile.items(), key=lambda x: -abs(x[1]["auc"] - 0.5)):
        L.append(f"- {name}: winners sit {spec['winner_side']} {spec['pooled_median']} "
                 f"(winner med {spec['winner_median']} vs loser med {spec['loser_median']}, "
                 f"AUC {spec['auc']}, coverage {spec['coverage']:.0%})")
    L += ["", "rejected (no winner/loser separation): " +
          ", ".join(nm for nm, auc, cov, why in audit if "no separation" in why),
          "insufficient coverage: " +
          ", ".join(nm for nm, auc, cov, why in audit if "coverage" in why)]
    open(f"reports/research/winner_profile_{date.today().isoformat()}.md", "w",
         encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("WINNER PROFILE BUILT", flush=True)


if __name__ == "__main__":
    main()

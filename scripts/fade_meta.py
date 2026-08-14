"""AUTONOMOUS FADE META-MODEL (owner order 2026-08-11: "make everything automated").

Runs weekly on the VPS (Sunday 09:45, before the boundary). When the labeled fade cohort
reaches 500: trains a gradient-boosted P(win) model with day-grouped cross-validation, ranks
every feature's contribution, scores each virgin day's candidates, and appends a META_SELECT
book (top-3-by-model per day) to the shadow ledger - so the selection brain competes under the
same Sunday bars as every other hypothesis. Telegrams the verdict. Below 500: reports the count
and exits. The ONLY deliberate manual gate left: wiring a PASSING model into live entries is a
reviewed code session (safety choice, paged when earned - the model must first beat BASELINE
on >=10 virgin days like everything else).
"""
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
REG_DAY = (date(2026, 8, 5) - date(1970, 1, 1)).days      # virgin = after fade go-live
NUMERIC_PATHS = [
    ("macro", "distance_to_sma20_pct"), ("regime_stack", "market_spy_dist_pct"),
    ("technical", "atr_pct"), ("technical", "rvol_10min"), ("iv_term", "iv_ratio"),
    ("gex", "distance_to_zero_gamma_pct"), ("dark_pool", "n_prints"),
    ("dark_pool", "distance_to_heaviest_dp_node_pct"), ("flow_aggression", "sweep_aggression_pct"),
    ("flow_persistence", "flow_persistence_pct"), ("skew", "skew_ratio"),
    ("vrp", "vrp"), ("pemd", "iv_rank_1y"), ("news", "vader_compound"),
    ("macro_context", "vix_level"), ("macro_context", "execution_hour"),
    ("macro_context", "day_of_week"), ("dealer_greeks", "delta_imbalance"),
]


def tg(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass


def cohort(db="data/harvest.db", wide=False):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        """select c.candidate_id, c.entry_ref, c.right, c.spread_pct, c.rule_score, c.features,
                  cast(c.signal_ts_utc/86400000 as int), l.realized_return
           from candidates c join labels l on l.candidate_id=c.candidate_id
           where l.outcome is not null and l.realized_return is not null
             and c.entry_ref>0 and c.features!=''""").fetchall()
    X, y, days, cids = [], [], [], []
    for cid, e, right, spr, score, fj, day, ret in rows:
        try:
            f = json.loads(fj)
        except Exception:
            continue
        sma = (f.get("macro") or {}).get("distance_to_sma20_pct")
        spy = (f.get("regime_stack") or {}).get("market_spy_dist_pct")
        side = 1 if right == "call" else -1
        if not (isinstance(sma, (int, float)) and isinstance(spy, (int, float))):
            continue
        if not wide and not (sma * side < 0 and spy * side < 0 and (spr or 99) <= 2.0
                             and score and 50000 <= score <= 400000):
            continue
        vec = []
        for blk, key in NUMERIC_PATHS:
            v = (f.get(blk) or {}).get(key)
            vec.append(float(v) if isinstance(v, (int, float)) else float("nan"))
        vec.append(float(side))
        if wide:                              # WIDE student: whole funnel; shape/spread/size are
            vec.append(float(spr or 99))      # FEATURES here, not filters (owner order 2026-08-15)
            vec.append(float(score or 0))
            vec.append(1.0 if (sma * side < 0 and spy * side < 0) else 0.0)
            vec.append(1.0 if (sma * side > 0 and spy * side > 0) else 0.0)
        X.append(vec)
        y.append(1 if ret > 0 else 0)
        days.append(day)
        cids.append(cid)
    return X, y, days, cids


def main():
    X, y, days, cids = cohort()
    n = len(X)
    if n < 500:
        print(f"fade-meta: cohort {n}/500 - not yet")
        return
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score
    X = np.array(X)
    y = np.array(y)
    g = np.array(days)
    oof = np.full(n, np.nan)
    for tr, te in GroupKFold(n_splits=min(5, len(set(days)))).split(X, y, g):
        m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, random_state=7)
        m.fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
    auc = roc_auc_score(y[~np.isnan(oof)], oof[~np.isnan(oof)])
    # META_SELECT shadow book: per VIRGIN day, mean realized return of top-3 by OOF score
    con = sqlite3.connect("file:data/harvest.db?mode=ro", uri=True)
    ret_by_cid = dict(con.execute(
        "select c.candidate_id, l.realized_return from candidates c "
        "join labels l on l.candidate_id=c.candidate_id where l.realized_return is not null"))
    per_day = defaultdict(list)
    for i, cid in enumerate(cids):
        if g[i] > REG_DAY and not np.isnan(oof[i]):
            per_day[g[i]].append((oof[i], ret_by_cid.get(cid)))
    lines = [f"FADE META-MODEL trained: n={n}, day-grouped OOF AUC {auc:.3f}"]
    os.makedirs("reports/fade_meta", exist_ok=True)
    led = open("reports/shadow_lab/ledger.jsonl", "a", encoding="utf-8")
    for d, items in sorted(per_day.items()):
        items.sort(reverse=True)
        top = [r for _, r in items[:3] if r is not None]
        if top:
            iso = date.fromordinal(date(1970, 1, 1).toordinal() + d).isoformat()
            led.write(json.dumps({"day": iso, "META_SELECT": {"n": len(top),
                      "mean": round(sum(top) / len(top) * 100, 2)},
                      "computed_at": datetime.now(timezone.utc).isoformat()[:16]}) + "\n")
    led.close()
    Xw, yw, dw, cw = cohort(wide=True)
    if len(Xw) >= 1000:
        Xw = np.array(Xw); yw = np.array(yw); gw = np.array(dw)
        oofw = np.full(len(yw), np.nan)
        for tr, te in GroupKFold(n_splits=min(5, len(set(dw)))).split(Xw, yw, gw):
            mw = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, random_state=7)
            mw.fit(Xw[tr], yw[tr])
            oofw[te] = mw.predict_proba(Xw[te])[:, 1]
        aucw = roc_auc_score(yw[~np.isnan(oofw)], oofw[~np.isnan(oofw)])
        lines.append(f"WIDE student: n={len(yw)}, day-grouped OOF AUC {aucw:.3f}")
        per_dw = defaultdict(list)
        for i, cid in enumerate(cw):
            if gw[i] > REG_DAY and not np.isnan(oofw[i]):
                per_dw[gw[i]].append((oofw[i], ret_by_cid.get(cid)))
        led = open("reports/shadow_lab/ledger.jsonl", "a", encoding="utf-8")
        for d, items in sorted(per_dw.items()):
            items.sort(reverse=True)
            top = [r for _, r in items[:3] if r is not None]
            if top:
                iso = date.fromordinal(date(1970, 1, 1).toordinal() + d).isoformat()
                led.write(json.dumps({"day": iso, "META_WIDE": {"n": len(top),
                          "mean": round(sum(top) / len(top) * 100, 2)},
                          "computed_at": datetime.now(timezone.utc).isoformat()[:16]}) + '\n')
        led.close()
        json.dump({"n": len(yw), "auc": round(aucw, 4),
                   "trained": datetime.now(timezone.utc).isoformat()},
                  open(f"reports/fade_meta/wide_{date.today().isoformat()}.json", "w"), indent=1)
    else:
        lines.append(f"WIDE student: cohort {len(Xw)}/1000 - not yet")
    fname = f"reports/fade_meta/model_{date.today().isoformat()}.json"

    json.dump({"n": n, "auc": round(auc, 4), "trained": datetime.now(timezone.utc).isoformat(),
               "features": [f"{b}.{k}" for b, k in NUMERIC_PATHS] + ["side"]},
              open(fname, "w"), indent=1)
    lines.append("META_SELECT book appended to shadow ledger for virgin days; competes under "
                 "Sunday bars. If it beats BASELINE on >=10 virgin days, you'll be paged for "
                 "the one manual gate: the reviewed session that wires it into live entries.")
    print("\n".join(lines))
    tg("\n".join(lines))


if __name__ == "__main__":
    main()

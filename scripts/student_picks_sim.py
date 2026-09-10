"""STUDENT PICKS SIMULATION (owner question 2026-09-10 23:43: "is the strategy not in the
identity of the strategy but in the quality of setup the student's knowledge suggests? maybe it's
the narrow student picks, not the fixed strategy - make sure the model has fully learnt all the
data at its disposal").

Strict WALK-FORWARD, not k-fold: for each scored day D, the model is trained on EVERY labeled
row from days strictly before D (expanding window - all the data at its disposal at that
moment), then scores day D's candidates. No day is scored by a model that saw it or any later
day. Books are compared on the SAME days on LABEL returns (the harvest's executable-price path),
so the question isolated is selection quality, not execution.

Books:
  CONTROL           every labeled candidate that day (take everything)
  FADE_SHAPE        every fade-shaped candidate (ticker and SPY both against the flow side)
  CALLS             every call (FOLLOW_CALLS' shape)
  MOMO_SHAPE        every momentum-shaped candidate (both with the flow side)
  WIDE_TOP3         wide model (all rows), top-3 that day
  WIDE_60           wide model, every pick with P >= 0.60 (cap 3)
  NARROW_TOP3       model trained on fade-shaped rows only, top-3 within the shape
  NARROW_60         same, P >= 0.60 (cap 3)
  CALLS_TOP3        wide model restricted to calls, top-3 (selection INSIDE a fixed strategy)
Reported per book: days, picks/day, day-mean %, paired t vs CONTROL on shared days, trimmed
(best+worst day dropped) mean, both halves, win rate of picks vs base rate.
Research tier: report only (channel policy 2026-09-09)."""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import numpy as np
import fade_meta as fm

MIN_TRAIN_DAYS = 12
TAU = 0.60
TOPK = 3


def daystats(dm, ctrl):
    days = sorted(dm)
    if not days:
        return None
    means = [dm[d] for d in days]
    mu = sum(means) / len(means)
    sh = [d for d in days if d in ctrl]
    diffs = [dm[d] - ctrl[d] for d in sh]
    t = None
    if len(diffs) >= 3:
        m2 = sum(diffs) / len(diffs)
        sd = (sum((x - m2) ** 2 for x in diffs) / (len(diffs) - 1)) ** 0.5
        t = m2 / (sd / math.sqrt(len(diffs))) if sd > 0 else 0.0
    tr = sorted(means)[1:-1] if len(means) >= 6 else means
    h = len(means) // 2
    return {"days": len(days), "mean": mu, "t": t, "trim": sum(tr) / len(tr) if tr else mu,
            "h1": sum(means[:h]) / h if h else 0, "h2": sum(means[h:]) / (len(means) - h) if len(means) - h else 0,
            "ahead": sum(1 for x in diffs if x > 0), "shared": len(sh)}


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    _cache = "reports/research/student_cohort_cache.npz"
    if os.path.exists(_cache) and (os.path.getmtime(_cache) > __import__("time").time() - 6 * 3600):
        _z = np.load(_cache, allow_pickle=True)
        X, y, g, cids = _z["X"], _z["y"], _z["g"], list(_z["cids"])
        days = list(g)
        print("cohort loaded from cache", flush=True)
    else:
        X, y, days, cids = fm.cohort(wide=True)
        X = np.array(X, float); y = np.array(y); g = np.array(days)
        np.savez(_cache, X=X, y=y, g=g, cids=np.array(cids, dtype=object))
    import sqlite3
    con = sqlite3.connect("file:data/harvest.db?mode=ro", uri=True)
    ret = dict(con.execute("select c.candidate_id, l.realized_return from candidates c "
                           "join labels l on l.candidate_id=c.candidate_id where l.realized_return is not null"))
    right = dict(con.execute("select candidate_id, right from candidates"))
    r = np.array([float(ret.get(c) or 0.0) * 100.0 for c in cids])
    side = np.array([1 if right.get(c) == "call" else -1 for c in cids])
    # wide vector layout (fade_meta.cohort wide=True): [...18 paths, side, rv20, prev_oi, iv_front,
    # spread, premium, fade_flag, momo_flag]
    fade_flag = X[:, -2] > 0.5
    momo_flag = X[:, -1] > 0.5
    spread_col = X[:, -4]; prem_col = X[:, -3]
    tradeable = (spread_col <= 2.0) & (prem_col >= 50000) & (prem_col <= 1000000)
    print(f"tradeable slice (spread<=2%, premium 50k-1M): {int(tradeable.sum())} of {len(y)} rows", flush=True)
    cov = float(np.mean(~np.isnan(X[:, :18])))
    udays = sorted(set(days))
    scored_days = [d for i, d in enumerate(udays) if i >= MIN_TRAIN_DAYS]
    print(f"rows {len(y)}, days {len(udays)}, scoring {len(scored_days)} days walk-forward; "
          f"feature coverage {cov:.1%}; base win rate {y.mean():.1%}", flush=True)
    books = defaultdict(dict)
    picks_n = defaultdict(int); picks_w = defaultdict(int)

    def book(name, d, idx):
        if len(idx) == 0:
            return
        books[name][d] = float(np.mean(r[idx]))
        picks_n[name] += len(idx); picks_w[name] += int(np.sum(r[idx] > 0))

    for d in scored_days:
        tr = g < d; te = g == d
        if te.sum() == 0 or tr.sum() < 200:
            continue
        iso = date.fromordinal(date(1970, 1, 1).toordinal() + int(d)).isoformat()
        te_idx = np.where(te)[0]
        # WIDE model: everything before D
        mw = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, random_state=7)
        mw.fit(X[tr], y[tr])
        pw = mw.predict_proba(X[te])[:, 1]
        # NARROW model: fade-shaped rows before D (all of them - no band filters)
        trn = tr & fade_flag
        pn = None
        if trn.sum() >= 150 and (te & fade_flag).sum() > 0:
            mn = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, random_state=7)
            mn.fit(X[trn], y[trn])
            pn = mn.predict_proba(X[te])[:, 1]
        book("CONTROL", iso, te_idx)
        book("FADE_SHAPE", iso, te_idx[fade_flag[te]])
        book("CALLS", iso, te_idx[side[te] == 1])
        book("MOMO_SHAPE", iso, te_idx[momo_flag[te]])
        order = np.argsort(-pw)
        book("WIDE_TOP3", iso, te_idx[order[:TOPK]])
        conf = order[pw[order] >= TAU][:TOPK]
        book("WIDE_60", iso, te_idx[conf])
        cmask = side[te] == 1
        if cmask.sum():
            co = np.where(cmask)[0]; co = co[np.argsort(-pw[co])]
            book("CALLS_TOP3", iso, te_idx[co[:TOPK]])
        # TRADEABLE slice: the candidates the engine could actually buy (owner question: are the
        # picks positive where it matters, not on the whole scored funnel)
        tmask = tradeable[te]
        if tmask.sum():
            book("TRADEABLE", iso, te_idx[tmask])
            to = np.where(tmask)[0]; to = to[np.argsort(-pw[to])]
            book("TRADEABLE_TOP3", iso, te_idx[to[:TOPK]])
            book("TRADEABLE_TOP1", iso, te_idx[to[:1]])
            tc = np.where(tmask & (side[te] == 1))[0]; tc = tc[np.argsort(-pw[tc])]
            if len(tc):
                book("TRADEABLE_CALLS_TOP3", iso, te_idx[tc[:TOPK]])
            tm = np.where(tmask & momo_flag[te])[0]
            if len(tm):
                book("TRADEABLE_MOMO", iso, te_idx[tm])
            tfw = np.where(tmask & fade_flag[te])[0]; tfw = tfw[np.argsort(-pw[tfw])]
            if len(tfw):
                book("TRADEABLE_FADE_WIDE_TOP3", iso, te_idx[tfw[:TOPK]])
                book("TRADEABLE_FADE_WIDE_TOP1", iso, te_idx[tfw[:1]])
            if pn is not None:
                tf = np.where(tmask & fade_flag[te])[0]; tf = tf[np.argsort(-pn[tf])]
                if len(tf):
                    book("TRADEABLE_NARROW_TOP3", iso, te_idx[tf[:TOPK]])
                    book("TRADEABLE_FADE", iso, te_idx[np.where(tmask & fade_flag[te])[0]])
        if pn is not None:
            fm_ = np.where(fade_flag[te])[0]
            fo = fm_[np.argsort(-pn[fm_])]
            book("NARROW_TOP3", iso, te_idx[fo[:TOPK]])
            fc = fo[pn[fo] >= TAU][:TOPK]
            book("NARROW_60", iso, te_idx[fc])
    ctrl = books["CONTROL"]
    trd = books["TRADEABLE"]
    L = [f"# STUDENT PICKS SIMULATION - {date.today().isoformat()} (strict walk-forward)",
         f"rows {len(y)}, {len(scored_days)} scored days, expanding-window retrain every day; label returns; "
         f"feature coverage {cov:.0%}; base win rate {y.mean():.0%}", "",
         "| book | days | picks/day | %/day | trimmed | paired t (vs CONTROL; TRADEABLE books vs TRADEABLE) | ahead | halves | pick win rate |",
         "|---|---|---|---|---|---|---|---|---|"]
    for name in ["CONTROL", "FADE_SHAPE", "CALLS", "MOMO_SHAPE", "WIDE_TOP3", "WIDE_60",
                 "CALLS_TOP3", "NARROW_TOP3", "NARROW_60", "TRADEABLE", "TRADEABLE_FADE", "TRADEABLE_MOMO",
                 "TRADEABLE_TOP1", "TRADEABLE_TOP3", "TRADEABLE_CALLS_TOP3", "TRADEABLE_NARROW_TOP3",
                 "TRADEABLE_FADE_WIDE_TOP3", "TRADEABLE_FADE_WIDE_TOP1"]:
        s = daystats(books[name], trd if name.startswith("TRADEABLE") else ctrl)
        if not s:
            L.append(f"| {name} | 0 | - | - | - | - | - | - | - |"); continue
        ppd = picks_n[name] / max(1, s["days"])
        wr = picks_w[name] / max(1, picks_n[name]) * 100
        L.append(f"| {name} | {s['days']} | {ppd:.1f} | {s['mean']:+.1f} | {s['trim']:+.1f} | "
                 f"{('%+.2f' % s['t']) if s['t'] is not None else 'n/a'} | {s['ahead']}/{s['shared']} | "
                 f"{s['h1']:+.1f}/{s['h2']:+.1f} | {wr:.0f}% |")
    L += ["", "READING: if the picker books (WIDE_TOP3/60, NARROW_TOP3/60, CALLS_TOP3) sit above their "
              "parent shapes AND above CONTROL with t near or beyond 1.8 on both halves, selection is the "
              "strategy and the fixed identity is only the pool it selects from. If the shapes alone match "
              "the pickers, the model adds nothing beyond the filter.",
          "CAVEATS: label returns (executable-price path, no live friction); ~25 scored days; one path; "
          "the narrow model here uses ALL fade-shaped rows (no band filters) so it has every row at its "
          "disposal - the nightly narrow model uses the banded fade cohort."]
    fn = f"reports/research/student_picks_sim_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("STUDENT PICKS SIM COMPLETE", flush=True)


if __name__ == "__main__":
    main()

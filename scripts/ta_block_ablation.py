"""TA BLOCK ABLATION (owner order 2026-09-09: adopt the classic-TA feature idea from the
CodeTrading video ONLY if it survives our own gauntlet).

Question: do classic price/volume technical indicators on the UNDERLYING's daily bars -
computed strictly at D-1 (information-time discipline) - add out-of-fold AUC to the wide
student beyond its existing options/flow features? Method identical to the VOL/IVX ablation:
BASE vs BASE+TA, day-grouped GroupKFold, plus a CANARY run (outcome leaked as a feature)
that must hit ~0.99 or the harness itself is broken. Observer-only research; the nightly
student adopts the block in a later commit only if this survives.
Output: reports/research/ta_block_ablation_<date>.md + Telegram summary."""
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import numpy as np
import fade_meta as fm

H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}

TA_NAMES = ["rsi5", "rsi14", "macd_hist", "cci20", "willr14", "roc10",
            "bb_pos20", "atr14_ratio", "obv_slope10", "nvi_slope10"]


def bars_for(tkr):
    end = date.today().isoformat()
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={tkr}&timeframe=1Day"
         f"&start=2024-05-01&end={end}&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                bs = (json.loads(r.read()).get("bars") or {}).get(tkr) or []
            return ([b["t"][:10] for b in bs], np.array([b["c"] for b in bs], float),
                    np.array([b["h"] for b in bs], float), np.array([b["l"] for b in bs], float),
                    np.array([b["v"] for b in bs], float))
        except Exception:
            pass
    return None


def rsi(c, n):
    d = np.diff(c)
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    au = np.full(len(c), np.nan)
    ad = np.full(len(c), np.nan)
    if len(c) <= n:
        return au
    au[n] = up[:n].mean()
    ad[n] = dn[:n].mean()
    for i in range(n + 1, len(c)):
        au[i] = (au[i - 1] * (n - 1) + up[i - 1]) / n
        ad[i] = (ad[i - 1] * (n - 1) + dn[i - 1]) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        return 100 - 100 / (1 + au / np.where(ad == 0, np.nan, ad))


def ema(c, n):
    out = np.full(len(c), np.nan)
    if len(c) < n:
        return out
    k = 2 / (n + 1)
    out[n - 1] = c[:n].mean()
    for i in range(n, len(c)):
        out[i] = c[i] * k + out[i - 1] * (1 - k)
    return out


def ta_features(dates, c, h, l, v):
    n = len(c)
    feats = {}
    r5, r14 = rsi(c, 5), rsi(c, 14)
    macd = ema(c, 12) - ema(c, 26)
    sig = np.full(n, np.nan)
    ok = ~np.isnan(macd)
    if ok.sum() > 9:
        sig[ok] = ema(macd[ok], 9)
    tp = (h + l + c) / 3
    cci = np.full(n, np.nan)
    wr = np.full(n, np.nan)
    bbp = np.full(n, np.nan)
    atrr = np.full(n, np.nan)
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    obv = np.concatenate([[0.0], np.cumsum(np.sign(np.diff(c)) * v[1:])])
    nvi = np.full(n, 1000.0)
    for i in range(1, n):
        nvi[i] = nvi[i - 1] * (1 + (c[i] / c[i - 1] - 1)) if v[i] < v[i - 1] else nvi[i - 1]
    for i in range(20, n):
        w = tp[i - 19:i + 1]
        md = np.mean(np.abs(w - w.mean()))
        cci[i] = (tp[i] - w.mean()) / (0.015 * md) if md > 0 else 0.0
        sd = c[i - 19:i + 1].std()
        bbp[i] = (c[i] - c[i - 19:i + 1].mean()) / (2 * sd) if sd > 0 else 0.0
    for i in range(14, n):
        hh, ll = h[i - 13:i + 1].max(), l[i - 13:i + 1].min()
        wr[i] = (hh - c[i]) / (hh - ll) * -100 if hh > ll else -50.0
        atrr[i] = tr[i - 14:i].mean() / c[i] * 100 if i >= 14 else np.nan
    roc = np.full(n, np.nan)
    roc[10:] = (c[10:] / c[:-10] - 1) * 100
    obs = np.full(n, np.nan)
    nvs = np.full(n, np.nan)
    vs = np.where(v[10:] > 0, v[10:], np.nan)
    obs[10:] = (obv[10:] - obv[:-10]) / (vs * 10)
    nvs[10:] = (nvi[10:] / nvi[:-10] - 1) * 100
    cols = [r5, r14, macd - sig, cci, wr, roc, bbp, atrr, obs, nvs]
    for i, d in enumerate(dates):
        feats[d] = [col[i] for col in cols]
    return feats


def main():
    X, y, days, cids = fm.cohort(wide=True)
    import sqlite3
    con = sqlite3.connect("file:data/harvest.db?mode=ro", uri=True)
    tkr_by_cid = dict(con.execute("select candidate_id, ticker from candidates"))
    X = np.array(X, float)
    y = np.array(y)
    g = np.array(days)
    tks = sorted({tkr_by_cid.get(c) for c in cids if tkr_by_cid.get(c)})
    print(f"cohort n={len(y)}, tickers={len(tks)}", flush=True)
    lib = {}
    fails = 0
    import time
    for i, t in enumerate(tks):
        b = bars_for(t)
        if b:
            lib[t] = (b[0], ta_features(*b))
        else:
            fails += 1
        time.sleep(0.25)
        if i % 100 == 0:
            print(f"bars {i}/{len(tks)} (fails {fails})", flush=True)
    print(f"bars complete: {len(lib)} ok, {fails} failed", flush=True)
    ta = np.full((len(y), len(TA_NAMES)), np.nan)
    epoch = date(1970, 1, 1).toordinal()
    for i, cid in enumerate(cids):
        t = tkr_by_cid.get(cid)
        if t not in lib:
            continue
        dates, feats = lib[t]
        iso = date.fromordinal(epoch + int(g[i])).isoformat()
        prior = [d for d in dates if d < iso]
        if prior:
            ta[i] = feats[prior[-1]]
    cov = float(np.mean(~np.isnan(ta[:, 0])))
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score

    def run(M):
        keep = [j for j in range(M.shape[1])
                if len(np.unique(M[:, j][~np.isnan(M[:, j])])) >= 2]
        M = M[:, keep]                  # a fold-empty/constant column crashes sklearn binning
        oof = np.full(len(y), np.nan)
        for tr, te in GroupKFold(n_splits=5).split(M, y, g):
            m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.08, random_state=7)
            m.fit(M[tr], y[tr])
            oof[te] = m.predict_proba(M[te])[:, 1]
        k = ~np.isnan(oof)
        return roc_auc_score(y[k], oof[k])

    base = run(X)
    plus = run(np.hstack([X, ta]))
    canary = run(np.hstack([X, ta, y.reshape(-1, 1).astype(float)]))
    verdict = ("SURVIVES - queue the student adoption commit" if plus - base >= 0.005
               else "NOISE - block stays out of the student")
    if canary < 0.95:
        verdict = "HARNESS BROKEN - canary failed, no verdict valid"
    if cov < 0.20:                      # a blind study must say it cannot see, never NOISE
        verdict = f"JOIN FAILED - TA coverage {cov:.1%}, no verdict valid"
    L = [f"# TA BLOCK ABLATION - {date.today().isoformat()}",
         f"cohort n={len(y)}, TA coverage {cov:.1%}, features: {', '.join(TA_NAMES)}",
         f"BASE AUC {base:.4f} | BASE+TA {plus:.4f} (delta {plus - base:+.4f}) | CANARY {canary:.4f}",
         f"VERDICT: {verdict}",
         "Method: day-grouped 5-fold OOF, D-1 information time, identical model to the nightly student."]
    open(f"reports/research/ta_block_ablation_{date.today().isoformat()}.md", "w",
         encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    fm.tg("TA BLOCK ABLATION:\n" + "\n".join(L[1:]))
    print("TA ABLATION COMPLETE", flush=True)


if __name__ == "__main__":
    main()

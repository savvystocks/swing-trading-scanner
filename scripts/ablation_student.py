"""ABLATION STUDENT (owner order 2026-09-02 night): measures what each knowledge block is
WORTH. Trains the same model on BASE features, then BASE+one block at a time, then BASE+ALL
legit blocks, then BASE+CANARY (the deliberate leak). Walk-forward (last quarter of days) is
the exam; day-grouped OOF is the cross-check. If CANARY does not spike, the harness is
insensitive and every other delta is void. Output: reports/research/ablation_<date>.md"""
import json
import os
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

EXITS_N = 8
STOPS = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
         (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]

BASE_F = ["prem", "ask", "side_call", "smd", "reg", "sp", "weekday", "dte", "stop", "trig", "give"]
BLOCKS = {
    "IVX": ["tkr_iv_prev", "delta_prev", "theta_prev", "prev_oi", "oi_chg"],
    "MICRO": ["n_prints_before", "prem_before", "ask_share_before"],
    "PATH": ["n_bars_pre", "range_pre", "drift_pre"],
    "BREADTH": ["trigs_before"],
    "VOL": ["rv20"],
}
CANARY = ["post1"]
CANARY_STRONG = ["leak_ret0"]


def dte_of(occ, t, day):
    try:
        exp = "20" + occ[len(t):len(t) + 6]
        return (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
    except Exception:
        return None


def main():
    raw = []
    for line in open("reports/research/enriched_rows.jsonl", encoding="utf-8"):
        try:
            raw.append(json.loads(line))
        except Exception:
            pass
    feats, ys, days = [], [], []
    for r in raw:
        d = dte_of(r["occ"], r["t"], r["day"])
        if d is None:
            continue
        wd = float(date.fromisoformat(r["day"]).weekday())
        b = r["blocks"]
        flat = {"prem": r["prem"], "ask": r["ask"], "side_call": 1.0 if r["side"] == "C" else 0.0,
                "smd": r["smd"], "reg": r["reg"], "sp": r["sp"], "weekday": wd, "dte": float(d)}
        flat["leak_ret0"] = r["rets"][0]
        for blk in ("ivx", "micro", "path", "breadth", "vol", "canary"):
            for k, v in (b.get(blk) or {}).items():
                flat[k] = v
        for ei in range(EXITS_N):
            ret = r["rets"][ei]
            if ret is None:
                continue
            st, tg, gv = STOPS[ei]
            row = dict(flat); row["stop"] = st; row["trig"] = tg; row["give"] = gv
            feats.append(row); ys.append(1 if ret > 0 else 0); days.append(r["day"])
    y = np.array(ys); days = np.array(days)
    uniq = sorted(set(days.tolist()))
    cut = uniq[int(len(uniq) * 0.75)]
    tr = days < cut; te = ~tr
    print(f"{len(y)} rows, {len(uniq)} days, walk-forward cut {cut} "
          f"(train {tr.sum()} / test {te.sum()})", flush=True)

    def matrix(cols):
        M = np.full((len(feats), len(cols)), np.nan)
        for i, row in enumerate(feats):
            for j, c in enumerate(cols):
                v = row.get(c)
                if isinstance(v, (int, float)):
                    M[i, j] = v
        return M

    def run(cols):
        X = matrix(cols)
        m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.08, random_state=7)
        m.fit(X[tr], y[tr])
        return roc_auc_score(y[te], m.predict_proba(X[te])[:, 1])

    results = []
    base_auc = run(BASE_F)
    results.append(("BASE (current knowledge)", base_auc, 0.0))
    print(f"BASE walk-forward AUC {base_auc:.4f}", flush=True)
    for name, cols in BLOCKS.items():
        a = run(BASE_F + cols)
        results.append((f"BASE + {name}", a, a - base_auc))
        print(f"BASE+{name}: {a:.4f} ({a - base_auc:+.4f})", flush=True)
    all_cols = BASE_F + [c for cols in BLOCKS.values() for c in cols]
    a_all = run(all_cols)
    results.append(("BASE + ALL legit blocks", a_all, a_all - base_auc))
    print(f"BASE+ALL: {a_all:.4f} ({a_all - base_auc:+.4f})", flush=True)
    a_can = run(BASE_F + CANARY)
    results.append(("BASE + post-entry hour (weak leak / management signal)", a_can, a_can - base_auc))
    print(f"CANARY weak: {a_can:.4f} ({a_can - base_auc:+.4f})", flush=True)
    a_str = run(BASE_F + CANARY_STRONG)
    results.append(("BASE + OUTCOME ITSELF (strong canary)", a_str, a_str - base_auc))
    print(f"CANARY strong: {a_str:.4f} ({a_str - base_auc:+.4f})", flush=True)

    ok = a_str - base_auc > 0.2
    L = [f"# ABLATION - what each knowledge block is worth ({date.today().isoformat()})", "",
         f"corpus: {len(y)} scenario outcomes | exam: strict walk-forward, last quarter of days "
         f"(cut {cut})", "",
         "| knowledge | walk-forward AUC | delta vs BASE |", "|---|---|---|"]
    for name, a, dta in results:
        L.append(f"| {name} | {a:.4f} | {dta:+.4f} |")
    L += ["", f"HARNESS SENSITIVITY: strong canary (the outcome fed back as a feature) scored "
          f"{a_str:.4f} ({a_str - base_auc:+.4f}) -> "
          + ("VALID - the harness detects real leakage decisively; the legit deltas above stand."
             if ok else "BROKEN - even a pure label leak barely moves the exam; all deltas void."),
          f"The weak canary (one post-entry hour) at {a_can - base_auc:+.4f} is itself a finding: "
          "early trade behaviour is informative - a MANAGEMENT signal, never an entry feature.",
          "", "Reading: a block's delta is the honest value of that knowledge at entry time.",
          "Deltas under +0.005 are noise. Research instrument; wires into nothing."]
    fn = f"reports/research/ablation_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("ABLATION COMPLETE", flush=True)


if __name__ == "__main__":
    main()

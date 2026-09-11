"""STUDENT MODEL EXPORT (2026-09-11, panel-corrected). Trains each picker in the spec's
probe.student block on the honest as-of corpus and exports it as dependency-free JSON:
  - thresholds from the WALK-FORWARD out-of-sample score stream's last 60 sessions (never
    in-sample), for k in 1..3, the same calibration the search used;
  - the walk-forward AUC on the honest columns, printed; a picker at or under 0.50 is marked
    "pulled" in the spec (owner decision 4, recommended default) and does not trade;
  - a DATED file, its path pinned in the spec, and probe.tuning.<name>.applied = today so the
    court's evidence clock restarts on any model change;
  - refuses to re-export a picker with an open case (any live fill in the last 14 days) unless
    STUDENT_FORCE_REFIT=1 by owner order (teacher-freeze, in code);
  - asserts evaluator parity <= 1e-4 and refuses to write otherwise;
  - appends the names to probe.priority so the Friday court judges them.
Writes the spec with verify-after-push, like the tuner.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import numpy as np
from src import student_features as sfx

ASOF = "reports/research/student_asof_v3.jsonl"
EXIT_IDX = {"BASE": 0, "WIDE": 5}


def tg(msg):
    try:
        import urllib.parse, urllib.request
        tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if tok and chat:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
    except Exception:
        pass


def cohort_mask(rows, name):
    out = []
    for r in rows:
        if name == "AFFORD":
            out.append(4.0 <= r["entry"] <= 9.9)
        elif name == "CALLS":
            out.append(r["side"] == "C")
        elif name == "CALLS_AFFORD":
            out.append(r["side"] == "C" and 4.0 <= r["entry"] <= 9.9)
        elif name == "FADE":
            out.append((r["smd"] < 0 and r["sp"] < 0) if r["side"] == "C" else (r["smd"] > 0 and r["sp"] > 0))
        elif name == "ALL":
            out.append(True)
        else:
            raise ValueError(f"unknown cohort {name}")   # never silently 'everything' (2026-09-11: F duplicated A)
    return np.array(out)


def open_case(name, days=14):
    try:
        log = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
        cut = (date.today().toordinal() - days)
        return any(r.get("probe_strategy") == name and (r.get("entry_ts_utc") or "")[:10]
                   and date.fromisoformat(r["entry_ts_utc"][:10]).toordinal() >= cut for r in log)
    except Exception:
        return False


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    from sklearn.metrics import roc_auc_score
    import student_formula_sim as sf
    os.environ["FEATURE_SET"] = "ASOF"
    spec = json.load(open("fade_book_spec.json", encoding="utf-8"))
    stu = (spec.setdefault("probe", {}).setdefault("student", {}))
    probes = stu.get("probes") or {}
    if not probes:
        print("no student probes in the spec"); return
    rows = [json.loads(l) for l in open(ASOF, encoding="utf-8")]
    X = np.array([r["vec"] for r in rows], float)
    days = [r["day"] for r in rows]
    meta = [(r["day"], r["side"], r["reg"], r["smd"], r["sp"], r["entry"], r["rets"], r["occ"]) for r in rows]
    if X.shape[1] != len(sfx.FEATS):
        print(f"REFUSED: as-of corpus has {X.shape[1]} features, module defines {len(sfx.FEATS)} - rebuild the corpus first")
        return
    today = date.today().isoformat()
    os.makedirs("reports/fade_meta", exist_ok=True)
    force = os.environ.get("STUDENT_FORCE_REFIT") == "1"
    lines = [f"STUDENT EXPORT {today}"]
    changed = False
    for name, cfg in sorted(probes.items()):
        target, cohort, ex = cfg.get("target", "PWIN"), cfg.get("cohort", "AFFORD"), cfg.get("exit_label", "BASE")
        if target not in ("PWIN", "PBIG", "EXPRET"):
            lines.append(f"{name}: unknown target {target} - not exported"); continue
        if open_case(name) and not force:
            lines.append(f"{name}: OPEN CASE (fills in the last 14 days) - export refused (teacher-freeze); STUDENT_FORCE_REFIT=1 to override")
            continue
        ei = EXIT_IDX.get(ex, 0)
        rets = np.array([r["rets"][ei] if r["rets"][ei] is not None else np.nan for r in rows])
        cm = cohort_mask(rows, cohort) & ~np.isnan(rets)
        y_all = (np.clip(np.nan_to_num(rets, nan=0.0), -100, 300) if target == "EXPRET"
                 else ((rets > 0) if target == "PWIN" else (rets >= 30)).astype(int))
        # walk-forward OOS stream (quarterly refits) - thresholds and AUC come from HERE
        y_cls = (rets > 0).astype(int); y_big = (rets >= 30).astype(int)
        y_reg = np.clip(np.nan_to_num(rets, nan=0.0), -100, 300)
        oos = sf.fit_stream(X, y_cls, y_big, y_reg, days, target, cm)
        have = cm & ~np.isnan(oos)
        _ywin = (rets > 0).astype(int)              # AUC always vs "did it win", whatever the target
        auc = float(roc_auc_score(_ywin[have], oos[have])) if have.sum() > 50 and len(set(_ywin[have])) > 1 else float("nan")
        thr_co = cfg.get("threshold_cohort") or cohort        # A: trained on ALL, calibrated on AFFORD
        have_t = have & cohort_mask(rows, thr_co)
        sub_days = sorted(set(np.array(days)[have_t]))[-60:]
        tail = have_t & np.isin(np.array(days), sub_days)
        weeks = max(1, len({date.fromisoformat(d).isocalendar()[:2] for d in np.array(days)[tail]}))
        per_week = tail.sum() / weeks
        thr = {}
        for k in (1, 2, 3):
            q = 1.0 - min(0.5, (k * 1.5) / per_week)
            thr[f"k{k}"] = float(np.quantile(oos[tail], q))
        # walk-forward result on the THRESHOLD cohort (what this picker will actually see live)
        try:
            _sc = oos.copy(); _sc[~have_t] = np.nan
            _pk = sf.pick_weekly(_sc, days, have_t, int(cfg.get("k_per_week", 3)))
            _ev = sf.evaluate(_pk, meta, ei, name + " on " + thr_co)
            live_slice = ({"trades": _ev["trades"], "weeks": _ev["weeks"], "per_trade": round(_ev["per_trade"], 1),
                           "win": round(_ev["win"], 3), "wk_t": round(_ev["wk_t"], 2), "pos_weeks": round(_ev["pos_weeks"], 2),
                           "total": round(_ev["total"])} if _ev else None)
        except Exception as _le:
            live_slice = {"error": type(_le).__name__}
        # final model on all rows of the cohort
        if target == "EXPRET":
            m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=150, random_state=7)
        else:
            m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=150, random_state=7)
        m.fit(X[cm], y_all[cm])
        exported = sfx.export_hgb(m)
        idx = np.where(cm)[0][:300]
        ours = np.array([sfx.predict(exported, list(X[i])) for i in idx])
        ref = m.predict(X[idx]) if target == "EXPRET" else m.predict_proba(X[idx])[:, 1]
        err = float(np.max(np.abs(ours - ref)))
        if err > 1e-4:
            lines.append(f"{name}: evaluator parity error {err:.2e} > 1e-4 - export REFUSED"); continue
        nan_rate = {f: float(np.mean(np.isnan(X[cm][:, j]))) for j, f in enumerate(sfx.FEATS)}
        out = dict(exported, name=name, target=target, cohort=cohort, exit_label=ex, trained=today,
                   n_train=int(cm.sum()), feats=sfx.FEATS, thresholds=thr, parity_max_err=err,
                   walk_forward_auc=auc, training_nan_rate=nan_rate, threshold_cohort=thr_co,
                   walk_forward_on_threshold_cohort=live_slice,
                   corpus_sha256=hashlib.sha256(open(ASOF, "rb").read()).hexdigest()[:16])
        fname = f"reports/fade_meta/student_{name}_{today}.json"
        json.dump(out, open(fname, "w", encoding="utf-8"))
        cfg["model"] = fname
        _neg = bool(isinstance(live_slice, dict) and live_slice.get("wk_t") is not None
                    and live_slice.get("trades", 0) >= 40 and live_slice["wk_t"] <= -1.5)
        cfg["pulled"] = bool(auc == auc and auc <= 0.50) or _neg   # owner decision 4, extended 2026-09-11: a
        if cfg["pulled"]:                                          # picker that LOSES on the slice it would
            cfg["live"] = False                                    # trade (t <= -1.5, n >= 40) never goes live
        spec["probe"].setdefault("tuning", {}).setdefault(name, {})["applied"] = today   # court clock restarts
        if "STUDENT_FAMILY" not in (spec["probe"].get("priority") or []):
            spec["probe"].setdefault("priority", []).append("STUDENT_FAMILY")             # the court judges the FAMILY
        changed = True
        lines.append(f"{name}: {target}/{cohort}/{ex} n={int(cm.sum())} walk-forward AUC {auc:.3f} | on {thr_co}: {live_slice}"
                     f"{' -> PULLED' if cfg['pulled'] else ''} thresholds "
                     f"{ {k: round(v, 4) for k, v in thr.items()} } parity {err:.1e} -> {fname}")
    print("\n".join(lines), flush=True)
    if changed:
        json.dump(spec, open("fade_book_spec.json", "w", encoding="utf-8"), indent=1)
        subprocess.run("git add fade_book_spec.json reports/fade_meta/student_*.json && git commit -qm "
                       "'student export: dated picker models, thresholds from the walk-forward stream, court clock stamped [skip ci]' && "
                       "git pull -q --rebase --autostash -X ours && git push -q", shell=True)
        try:                                                # verify-after-push (2026-09-09 lesson)
            chk = json.load(open("fade_book_spec.json", encoding="utf-8"))
            lost = [n for n in probes if ((chk.get("probe") or {}).get("student") or {}).get("probes", {}).get(n, {}).get("model") != probes[n].get("model")]
            if lost:
                lines.append("SPEC WRITE LOST for: " + ", ".join(lost))
        except Exception as e:
            lines.append(f"verify failed: {type(e).__name__}")
    tg("\n".join(lines))
    print("STUDENT EXPORT COMPLETE", flush=True)


if __name__ == "__main__":
    main()

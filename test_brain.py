import os, sys, ast, json, gzip, sqlite3, tempfile, shutil
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.brain import weights as W, harness as H, calibration as C, ev as EV, foundry, loader, run_weekly

DAY = 24 * 3600 * 1000
fails = []
def chk(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- GATE 1 weights
def test_gate1_overlap_weights():
    import pandas as pd
    # 3-day contract fully inside a 30-day contract, same underlying
    df = pd.DataFrame({
        "candidate_id": ["A30", "B3"], "ticker": ["XYZ", "XYZ"],
        "signal_ts": [0, 10 * DAY], "resolution_ts": [30 * DAY, 13 * DAY]})
    out, _ = W.compute_weights(df)
    wa = float(out.loc[out.candidate_id == "A30", "weight"].iloc[0])
    wb = float(out.loc[out.candidate_id == "B3", "weight"].iloc[0])
    chk("gate1 asymmetric: 30-day weight ~ 0.95", abs(wa - 0.95) < 1e-6, f"{wa:.6f}")
    chk("gate1 asymmetric: 3-day nested weight ~ 0.50", abs(wb - 0.5) < 1e-6, f"{wb:.6f}")
    # same ticker, non-overlapping -> 1.0 each
    df2 = pd.DataFrame({"candidate_id": ["C", "D"], "ticker": ["XYZ", "XYZ"],
                        "signal_ts": [0, 100 * DAY], "resolution_ts": [5 * DAY, 105 * DAY]})
    out2, _ = W.compute_weights(df2)
    chk("gate1 non-overlap: both weight 1.0",
        abs(out2["weight"].iloc[0] - 1.0) < 1e-9 and abs(out2["weight"].iloc[1] - 1.0) < 1e-9,
        f"{out2['weight'].tolist()}")


def test_weight_cache_equality():
    import pandas as pd
    rng = np.random.default_rng(1)
    rows = []
    # old, stable group + a recent unstable group (same and different tickers)
    for i in range(20):
        s = int(rng.integers(0, 3 * DAY)); rows.append(("old%d" % i, "AAA", s, s + int(rng.integers(DAY, 4 * DAY))))
    for i in range(15):
        s = int(58 * DAY + rng.integers(0, 3 * DAY)); rows.append(("new%d" % i, "BBB", s, s + int(rng.integers(DAY, 4 * DAY))))
    df = pd.DataFrame(rows, columns=["candidate_id", "ticker", "signal_ts", "resolution_ts"])
    newest = float(df["signal_ts"].max())
    full, cache = W.compute_weights(df, newest_signal_ts=newest)
    cached, _ = W.compute_weights(df, cache=cache, newest_signal_ts=newest)
    eq = np.allclose(full["weight"].to_numpy(), cached["weight"].to_numpy(), atol=1e-12)
    n_stable = sum(1 for v in cache.values() if v["final"])
    chk("gate4a cache == full recompute", eq, f"n_stable={n_stable}/{len(cache)}")


# ---------------------------------------------------------------- PurgedKFold leakage
def _random_kfold(n, k, seed=0):
    idx = np.arange(n); np.random.default_rng(seed).shuffle(idx)
    return [np.sort(f) for f in np.array_split(idx, k)]

def _nn_time_acc(train_s, train_y, test_s, test_y):
    preds = np.array([train_y[np.argmin(np.abs(train_s - t))] for t in test_s])
    return float(np.mean(preds == test_y))

def test_purgedkfold_leakage():
    rng = np.random.default_rng(7)
    starts, ends, labels = [], [], []
    for c in range(60):                              # 60 clusters, 6 overlapping rows each, shared label
        base = c * 100 * DAY
        y = int(rng.choice([-1, 1]))
        for _ in range(6):
            s = base + int(rng.integers(0, 5 * DAY))
            starts.append(s); ends.append(s + 20 * DAY); labels.append(y)
    starts = np.array(starts, float); ends = np.array(ends, float); labels = np.array(labels)
    n = len(starts)
    # naive random KFold - overlapping cluster-mates leak into train
    naive = []
    for test_idx in _random_kfold(n, 5):
        tr = np.setdiff1d(np.arange(n), test_idx)
        naive.append(_nn_time_acc(starts[tr], labels[tr], starts[test_idx], labels[test_idx]))
    naive_acc = float(np.mean(naive))
    # PurgedKFold - overlapping train rows purged, so the leak is removed
    purged = []
    for tr, te in H.PurgedKFold(5, embargo_frac=0.0).split(starts, ends):
        if len(tr) == 0 or len(te) == 0:
            continue
        purged.append(_nn_time_acc(starts[tr], labels[tr], starts[te], labels[te]))
    purged_acc = float(np.mean(purged))
    chk("leakage: naive KFold shows inflated skill", naive_acc > 0.75, f"naive={naive_acc:.3f}")
    chk("leakage: PurgedKFold discriminates (near chance)", purged_acc < 0.65, f"purged={purged_acc:.3f}")
    chk("leakage: naive >> purged (build-failure guard)", naive_acc - purged_acc > 0.2,
        f"gap={naive_acc - purged_acc:.3f}")


# ---------------------------------------------------------------- GATE 2 EV solver
def test_ev_solver():
    # fat-tailed with gap-throughs: wins {+.3,+.5,+.4}, losses {-.5,-.6,-1.0}
    r = np.array([0.3, 0.5, 0.4, -0.5, -0.6, -1.0])
    mu_win = (0.3 + 0.5 + 0.4) / 3
    mu_loss = (-0.5 - 0.6 - 1.0) / 3
    cost = 0.02
    expected = (cost - mu_loss) / (mu_win - mu_loss)      # hand-computed closed form
    res = EV.solve_threshold(r, cost=cost, n_boot=200)
    chk("EV threshold matches closed form", abs(res["threshold"] - expected) < 1e-9,
        f"{res['threshold']:.6f} vs {expected:.6f}")
    chk("EV(p*) == 0", abs(EV.ev_of_p(res["threshold"], mu_win, mu_loss, cost)) < 1e-9)
    st = EV.class_stats(r, np.array(["up", "up", "up", "down", "down", "down"]))
    chk("gap-through captured (down below -0.50)", st["gap_through"]["down_below_-0.50_rate"] > 0,
        f"rate={st['gap_through']['down_below_-0.50_rate']}")
    chk("EV bootstrap CI present", np.isfinite(res["ci"][0]) and np.isfinite(res["ci"][1]),
        f"CI={res['ci']}")


# ---------------------------------------------------------------- GATE 3 calibration selection
def _synth_scores(n, seed):
    rng = np.random.default_rng(seed)
    s = rng.normal(0, 1, n)
    y = (rng.random(n) < C._sigmoid(1.2 * s)).astype(int)
    return s, y

def test_calibration_selection():
    s, y = _synth_scores(200, 1)
    thin = C.calibrate(s, y, n_threshold=1000)
    s2, y2 = _synth_scores(5000, 2)
    thick = C.calibrate(s2, y2, n_threshold=1000)
    chk("calibration thin n -> sigmoid", thin["selected"] == "sigmoid", thin["reason"])
    chk("calibration thick n -> isotonic", thick["selected"] == "isotonic", thick["reason"])
    chk("both Brier scores reported", set(thin["brier"]) == {"sigmoid", "isotonic"}, str(thin["brier"]))
    p = thick["predict"](np.array([-2.0, 0.0, 2.0]))
    chk("isotonic predictions monotone in score", p[0] <= p[1] <= p[2], f"{p}")


# ---------------------------------------------------------------- two-way isolation
EXEC_MODULES = {"sandbox_proactive_lab", "poller", "harvest_db", "harvest_labeler", "harvest_logger",
                "harvest", "tune_parameters", "v10_params", "v11_mot_harness", "prototype_alt_data",
                "sandbox_v10_upgrades", "sandbox_v11_sensors", "funnel_autopsy", "v9_diagnostic"}
EXEC_SRC = {"catalyst", "telegram", "terminal", "unusual_whales_api", "alpaca_creds",
            "alpaca_ohlcv", "alpaca_options", "indicators", "conviction", "pillars", "universe"}

def _imports(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception:
        return []
    mods = []
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Import):
            mods += [a.name for a in nd.names]
        elif isinstance(nd, ast.ImportFrom) and nd.module:
            mods.append(nd.module)
    return mods

def test_isolation():
    root = os.path.dirname(os.path.abspath(__file__))
    brain_dir = os.path.join(root, "src", "brain")
    # (a) src/brain imports NO execution module
    a_ok = True; a_bad = []
    for dp, _, fns in os.walk(brain_dir):
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            for m in _imports(os.path.join(dp, fn)):
                top = m.split(".")[0]
                if top in EXEC_MODULES or (top == "src" and len(m.split(".")) > 1 and m.split(".")[1] in EXEC_SRC):
                    a_ok = False; a_bad.append(f"{fn}: {m}")
    chk("isolation: src/brain imports no execution module", a_ok, str(a_bad[:5]))
    # (b) no live engine/poller module imports src.brain
    b_ok = True; b_bad = []
    for dp, dns, fns in os.walk(root):
        if ".git" in dp or "worktrees" in dp or os.path.join("src", "brain") in dp:
            continue
        for fn in fns:
            if not fn.endswith(".py") or fn == "test_brain.py":
                continue
            for m in _imports(os.path.join(dp, fn)):
                if m == "brain" or m.startswith("src.brain") or m.endswith(".brain"):
                    b_ok = False; b_bad.append(f"{fn}: {m}")
    chk("isolation: no engine/poller module imports src.brain", b_ok, str(b_bad[:5]))


# ---------------------------------------------------------------- synthetic snapshot + end-to-end
def build_synthetic_snapshot(gz_path, n=140, seed=11):
    rng = np.random.default_rng(seed)
    tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "SPY"]
    fsv = "fs_v3"
    con = sqlite3.connect(":memory:")
    con.executescript("""
      CREATE TABLE candidates (candidate_id TEXT PRIMARY KEY, run_id TEXT, code_version TEXT,
        feature_set_version TEXT, signal_ts_utc INTEGER, ticker TEXT, occ_symbol TEXT, expiry TEXT,
        strike REAL, "right" TEXT, side TEXT, bid REAL, ask REAL, bid_size REAL, ask_size REAL, mid REAL,
        spread_pct REAL, last REAL, underlying_last REAL, entry_ref REAL, features TEXT, rule_score REAL,
        executed INTEGER, skip_reason TEXT, vertical_barrier_ts INTEGER, barrier_up_pct REAL,
        barrier_down_pct REAL, poll_tier TEXT, sample_tier TEXT);
      CREATE TABLE bid_path (id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT, poll_ts_utc INTEGER,
        bid REAL, ask REAL, quote_ts INTEGER, stale INTEGER);
      CREATE TABLE labels (candidate_id TEXT PRIMARY KEY, outcome TEXT, label INTEGER, realized_return REAL,
        touch_ts_utc INTEGER, time_to_touch_min REAL, mfe REAL, mae REAL, n_polls INTEGER, n_stale INTEGER,
        ambiguous_touch INTEGER, poll_cadence_min REAL, censored_reason TEXT);
    """)
    base = 1_780_000_000_000
    for i in range(n):
        tk = tickers[i % len(tickers)]
        sig = base + int(rng.integers(0, 5 * DAY))
        entry = float(rng.uniform(0.5, 4.0))
        spread = float(rng.uniform(1, 8))
        executed = int(rng.random() < 0.4)
        tier = rng.choice(["topn", "random", "quota_cap", "prefilter"], p=[0.15, 0.15, 0.4, 0.3])
        vbar = sig + int(rng.integers(1, 5) * DAY)
        feats = {"macro": {"spot": float(rng.uniform(50, 500)), "vix": float(rng.uniform(12, 30))},
                 "iv_term": {"iv_ratio": float(rng.uniform(0.8, 1.3))},
                 "flow": {"sweep_pct": float(rng.uniform(0, 100))}}
        con.execute("INSERT INTO candidates (candidate_id,run_id,code_version,feature_set_version,"
                    "signal_ts_utc,ticker,occ_symbol,strike,\"right\",side,spread_pct,entry_ref,features,"
                    "rule_score,executed,vertical_barrier_ts,barrier_up_pct,barrier_down_pct,poll_tier,sample_tier)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"c{i}", "r1", "v10", str(fsv), sig, tk, f"{tk}260717C0001", 100.0, "call", "long",
                     spread, entry, json.dumps(feats), float(rng.uniform(2e4, 2e6)), executed, vbar, 0.30, -0.50,
                     "standard", str(tier)))
        # outcome: mix of up/down/vertical + a few censored/open (excluded by the Foundry)
        u = rng.random()
        if u < 0.30:
            outcome, label, ret = "up", 1, float(rng.choice([0.30, 0.45, 0.9]))          # +touch, some beyond +30%
            touch = sig + int(rng.integers(1, 3) * DAY)
        elif u < 0.60:
            outcome, label, ret = "down", -1, float(rng.choice([-0.50, -0.75, -1.0]))    # -touch, gap-throughs
            touch = sig + int(rng.integers(1, 3) * DAY)
        elif u < 0.85:
            ret = float(rng.uniform(-0.4, 0.4)); outcome = "vertical"; label = 1 if ret > 0 else -1
            touch = vbar
        elif u < 0.93:
            con.execute("INSERT INTO labels (candidate_id,outcome,label,censored_reason) VALUES (?,?,?,?)",
                        (f"c{i}", "censored", None, "no_fresh_quote_at_vertical")); continue
        else:
            con.execute("INSERT INTO labels (candidate_id,outcome,label) VALUES (?,?,?)",
                        (f"c{i}", "open", None)); continue
        ttt = (touch - sig) / 60000.0
        con.execute("INSERT INTO labels (candidate_id,outcome,label,realized_return,touch_ts_utc,"
                    "time_to_touch_min,mfe,mae,n_polls,n_stale,ambiguous_touch,poll_cadence_min)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"c{i}", outcome, label, ret, touch, ttt, max(ret, 0.1), min(ret, -0.05), 5, 0, 0, 15.0))
        for p in range(3):
            pts = sig + p * 3600 * 1000
            con.execute("INSERT INTO bid_path (candidate_id,poll_ts_utc,bid,ask,quote_ts,stale) VALUES (?,?,?,?,?,?)",
                        (f"c{i}", pts, entry * (1 + 0.1 * p), entry * (1 + 0.1 * p) + 0.05, pts, 0))
    con.commit()
    tmp = gz_path[:-3]
    disk = sqlite3.connect(tmp); con.backup(disk); disk.close(); con.close()
    with open(tmp, "rb") as f, gzip.open(gz_path, "wb") as g:
        shutil.copyfileobj(f, g)
    os.remove(tmp)
    return gz_path

def test_end_to_end_synthetic():
    d = tempfile.mkdtemp(prefix="brain_test_")
    gz = build_synthetic_snapshot(os.path.join(d, "harvest_20260704_2130.db.gz"))
    out = run_weekly.run(gz, os.path.join(d, "work"), os.path.join(d, "reports"))
    md = out["markdown"]
    chk("end-to-end: report written", os.path.exists(out["report_path"]))
    chk("end-to-end: dataset non-empty", out["summary"]["rows"] > 0, f"rows={out['summary']['rows']}")
    chk("end-to-end: report has EV + verdict sections",
        "Empirical EV thresholds" in md and "Verdict" in md)
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    test_gate1_overlap_weights()
    test_weight_cache_equality()
    test_purgedkfold_leakage()
    test_ev_solver()
    test_calibration_selection()
    test_isolation()
    test_end_to_end_synthetic()
    total = 7 * 3
    print(f"\nTOTAL: brain suite - {len(fails)} failure(s)")
    if fails:
        raise SystemExit("FAILS: " + ", ".join(fails))
    print("BRAIN SUITE PASS: isolation intact, leakage caught, weights + EV + calibration verified")

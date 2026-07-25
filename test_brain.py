import os, sys, ast, json, gzip, sqlite3, tempfile, shutil
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.brain import weights as W, harness as H, calibration as C, ev as EV, foundry, loader, run_weekly
from src.brain import discovery as D, convergence as CV, student as S

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
            # test + MOT harnesses are NOT execution modules (never on the trade path); they may import
            # the brain to assert its behavior, exactly as test_brain.py does.
            if not fn.endswith(".py") or fn.startswith("test_") or fn.endswith("_mot.py") \
                    or fn.endswith("_mot_harness.py"):
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

def test_foundry_pools_across_params_hash():
    # params_hash fingerprints the WHOLE tunables dict, so it rotates on any operational-config change
    # (e.g. a backstop canary swap) with NO change to the trading recipe. The Foundry must pool every row
    # across all params_hash values and never segment by them, or an ops change would fragment the brain's
    # first training sample. This locks that invariant: a snapshot with 2 distinct hashes must come back
    # fully pooled, every row of both cohorts present.
    d = tempfile.mkdtemp(prefix="brain_hash_")
    dbp = os.path.join(d, "harvest.db")
    con = sqlite3.connect(dbp)
    con.executescript("""
      CREATE TABLE candidates (candidate_id TEXT PRIMARY KEY, feature_set_version TEXT, signal_ts_utc INTEGER,
        ticker TEXT, occ_symbol TEXT, entry_ref REAL, features TEXT, rule_score REAL, executed INTEGER,
        vertical_barrier_ts INTEGER, barrier_up_pct REAL, barrier_down_pct REAL, sample_tier TEXT,
        spread_pct REAL, params_hash TEXT);
      CREATE TABLE bid_path (id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT, poll_ts_utc INTEGER,
        bid REAL, ask REAL, quote_ts INTEGER, stale INTEGER);
      CREATE TABLE labels (candidate_id TEXT PRIMARY KEY, outcome TEXT, label INTEGER, realized_return REAL,
        touch_ts_utc INTEGER, time_to_touch_min REAL, mfe REAL, mae REAL, n_polls INTEGER, n_stale INTEGER,
        ambiguous_touch INTEGER, poll_cadence_min REAL, censored_reason TEXT);
    """)
    base = 1_780_000_000_000
    hashes = ["hashOLD_recipe", "hashNEW_after_canary_swap"]   # SAME recipe; hash rotated by an ops change
    n_each = 20
    for h_i, h in enumerate(hashes):
        for j in range(n_each):
            cid = f"c{h_i}_{j}"
            sig = base + (h_i * 100 + j) * (DAY // 10)
            con.execute("INSERT INTO candidates (candidate_id,feature_set_version,signal_ts_utc,ticker,occ_symbol,"
                        "entry_ref,features,rule_score,executed,vertical_barrier_ts,barrier_up_pct,barrier_down_pct,"
                        "sample_tier,spread_pct,params_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, "fs_v3", sig, "AAPL", "AAPL260717C0001", 2.0, json.dumps({"flow": {"x": 1.0}}),
                         1e5, j % 2, sig + 2 * DAY, 0.30, -0.50, "topn", 3.0, h))
            ret = 0.30 if j % 2 == 0 else -0.50
            con.execute("INSERT INTO labels (candidate_id,outcome,label,realized_return,touch_ts_utc,"
                        "time_to_touch_min,mfe,mae,n_polls,n_stale,ambiguous_touch,poll_cadence_min) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, "up" if ret > 0 else "down", 1 if ret > 0 else -1, ret, sig + DAY, 1440.0,
                         max(ret, 0.1), min(ret, -0.05), 5, 0, 0, 15.0))
            con.execute("INSERT INTO bid_path (candidate_id,poll_ts_utc,bid,ask,quote_ts,stale) VALUES (?,?,?,?,?,?)",
                        (cid, sig, 2.0, 2.1, sig, 0))
    con.commit(); con.close()
    res = foundry.build_dataset({"db_path": dbp, "snapshot_id": "hashtest"}, os.path.join(d, "work"))
    df = res["df"]
    present = set(df["params_hash"].dropna().unique())
    per = df["params_hash"].value_counts().to_dict()
    chk("foundry pools BOTH params_hash cohorts (no segmentation)", present == set(hashes), f"present={present}")
    chk("foundry keeps every gradeable row across hashes", len(df) == 2 * n_each, f"rows={len(df)} exp={2 * n_each}")
    chk("foundry: each hash cohort fully represented", all(per.get(h) == n_each for h in hashes), f"{per}")
    shutil.rmtree(d, ignore_errors=True)


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


# ---------------------------------------------------------------- discovery rig honesty
def _discovery_df(n, seed, leak_signal=False):
    import pandas as pd
    rng = np.random.default_rng(seed)
    day = DAY // 24
    start = np.arange(n) * day * 6.0
    f1 = rng.random(n)
    f2 = rng.random(n)
    y = (rng.random(n) < 0.25).astype(float)
    half = n // 2
    y[:half] = np.where(f1[:half] > 0.67, 1.0, (rng.random(half) < 0.25).astype(float))
    both = f2 > 0.67
    y[both] = (rng.random(both.sum()) < 0.85).astype(float)
    if leak_signal:
        y[half:] = np.where(f1[half:] > 0.67, 1.0, y[half:])
    df = pd.DataFrame({
        "candidate_id": [f"d{i}" for i in range(n)], "ticker": [f"T{i % 40}" for i in range(n)],
        "occ_symbol": "OCC", "signal_ts": start, "window_start": start, "window_end": start + day,
        "y_up": y, "weight": 1.0, "w_raw": 1.0, "outcome": np.where(y > 0, "up", "down"),
        "realized_return": np.where(y > 0, 0.4, -0.4), "cost_base": 0.02,
        "net_ret": np.where(y > 0, 0.38, -0.42), "executed": 0, "sample_tier": "topn"})
    X = pd.DataFrame({"f.a.one": f1, "f.a.two": f2})
    return df, X, ["f.a.one", "f.a.two"]


def test_discovery_oos_only():
    # a rule that is perfect ONLY in the discovery half must NOT come back confirmed; a rule real in
    # BOTH halves must. Grading never touches discovery data.
    df, X, kept = _discovery_df(1200, seed=3)
    tr = D.Trials()
    cfg = {**CV.BASE_CFG, "slice": "first_to_second", "learner": "rules"}
    res = CV.run_variant(df, X, kept, cfg, tr)
    sig_fake = "a.one:HIGH"
    sig_real = "a.two:HIGH"
    fake = res.get(sig_fake, {"status": "absent"})["status"]
    real = res.get(sig_real, {"status": "absent"})["status"]
    chk("discovery: train-only pattern is NOT confirmed OOS", fake != "confirmed", f"fake={fake}")
    chk("discovery: genuine pattern IS confirmed OOS", real == "confirmed", f"real={real}")
    chk("discovery: every candidate rule was counted", tr.counts.get("rules_evaluated", 0) >= 6,
        f"trials={tr.as_dict()}")


def test_discovery_walkforward_purge():
    # a candidate whose label window crosses the test week's open must be EXCLUDED from training
    df, X, kept = _discovery_df(900, seed=5)
    wk = D.week_key(df["signal_ts"])
    weeks = sorted(np.unique(wk))
    test_week = weeks[-1]
    t_open = float(df.loc[wk == test_week, "window_start"].min())
    leak = (wk < test_week) & (df["window_end"].to_numpy() > t_open - D.EMBARGO_MS)
    eligible = int(((df["window_end"].to_numpy() <= t_open - D.EMBARGO_MS) & (wk < test_week)).sum())
    tr = D.Trials()
    cfg = {**CV.BASE_CFG, "learner": "rules"}
    wf = D.walk_forward(df, X, kept, cfg, tr)
    last = [w for w in wf["windows"] if w["week"].endswith(str(test_week)[4:])]
    chk("discovery: walk-forward train excludes window-crossing rows",
        bool(last) and last[0]["n_train"] == eligible,
        f"n_train={last[0]['n_train'] if last else None} eligible={eligible} leaky={int(leak.sum())}")
    chk("discovery: ledger only contains test-week rows with decisions",
        wf["ledger"].empty or set(wf["ledger"]["decision"].unique()) <= {"TAKE", "skip"})


def test_student_stage2():
    import pandas as pd
    # decay: exactly half at one half-life
    ts = np.array([0.0, S.HALF_LIFE_DAYS * S.DAY_MS], dtype=np.float64)
    dec = S.time_decay(ts, S.HALF_LIFE_DAYS, now_ts=ts[1])
    chk("student: time-decay halves at one half-life", abs(dec[0] - 0.5) < 1e-9 and dec[1] == 1.0,
        str(dec))
    # clustering kills a planted duplicate feature
    rng = np.random.default_rng(2)
    f1 = rng.random(400)
    Xc = pd.DataFrame({"f.a.one": f1, "f.a.dup": f1 * 2 + 1e-9 * rng.random(400),
                       "f.b.other": rng.random(400)})
    reduced, dropped = S.cluster_features(Xc, list(Xc.columns))
    chk("student: correlation clustering drops the duplicate",
        len(reduced) == 2 and ("f.a.dup" in dropped or "f.a.one" in dropped), f"{reduced} {dropped}")
    # end-to-end provisional train on synthetic data + the gate honesty
    df, X, kept = _discovery_df(1200, seed=9)
    tr = D.Trials()
    trained = S.train_student(df, X, kept, tr)
    chk("student: OOF produced under purged folds", trained["n_oof"] > 600,
        f"n_oof={trained['n_oof']}")
    pbo_stub = {"pbo": 0.1, "pbo_note": "", "dsr": 0.9, "dsr_benchmark": 0.0, "dsr_note": "",
                "n_splits": 15, "n_paths": 5, "grid_size": 12, "hurdle": 0.5}
    acc = S.acceptance(trained, pbo_stub, n_fb=1200, trials=tr)
    chk("student: below-gate run is PROVISIONAL with verdict withheld",
        acc["provisional"] and acc["verdict"].startswith("WITHHELD"), acc["verdict"])
    acc2 = S.acceptance(trained, pbo_stub, n_fb=S.GATE_FB, trials=tr)
    chk("student: at-gate run issues an official verdict", not acc2["provisional"]
        and not acc2["verdict"].startswith("WITHHELD"), acc2["verdict"])


def _council_df(n, seed):
    import pandas as pd
    rng = np.random.default_rng(seed)
    day = DAY // 24
    start = np.arange(n) * day * 6.0
    flow = rng.random(n)
    dayrange = rng.random(n)
    ivr = rng.random(n)
    spread = rng.random(n) * 25.0
    noise = rng.random(n)
    # real, learnable signal: high flow AND mid IV win more; wide spread loses
    base = 0.25 + 0.35 * (flow > 0.6) * (ivr > 0.4) - 0.15 * (spread > 15)
    y = (rng.random(n) < np.clip(base, 0.03, 0.95)).astype(float)
    df = pd.DataFrame({
        "candidate_id": [f"c{i}" for i in range(n)], "ticker": [f"T{i % 40}" for i in range(n)],
        "occ_symbol": "OCC", "signal_ts": start, "window_start": start, "window_end": start + day,
        "y_up": y, "weight": 1.0, "w_raw": 1.0, "outcome": np.where(y > 0, "up", "down"),
        "realized_return": np.where(y > 0, 0.4, -0.5), "cost_base": 0.03,
        "net_ret": np.where(y > 0, 0.37, -0.53), "executed": (noise > 0.9).astype(int),
        "sample_tier": "topn", "spread_pct": spread})
    X = pd.DataFrame({"flow_aggression.ask_sweep_prem": flow, "price_action.day_range": dayrange,
                      "iv_term.iv_ratio": ivr, "macro.vix": rng.random(n), "news.vader_compound": noise})
    return df, X, list(X.columns)


def test_council_stage2():
    from src.brain import council as CC
    from src.brain import ttl as TTL
    df, X, kept = _council_df(1400, seed=11)
    tr = D.Trials()
    res = CC.run_council(df, X, kept, tr)
    chk("council: all five members are defined", len(res["members"]) == 5)
    scoring = [m for m in res["members"] if res["member_auc"][m] is not None]
    chk("council: at least a quorum of members produced calibrated scores", len(scoring) >= 3,
        f"scoring={scoring}")
    chk("council: blended OOF AUC recovers the planted signal", res["blend_auc"] > 0.55,
        f"blend_auc={res['blend_auc']}")
    chk("council: disagreement is measured per candidate", np.isfinite(res["disagree"]).any())
    # FAIL-CLOSED: a member that raises -> component_failure VETO (never a silent take)
    good = {m: (lambda fr, a, d, p=0.9: p) for m in ["gbm_meta", "logistic_linear", "base_rate_2d"]}
    boom = dict(good); boom["flow_specialist"] = (lambda fr, a, d: (_ for _ in ()).throw(RuntimeError("x")))
    dec = CC.score_one(boom, {"_contract_bar": 0.5}, 0, 0)
    chk("council: a failed component forces a VETO (fail-closed)",
        dec["decision"] == "VETO" and dec["reason"] == "component_failure", str(dec)[:80])
    # latency budget exceeded -> VETO
    slow = {"m1": (lambda fr, a, d: __import__("time").sleep(0.05) or 0.9)}
    dec2 = CC.score_one(slow, {"_contract_bar": 0.5}, 0, 0, latency_budget_s=0.0)
    chk("council: latency budget breach is a VETO", dec2["decision"] == "VETO"
        and dec2["reason"] == "latency_exceeded", str(dec2)[:80])
    # a clean quorum that clears the bar with tight agreement -> TAKE
    agree = {m: (lambda fr, a, d: 0.80) for m in ["gbm_meta", "logistic_linear", "base_rate_2d", "flow_specialist"]}
    dec3 = CC.score_one(agree, {"_contract_bar": 0.55}, 0, 0)
    chk("council: aligned quorum above the bar TAKES", dec3["decision"] == "TAKE", str(dec3)[:80])
    # TTL: an old asof nulls a short-TTL block but preserves a long-TTL block
    import pandas as pd
    Xt = pd.DataFrame({"quotes_and_spreads.bid": [1.0, 2.0], "fundamentals.short_ratio": [3.0, 4.0]})
    sig = np.array([0.0, 0.0])
    out = TTL.apply_ttl(Xt, list(Xt.columns), sig, asof_ms=0.0, decision_ms=60 * 60 * 1000.0)  # 60 min later
    chk("ttl: quotes block (10m TTL) goes MISSING after 60m",
        np.isnan(out["quotes_and_spreads.bid"].to_numpy()).all())
    chk("ttl: fundamentals block (7d TTL) survives 60m", np.isfinite(out["fundamentals.short_ratio"].to_numpy()).all())
    chk("ttl: retrospective call (asof=None) never nulls anything",
        TTL.apply_ttl(Xt, list(Xt.columns), sig)["quotes_and_spreads.bid"].notna().all())


def test_governor_stage3():
    from src.brain import governor as GV
    d = tempfile.mkdtemp(prefix="gov_")
    reg = {"organs": {}, "history": []}
    # six consecutive GREEN weeks promote CANDIDATE -> SHADOW_PROVEN (evidence, not drift)
    for wk in range(GV.PROMOTE_WEEKS):
        GV.evaluate_organ(reg, "student", f"W{wk}", "GREEN", metric=0.05 + 0.01 * wk)
    chk("governor: 6 GREEN weeks climb a rung",
        reg["organs"]["student"]["rung"] == "SHADOW_PROVEN", reg["organs"]["student"]["rung"])
    chk("governor: promotion never reaches LIVE without owner flag",
        reg["organs"]["student"]["rung"] != "LIVE")
    # a single RED demotes within one cycle and zeroes the streak
    GV.evaluate_organ(reg, "student", "W6", "RED", metric=-0.1)
    chk("governor: one RED demotes a rung immediately",
        reg["organs"]["student"]["rung"] == "CANDIDATE" and reg["organs"]["student"]["green_streak"] == 0,
        reg["organs"]["student"]["rung"])
    # PERFORMANCE drift: a falling metric series flags concept drift and knocks GREEN to AMBER
    reg2 = {"organs": {}, "history": []}
    for wk, m in enumerate([0.20, 0.14, 0.08, 0.02]):
        o = GV.evaluate_organ(reg2, "council", f"W{wk}", "GREEN", metric=m)
    chk("governor: falling metric raises performance-drift and caps state at AMBER",
        o["drift"]["perf_drift"] and o["state"] == "AMBER",
        f"slope={o['drift']['slope']} state={o['state']}")
    # POPULATION drift: a shifted signature vs the prior week flags data drift
    reg3 = {"organs": {}, "history": []}
    GV.evaluate_organ(reg3, "student", "W0", "GREEN", metric=0.1,
                      signature={"base_up": 0.19, "wide_share": 0.10, "tight_share": 0.40})
    o3 = GV.evaluate_organ(reg3, "student", "W1", "GREEN", metric=0.1,
                           signature={"base_up": 0.19, "wide_share": 0.55, "tight_share": 0.10})
    chk("governor: shifted population signature raises data-drift",
        o3["drift"]["data_drift"] and o3["state"] == "AMBER", str(o3["drift"]))
    # scoreboard renders and surfaces eligibility
    md = GV.scoreboard_md(reg2, "W-test")
    chk("governor: scoreboard renders a table", "| organ | rung | state |" in md)
    shutil.rmtree(d, ignore_errors=True)


def test_treasurer_stage4():
    from src.brain import treasurer as T
    # Kelly: positive edge sizes > 0 and is capped; non-positive edge sizes 0
    f_edge = T.kelly_fraction(0.65, 0.40, -0.50)
    chk("treasurer: positive edge -> positive fractional Kelly, capped at hard cap",
        0 < f_edge <= T.KELLY_HARD_CAP, f"f={f_edge}")
    chk("treasurer: no edge -> zero Kelly", T.kelly_fraction(0.40, 0.40, -0.50) == 0.0)
    chk("treasurer: coin-flip below breakeven -> zero", T.kelly_fraction(0.50, 0.30, -0.50) == 0.0)
    # liquidity cap: never exceeds 10% of resting size, nor the budget
    cap = T.liquidity_cap(price=1.00, top_size=50, budget=800.0)      # budget allows 8; liquidity allows 5
    chk("treasurer: liquidity cap binds below budget", cap == 5, f"cap={cap}")
    cap2 = T.liquidity_cap(price=1.00, top_size=None, budget=800.0)   # no liquidity info -> budget only
    chk("treasurer: budget cap when liquidity unknown", cap2 == 8, f"cap2={cap2}")
    # ratchet only reduces, and zeroes at the halt
    chk("treasurer: ratchet is 1.0 when flat", T.drawdown_ratchet(0.0) == 1.0)
    chk("treasurer: ratchet reduces at 15% dd", T.drawdown_ratchet(0.15) == 0.5)
    chk("treasurer: ratchet zeroes at the 30% halt", T.drawdown_ratchet(0.30) == 0.0)
    # a deep drawdown forces zero contracts regardless of a strong edge
    rec = T.recommend_size(0.80, 0.40, -0.50, price=0.50, top_size=1000, drawdown=0.30)
    chk("treasurer: at the halt, recommended size is 0 even with a strong edge", rec["contracts"] == 0,
        str(rec))
    # P(halt): a losing distribution is far more likely to halt than a winning one, at equal sizing
    rng = np.random.default_rng(1)
    winners = np.where(rng.random(400) < 0.6, 0.4, -0.5)
    losers = np.where(rng.random(400) < 0.3, 0.4, -0.5)
    w = np.ones(400)
    ph_win = T.estimate_p_halt(winners, w, fraction=0.2, n_paths=300)["p_halt"]
    ph_lose = T.estimate_p_halt(losers, w, fraction=0.2, n_paths=300)["p_halt"]
    chk("treasurer: P(halt) higher for a losing distribution", ph_lose > ph_win, f"{ph_lose} vs {ph_win}")
    # macro brake: fires on a VIX spike / absolute level, fail-open on missing data
    chk("treasurer: macro brake fires on absolute VIX", T.macro_brake_state(35.0, 18.0)["state"] == "BRAKE")
    chk("treasurer: macro brake fires on a VIX spike", T.macro_brake_state(24.0, 18.0)["state"] == "BRAKE")
    chk("treasurer: macro brake CLEAR in calm tape", T.macro_brake_state(16.0, 17.0)["state"] == "CLEAR")
    chk("treasurer: macro brake fail-open on missing VIX", T.macro_brake_state(None, None)["state"] == "CLEAR")


def test_convergence_classify_accrete():
    angle_names = [a for a, _ in CV.ANGLES]
    m = {"surv": {a: "confirmed" for a in angle_names[:8]} | {a: "absent" for a in angle_names[8:]},
         "flick": {a: "confirmed" for a in angle_names[:5]} | {a: "absent" for a in angle_names[5:]},
         "mirage": {a: "confirmed" for a in angle_names[:2]} | {a: "absent" for a in angle_names[2:]}}
    s, f, g = CV.classify(m)
    chk("convergence: 8/10 -> survivor, 5 -> flicker, 2 -> mirage",
        [x[0] for x in s] == ["surv"] and [x[0] for x in f] == ["flick"] and [x[0] for x in g] == ["mirage"])
    d = tempfile.mkdtemp(prefix="conv_")
    sp = os.path.join(d, "state.json")
    CV.accrete(sp, "snapA", m, s)
    st1 = CV.accrete(sp, "snapB", m, s)
    chk("convergence: survivor persists across runs in accretion state",
        st1.get("surv", "").startswith("SURVIVOR x2"), st1.get("surv"))
    st2 = CV.accrete(sp, "snapC", m, [])
    chk("convergence: a survivor that stops surviving LAPSES", st2.get("surv", "").startswith("LAPSED"),
        st2.get("surv"))
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    test_gate1_overlap_weights()
    test_weight_cache_equality()
    test_purgedkfold_leakage()
    test_ev_solver()
    test_calibration_selection()
    test_isolation()
    test_foundry_pools_across_params_hash()
    test_end_to_end_synthetic()
    test_discovery_oos_only()
    test_discovery_walkforward_purge()
    test_student_stage2()
    test_council_stage2()
    test_governor_stage3()
    test_treasurer_stage4()
    test_convergence_classify_accrete()
    total = 15 * 3
    print(f"\nTOTAL: brain suite - {len(fails)} failure(s)")
    if fails:
        raise SystemExit("FAILS: " + ", ".join(fails))
    print("BRAIN SUITE PASS: isolation intact, leakage caught, weights + EV + calibration verified")

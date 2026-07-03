from harvest_labeler import label_path

M = 60000
UP = 0.30
DOWN = -0.50
FAR = 999 * M
E = 1.00
S = 0

_fails = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    if not cond:
        _fails.append(name)


def approx(a, b, tol=1e-6):
    return a is not None and abs(a - b) <= tol


print("=== BARRIER LABELER: 8 synthetic bid-path tests ===")

r = label_path(E, UP, DOWN, FAR, S, [{"poll_ts": 1 * M, "bid": 1.35}])
check("1 clean up-touch mid-week -> +1, touch@1m",
      r["outcome"] == "up" and r["label"] == 1 and r["touch_ts_utc"] == 1 * M and approx(r["realized_return"], 0.35),
      f"outcome={r['outcome']} label={r['label']} rr={r['realized_return']} ttt={r['time_to_touch_min']}")

r = label_path(E, UP, DOWN, FAR, S, [{"poll_ts": 1 * M, "bid": 0.45}])
check("2 clean down-touch -> -1",
      r["outcome"] == "down" and r["label"] == -1 and approx(r["realized_return"], -0.55),
      f"outcome={r['outcome']} label={r['label']} rr={r['realized_return']}")

r = label_path(E, UP, DOWN, 3 * M, S, [{"poll_ts": 1 * M, "bid": 1.25}, {"poll_ts": 2 * M, "bid": 1.10}, {"poll_ts": 3 * M, "bid": 0.90}])
check("3 spike +25% then bleed to -10% at vertical -> -1, mfe~+25%",
      r["outcome"] == "vertical" and r["label"] == -1 and approx(r["realized_return"], -0.10) and approx(r["mfe"], 0.25),
      f"outcome={r['outcome']} label={r['label']} rr={r['realized_return']} mfe={r['mfe']}")

r = label_path(E, UP, DOWN, 2 * M, S, [{"poll_ts": 1 * M, "bid": 1.05}, {"poll_ts": 2 * M, "bid": 1.12}])
check("4 vertical at +12% -> +1, outcome vertical",
      r["outcome"] == "vertical" and r["label"] == 1 and approx(r["realized_return"], 0.12),
      f"outcome={r['outcome']} label={r['label']} rr={r['realized_return']}")

r = label_path(E, UP, DOWN, FAR, S, [{"poll_ts": 1 * M, "bid": 1.40, "low": 0.40}])
check("5 both barriers in one interval -> -1, ambiguous",
      r["outcome"] == "down" and r["label"] == -1 and r["ambiguous_touch"] is True,
      f"outcome={r['outcome']} label={r['label']} ambiguous={r['ambiguous_touch']} rr={r['realized_return']}")

r = label_path(E, UP, DOWN, FAR, S, [{"poll_ts": 1 * M, "bid": 0.0}])
check("6 bid=0 fresh quote -> down touch",
      r["outcome"] == "down" and r["label"] == -1 and approx(r["realized_return"], -1.0),
      f"outcome={r['outcome']} label={r['label']} rr={r['realized_return']}")

r = label_path(E, UP, DOWN, FAR, S, [{"poll_ts": 1 * M, "bid": None, "stale": True}, {"poll_ts": 2 * M, "bid": None, "stale": True}, {"poll_ts": 3 * M, "bid": None, "stale": True}])
check("7 stale-quote run -> no false trigger, n_stale=3",
      r["outcome"] == "open" and r["label"] is None and r["n_stale"] == 3 and r["n_polls"] == 3,
      f"outcome={r['outcome']} label={r['label']} n_stale={r['n_stale']}")

r = label_path(E, UP, DOWN, 1 * M, S, [{"poll_ts": 1 * M, "bid": 0.0}])
check("8 expires worthless at vertical -> realized -1.0, outcome vertical",
      r["outcome"] == "vertical" and r["label"] == -1 and approx(r["realized_return"], -1.0),
      f"outcome={r['outcome']} label={r['label']} rr={r['realized_return']}")

print(f"\nTOTAL: {8 - len(_fails)}/8 passed")
if _fails:
    raise SystemExit("FAILURES: " + ", ".join(_fails))
print("ALL BARRIER TESTS PASS")

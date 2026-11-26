import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in ("scripts", "research"):
    sys.path.insert(0, os.path.join(ROOT, _p))


def near(a, b, tol=1e-9):
    return a is not None and abs(a - b) <= tol


def run(ns):
    names = sorted(k for k, v in ns.items() if callable(v) and k.startswith(("test_", "case_")))
    bad = 0
    for k in names:
        try:
            r = ns[k]()
            if k.startswith("case_"):
                got, want = r
                assert got == want, f"got {got} want {want}"
            print("ok   " + k)
        except Exception as e:
            bad += 1
            line = traceback.extract_tb(e.__traceback__)[-1].lineno
            print(f"FAIL {k} (line {line}): {type(e).__name__}: {e}")
    print(f"{os.path.basename(sys.argv[0])}: {len(names) - bad}/{len(names)} passed")
    sys.exit(1 if bad else 0)

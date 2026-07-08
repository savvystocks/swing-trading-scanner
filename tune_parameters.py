"""V10 sandbox - iterative parametric tuning CLI (STANDALONE).

Turn the knobs in v10_tunable_parameters.json from the command line, and read the latest
tuning advisory the autopsy wrote.

  python tune_parameters.py --show
  python tune_parameters.py --advisory
  python tune_parameters.py --gate take_profit_pct --value 40
  python tune_parameters.py --gate regime_compass_bypass --value false
"""

import os
import sys
import argparse

from v10_params import load, save, PARAMS_PATH

ADVISORY_MD = "v10_tuning_advisory.md"


def _coerce(s):
    low = str(s).strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        f = float(s)
        return int(f) if f.is_integer() and "." not in str(s) else f
    except ValueError:
        return s


def latest_advisory():
    if not os.path.exists(ADVISORY_MD):
        return None
    text = open(ADVISORY_MD, encoding="utf-8").read().strip()
    blocks = [b for b in text.split("\n---\n") if b.strip()]
    return blocks[-1] if blocks else text


def main(argv=None):
    ap = argparse.ArgumentParser(description="V10 tunable-parameter CLI")
    ap.add_argument("--gate", help="parameter name to set")
    ap.add_argument("--value", help="new value (true/false, number, or string)")
    ap.add_argument("--show", action="store_true", help="print current parameters")
    ap.add_argument("--advisory", action="store_true", help="print the latest tuning advisory")
    args = ap.parse_args(argv)

    params = load()

    if args.advisory:
        adv = latest_advisory()
        print(adv or f"(no {ADVISORY_MD} yet - run an autopsy first)")
        return 0

    if args.show or not (args.gate and args.value is not None):
        import json
        print(f"# {PARAMS_PATH}")
        print(json.dumps(params, indent=2))
        if not (args.gate and args.value is not None) and not args.show:
            print("\nusage: --gate <name> --value <v> | --show | --advisory", file=sys.stderr)
        return 0

    val = _coerce(args.value)
    old = params.get(args.gate, "(new)")
    params[args.gate] = val
    save(params)
    print(f"set {args.gate}: {old} -> {val}  ({PARAMS_PATH})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import pathlib

COHORTS_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "catalyst" / "cohorts.json"


def load_cohorts():
    with open(COHORTS_PATH) as f:
        return json.load(f)


def cohort_signals():
    cohorts = load_cohorts()
    out = {}
    for cohort_key, cohort in cohorts.items():
        for ticker in cohort.get("tickers", []):
            t = ticker.split(".")[0] if ticker.endswith((".US", ".LSE")) else ticker
            out.setdefault(t, []).append({
                "cohort": cohort_key,
                "description": cohort.get("description", ""),
            })
    return out


def cohort_for_ticker(ticker, cache=None):
    if cache is None:
        cache = cohort_signals()
    return cache.get(ticker, [])

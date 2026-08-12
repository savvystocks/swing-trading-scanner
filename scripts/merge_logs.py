"""RECORD-LEVEL CONFLICT RESOLVER (built 2026-08-12 after the NVDA orphan).

Root cause it fixes: proactive_sandbox_logs.json and data/harvest_state.json are whole-file
JSON, not union-mergeable. When two writers race (engine cycle vs VPS heartbeat/failover),
the loser's `git pull --rebase` hits CONFLICT, the rebase dies, the retry loop exhausted
silently, and that run's trade records vanished - the 2026-08-12 14:13 run lost an NVDA
entry exactly this way (adopted as an orphan 15 min later, evidence attribution gone).

This script runs INSIDE the conflicted rebase: for each known file it reads both stages
(:2 and :3 - rebase inverts ours/theirs, but every merge below is symmetric union with a
deterministic winner, so orientation cannot matter), merges at RECORD level, writes the
resolution, and stages it. Unknown conflicted files -> exit 1 (the workflow falls back).

Merge rules:
  proactive_sandbox_logs.json - union by trade_set_id (fallback: type+ts marker key).
    Shared id -> the more ADVANCED version wins: terminal status (CLOSED/FLUSHED/...) beats
    PARKED beats OPEN; then more leg_exits; then longer serialization (exits only add data).
  data/harvest_state.json - later date wins outright; same date -> contracts union,
    tickers dict union, counters element-wise max.
  sandbox_ticker_cooloff.json / sandbox_watchlist.json - dict union, later/richer value wins.
"""
import json
import subprocess
import sys

TERMINAL = {"CLOSED", "FLUSHED", "CANCELLED", "SKIPPED", "SETTLED", "EXPIRED"}


def _rank(rec):
    st = (rec.get("status") or "").upper()
    stage = 2 if st in TERMINAL else (1 if st == "PARKED" else 0)
    return (stage, len(rec.get("leg_exits") or {}), len(json.dumps(rec, sort_keys=True)))


def _key(rec, i):
    if rec.get("trade_set_id"):
        return ("id", rec["trade_set_id"])
    if rec.get("type"):
        return ("marker", rec.get("type"), rec.get("ts_utc"))
    return ("pos", json.dumps(rec, sort_keys=True)[:120], i)


def merge_log(a, b):
    """Union of two record lists; shared trade_set_id -> most advanced version wins."""
    out, idx = [], {}
    for src in (a, b):
        for i, rec in enumerate(src):
            k = _key(rec, i)
            if k in idx:
                if _rank(rec) > _rank(out[idx[k]]):
                    out[idx[k]] = rec
            else:
                idx[k] = len(out)
                out.append(rec)
    return out


def merge_state(a, b):
    if (a.get("date") or "") != (b.get("date") or ""):
        return a if (a.get("date") or "") > (b.get("date") or "") else b
    m = dict(b)
    m["contracts"] = list(dict.fromkeys((b.get("contracts") or []) + (a.get("contracts") or [])))
    tk = dict(b.get("tickers") or {})
    for t, v in (a.get("tickers") or {}).items():
        tk.setdefault(t, v)
    m["tickers"] = tk
    for c in ("payload_count", "topn_count", "random_count"):
        m[c] = max(a.get(c) or 0, b.get(c) or 0)
    return m


def merge_flat_dict(a, b):
    m = dict(b)
    for k, v in a.items():
        if k not in m or json.dumps(v, sort_keys=True) > json.dumps(m[k], sort_keys=True):
            m[k] = v
    return m


MERGERS = {
    "proactive_sandbox_logs.json": merge_log,
    "data/harvest_state.json": merge_state,
    "sandbox_ticker_cooloff.json": merge_flat_dict,
    "sandbox_watchlist.json": merge_flat_dict,
}


def _stage(path, n):
    r = subprocess.run(["git", "show", f":{n}:{path}"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def resolve():
    r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                       capture_output=True, text=True)
    files = [f for f in r.stdout.splitlines() if f.strip()]
    if not files:
        print("merge_logs: no conflicted files")
        return 0
    for f in files:
        fn = MERGERS.get(f)
        if fn is None:
            print(f"merge_logs: UNKNOWN conflicted file {f} - cannot resolve")
            return 1
        ours, theirs = _stage(f, 2), _stage(f, 3)
        if ours is None or theirs is None:
            print(f"merge_logs: missing stage for {f} - cannot resolve")
            return 1
        merged = fn(ours, theirs)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=1)
        subprocess.run(["git", "add", f], check=True)
        na = len(ours) if isinstance(ours, list) else len(ours or {})
        nb = len(theirs) if isinstance(theirs, list) else len(theirs or {})
        nm = len(merged) if isinstance(merged, list) else len(merged or {})
        print(f"merge_logs: resolved {f} ({na} ours + {nb} theirs -> {nm} merged)")
    return 0


def selftest():
    a = [{"trade_set_id": "x", "status": "OPEN", "leg_exits": {}},
         {"trade_set_id": "lost_nvda", "status": "OPEN", "ticker": "NVDA"}]
    b = [{"trade_set_id": "x", "status": "CLOSED", "leg_exits": {"l": {}}},
         {"trade_set_id": "y", "status": "OPEN"}]
    m = merge_log(a, b)
    ids = {r["trade_set_id"]: r for r in m}
    assert set(ids) == {"x", "y", "lost_nvda"}, "union failed"
    assert ids["x"]["status"] == "CLOSED", "advanced-version rule failed"
    assert merge_log(b, a) and {r["trade_set_id"] for r in merge_log(b, a)} == set(ids), "symmetry failed"
    sa = {"date": "2026-08-12", "contracts": ["A", "B"], "tickers": {"T1": {"x": 1}},
          "payload_count": 5, "topn_count": 1, "random_count": 0}
    sb = {"date": "2026-08-12", "contracts": ["B", "C"], "tickers": {"T2": {"y": 2}},
          "payload_count": 3, "topn_count": 4, "random_count": 1}
    ms = merge_state(sa, sb)
    assert set(ms["contracts"]) == {"A", "B", "C"} and set(ms["tickers"]) == {"T1", "T2"}
    assert ms["payload_count"] == 5 and ms["topn_count"] == 4
    assert merge_state({"date": "2026-08-13"}, sb)["date"] == "2026-08-13", "later-date rule failed"
    print("merge_logs selftest: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else resolve())

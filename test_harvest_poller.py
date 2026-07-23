import os, json, tempfile, sys
sys.path.insert(0, r"C:\Users\savva\OneDrive\Documents\Swing Trading")
import harvest_db as db

tmp = tempfile.mkdtemp()
db.DATA_DIR = tmp
db.DB_PATH = os.path.join(tmp, "harvest.db")
db.BACKUP_DIR = os.path.join(tmp, "bk")
db.INBOX_DIR = os.path.join(tmp, "inbox")
os.makedirs(db.INBOX_DIR, exist_ok=True)

import poller
poller._market_open_now = lambda: True

_clock = {"t": 1000}
poller._now_ms = lambda: _clock["t"]

_quotes = {"t": {}, "force_status": None}
def _mock_fetch(symbols, creds):
    if _quotes["force_status"]:
        return {}, {s: _quotes["force_status"] for s in symbols}
    qs = dict(_quotes["t"])
    return qs, {s: ("OK" if s in qs else "EMPTY") for s in symbols}
poller._fetch_alpaca = _mock_fetch
poller._fetch_uw = lambda symbols: {}
poller._paper_creds = lambda: ("k", "s")

base = {"run_id": "r", "code_version": "x", "feature_set_version": "v", "expiry": "2026-12-18",
        "right": "call", "side": "long", "features": None, "rule_score": 100.0, "executed": 0,
        "skip_reason": "quota_cap", "vertical_barrier_ts": 9_999_999_999_999,
        "barrier_up_pct": 0.30, "barrier_down_pct": -0.50, "poll_tier": "standard", "sample_tier": "none",
        "bid": 1.0, "ask": 1.0, "bid_size": None, "ask_size": None, "mid": 1.0, "spread_pct": 0.0,
        "last": 1.0, "underlying_last": 20.0, "strike": 10.0, "signal_ts_utc": 500}
cands = [
    {**base, "candidate_id": "C_up", "ticker": "AAA", "occ_symbol": "AAA261218C00010000", "entry_ref": 1.0},
    {**base, "candidate_id": "C_down", "ticker": "BBB", "occ_symbol": "BBB261218C00010000", "entry_ref": 1.0},
    {**base, "candidate_id": "C_stale", "ticker": "CCC", "occ_symbol": "CCC261218C00010000", "entry_ref": 1.0},
]
with open(os.path.join(db.INBOX_DIR, "candidates_test.jsonl"), "w") as fh:
    for c in cands:
        fh.write(json.dumps(c) + "\n")

fails = []
def chk(n, c, d=""):
    print(f"  [{'PASS' if c else 'FAIL'}] {n}  {d}")
    if not c: fails.append(n)

print("--- round 1 (all mid-range / stale) ---")
_clock["t"] = 1000
_quotes["t"] = {"AAA261218C00010000": {"bid": 1.0, "ask": 1.05, "quote_ts": 1000, "stale": False},
                "BBB261218C00010000": {"bid": 1.0, "ask": 1.05, "quote_ts": 1000, "stale": False}}
poller.run_once()

print("--- round 2 (up / down / stale) ---")
_clock["t"] = 2000
_quotes["t"] = {"AAA261218C00010000": {"bid": 1.40, "ask": 1.45, "quote_ts": 2000, "stale": False},
                "BBB261218C00010000": {"bid": 0.40, "ask": 0.45, "quote_ts": 2000, "stale": False}}
poller.run_once()

con = db.connect()
paths = {r[0]: r[1] for r in con.execute("SELECT candidate_id, COUNT(*) FROM bid_path GROUP BY candidate_id").fetchall()}
labels = {r["candidate_id"]: dict(r) for r in con.execute("SELECT * FROM labels").fetchall()}

chk("C_up 2 path rows", paths.get("C_up") == 2, f"got {paths.get('C_up')}")
chk("C_stale 2 path rows (both stale)", paths.get("C_stale") == 2, f"got {paths.get('C_stale')}")
chk("C_up resolved outcome=up label=+1", labels.get("C_up", {}).get("outcome") == "up" and labels["C_up"]["label"] == 1)
chk("C_down resolved outcome=down label=-1", labels.get("C_down", {}).get("outcome") == "down" and labels["C_down"]["label"] == -1)
chk("C_stale NOT labeled (still open)", "C_stale" not in labels)
chk("C_stale n_stale tracked in path", con.execute("SELECT SUM(stale) FROM bid_path WHERE candidate_id='C_stale'").fetchone()[0] == 2)
chk("C_up poll_cadence_min=15 recorded", labels["C_up"]["poll_cadence_min"] == 15.0)

print("--- round 2 re-run (idempotency: same clock) ---")
poller.run_once()
con2 = db.connect()
tot = con2.execute("SELECT COUNT(*) FROM bid_path").fetchone()[0]
chk("no duplicate path rows on re-run (idempotent)", tot == 6, f"total bid_path rows={tot} (C_up 2 + C_down 2 + C_stale 2)")

print("--- round 3 (school 1b: simulated 429 - no answer is NOT a market fact) ---")
_clock["t"] = 3000
_quotes["force_status"] = "RATE_LIMITED"
poller.run_once()
_quotes["force_status"] = None
con3 = db.connect()
r3 = con3.execute("SELECT bid, stale, fetch_status FROM bid_path WHERE candidate_id='C_stale' AND poll_ts_utc=3000").fetchone()
chk("429 poll writes MISSING_RATE_LIMITED, bid NULL", r3 is not None and r3["bid"] is None
    and r3["fetch_status"] == "MISSING_RATE_LIMITED", f"row={dict(r3) if r3 else None}")
chk("C_stale STILL unlabeled after 429 round (missing row excluded from barriers)",
    con3.execute("SELECT COUNT(*) FROM labels WHERE candidate_id='C_stale'").fetchone()[0] == 0)
tele = {r["status"]: r["n"] for r in con3.execute("SELECT status, SUM(n) n FROM api_telemetry GROUP BY status")}
chk("telemetry counted the RATE_LIMITED call", tele.get("RATE_LIMITED", 0) >= 1, f"telemetry={tele}")

print("--- round 4 (C_stale finally gets a real quote through the up barrier) ---")
_clock["t"] = 4000
_quotes["t"] = {"CCC261218C00010000": {"bid": 1.40, "ask": 1.45, "quote_ts": 4000, "stale": False}}
poller.run_once()
con4 = db.connect()
lab = con4.execute("SELECT * FROM labels WHERE candidate_id='C_stale'").fetchone()
chk("C_stale labeled up on the real quote", lab is not None and lab["outcome"] == "up")
chk("n_missing=1 counted APART from n_stale=2 (no-answer never becomes stale-market)",
    lab is not None and lab["n_missing"] == 1 and lab["n_stale"] == 2,
    f"n_missing={lab['n_missing'] if lab else None} n_stale={lab['n_stale'] if lab else None}")

print(f"\nTOTAL: {13 - len(fails)}/13 passed")
if fails:
    raise SystemExit("FAILS: " + ", ".join(fails))
print("POLLER OK")

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

_quotes = {"t": {}}
poller._fetch_alpaca = lambda symbols, creds: dict(_quotes["t"])
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

print(f"\nTOTAL: {8 - len(fails)}/8 passed")
if fails:
    raise SystemExit("FAILS: " + ", ".join(fails))
print("POLLER OK")

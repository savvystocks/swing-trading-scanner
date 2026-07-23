import os
import json
import glob
import shutil
import sqlite3
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "harvest.db")
BACKUP_DIR = os.path.join(DATA_DIR, "harvest_backups")
INBOX_DIR = os.path.join(DATA_DIR, "harvest_inbox")


def inbox_path():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return os.path.join(INBOX_DIR, "candidates_%s.jsonl" % stamp)

CANDIDATE_COLS = [
    "candidate_id", "run_id", "code_version", "params_hash", "feature_set_version", "signal_ts_utc",
    "ticker", "occ_symbol", "expiry", "strike", "right", "side",
    "bid", "ask", "bid_size", "ask_size", "mid", "spread_pct", "last", "underlying_last",
    "entry_ref", "features", "rule_score", "executed", "skip_reason",
    "vertical_barrier_ts", "barrier_up_pct", "barrier_down_pct", "poll_tier", "sample_tier",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT, code_version TEXT, params_hash TEXT, feature_set_version TEXT, signal_ts_utc INTEGER,
    ticker TEXT, occ_symbol TEXT, expiry TEXT, strike REAL, "right" TEXT, side TEXT,
    bid REAL, ask REAL, bid_size REAL, ask_size REAL, mid REAL, spread_pct REAL, last REAL, underlying_last REAL,
    entry_ref REAL, features TEXT, rule_score REAL, executed INTEGER, skip_reason TEXT,
    vertical_barrier_ts INTEGER, barrier_up_pct REAL, barrier_down_pct REAL, poll_tier TEXT, sample_tier TEXT
);
CREATE INDEX IF NOT EXISTS idx_candidates_occ ON candidates(occ_symbol);
CREATE INDEX IF NOT EXISTS idx_candidates_signal ON candidates(signal_ts_utc);

CREATE TABLE IF NOT EXISTS bid_path (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT, poll_ts_utc INTEGER, bid REAL, ask REAL, quote_ts INTEGER, stale INTEGER,
    UNIQUE(candidate_id, poll_ts_utc)
);
CREATE INDEX IF NOT EXISTS idx_bidpath_cand ON bid_path(candidate_id);

CREATE TABLE IF NOT EXISTS labels (
    candidate_id TEXT PRIMARY KEY NOT NULL,
    outcome TEXT, label INTEGER, realized_return REAL, touch_ts_utc INTEGER, time_to_touch_min REAL,
    mfe REAL, mae REAL, n_polls INTEGER, n_stale INTEGER, ambiguous_touch INTEGER,
    poll_cadence_min REAL, censored_reason TEXT
);

CREATE TABLE IF NOT EXISTS fills (
    event_id TEXT PRIMARY KEY NOT NULL,
    kind TEXT, ts_utc INTEGER, ticker TEXT, occ_symbol TEXT, order_id TEXT,
    ordered_qty REAL, filled_qty REAL, filled_avg_price REAL, terminal_state TEXT,
    payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_fills_occ ON fills(occ_symbol);

CREATE TABLE IF NOT EXISTS api_telemetry (
    day TEXT NOT NULL, provider TEXT NOT NULL, status TEXT NOT NULL, n INTEGER DEFAULT 0,
    PRIMARY KEY (day, provider, status)
);

CREATE TABLE IF NOT EXISTS integrity_quarantine (
    candidate_id TEXT, reason TEXT, detected_ts_utc INTEGER,
    PRIMARY KEY (candidate_id, reason)
);
"""


def connect(path=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(path or DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA synchronous=NORMAL")
    con.row_factory = sqlite3.Row
    return con


def init_db(path=None):
    con = connect(path)
    con.executescript(_SCHEMA)
    _migrate(con)
    con.commit()
    return con


def _migrate(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(candidates)").fetchall()}
    if "params_hash" not in cols:                     # add the frozen-baseline stamp column to a pre-existing DB
        con.execute('ALTER TABLE candidates ADD COLUMN params_hash TEXT')
    if "untradeable" not in cols:                     # school 1d: zero-bid / crossed-market at signal time
        con.execute('ALTER TABLE candidates ADD COLUMN untradeable INTEGER')
    bp_cols = {r[1] for r in con.execute("PRAGMA table_info(bid_path)").fetchall()}
    if "fetch_status" not in bp_cols:                 # school 1b: OK/EMPTY/MISSING_RATE_LIMITED/MISSING_ERROR
        con.execute('ALTER TABLE bid_path ADD COLUMN fetch_status TEXT')
    lb_cols = {r[1] for r in con.execute("PRAGMA table_info(labels)").fetchall()}
    if "n_missing" not in lb_cols:                    # school 1b: no-answer polls, counted apart from stale-market
        con.execute('ALTER TABLE labels ADD COLUMN n_missing INTEGER')


def insert_candidate(con, row):
    vals = [row.get(c) for c in CANDIDATE_COLS]
    if isinstance(row.get("features"), (dict, list)):
        vals[CANDIDATE_COLS.index("features")] = json.dumps(row["features"])
    quoted = ",".join('"%s"' % c for c in CANDIDATE_COLS)
    marks = ",".join("?" for _ in CANDIDATE_COLS)
    cur = con.execute("INSERT OR IGNORE INTO candidates (%s) VALUES (%s)" % (quoted, marks), vals)
    con.commit()
    return cur.rowcount


def ingest_jsonl(con, path):
    if not path or not os.path.exists(path):
        return 0, 0
    new = 0
    total = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                new += insert_candidate(con, json.loads(line))
            except Exception:
                pass
    return new, total - new


def ingest_inbox(con):
    new = 0
    skipped = 0
    for f in sorted(glob.glob(os.path.join(INBOX_DIR, "*.jsonl"))):
        if os.path.basename(f).startswith("fills_"):
            continue                                   # fill-ledger events have their own ingest
        n, s = ingest_jsonl(con, f)
        new += n
        skipped += s
    return new, skipped


def ingest_fills(con):
    """School 1c: ingest fill-ledger events, idempotent on event_id. Core metrics to columns, the
    full event kept verbatim in payload."""
    new = 0
    for f in sorted(glob.glob(os.path.join(INBOX_DIR, "fills_*.jsonl"))):
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    cur = con.execute(
                        "INSERT OR IGNORE INTO fills (event_id, kind, ts_utc, ticker, occ_symbol, "
                        "order_id, ordered_qty, filled_qty, filled_avg_price, terminal_state, payload) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (e.get("event_id"), e.get("kind"), e.get("ts_utc"), e.get("ticker"),
                         e.get("occ") or e.get("occ_symbol"), e.get("order_id"),
                         e.get("ordered_qty"), e.get("filled_qty"), e.get("filled_avg_price"),
                         e.get("terminal_state"), json.dumps(e)))
                    new += cur.rowcount
                except Exception:
                    pass
    con.commit()
    return new


def append_bid_path(con, candidate_id, poll_ts, bid, ask, quote_ts, stale, fetch_status="OK"):
    cur = con.execute(
        "INSERT OR IGNORE INTO bid_path (candidate_id, poll_ts_utc, bid, ask, quote_ts, stale, fetch_status) "
        "VALUES (?,?,?,?,?,?,?)",
        (candidate_id, poll_ts, bid, ask, quote_ts, 1 if stale else 0, fetch_status),
    )
    con.commit()
    return cur.rowcount


def bump_telemetry(con, provider, status, n=1):
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    con.execute(
        "INSERT INTO api_telemetry (day, provider, status, n) VALUES (?,?,?,?) "
        "ON CONFLICT(day, provider, status) DO UPDATE SET n = n + excluded.n",
        (day, provider, status, n),
    )
    con.commit()


def upsert_label(con, candidate_id, res, poll_cadence_min=None, censored_reason=None):
    con.execute(
        "INSERT OR REPLACE INTO labels (candidate_id, outcome, label, realized_return, touch_ts_utc, "
        "time_to_touch_min, mfe, mae, n_polls, n_stale, ambiguous_touch, poll_cadence_min, censored_reason, "
        "n_missing) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (candidate_id, res.get("outcome"), res.get("label"), res.get("realized_return"),
         res.get("touch_ts_utc"), res.get("time_to_touch_min"), res.get("mfe"), res.get("mae"),
         res.get("n_polls"), res.get("n_stale"), 1 if res.get("ambiguous_touch") else 0,
         poll_cadence_min, censored_reason, res.get("n_missing")),
    )
    con.commit()


def open_candidates(con):
    rows = con.execute(
        "SELECT c.* FROM candidates c LEFT JOIN labels l ON c.candidate_id = l.candidate_id "
        "WHERE l.candidate_id IS NULL AND c.poll_tier != 'none' AND c.occ_symbol IS NOT NULL"
    ).fetchall()
    return [dict(r) for r in rows]


def get_path(con, candidate_id):
    rows = con.execute(
        "SELECT poll_ts_utc, bid, ask, quote_ts, stale, fetch_status FROM bid_path "
        "WHERE candidate_id=? ORDER BY poll_ts_utc",
        (candidate_id,),
    ).fetchall()
    return [{"poll_ts": r["poll_ts_utc"], "bid": r["bid"], "ask": r["ask"],
             "quote_ts": r["quote_ts"], "stale": bool(r["stale"]),
             "fetch_status": r["fetch_status"] or "OK"} for r in rows]


def backup(path=None, keep=14):
    src = path or DB_PATH
    if not os.path.exists(src):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    dst = os.path.join(BACKUP_DIR, "harvest_%s.db" % stamp)
    con = connect(src)
    bck = sqlite3.connect(dst)
    con.backup(bck)
    bck.close()
    con.close()
    existing = sorted(glob.glob(os.path.join(BACKUP_DIR, "harvest_*.db")))
    for old in existing[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dst

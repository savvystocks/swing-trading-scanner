"""Stage 0 loader. Fetches the latest nightly gzipped snapshot from the private harvest-snapshots repo
(read-only), decompresses it to a working copy, and verifies it. The brain NEVER opens the live
harvest.db - only these snapshots.

Pure stdlib + sqlite3. Imports no execution module.
"""
import os
import gzip
import glob
import shutil
import sqlite3
import tempfile


def latest_snapshot_gz(source):
    """`source` is either a .db.gz file or a directory (a harvest-snapshots checkout). Returns the
    newest snapshot .gz path."""
    if os.path.isfile(source) and source.endswith(".gz"):
        return source
    if os.path.isdir(source):
        gzs = sorted(glob.glob(os.path.join(source, "harvest_*.db.gz")))
        if not gzs:
            raise FileNotFoundError(f"no harvest_*.db.gz under {source}")
        return gzs[-1]                                        # names are timestamp-sortable
    raise FileNotFoundError(f"snapshot source not found: {source}")


def load_snapshot(source, workdir=None):
    """Decompress the latest snapshot to a working copy and verify it. Returns a dict with db_path,
    snapshot_id, integrity, and row counts. Read-only w.r.t. the source."""
    gz = latest_snapshot_gz(source)
    snapshot_id = os.path.basename(gz)[:-len(".db.gz")] if gz.endswith(".db.gz") else os.path.basename(gz)
    workdir = workdir or tempfile.mkdtemp(prefix="brain_snap_")
    os.makedirs(workdir, exist_ok=True)
    db_path = os.path.join(workdir, "snapshot.db")
    with gzip.open(gz, "rb") as fin, open(db_path, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    con = sqlite3.connect(db_path)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {}
        for t in ("candidates", "bid_path", "labels"):
            try:
                counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                counts[t] = None
    finally:
        con.close()
    if integrity != "ok":
        raise ValueError(f"snapshot integrity_check failed: {integrity}")
    return {"db_path": db_path, "snapshot_id": snapshot_id, "gz_path": gz,
            "integrity": integrity, "row_counts": counts, "workdir": workdir}

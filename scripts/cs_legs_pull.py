"""CREDIT-SPREAD LEGS, ASKED FOR BY NAME (owner order 2026-09-19: "get the coverage as high as possible").

The chain feed lists only the 500 busiest contracts a day, which dropped 46% of this strategy's weeks - and the bad
ones, because a far strike trades when the market is falling. `/api/option-contract/{occ}/historic` returns ONE
contract's whole daily life WITH closing bid and ask, traded or not, so coverage becomes the vendor's, not our cap's.
Every finished week since the token floor, put strikes 1.0-6.0% below spot in 0.5% steps, on XSP (what the book
trades) and on SPY (what every earlier backtest priced). Weekly cron; resumable; a contract is re-asked until its
expiry-day row has arrived (or ten days have passed), then it is final. Own small database (data/cs_legs.db), never
the 14 GB archive. The vendor's history floor rolls forward a day at a time, so the oldest weeks can never be pulled
again: each run leaves a compressed copy in ~/harvest-snapshots, which the nightly backup job pushes off the box.
Off the trade path entirely."""
import gzip
import json
import os
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request
import warnings
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
DB = "data/cs_legs.db"
OFFSETS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
FIRST_WEEK = "2023-10-23"
GIVE_UP_DAYS = 10
SNAP = os.path.expanduser("~/harvest-snapshots")
H = {"Authorization": "Bearer " + os.environ.get("UNUSUAL_WHALES_TOKEN", ""), "Accept": "application/json"}


def week_contracts(ent, exp, spots):
    """One finished week -> the OCC names of every leg the rule could have traded, on both instruments."""
    out = {}
    for root, spot in spots.items():
        for x in OFFSETS:
            k = round(float(spot) * (1 - x / 100))
            out[f"{root}{exp.strftime('%y%m%d')}P{int(k * 1000):08d}"] = (root, ent.strftime("%Y-%m-%d"), exp.strftime("%Y-%m-%d"), k)
    return out


def wanted(today=None):
    import pandas as pd
    import yfinance as yf
    warnings.filterwarnings("ignore")
    today = today or date.today()
    px = yf.download(["^XSP", "SPY"], start="2023-10-01", auto_adjust=False, progress=False)["Close"]
    xsp, spy = px["^XSP"].dropna(), px["SPY"].dropna()
    weeks = {}
    for d in spy.index:
        if d >= pd.Timestamp(FIRST_WEEK) and d in xsp.index:
            weeks.setdefault(d.isocalendar()[:2], []).append(d)
    out = {}
    for _, ds in sorted(weeks.items()):
        ent, exp = ds[0], ds[-1]
        friday = (ent + pd.Timedelta(days=4 - ent.weekday())).date()
        if len(ds) < 3 or friday >= today:              # short weeks are not traded; an unfinished week has no expiry yet
            continue
        out.update(week_contracts(ent, exp, {"XSP": xsp.loc[ent], "SPY": spy.loc[ent]}))
    return out


def _f(x):
    try:
        return float(x) if x not in (None, "") else None
    except Exception:
        return None


def historic(occ):
    for i in range(4):
        try:
            req = urllib.request.Request(f"https://api.unusualwhales.com/api/option-contract/{occ}/historic", headers=H)
            with urllib.request.urlopen(req, timeout=40) as r:
                j = json.loads(r.read())
                return j.get("chains") or j.get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(30 * (i + 1))
                continue
            if e.code in (404, 422):
                return []
            time.sleep(5)
        except Exception:
            time.sleep(5)
    return None


def bump(n):
    if n <= 0:
        return
    for _ in range(5):                                  # the shared daily budget lives in the big archive; never fight its writers
        try:
            b = sqlite3.connect("data/uw_history.db", timeout=60)
            b.execute("insert into budget(utc_day, used) values(?, ?) on conflict(utc_day) do update set used=used+?",
                      (date.today().isoformat(), n, n))
            b.commit()
            b.close()
            return
        except sqlite3.OperationalError:
            time.sleep(20)


def mark_final(db, today=None):
    """A contract's rows keep arriving until its expiry day has been published; only then is one answer the whole answer."""
    cutoff = ((today or date.today()) - timedelta(days=GIVE_UP_DAYS)).isoformat()
    db.execute("update asked set final = 1 where final = 0 and (expiry < ? or exists "
               "(select 1 from legs l where l.occ = asked.occ and l.day = asked.expiry))", (cutoff,))
    db.commit()


def backup(src=DB, snap=SNAP):
    if not os.path.isdir(snap):
        return None
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        c, b = sqlite3.connect(src), sqlite3.connect(tmp)
        c.backup(b)
        b.close()
        c.close()
        out = os.path.join(snap, "cs_legs.db.gz")
        with open(tmp, "rb") as f, gzip.open(out + ".part", "wb") as g:
            g.writelines(f)
        os.replace(out + ".part", out)
        return out
    finally:
        os.remove(tmp)


def open_db(path=DB):
    db = sqlite3.connect(path, timeout=120)
    db.execute("create table if not exists legs(occ text, day text, bid real, ask real, volume int, oi int, iv real, "
               "high real, low real, last real, primary key(occ, day))")
    db.execute("create table if not exists asked(occ text primary key, root text, entry text, expiry text, k real, n int, "
               "pulled_utc text, final int default 0)")
    if "final" not in [r[1] for r in db.execute("pragma table_info(asked)")]:
        db.execute("alter table asked add column final int default 0")
    db.commit()
    return db


def main():
    db = open_db()
    mark_final(db)
    want = wanted()
    final = {r[0] for r in db.execute("select occ from asked where final = 1")}
    todo = [o for o in sorted(want) if o not in final]
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} cs legs: wanted {len(want)}, final {len(final)}, to ask {len(todo)}", flush=True)
    n = 0
    for occ in todo:
        rows = historic(occ)
        n += 1
        if rows is None:
            continue
        for r in rows:
            db.execute("insert or replace into legs values (?,?,?,?,?,?,?,?,?,?)",
                       (occ, r.get("date"), _f(r.get("nbbo_bid")), _f(r.get("nbbo_ask")), r.get("volume"), r.get("open_interest"),
                        _f(r.get("implied_volatility")), _f(r.get("high_price")), _f(r.get("low_price")), _f(r.get("last_price"))))
        root, ent, exp, k = want[occ]
        db.execute("insert or replace into asked(occ, root, entry, expiry, k, n, pulled_utc, final) values (?,?,?,?,?,?,?,0)",
                   (occ, root, ent, exp, k, len(rows), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        if n % 100 == 0:
            db.commit()
            bump(100)
        time.sleep(0.3)
    db.commit()
    bump(n % 100)
    mark_final(db)
    tot, contracts = db.execute("select count(*), count(distinct occ) from legs").fetchone()
    asked, empty, last = db.execute("select count(*), sum(n = 0), max(expiry) from asked").fetchone()
    print(f"cs legs session done: {n} asked this run; {tot:,} contract-days over {contracts:,} contracts; "
          f"{asked:,} names asked, vendor empty on {empty or 0}; newest expiry {last}", flush=True)
    db.close()
    out = backup()
    print(f"cs legs backup: {out} {os.path.getsize(out):,} bytes" if out else "cs legs backup: no snapshot folder - NOT backed up", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                              # an evidence job never pages and never raises
        print(f"cs legs pull failed open: {type(e).__name__}: {e}", flush=True)

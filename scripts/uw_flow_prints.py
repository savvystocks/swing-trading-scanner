"""UW FLOW PRINTS - stage 2 (owner order 2026-08-25: "no shortcuts, full view").

Pulls the INDIVIDUAL prints (exact executed_at timestamp + the real ask at execution) for
every contract-day in the decisive cohorts, via /api/option-contract/{occ}/flow?date= - the
endpoint our plan includes but we never pulled. This removes the last approximation in the
replays: entry at the TRUE trigger time and TRUE ask, not the day's closing quote.

Budget-integrated: shares the same budget table as uw_history_pull (30k/day cap between them,
engine keeps 10k headroom of the 40k plan). Checkpointed per (day, occ); the nightly archive
expansion simply resumes after this finishes - prints outrank breadth this week.
Output: table flow_prints in data/uw_history.db. Replay v3 consumes it once landed.
"""
import json
import os
import sqlite3
import time
import urllib.request
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
DB = "data/uw_history.db"
H = {"Authorization": "Bearer " + os.environ.get("UNUSUAL_WHALES_TOKEN", ""),
     "Accept": "application/json"}
STATE_FILE = os.path.expanduser("~/uw_prints_state.json")
REASK_DAYS = int(os.environ.get("UW_PRINTS_REASK_DAYS", "12"))
DAILY_BUDGET = int(os.environ.get("UW_PULL_BUDGET", "30000"))


def used_today(con):
    r = con.execute("select used from budget where utc_day=?", (date.today().isoformat(),)).fetchone()
    return r[0] if r else 0


def bump(con):
    con.execute("insert into budget(utc_day, used) values(?, 1) on conflict(utc_day) "
                "do update set used=used+1", (date.today().isoformat(),))


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
                return json.loads(r.read()).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(30 * (i + 1)); continue
            if e.code in (404, 422):
                return []
            time.sleep(5)
        except Exception:
            time.sleep(5)
    return None


def _session_state(status, path=None, **kw):
    """One line of truth for scripts/landing_watch.sh: a session that crashes, is killed or hangs
    leaves this file stale or marked crashed, and the watch pages. Never raises."""
    try:
        kw.update({"status": status, "ended_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        with open(path or STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(kw, fh)
    except Exception:
        pass


def is_final(day, reask_floor):
    """UW serves a day's prints late, then in full, then THINS them: contract-days pulled fresh on
    2026-09-11 hold 149-484 prints and the same requests a week later return 2-9. Inside the re-ask
    window no answer is final - the contract-day is asked again every night and `insert or ignore`
    keeps the fullest tape ever seen. Only a day older than the window may be marked done."""
    return day < reask_floor


def commit_retry(con, tries=10, wait=30, _sleep=time.sleep):
    for i in range(tries):
        try:
            con.commit()
            return True
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            print(f"LOCK RETRY {i + 1}/{tries}: {e}", flush=True)
            _sleep(wait)
    raise sqlite3.OperationalError("database is locked after %d retries" % tries)


def main():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("""create table if not exists flow_prints (
        occ text, day text, executed_at text, price real, size int, premium real,
        nbbo_bid real, nbbo_ask real, side_hint text,
        primary key (occ, day, executed_at, size))""")
    con.execute("create table if not exists prints_pulled (day text, occ text, n int, "
                "primary key (day, occ))")
    con.commit()

    # cohort contract-days: every tradeable aggressor-buy row the decisive verdicts rest on
    # (band 50k-1M, spread<=2 at the day quote, full-coverage tickers)
    tks = {r[0] for r in con.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    rows = con.execute(
        """select ticker, option_symbol, day from contracts_daily
           where total_premium between 50000 and 1000000 and ask_volume > bid_volume
             and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
             and (nbbo_ask - nbbo_bid) / ((nbbo_ask + nbbo_bid) / 2.0) * 100 <= 2.0
           order by day desc""").fetchall()
    done = {(r[0], r[1]) for r in con.execute("select day, occ from prints_pulled")}
    _reask = date.fromordinal(date.today().toordinal() - REASK_DAYS).isoformat()
    todo = [(d, occ) for t, occ, d in rows if t in tks and ((d, occ) not in done or not is_final(d, _reask))]
    _win = {}
    print(f"cohort contract-days to pull: {len(todo)}; budget used today "
          f"{used_today(con)}/{DAILY_BUDGET}", flush=True)
    n = 0
    n_def = 0
    d0 = date.today()
    _floor = date.fromordinal(d0.toordinal() - 7).isoformat()   # ZERO-RESULT-DEFER window
    for d, occ in todo:
        if date.today() != d0:
            print("UTC day rolled - stop; the new budget belongs to the new day's crons", flush=True)
            break               # crossing midnight let one session eat two days' budgets and
                                # starve every other puller (2026-09-04)
        if used_today(con) >= DAILY_BUDGET:
            print("budget cap reached - resuming next UTC day", flush=True)
            break
        prints = get(f"https://api.unusualwhales.com/api/option-contract/{occ}/flow?date={d}&limit=500")
        bump(con)
        n += 1
        if prints is None:
            continue
        for pr in prints:
            try:
                con.execute("insert or ignore into flow_prints values (?,?,?,?,?,?,?,?,?)",
                            (occ, d, (pr.get("executed_at") or "")[:23],
                             float(pr.get("price") or 0), int(pr.get("size") or 0),
                             float(pr.get("premium") or 0),
                             float(pr.get("ewma_nbbo_bid") or pr.get("nbbo_bid") or 0),
                             float(pr.get("ewma_nbbo_ask") or pr.get("nbbo_ask") or 0),
                             "ask" if (pr.get("ask_vol") or 0) >= (pr.get("bid_vol") or 0) else "bid"))
            except Exception:
                continue
        if not is_final(d, _reask):
            _w = _win.setdefault(d, [0, 0])
            _w[0] += 1
            _w[1] += len(prints)
            n_def += 1      # ZERO-RESULT-DEFER (2026-09-10): UW publishes a day's prints with a
                            # lag; pulling at 00:15 the next morning returned EMPTY for Sep 1/2/3/8
                            # and the mark made them "done" forever - September held 14 corpus rows
                            # while every newest-day check passed. Inside the recent window an
                            # empty result is "not yet", never "none": retried next session.
        else:
            con.execute("insert into prints_pulled values (?,?,?) on conflict(day, occ) do update "
                        "set n = max(n, excluded.n)", (d, occ, len(prints)))
        if n % 100 == 0:
            commit_retry(con)
            print(f"{n} contract-days pulled ({d} {occ}: {len(prints)} prints)", flush=True)
        time.sleep(0.2)
    commit_retry(con)
    for _d in sorted(_win):     # the vendor's window, learned one night at a time
        _held = con.execute("select count(*) from flow_prints where day = ?", (_d,)).fetchone()[0]
        _age = (date.today() - date.fromisoformat(_d)).days
        print(f"window {_d} (age {_age}d): asked {_win[_d][0]}, API returned {_win[_d][1]} prints tonight, "
              f"archive holds {_held}", flush=True)
    tot = con.execute("select count(*) from flow_prints").fetchone()[0]
    print(f"session done: {n} requests, {tot} prints stored total, {n_def} recent zero-results deferred", flush=True)


if __name__ == "__main__":
    try:
        main()
        _session_state("done")
    except Exception as _e:
        _session_state("crashed", error=f"{type(_e).__name__}: {_e}"[:200])
        raise

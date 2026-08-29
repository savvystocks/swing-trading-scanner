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
    todo = [(d, occ) for t, occ, d in rows if t in tks and (d, occ) not in done]
    print(f"cohort contract-days to pull: {len(todo)}; budget used today "
          f"{used_today(con)}/{DAILY_BUDGET}", flush=True)
    n = 0
    for d, occ in todo:
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
        con.execute("insert or replace into prints_pulled values (?,?,?)", (d, occ, len(prints)))
        if n % 100 == 0:
            con.commit()
            print(f"{n} contract-days pulled ({d} {occ}: {len(prints)} prints)", flush=True)
        time.sleep(0.2)
    con.commit()
    tot = con.execute("select count(*) from flow_prints").fetchone()[0]
    print(f"session done: {n} requests, {tot} prints stored total", flush=True)


if __name__ == "__main__":
    main()

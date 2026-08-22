"""UW HISTORY PULL (owner discovery 2026-08-22: API Basic already includes a 2-YEAR lookback -
the $4,650 Data Shop file is served per contract/date by endpoints we pay for).

Stage 1 (this script): for every ticker x trading day, pull /stock/{t}/option-contracts?date=
-> per-contract daily rows with ASK/BID-side volume, sweep volume, premium, OI, IV, greeks.
Stored in data/uw_history.db (sqlite). Checkpointed and resumable; budget-aware: stops at
DAILY_BUDGET requests per UTC day (engine uses ~6k of the plan's 40k; we take <=30k).
Stage 2 (next): per-contract prints via /option-contract/{occ}/flow?date= for qualifying
contracts (the exact executed_at trigger times).
Run nightly off-hours: cron 22:30 UTC weekdays + all day weekends until complete.
"""
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
DB = "data/uw_history.db"
TOKEN = os.environ.get("UNUSUAL_WHALES_TOKEN", "")
H = {"Authorization": "Bearer " + TOKEN, "Accept": "application/json"}
DAILY_BUDGET = int(os.environ.get("UW_PULL_BUDGET", "30000"))
TICKERS = ("SPY QQQ IWM NVDA TSLA AAPL MSFT AMZN META GOOGL AMD SLV GLD TLT COIN PLTR NFLX MU INTC BA "
           "AVGO SMCI MSTR HOOD IBIT XLE XLF GDX TQQQ SQQQ KO CHWY HIMS PYPL ETHA RIOT CLSK QCOM "
           "IREN ONDS FCEL CCL APLD QBTS WULF PINS EEM TE PURR KWEB").split()
START, END = date(2024, 9, 3), date(2026, 8, 21)


def init():
    con = sqlite3.connect(DB, timeout=60)
    con.execute("""create table if not exists contracts_daily (
        day text, ticker text, option_symbol text, volume int, ask_volume int, bid_volume int,
        mid_volume int, no_side_volume int, sweep_volume int, multi_leg_volume int, floor_volume int,
        total_premium real, open_interest int, prev_oi int, nbbo_bid real, nbbo_ask real,
        avg_price real, last_price real, implied_volatility real, delta real, gamma real,
        theta real, vega real, last_tape_time text, primary key (day, option_symbol))""")
    con.execute("create table if not exists pulled (day text, ticker text, n int, primary key (day, ticker))")
    con.execute("create table if not exists budget (utc_day text primary key, used int)")
    con.commit()
    return con


def used_today(con):
    r = con.execute("select used from budget where utc_day=?", (date.today().isoformat(),)).fetchone()
    return r[0] if r else 0


def bump(con, n=1):
    con.execute("insert into budget(utc_day, used) values(?, ?) on conflict(utc_day) do update set used=used+?",
                (date.today().isoformat(), n, n))


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


def f(x):
    try:
        return float(x) if x not in (None, "") else None
    except Exception:
        return None


def main():
    con = init()
    days = []
    d = START
    while d <= END:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    done = {(r[0], r[1]) for r in con.execute("select day, ticker from pulled")}
    todo = [(dd, t) for dd in reversed(days) for t in TICKERS if (dd, t) not in done]
    print(f"todo {len(todo)} ticker-days; budget used today {used_today(con)}/{DAILY_BUDGET}", flush=True)
    n_calls = 0
    for dd, t in todo:
        if used_today(con) >= DAILY_BUDGET:
            print("daily budget reached - resume tomorrow", flush=True)
            break
        rows = get(f"https://api.unusualwhales.com/api/stock/{t}/option-contracts?date={dd}&limit=500")
        bump(con)
        n_calls += 1
        if rows is None:
            continue
        for r in rows:
            con.execute("insert or replace into contracts_daily values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (dd, t, r.get("option_symbol"), r.get("volume"), r.get("ask_volume"), r.get("bid_volume"),
                         r.get("mid_volume"), r.get("no_side_volume"), r.get("sweep_volume"),
                         r.get("multi_leg_volume"), r.get("floor_volume"), f(r.get("total_premium")),
                         r.get("open_interest"), r.get("prev_oi"), f(r.get("nbbo_bid")), f(r.get("nbbo_ask")),
                         f(r.get("avg_price")), f(r.get("last_price")), f(r.get("implied_volatility")),
                         f(r.get("delta")), f(r.get("gamma")), f(r.get("theta")), f(r.get("vega")),
                         r.get("last_tape_time")))
        con.execute("insert or replace into pulled values (?,?,?)", (dd, t, len(rows)))
        if n_calls % 50 == 0:
            con.commit()
            print(f"{n_calls} calls, latest {dd} {t} ({len(rows)} contracts)", flush=True)
        time.sleep(0.25)
    con.commit()
    tot = con.execute("select count(*) from contracts_daily").fetchone()[0]
    print(f"session done: {n_calls} calls, {tot} contract-days stored", flush=True)


if __name__ == "__main__":
    main()

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
import shutil
import time
import urllib.request
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
DB = "data/uw_history.db"
TOKEN = os.environ.get("UNUSUAL_WHALES_TOKEN", "")
H = {"Authorization": "Bearer " + TOKEN, "Accept": "application/json"}
MAX_PAGES = int(os.environ.get("UW_MAX_PAGES", "12"))   # 5 tripped the sentinel on night one (91 ticker-days)
DAILY_BUDGET = int(os.environ.get("UW_PULL_BUDGET", "30000"))
TICKERS = ("SPY QQQ IWM NVDA TSLA AAPL MSFT AMZN META GOOGL AMD SLV GLD TLT COIN PLTR NFLX MU INTC BA "
           "AVGO SMCI MSTR HOOD IBIT XLE XLF GDX TQQQ SQQQ KO CHWY HIMS PYPL ETHA RIOT CLSK QCOM "
           "IREN ONDS FCEL CCL APLD QBTS WULF PINS EEM TE PURR KWEB "
           # EXPANSION 2026-08-23 (owner: take everything while the subscription is live - the
           # archive is ours forever after cancellation). Liquid optionable names the live engine
           # can actually trade, so the archive covers the real candidate universe, not my guess.
           "DIS GM F T VZ PFE BAC JPM WFC C GS MS XOM CVX OXY SLB HAL UNH JNJ LLY MRK ABBV "
           "WMT TGT COST HD LOW NKE SBUX MCD CMG ORCL CRM ADBE NOW SNOW PANW CRWD ZS DDOG NET "
           "SHOP SQ SOFI AFRM UPST LCID RIVN NIO XPEV LI BABA JD PDD TSM ASML ARM AMAT LRCX KLAC "
           "MRVL ON SWKS QRVO TXN ADI NXPI STX WDC DELL HPQ IBM CSCO ANET JNPR "
           "UBER LYFT DASH ABNB BKNG MAR HLT DAL UAL AAL LUV CVNA CARR OTIS "
           "AMC GME BBBY BB NOK SNDL TLRY ACB HEXO PLUG BLNK CHPT RUN ENPH SEDG FSLR "
           "XLK XLV XLI XLP XLU XLB XLRE XBI SMH SOXL SOXS SPXL SPXS UVXY VXX SVXY "
           "ARKK ARKG ARKW JETS XRT ITB KRE IYR VNQ EFA VEA VWO FXI YINN "
           "MARA HUT BITF CIFR CORZ GLXY BTBT SDIG HIVE "
           "AI SOUN BBAI PATH SMR OKLO NNE LEU CCJ UEC DNN "
           "AVAV RKLB LUNR ASTS PL SPCE JOBY ACHR "
           "GEV VST CEG NRG TLN PWR ETN "
           "NVO NVAX MRNA BNTX PFE GILD BIIB REGN VRTX AMGN "
           "DKNG PENN CZR MGM LVS WYNN RCL NCLH "
           "TTD ROKU SPOT PINS SNAP RDDT DUOL "
           "IONQ RGTI ARQQ QUBT "
           "USO UNG BNO XOP OIH URA LIT REMX COPX SILJ NUGT DUST JNUG").split()
START = date(2023, 10, 17)   # the UW token's floor: a ROLLING 730-TRADING-day window, verified
                             # 2026-09-17 by a live 403 ("earliest date currently available ...
                             # 2023-10-17"). It moves forward a day at a time, so unpulled history
                             # expires permanently. reversed(days) below keeps recent days first,
                             # so the backfill only ever spends leftover budget.
END = date.today() - timedelta(days=1)  # ROLLING - a hardcoded END froze the archive at 08-21
                                        # and every corpus downstream went silently stale while
                                        # 30k calls/night backfilled ancient days (2026-09-04)


def init():
    con = sqlite3.connect(DB, timeout=300)
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


def commit_retry(con, tries=10, wait=30, _sleep=time.sleep):
    """A long READ elsewhere (fade_meta walks this archive for ~30 minutes) holds a shared lock and the
    commit cannot take its exclusive one. On 2026-09-18 that killed the session at call 900 of a
    night's 18,000 while an expiring window was being backfilled. Wait it out; only a lock is retried."""
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
    d0 = date.today()
    n_def = 0
    n_trunc = 0
    _floor = (date.today() - timedelta(days=7)).isoformat()   # ZERO-RESULT-DEFER window
    for dd, t in todo:
        if date.today() != d0:
            print("UTC day rolled - stop; the new budget belongs to the new day's crons", flush=True)
            break               # crossing midnight let one session eat two days' budgets and
                                # starve every other puller (2026-09-04)
        if used_today(con) >= DAILY_BUDGET:
            print("daily budget reached - resume tomorrow", flush=True)
            break
        if shutil.disk_usage(".").free / 2 ** 30 < 3.0:
            print("DISK GUARD: under 3 GiB free - stopping", flush=True)
            break
        # PAGINATION (2026-09-17). limit is a hard server cap of 500 and `page` is the only way
        # past it; `offset`/`skip` are ignored. Two years were silently truncated because nothing
        # ever asked for page 2 - 80.6% of ticker-days sat at exactly 500 rows. Page on only while
        # the page came back FULL and its tail still has volume, so we fetch the real missing tail
        # on SPY/QQQ/NVDA and not zero-volume chain padding on all 260 names.
        rows = []
        for _pg in range(1, MAX_PAGES + 1):
            _u = f"https://api.unusualwhales.com/api/stock/{t}/option-contracts?date={dd}&limit=500"
            if _pg > 1:
                _u += f"&page={_pg}"
            _page = get(_u)
            bump(con)
            n_calls += 1
            if _page is None:
                rows = None if _pg == 1 else rows
                break
            rows.extend(_page)
            _v = [int(x.get("volume") or 0) for x in _page]
            if len(_page) < 500 or not _v or min(_v) <= 0:
                break
            if _pg == MAX_PAGES:
                n_trunc += 1        # still full AND still has volume at the page cap = truncated
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
        if len(rows) == 0 and dd >= _floor:
            n_def += 1      # ZERO-RESULT-DEFER (2026-09-10): an empty day inside the recent
                            # window is "not published yet", never "done" - retried next session
        else:
            con.execute("insert or replace into pulled values (?,?,?)", (dd, t, len(rows)))
        if n_calls % 50 < MAX_PAGES:
            commit_retry(con)
            print(f"{n_calls} calls, latest {dd} {t} ({len(rows)} contracts)", flush=True)
        time.sleep(0.25)
    commit_retry(con)
    tot = con.execute("select count(*) from contracts_daily").fetchone()[0]
    print(f"session done: {n_calls} calls, {tot} contract-days stored, {n_def} recent zero-results deferred", flush=True)
    if n_trunc:
        # REGRESSION SENTINEL for the 2026-09-17 truncation: a ticker-day that hits the page cap
        # while its tail still has volume is still being cut. Silence here is the healthy state.
        print(f"TRUNCATION WARNING: {n_trunc} ticker-days hit the {MAX_PAGES}-page cap with volume "
              f"still in the tail - raise UW_MAX_PAGES", flush=True)


if __name__ == "__main__":
    main()

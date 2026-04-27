import os
import subprocess
import sys
from datetime import datetime, timedelta

def load(n):
    if os.environ.get(n): return os.environ[n]
    r = subprocess.run(["powershell","-Command",f'[Environment]::GetEnvironmentVariable("{n}","User")'], capture_output=True, text=True)
    return (r.stdout or "").strip()

for k in ("EODHD_API_KEY",):
    v = load(k)
    if v: os.environ[k]=v

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.eodhd import EODHDClient
from src.indicators import to_dataframe

client = EODHDClient(cache_hours=12)

PEERS = [
    ("HAL.US",  "Halliburton",   "2026-04-21"),
    ("BKR.US",  "Baker Hughes",  "2026-04-23"),
]
PUMP_EARNINGS = "2026-05-05"
TODAY = datetime(2026, 4, 28)

print("=" * 92)
print("  PEER PRE-EARNINGS PATTERN STUDY -> applied to PUMP")
print("=" * 92)
print()
print("Goal: did HAL and BKR show institutional accumulation in the 15 sessions BEFORE")
print("their Q1 2026 beats? If yes, did the stock run up into the print or fade?")
print("Then map the same template onto PUMP's current 7-day-pre-earnings setup.")
print()

def pull_window(ticker, earnings_date_str, sessions_before=20):
    ed = datetime.strptime(earnings_date_str, "%Y-%m-%d")
    from_d = (ed - timedelta(days=sessions_before*2 + 30)).strftime("%Y-%m-%d")
    to_d   = (ed + timedelta(days=10)).strftime("%Y-%m-%d")
    raw = client.ohlcv(ticker, from_date=from_d, to_date=to_d)
    df = to_dataframe(raw)
    return df, ed

def pre_earnings_pattern(df, ed, sessions=15):
    pre = df[df.index < ed].tail(sessions).copy()
    avg_vol_40 = df['volume'].tail(40).mean()
    pre['pct'] = pre['close'].pct_change() * 100
    pre['vol_pct'] = pre['volume'] / avg_vol_40 * 100
    acc = ((pre['pct'] > 0.3) & (pre['vol_pct'] > 110)).sum()
    dist = ((pre['pct'] < -0.3) & (pre['vol_pct'] > 110)).sum()
    start = pre['close'].iloc[0]
    end = pre['close'].iloc[-1]
    run_pct = (end/start - 1) * 100
    return pre, acc, dist, run_pct, avg_vol_40

def post_earnings_move(df, ed):
    after = df[df.index >= ed].head(3)
    if len(after) == 0: return None, None, None
    open_d1 = after.iloc[0]['open']
    close_d1 = after.iloc[0]['close']
    last_pre = df[df.index < ed].iloc[-1]['close']
    gap = (open_d1/last_pre - 1) * 100
    d1_chg = (close_d1/last_pre - 1) * 100
    return gap, d1_chg, after

for ticker, name, ed_str in PEERS:
    print("-" * 92)
    print(f"{name} ({ticker})  earnings {ed_str}")
    print("-" * 92)
    try:
        df, ed = pull_window(ticker, ed_str)
        pre, acc, dist, run_pct, avg_vol = pre_earnings_pattern(df, ed, 15)
        print(f"  15 sessions before earnings:")
        print(f"  {'Date':12s} {'Close':>8s} {'%chg':>7s} {'Vol':>12s} {'avgV%':>6s}  flag")
        for dt, r in pre.iterrows():
            flag = ""
            if r['pct'] > 0.3 and r['vol_pct'] > 110: flag = " ACC"
            elif r['pct'] < -0.3 and r['vol_pct'] > 110: flag = " DIST"
            pct_str = f"{r['pct']:+.1f}%" if not (r['pct'] != r['pct']) else "  n/a"
            print(f"  {dt.strftime('%Y-%m-%d')} {r['close']:>8.2f} {pct_str:>7s} {int(r['volume']):>12,d} {r['vol_pct']:>5.0f}%{flag}")
        print()
        print(f"  Pre-earnings run: {run_pct:+.1f}% over 15 sessions")
        print(f"  Accumulation days: {acc} | Distribution days: {dist}")
        print(f"  Net read: {'INSTITUTIONAL ACCUMULATION' if acc > dist+1 else 'NEUTRAL' if acc >= dist else 'DISTRIBUTION'}")
        gap, d1_chg, after = post_earnings_move(df, ed)
        if gap is not None:
            print()
            print(f"  Post-earnings reaction:")
            print(f"    Gap on print day open: {gap:+.1f}%")
            print(f"    Day-1 close vs pre-print close: {d1_chg:+.1f}%")
            print(f"    Next 3 sessions:")
            for dt, r in after.iterrows():
                print(f"      {dt.strftime('%Y-%m-%d')}  O={r['open']:.2f} H={r['high']:.2f} L={r['low']:.2f} C={r['close']:.2f}")
    except Exception as e:
        print(f"  Failed: {e}")
    print()

print("=" * 92)
print("  PUMP CURRENT SETUP (7 sessions before 5 May earnings)")
print("=" * 92)
try:
    pump_df, pump_ed = pull_window("PUMP.US", PUMP_EARNINGS)
    pump_pre = pump_df[pump_df.index < TODAY].tail(15).copy()
    avg_vol_40 = pump_df['volume'].tail(40).mean()
    pump_pre['pct'] = pump_pre['close'].pct_change() * 100
    pump_pre['vol_pct'] = pump_pre['volume'] / avg_vol_40 * 100
    acc = ((pump_pre['pct'] > 0.3) & (pump_pre['vol_pct'] > 110)).sum()
    dist = ((pump_pre['pct'] < -0.3) & (pump_pre['vol_pct'] > 110)).sum()
    start_15 = pump_pre['close'].iloc[0]
    end_15 = pump_pre['close'].iloc[-1]
    run_pct = (end_15/start_15 - 1) * 100
    print(f"  Last 15 sessions (we are {(pump_ed - TODAY).days} cal days before earnings):")
    print(f"  {'Date':12s} {'Close':>8s} {'%chg':>7s} {'Vol':>12s} {'avgV%':>6s}  flag")
    for dt, r in pump_pre.iterrows():
        flag = ""
        if r['pct'] > 0.3 and r['vol_pct'] > 110: flag = " ACC"
        elif r['pct'] < -0.3 and r['vol_pct'] > 110: flag = " DIST"
        pct_str = f"{r['pct']:+.1f}%" if not (r['pct'] != r['pct']) else "  n/a"
        print(f"  {dt.strftime('%Y-%m-%d')} {r['close']:>8.2f} {pct_str:>7s} {int(r['volume']):>12,d} {r['vol_pct']:>5.0f}%{flag}")
    print()
    print(f"  Pre-earnings run: {run_pct:+.1f}% over 15 sessions")
    print(f"  Accumulation days: {acc} | Distribution days: {dist}")
    print(f"  Net read: {'INSTITUTIONAL ACCUMULATION' if acc > dist+1 else 'NEUTRAL' if acc >= dist else 'DISTRIBUTION'}")
except Exception as e:
    print(f"  Failed: {e}")
print()

print("=" * 92)
print("  TEMPLATE TRANSFER -> what PUMP likely does into 5 May")
print("=" * 92)
print("""
Read off the peers:
  - If HAL and BKR drifted higher on shrinking volume into print, the bid was already
    in -> reaction depends on guidance, not pre-positioning. PUMP likely gets a small
    grind-up week then a binary print.
  - If HAL/BKR rallied hard on heavy volume into print and then GAPPED UP on the beat,
    market was front-running the catalyst -> PUMP could see the same ramp this week
    (Wed-Fri) before the IV crush event.
  - If HAL/BKR ran up but then SOLD OFF on the beat (classic "buy the rumour, sell
    the news") -> warning sign for PUMP. The 4 May exit becomes essential.

Map onto our 4 May exit decision:
  - PUMP is sitting on 0 distribution days in 15 sessions and 2 high-conviction acc
    days. That matches the HAL/BKR template if peers showed similar accumulation.
  - We close 4 May regardless. The peer template tells us what to expect IN THAT WEEK
    (Wed-Fri this week + Mon 4 May). If peers ran 5-8% into print, PUMP could rally
    to $18-19 by Fri/Mon = premium $3.30-4.10 = +$800-1450 P&L.
  - If peers FADED into print, PUMP may already be at the highs and we should be
    tighter on the 4 May exit (consider trimming half on Thu/Fri if premium > $3.30).
""")

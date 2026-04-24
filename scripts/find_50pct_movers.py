import os
import subprocess
import sys
import json
from datetime import datetime, timedelta
import pandas as pd

def load(n):
    r = subprocess.run(
        ["powershell", "-Command", f'[Environment]::GetEnvironmentVariable("{n}","User")'],
        capture_output=True, text=True,
    )
    return (r.stdout or "").strip()

for k in ("EODHD_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
    if not os.environ.get(k):
        v = load(k)
        if v:
            os.environ[k] = v

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eodhd import EODHDClient

client = EODHDClient()

universe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "universe", "universe.json")
with open(universe_path) as f:
    universe = json.load(f)

print(f"Universe size: {len(universe)}")

end = datetime.now().strftime("%Y-%m-%d")
start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

winners = []
errors = 0

for i, t in enumerate(universe):
    tkr = t["ticker"]
    try:
        raw = client.ohlcv(tkr, from_date=start, to_date=end)
        if not raw or len(raw) < 30:
            continue
        df = pd.DataFrame(raw)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        if len(df) < 30:
            continue

        closes = df["close"]
        recent = closes.tail(30)
        if recent.empty:
            continue

        best_return = 0
        best_start = None
        best_end = None
        for window in (15, 20, 25):
            if len(closes) < window + 30:
                continue
            for end_idx in range(len(closes) - 30, len(closes)):
                start_idx = max(0, end_idx - window)
                if start_idx == end_idx:
                    continue
                lo = closes.iloc[start_idx:end_idx+1].min()
                hi = closes.iloc[start_idx:end_idx+1].max()
                if lo > 0:
                    ret = (hi / lo) - 1
                    if ret > best_return:
                        best_return = ret
                        lo_idx = closes.iloc[start_idx:end_idx+1].idxmin()
                        hi_idx = closes.iloc[start_idx:end_idx+1].idxmax()
                        if lo_idx < hi_idx:
                            best_start = lo_idx
                            best_end = hi_idx

        if best_return >= 0.50 and best_start is not None:
            entry_price = float(closes.loc[best_start])
            peak_price = float(closes.loc[best_end])
            current_price = float(closes.iloc[-1])
            days_to_peak = (best_end - best_start).days
            winners.append({
                "ticker": tkr,
                "name": t.get("name",""),
                "sector": t.get("sector",""),
                "industry": t.get("industry",""),
                "index": t.get("index",""),
                "entry_date": best_start.strftime("%Y-%m-%d"),
                "entry_price": round(entry_price, 2),
                "peak_date": best_end.strftime("%Y-%m-%d"),
                "peak_price": round(peak_price, 2),
                "current_price": round(current_price, 2),
                "move_pct": round(best_return*100, 1),
                "days_to_peak": days_to_peak,
                "pct_from_peak": round((current_price/peak_price-1)*100, 1),
            })

        if (i+1) % 100 == 0:
            print(f"  scanned {i+1}/{len(universe)}, {len(winners)} winners, {errors} errors")
    except Exception as ex:
        errors += 1
        if errors < 5:
            print(f"  err {tkr}: {type(ex).__name__}: {ex}")
        continue

winners.sort(key=lambda w: w["move_pct"], reverse=True)

print(f"\n=== STOCKS THAT MOVED 50%+ IN A 15-25 DAY WINDOW (LAST 30 DAYS) ===")
print(f"Total winners: {len(winners)}\n")
print(f"{'TICKER':12s} {'MOVE%':>6s} {'DAYS':>4s} {'ENTRY_DT':11s} {'ENTRY$':>8s} {'PEAK_DT':11s} {'PEAK$':>8s} {'NOW$':>8s} {'FROM_PEAK':>9s} {'INDEX':6s} {'SECTOR':16s} {'NAME':28s}")
for w in winners[:50]:
    print(f"{w['ticker']:12s} {w['move_pct']:>5.1f}% {w['days_to_peak']:>4d} {w['entry_date']:11s} {w['entry_price']:>7.2f} {w['peak_date']:11s} {w['peak_price']:>7.2f} {w['current_price']:>7.2f} {w['pct_from_peak']:>+7.1f}% {w['index']:6s} {(w['sector'] or '')[:16]:16s} {(w['name'] or '')[:28]:28s}")

os.makedirs("data/results", exist_ok=True)
with open("data/results/50pct_movers_raw.json", "w") as f:
    json.dump(winners, f, indent=2, default=str)
print(f"\nSaved to data/results/50pct_movers_raw.json")

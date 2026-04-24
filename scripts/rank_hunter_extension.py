import os
import subprocess
import sys
from datetime import datetime, timedelta
import pandas as pd

def load(n):
    r = subprocess.run(
        ["powershell", "-Command", f'[Environment]::GetEnvironmentVariable("{n}","User")'],
        capture_output=True, text=True,
    )
    return (r.stdout or "").strip()

for k in ("EODHD_API_KEY",):
    if not os.environ.get(k):
        v = load(k)
        if v:
            os.environ[k] = v

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.eodhd import EODHDClient
from src.indicators import compute_all, to_dataframe

client = EODHDClient()

PICKS = [
    ("SYNA.US", 94, "Synaptics", "Tech"),
    ("LBRT.US", 93, "Liberty Oilfield", "Energy"),
    ("NVTS.US", 89, "Navitas Semi", "Tech"),
    ("ARWR.US", 87, "Arrowhead Pharma", "Healthcare"),
    ("PUMP.US", 85, "ProPetro Holding", "Energy"),
    ("IMNM.US", 83, "Immunome", "Healthcare"),
    ("AMKR.US", 80, "Amkor Tech", "Tech"),
    ("ON.US",   79, "ON Semi", "Tech"),
    ("AMAT.US", 69, "Applied Materials", "Tech"),
]

end = datetime.now().strftime("%Y-%m-%d")
start = (datetime.now() - timedelta(days=420)).strftime("%Y-%m-%d")

rows = []
for tkr, hunter, name, sec in PICKS:
    try:
        raw = client.ohlcv(tkr, from_date=start, to_date=end)
        df = to_dataframe(raw)
        ind = compute_all(df)
        last = ind.iloc[-1]
        close = float(last["close"])

        sma_50 = float(last["sma_50"]) if pd.notna(last["sma_50"]) else None
        sma_200 = float(last["sma_200"]) if pd.notna(last["sma_200"]) else None

        pct_50 = (close/sma_50 - 1)*100 if sma_50 else None
        pct_200 = (close/sma_200 - 1)*100 if sma_200 else None

        high_252 = float(df["high"].iloc[-252:].max()) if len(df) >= 252 else float(df["high"].max())
        low_252 = float(df["low"].iloc[-252:].min()) if len(df) >= 252 else float(df["low"].min())
        pct_from_high = (close/high_252 - 1)*100
        pct_above_low = (close/low_252 - 1)*100

        price_20d_ago = float(df["close"].iloc[-21]) if len(df) >= 21 else close
        ret_20d = (close/price_20d_ago - 1)*100

        price_5d_ago = float(df["close"].iloc[-6]) if len(df) >= 6 else close
        ret_5d = (close/price_5d_ago - 1)*100

        atr_pct = float(last["atr_14"])/close*100 if pd.notna(last["atr_14"]) else None

        # BB squeeze percentile
        sq = last.get("bb_squeeze_pct")
        sq_v = float(sq) if pd.notna(sq) else None

        rows.append({
            "tkr": tkr.replace(".US",""),
            "hunter": hunter,
            "name": name,
            "sector": sec,
            "close": close,
            "pct_50": pct_50,
            "pct_200": pct_200,
            "pct_from_high": pct_from_high,
            "pct_above_low": pct_above_low,
            "ret_5d": ret_5d,
            "ret_20d": ret_20d,
            "atr_pct": atr_pct,
            "sq_pct": sq_v,
        })
    except Exception as e:
        print(f"err {tkr}: {e}")

print("\n=== HUNTER PICKS — EXTENSION & ROOM-TO-RUN ANALYSIS ===\n")
print(f"{'TICKER':7s} {'HUNT':>4s} {'PRICE':>7s} {'%50d':>6s} {'%200d':>7s} {'%52wH':>6s} {'5d':>6s} {'20d':>6s} {'ATR':>5s} {'SqPct':>5s}")
for r in rows:
    print(f"{r['tkr']:7s} {r['hunter']:>4d} ${r['close']:>6.2f} "
          f"{r['pct_50']:>+5.1f}% {r['pct_200']:>+6.1f}% {r['pct_from_high']:>+5.1f}% "
          f"{r['ret_5d']:>+5.1f}% {r['ret_20d']:>+5.1f}% {r['atr_pct']:>4.1f}% "
          f"{r['sq_pct']:>4.0f}")

def freshness_score(r):
    s = r["hunter"]
    if r["pct_50"] is None:
        return s
    ext = r["pct_50"]
    if ext <= 8:
        s += 10
    elif ext <= 15:
        s += 0
    elif ext <= 25:
        s -= 8
    elif ext <= 35:
        s -= 18
    else:
        s -= 28
    if r["ret_20d"] and r["ret_20d"] > 25:
        s -= 10
    if r["sq_pct"] is not None and r["sq_pct"] <= 25:
        s += 8
    return s

for r in rows:
    r["fresh"] = freshness_score(r)

print("\n=== RERANKED: HUNTER + FRESHNESS (extension-aware) ===\n")
print(f"{'TICKER':7s} {'HUNT':>4s} {'FRESH':>5s} {'%50d':>6s} {'20d':>6s} {'Squeeze':>7s}  Verdict")
for r in sorted(rows, key=lambda x: -x["fresh"]):
    ext = r["pct_50"] or 0
    ret20 = r["ret_20d"] or 0
    sq = r["sq_pct"] or 999
    if ext <= 10 and ret20 <= 15:
        verdict = "PRIME — still basing"
    elif ext <= 18:
        verdict = "Good — mild extension"
    elif ext <= 28:
        verdict = "Extended — smaller size"
    else:
        verdict = "CHASING — skip or tiny size"
    if sq <= 25:
        verdict += " + coiled"
    print(f"{r['tkr']:7s} {r['hunter']:>4d} {r['fresh']:>5d} {ext:>+5.1f}% {ret20:>+5.1f}% {sq:>6.0f}   {verdict}")

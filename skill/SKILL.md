---
name: swing-research
description: Analyze a single stock ticker against Savvas's v3.1 quantitative swing trading system. Use this skill when the user asks to research a ticker, check a swing trade setup, evaluate a stock for swing trading, or run the Minervini-style pillar analysis. Works for US tickers (S&P 500, Russell 2000) and LSE tickers (FTSE 100, FTSE 250). Requires an EODHD All-in-One API key.
---

# Swing Trading Research (v3.1)

Analyze a ticker against the 7-pillar + 4-gate quantitative swing trading system. The user will provide a ticker like "ENVA", "SHEL.LSE", or "STRL.US". Default to `.US` suffix if no market suffix given.

## When to trigger
The user asks to research, analyze, check, evaluate, or screen a specific stock ticker for swing trading. Examples: "research ENVA", "check SHEL.LSE for a swing trade", "what's the v3.1 setup on AAPL", "is STRL worth buying".

## API key handling
This skill needs an EODHD All-in-One API key. If the user hasn't pasted one in the current conversation, ask for it once. Do not store it; just use it for the current session's analysis tool calls.

## Workflow

1. Normalise the ticker: strip whitespace, uppercase, append `.US` if no market suffix.
2. Run the embedded Python script in the analysis tool with the ticker and API key as variables.
3. Walk the user through every pillar and gate in plain English, matching the style of the example breakdown below. For each pillar: what it checks, this stock's numbers, pass/fail, and why. For each gate: same. End with an honest verdict.

## Python analysis script

Use the analysis tool to run this exact script (paste the `API_KEY` and `TICKER` values in at the top). It is self-contained and uses only `requests` and `pandas`, both available in the analysis tool sandbox.

```python
import requests, pandas as pd, re
from datetime import datetime

API_KEY = "<paste user's EODHD key>"
TICKER = "<paste ticker>"
FROM_DATE = "2024-11-01"
BASE = "https://eodhd.com/api"

def get(path, params=None):
    p = {"api_token": API_KEY, "fmt": "json"}
    if params: p.update(params)
    r = requests.get(f"{BASE}{path}", params=p, timeout=30)
    if r.status_code == 404: return None
    r.raise_for_status()
    return r.json()

def to_df(ohlcv):
    df = pd.DataFrame(ohlcv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    for c in ("open","high","low","close","adjusted_close","volume"):
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def sma(s, p): return s.rolling(p, min_periods=p).mean()
def ema(s, p): return s.ewm(span=p, adjust=False).mean()

def bollinger(s, p=20, m=2.0):
    mid = sma(s, p)
    std = s.rolling(p, min_periods=p).std()
    return mid, mid+m*std, mid-m*std, ((mid+m*std)-(mid-m*std))/mid

def compute(df):
    c = df["close"]
    out = df.copy()
    for p in (50,150,200): out[f"sma_{p}"] = sma(c, p)
    mid, upper, lower, width = bollinger(c, 20, 2.0)
    out["bb_upper"] = upper
    out["bb_width"] = width
    out["bb_squeeze_pct"] = width.rolling(120, min_periods=120).apply(lambda w: w.rank(pct=True).iloc[-1]*100)
    out["avg_vol_20"] = df["volume"].rolling(20, min_periods=20).mean()
    return out

def num(x):
    try: return float(x)
    except: return None

is_us = TICKER.endswith(".US")

spy = to_df(get("/eod/SPY.US", {"from": FROM_DATE}))
vuke = to_df(get("/eod/VUKE.LSE", {"from": FROM_DATE}))
vix_data = get("/eod/VIX.INDX", {"from": FROM_DATE})
vix_df = to_df(vix_data) if vix_data else None

ohlcv = get(f"/eod/{TICKER}", {"from": FROM_DATE})
if not ohlcv or len(ohlcv) < 210:
    raise SystemExit(f"Insufficient OHLCV history for {TICKER}")
df = to_df(ohlcv)
ind = compute(df)

fundamentals = get(f"/fundamentals/{TICKER}")
if not fundamentals:
    raise SystemExit(f"No fundamentals for {TICKER}")

insider = get("/insider-transactions", {"code": TICKER, "limit": 20}) if is_us else []
try:
    news = get("/news", {"s": TICKER, "limit": 20}) or []
except:
    news = []

benchmark = vuke if TICKER.endswith(".LSE") else spy

last = ind.iloc[-1]
close = float(last["close"])
sma50, sma150, sma200 = last["sma_50"], last["sma_150"], last["sma_200"]
high52 = df["high"].iloc[-252:].max()
low52 = df["low"].iloc[-252:].min()
past_200 = ind["sma_200"].iloc[-22:]
trend_200_up = past_200.iloc[-1] > past_200.iloc[0]

tt = {
  "1_above_150_200": close > sma150 and close > sma200,
  "2_sma150_above_sma200": sma150 > sma200,
  "3_sma200_trending_up": bool(trend_200_up),
  "4_sma50_above_sma150_sma200": sma50 > sma150 and sma50 > sma200,
  "5_30pct_above_52wk_low": close >= low52*1.30,
  "6_within_25pct_of_52wk_high": close >= high52*0.75,
  "7_rs_placeholder": True,
}
tt_passed = sum(1 for v in tt.values() if v)

sma_30wk = df["close"].rolling(150, min_periods=150).mean().iloc[-1]
sma_30wk_prev = df["close"].rolling(150, min_periods=150).mean().iloc[-21]
stage = 2 if (close > sma_30wk and sma_30wk > sma_30wk_prev) else (3 if close > sma_30wk else (4 if sma_30wk < sma_30wk_prev else 1))

p1_verdict = "PASS" if (tt_passed == 7 and stage == 2) else ("PARTIAL" if (tt_passed >= 5 and stage == 2) else "FAIL")

squeeze_pct = last["bb_squeeze_pct"]
upper_break = close > last["bb_upper"]
recent_squeeze = ind["bb_squeeze_pct"].iloc[-10:].min() <= 20
p2_verdict = "PASS" if (recent_squeeze and upper_break) else ("PARTIAL" if squeeze_pct <= 20 else "FAIL")

h = fundamentals.get("Highlights", {}) or {}
eps_g = num(h.get("QuarterlyEarningsGrowthYOY"))
rev_g = num(h.get("QuarterlyRevenueGrowthYOY"))
pm = num(h.get("ProfitMargin"))
roe = num(h.get("ReturnOnEquityTTM"))
peg = num(h.get("PEGRatio"))
p3_checks = {
    "eps_25pct": eps_g is not None and eps_g >= 0.25,
    "rev_20pct": rev_g is not None and rev_g >= 0.20,
    "margin_pos": pm is not None and pm > 0,
    "roe_17pct": roe is not None and roe >= 0.17,
    "peg_ok": peg is not None and 0 < peg <= 2.5,
}
p3_passed = sum(1 for v in p3_checks.values() if v)
p3_verdict = "PASS" if p3_passed >= 4 else ("PARTIAL" if p3_passed >= 3 else "FAIL")

c_start = ind["close"].iloc[-21]; c_end = ind["close"].iloc[-1]
b_start = benchmark["close"].iloc[-21]; b_end = benchmark["close"].iloc[-1]
cret = (c_end-c_start)/c_start*100
bret = (b_end-b_start)/b_start*100
rs = cret - bret
p4_verdict = "PASS" if rs >= 3.0 else ("PARTIAL" if rs >= 1.0 else "FAIL")

vix = float(vix_df["close"].iloc[-1]) if vix_df is not None else None
if vix is None: regime, p5_verdict = "unknown", "PARTIAL"
elif vix < 15: regime, p5_verdict = "low_vol", "PASS"
elif vix <= 22: regime, p5_verdict = "normal", "PASS"
elif vix <= 30: regime, p5_verdict = "elevated", "PARTIAL"
elif vix <= 35: regime, p5_verdict = "extreme", "FAIL"
else: regime, p5_verdict = "crisis", "FAIL"

earnings = fundamentals.get("Earnings", {}) or {}
history = earnings.get("History", {}) or {}
trend = earnings.get("Trend", {}) or {}
ratings = fundamentals.get("AnalystRatings", {}) or {}

beats, last_surprise = 0, None
for _, row in sorted(history.items(), reverse=True)[:4]:
    sp = num(row.get("surprisePercent"))
    if sp is not None:
        if last_surprise is None: last_surprise = sp
        if sp > 0: beats += 1

up30, down30 = 0, 0
if trend:
    ft = list(trend.values())[0]
    up30 = int(float(ft.get("epsRevisionsUpLast30days") or 0))
    down30 = int(float(ft.get("epsRevisionsDownLast30days") or 0))

beat_and_raise = beats >= 2 and last_surprise and last_surprise > 0
pos_rev = up30 > down30 and up30 >= 2
if down30 > up30*2 and down30 >= 3: p6_verdict = "FAIL"
elif beat_and_raise and pos_rev: p6_verdict = "PASS_BONUS"
elif beat_and_raise or pos_rev: p6_verdict = "PASS"
elif up30 >= 1 and down30 == 0: p6_verdict = "PARTIAL"
else: p6_verdict = "FAIL"

stats = fundamentals.get("SharesStats", {}) or {}
sp_float = num(stats.get("ShortPercentFloat"))
shares_float = num(stats.get("SharesFloat"))
if sp_float is None:
    p7_verdict = "FAIL" if is_us else "UNAVAILABLE"
    si_pct, si_level, dtc = 0, "none", None
else:
    si_pct = sp_float if sp_float <= 1 else sp_float/100.0
    si_level = "coiled_spring" if si_pct >= 0.20 else ("moderate" if si_pct >= 0.10 else ("low" if si_pct >= 0.03 else "none"))
    avg_vol = last["avg_vol_20"]
    dtc = (shares_float * si_pct / avg_vol) if shares_float and avg_vol else None
    if si_level == "coiled_spring": p7_verdict = "PASS_BONUS"
    elif si_level == "moderate": p7_verdict = "PASS"
    else: p7_verdict = "FAIL"

avg_vol = last["avg_vol_20"]
rvol = float(last["volume"]/avg_vol) if avg_vol else None
g3_verdict = "PASS" if rvol and rvol >= 1.5 else ("PARTIAL" if rvol and rvol >= 1.0 else "FAIL")

cutoff = pd.Timestamp.now() - pd.Timedelta(days=90)
recent_beat = any(pd.Timestamp(k) >= cutoff and num(r.get("surprisePercent")) and num(r.get("surprisePercent")) >= 5 for k, r in history.items() if k)
KW_A = [r"beat.{0,20}estimate", r"raises? guidance", r"fda approval", r"acquires?", r"merger", r"buyout"]
KW_B = [r"analyst upgrade", r"price target raised?", r"new product", r"partnership"]
tier_a = []
tier_b = []
for n in (news or [])[:20]:
    t = ((n.get("title") or "") + " " + (n.get("content") or "")[:500]).lower()
    if any(re.search(k, t) for k in KW_A): tier_a.append(n.get("title",""))
    elif any(re.search(k, t) for k in KW_B): tier_b.append(n.get("title",""))
if recent_beat or tier_a: g4_verdict, cat_tier = "PASS", "A"
elif tier_b: g4_verdict, cat_tier = "PASS", "B"
else: g4_verdict, cat_tier = "FAIL", "C"

mcap = num(h.get("MarketCapitalization"))
shares_out = num(stats.get("SharesOutstanding"))
float_pct = (shares_float/shares_out*100) if shares_float and shares_out else None
dvol = (avg_vol * close) if avg_vol else 0
g6_verdict = "PASS" if (mcap and mcap >= 500_000_000 and dvol >= 2_000_000 and float_pct is not None and float_pct >= 30) else "FAIL"

today = pd.Timestamp.now().normalize()
future, past_actual = [], 0
for row in history.values():
    rd = row.get("reportDate")
    if not rd: continue
    try: d = pd.Timestamp(rd)
    except: continue
    if row.get("epsActual") is not None: past_actual += 1
    elif d >= today: future.append(d)
if not history or past_actual == 0:
    g7_verdict, next_e, days_until = "FAIL", None, None
elif not future:
    g7_verdict, next_e, days_until = "PASS", None, None
else:
    next_date = min(future)
    days_until = (next_date - today).days
    g7_verdict = "FAIL" if days_until <= 10 else "PASS"
    next_e = next_date.strftime("%Y-%m-%d")

pillars = {"P1":p1_verdict,"P2":p2_verdict,"P3":p3_verdict,"P4":p4_verdict,"P5":p5_verdict,"P6":p6_verdict,"P7":p7_verdict}
applicable = 6 if (not is_us and p7_verdict == "UNAVAILABLE") else 7
if not is_us and p7_verdict == "UNAVAILABLE": pillars.pop("P7")
passes = sum(1 for v in pillars.values() if v in ("PASS","PASS_BONUS"))

if applicable == 7:
    tier = 5 if passes >= 6 else (4 if passes >= 5 else (3 if passes >= 4 else 2))
else:
    tier = 5 if passes >= 6 else (4 if passes >= 4 else (3 if passes >= 3 else 2))

hard_fails = []
if p1_verdict == "FAIL": hard_fails.append("Pillar 1 Trend Template")
if g4_verdict == "FAIL": hard_fails.append("Gate 4 Catalyst")
if g6_verdict == "FAIL": hard_fails.append("Gate 6 Liquidity")
if g7_verdict == "FAIL": hard_fails.append("Gate 7 Earnings Blackout")
if hard_fails: tier = 0

stop_pct = {"low_vol":0.10,"normal":0.12,"elevated":0.15,"extreme":0.20,"crisis":0.20,"unknown":0.12}.get(regime, 0.12)
stop = round(close*(1-stop_pct), 2)
phase1 = round(close*1.50, 2)
runner = round(close*1.80, 2)
rr = round((phase1-close)/(close-stop), 2) if close > stop else None

name = (fundamentals.get("General", {}) or {}).get("Name", TICKER)

print(f"{'='*72}")
print(f"  {TICKER}  -  {name}")
print(f"  Tier {tier}   |   {passes}/{applicable} pillars")
print(f"{'='*72}")
print(f"\nTrade levels:")
print(f"  Entry    ${close:.2f}")
print(f"  Stop     ${stop:.2f}  ({stop_pct*100:.0f}%)")
print(f"  Phase 1  ${phase1:.2f}  (+50%)")
print(f"  Runner   ${runner:.2f}  (+80%)")
print(f"  R/R      {rr}")
print(f"\nPillars:")
print(f"  P1 Trend         {p1_verdict:12s}  {tt_passed}/7 template, stage {stage}")
print(f"  P2 Squeeze       {p2_verdict:12s}  squeeze pct {squeeze_pct:.0f}, break={upper_break}")
print(f"  P3 Growth        {p3_verdict:12s}  EPS YoY {(eps_g or 0)*100:+.1f}%, Rev YoY {(rev_g or 0)*100:+.1f}%, ROE {(roe or 0)*100:.0f}%")
print(f"  P4 RS            {p4_verdict:12s}  RS {rs:+.2f}% (stock {cret:+.2f} vs bench {bret:+.2f})")
print(f"  P5 Macro         {p5_verdict:12s}  VIX {vix:.1f} ({regime})" if vix else f"  P5 Macro         {p5_verdict:12s}  no vix data")
print(f"  P6 Revisions     {p6_verdict:12s}  beats={beats}, up30d={up30}, down30d={down30}")
print(f"  P7 Short Squeeze {p7_verdict:12s}  SI {si_pct*100:.1f}% ({si_level}), DTC {dtc:.1f}" if dtc else f"  P7 Short Squeeze {p7_verdict:12s}")
print(f"\nGates:")
print(f"  G3 RVOL       {g3_verdict:12s}  RVOL {rvol:.2f}x" if rvol else f"  G3 RVOL       {g3_verdict:12s}")
print(f"  G4 Catalyst   {g4_verdict:12s}  Tier {cat_tier}, beat={recent_beat}")
print(f"  G6 Liquidity  {g6_verdict:12s}  mcap ${mcap/1e9:.1f}B, $vol ${dvol/1e6:.1f}M, float {float_pct:.0f}%" if float_pct else f"  G6 Liquidity  {g6_verdict:12s}")
print(f"  G7 Earnings   {g7_verdict:12s}  next {next_e} ({days_until} days)" if next_e else f"  G7 Earnings   {g7_verdict:12s}")
print()
if hard_fails:
    print(f"NO TRADE - hard fails: {', '.join(hard_fails)}")
else:
    print(f"Tradeable per v3.1 spec")
```

## Explanation style

After running the script, explain every pillar and gate in plain English using the stock's actual numbers. For each:
- What the pillar/gate is checking
- This stock's numbers
- Whether it passed and why
- Any nuance (earnings within hold window, extended from base, low RVOL means wait for volume, etc.)

End with an honest verdict: genuine tradeable setup, watchlist only, or clear reject. For Tier 0 rejections, name the specific hard gate that failed and explain what that means.

## v3.1 spec reference (essentials)

- Tier 5: 6-7 pillars PASS (of 7 for US, 6 for LSE)
- Tier 4: 5 pillars (or 4 of 6 for LSE)
- Tier 3: 4 pillars (or 3 of 6 for LSE)
- Below threshold: watchlist only, no trade
- Hard gates (auto-reject): Pillar 1 FAIL, Gate 4 FAIL, Gate 6 FAIL, Gate 7 FAIL
- Stop widths by VIX regime: low vol 10%, normal 12%, elevated 15%, extreme 20%
- Targets: Phase 1 = +50% (sell 40%), Runner = +80% (trail remaining 60% with 15% trailing stop)
- Minimum R/R: 4:1
- LSE tickers: no options, no insider Form 4, Pillar 7 uses short interest only, scored out of 6 pillars

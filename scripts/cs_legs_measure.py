"""THE CREDIT SPREAD ON THE REAL INSTRUMENT, END TO END, WITH COVERAGE.
Legs asked for by name (data/cs_legs.db), so a week is only missing if the VENDOR has no quote. Mirrors the live rule:
first trading day of the week, short = round(spot x (1-a%)), long = round(spot x (1-b%)), sell the short at the BID, buy the
long at the ASK (closing NBBO), hold to the week's last trading day, cash-settle on the index close. BEAR stand-down as live.
Reads the frozen data/cs_legs.db (built by scripts/cs_legs_pull.py, deleted 2026-09-21 when Unusual Whales ended); run on demand: `./.venv/bin/python scripts/cs_legs_measure.py`."""
import math, os, sqlite3, warnings
from math import erf, log, sqrt, lgamma, exp
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
px = yf.download(["^XSP", "^GSPC", "SPY", "^VIX"], start="1990-01-01", auto_adjust=False, progress=False)["Close"]
SPOT = {"XSP": px["^XSP"].dropna(), "SPY": px["SPY"].dropna()}
spy, vix, spx = px["SPY"].dropna(), px["^VIX"].dropna(), px["^GSPC"].dropna()
db = sqlite3.connect("file:data/cs_legs.db?mode=ro", uri=True)
Q = {(o, d): (b, a) for o, d, b, a in db.execute("select occ, day, bid, ask from legs")}
asked = db.execute("select count(*), sum(n=0), max(expiry) from asked").fetchone()
print(f"legs db: {len(Q):,} contract-days; contracts asked {asked[0]:,}, vendor returned nothing for {asked[1] or 0}")
sma50 = spy.rolling(50).mean().shift(1); prev = spy.shift(1)
BEAR = ((prev / sma50 - 1) * 100 < -2)
weeks = {}
for d in spy.index:
    if d >= pd.Timestamp("2023-10-23") and d in SPOT["XSP"].index:
        weeks.setdefault(d.isocalendar()[:2], []).append(d)
WK = [(ds[0], ds[-1]) for _, ds in sorted(weeks.items()) if len(ds) >= 3 and ds[-1] <= pd.Timestamp(asked[2])]


def tstat(v):
    v = np.asarray(v, float); return v.mean() / (v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 2 and v.std() > 0 else 0.0


def cp_upper(k, n, a=0.05):
    def bcdf(x, p, q):
        N = 3000; s = sum(((i + 0.5) / N * x) ** (p - 1) * (1 - (i + 0.5) / N * x) ** (q - 1) for i in range(N)) * x / N
        return s / exp(lgamma(p) + lgamma(q) - lgamma(p + q))
    lo, hi = k / n, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if (1 - bcdf(mid, k + 1, n - k) if n - k > 0 else 1.0) > a: lo = mid
        else: hi = mid
    return hi


def run(root, a, b, gate=True):
    rows = []
    for ent, ex in WK:
        spot = float(SPOT[root].loc[ent]); ks, kl = round(spot * (1 - a / 100)), round(spot * (1 - b / 100))
        e, x = ent.strftime("%Y-%m-%d"), ex.strftime("%y%m%d")
        sb = (Q.get((f"{root}{x}P{int(ks * 1000):08d}", e)) or (None, None))
        lg = (Q.get((f"{root}{x}P{int(kl * 1000):08d}", e)) or (None, None))
        usable = sb[0] is not None and lg[1] is not None and sb[0] > 0.02 and lg[1] > 0 and ks > kl
        rec = dict(ent=ent, usable=usable, bear=bool(BEAR.get(ent, False)), vix=float(vix.get(ent, np.nan)))
        if usable:
            S = float(SPOT[root].loc[ex]); cr = sb[0] - lg[1]
            mid = ((sb[0] + (sb[1] or sb[0])) / 2) - (((lg[0] or 0) + lg[1]) / 2)
            rec.update(credit=cr * 100, mid=mid * 100, width=(ks - kl) * 100, T=(ex - ent).days / 365.0,
                       pnl=(cr - max(ks - S, 0) + max(kl - S, 0)) * 100, a=a, b=b)
        rows.append(rec)
    return pd.DataFrame(rows)


def line(label, df, gate):
    u = df[df.usable]; t = u[~u.bear] if gate else u
    v = t.pnl.values; eq = v.cumsum(); k = int((v < 0).sum()); n = len(v)
    ub = cp_upper(k, n); mw = v[v > 0].mean() if (v > 0).any() else 0; ml = v[v < 0].mean() if k else 0; mx = (t.width - t.credit).mean()
    h = n // 2
    print(f"  {label:<30}{len(df):>5}{len(u):>7}{len(u) / len(df):>8.0%}{n:>7}{(v > 0).mean():>7.0%}{v.mean():>+8.1f}{v.sum():>+8.0f}{tstat(v):>+6.2f}"
          f"{v[:h].mean():>+8.0f}/{v[h:].mean():<+6.0f}{v.min():>+8.0f}{(eq - np.maximum.accumulate(eq)).min():>+8.0f}{t.credit.mean():>8.0f}{mx:>8.0f}"
          f"{(t.credit <= 0).mean():>7.0%}{ub:>7.0%}{(1 - ub) * mw + ub * ml:>+8.1f}{(1 - ub) * mw - ub * mx:>+8.1f}")


HDR = (f"  {'':<30}{'weeks':>5}{'usable':>7}{'cover':>8}{'traded':>7}{'win%':>7}{'$/wk':>8}{'total':>8}{'t':>6}{'halves $/wk':>15}{'worst':>8}{'maxDD':>8}"
       f"{'credit':>8}{'maxloss':>8}{'cr<=0':>7}{'ub loss':>7}{'EV@ub':>8}{'EV@max':>8}")
STRUCT = [("2%/4%  THE LIVE RULE", 2.0, 4.0), ("2%/3%  fits the $1,000 cap", 2.0, 3.0), ("2.5%/4.5%", 2.5, 4.5), ("3%/5%", 3.0, 5.0), ("3%/4%  fits the cap", 3.0, 4.0), ("4%/6%", 4.0, 6.0)]
for root in ("XSP", "SPY"):
    print(f"\n{'=' * 150}\n{root}: REAL QUOTES, REAL SETTLEMENT, {WK[0][0].date()} .. {WK[-1][1].date()}  ({'the instrument the book trades' if root == 'XSP' else 'the proxy every earlier backtest used'})")
    for gate in (True, False):
        print(f" {'WITH the BEAR stand-down (as live)' if gate else 'NO gate'}"); print(HDR)
        for name, a, b in STRUCT:
            line(name, run(root, a, b), gate)
print("\n  cover = weeks where the vendor has a closing quote for BOTH exact strikes on the entry day.  cr<=0 = weeks the executable credit was zero or negative (the live rule still enters).")
print("  ub loss = 95% upper bound on the losing-week rate;  EV@ub = expectancy at that rate with losses at their realised size;  EV@max = with every loss at maximum.")

print(f"\n{'=' * 150}\nXSP vs SPY, SAME WEEKS, SAME RULE (2%/4%): what the instrument costs")
x, s = run("XSP", 2.0, 4.0), run("SPY", 2.0, 4.0)
m = x.usable & s.usable
fx, fs = (x.mid - x.credit)[m], (s.mid - s.credit)[m]
print(f"  paired weeks {int(m.sum())}:  executable credit XSP ${x.credit[m].mean():.0f} vs SPY ${s.credit[m].mean():.0f};  friction (mid minus executable) XSP ${fx.mean():.1f} vs SPY ${fs.mean():.1f}")
d = (fx - fs)
print(f"  EXCESS FRICTION on XSP: mean ${d.mean():.1f}, median ${d.median():.1f} per spread, t {tstat(d.values):.1f};  P&L XSP ${x.pnl[m].mean():+.1f}/wk vs SPY ${s.pnl[m].mean():+.1f}/wk")
print(f"  pre-registered rule (scripts/xsp_quote_log.py): <= $5 transfers, $5-20 haircut, >= $20 edge consumed.  NOTE these are CLOSING quotes; the logger measures the 15:05 UTC entry window.")

# ---------------------------------------------------------------- recalibrate the 35-year model on the FULL volatility range
def _N(z): return 0.5 * (1 + erf(z / sqrt(2)))
def _put(S, K, sig, T):
    if sig <= 0 or T <= 0: return max(K - S, 0.0)
    d1 = (log(S / K) + 0.5 * sig * sig * T) / (sig * sqrt(T)); return K * _N(-(d1 - sig * sqrt(T))) - S * _N(-d1)
def frac(v, a, b, T, ms, ml, fr): return (_put(100, 100 - a, v / 100 * ms, T) - _put(100, 100 - b, v / 100 * ml, T)) / (b - a) + fr
wk35 = {}
for dd in spx.index:
    if dd in vix.index: wk35.setdefault(dd.isocalendar()[:2], []).append(dd)
s50 = spx.rolling(50).mean().shift(1); pv = spx.shift(1)
W = pd.DataFrame([(ds[0], float(spx.loc[ds[-1]] / spx.loc[ds[0]] - 1) * 100, float(vix.loc[ds[0]]), bool((pv.loc[ds[0]] / s50.loc[ds[0]] - 1) * 100 < -2))
                  for _, ds in sorted(wk35.items()) if len(ds) >= 3 and not np.isnan(s50.loc[ds[0]])], columns=["ent", "ret", "vix", "bear"]).set_index("ent")
print(f"\n{'=' * 150}\n35 YEARS ({W.index[0].date()} .. {W.index[-1].date()}, {len(W)} weeks), credits from a curve fitted to the REAL XSP credits above - now including the high-volatility weeks")
print(f"  {'structure':<28}{'fit weeks':>10}{'VIX range':>11}{'fit R2':>8}{'traded':>8}{'win%':>7}{'$/wk':>8}{'t':>7}{'yrs +':>8}{'worst yr':>10}{'maxDD':>9}{'$/wk @0.8x':>12}{'$/wk @0.7x':>12}")
for name, a, b in STRUCT[:5]:
    u = run("XSP", a, b); u = u[u.usable & u.vix.notna()]
    v_, f_, t_ = u.vix.values, (u.credit / u.width).values, u["T"].values
    best = None
    for ms in np.arange(0.7, 2.01, 0.05):
        for ml in np.arange(0.7, 2.61, 0.05):
            p = np.array([frac(vv, a, b, ti, ms, ml, 0.0) for vv, ti in zip(v_, t_)]); fr = float(np.mean(f_ - p)); e = float(np.mean((f_ - p - fr) ** 2))
            if best is None or e < best[0]: best = (e, ms, ml, fr)
    _, ms, ml, fr = best
    p = np.array([frac(vv, a, b, ti, ms, ml, fr) for vv, ti in zip(v_, t_)]); r2 = 1 - np.sum((f_ - p) ** 2) / np.sum((f_ - f_.mean()) ** 2)
    g = W[~W.bear]; width = 765.0 * (b - a)
    out = {}
    for mult in (1.0, 0.8, 0.7):
        cr = np.clip(np.array([frac(vv, a, b, 4 / 365.0, ms, ml, fr) for vv in g.vix]) * mult, 0, 0.9)
        out[mult] = pd.Series((cr - np.clip((-g.ret.values - a) / (b - a), 0, 1)) * width, index=g.index)
    usd = out[1.0]; eq = usd.cumsum(); ann = usd.groupby(usd.index.year).sum()
    print(f"  {name:<28}{len(u):>10}{f'{v_.min():.0f}-{v_.max():.0f}':>11}{r2:>8.2f}{len(usd):>8}{(usd > 0).mean():>7.0%}{usd.mean():>+8.1f}{tstat(usd.values):>+7.2f}"
          f"{f'{int((ann > 0).sum())}/{len(ann)}':>8}{ann.min():>+10.0f}{(eq - eq.cummax()).min():>+9.0f}{out[0.8].mean():>+12.1f}{out[0.7].mean():>+12.1f}")

import json, math, os
from collections import defaultdict
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
rows = []
for l in open("reports/research/spread_trail_v1.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if "_meta" in r:
        META = r; continue
    rows.append(r)
ARMS = ["single", "hold", "buyback50", "roll50", "buyback100", "roll100"]
NICE = {"single": "buy one option outright", "hold": "spread, held as is",
        "buyback50": "close the short at +50%", "roll50": "roll the short out at +50%",
        "buyback100": "close the short at +100%", "roll100": "roll the short out at +100%"}
print(f"trades {len(rows):,} | days {len(set(r['day'] for r in rows))} | triggers {META['triggers']}")


def ts(x):
    n = len(x)
    if n < 3: return 0.0
    m = sum(x) / n; sd = (sum((v - m) ** 2 for v in x) / (n - 1)) ** 0.5
    return (m / (sd / math.sqrt(n))) if sd > 0 else 0.0


def usd(r, arm):
    v = r.get(arm)
    return None if v is None else r["debit0"] * 100 * v / 100.0


print(f"\n=== EVERY ARM, all trades (dollars per trade, 1 contract) ===")
print(f"  {'arm':<30}{'n':>7}{'$/trade':>10}{'mean %':>9}{'win':>7}{'t (day means)':>15}{'halves':>18}")
base = None
for a in ARMS:
    sel = [r for r in rows if r.get(a) is not None]
    if len(sel) < 200: print(f"  {NICE[a]:<30}{len(sel):>7}  thin"); continue
    d = defaultdict(list)
    for r in sel: d[r["day"]].append(r[a])
    days = sorted(d); v = [sum(d[k]) / len(d[k]) for k in days]; h = len(v) // 2
    dollars = sum(usd(r, a) for r in sel) / len(sel)
    print(f"  {NICE[a]:<30}{len(sel):>7}{dollars:>+10,.0f}{sum(v)/len(v):>+9.2f}"
          f"{sum(1 for r in sel if r[a] > 0)/len(sel):>7.0%}{ts(v):>+15.2f}"
          f"{sum(v[:h])/max(1,h):>+9.1f}/{sum(v[h:])/max(1,len(v)-h):>+8.1f}")
print("\n=== PAIRED against holding the spread (same trade, both ways) ===")
for a in ARMS:
    if a == "hold": continue
    d = defaultdict(list)
    for r in rows:
        if r.get(a) is not None and r.get("hold") is not None:
            d[r["day"]].append(usd(r, a) - usd(r, "hold"))
    if len(d) < 60: continue
    days = sorted(d); v = [sum(d[k]) / len(d[k]) for k in days]; h = len(v) // 2
    n = sum(len(x) for x in d.values())
    print(f"  {NICE[a]:<30} n {n:>6}  {sum(v)/len(v):>+7.2f} $/trade vs holding  t {ts(v):>+6.2f}  "
          f"halves {sum(v[:h])/max(1,h):>+7.2f}/{sum(v[h:])/max(1,len(v)-h):>+6.2f}")
print("\n=== HOW OFTEN DOES THE TRAIL EVEN FIRE, and what happens when it does ===")
for a in ("buyback50", "roll50", "buyback100", "roll100"):
    fired = [r for r in rows if r.get(a + "_fired")]
    if not fired: continue
    both = [r for r in fired if r.get("hold") is not None and r.get(a) is not None]
    dd = [usd(r, a) - usd(r, "hold") for r in both]
    print(f"  {NICE[a]:<30} fired on {len(fired)/len(rows):>5.1%} of trades ({len(fired):,})   "
          f"when it fires: {sum(dd)/max(1,len(dd)):>+7.0f} $/trade vs holding")
print("\n=== THE TAIL: trades where holding the spread made 100%+ ===")
big = [r for r in rows if (r.get("hold") or -99) >= 100]
print(f"  {len(big):,} trades")
for a in ARMS:
    sel = [r for r in big if r.get(a) is not None]
    if not sel: continue
    print(f"    {NICE[a]:<30} ${sum(usd(r,a) for r in sel)/len(sel):>+8,.0f}/trade   mean {sum(r[a] for r in sel)/len(sel):>+8.1f}%")
print("\n=== AND THE COST: trades that triggered the trail then went on to LOSE ===")
for a in ("buyback50", "roll50"):
    fired = [r for r in rows if r.get(a + "_fired") and r.get(a) is not None and r.get("hold") is not None]
    bad = [r for r in fired if r[a] < r["hold"]]
    if not fired: continue
    print(f"  {NICE[a]:<30} of {len(fired):,} that fired, {len(bad)/len(fired):>5.1%} ended WORSE than holding, "
          f"costing {sum(usd(r,a)-usd(r,'hold') for r in bad)/max(1,len(bad)):>+7.0f} $ each")

import json, math, os
from collections import defaultdict
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
rows=[]
for l in open("reports/research/entry_timing_v1.jsonl",encoding="utf-8"):
    r=json.loads(l)
    if "_meta" in r: continue
    rows.append(r)
def tstat(x):
    n=len(x)
    if n<3: return 0.0
    m=sum(x)/n; sd=(sum((v-m)**2 for v in x)/(n-1))**0.5
    return (m/(sd/math.sqrt(n))) if sd>0 else 0.0
def dm(sel,key):
    d=defaultdict(list)
    for r in sel:
        v=r.get(key)
        if v is not None: d[r["day"]].append(v)
    return d
def show(label, sel, key):
    d=dm(sel,key); days=sorted(d)
    if len(days)<30: print(f"  {label:<46} thin"); return None
    v=[sum(d[k])/len(d[k]) for k in days]; n=sum(len(x) for x in d.values()); h=len(v)//2
    m=sum(v)/len(v)
    print(f"  {label:<46} days {len(days):>3} n {n:>5}  mean {m:+7.2f}%/day  t {tstat(v):+6.2f}  halves {sum(v[:h])/max(1,h):+7.1f}/{sum(v[h:])/max(1,len(v)-h):+7.1f}")
    return m
CELL=[r for r in rows if r.get("side")=="C" and r.get("at_print") and 0.30<=r["at_print"]<=9.90]
COV=[r for r in CELL if r.get("at_print_hourly") is not None and r.get("at_print_daily") is not None]
UNC=[r for r in CELL if r.get("at_print_hourly") is None and r.get("at_print_daily") is not None]
print(f"CELL: calls, at_print $0.30-9.90 | rows {len(CELL):,} | both clocks {len(COV):,} | daily only {len(UNC):,}")
print("\n=== A. THE SELECTION TEST: does hourly bar coverage pick winners? (DAILY clock, available to all) ===")
a=show("covered rows, daily clock", COV, "at_print_daily")
b=show("UNcovered rows, daily clock", UNC, "at_print_daily")
c=show("whole cell, daily clock", CELL, "at_print_daily")
if a is not None and b is not None:
    d=defaultdict(list)
    for r in COV: d[r["day"]].append(("cov", r["at_print_daily"]))
    for r in UNC: d[r["day"]].append(("unc", r["at_print_daily"]))
    diffs=[]
    for k,v in d.items():
        cv=[x for t,x in v if t=="cov"]; uv=[x for t,x in v if t=="unc"]
        if cv and uv: diffs.append(sum(cv)/len(cv)-sum(uv)/len(uv))
    print(f"  PAIRED same-day (covered minus uncovered), daily clock: {sum(diffs)/len(diffs):+7.2f} pts/day  t {tstat(diffs):+6.2f}  days {len(diffs)}")
print("\n=== B. THE CLOCK EFFECT on rows where both exist ===")
show("both-clocks rows, DAILY", COV, "at_print_daily")
show("both-clocks rows, HOURLY", COV, "at_print_hourly")
d=defaultdict(list)
for r in COV: d[r["day"]].append(r["at_print_hourly"]-r["at_print_daily"])
days=sorted(d); v=[sum(d[k])/len(d[k]) for k in days]; h=len(v)//2
print(f"  PAIRED hourly-minus-daily: {sum(v)/len(v):+7.2f} pts/day  t {tstat(v):+6.2f}  halves {sum(v[:h])/max(1,h):+7.1f}/{sum(v[h:])/max(1,len(v)-h):+7.1f}")
print("\n=== C. WHAT the headline number actually was, and the honest version ===")
show("headline: hourly on covered rows only", COV, "at_print_hourly")
print("\n=== D. what differs between covered and uncovered rows ===")
for lab,f in (("mean ask", lambda r: r["at_print"]), ("mean dte", lambda r: r.get("dte") or 0)):
    cv=[f(r) for r in COV]; uv=[f(r) for r in UNC]
    print(f"  {lab:<12} covered {sum(cv)/max(1,len(cv)):8.2f}   uncovered {sum(uv)/max(1,len(uv)):8.2f}")
from collections import Counter
print("  top uncovered tickers:", Counter("".join(ch for ch in r["occ"][:6] if ch.isalpha()) for r in UNC).most_common(6))
print("  top covered tickers:  ", Counter("".join(ch for ch in r["occ"][:6] if ch.isalpha()) for r in COV).most_common(6))
print("\n=== E. same test on the at_close arm (does the conclusion hold for the other entry?) ===")
COV2=[r for r in CELL if r.get("at_close_hourly") is not None and r.get("at_close_daily") is not None]
show("both-clocks rows, at_close DAILY", COV2, "at_close_daily")
show("both-clocks rows, at_close HOURLY", COV2, "at_close_hourly")

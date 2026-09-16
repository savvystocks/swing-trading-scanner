import json, math, os
from collections import defaultdict
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
rows=[json.loads(l) for l in open("reports/research/probe_tuner_rows_v3.jsonl",encoding="utf-8")]
rows=[r for r in rows if r.get("basis")=="ask_at_qualifying_print" and r["rets"] and r["rets"][0] is not None]
def ts(x):
    n=len(x)
    if n<3: return 0.0
    m=sum(x)/n; sd=(sum((v-m)**2 for v in x)/(n-1))**0.5
    return (m/(sd/math.sqrt(n))) if sd>0 else 0.0
EXITS=[(-50,50,.2),(-50,80,.3),(-50,80,.2),(-50,50,.3),(-70,50,.2),(-70,80,.3),(-70,80,.2),(-70,50,.3)]
pool={}
for ei in (0,5):
    d=defaultdict(list)
    for r in rows: d[r["day"]].append(r["rets"][ei])
    pool[ei]={k:sum(v)/len(v) for k,v in d.items()}
C=lambda r: r["side"]=="C"
CELLS={"BULL_DIP":(lambda r: C(r) and r["reg"]>2 and r["smd"]<0,0),
       "DIP_CONF_MILD":(lambda r: C(r) and -2<=r["reg"]<=2 and r["smd"]<0 and r["sp"]<0,0),
       "DIP_CONVEXITY":(lambda r: C(r) and r["reg"]<0 and r["sp"]<0,5),
       "FOLLOW_CALLS":(C,0),
       "WINNER_PROFILE":(lambda r: r["prem"]>73200,0),
       "POOL":(lambda r: True,0)}
SPR=lambda r: (r.get("spread_frac") or 0)<=0.03
def line(name,pred,ei,lo,hi):
    d=defaultdict(list)
    for r in rows:
        if pred(r) and SPR(r) and lo<=r["ask"]<hi: d[r["day"]].append(r["rets"][ei])
    days=sorted(d)
    if len(days)<40: return f"  {name:<16} ${lo}-{hi:<5} thin ({len(days)}d)"
    v=[sum(d[k])/len(d[k]) for k in days]; n=sum(len(x) for x in d.values()); h=len(v)//2
    diff=[sum(d[k])/len(d[k])-pool[ei][k] for k in days]
    h1=sum(v[:h])/max(1,h); h2=sum(v[h:])/max(1,len(v)-h)
    ok="BOTH+" if (h1>0 and h2>0) else ("one+" if (h1>0 or h2>0) else "both-")
    return (f"  {name:<16} ${lo}-{hi:<5} days {len(days):>3} n {n:>5} ({n/len(days):4.1f}/d) own {sum(v)/len(v):+7.2f} "
            f"vs pool {sum(diff)/len(diff):+6.2f} t {ts(diff):+5.2f}  halves {h1:+7.1f}/{h2:+7.1f} {ok}")
print("=== THE $1,600 BAND ($9.90-16) vs TODAY'S BAND ($4-9.90), v3 live basis, spread<=3% ===")
for name,(pred,ei) in CELLS.items():
    print(f"-- {name} (exit {EXITS[ei]}) --")
    for lo,hi in ((4,9.9),(9.9,16),(16,25)):
        print(line(name,pred,ei,lo,hi))
print("\n=== ONE CONTRACT AT $1,600 vs 1 or 2 CONTRACTS AT $1,000: what the slot actually buys ===")
for lo,hi,lab in ((0.30,9.9,"$1,000 slot: ask 0.30-9.90"),(0.30,16,"$1,600 slot: ask 0.30-16.00")):
    for name,(pred,ei) in (("FOLLOW_CALLS",CELLS["FOLLOW_CALLS"]),("BULL_DIP",CELLS["BULL_DIP"]),("POOL",CELLS["POOL"])):
        print(f"  {lab:<28}", line(name,pred,ei,lo,hi).strip())

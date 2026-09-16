import json, math, os
from collections import defaultdict
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
# regime context per (occ, day) from the court's corpus
ctx={}
for l in open("reports/research/probe_tuner_rows_v3.jsonl",encoding="utf-8"):
    r=json.loads(l)
    if r.get("basis")!="ask_at_qualifying_print": continue
    ctx[(r["occ"],r["day"])]=(r["side"],r["reg"],r["smd"],r["sp"],r["prem"],r["ask"])
print(f"context rows {len(ctx):,}")
S={}; P={}
for l in open("reports/research/spread_access_v1.jsonl",encoding="utf-8"):
    r=json.loads(l)
    if "_meta" in r or r.get("ret") is None or r["budget"]!=1000.0: continue
    (S if r["arm"]=="single" else P)[(r["occ"],r["day"])]=r
keys=[k for k in S if k in P and k in ctx]
print(f"paired single+spread WITH court context: {len(keys):,}")
def ts(x):
    n=len(x)
    if n<3: return 0.0
    m=sum(x)/n; sd=(sum((v-m)**2 for v in x)/(n-1))**0.5
    return (m/(sd/math.sqrt(n))) if sd>0 else 0.0
C=lambda c: c[0]=="C"
CELLS={"BULL_DIP": lambda c: C(c) and c[1]>2 and c[2]<0,
       "DIP_CONF_MILD": lambda c: C(c) and -2<=c[1]<=2 and c[2]<0 and c[3]<0,
       "DIP_CONVEXITY": lambda c: C(c) and c[1]<0 and c[3]<0,
       "FOLLOW_CALLS": lambda c: C(c),
       "WINNER_PROFILE": lambda c: c[4]>73200,
       "POOL": lambda c: True}
print("\n=== SPREAD vs SINGLE INSIDE EACH STRATEGY CELL (budget $1,000, paired, close-to-close basis) ===")
print(f"  {'cell':<16} {'n':>6} {'single':>9} {'spread':>9} {'diff':>8} {'t':>7}  {'halves of the diff':>20}  {'sprd halves':>16}")
for name,f in CELLS.items():
    sel=[k for k in keys if f(ctx[k])]
    if len(sel)<200: print(f"  {name:<16} {len(sel):>6}  thin"); continue
    ds=defaultdict(list); dp=defaultdict(list); dd=defaultdict(list)
    for k in sel:
        d=S[k]["day"]; ds[d].append(S[k]["ret"]); dp[d].append(P[k]["ret"]); dd[d].append(P[k]["ret"]-S[k]["ret"])
    days=sorted(dd)
    vs=[sum(ds[d])/len(ds[d]) for d in days]; vp=[sum(dp[d])/len(dp[d]) for d in days]; vd=[sum(dd[d])/len(dd[d]) for d in days]
    h=len(vd)//2
    ph1=sum(vp[:h])/max(1,h); ph2=sum(vp[h:])/max(1,len(vp)-h)
    print(f"  {name:<16} {len(sel):>6} {sum(vs)/len(vs):>+8.2f} {sum(vp)/len(vp):>+8.2f} {sum(vd)/len(vd):>+7.2f} {ts(vd):>+7.2f}  "
          f"{sum(vd[:h])/max(1,h):>+8.1f}/{sum(vd[h:])/max(1,len(vd)-h):>+7.1f}  {ph1:>+7.1f}/{ph2:>+6.1f} {'BOTH+' if ph1>0 and ph2>0 else ''}")
print("\n=== and with a PRICE FLOOR on the long leg (the $1,600 finding, applied here) ===")
for lo,hi,lab in ((0.30,9.9,"no floor $0.30-9.90"),(6.0,9.9,"floor $6"),(9.9,16.0,"floor $9.90 (needs $1,600)")):
    for name in ("BULL_DIP","FOLLOW_CALLS","POOL"):
        f=CELLS[name]
        sel=[k for k in keys if f(ctx[k]) and lo<=ctx[k][5]<hi]
        if len(sel)<150: continue
        dp=defaultdict(list); dd=defaultdict(list)
        for k in sel:
            d=S[k]["day"]; dp[d].append(P[k]["ret"]); dd[d].append(P[k]["ret"]-S[k]["ret"])
        days=sorted(dp); vp=[sum(dp[d])/len(dp[d]) for d in days]; vd=[sum(dd[d])/len(dd[d]) for d in days]; h=len(vp)//2
        h1=sum(vp[:h])/max(1,h); h2=sum(vp[h:])/max(1,len(vp)-h)
        print(f"  {lab:<28} {name:<14} n {len(sel):>5}  spread {sum(vp)/len(vp):+7.2f}/day t {ts(vp):+6.2f}  halves {h1:+7.1f}/{h2:+6.1f} {'BOTH+' if h1>0 and h2>0 else ''}")

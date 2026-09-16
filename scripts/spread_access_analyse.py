import json, math, os
from collections import defaultdict
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
rows=[]
for l in open("reports/research/spread_access_v1.jsonl",encoding="utf-8"):
    r=json.loads(l)
    if "_meta" in r: META=r; continue
    if r.get("ret") is not None: rows.append(r)
print(f"rows {len(rows):,} | days {len(set(r['day'] for r in rows))} | basis {META['basis']}")
def ts(x):
    n=len(x)
    if n<3: return 0.0
    m=sum(x)/n; sd=(sum((v-m)**2 for v in x)/(n-1))**0.5
    return (m/(sd/math.sqrt(n))) if sd>0 else 0.0
def cell(label, sel):
    if len(sel)<200: print(f"  {label:<44} thin ({len(sel)})"); return
    d=defaultdict(list)
    for r in sel: d[r["day"]].append(r["ret"])
    days=sorted(d); v=[sum(d[k])/len(d[k]) for k in days]; n=len(sel); h=len(v)//2
    sp=sorted(r["ret"] for r in sel)
    nobest=(sum(sp)-sp[-1])/(n-1); no3=(sum(sp)-sum(sp[-3:]))/(n-3)
    h1=sum(v[:h])/max(1,h); h2=sum(v[h:])/max(1,len(v)-h)
    print(f"  {label:<44} days {len(days):>3} n {n:>6} own {sum(v)/len(v):+7.2f}/day t {ts(v):+6.2f} "
          f"best-rm {nobest:+7.2f} top3-rm {no3:+7.2f} win {sum(1 for x in sp if x>0)/n:.0%} "
          f"halves {h1:+7.1f}/{h2:+7.1f} {'BOTH+' if h1>0 and h2>0 else ''}")
for B in (1000.0,1600.0,2500.0):
    print(f"\n=== BUDGET ${B:.0f} ===")
    sing=[r for r in rows if r["budget"]==B and r["arm"]=="single"]
    spr=[r for r in rows if r["budget"]==B and r["arm"]=="spread"]
    cell("SINGLE (outright, affordable at this budget)", sing)
    cell("SPREAD (long + short, net debit in budget)", spr)
    # paired: same occ+day where both arms exist
    sk={(r["occ"],r["day"]):r for r in sing}; pk={(r["occ"],r["day"]):r for r in spr}
    both=[(sk[k],pk[k]) for k in sk if k in pk]
    if len(both)>200:
        d=defaultdict(list)
        for a,b in both: d[a["day"]].append(b["ret"]-a["ret"])
        days=sorted(d); v=[sum(d[k])/len(d[k]) for k in days]; h=len(v)//2
        print(f"  PAIRED spread-minus-single (same contract-day, n={len(both)}): {sum(v)/len(v):+6.2f} pts/day t {ts(v):+5.2f} halves {sum(v[:h])/max(1,h):+6.1f}/{sum(v[h:])/max(1,len(v)-h):+6.1f}")
    # what the spread unlocks: long legs too expensive to buy outright
    unl=[r for r in spr if r["long_ask"]*100>B]
    cell(f"  SPREAD on legs UNAFFORDABLE outright (>{B:.0f})", unl)
    if unl:
        print(f"     those legs' ask: median ${sorted(r['long_ask'] for r in unl)[len(unl)//2]:.2f}  median width ${sorted(r['width'] for r in unl if r.get('width'))[len(unl)//2]:.1f}  median debit ${sorted(r['debit'] for r in unl)[len(unl)//2]*100:.0f}")
print("\n=== DOES THE SPREAD CAP THE TAIL? (budget 1000, paired rows) ===")
sing={ (r["occ"],r["day"]):r for r in rows if r["budget"]==1000.0 and r["arm"]=="single"}
spr={ (r["occ"],r["day"]):r for r in rows if r["budget"]==1000.0 and r["arm"]=="spread"}
both=[(sing[k],spr[k]) for k in sing if k in spr]
if both:
    big=[(a,b) for a,b in both if a["ret"]>=100]
    print(f"  single trades that returned >= +100%: {len(big)} of {len(both)}")
    if big:
        print(f"    their mean as SINGLE {sum(a['ret'] for a,b in big)/len(big):+8.1f}%   as SPREAD {sum(b['ret'] for a,b in big)/len(big):+8.1f}%")
    los=[(a,b) for a,b in both if a["ret"]<=-50]
    print(f"  single trades that hit the stop: {len(los)} of {len(both)}")
    if los:
        print(f"    their mean as SINGLE {sum(a['ret'] for a,b in los)/len(los):+8.1f}%   as SPREAD {sum(b['ret'] for a,b in los)/len(los):+8.1f}%")

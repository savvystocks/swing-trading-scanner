"""Is STUDENT_A's executed-slice result an edge or a handful of outliers? Read-only."""
import json, os, sys, math
from collections import defaultdict
from datetime import date
REPO=os.path.expanduser("~/swing-trading-scanner"); os.chdir(REPO)
sys.path.insert(0,REPO); sys.path.insert(0,os.path.join(REPO,"scripts"))
import numpy as np
from src import student_features as sfx
import student_formula_sim as sf
from student_export import cohort_mask, ASOF, EXIT_IDX
os.environ["FEATURE_SET"]="ASOF"
spec=json.load(open("fade_book_spec.json",encoding="utf-8"))
stu=(spec.get("probe") or {}).get("student") or {}
cfg=(stu.get("probes") or {}).get("STUDENT_A") or {}
rows=[json.loads(l) for l in open(ASOF,encoding="utf-8")]
X=np.array([r["vec"] for r in rows],float); days=[r["day"] for r in rows]
ei=EXIT_IDX.get(cfg.get("exit_label","BASE"),0)
rets=np.array([r["rets"][ei] if r["rets"][ei] is not None else np.nan for r in rows])
cm=cohort_mask(rows,cfg.get("cohort","ALL")) & ~np.isnan(rets)
y_cls=(rets>0).astype(int); y_big=(rets>=30).astype(int); y_reg=np.clip(np.nan_to_num(rets,nan=0.0),-100,300)
print("rebuilding A's walk-forward stream...",flush=True)
oos=sf.fit_stream(X,y_cls,y_big,y_reg,days,cfg.get("target","EXPRET"),cm)
have=cm & ~np.isnan(oos) & cohort_mask(rows,cfg.get("threshold_cohort") or cfg.get("cohort","ALL"))
thr=json.load(open(cfg["model"],encoding="utf-8"))["thresholds"]
cap=float(cfg.get("exec_max_ask", stu.get("exec_max_ask",10.0))); k=int(cfg.get("k_per_week",3))
def wk(d): return date.fromisoformat(d).isocalendar()[:2]
def picks(bar):
    idx=[i for i in np.argsort(np.array(days)) if have[i] and not np.isnan(oos[i]) and oos[i]>=bar]
    byd=defaultdict(list)
    for i in idx: byd[days[i]].append(i)
    out=[]; c=defaultdict(int)
    for d in sorted(byd):
        for i in sorted(byd[d],key=lambda j:-oos[j]):
            if c[wk(d)]>=k: break
            c[wk(d)]+=1; out.append(i)
    return out
def tstat(x):
    n=len(x)
    if n<3: return 0.0
    m=sum(x)/n; sd=(sum((v-m)**2 for v in x)/(n-1))**0.5
    return (m/(sd/math.sqrt(n))) if sd>0 else 0.0
for lab,bar in (("loose k3 (LIVE)",thr["k3"]),("middle k2",thr["k2"]),("strict k1",thr["k1"])):
    pk=[i for i in picks(bar) if rows[i]["entry"]<=cap]
    if not pk: print(f"{lab}: no executed picks"); continue
    pct=sorted((rows[i]["rets"][ei] or 0.0) for i in pk)
    n=len(pct); mean=sum(pct)/n
    nobest=(sum(pct)-pct[-1])/(n-1) if n>1 else 0.0
    no3=(sum(pct)-sum(pct[-3:]))/(n-3) if n>3 else 0.0
    wkusd=defaultdict(float)
    for i in pk:
        r=rows[i]; p=r["rets"][ei] or 0.0
        wkusd[wk(r["day"])]+= max(1,int(1000.0//(r["entry"]*100)))*p/100.0*r["entry"]*100.0
    w=[wkusd[x] for x in sorted(wkusd)]
    print(f"\n{lab}: {n} executed trades over {len(w)} weeks")
    print(f"  mean/trade {mean:+7.1f}%   BEST REMOVED {nobest:+7.1f}%   TOP-3 REMOVED {no3:+7.1f}%   win {sum(1 for x in pct if x>0)/n:.1%}")
    print(f"  median {pct[n//2]:+6.1f}%  p25 {pct[n//4]:+6.1f}%  p75 {pct[3*n//4]:+6.1f}%  best {pct[-1]:+7.1f}%  worst {pct[0]:+7.1f}%")
    print(f"  trades >= +100%: {sum(1 for x in pct if x>=100)}  >= +50%: {sum(1 for x in pct if x>=50)}  at the -50 stop: {sum(1 for x in pct if x<=-50)}")
    print(f"  weekly $ mean {sum(w)/len(w):+8.0f}  t {tstat(w):+5.2f}  positive weeks {sum(1 for x in w if x>0)/len(w):.0%}")
    h=len(w)//2
    print(f"  weekly $ halves {sum(w[:h])/max(1,h):+8.0f} / {sum(w[h:])/max(1,len(w)-h):+8.0f}   share of total from the best week {max(w)/max(1,sum(x for x in w if x>0)):.0%}")

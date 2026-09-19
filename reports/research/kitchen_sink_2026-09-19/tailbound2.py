import json, glob, os, math
from math import lgamma, exp
os.chdir("/tmp/research")
def betacdf(x,p,q):
    N=4000; s=0.0
    for i in range(N):
        u=(i+0.5)/N*x; s+=u**(p-1)*(1-u)**(q-1)
    return s*x/N/exp(lgamma(p)+lgamma(q)-lgamma(p+q))
def cp_upper(k,n,a=0.05):
    lo,hi=k/n,1.0
    for _ in range(40):
        mid=(lo+hi)/2
        pr=1-betacdf(mid,k+1,n-k) if n-k>0 else 1.0
        if pr>a: lo=mid
        else: hi=mid
    return hi
def num(x):
    try: return float(x)
    except Exception: return None
print(f"{'candidate':<34}{'n':>4}{'k':>3}{'ub':>7}{'mean win':>9}{'real loss':>10}{'max loss':>9}{'EV real':>8}{'EV@ub,real':>11}{'EV@ub,max':>10}{'need n':>7}")
for f in sorted(glob.glob("*_results.json")):
    if "full" in f or "keep" in f: continue
    d=json.load(open(f))
    for c in d.get("candidates",[]):
        if not c.get("passes_search_bar"): continue
        m=c.get("metrics") or {}; tail=m.get("tail") or {}; raw=m.get("raw") or {}
        n=num(m.get("n_weeks") or m.get("weeks") or m.get("n") or raw.get("n"))
        win=num(m.get("win_rate") if m.get("win_rate") is not None else m.get("win"))
        k=num(tail.get("losses"));  k = k if k is not None else (round(n*(1-win)) if (n and win is not None) else None)
        per=num(m.get("per_week") or m.get("per_period") or m.get("mean") or raw.get("per_period"))
        maxloss=num(c.get("max_loss_per_contract") or m.get("max_loss_per_contract") or m.get("max_loss") or raw.get("max_loss_per_contract"))
        worst=num(m.get("worst") or m.get("worst_week") or m.get("worst_trade"))
        mw=num(tail.get("mean_win")); ml=num(tail.get("mean_loss"))
        if n is None or k is None: continue
        n=int(n); k=int(k); lr=k/n; ub=cp_upper(k,n)
        if ml is None:
            # realised mean loss unknown: the worst period is the best available (conservative) stand-in
            ml = -abs(worst) if worst is not None else -maxloss
        if mw is None and per is not None:
            mw=(per - lr*ml)/(1-lr) if lr<1 else None
        ev_real = (1-lr)*mw + lr*ml if mw is not None else None
        ev_ub_real = (1-ub)*mw + ub*ml if mw is not None else None
        ev_ub_max = (1-ub)*mw - ub*maxloss if (mw is not None and maxloss) else None
        # periods needed for the upper bound to fall enough that EV@ub,max turns positive, at the same realised rate
        need=None
        if mw is not None and maxloss:
            z=1.645
            for N in range(n, 1600, 5):
                p_=lr; den=1+z*z/N
                u=(p_+z*z/(2*N)+z*math.sqrt(p_*(1-p_)/N+z*z/(4*N*N)))/den   # Wilson upper bound
                if (1-u)*mw - u*maxloss > 0: need=N; break
        print(f"{str(c.get('name'))[:33]:<34}{n:>4}{k:>3}{ub:>7.1%}{(mw if mw is not None else float('nan')):>9.1f}{ml:>10.1f}{(maxloss or float('nan')):>9.0f}"
              f"{(ev_real if ev_real is not None else float('nan')):>+8.1f}{(ev_ub_real if ev_ub_real is not None else float('nan')):>+11.1f}{(ev_ub_max if ev_ub_max is not None else float('nan')):>+10.1f}{(need if need else 0):>7}")
print("\nEV real     = the backtest's own number (realised loss rate, realised mean loss)")
print("EV@ub,real  = loss rate at its 95% upper bound, losses at their REALISED mean  <- the fair test")
print("EV@ub,max   = loss rate at its 95% upper bound, losses at MAX               <- the worst case")
print("need n      = periods of history needed before the worst-case bound turns positive at this loss rate (0 = never within 3000)")

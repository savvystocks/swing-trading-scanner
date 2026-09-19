import json, os, urllib.request, time
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
T="SPY QQQ IWM DIA TLT GLD SLV XLF XLE SMH AAPL MSFT NVDA AMZN META GOOGL TSLA AMD AVGO NFLX JPM XOM UNH LLY COST WMT HD BAC COIN PLTR MSTR MU CRM ORCL".split()
AH={"APCA-API-KEY-ID":os.environ.get("ALPACA_PAPER_API_KEY",""),"APCA-API-SECRET-KEY":os.environ.get("ALPACA_PAPER_SECRET_KEY","")}
out={}
for s in T:
    url=(f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day&start=2024-03-01&end=2026-09-17&limit=10000&adjustment=split&feed=iex")
    u=url; d={}
    while u:
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=AH),timeout=40) as r: j=json.loads(r.read())
        except Exception as e:
            print(s,"ERR",str(e)[:80]); break
        for b in (j.get("bars") or {}).get(s) or []: d[b["t"][:10]]=[b["o"],b["h"],b["l"],b["c"],b["v"]]
        tok=j.get("next_page_token"); u=url+"&page_token="+tok if tok else None
    out[s]=d; print(f"{s} {len(d)} days",flush=True); time.sleep(0.3)
json.dump(out,open("/tmp/research/closes.json","w"))
spy=out["SPY"]; days=sorted(spy); cl=[spy[d][3] for d in days]
reg={}
for i,d in enumerate(days):
    if i<50: continue
    sma50=sum(cl[i-50:i])/50; sma20=sum(cl[i-20:i])/20      # D-1 convention: prior 50 closes, excluding today
    prev=cl[i-1]
    dist=(prev/sma50-1)*100; sp=(prev/sma20-1)*100
    reg[d]={"reg":round(dist,2),"sp":round(sp,2),"regime":("BEAR" if dist<-2 else "BULL" if dist>2 else "MILD")}
json.dump(reg,open("/tmp/research/regime.json","w"))
from collections import Counter
print("regime days:",Counter(v["regime"] for v in reg.values()))
print("DONE closes + regime")

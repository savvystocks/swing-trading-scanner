"""Research base: one compact DB of every option row for the liquid universe, parsed and indexed."""
import os, sqlite3, time
os.chdir(os.path.expanduser("~/swing-trading-scanner"))
T="SPY QQQ IWM DIA TLT GLD SLV XLF XLE SMH AAPL MSFT NVDA AMZN META GOOGL TSLA AMD AVGO NFLX JPM XOM UNH LLY COST WMT HD BAC COIN PLTR MSTR MU CRM ORCL".split()
os.makedirs("/tmp/research",exist_ok=True)
try: os.remove("/tmp/research/opt.db")
except OSError: pass
dst=sqlite3.connect("/tmp/research/opt.db")
dst.execute("pragma journal_mode=off"); dst.execute("pragma synchronous=off")
dst.execute("""create table o(t text, day text, exp text, cp text, k real, occ text,
    vol int, askv int, bidv int, prem real, oi int, bid real, ask real, iv real, delta real)""")
src=sqlite3.connect("file:data/uw_history.db?mode=ro",uri=True); src.execute("pragma busy_timeout=120000"); src.execute("pragma cache_size=-80000")
q=",".join("?"*len(T)); buf=[]; n=0; t0=time.time()
for t,d,o,vol,av,bv,pr,oi,b,a,iv,de in src.execute(f"""select ticker,day,option_symbol,volume,ask_volume,bid_volume,total_premium,
        open_interest,nbbo_bid,nbbo_ask,implied_volatility,delta from contracts_daily where ticker in ({q})""",T):
    if not o or len(o)<16: continue
    i=len(o)-15
    try: exp=f"20{o[i:i+2]}-{o[i+2:i+4]}-{o[i+4:i+6]}"; cp=o[i+6]; k=int(o[i+7:])/1000.0
    except Exception: continue
    buf.append((t,d,exp,cp,k,o,vol,av,bv,pr,oi,b,a,iv,de))
    if len(buf)>=100000:
        dst.executemany("insert into o values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",buf); n+=len(buf); buf=[]
        print(f"  {n:,} rows  {time.time()-t0:.0f}s",flush=True)
if buf: dst.executemany("insert into o values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",buf); n+=len(buf)
dst.commit()
print("indexing...",flush=True)
dst.execute("create index ix1 on o(t,day,exp,cp)"); dst.execute("create index ix2 on o(t,exp,cp,k)")
dst.commit()
print(f"DONE {n:,} rows; tickers {len(T)}; size {os.path.getsize('/tmp/research/opt.db')/2**30:.2f} GiB",flush=True)

import os, sqlite3
os.chdir("/tmp/research")
src=sqlite3.connect("opt.db")
try: os.remove("search.db")
except OSError: pass
dst=sqlite3.connect("search.db"); dst.execute("pragma journal_mode=off"); dst.execute("pragma synchronous=off")
dst.execute("""create table o(t text, day text, exp text, cp text, k real, occ text, vol int, askv int, bidv int,
    prem real, oi int, bid real, ask real, iv real, delta real)""")
n=0; buf=[]
for row in src.execute("select * from o where day < '2026-03-16'"):
    buf.append(row)
    if len(buf)>=200000: dst.executemany("insert into o values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",buf); n+=len(buf); buf=[]
if buf: dst.executemany("insert into o values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",buf); n+=len(buf)
dst.commit(); dst.execute("create index ix1 on o(t,day,exp,cp)"); dst.execute("create index ix2 on o(t,exp,cp,k)"); dst.commit()
print(f"search.db {n:,} rows  days {dst.execute('select min(day),max(day),count(distinct day) from o').fetchone()}")
print(f"opt.db    {src.execute('select count(*) from o').fetchone()[0]:,} rows  days {src.execute('select min(day),max(day),count(distinct day) from o').fetchone()}")
print("holdout rows:", src.execute("select count(*) from o where day>='2026-03-16'").fetchone()[0])

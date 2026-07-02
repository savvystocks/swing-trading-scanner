import os, json, tempfile, random as _r
os.environ["GITHUB_ACTIONS"] = "true"
import sys
sys.path.insert(0, r"C:\Users\savva\OneDrive\Documents\Swing Trading")
import harvest_logger as hl
import harvest_db as db

hl._payload_for = lambda ticker, state, mock: ({"macro": {"spot": 1.0}, "fake_payload": ticker}, True)

fails = []
def chk(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def fresh():
    t = tempfile.mkdtemp()
    db.DATA_DIR = t
    db.INBOX_DIR = os.path.join(t, "inbox")
    hl.STATE_PATH = os.path.join(t, "state.json")


def read_inbox():
    return [json.loads(l) for l in open(db.inbox_path(), encoding="utf-8")]


# ===== PART A: single cycle, deterministic (p=0, not near-close) =====
fresh()
hl._near_session_close = lambda ts, window_min=45: False
rows = []
for i in range(30):
    px = 1.0 + i * 0.1
    rows.append({"ticker": f"MID{i}", "type": "call", "strike": 10 + i, "expiry": "2026-07-17",
                 "price": round(px, 2), "bid": round(px - 0.05, 2), "ask": round(px + 0.05, 2),
                 "underlying_price": 20 + i, "total_premium": 1000000 - i * 10000})
rows.append({"ticker": "PRICEY", "type": "call", "strike": 100, "expiry": "2026-07-17", "price": 20.0,
             "bid": 19.9, "ask": 20.1, "underlying_price": 700, "total_premium": 5000000})
rows.append({"ticker": "PENNY", "type": "put", "strike": 5, "expiry": "2026-07-17", "price": 0.10,
             "bid": 0.08, "ask": 0.12, "underlying_price": 6, "total_premium": 80000})
rows.append({"ticker": "SPXW", "type": "call", "strike": 7000, "expiry": "2026-07-17", "price": 2.0,
             "bid": 1.9, "ask": 2.1, "underlying_price": 7000, "total_premium": 3000000})
hl._flow_rows = lambda params: rows
params = {"scanner_flow_limit": 600, "scanner_min_premium": 50000, "scanner_premium_min": 0.30,
          "scanner_premium_max": 4.00, "harvest_topn": 20, "harvest_random": 5, "harvest_random_p": 0.0,
          "harvest_daily_cap": 300}
hl.harvest_scan(params)
recs = read_inbox()
topn = [r for r in recs if r["sample_tier"] == "topn"]
rand = [r for r in recs if r["sample_tier"] == "random"]
qcap = [r for r in recs if r["skip_reason"] == "quota_cap"]
pref = [r for r in recs if r["skip_reason"] == "prefilter"]
chk("A: topn = 20", len(topn) == 20, f"got {len(topn)}")
chk("A: random = 0 (p=0, not near-close)", len(rand) == 0, f"got {len(rand)}")
chk("A: quota_cap = 10 (in-band below cut)", len(qcap) == 10, f"got {len(qcap)}")
chk("A: prefilter = 2 (PRICEY + PENNY)", len(pref) == 2, f"{sorted(r['ticker'] for r in pref)}")
chk("A: SPXW index dropped", not any(r["ticker"] == "SPXW" for r in recs))
chk("A: topn full features, cheap null", all(r["features"] is not None for r in topn) and all(r["features"] is None for r in qcap + pref))
chk("A: entry_ref == ask on every row", all(r["entry_ref"] == r["ask"] for r in recs))
chk("A: barrier ts + pcts stamped", all(r["vertical_barrier_ts"] and r["barrier_up_pct"] == 0.30 and r["barrier_down_pct"] == -0.50 for r in recs))
chk("A: top row is MID0", sorted(topn, key=lambda r: -r["rule_score"])[0]["ticker"] == "MID0")
w2 = hl.harvest_scan(params)
chk("A: per-contract-per-day dedup (run2 no new rows)", len(read_inbox()) == len(recs) and w2["skipped_dup"] == 32, f"{w2}")

# ===== PART B: multi-cycle random mechanism (Bernoulli spread + near-close top-up) =====
fresh()
_r.seed(11)
paramsb = {**params, "harvest_random_p": 0.5}
cycles_with_random = set()
for cyc in range(4):
    rb = [{"ticker": f"OOB{cyc}_{i}", "type": "call", "strike": 100, "expiry": "2026-07-17", "price": 10.0,
           "bid": 9.9, "ask": 10.1, "underlying_price": 700, "total_premium": 500000 + i} for i in range(6)]
    hl._flow_rows = lambda params, _rb=rb: _rb
    hl._near_session_close = lambda ts, window_min=45, _c=cyc: (_c == 3)     # near-close only on the last cycle
    wc = hl.harvest_scan(paramsb)
    if wc["random"] > 0:
        cycles_with_random.add(cyc)
randb = [r for r in read_inbox() if r["sample_tier"] == "random"]
chk("B: >= 5 random over the day", len(randb) >= 5, f"got {len(randb)}")
chk("B: random spread across >= 2 cycles (not morning-concentrated)", len(cycles_with_random) >= 2, f"cycles={sorted(cycles_with_random)}")
chk("B: random rows = out-of-band pool, full payload", all(r["features"] is not None and r["sample_tier"] == "random" for r in randb) and any(r["ticker"].startswith("OOB") for r in randb))

# ===== PART C: cap respected by random draws =====
fresh()
_r.seed(3)
hl._near_session_close = lambda ts, window_min=45: False
paramsc = {**params, "harvest_random_p": 1.0, "harvest_daily_cap": 3}
rc = [{"ticker": f"CAP{i}", "type": "call", "strike": 100, "expiry": "2026-07-17", "price": 10.0,
       "bid": 9.9, "ask": 10.1, "underlying_price": 700, "total_premium": 500000} for i in range(20)]
hl._flow_rows = lambda params: rc
hl.harvest_scan(paramsc)
st = json.load(open(hl.STATE_PATH))
chk("C: payload_count respects cap=3 even at p=1.0", st["payload_count"] <= 3, f"payload_count={st['payload_count']}")

print(f"\nTOTAL: {14 - len(fails)}/14 passed")
if fails:
    raise SystemExit("FAILS: " + ", ".join(fails))
print("HARVESTER OK")

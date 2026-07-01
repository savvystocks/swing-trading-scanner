import os, json
os.environ["GITHUB_ACTIONS"] = "true"
import sys
sys.path.insert(0, r"C:\Users\savva\OneDrive\Documents\Swing Trading")
import harvest_logger as hl
import harvest_db as db
import tempfile

_tmp = tempfile.mkdtemp()
db.DATA_DIR = _tmp
db.INBOX_DIR = os.path.join(_tmp, "inbox")
hl.STATE_PATH = os.path.join(_tmp, "state.json")

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
hl._payload_for = lambda ticker, state, mock: ({"macro": {"spot": 1.0}, "fake_payload": ticker}, True)

params = {"scanner_flow_limit": 600, "scanner_min_premium": 50000, "scanner_premium_min": 0.30,
          "scanner_premium_max": 4.00, "harvest_topn": 20, "harvest_random": 5, "harvest_daily_cap": 300}

w = hl.harvest_scan(params, executed_record=None, mock=True)
print("run1 written:", w)
recs = [json.loads(l) for l in open(db.inbox_path(), encoding="utf-8")]
topn = [r for r in recs if r["sample_tier"] == "topn"]
rand = [r for r in recs if r["sample_tier"] == "random"]
qcap = [r for r in recs if r["skip_reason"] == "quota_cap"]
pref = [r for r in recs if r["skip_reason"] == "prefilter"]

fails = []
def chk(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond: fails.append(name)

chk("total rows = 20 topn + 5 random + 5 quota_cap + 2 prefilter = 32", len(recs) == 32, f"got {len(recs)}")
chk("topn = 20", len(topn) == 20, f"got {len(topn)}")
chk("random = 5", len(rand) == 5, f"got {len(rand)}")
chk("quota_cap = 5", len(qcap) == 5, f"got {len(qcap)}")
chk("prefilter = 2 (PRICEY + PENNY)", len(pref) == 2, f"tickers={sorted(r['ticker'] for r in pref)}")
chk("SPXW index dropped", not any(r["ticker"] == "SPXW" for r in recs))
chk("topn+random carry full features", all(r["features"] is not None for r in topn + rand))
chk("quota_cap + prefilter have null features", all(r["features"] is None for r in qcap + pref))
chk("entry_ref == ask on every row", all(r["entry_ref"] == r["ask"] for r in recs))
chk("all rows have vertical_barrier_ts", all(r["vertical_barrier_ts"] for r in recs))
chk("barrier pcts stamped", all(r["barrier_up_pct"] == 0.30 and r["barrier_down_pct"] == -0.50 for r in recs))
chk("topn poll_tier standard", all(r["poll_tier"] == "standard" for r in topn))
chk("quota_cap poll_tier reduced (valid quote)", all(r["poll_tier"] == "reduced" for r in qcap))
r0 = sorted(topn, key=lambda r: -r["rule_score"])[0]
chk("top row is MID0 (highest premium)", r0["ticker"] == "MID0", f"got {r0['ticker']}")
chk("OCC well-formed", r0["occ_symbol"] and r0["occ_symbol"].startswith("MID0") and r0["occ_symbol"].endswith("C00010000"), r0["occ_symbol"])

w2 = hl.harvest_scan(params, executed_record=None, mock=True)
recs2 = [json.loads(l) for l in open(db.inbox_path(), encoding="utf-8")]
chk("run2 logs no new rows (per-contract-per-day dedup)", len(recs2) == 32, f"total after run2={len(recs2)}")
chk("run2 all skipped_dup", w2["skipped_dup"] == 32 and w2["topn"] == 0, f"{w2}")

print(f"\nTOTAL: {16 - len(fails)}/16 passed")
if fails:
    raise SystemExit("FAILS: " + ", ".join(fails))
print("HARVESTER OK")

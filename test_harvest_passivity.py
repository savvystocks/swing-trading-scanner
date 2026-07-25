import os, json, copy, tempfile, sys
os.environ["GITHUB_ACTIONS"] = "true"
sys.path.insert(0, r"C:\Users\savva\OneDrive\Documents\Swing Trading")
import harvest_db as db
import harvest_logger as hl
import fill_ledger as fl
import sandbox_proactive_lab as lab

tmp = tempfile.mkdtemp()
db.DATA_DIR = tmp
db.DB_PATH = os.path.join(tmp, "harvest.db")
db.INBOX_DIR = os.path.join(tmp, "inbox")
fl.INBOX_DIR = db.INBOX_DIR
hl.STATE_PATH = os.path.join(tmp, "state.json")
# isolate the engine's committed-state files - the Tier B daily brake / scoreboard read LOG_PATH,
# so a run against the real log would trip the brake and skip the entry this test asserts on.
lab.LOG_PATH = os.path.join(tmp, "logs.json")
lab.COOLOFF_PATH = os.path.join(tmp, "cooloff.json")
lab.AUTOPSY_MD = os.path.join(tmp, "autopsy.md")
lab.ADVISORY_MD = os.path.join(tmp, "advisory.md")

CANDS = [{"ticker": "AAA", "total_premium": 900000, "flow_type": "call", "underlying_price": 20},
         {"ticker": "BBB", "total_premium": 800000, "flow_type": "put", "underlying_price": 18},
         {"ticker": "CCC", "total_premium": 700000, "flow_type": "call", "underlying_price": 25}]

FLOW = [{"ticker": "AAA", "type": "call", "strike": 21, "expiry": "2026-07-17", "price": 1.5,
         "bid": 1.45, "ask": 1.55, "underlying_price": 20, "total_premium": 900000},
        {"ticker": "DDD", "type": "put", "strike": 30, "expiry": "2026-07-17", "price": 2.0,
         "bid": 1.9, "ask": 2.1, "underlying_price": 32, "total_premium": 500000}]

lab._paper_creds = lambda: (None, None)
lab.get_open_orders = lambda creds: []
lab.audit_stale_orders = lambda creds, orders=None: []
lab.manage_open_positions = lambda creds, params: ([], [])
lab.get_open_positions = lambda creds=None: []
lab._maybe_send_digest = lambda: None
lab.scan_candidates = lambda params: [dict(c) for c in CANDS]
hl._flow_rows = lambda params: [dict(r) for r in FLOW]
hl._payload_for = lambda ticker, state, mock: ({"macro": {"spot": 20.0}, "fake": ticker}, True)

MD = {"macro": {"spot": 20.0, "distance_to_sma20_pct": 0.5}, "iv_term": {"iv_ratio": 1.1},
      "skew": {"skew_ratio": 1.0, "skew_bias": "flat"}, "news_sentiment_score": 0.2,
      "news": {"news_type": "none"}, "regime_stack": {"sector_etf": "XLK", "sector_dist_pct": 1.2}}

def make_enter():
    def stub(t, regime, mock=False, candidate=None, dry_run=True, positions=None, open_orders=None):
        return {"trade_set_id": "tsid", "ticker": t, "regime": "BULL_TREND", "execution_mode": "DRY_RUN",
                "occ_resolution": "synth", "metadata": copy.deepcopy(MD),
                "legs": {"bullish_call": {"structure": "LONG_CALL", "occ_symbol": "AAA260717C00021000",
                                          "expiry": "2026-07-17", "strike": 21.0, "entry_premium": 1.5,
                                          "limit_price": 1.52, "contracts": 5}},
                "orders": {"bullish_call": {"status": "accepted", "order_id": "OID-DETERMINISTIC",
                                            "submitted": True}},
                "status": "OPEN", "skipped": False}
    return stub
lab.enter_proactive_set = make_enter()

def run_capture():
    rec = lab.run_scheduled_cycle(mock=True)
    return copy.deepcopy(rec["orders"]) if rec else None

print("--- run A: harvest ENABLED ---")
os.makedirs(db.INBOX_DIR, exist_ok=True)
orders_on = run_capture()
recs = [json.loads(l) for l in open(db.inbox_path(), encoding="utf-8")]
executed_rows = [r for r in recs if r["executed"] == 1]

print("--- run B: harvest DISABLED (no-op) ---")
_real = hl.harvest_scan
hl.harvest_scan = lambda *a, **k: {}
orders_off = run_capture()
hl.harvest_scan = _real

print("--- run C: harvest CRASHES (raises) ---")
def boom(*a, **k):
    raise RuntimeError("intentional harvest crash")
hl.harvest_scan = boom
orders_crash = run_capture()
hl.harvest_scan = _real

print("--- run D: FILL LEDGER crashes (school 1c fail-open) ---")
_real_log = fl.log_event
def ledger_boom(*a, **k):
    raise RuntimeError("intentional ledger crash")
fl.log_event = ledger_boom
orders_ledger_crash = run_capture()
fl.log_event = _real_log

print("--- run E: OWNER HALT active (school 1e - entries pause, harvest continues) ---")
os.environ["SCHOOL_HALT"] = "1"
orders_halt = run_capture()
_halt_recs = [json.loads(l) for l in open(db.inbox_path(), encoding="utf-8")]
os.environ.pop("SCHOOL_HALT")

fails = []
def chk(n, c, d=""):
    print(f"  [{'PASS' if c else 'FAIL'}] {n}  {d}")
    if not c: fails.append(n)

chk("orders identical harvest-ON vs harvest-OFF", orders_on == orders_off, f"{orders_on} vs {orders_off}")
chk("orders identical when harvest CRASHES (fail-safe)", orders_on == orders_crash)
chk("a trade was actually placed", orders_on and orders_on["bullish_call"]["order_id"] == "OID-DETERMINISTIC")
chk("exactly 1 executed row logged == 1 trade placed", len(executed_rows) == 1, f"executed rows={len(executed_rows)}")
chk("executed row OCC matches the placed order leg", executed_rows and executed_rows[0]["occ_symbol"] == "AAA260717C00021000")
chk("executed row carries full features (not null)", executed_rows[0]["features"] is not None)
chk("counterfactual rows also logged (DDD prefilter/quota + AAA flow-dup skipped)", len(recs) >= 2, f"total rows={len(recs)}")
chk("returned record is clean (_scan_candidate popped)", "_scan_candidate" not in (lab.run_scheduled_cycle(mock=True) or {}))
chk("orders identical when the FILL LEDGER crashes (school 1c fail-open)", orders_on == orders_ledger_crash)
import glob as _glob
_fill_files = _glob.glob(os.path.join(db.INBOX_DIR, "fills_*.jsonl"))
_fill_events = [json.loads(l) for f in _fill_files for l in open(f, encoding="utf-8") if l.strip()]
_subs = [e for e in _fill_events if e["kind"] == "entry_submit"]
chk("fill ledger logged entry_submit for the placed order (signal quote attached)",
    any(e.get("order_id") == "OID-DETERMINISTIC" and e.get("occ") == "AAA260717C00021000" for e in _subs),
    f"entry_submit events={len(_subs)}")
chk("OWNER HALT paused new entries (no order placed this cycle)", orders_halt is None,
    f"orders_halt={orders_halt}")
chk("OWNER HALT still harvested (counterfactual logging continues under halt)", len(_halt_recs) > len(recs),
    f"recs grew {len(recs)}->{len(_halt_recs)}")

print(f"\nTOTAL: {12 - len(fails)}/12 passed", flush=True)
if fails:
    raise SystemExit("FAILS: " + ", ".join(fails))
print("PASSIVITY PROVEN: logging never alters or crashes the trade path")

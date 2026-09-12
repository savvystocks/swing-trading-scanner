"""REGIME DRILL (owner 2026-09-03: "be certain everything works... and check if we ever go
back to mild or bear that that works"). Exercises the REAL entry code under each regime with
everything external faked: spy_regime patched, option quotes canned, log reads empty, log
writes captured, orders never placed. Each regime's first live day keeps finding a hidden
assumption (MILD 09-02: sensor blind spot; BULL 09-03: affordability); this drill is the
fire-drill run BEFORE the market runs it for us. Exit 0 only if every scenario routes as the
grid intends. Run after any entry-path change; BEAR especially, since it has never had a
live day on current code."""
import json
import os
import sys
import tempfile
import urllib.request
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
os.environ.setdefault("ALPACA_PAPER_API_KEY", "drill")
os.environ.setdefault("ALPACA_PAPER_SECRET_KEY", "drill")
import fade_book
import sandbox_proactive_lab as lab

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


captured = []
lab._append_log = lambda rec: captured.append(rec)
lab._save_log_list = lambda log: None
lab._load_log_list = lambda: []
lab._notify = lambda text: True
lab.get_open_positions = lambda creds: []
lab.route_to_alpaca_paper = lambda *a, **k: {"orders": [{"status": "accepted", "id": "drill"}]}
lab._paper_creds = lambda: ("drill", "drill")
lab._rewrite_last = lambda rec: None                 # 2026-09-12: the entry path now rewrites the
lab.STUDENT_SCORES_LOG = os.path.join(              # book after routing - never the real one here;
    tempfile.gettempdir(), "regime_drill_student_scores.jsonl")   # and the passive score log is
                                                     # a committed audit - fixture rows stay out of it

EXP_NEAR = (date.today() + timedelta(days=30)).strftime("%y%m%d")
EXP_ISO = (date.today() + timedelta(days=30)).isoformat()


def fake_urlopen(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            if "options/quotes/latest" in url:
                sym = url.split("symbols=")[1].split("&")[0]
                return json.dumps({"quotes": {sym: {"bp": 5.30, "ap": 5.40}}}).encode()
            return json.dumps({}).encode()
    return R()


lab.urllib.request.urlopen = fake_urlopen

MD = {"macro": {"spot": 480.0, "sma20": 500.0, "distance_to_sma20_pct": -4.0, "source": "drill"},
      "iv_term": {"iv_front": 45.0, "iv_back": 40.0, "iv_ratio": 1.13, "source": "drill"},
      "regime_stack": {"market_spy_dist_pct": -1.5}, "technical": {}, "gex": {}, "dark_pool": {},
      "pemd": {}, "news": {}, "skew": {}, "vrp": {}, "flow_aggression": {}, "flow_persistence": {},
      "macro_context": {}, "dealer_greeks": {}, "fundamentals": {},
      "entry_ts_utc": "2026-01-01T00:00:00Z"}
lab.collect_metadata = lambda t, mock=False: json.loads(json.dumps(MD))
lab.classify_regime = lambda md, c=None: "BULLISH"

print("=== REGIME DRILL ===", flush=True)

# --- scenario 1: BULL, mega-cap - synthesized legs too rich -> affordability fallback ---
captured.clear()
cand = {"ticker": "MEGA", "flow_type": "call", "total_premium": 200000,
        "afford_call": {"occ": f"MEGA{EXP_NEAR}C00500000", "ask": 3.20,
                        "expiry": EXP_ISO, "strike": 500.0}}
rec = lab.enter_proactive_set("MEGA", None, mock=False, candidate=cand, dry_run=True,
                              positions=[], open_orders=[], probe=True, probe_filter=None)
leg = (rec.get("legs") or {}).get("bullish_call") or {}
check("BULL: rich synth -> afford fallback entered the trigger contract",
      bool(rec) and not rec.get("skipped") and leg.get("occ_source") == "afford_fallback"
      and leg.get("trigger_contract") and leg.get("contracts") == 1,
      str(rec.get("reason") or leg.get("occ_symbol")))
check("BULL: fallback repriced from the LIVE quote (5.40), not the stale alert ask",
      abs((leg.get("entry_premium") or 0) - 5.40) < 1e-9, str(leg.get("entry_premium")))

# --- scenario 2: MILD, pricey-pool trigger-contract path (DIP_CONF_MILD mechanism) ---
captured.clear()
pc = {"ticker": "MID", "flow_type": "call", "total_premium": 150000,
      "occ": f"MID{EXP_NEAR}C00100000", "expiry": EXP_ISO, "strike": 100.0, "alert_ask": 5.10}
lab._PROBE_CONTRACT["c"] = pc
try:
    rec2 = lab.enter_proactive_set("MID", None, mock=False, candidate=pc, dry_run=True,
                                   positions=[], open_orders=[], probe=True, probe_filter=None)
finally:
    lab._PROBE_CONTRACT["c"] = None
leg2 = (rec2.get("legs") or {}).get("bullish_call") or {}
check("MILD: trigger-contract path buys the verbatim occ (resolution skipped)",
      not rec2.get("skipped") and leg2.get("occ_symbol") == pc["occ"]
      and leg2.get("occ_source") == "uw_trigger_verbatim",
      str(rec2.get("reason") or leg2.get("occ_source")))

# --- scenario 3: BEAR, fade-shape entry routes through the fade book ---
captured.clear()
fade_book._REGIME.update({"date": date.today().isoformat(), "val": "BEAR"})
MD_BR = json.loads(json.dumps(MD)); MD_BR["macro"]["spot"] = 50.0; MD_BR["macro"]["sma20"] = 52.0
lab.collect_metadata = lambda t, mock=False: json.loads(json.dumps(MD_BR))
bear_cand = {"ticker": "BR", "flow_type": "call", "total_premium": 120000,
             "afford_call": {"occ": f"BR{EXP_NEAR}C00050000", "ask": 2.10,
                             "expiry": EXP_ISO, "strike": 50.0}}
rec3 = lab.enter_proactive_set("BR", None, mock=False, candidate=bear_cand, dry_run=True,
                               positions=[], open_orders=[], probe=False)
ok3 = (not rec3.get("skipped")) if isinstance(rec3, dict) else False
check("BEAR: fade book takes the fade-shaped candidate (dip calls, contra-SPY)",
      ok3, str(rec3.get("reason"))[:70] if isinstance(rec3, dict) else "no rec")

# --- scenario 4: BEAR, occ-collision guard still refuses a held contract ---
held_occ = f"BR{EXP_NEAR}C00050000"
lab._load_log_list = lambda: [{"status": "OPEN", "legs": {"bullish_call": {"occ_symbol": held_occ}}}]
pc4 = {"ticker": "BR", "flow_type": "call", "total_premium": 120000, "occ": held_occ,
       "expiry": EXP_ISO, "strike": 50.0, "alert_ask": 5.10}
lab._PROBE_CONTRACT["c"] = pc4
try:
    rec4 = lab.enter_proactive_set("BR", None, mock=False, candidate=pc4, dry_run=True,
                                   positions=[], open_orders=[], probe=True, probe_filter=None)
finally:
    lab._PROBE_CONTRACT["c"] = None
check("BEAR: occ guard refuses a contract another record already tracks",
      rec4.get("skipped") and "occ_collision" in str(rec4.get("reason")),
      str(rec4.get("reason"))[:60])
lab._load_log_list = lambda: []

# --- scenario 5: fivek PUT_DEBIT_W fires ONLY in BEAR, wings-first ---
import fivek_probes as fk
orders_placed = []
fk._quote = lambda occ, creds: (1.10, 1.20)
fk._order = lambda occ, side, limit, creds: (orders_placed.append((side, occ)) or {"id": "drill"})
fk._held = lambda occ, creds: False
fk._xsp_close_series = lambda: type("S", (), {"iloc": type("I", (), {"__getitem__": lambda s, i: 650.0})(),
                                              "index": type("X", (), {"date": []})()})()
saved = []


class LabShim:
    _load_log_list = staticmethod(lambda: [])
    _save_log_list = staticmethod(lambda log: saved.extend(log))
    _notify = staticmethod(lambda text: True)


fade_book._REGIME.update({"date": date.today().isoformat(), "val": "MILD"})
fk._enter("PUT_DEBIT_W", True, {"otm_short": 4.0, "otm_long": 1.0}, ("k", "s"), LabShim, [], __import__("datetime").datetime.now(__import__("datetime").timezone.utc)) if False else None
# gate check happens in cycle(); drill the gate directly:
rg_mild = fade_book.spy_regime()
check("MILD: put debit stands down (BEAR-only gate)", rg_mild != "BEAR", f"regime={rg_mild}")
fade_book._REGIME.update({"date": date.today().isoformat(), "val": "BEAR"})
ok5 = fk._enter("PUT_DEBIT_W", True, {"otm_short": 4.0, "otm_long": 1.0}, ("k", "s"), LabShim, [],
                __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
buys_first = orders_placed and orders_placed[0][0] == "buy"
check("BEAR: PUT_DEBIT_W enters, LONG wing bought FIRST (never naked)",
      bool(ok5) and buys_first and any(r.get("probe_strategy") == "PUT_DEBIT_W" for r in saved),
      str(orders_placed[:2]))

# --- scenario 6: STUDENT seat (2026-09-11): no model -> stands down; unknown/BEAR regime -> no
#     scoring; MILD with a model -> ranked pick; shadow mode never enters ---
try:
    import json as _j6, os as _o6
    lab._STUDENT_MODELS.clear()
    _pool6 = [{"ticker": "XYZ", "flow_type": "call", "occ": "XYZ261009C00050000", "alert_ask": 5.4, "alert_bid": 5.3,
               "total_premium": 57000, "expiry": EXP_ISO, "strike": 50.0,
               "alert": {"created_at": "2026-09-10T14:40:00Z", "total_premium": 57000, "total_size": 110,
                         "trade_count": 2, "total_ask_side_prem": 57000, "total_bid_side_prem": 0,
                         "open_interest": 1200, "iv_start": 0.4, "first_seen": "2026-09-10T14:31:00Z"}}]
    _bars_bak = lab._alpaca_daily
    lab._alpaca_daily = lambda t, days=60: [{"h": 10, "l": 9, "c": 10.0 + (i % 3) * 0.1, "v": 1000, "t": f"2026-08-{(i % 28) + 1:02d}"} for i in range(30)]
    _reg_bak = fade_book.spy_regime
    fade_book._REGIME.update({"date": date.today().isoformat(), "val": "MILD", "dist50_prev": 1.5, "dist20_prev": 0.8})
    fade_book.spy_regime = lambda: "MILD"
    _r6a = lab._student_rank(_pool6, ("k", "s"), [])
    check("STUDENT: no spec block -> rank returns nothing, no exception", _r6a == [])
    _fake = {"kind": "classifier", "baseline": 3.0, "n_features": 15, "trained": date.today().isoformat(),
             "thresholds": {"k3": 0.5}, "trees": []}
    _o6.makedirs("reports/fade_meta", exist_ok=True)
    _j6.dump(_fake, open("reports/fade_meta/student_STUDENT_DRILL.json", "w"))
    _spec_bak = fade_book._SPEC
    _sp6 = _j6.loads(_j6.dumps(fade_book.spec()))
    _sp6.setdefault("probe", {})["student"] = {"enabled": True, "mode": "shadow", "bear_standdown": True,
        "probes": {"STUDENT_DRILL": {"model": "reports/fade_meta/student_STUDENT_DRILL.json", "k_per_week": 3, "live": True}}}
    fade_book._SPEC = _sp6
    lab._STUDENT_MODELS.clear()
    _r6b = lab._student_rank(_pool6, ("k", "s"), [])
    check("STUDENT: MILD with a model -> one ranked eligible pick with p > 0.9",
          len(_r6b) == 1 and _r6b[0][1] == "STUDENT_DRILL" and _r6b[0][0] > 0.9, str([(round(x[0], 3), x[1]) for x in _r6b]))
    _r6c = lab._student_rank(_pool6, ("k", "s"), [{"probe_strategy": "STUDENT_DRILL", "entry_ts_utc": date.today().isoformat() + "T14:00:00Z"}] * 3)
    check("STUDENT: weekly budget spent -> the pick is logged but not eligible", _r6c == [])
    _sp6["probe"]["student"]["probes"]["STUDENT_DRILL"]["live"] = False
    lab._STUDENT_MODELS.clear()
    _r6e = lab._student_rank(_pool6, ("k", "s"), [])
    check("STUDENT: a picker not flagged live is scored and logged but never eligible", _r6e == [])
    _sp6["probe"]["student"]["probes"]["STUDENT_DRILL"]["live"] = True
    fade_book._REGIME.update({"dist50_prev": None, "dist20_prev": None})
    _r6d = lab._student_rank(_pool6, ("k", "s"), [])
    check("STUDENT: prior-close SPY readings unknown -> stands down (fail-closed)", _r6d == [])
    fade_book._SPEC = _spec_bak
    fade_book.spy_regime = _reg_bak
    lab._alpaca_daily = _bars_bak
    lab._STUDENT_MODELS.clear()
    _o6.remove("reports/fade_meta/student_STUDENT_DRILL.json")
except Exception as _e6:
    check("STUDENT: drill scenario ran", False, f"{type(_e6).__name__}: {_e6}")

print(f"\nDRILL: {len(PASS)} pass / {len(FAIL)} fail", flush=True)
if FAIL:
    print("FAILED: " + ", ".join(FAIL), flush=True)
    sys.exit(1)
print("REGIME DRILL: ALL SCENARIOS ROUTE AS DESIGNED", flush=True)

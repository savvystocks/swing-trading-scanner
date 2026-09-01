"""$5K DEFINED-RISK PROBES (owner order 2026-08-18 20:29: integrate the 5k strategies live).

Two weekly XSP structures, both sized for a real $5k account, both European cash-settled
(no sell-to-close orders ever exist -> can never day-trade):
  CREDIT_SPREAD_W - sell the 2%-OTM put, BUY the 4%-OTM put. Max loss = width - credit
                    (~$1.2k on XSP), the premium edge in its 5k-legal form.
  CONDOR_W        - the same put spread PLUS sell 2%-OTM call / buy 4%-OTM call. Collects
                    both sides; capped both sides.
Mechanics: one entry per structure per week (first cycle >= 15:00 UTC); LONG wings are
bought FIRST so a partial fill can never leave a naked short; broker-position idempotency
check before entering (the record-propagation lesson); settle after Friday expiry vs ^XSP
close. Records: no legs dict (options exit engine ignores), occ + occ_more (reconciler
knows every leg). Fail-open everywhere.
"""
import json
import urllib.request
from datetime import date, datetime, timedelta, timezone

import fade_book


def _cfg():
    return ((fade_book.spec().get("probe") or {}).get("fivek") or {}) if fade_book.active() else {}


def _xsp_close_series():
    import yfinance as yf
    s = yf.download("^XSP", period="10d", progress=False, auto_adjust=True)["Close"].dropna()
    return s.iloc[:, 0] if hasattr(s, "columns") else s


def _quote(occ, creds):
    req = urllib.request.Request(
        f"https://data.alpaca.markets/v1beta1/options/quotes/latest?symbols={occ}&feed=indicative",
        headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            q = json.loads(r.read()).get("quotes", {}).get(occ) or {}
            return q.get("bp"), q.get("ap")
    except Exception:
        return None, None


def _order(occ, side, limit, creds):
    body = json.dumps({"symbol": occ, "qty": "1", "side": side, "type": "limit",
                       "limit_price": str(round(limit, 2)), "time_in_force": "day"}).encode()
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/orders", data=body,
                                 headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1],
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  fivek: {side} {occ} failed {type(e).__name__}: {str(e)[:70]}")
        return None


def _held(occ, creds):
    """Position OR pending order on this occ (2026-08-20: the 15:07 entry's short leg was
    still an unfilled order at 15:16, so the position-only check let a double-entry through)."""
    h = {"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]}
    try:
        req = urllib.request.Request(f"https://paper-api.alpaca.markets/v2/positions/{occ}", headers=h)
        with urllib.request.urlopen(req, timeout=15) as r:
            if abs(float(json.loads(r.read()).get("qty") or 0)) > 0:
                return True
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            "https://paper-api.alpaca.markets/v2/orders?status=open&limit=100", headers=h)
        with urllib.request.urlopen(req, timeout=15) as r:
            return any((o.get("symbol") or "").upper() == occ.upper() for o in json.loads(r.read()))
    except Exception:
        return False


def _occ(exp, cp, k):
    return f"XSP{exp.strftime('%y%m%d')}{cp}{int(round(k * 1000)):08d}"


def _settle_one(r, lab, now):
    try:
        s = _xsp_close_series()
        exp = date.fromisoformat(r["expiry"])
        sd = [d for d in s.index.date if d <= exp]
        settle = float(s[s.index.date == sd[-1]].iloc[-1]) if sd else None
    except Exception:
        settle = None
    if settle is None:
        return False
    pnl = 0.0
    for lg in r["structure"]["short"]:
        intr = max(lg["k"] - settle, 0.0) if lg["cp"] == "P" else max(settle - lg["k"], 0.0)
        pnl += lg["prem"] - intr
    for lg in r["structure"]["long"]:
        intr = max(lg["k"] - settle, 0.0) if lg["cp"] == "P" else max(settle - lg["k"], 0.0)
        pnl += intr - lg["prem"]
    pnl *= 100
    r["status"] = "CLOSED"
    r["settle"] = {"xsp": settle, "pnl_usd": round(pnl, 2), "at": now.isoformat()}
    print(f"  PROBE[{r['probe_strategy']}] settled: ${pnl:+.0f}")
    try:
        lab._notify(f"<b>PROBE {r['probe_strategy']} settled</b> ${pnl:+.0f} (XSP {settle:.2f})")
    except Exception:
        pass
    return True


def _enter(strategy, put_only, cfg, creds, lab, log, now):
    try:
        s = _xsp_close_series()
        spot = float(s.iloc[-1])
    except Exception:
        print(f"  fivek {strategy}: XSP spot fetch failed - no entry this cycle")
        return False
    exp = now.date() + timedelta(days=(4 - now.date().weekday()) % 7)
    if exp <= now.date():
        exp += timedelta(days=7)
    k1 = round(spot * (1 - cfg.get("otm_short", 2.0) / 100))
    k2 = round(spot * (1 - cfg.get("otm_long", 4.0) / 100))
    legs_s = [("P", k1)]
    legs_l = [("P", k2)]
    if not put_only:
        legs_s.append(("C", round(spot * (1 + cfg.get("call_short", 2.0) / 100))))
        legs_l.append(("C", round(spot * (1 + cfg.get("call_long", 4.0) / 100))))
    if _held(_occ(exp, legs_s[0][0], legs_s[0][1]), creds):
        print(f"  fivek {strategy}: short leg already held at broker - skip (record in flight?)")
        return False
    struct = {"short": [], "long": []}
    for cp, k in legs_l:                            # LONG wings first - never naked
        o = _occ(exp, cp, k)
        if _held(o, creds):
            print(f"  fivek {strategy}: long wing {o} already held at broker - skip")
            return False
        bid, ask = _quote(o, creds)
        if not ask or ask <= 0:
            print(f"  fivek {strategy}: no ask on long wing {o} - structure aborted pre-order")
            return False
        resp = _order(o, "buy", ask, creds)
        if not (resp and resp.get("id")):
            return False
        struct["long"].append({"occ": o, "cp": cp, "k": k, "prem": ask})
    for cp, k in legs_s:
        o = _occ(exp, cp, k)
        bid, ask = _quote(o, creds)
        if not bid or bid <= 0.02:
            print(f"  fivek: no usable bid on short leg {o} - wings held, structure incomplete")
            break
        resp = _order(o, "sell", bid, creds)
        if not (resp and resp.get("id")):
            break
        struct["short"].append({"occ": o, "cp": cp, "k": k, "prem": bid})
    if not struct["short"]:
        # WINGS-ONLY record (adversarial review 2026-09-01): a filled long with a failed short
        # used to vanish - no record, so the weekly gate never armed and every later cycle
        # re-bought the long. Worst under put_debit, where the long is the expensive near-ATM
        # leg and BEAR (its only regime) is when short bids go thin. Logging it blocks the
        # weekly re-entry, prices the legs at expiry, and keeps the reconciler seeing every occ.
        if struct["long"]:
            cost = -sum(l["prem"] for l in struct["long"])
            log.append({"book": "PROBE", "probe_strategy": strategy,
                        "trade_set_id": "f5k" + now.strftime("%m%d%H%M"), "ticker": "XSP",
                        "occ": struct["long"][0]["occ"],
                        "occ_more": [l["occ"] for l in struct["long"][1:]],
                        "structure": struct, "expiry": exp.isoformat(), "contracts": 1,
                        "net_credit": round(cost, 2), "status": "OPEN",
                        "entry_ts_utc": now.isoformat(),
                        "note": "INCOMPLETE - long wings only, short leg failed; logged to stop re-entry"})
            lab._save_log_list(log)
            print(f"  PROBE[{strategy}] INCOMPLETE - short failed, wings logged (${cost * 100:+.0f})")
            try:
                lab._notify(f"<b>PROBE {strategy}</b> INCOMPLETE - long wings held, short leg failed; "
                            f"recorded, no re-entry this week")
            except Exception:
                pass
        return False
    credit = sum(l["prem"] for l in struct["short"]) - sum(l["prem"] for l in struct["long"])
    log.append({"book": "PROBE", "probe_strategy": strategy,
                "trade_set_id": "f5k" + now.strftime("%m%d%H%M"), "ticker": "XSP",
                "occ": struct["short"][0]["occ"],
                "occ_more": [l["occ"] for l in struct["short"][1:] + struct["long"]],
                "structure": struct, "expiry": exp.isoformat(), "contracts": 1,
                "net_credit": round(credit, 2), "status": "OPEN",
                "entry_ts_utc": now.isoformat(),
                "note": "5k defined-risk weekly (owner order 2026-08-18)"})
    lab._save_log_list(log)
    print(f"  PROBE[{strategy}] entered exp {exp}, net credit ${credit * 100:+.0f}")
    try:
        lab._notify(f"<b>PROBE {strategy}</b> entered (exp {exp}, credit ${credit * 100:+.0f}, defined risk)")
    except Exception:
        pass
    return True


def cycle(creds, allow_entries=True):
    cfg = _cfg()
    print(f"  fivek: cycle cfg={'ok' if cfg else 'EMPTY'} creds={'ok' if creds and all(creds) else 'MISSING'} allow={allow_entries}")
    if not cfg or not creds or not all(creds):
        return
    import sandbox_proactive_lab as lab
    now = datetime.now(timezone.utc)
    log = lab._load_log_list()
    week0 = (now.date() - timedelta(days=now.date().weekday())).isoformat()
    dirty = False
    have = set()
    for r in log:
        if r.get("probe_strategy") not in ("CREDIT_SPREAD_W", "CONDOR_W", "PUT_DEBIT_W"):
            continue
        if (r.get("entry_ts_utc") or "") >= week0:
            have.add(r["probe_strategy"])
        if r.get("status") == "OPEN" and now.date() > date.fromisoformat(r["expiry"]):
            dirty = _settle_one(r, lab, now) or dirty
    if dirty:
        lab._save_log_list(log)
    if not allow_entries or now.hour < 15:
        print(f"  fivek: entries gated (allow={allow_entries} hour={now.hour}) - settles only")
        return
    _rg = None
    try:
        _rg = fade_book.spy_regime()
    except Exception:
        pass
    cs = cfg.get("credit_spread") or {}
    if cs.get("enabled") and "CREDIT_SPREAD_W" not in have:
        # REGIME GATE (Friday window 2026-08-28, regime playbook on real SPY quotes): put credit
        # spreads are a MILD-market specialist (+$64/wk t+4.5, 94% win) that BLEEDS in bear
        # (-$140/wk, worst -$923). Stand down in BEAR; trade MILD+BULL. Fail-open: unknown
        # regime -> allow (a missed income week beats a blocked settle path never).
        if cs.get("regime_gate", True) and _rg == "BEAR":
            print("  fivek: credit spread stands down (BEAR regime - playbook gate)")
        else:
            _enter("CREDIT_SPREAD_W", True, cs, creds, lab, log, now)
        log = lab._load_log_list()
    co = cfg.get("condor") or {}
    if co.get("enabled") and "CONDOR_W" not in have:
        _enter("CONDOR_W", False, co, creds, lab, log, now)
        log = lab._load_log_list()
    # PUT_DEBIT_W (owner order 2026-09-01, 3x3 grid bear cell): BUY the near put, sell the far
    # put = defined-risk bearish weekly. otm_long < otm_short in cfg flips _enter's k1/k2 into
    # debit orientation; long wing still bought first (never naked). UNPROVEN by backtest -
    # enters as a structural hypothesis; regime-gated the OPPOSITE way to the credit spread
    # (fires ONLY in BEAR, where the credit spread stands down). Fail-CLOSED on unknown regime:
    # an unproven directional bet does not get the benefit of a data hiccup.
    pd_ = cfg.get("put_debit") or {}
    if pd_.get("enabled") and "PUT_DEBIT_W" not in have:
        if _rg == "BEAR":
            _enter("PUT_DEBIT_W", True, pd_, creds, lab, log, now)
        else:
            print(f"  fivek: put debit stands down (regime {_rg or 'unknown'} - BEAR-only grid cell)")

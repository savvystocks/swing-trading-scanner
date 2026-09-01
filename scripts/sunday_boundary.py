"""AUTONOMOUS SUNDAY BOUNDARY (owner order 2026-08-10: improvement without Claude).

Runs on the VPS every Sunday. Reads the shadow-lab ledger's VIRGIN days, applies the
pre-registered promotion bars, and - because every candidate upgrade is now a SPEC KEY the
engine reads - can apply a passing upgrade mechanically: edit spec, bump version, commit,
push, Telegram the verdict. No bars passed -> report only. Nothing outside the pre-registered
MENU can ever be auto-applied; code-level changes still require a human session.

MENU (hypothesis -> spec keys) + BARS (all must hold):
  V13_DEPTH  -> entry.max_depth_pct = 2.0
  MILD_ONLY  -> entry.max_depth_pct = 2.0, entry.max_spy_dist_pct = 1.5
  BAND_WIDE  -> entry.flow_min = 40000, entry.flow_max = 300000
BARS: >= 10 virgin days where the book had trades; book day-mean > BASELINE day-mean + 2pts;
      book day-mean > 0; book positive in BOTH halves of its virgin window.
"""
import json
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
import math

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
LEDGER = os.path.join(REPO, "reports", "shadow_lab", "ledger.jsonl")
MENU = {
    "V13_DEPTH": {"entry.max_depth_pct": 2.0},
    "MILD_ONLY": {"entry.max_depth_pct": 2.0, "entry.max_spy_dist_pct": 1.5},
    "BAND_WIDE": {"entry.flow_min": 40000, "entry.flow_max": 300000},
    "OPT_WINNER": {"entry.max_depth_pct": 3.0, "exit.stop": -40, "entry.flow_max": 250000},
    "EARLY_CUT": {"exit.early_cut_hours": 2, "exit.early_cut_below": -15},
    # VOLUME hypotheses (owner priority 2026-08-12: "we need improvements and volume").
    # "_vs" picks the comparator book: these differ from the LIVE book by exactly one key,
    # so they are judged against LIVE_SPEC, not the unrouted BASELINE. Both are EXPANSIVE
    # (more trades) - the throughput floor never blocks them.
    "FADE_WHALE": {"entry.flow_max": 1000000, "_vs": "LIVE_SPEC"},
    "BAND_50_400": {"entry.max_spy_dist_pct": 99.0, "_vs": "LIVE_SPEC"},   # = kill the router
    # EXIT exploration (2026-08-12): the one exit variant that maps to an existing live spec
    # key. Trail/TP/time variants are ledger-measured but need a code session to wire.
    "EXIT_STOP40": {"exit.stop": -40, "_vs": "LIVE_SPEC"},
    # SOFT_ROUTER (2026-08-12): widen the mild window 1.5 -> 2.5 if the middle rung earns it.
    "SOFT_ROUTER": {"entry.max_spy_dist_pct": 2.5, "_vs": "LIVE_SPEC"},
}


def spawn_challengers(keys):
    """Respawn the challenger ring around a newly promoted config (owner design 2026-08-21)."""
    steps = {"entry.flow_max": 100000, "entry.flow_min": 20000, "entry.max_spy_dist_pct": 0.5,
             "entry.max_depth_pct": 0.5, "entry.max_spread_pct": 0.5, "exit.stop": 5}
    fmap = {"entry.flow_max": "band_hi", "entry.flow_min": "band_lo",
            "entry.max_spy_dist_pct": "spy_max", "entry.max_spread_pct": "spr_max",
            "exit.stop": "stop"}
    books, menu = {}, {}
    for path, val in keys.items():
        if path.startswith("_") or path not in steps or not isinstance(val, (int, float)):
            continue
        for sgn in (-1, 1):
            nv = round(val + sgn * steps[path], 2)
            nm = "CH_" + path.split(".")[1][:8].upper() + "_" + str(nv).replace(".", "p").replace("-", "m")
            if path in fmap:
                books[nm] = {fmap[path]: nv}
            menu[nm] = {path: nv, "_vs": "CHAMPION"}
    if menu:
        json.dump({"note": "ring respawned " + str(datetime.now(timezone.utc).date()),
                   "books": books, "menu": menu}, open("challengers.json", "w"), indent=1)
    # FULL SWEEP on promotion (owner order 2026-08-21 22:57): every variable at every figure,
    # no assumptions - the finished sweep reseeds the ring with evidence-chosen challengers.
    subprocess.Popen("nohup python3 scripts/variable_sweep.py --reseed >> "
                     "/home/poller/sweep.log 2>&1 &", shell=True)


def tstat(diffs):
    n = len(diffs)
    if n < 3:
        return 0.0
    mu = sum(diffs) / n
    sd = (sum((x - mu) ** 2 for x in diffs) / (n - 1)) ** 0.5
    return mu / (sd / math.sqrt(n)) if sd > 0 else 0.0


def placebo_thr(days_sub, bmap):
    """Empirical 95th-pct t over 200 placebo books on the SAME days (lab v2.1). Fallback 1.83."""
    ts = []
    for p in range(200):
        diffs = []
        for d in days_sub:
            pl = d.get("PL")
            if pl and p < len(pl) and pl[p] is not None and d["day"] in bmap:
                diffs.append(pl[p] - bmap[d["day"]])
        if len(diffs) >= 5:
            ts.append(tstat(diffs))
    if len(ts) < 50:
        return 1.83
    ts.sort()
    return ts[int(len(ts) * 0.95)]


def tg(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass


def tg_or_log(msg):
    if os.environ.get("BOUNDARY_SILENT") == "1":
        print(msg)
    else:
        tg(msg)


def main():
    try:                                              # challenger ring joins the judged menu
        MENU.update(json.load(open("challengers.json")).get("menu") or {})
    except Exception:
        pass
    if not os.path.exists(LEDGER):
        tg_or_log("SUNDAY BOUNDARY: no shadow ledger yet - nothing to review.")
        return
    days = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    seen = {}
    for d in days:
        seen.setdefault(d["day"], {}).update(d)  # MERGE per day (2026-08-14: a META_SELECT-only
                                                 # append was clobbering the day's full book row -
                                                 # every book read 0d on the first Friday boundary)
    days = [seen[k] for k in sorted(seen)]
    base = [(d["day"], d["BASELINE"]["mean"]) for d in days if d.get("BASELINE", {}).get("mean") is not None]
    lines = [f"SUNDAY BOUNDARY {datetime.now(timezone.utc).date()} - virgin days: {len(days)}"]
    if base:
        bm = sum(m for _, m in base) / len(base)
        lines.append(f"BASELINE: {len(base)}d day-mean {bm:+.2f}%")
    # THROUGHPUT FLOOR (owner guard 2026-08-10: refinement must never become starvation).
    # If the live book filled < 3 trades this week WHILE the funnel offered >= 15 qualifying
    # candidates, the system is over-filtered: page it loudly, and block any RESTRICTIVE
    # promotion (adding filters) until throughput recovers. Expansive changes stay allowed.
    RESTRICTIVE = {"V13_DEPTH", "MILD_ONLY", "OPT_WINNER"}
    starving = False
    try:
        recs = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
        import datetime as _dt
        wk_ago = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
        _legs = ["FADE"] + list((json.load(open("fade_book_spec.json")).get("probe") or {}).get("promoted") or [])
        fills_by = {lg: 0 for lg in _legs}
        for r in recs:
            if (r.get("entry_ts_utc") or "") < wk_ago:
                continue
            if r.get("book") in fills_by:
                fills_by[r.get("book")] += 1
            elif r.get("book") == "PROBE" and r.get("probe_strategy") in fills_by:
                fills_by[r.get("probe_strategy")] += 1
        fills = fills_by.get("FADE", 0)
        quals = sum(d.get("BASELINE", {}).get("n") or 0 for d in days if d["day"] >= wk_ago)
        # the _W fivek legs are weekly-cadence and regime-gated: at most 1 fill/week, often
        # legitimately 0 - a promoted one under the daily >=3 floor would false-page every
        # Sunday and block restrictive promotions forever. The floor measures the daily
        # engine's funnel; weekly structures are exempt.
        _breached = ([lg for lg, f in fills_by.items() if not lg.endswith("_W") and f < 3]
                     if quals >= 15 else [])
        if _breached:
            starving = True
            if len(_breached) > 1 or _breached != ["FADE"]:
                lines.append(f"THROUGHPUT (per-leg): breach on {_breached} - promoted legs must "
                             "trade; restrictive promotions blocked until throughput recovers")
        if fills < 3 and quals >= 15:
            starving = True
            lines.append(f"THROUGHPUT FLOOR BREACH: {fills} fills vs {quals} qualifying this week - "
                         "system is over-filtered. Restrictive promotions BLOCKED; investigate the "
                         "newest gate first (funnel skip-reasons name the killer).")
        else:
            lines.append(f"throughput: {fills} fills / {quals} qualifying this week - ok")
    except Exception as _tf:
        lines.append("THROUGHPUT FLOOR DISABLED this run (" + type(_tf).__name__ + ") - the "
                     "never-starve guard did not execute; investigate if it repeats")
    # META-MODEL TRIGGER (owner order 2026-08-11): when the labeled fade cohort reaches 500,
    # page loudly - the selection-brain training session unlocks (code-level, needs a session).
    try:
        con = __import__("sqlite3").connect("file:data/harvest.db?mode=ro", uri=True)
        rows = con.execute("""select c.right, c.spread_pct, c.rule_score, c.features from candidates c
            join labels l on l.candidate_id=c.candidate_id
            where l.outcome is not null and c.features!='' and c.entry_ref>0""").fetchall()
        nco = 0
        for right, spr, score, fj in rows:
            try:
                f = json.loads(fj)
            except Exception:
                continue
            sma = (f.get("macro") or {}).get("distance_to_sma20_pct")
            spy = (f.get("regime_stack") or {}).get("market_spy_dist_pct")
            side = 1 if right == "call" else -1
            if (isinstance(sma, (int, float)) and isinstance(spy, (int, float)) and sma * side < 0
                    and spy * side < 0 and (spr or 99) <= 2.0 and score and 50000 <= score <= 400000):
                nco += 1
        lines.append(f"fade-cohort labels: {nco}/500 toward the meta-model (selection brain)")
        if nco >= 500:
            lines.append(">>> META-MODEL THRESHOLD REACHED - training session unlocked. "
                         "Tell Claude: 'run the fade meta-model' - it trains the Student on the "
                         "fade cohort only and adds P(win) ranking to the lab.")
    except Exception:
        pass
    # DEMOTION SYMMETRY (owner order 2026-08-18): every promoted key is re-checked on its
    # NEXT 10 virgin days vs the same comparator and auto-reverted if the edge died.
    try:
        spec0 = json.load(open("fade_book_spec.json"))
        chg = False
        for ak in [k for k in spec0 if k.startswith("auto_")]:
            av = spec0[ak]
            if not isinstance(av, dict) or av.get("demoted"):
                continue
            pd0 = ak.replace("auto_", "")
            b, vs0 = av.get("book"), av.get("vs", "BASELINE")
            # succession fix (audit finding #8): after promotion the ring respawns and the
            # promoted book's named stream can vanish from the ledger - but CHAMPION replays
            # the LIVE spec nightly, which post-promotion IS the promoted config. Fall back
            # to CHAMPION days so the 10-day demotion watch can never go structurally blind.
            after = []
            for d in days:
                if d["day"] <= pd0:
                    continue
                row = d.get(b) if ((d.get(b) or {}).get("mean") is not None
                                   and (d.get(b) or {}).get("n", 0) > 0) else None
                if row is None:
                    row = (d.get("CHAMPION") if ((d.get("CHAMPION") or {}).get("mean") is not None
                                                 and (d.get("CHAMPION") or {}).get("n", 0) > 0) else None)
                if row is not None:
                    after.append((d["day"], row["mean"]))
            cmpm = {d["day"]: (d.get(vs0) or {}).get("mean") for d in days
                    if (d.get(vs0) or {}).get("mean") is not None}
            dif = [x - cmpm[dd] for dd, x in after if dd in cmpm]
            if len(dif) >= 10 and sum(dif) / len(dif) < 0:
                for path, old in (av.get("prev") or {}).items():
                    sect, key = path.split(".")
                    spec0.setdefault(sect, {})[key] = old
                av["demoted"] = str(datetime.now(timezone.utc).date())
                chg = True
                lines.append(f"DEMOTED {b}: post-promotion mean {sum(dif)/len(dif):+.2f} vs {vs0} "
                             f"over {len(dif)}d - keys reverted (the ratchet turns both ways)")
        if chg:
            json.dump(spec0, open("fade_book_spec.json", "w"), indent=1)
            subprocess.run("git add fade_book_spec.json && git commit -qm 'auto-boundary: demotion - "
                           "promoted keys reverted per post-promotion evidence [skip ci]' && "
                           "git pull -q --rebase -X ours && git push -q", shell=True)
    except Exception as _de:
        lines.append(f"demotion check skipped: {type(_de).__name__}")
    # ANTI-RUBIKS-CUBE (owner question 2026-08-18 15:38): (a) every spec change RESTARTS all
    # other hypotheses' evidence clocks - verdicts are earned against the system AS IT NOW IS,
    # never against a configuration that no longer exists; (b) a key that just changed is
    # frozen 14 calendar days - no oscillation. Changes therefore compound in SERIES.
    # PER-KEY EVIDENCE CLOCKS (Friday batch, owner order 2026-08-23): a spec change now
    # resets ONLY the candidates whose keys it touched. Markers carrying a "keys" dict are
    # per-key; markers without keys stay BLANKET (the 2026-08-19 reset is the last blanket
    # one ever paid). The audit found the old global clock wiped every book's virgin days on
    # any change - the court never saw more than ~4 consecutive days. Fixed at zero
    # specificity cost: an unchanged candidate keeps its accrued evidence.
    blanket_chg = ""
    key_chg = {}
    frozen_keys = set()
    _spec1 = {}
    try:
        _spec1 = json.load(open("fade_book_spec.json"))
        for ak in [k for k in _spec1 if k.startswith("auto_")]:
            av = _spec1[ak] if isinstance(_spec1[ak], dict) else {}
            d0 = ak.replace("auto_", "")
            dd0 = av.get("demoted") or ""
            mk = list((av.get("keys") or {}).keys())
            if mk:
                for k in mk:
                    key_chg[k] = max(key_chg.get(k, ""), d0, dd0)
            else:
                blanket_chg = max(blanket_chg, d0, dd0)
            try:
                from datetime import date as _dt2
                if (_dt2.today() - _dt2.fromisoformat(max(d0, dd0 or d0))).days < 14:
                    frozen_keys.update(mk)
            except Exception:
                pass
    except Exception:
        pass

    def _clock(keys):
        c = blanket_chg
        for k in keys:
            if not k.startswith("_"):
                c = max(c, key_chg.get(k, ""))
        return c

    last_chg = blanket_chg      # legacy readers (demotion audit lines) see the blanket clock
    if last_chg:
        lines.append(f"evidence clock: restarted at last spec change {last_chg}; "
                     f"{len(frozen_keys)} key(s) in cooldown")
    # PROBE-TO-LIVE PROMOTION (owner order 2026-08-23): a PRIORITY probe strategy whose LIVE
    # fills beat the EXEC_BASELINE control on the hardened bar auto-graduates to a recognised
    # live leg (marked promoted, prioritised, paged). Paper size stays $1k until the real-money
    # gate; probation + demotion still apply. Turns "tested positive -> promoted" into a rung.
    try:
        spec_p = json.load(open("fade_book_spec.json"))
        prio = (spec_p.get("probe") or {}).get("priority") or []
        promoted = set((spec_p.get("probe") or {}).get("promoted") or [])
        recs_p = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
        by_strat = {}
        for r in recs_p:
            st_ = r.get("probe_strategy")
            if r.get("book") != "PROBE" or not st_:
                continue
            day = (r.get("entry_ts_utc") or "")[:10]
            ret = None
            for le in (r.get("leg_exits") or {}).values():
                if le.get("return_pct") is not None:
                    ret = le["return_pct"]; break
            if r.get("settle") and r["settle"].get("pnl_usd") is not None:
                ret = (r["settle"]["pnl_usd"] / 1000.0) * 100
            if day and ret is not None:
                by_strat.setdefault(st_, {}).setdefault(day, []).append(ret)

        def daymeans(strat):
            return {d: sum(v) / len(v) for d, v in (by_strat.get(strat) or {}).items()}

        ctrl = daymeans("EXEC_BASELINE")
        if not prio:
            # 2026-08-28 (owner catch): the track sat EMPTY for 4 days after a demotion cleared
            # it - the rung ran nightly checking nothing, silently. An empty promotion track is
            # a state the owner must always see, never infer.
            lines.append("PROMOTION TRACK EMPTY - no probe is being tracked toward "
                         "auto-promotion (probe.priority has no entries)")
        for st_ in prio:
            if st_ in promoted:
                continue
            dm = daymeans(st_)
            shared = sorted(d for d in dm if d in ctrl)
            if len(shared) < 8:
                lines.append(f"PROBE {st_}: {len(shared)}/8 live virgin days vs control - HOLD")
                continue
            diffs = [dm[d] - ctrl[d] for d in shared]
            own = [dm[d] for d in shared]
            # OWNER UPGRADE 2026-08-31 ("is the control right when it caught a monster?"):
            # (a) SYMMETRIC TRIM - with 8+ shared days, drop the single best AND worst diff
            #     day before the t-test. Removes the control's jackpot AND the strategy's own,
            #     so the bar measures CONSISTENCY, not who got lucky once. Never one-sided.
            # (b) ABSOLUTE FLOOR - skill alone is not enough; the strategy's own day-mean must
            #     clear a worth-the-capital floor (spec probe.promotion_floor_day_mean, default
            #     +3%/day on its traded days ~ the owner's 3-6%/month ladder at probe scale).
            tdiffs = sorted(diffs)[1:-1] if len(diffs) >= 8 else diffs
            t = tstat(tdiffs)
            floor = float((spec_p.get("probe") or {}).get("promotion_floor_day_mean", 3.0))
            h = len(own) // 2
            ok = (sum(own) / len(own) >= floor and t >= 1.8 and sum(tdiffs) / max(len(tdiffs), 1) > 0
                  and sum(own[:h]) / max(h, 1) > 0 and sum(own[h:]) / max(len(own) - h, 1) > 0)
            lines.append(f"PROBE {st_}: {len(shared)}d vs control t {t:+.2f} (trimmed) "
                         f"own-mean {sum(own)/len(own):+.1f} (floor {floor:+.0f}) "
                         f"{'PROMOTE' if ok else 'HOLD'}")
            if ok and os.environ.get("BOUNDARY_REPORT_ONLY") != "1":
                spec_p.setdefault("probe", {}).setdefault("promoted", []).append(st_)
                spec_p[f"promo_{datetime.now(timezone.utc).date()}"] = {
                    "strategy": st_, "days": len(shared), "t": round(t, 2),
                    "note": "probe->live leg; paper size unchanged; probation armed"}
                json.dump(spec_p, open("fade_book_spec.json", "w"), indent=1)
                subprocess.run("git add fade_book_spec.json && git commit -qm "
                               "'auto-boundary: probe " + st_ + " PROMOTED to live leg [skip ci]' && "
                               "git pull -q --rebase -X ours && git push -q", shell=True)
                tg(f"PROBE PROMOTION: {st_} beat the control on {len(shared)} live virgin days "
                   f"(t {t:+.2f}) - graduated to a recognised live leg, prioritised. Paper size "
                   f"unchanged; probation armed; real sizing waits for the capital gate.")
                promoted.add(st_)
    except Exception as _pp:
        lines.append(f"probe-promotion check skipped: {type(_pp).__name__}")
    # SENTINEL COURT (Friday batch): judge the known-edge synthetic books with the SAME
    # machinery as real candidates. Their pass/kill times are the court's published operating
    # characteristics; any machinery change must keep P8/P24/N20 inside their windows.
    try:
        _sents = ["SENTINEL_P2", "SENTINEL_P8", "SENTINEL_P24", "SENTINEL_N20",
                  "SENTINEL_C1", "SENTINEL_C2", "SENTINEL_C3", "SENTINEL_C4"]
        _sfile = os.path.join("reports", "shadow_lab", "sentinels.jsonl")
        _prior_pass = set()
        if os.path.exists(_sfile):
            for _l in open(_sfile, encoding="utf-8"):
                try:
                    _j = json.loads(_l)
                    if _j.get("verdict") in ("PASS", "KILL"):
                        _prior_pass.add(_j["book"])
                except Exception:
                    pass
        _bmap_s = {d["day"]: (d.get("BASELINE") or {}).get("mean") for d in days
                   if (d.get("BASELINE") or {}).get("mean") is not None}
        _snew = []
        for _sb in _sents:
            _pts = [(d["day"], d[_sb]["mean"]) for d in days
                    if d.get(_sb, {}).get("mean") is not None and d["day"] in _bmap_s]
            if not _pts:
                continue
            _rel = [x - _bmap_s[d] for d, x in _pts]
            _mu = sum(_rel) / len(_rel)
            _var = sum((x - _mu) ** 2 for x in _rel) / max(len(_rel) - 1, 1)
            _llr = sum(2.0 * (x - 1.0) for x in _rel) / max(_var, 100.0)
            _ds = [dd for dd in days if dd["day"] in {p0 for p0, _ in _pts}]
            _th = placebo_thr(_ds, _bmap_s)
            _tb2 = tstat(_rel)
            _m2 = sum(x for _, x in _pts) / len(_pts)
            _h2 = len(_pts) // 2
            _ok = (len(_rel) >= 5 and _llr >= 2.94 and _tb2 >= _th and _m2 > 0 and _h2 > 0
                   and sum(x for _, x in _pts[:_h2]) / max(_h2, 1) > 0
                   and sum(x for _, x in _pts[_h2:]) / max(len(_pts) - _h2, 1) > 0)
            _kill = len(_rel) >= 5 and _llr <= -2.94
            _vd = "PASS" if _ok else ("KILL" if _kill else "accruing")
            if _vd in ("PASS", "KILL") and _sb in _prior_pass:
                _vd = "settled"
            _snew.append({"run": str(datetime.now(timezone.utc).date()), "book": _sb,
                          "days": len(_pts), "llr": round(_llr, 2), "t": round(_tb2, 2),
                          "thr": round(_th, 2), "verdict": _vd})
            lines.append(f"SENTINEL {_sb}: {len(_pts)}d LLR {_llr:+.2f} t {_tb2:+.2f} "
                         f"thr {_th:.2f} -> {_vd}")
        if _snew:
            os.makedirs(os.path.dirname(_sfile), exist_ok=True)
            with open(_sfile, "a", encoding="utf-8") as _f:
                for _j in _snew:
                    _f.write(json.dumps(_j) + chr(10))
    except Exception as _se:
        lines.append(f"sentinel court skipped: {type(_se).__name__}")

    # EVIDENCE ODOMETER (Friday batch): accrued judgeable days per candidate - the one number
    # that says whether the learning loop is running. If accrued days stop growing, the lab
    # is not learning regardless of how good the strategies are.
    try:
        lines.append("--- EVIDENCE ODOMETER ---")
        for book, keys in MENU.items():
            _ck2 = _clock(keys)
            _tot = sum(1 for d in days if d.get(book, {}).get("mean") is not None)
            _acc = sum(1 for d in days if d.get(book, {}).get("mean") is not None
                       and d["day"] > _ck2)
            if _tot:
                lines.append(f"  {book}: {_acc} judgeable d (clock {_ck2 or 'epoch'}, "
                             f"{_tot - _acc} behind clock)")
        _bf = os.path.join("reports", "shadow_lab", "breaker.jsonl")
        if os.path.exists(_bf):
            _bl = [json.loads(x) for x in open(_bf, encoding="utf-8") if x.strip()]
            if _bl:
                lines.append(f"  fade bear-regime days available in 2026: "
                             f"{_bl[-1].get('bear_days_2026', '?')} "
                             f"(fade evidence accrues ONLY on these)")
    except Exception as _oe:
        lines.append(f"odometer skipped: {type(_oe).__name__}")

    applied = []
    traj = []
    for book, keys in MENU.items():
        if any(k in frozen_keys for k in keys if not k.startswith("_")):
            lines.append(f"{book}: COOLDOWN (touches a key changed <14d ago)")
            continue
        if starving and book in RESTRICTIVE:
            lines.append(f"{book}: SKIPPED (throughput floor breach - no new restrictions while starving)")
            continue
        vs = keys.get("_vs", "BASELINE")
        _ck = _clock(keys)
        pts = [(d["day"], d[book]["mean"]) for d in days
               if d.get(book, {}).get("mean") is not None and d[book].get("n", 0) > 0
               and d["day"] > _ck]
        bmap = {d: v for d, v in ((dd["day"], (dd.get(vs) or {}).get("mean")) for dd in days)
                if v is not None}
        rel = [x - bmap[d] for d, x in pts if d in bmap]
        # SEQUENTIAL VERDICT (owner order 2026-08-18): SPRT on daily book-minus-comparator
        # diffs (H1: +2pts/day). Decisive evidence passes from day 5; ambiguity falls back
        # to the fixed 10-day bars; LLR <= -2.94 is an early honest reject.
        llr = 0.0
        if len(rel) >= 3:
            mu = sum(rel) / len(rel)
            var = sum((x - mu) ** 2 for x in rel) / max(len(rel) - 1, 1)
            s2 = max(var, 100.0)   # audit v2 repair 2026-08-19: sample variance from 5 days
            # underestimates truth on exactly the lucky windows that false-promote
            # (sim fingerprint: median s2 112 vs true 225 at false passes). Floor 100
            # until the e-process rebuild makes the boundary variance-honest.
            llr = sum(2.0 * (x - 1.0) for x in rel) / s2
        if pts:
            m = sum(x for _, x in pts) / len(pts)
            _h = len(pts) // 2
            _e0 = sum(x for _, x in pts[:_h]) / max(_h, 1)
            _l0 = sum(x for _, x in pts[_h:]) / max(len(pts) - _h, 1)
            traj.append(f"{datetime.now(timezone.utc).date()} {book}: {len(pts)}d mean {m:+.2f} "
                        f"LLR {llr:+.2f} halves {_e0:+.1f}/{_l0:+.1f} vs {vs}")
        _dsub = [dd for dd in days if dd["day"] in {p0 for p0, _ in pts}]
        _thr = placebo_thr(_dsub, bmap)
        _tb = tstat(rel)
        if len(rel) >= 5 and llr >= 2.94 and _tb >= _thr and pts:
            _h = len(pts) // 2
            _e1 = sum(x for _, x in pts[:_h]) / max(_h, 1)
            _l1 = sum(x for _, x in pts[_h:]) / max(len(pts) - _h, 1)
            if m > 0 and _e1 > 0 and _l1 > 0:
                lines.append(f"{book}: SEQUENTIAL PASS at {len(pts)}d (LLR {llr:+.2f}) vs {vs}")
                if (os.environ.get("BOUNDARY_REPORT_ONLY") == "1"
                        and os.environ.get("BOUNDARY_SEQ_APPLY") != "1"):
                    lines.append(f">>> {book} passes SEQUENTIALLY - application deferred (report-only)")
                    continue          # owner order 2026-08-18 15:35: nightly runs set SEQ_APPLY -
                                      # a proven edge calibrates THAT NIGHT, not on a weekday
                # LIVE-WIRED WHITELIST (audit finding #9): refuse to promote a key the engine
                # does not actually read - a decorative promotion looks like a calibration but
                # changes nothing, poisoning the evidence clock it restarts.
                LIVE_WIRED = {"entry.flow_min", "entry.flow_max", "entry.max_spread_pct",
                              "entry.max_spy_dist_pct", "entry.max_depth_pct",
                              "entry.regime_router", "exit.stop", "exit.max_hold_days",
                              "exit.early_cut_hours", "exit.early_cut_below",
                              "exit.trail_activate", "exit.trail_drawdown"}
                _unwired = [k for k in keys if not k.startswith("_") and k not in LIVE_WIRED]
                if _unwired:
                    lines.append(">>> " + book + " PASSES but touches non-live-wired key(s) "
                                 + str(_unwired) + " - promotion REFUSED until the key is wired")
                    continue
                if not applied:
                    spec = json.load(open("fade_book_spec.json"))
                    prev = {}
                    for path, val in keys.items():
                        if path.startswith("_"):
                            continue
                        sect, key = path.split(".")
                        prev[path] = spec.get(sect, {}).get(key)
                        spec.setdefault(sect, {})[key] = val
                    spec[f"auto_{datetime.now(timezone.utc).date()}"] = {
                        "book": book, "vs": vs, "prev": prev,
                        "keys": {k: v for k, v in keys.items() if not k.startswith("_")},
                        "mode": "sequential"}
                    json.dump(spec, open("fade_book_spec.json", "w"), indent=1)
                    spawn_challengers(keys)
                    subprocess.run("git add fade_book_spec.json challengers.json && git commit -qm "
                                   "'auto-boundary: " + book + " promoted (sequential) [skip ci]' && "
                                   "git pull -q --rebase -X ours && git push -q", shell=True)
                    applied.append(book)
                    lines.append(f">>> APPLIED {book} (sequential verdict)")
                    tg(f"NIGHTLY PROMOTION: {book} proved its edge sequentially (LLR {llr:+.2f}, "
                       f"{len(pts)}d) and the spec recalibrated NOW. Prior values stored; "
                       f"demotion watch armed on its next 10 virgin days.")   # pages even in silent mode
                continue
        if len(rel) >= 5 and llr <= -2.94:
            lines.append(f"{book}: SPRT REJECT at {len(pts)}d (LLR {llr:+.2f}) - losing vs {vs}")
            continue
        if len(pts) < 10:
            lines.append(f"{book}: {len(pts)}d traded - HOLD (needs 10, LLR {llr:+.2f})")
            continue
        m = sum(x for _, x in pts) / len(pts)
        half = len(pts) // 2
        e = sum(x for _, x in pts[:half]) / max(half, 1)
        l2 = sum(x for _, x in pts[half:]) / max(len(pts) - half, 1)
        ok = (m > 0 and rel and _tb >= _thr and e > 0 and l2 > 0)   # lab v2.1: t-unit bar vs
        lines.append(f"{book}: {len(pts)}d mean {m:+.2f}% t {_tb:+.2f} vs placebo-thr "
                     f"{_thr:.2f} ({vs}) {'PASS' if ok else 'HOLD'}")   # 200-placebo empirical null
        try:                                     # 2y corpus prior beside every verdict - ADVISORY
            pri = json.load(open("reports/research/historical_corpus_2026-08-13/corpus_priors.json"))
            cp = pri.get(book)
            if cp:
                lines.append(f"   corpus prior 2y: {cp['day_mean']:+.2f}% t={cp['t']} over "
                             f"{cp['days']}d (advisory - virgin days decide)")
        except Exception:
            pass
        if ok and os.environ.get("BOUNDARY_REPORT_ONLY") == "1":
            lines.append(f">>> {book} PASSES its bars - application deferred to Sunday (report-only run)")
            continue
        if ok and not applied:                  # apply at most ONE upgrade per Sunday
            spec = json.load(open("fade_book_spec.json"))
            prev = {}
            for path, val in keys.items():
                if path.startswith("_"):
                    continue                    # "_vs" is boundary metadata, never a spec key
                sect, key = path.split(".")
                prev[path] = spec.get(sect, {}).get(key)
                spec.setdefault(sect, {})[key] = val
            v = spec.get("spec_version", "1.2")
            spec["spec_version"] = v + "+auto"
            spec[f"auto_{datetime.now(timezone.utc).date()}"] = {
                "book": book, "vs": vs, "prev": prev,
                "keys": {k: v2 for k, v2 in keys.items() if not k.startswith("_")}, "mode": "fixed"}
            json.dump(spec, open("fade_book_spec.json", "w"), indent=1)
            spawn_challengers(keys)
            subprocess.run("git add fade_book_spec.json challengers.json && git commit -qm "
                           "'auto-boundary: " + book + " promoted per pre-registered bars [skip ci]' && "
                           "git pull -q --rebase -X ours && git push -q", shell=True)
            applied.append(book)
            lines.append(f">>> APPLIED {book} to the live spec (data-only change; engine reads it next cycle)")
    if not applied:
        lines.append("No upgrade passed its bars - spec unchanged. The grind continues honestly.")
    # DEFERRAL AUDIT (owner order 2026-08-18): measured cost of the no-same-day-sell rule.
    try:
        _lg = json.load(open("proactive_sandbox_logs.json"))
        _da = []
        for r in _lg:
            for ln2, pth in (r.get("leg_path") or {}).items():
                if pth.get("pdt_deferred") and (r.get("leg_exits") or {}).get(ln2):
                    fin = r["leg_exits"][ln2].get("return_pct")
                    mfe = pth.get("mfe_pct")
                    if fin is not None and mfe is not None:
                        _da.append((r.get("ticker"), pth["pdt_deferred"], round(mfe - fin, 1), fin))
        if _da:
            _tot = sum(x[2] for x in _da)
            lines.append(f"DEFERRAL AUDIT: {len(_da)} held-over exits; peak-vs-final giveback "
                         f"{_tot:+.0f}pts total; worst: " +
                         ", ".join(f"{t} {a} gave {g:+.0f} (final {f:+.0f}%)" for t, a, g, f in
                                   sorted(_da, key=lambda x: -x[2])[:3]))
    except Exception:
        pass
    try:
        os.makedirs("reports/shadow_lab", exist_ok=True)
        with open("reports/shadow_lab/trajectory.log", "a", encoding="utf-8") as _tf:
            _tf.write(chr(10).join(traj) + chr(10))
    except Exception:
        pass
    tg_or_log("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()

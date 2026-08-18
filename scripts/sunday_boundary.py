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
        fills = sum(1 for r in recs if r.get("book") == "FADE" and (r.get("entry_ts_utc") or "") >= wk_ago)
        quals = sum(d.get("BASELINE", {}).get("n") or 0 for d in days if d["day"] >= wk_ago)
        if fills < 3 and quals >= 15:
            starving = True
            lines.append(f"THROUGHPUT FLOOR BREACH: {fills} fills vs {quals} qualifying this week - "
                         "system is over-filtered. Restrictive promotions BLOCKED; investigate the "
                         "newest gate first (funnel skip-reasons name the killer).")
        else:
            lines.append(f"throughput: {fills} fills / {quals} qualifying this week - ok")
    except Exception:
        pass
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
            after = [(d["day"], d[b]["mean"]) for d in days
                     if d["day"] > pd0 and (d.get(b) or {}).get("mean") is not None and d[b].get("n", 0) > 0]
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
    last_chg = ""
    frozen_keys = set()
    try:
        spec1 = json.load(open("fade_book_spec.json"))
        cutoff = (datetime.now(timezone.utc).date() - __import__("datetime").timedelta(days=14)).isoformat()
        for ak in [k for k in spec1 if k.startswith("auto_")]:
            av = spec1[ak]
            d0 = ak.replace("auto_", "")
            dd0 = av.get("demoted") if isinstance(av, dict) else None
            last_chg = max(last_chg, d0, dd0 or "")
            if isinstance(av, dict) and (d0 >= cutoff or (dd0 or "") >= cutoff):
                frozen_keys.update((av.get("keys") or {}).keys())
    except Exception:
        pass
    if last_chg:
        lines.append(f"evidence clock: restarted at last spec change {last_chg}; "
                     f"{len(frozen_keys)} key(s) in cooldown")
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
        pts = [(d["day"], d[book]["mean"]) for d in days
               if d.get(book, {}).get("mean") is not None and d[book].get("n", 0) > 0
               and d["day"] > last_chg]
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
            s2 = max(var, 25.0)
            llr = sum(2.0 * (x - 1.0) for x in rel) / s2
        if pts:
            m = sum(x for _, x in pts) / len(pts)
            _h = len(pts) // 2
            _e0 = sum(x for _, x in pts[:_h]) / max(_h, 1)
            _l0 = sum(x for _, x in pts[_h:]) / max(len(pts) - _h, 1)
            traj.append(f"{datetime.now(timezone.utc).date()} {book}: {len(pts)}d mean {m:+.2f} "
                        f"LLR {llr:+.2f} halves {_e0:+.1f}/{_l0:+.1f} vs {vs}")
        if len(rel) >= 5 and llr >= 2.94 and pts:
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
                    subprocess.run("git add fade_book_spec.json && git commit -qm 'auto-boundary: "
                                   + book + " promoted (sequential) [skip ci]' && "
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
        ok = (m > 0 and rel and sum(rel) / len(rel) > 2.0 and e > 0 and l2 > 0)
        lines.append(f"{book}: {len(pts)}d mean {m:+.2f}% vs {vs} {'PASS' if ok else 'HOLD'}")
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
            subprocess.run("git add fade_book_spec.json && git commit -qm 'auto-boundary: "
                           + book + " promoted per pre-registered bars [skip ci]' && "
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

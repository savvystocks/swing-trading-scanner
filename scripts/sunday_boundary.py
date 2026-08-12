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
}


def tg(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass


def main():
    if not os.path.exists(LEDGER):
        tg("SUNDAY BOUNDARY: no shadow ledger yet - nothing to review.")
        return
    days = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    seen = {}
    for d in days:
        seen[d["day"]] = d                      # last write per day wins
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
    applied = []
    for book, keys in MENU.items():
        if starving and book in RESTRICTIVE:
            lines.append(f"{book}: SKIPPED (throughput floor breach - no new restrictions while starving)")
            continue
        vs = keys.get("_vs", "BASELINE")
        pts = [(d["day"], d[book]["mean"]) for d in days
               if d.get(book, {}).get("mean") is not None and d[book].get("n", 0) > 0]
        if len(pts) < 10:
            lines.append(f"{book}: {len(pts)}d traded - HOLD (needs 10)")
            continue
        m = sum(x for _, x in pts) / len(pts)
        bmap = {d: v for d, v in ((dd["day"], (dd.get(vs) or {}).get("mean")) for dd in days)
                if v is not None}
        rel = [x - bmap[d] for d, x in pts if d in bmap]
        half = len(pts) // 2
        e = sum(x for _, x in pts[:half]) / max(half, 1)
        l2 = sum(x for _, x in pts[half:]) / max(len(pts) - half, 1)
        ok = (m > 0 and rel and sum(rel) / len(rel) > 2.0 and e > 0 and l2 > 0)
        lines.append(f"{book}: {len(pts)}d mean {m:+.2f}% vs {vs} {'PASS' if ok else 'HOLD'}")
        if ok and os.environ.get("BOUNDARY_REPORT_ONLY") == "1":
            lines.append(f">>> {book} PASSES its bars - application deferred to Sunday (report-only run)")
            continue
        if ok and not applied:                  # apply at most ONE upgrade per Sunday
            spec = json.load(open("fade_book_spec.json"))
            for path, val in keys.items():
                if path.startswith("_"):
                    continue                    # "_vs" is boundary metadata, never a spec key
                sect, key = path.split(".")
                spec.setdefault(sect, {})[key] = val
            v = spec.get("spec_version", "1.2")
            spec["spec_version"] = v + "+auto"
            spec[f"auto_{datetime.now(timezone.utc).date()}"] = f"{book} passed pre-registered bars"
            json.dump(spec, open("fade_book_spec.json", "w"), indent=1)
            subprocess.run("git add fade_book_spec.json && git commit -qm 'auto-boundary: "
                           + book + " promoted per pre-registered bars [skip ci]' && "
                           "git pull -q --rebase -X ours && git push -q", shell=True)
            applied.append(book)
            lines.append(f">>> APPLIED {book} to the live spec (data-only change; engine reads it next cycle)")
    if not applied:
        lines.append("No upgrade passed its bars - spec unchanged. The grind continues honestly.")
    tg("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()

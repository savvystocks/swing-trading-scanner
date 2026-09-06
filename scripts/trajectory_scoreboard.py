"""TRAJECTORY SCOREBOARD (owner order 2026-09-06: the graph that says we're heading right).

The paper account line is not the scoreboard: it carries V10's tuition forever and blends
the discovery tier's deliberate losses with the strategies earning promotion. This splits
realized P&L into the three lines that mean something:
  PRIORITY   - the 8 priority strategies + the weekly structures: the curve that must rise.
  DISCOVERY  - every other audition-era probe incl. the EXEC_BASELINE control: tuition;
               must stay small and flat.
  V10 LEGACY - records entered before the 2026-08-05 audition reset: frozen history.
Realized exits only (leg_exits return_pct on the recorded entry premium) - open marks can
flatter a curve, so they are reported as a footnote count, never drawn. Known caveat: entry
premiums are decision marks until the fill-honesty fix ships; consistent across cohorts.
Output: reports/research/trajectory_scoreboard.json + a compact weekly Telegram.
Cron: Friday 22:25 UTC. Sentinel row ships in the same commit (registry rule)."""
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

AUDITION_ERA = "2026-08-05"
PRIORITY = {"CREDIT_SPREAD_W", "DIP_CONVEXITY", "BULL_DIP", "CONSENSUS_CALLS", "FOLLOW_CALLS",
            "DIP_CONF_MILD", "PUT_DEBIT_W", "BULL_DIP_X", "FADE", "FADE_BEAR", "PUTW_WEEKLY"}


def leg_pnl(rec):
    out = []
    legs = rec.get("legs") or {}
    for lname, ex in (rec.get("leg_exits") or {}).items():
        if not isinstance(ex, dict):
            continue
        lg = legs.get(lname) or {}
        ep = lg.get("entry_premium")
        n = lg.get("contracts") or 1
        rp = ex.get("return_pct")
        d = (ex.get("closed_at") or "")[:10]
        if ep and rp is not None and d:
            out.append((d, ep * 100 * n * rp / 100.0))
    st = rec.get("settle") or {}
    if isinstance(st, dict):
        p = st.get("pnl_usd", st.get("pnl"))
        d = (str(st.get("at") or st.get("date") or ""))[:10]
        if p is not None and d:
            out.append((d, float(p)))
    return out


def main():
    log = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
    daily = {"priority": defaultdict(float), "discovery": defaultdict(float), "legacy": defaultdict(float)}
    open_counts = {"priority": 0, "discovery": 0, "legacy": 0}
    skipped = 0
    for r in log:
        entered = (r.get("entry_ts_utc") or r.get("timestamp") or "")[:10]
        strat = r.get("probe_strategy") or r.get("set_type") or ""
        if entered and entered < AUDITION_ERA:
            cohort = "legacy"
        elif strat in PRIORITY or str(strat).endswith("_W"):
            cohort = "priority"
        else:
            cohort = "discovery"
        if r.get("status") == "OPEN":
            open_counts[cohort] += 1
        rows = leg_pnl(r)
        if not rows and r.get("status") == "CLOSED":
            skipped += 1
        for d, p in rows:
            daily[cohort][d] += p
    series = {}
    latest = {}
    for cohort, dd in daily.items():
        cum, out = 0.0, []
        for d in sorted(dd):
            cum += dd[d]
            out.append([d, round(cum)])
        series[cohort] = out
        latest[cohort] = round(cum)
    days = sorted(set(daily["priority"]) | set(daily["discovery"]))
    last7 = days[-5:]
    week = {c: round(sum(daily[c][d] for d in last7 if d in daily[c])) for c in ("priority", "discovery")}
    out = {"generated": days[-1] if days else "", "series": series, "latest": latest,
           "week": week, "open_counts": open_counts, "closed_without_pnl": skipped,
           "note": "realized exits only; entry premiums are decision marks until the fill-honesty fix"}
    json.dump(out, open("reports/research/trajectory_scoreboard.json", "w", encoding="utf-8"), indent=1)
    msg = ("TRAJECTORY SCOREBOARD (realized, cumulative):\n"
           f"PRIORITY book: ${latest.get('priority', 0):+,} lifetime, ${week.get('priority', 0):+,} this week "
           f"({open_counts['priority']} open)\n"
           f"DISCOVERY tuition: ${latest.get('discovery', 0):+,} lifetime, ${week.get('discovery', 0):+,} this week "
           f"({open_counts['discovery']} open)\n"
           f"V10 legacy (frozen): ${latest.get('legacy', 0):+,}\n"
           "Right direction = PRIORITY rising while DISCOVERY stays small and flat.")
    print(msg, flush=True)
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat and os.environ.get("SCOREBOARD_DRY") != "1":
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass
    print("SCOREBOARD COMPLETE", flush=True)


if __name__ == "__main__":
    main()

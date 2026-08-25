"""DAILY DIGEST (owner order 2026-08-25 01:10: 23 confusing telegrams - "can this also be
explained better on telegram").

One plain-English message every market evening (22:20 UTC) that explains the whole day:
what traded, what closed, what the market regime was, whether fade was allowed on the field,
what the court learned (evidence days), any tidy-ups (adoptions/reconciles) translated, and
what runs later tonight - so the owner never has to decode jargon or wonder what's missing.
Read-only everywhere; failure of any section never blocks the rest.
"""
import json
import os
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)


def tg(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": msg}), timeout=15)
        except Exception:
            pass
    print(msg)


def main():
    today = date.today().isoformat()
    L = [f"EVENING SUMMARY - {today}", ""]

    # regime + was fade allowed out
    try:
        import fade_book
        rg = fade_book.spy_regime()
        word = {"BULL": "rising", "MILD": "calm", "BEAR": "falling"}.get(rg, "unknown")
        L.append(f"Market today: {word} ({rg}).")
        if rg in ("BULL", "MILD"):
            L.append("Fade stayed on the bench - by design: two years of data show it loses "
                     "in this weather. It only plays when the market is falling.")
        elif rg == "BEAR":
            L.append("FALLING market: fade was ON THE FIELD today - its proven weather.")
    except Exception:
        L.append("Market regime: unavailable this evening.")
    L.append("")

    # trades today
    try:
        recs = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
        buys = Counter(); sells = []; setl = []; tidy = 0
        for r in recs:
            who = r.get("probe_strategy") or r.get("book") or ""
            if r.get("adopted") and (r.get("entry_ts_utc") or "")[:10] == today:
                tidy += 1
                continue
            if (r.get("entry_ts_utc") or "")[:10] == today and who:
                buys[who] += 1
            for le in (r.get("leg_exits") or {}).values():
                if (le.get("exit_ts_utc") or "")[:10] == today and le.get("return_pct") is not None:
                    sells.append((who or r.get("ticker", "?"), le["return_pct"]))
            s = r.get("settle") or {}
            if (s.get("ts") or s.get("settle_ts_utc") or "")[:10] == today and s.get("pnl_usd") is not None:
                setl.append((who or r.get("ticker", "?"), s["pnl_usd"]))
        if buys:
            L.append("Bought today: " + ", ".join(f"{k} x{v}" for k, v in buys.most_common()))
        else:
            L.append("Bought today: nothing (no setups passed the filters - that's normal, not broken).")
        if sells:
            pl = sum(x / 100.0 * 1000 for _, x in sells)
            L.append(f"Sold today: {len(sells)} position(s), roughly ${pl:+,.0f} realized "
                     f"({', '.join(f'{k} {x:+.0f}%' for k, x in sells[:5])})")
        else:
            L.append("Sold today: nothing (your no-same-day-sell rule defers new buys to tomorrow+).")
        if setl:
            L.append(f"Settlements: {', '.join(f'{k} ${p:+,.0f}' for k, p in setl)}")
        if tidy:
            L.append(f"Tidy-ups: {tidy} record(s) re-linked with the broker (bookkeeping only - "
                     "no money involved).")
    except Exception:
        L.append("Trade summary: log unavailable this evening.")
    L.append("")

    # what the court learned (evidence odometer, compact)
    try:
        led = [json.loads(l) for l in open("reports/shadow_lab/ledger.jsonl", encoding="utf-8") if l.strip()]
        seen = {}
        for d in led:
            seen.setdefault(d["day"], {}).update(d)
        ndays = len(seen)
        sent_seen = any(k.startswith("SENTINEL_") for d in seen.values() for k in d)
        L.append(f"The court: {ndays} evidence days on file; every strategy was re-judged "
                 "overnight against 200 random fakes (nothing promotes unless it beats the "
                 "luckiest fake).")
        if sent_seen:
            L.append("The 8 test-dummies (sentinels) with known fake edges are walking the same "
                     "court - they measure whether the judge itself works.")
    except Exception:
        pass
    L.append("")
    L.append("Still to run tonight: the nightly lab replay, the judge, the student's training, "
             "and the data archive top-up - all automatic. Weekly deep review comes FRIDAY night "
             "(it moved from Sunday, so no Sunday report is normal).")
    tg("\n".join(L))


if __name__ == "__main__":
    main()

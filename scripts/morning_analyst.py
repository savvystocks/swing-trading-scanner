"""MORNING ANALYST (owner order 2026-09-07, adopted from the agent-course mapping: the one
pattern worth stealing - an LLM that reads structured evidence and writes a plain-English
routed judgment).

Every weekday morning after the freshness sentinel, this composes a brief from COMMITTED
OUTPUTS ONLY - last night's boundary verdict, the latest sentinel reading, the scoreboard
state, yesterday's record activity - and telegrams the kind of plain-English update the
owner otherwise gets only in a session. Monitoring tier: reads only, never trades, never
touches the spec. Guardrails: the model may summarize ONLY the provided data, never invent
numbers, and the raw source lines ride along beneath the prose so every claim is checkable.
Fail LOUD (2026-09-07 messenger lesson): an analyst that cannot produce a brief telegrams
its failure - silence is never normal. Model: Gemini Flash free tier (one call/day, GBP 0).
Cron: 08:10 UTC weekdays. Sentinel row ships in the same commit (registry rule)."""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
H = "/home/poller"


def tail(path, n=25):
    try:
        return "".join(open(path, encoding="utf-8", errors="ignore").readlines()[-n:])
    except Exception as e:
        return f"(unavailable: {e})"


def gather():
    parts = [f"DATE: {datetime.now(timezone.utc):%A %Y-%m-%d %H:%M} UTC"]
    parts.append("== LAST NIGHTLY BOUNDARY (court verdict) ==\n" + tail(H + "/trajectory_nightly.log", 20))
    parts.append("== FRESHNESS SENTINEL (this morning) ==\n" + tail(H + "/freshness.log", 12))
    try:
        sb = json.load(open("reports/research/trajectory_scoreboard.json", encoding="utf-8"))
        parts.append("== TRAJECTORY SCOREBOARD (last Friday) ==\n" +
                     json.dumps({k: sb.get(k) for k in ("latest", "week", "open_counts")}, indent=1))
    except Exception:
        pass
    try:
        log = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
        yday = None
        for r in reversed(log):
            d = (r.get("entry_ts_utc") or "")[:10]
            if d and d < date.today().isoformat():
                yday = d
                break
        if yday:
            opens = [f"{r.get('probe_strategy') or r.get('set_type')}/{r.get('ticker')}"
                     for r in log if (r.get("entry_ts_utc") or "")[:10] == yday]
            closes = []
            for r in log:
                for ex in (r.get("leg_exits") or {}).values():
                    if isinstance(ex, dict) and (ex.get("closed_at") or "")[:10] == yday:
                        closes.append(f"{r.get('probe_strategy') or r.get('set_type')}/"
                                      f"{r.get('ticker')} {ex.get('return_pct')}%")
            parts.append(f"== LAST TRADING DAY ({yday}) ==\nENTRIES: " + (", ".join(opens) or "none")
                         + "\nEXITS: " + (", ".join(closes) or "none"))
    except Exception as e:
        parts.append(f"== RECORDS == (unavailable: {e})")
    return "\n\n".join(parts)


PROMPT = """You are the morning analyst for the owner of an automated options trading lab.
Write his morning brief in plain English - warm, direct, no jargon walls, no markdown, no
emojis, 8-13 sentences. RULES: use ONLY the data below; never invent or extrapolate numbers;
if a section is unavailable, say so in one clause and move on; lead with what matters most
(court verdicts, anything stale, notable exits); end with what today's rhythm brings. The
owner knows the system - PRIORITY book vs DISCOVERY tuition, the courts, the sentinel.

DATA:
"""


def gemini(text):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    body = json.dumps({"contents": [{"parts": [{"text": text}]}],
                       "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2000,
                                            "thinkingConfig": {"thinkingBudget": 0}}}).encode()
    # thinkingBudget 0: flash models otherwise spend the output budget on hidden reasoning
    # tokens and truncate the visible brief mid-sentence (found in the 2026-09-07 test)
    import time
    errs = []
    for model in ("gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3-flash-preview"):
        for attempt in range(3):        # 503/429 are demand spikes - back off, don't give up
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    j = json.load(r)
                return j["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as e:
                errs.append(f"{model}: HTTP {e.code}")
                if e.code in (429, 503) and attempt < 2:
                    time.sleep(20 * (attempt + 1))
                    continue
                break
            except Exception as e:
                errs.append(f"{model}: {e!r:.80}")
                break
    raise RuntimeError("gemini failed: " + " | ".join(errs)[:300])


def telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        print("TELEGRAM ENV MISSING", flush=True)
        return False
    import time
    for i in range(3):
        try:
            urllib.request.urlopen("https://api.telegram.org/bot" + tok + "/sendMessage?" +
                                   urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}),
                                   timeout=20)
            return True
        except Exception as e:
            print(f"send attempt {i + 1} failed: {e!r:.100}", flush=True)
            time.sleep(15 * (i + 1))
    return False


def main():
    marker = "[TEST] " if os.environ.get("ANALYST_TEST") == "1" else ""
    try:
        data = gather()
        brief = gemini(PROMPT + data)
        ok = telegram(marker + "MORNING ANALYST\n\n" + brief)
        print(("SENT" if ok else "SEND FAILED") + f" ({len(brief)} chars)", flush=True)
        if not ok:
            sys.exit(1)
    except Exception as e:
        telegram(marker + f"MORNING ANALYST FAILED: {e!r:.200} - no brief today; the data itself "
                 "is unaffected (this is the messenger, not the machine).")
        print(f"ANALYST FAILED: {e!r}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

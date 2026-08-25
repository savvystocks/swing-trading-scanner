"""SHADOW CIRCUIT BREAKER (owner order 2026-08-23: "do the breaker then but a shadow breaker
so it doesnt stop the trading but can learn from it").

READ-ONLY. Never touches the trade path, never blocks an entry. Each night it replays the
fade-family's closed trades and asks: if a breaker had stood down after N consecutive stop-outs
inside one BEAR EPISODE (SPY < -2% vs its 50d SMA; a gap of >5 days starts a new episode),
which trades would it have blocked, and what P&L would that have saved or cost?

Three candidate settings run side by side (N = 2, 3, 4). By the time real money arrives
(~October gate), the ledger says which N earns its place - the breaker goes live pre-tested
instead of designed during a crash.

Output: one JSON line per run -> reports/shadow_lab/breaker.jsonl (committed by the nightly
persist like everything else). Books covered: FADE (live) + FADE_UNROUTED/FADE_WHALE/FADE_DP.
"""
import json
import os
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
OUT = os.path.join(REPO, "reports", "shadow_lab", "breaker.jsonl")
STOP_OUT = -45.0          # a closed return at/below this counts as a stop-out
FADE_BOOKS = {"FADE"}
FADE_PROBES = {"FADE_UNROUTED", "FADE_WHALE", "FADE_DP"}


def spy_regime_series():
    """day -> SPY dist vs 50d SMA (%). Fail-open: {} on any error."""
    k1 = os.environ.get("ALPACA_PAPER_API_KEY")
    k2 = os.environ.get("ALPACA_PAPER_SECRET_KEY")
    if not (k1 and k2):
        return {}
    from datetime import timedelta
    _start = (date.today() - timedelta(days=400)).isoformat()   # rolling (audit 2026-08-25)
    u = ("https://data.alpaca.markets/v2/stocks/bars?symbols=SPY&timeframe=1Day"
         f"&start={_start}&limit=400&adjustment=split&feed=iex")
    try:
        req = urllib.request.Request(u, headers={"APCA-API-KEY-ID": k1, "APCA-API-SECRET-KEY": k2})
        with urllib.request.urlopen(req, timeout=20) as r:
            bars = (json.loads(r.read()).get("bars") or {}).get("SPY") or []
    except Exception:
        return {}
    out, buf = {}, []
    for b in bars:
        buf.append(b["c"])
        sma = sum(buf[-50:]) / min(len(buf), 50)
        out[b["t"][:10]] = (b["c"] / sma - 1) * 100
    return out


def main():
    try:
        recs = json.load(open("proactive_sandbox_logs.json", encoding="utf-8"))
    except Exception as e:
        print(f"shadow-breaker: no log readable ({type(e).__name__}) - skipping")
        return
    trades = []
    for r in recs:
        is_fade = (r.get("book") in FADE_BOOKS) or (r.get("book") == "PROBE"
                                                    and r.get("probe_strategy") in FADE_PROBES)
        if not is_fade:
            continue
        day = (r.get("entry_ts_utc") or "")[:10]
        if not day:
            continue
        for le in (r.get("leg_exits") or {}).values():
            if le.get("return_pct") is not None:
                trades.append({"day": day, "ts": r.get("entry_ts_utc"),
                               "ret": le["return_pct"],
                               "who": r.get("probe_strategy") or r.get("book")})
                break
    spy = spy_regime_series()
    bear_days = sorted(d for d, v in spy.items() if v < -2.0)
    # bear episodes
    eps = []
    cur = []
    for d in bear_days:
        if cur and (date.fromisoformat(d) - date.fromisoformat(cur[-1])).days > 5:
            eps.append(cur)
            cur = []
        cur.append(d)
    if cur:
        eps.append(cur)
    ep_of = {}
    for i, e in enumerate(eps):
        for d in e:
            ep_of[d] = i

    verdicts = {}
    for N in (2, 3, 4):
        blocked, blocked_pnl, tripped_eps = 0, 0.0, set()
        streak = defaultdict(int)
        for t in sorted(trades, key=lambda x: x["ts"] or ""):
            ep = ep_of.get(t["day"])
            if ep is None:
                continue                       # breaker only lives inside bear episodes
            if streak[ep] >= N:
                blocked += 1
                blocked_pnl += t["ret"] / 100.0 * 1000
                tripped_eps.add(ep)
                continue
            if t["ret"] <= STOP_OUT:
                streak[ep] += 1
            else:
                streak[ep] = 0
        verdicts[f"N{N}"] = {"blocked": blocked, "blocked_pnl_usd": round(blocked_pnl, 2),
                             "saved_usd": round(-blocked_pnl, 2), "episodes_tripped": len(tripped_eps)}
    line = {"run": datetime.now(timezone.utc).isoformat()[:16],
            "fade_trades_closed": len(trades),
            "bear_episodes_2026": len(eps),
            "bear_days_2026": len(bear_days),
            "breaker": verdicts,
            "note": "shadow only - nothing was blocked; saved_usd>0 means the breaker would have helped"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    print("SHADOW BREAKER:", json.dumps(line))


if __name__ == "__main__":
    main()

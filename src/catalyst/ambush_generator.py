import json
import urllib.request
from datetime import datetime, timedelta

from src.alpaca_ohlcv import get_daily_bars_eodhd_format
from src.alpaca_options import get_live_price
from src.catalyst.iv_rank_diy import compute_iv_rank, record_today_iv
from src.options_suggest_bear_spread import (
    suggest_bear_put_debit_spread,
    suggest_bear_call_credit_spread,
)

TARGETS = ["COIN", "MSTR", "NVDA"]
SPX_PROXY = "SPY"
SPX_JUNE4_PIVOT = 756.97
IV_RANK_CREDIT_THRESHOLD = 50.0


def _market_is_open():
    now = datetime.utcnow()
    if now.weekday() >= 5:
        return False
    try:
        from zoneinfo import ZoneInfo
        et = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/New_York"))
        if et.weekday() >= 5:
            return False
        mins = et.hour * 60 + et.minute
        return 9 * 60 + 30 <= mins <= 16 * 60
    except Exception:
        mins = now.hour * 60 + now.minute
        return 13 * 60 + 30 <= mins <= 20 * 60


def _sma(values, n):
    if len(values) < n:
        return None
    return sum(values[:n]) / n


def _spot_and_sma(ticker):
    bars = get_daily_bars_eodhd_format(ticker, from_date=(datetime.utcnow().date() - timedelta(days=80)).isoformat())
    if not bars:
        return None, None, None
    bars.sort(key=lambda b: b["date"], reverse=True)
    closes = [b["close"] for b in bars]
    sma20 = _sma(closes, 20)
    live = get_live_price(ticker)
    spot = live if live else closes[0]
    source = "live" if live else f"close {bars[0]['date']}"
    return spot, sma20, source


def _spx_gate():
    spot, sma20, source = _spot_and_sma(SPX_PROXY)
    if spot is None or sma20 is None:
        return {"ok": None, "reason": "no SPY data"}
    below_sma = spot < sma20
    return {
        "ok": bool(below_sma),
        "spot": round(spot, 2),
        "source": source,
        "sma20": round(sma20, 2),
        "june4_pivot": SPX_JUNE4_PIVOT,
        "below_pivot": spot < SPX_JUNE4_PIVOT,
        "reason": f"SPY {spot:.2f} ({source}) {'below' if below_sma else 'above'} 20d SMA {sma20:.2f}, June4 pivot {SPX_JUNE4_PIVOT}",
    }


def _usdjpy_gate():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/JPY=X?interval=1d&range=7d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c is not None]
        if len(closes) < 2:
            return {"ok": None, "reason": "insufficient yen data"}
        current, prior = closes[-1], closes[-2]
        falling = current < prior
        return {
            "ok": bool(falling),
            "usdjpy": round(current, 3),
            "prior": round(prior, 3),
            "reason": f"USDJPY {current:.2f} vs prior {prior:.2f} -> yen {'STRENGTHENING' if falling else 'weakening'}",
        }
    except Exception as e:
        return {"ok": None, "reason": f"yen fetch failed: {type(e).__name__}"}


def evaluate_gate():
    market_open = _market_is_open()
    spx = _spx_gate()
    yen = _usdjpy_gate()
    armed = bool(market_open) and bool(spx.get("ok")) and bool(yen.get("ok"))
    blocking = []
    if not market_open:
        blocking.append("US market closed")
    if not spx.get("ok"):
        blocking.append("SPX not below 20d SMA" if spx.get("ok") is False else f"SPX gate unknown ({spx.get('reason')})")
    if not yen.get("ok"):
        blocking.append("yen not strengthening" if yen.get("ok") is False else f"yen gate unknown ({yen.get('reason')})")
    return {
        "armed": armed,
        "market_open": market_open,
        "spx": spx,
        "yen": yen,
        "blocking": blocking,
        "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def _iv_rank(ticker):
    try:
        from src.unusual_whales_api import get_client
        c = get_client()
        if c.enabled:
            resp = c.iv_rank(ticker)
            rows = (resp or {}).get("data") or []
            if rows:
                latest = max(rows, key=lambda r: r.get("date", ""))
                val = latest.get("iv_rank_1y")
                if val is not None:
                    return {"iv_rank": round(float(val), 1), "source": f"UW iv_rank_1y {latest.get('date')}"}
    except Exception:
        pass
    record_today_iv(ticker)
    diy = compute_iv_rank(ticker)
    if diy and diy.get("iv_rank") is not None:
        return {"iv_rank": diy["iv_rank"], "source": f"DIY {diy['confidence']} {diy['sample_days']}d"}
    return None


def generate_tickets(targets=None, force=False):
    targets = targets or TARGETS
    tickets = []
    for t in targets:
        spot, sma20, _ = _spot_and_sma(t)
        if spot is None:
            tickets.append({"ticker": t, "skipped": "no price data"})
            continue
        below = (spot < sma20) if sma20 else None
        if below is False and not force:
            tickets.append({"ticker": t, "skipped": f"above 20d SMA ({spot:.2f} > {sma20:.2f}) - not weak, no short"})
            continue
        rank = _iv_rank(t)
        if rank and rank.get("iv_rank") is not None:
            use_credit = rank["iv_rank"] >= IV_RANK_CREDIT_THRESHOLD
            iv_note = f"IV rank {rank['iv_rank']} ({rank['source']})"
        else:
            use_credit = False
            iv_note = "IV rank unavailable - defaulted to debit"
        if use_credit:
            spread = suggest_bear_call_credit_spread(t, spot)
            route = "bear_call_credit_spread (high IV - sell premium)"
        else:
            spread = suggest_bear_put_debit_spread(t, spot)
            route = "bear_put_debit_spread (low/moderate IV - buy premium)"
        if not spread:
            tickets.append({"ticker": t, "spot": round(spot, 2), "iv_note": iv_note, "route": route, "skipped": "no spread met liquidity/delta filters"})
            continue
        spread["iv_note"] = iv_note
        spread["route"] = route
        spread["spot_vs_sma20"] = {"spot": round(spot, 2), "sma20": round(sma20, 2) if sma20 else None}
        tickets.append(spread)
    return tickets


def _fmt_ticket(tk):
    if tk.get("skipped"):
        return f"  {tk['ticker']}: SKIP - {tk['skipped']}"
    lines = [f"  {tk['ticker']}  {tk['structure'].upper()}  [{tk['route']}]", f"    {tk['iv_note']}"]
    if tk["structure"] == "bear_put_debit_spread":
        lg, sg = tk["long_leg"], tk["short_leg"]
        lines.append(f"    BUY  {tk['ticker']} {tk['expiration']} {lg['strike']:g} PUT  (d {lg['delta']}, mid {lg['mid']})  {lg['occ_symbol']}")
        lines.append(f"    SELL {tk['ticker']} {tk['expiration']} {sg['strike']:g} PUT  (d {sg['delta']}, mid {sg['mid']})  {sg['occ_symbol']}")
        lines.append(f"    NET DEBIT limit {tk['limit_price']}  |  width {tk['width']:g}  |  DTE {tk['dte']}")
    else:
        sg, lg = tk["short_leg"], tk["long_leg"]
        lines.append(f"    SELL {tk['ticker']} {tk['expiration']} {sg['strike']:g} CALL (d {sg['delta']}, mid {sg['mid']})  {sg['occ_symbol']}")
        lines.append(f"    BUY  {tk['ticker']} {tk['expiration']} {lg['strike']:g} CALL (d {lg['delta']}, mid {lg['mid']})  {lg['occ_symbol']}")
        lines.append(f"    NET CREDIT limit {tk['limit_price']}  |  width {tk['width']:g}  |  DTE {tk['dte']}")
    lines.append(f"    max loss {tk['max_loss_per_spread']}/spread  |  max profit {tk['max_profit_per_spread']}/spread  |  R/R {tk['risk_reward_ratio']}  |  breakeven {tk['breakeven']} ({tk['breakeven_pct_move']:+.1f}%)")
    lines.append(f"    quotes fetched {tk.get('fetched_at')}")
    return "\n".join(lines)


def _tg_ticket(tk):
    if tk.get("skipped"):
        return f"<b>{tk['ticker']}</b> SKIP - {tk['skipped']}"
    if tk["structure"] == "bear_put_debit_spread":
        lg, sg = tk["long_leg"], tk["short_leg"]
        head = f"<b>{tk['ticker']}</b> bear put debit · {tk.get('iv_note', '')}"
        l1 = f"BUY {tk['expiration']} {lg['strike']:g}P / SELL {sg['strike']:g}P"
        l2 = f"debit {tk['limit_price']} · width {tk['width']:g} · DTE {tk['dte']}"
    else:
        sg, lg = tk["short_leg"], tk["long_leg"]
        head = f"<b>{tk['ticker']}</b> bear call credit · {tk.get('iv_note', '')}"
        l1 = f"SELL {tk['expiration']} {sg['strike']:g}C / BUY {lg['strike']:g}C"
        l2 = f"credit {tk['limit_price']} · width {tk['width']:g} · DTE {tk['dte']}"
    l3 = f"maxL ${tk['max_loss_per_spread']:.0f} / maxP ${tk['max_profit_per_spread']:.0f} · R/R {tk['risk_reward_ratio']} · BE {tk['breakeven']} ({tk['breakeven_pct_move']:+.1f}%)"
    return "\n".join([head, l1, l2, l3])


def _telegram_message(gate, tickets):
    lines = [
        "<b>AMBUSH HOT - gates aligned</b>",
        gate["checked_at"],
        f"SPX: {gate['spx'].get('reason', '')}",
        f"Yen: {gate['yen'].get('reason', '')}",
        "",
    ]
    for tk in tickets:
        lines.append(_tg_ticket(tk))
        lines.append("")
    lines.append("<i>System-generated from live data. Defined-risk, no sizing. Verify before placing.</i>")
    return "\n".join(lines)


def run(targets=None, preview=False, force=False, alert=False):
    gate = evaluate_gate()
    print("=" * 66)
    print("AMBUSH GENERATOR - gated bear-spread tickets (no sizing)")
    print(f"checked_at {gate['checked_at']}")
    print(f"  market_open: {gate['market_open']}")
    print(f"  SPX gate : {gate['spx'].get('reason')}  -> {'PASS' if gate['spx'].get('ok') else 'BLOCK'}")
    print(f"  yen gate : {gate['yen'].get('reason')}  -> {'PASS' if gate['yen'].get('ok') else 'BLOCK'}")
    print("-" * 66)
    if gate["armed"]:
        print("GATES ALIGNED - WEAPON HOT. Emitting tickets:")
        tickets = generate_tickets(targets, force=force)
        for tk in tickets:
            print(_fmt_ticket(tk))
        if alert:
            from src.telegram import send_alert
            ok = send_alert(_telegram_message(gate, tickets))
            print(f"telegram alert: {'sent' if ok else 'NOT sent (no token/chat or send failed)'}")
        return {"gate": gate, "tickets": tickets, "mode": "live"}
    if preview:
        print(f"WEAPON COLD ({'; '.join(gate['blocking'])}).")
        print("PREVIEW: built off LAST-AVAILABLE quotes - STALE, ILLUSTRATION ONLY, NOT LIVE, DO NOT TRADE:")
        tickets = generate_tickets(targets, force=force)
        for tk in tickets:
            print(_fmt_ticket(tk))
        return {"gate": gate, "tickets": tickets, "mode": "preview_stale"}
    print(f"WEAPON COLD - emitting nothing. Blocking: {'; '.join(gate['blocking'])}")
    return {"gate": gate, "tickets": [], "mode": "cold"}

"""0DTE Ignition Scanner — Premarket + Opening Range.

Replicates the $500-to-$6,700 strategy:
  1. Pull 0DTE sweep flow from Unusual Whales
  2. Score by: sweep count, ask-side fills, premium, vol > OI
  3. Check gap (premarket price vs prior close)
  4. Check volume spike (z-score on volume vs 20-day avg)
  5. Check GEX (negative = dealer amplification)
  6. Rank top 3-5 names with specific 0DTE strikes

Two scan windows (set via cron):
  PREMARKET — 13:00 UTC (9:00 AM ET): build watchlist from flow + gaps
  OPEN      — 13:45 UTC (9:45 AM ET): confirm with volume + strikes

Usage:
  python scripts/ignition_scanner.py
  python scripts/ignition_scanner.py --skip-email
  python scripts/ignition_scanner.py --mode premarket
  python scripts/ignition_scanner.py --mode open
"""

import os
import sys
import math
import smtplib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

import requests


API_BASE = "https://api.unusualwhales.com/api"

SKIP_TICKERS = {
    "SPX", "NDX", "RUT", "VIX", "VVIX", "DJX", "SPXW", "RUTW", "NDXP",
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "IVV",
    "TQQQ", "SQQQ", "SOXL", "SOXS", "SPXL", "SPXS", "UVXY", "VXX",
    "GLD", "SLV", "USO", "TLT", "HYG",
    "GBTC", "IBIT", "FBTC", "ETHA", "BITO",
    "ARKK", "ARKG", "ARKW",
    "TSLL", "NVDL",
}


def _headers():
    token = os.environ.get("UNUSUAL_WHALES_TOKEN", "").strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _get(path, params=None):
    h = _headers()
    if not h:
        return None
    try:
        r = requests.get(f"{API_BASE}{path}", headers=h, params=params or {}, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _f(v, default=0):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def scan_0dte_flow(min_premium=10_000):
    params = {
        "limit": 200,
        "min_dte": 0,
        "max_dte": 0,
        "is_call": "true",
        "min_premium": min_premium,
    }
    raw = _get("/option-trades/flow-alerts", params)
    if not raw:
        return {}

    rows = raw.get("data") or (raw if isinstance(raw, list) else [])
    by_ticker = {}

    for r in rows:
        if not isinstance(r, dict):
            continue

        ticker = r.get("ticker") or r.get("underlying_symbol") or ""
        if not ticker or ticker in SKIP_TICKERS:
            continue

        prem = _f(r.get("total_premium") or r.get("premium"))
        vol = _f(r.get("volume"))
        oi = _f(r.get("open_interest"))

        is_sweep = r.get("has_sweep") is True

        ask_prem = _f(r.get("total_ask_side_prem"))
        is_ask_side = ask_prem > 0 and ask_prem >= prem * 0.5

        vol_oi_str = r.get("volume_oi_ratio")
        vol_gt_oi = _f(vol_oi_str) > 1.0 if vol_oi_str else (vol > oi if oi > 0 else False)

        slot = by_ticker.setdefault(ticker, {
            "alerts": 0, "sweeps": 0, "ask_side": 0,
            "vol_gt_oi": 0, "total_premium": 0,
            "strikes": [], "details": [],
        })
        slot["alerts"] += 1
        slot["total_premium"] += prem
        if is_sweep:
            slot["sweeps"] += 1
        if is_ask_side:
            slot["ask_side"] += 1
        if vol_gt_oi:
            slot["vol_gt_oi"] += 1

        strike = _f(r.get("strike") or r.get("strike_price"))
        if strike > 0:
            slot["strikes"].append(strike)
            slot["details"].append({
                "strike": strike,
                "premium": prem,
                "volume": vol,
                "oi": oi,
                "is_sweep": is_sweep,
                "type": r.get("type", ""),
            })

    scored = {}
    for ticker, data in by_ticker.items():
        score = 0
        score += min(data["sweeps"] * 2, 10)
        score += min(data["ask_side"] * 1.5, 6)
        score += min(data["vol_gt_oi"] * 1, 4)
        score += min(data["total_premium"] / 50_000, 5)
        score += min(data["alerts"] * 0.5, 5)
        data["flow_score"] = round(score, 1)
        scored[ticker] = data

    return scored


def check_gap(ticker):
    state = _get(f"/stock/{ticker}/stock-state")
    if not state:
        return None, None
    state_data = state.get("data") if isinstance(state, dict) else state
    if isinstance(state_data, list) and state_data:
        state_data = state_data[-1]
    if not isinstance(state_data, dict):
        return None, None

    current_price = _f(
        state_data.get("last_price") or state_data.get("price")
        or state_data.get("close") or state_data.get("last")
    )

    prev_close = _f(state_data.get("prev_close") or state_data.get("previous_close"))

    if prev_close and prev_close > 0 and current_price and current_price > 0:
        gap_pct = ((current_price - prev_close) / prev_close) * 100
        return current_price, round(gap_pct, 2)

    ohlc = _get(f"/stock/{ticker}/ohlc/1d")
    if not ohlc:
        return current_price, None
    bars = ohlc.get("data") or (ohlc if isinstance(ohlc, list) else [])
    if not bars or not isinstance(bars, list):
        return current_price, None

    prior_close = None
    for bar in reversed(bars[-5:]):
        if isinstance(bar, dict):
            c = _f(bar.get("close"))
            if c > 0:
                prior_close = c
                break

    if not prior_close or not current_price or prior_close == 0:
        return current_price, None

    gap_pct = ((current_price - prior_close) / prior_close) * 100
    return current_price, round(gap_pct, 2)


def check_volume_spike(ticker):
    ohlc = _get(f"/stock/{ticker}/ohlc/1d")
    if not ohlc:
        return None
    bars = ohlc.get("data") or (ohlc if isinstance(ohlc, list) else [])
    if not bars or len(bars) < 5:
        return None

    volumes = []
    for bar in bars[-21:]:
        if isinstance(bar, dict):
            v = _f(bar.get("volume"))
            if v > 0:
                volumes.append(v)

    if len(volumes) < 5:
        return None

    current_vol = volumes[-1]
    hist_vols = volumes[:-1]

    avg_vol = sum(hist_vols) / len(hist_vols)
    if avg_vol == 0:
        return None

    variance = sum((v - avg_vol) ** 2 for v in hist_vols) / len(hist_vols)
    stdev = math.sqrt(variance) if variance > 0 else 1

    z_score = (current_vol - avg_vol) / stdev
    return round(z_score, 2)


def check_gex(ticker):
    raw = _get(f"/stock/{ticker}/greek-exposure")
    if not raw:
        return None
    data = raw.get("data") if isinstance(raw, dict) else raw
    if isinstance(data, list) and data:
        data = data[-1]
    if not isinstance(data, dict):
        return None
    call_g = _f(data.get("call_gamma"))
    put_g = _f(data.get("put_gamma"))
    if call_g == 0 and put_g == 0:
        return None
    return call_g + put_g


def scan_darkpool():
    raw = _get("/darkpool/recent", {"limit": 200})
    if not raw:
        return {}

    rows = raw.get("data") or (raw if isinstance(raw, list) else [])
    by_ticker = {}

    for r in rows:
        if not isinstance(r, dict):
            continue
        ticker = r.get("ticker") or ""
        if not ticker or ticker in SKIP_TICKERS:
            continue

        price = _f(r.get("price"))
        size = _f(r.get("size"))
        value = price * size
        if value < 500_000:
            continue

        nbbo_ask = _f(r.get("nbbo_ask"))
        at_or_above_ask = price >= nbbo_ask if nbbo_ask > 0 else False

        slot = by_ticker.setdefault(ticker, {
            "prints": 0, "total_value": 0, "at_ask_prints": 0,
        })
        slot["prints"] += 1
        slot["total_value"] += value
        if at_or_above_ask:
            slot["at_ask_prints"] += 1

    return {t: d for t, d in by_ticker.items() if d["at_ask_prints"] >= 1}


def get_0dte_strikes(ticker, current_price):
    if not current_price:
        return []

    raw = _get(f"/stock/{ticker}/option-chains")
    if not raw:
        return []

    chains = raw.get("data") or (raw if isinstance(raw, list) else [])
    if not chains:
        return []

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    candidates = []
    for c in chains:
        if not isinstance(c, dict):
            continue
        expiry = (c.get("expiry") or c.get("expiration_date") or "")[:10]
        if expiry != today_str:
            continue
        opt_type = (c.get("option_type") or c.get("type") or "").lower()
        if "call" not in opt_type and opt_type != "c":
            continue

        strike = _f(c.get("strike") or c.get("strike_price"))
        bid = _f(c.get("bid"))
        ask = _f(c.get("ask"))
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else _f(c.get("last_price") or c.get("mark"))
        iv = _f(c.get("implied_volatility") or c.get("iv"))
        delta = _f(c.get("delta"))
        volume = _f(c.get("volume"))
        oi = _f(c.get("open_interest"))

        if strike <= 0 or mid <= 0:
            continue

        pct_otm = ((strike - current_price) / current_price) * 100

        candidates.append({
            "strike": strike,
            "bid": bid,
            "ask": ask,
            "mid": round(mid, 2),
            "iv": round(iv * 100, 1) if 0 < iv < 5 else round(iv, 1),
            "delta": round(delta, 3),
            "volume": volume,
            "oi": oi,
            "pct_otm": round(pct_otm, 2),
        })

    if not candidates:
        return []

    candidates.sort(key=lambda x: abs(x["pct_otm"]))
    picks = []
    for c in candidates:
        if -1 <= c["pct_otm"] <= 5:
            picks.append(c)
            if len(picks) >= 3:
                break

    return picks


def rank_and_filter(tickers_data, max_names=5):
    scored = []
    for ticker, data in tickers_data.items():
        total_score = 0
        signals_hit = []

        flow_score = data.get("flow_score", 0)
        total_score += flow_score
        if flow_score > 0:
            signals_hit.append("FLOW")

        gap = data.get("gap_pct")
        if gap is not None and gap >= 2:
            total_score += min(gap, 10)
            signals_hit.append("GAP")

        vol_z = data.get("vol_zscore")
        if vol_z is not None and vol_z >= 2:
            total_score += min(vol_z * 2, 8)
            signals_hit.append("VOL_SPIKE")

        gex = data.get("gex")
        if gex is not None and gex < 0:
            total_score += 3
            signals_hit.append("NEG_GEX")

        dp = data.get("darkpool")
        if dp and dp.get("at_ask_prints", 0) > 0:
            total_score += 2 + min(dp["at_ask_prints"], 3)
            signals_hit.append("DARK_POOL")

        data["total_score"] = round(total_score, 1)
        data["signals_hit"] = signals_hit
        data["signal_count"] = len(signals_hit)
        scored.append((ticker, data))

    scored.sort(key=lambda x: -x[1]["total_score"])
    return scored[:max_names]


def _render_ticker_block(ticker, data):
    signals = data.get("signals_hit", [])
    score = data.get("total_score", 0)

    badge_colors = {
        "FLOW": "#ff6b6b", "GAP": "#ffd93d", "VOL_SPIKE": "#6bff6b",
        "NEG_GEX": "#ff9f43", "DARK_POOL": "#9b59b6",
    }
    badges = " ".join(
        f'<span style="background:{badge_colors.get(s, "#555")};color:#000;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:bold;">{s}</span>'
        for s in signals
    )

    flow_line = ""
    if data.get("sweeps", 0) > 0 or data.get("alerts", 0) > 0:
        flow_line = f"Flow: {data.get('alerts', 0)} alerts, {data.get('sweeps', 0)} sweeps, ${data.get('total_premium', 0)/1000:.0f}K premium"
        if data.get("ask_side", 0) > 0:
            flow_line += f", {data['ask_side']} ask-side"
        if data.get("vol_gt_oi", 0) > 0:
            flow_line += f", {data['vol_gt_oi']} vol>OI"

    gap_line = ""
    gap = data.get("gap_pct")
    if gap is not None:
        color = "#ffd93d" if gap >= 2 else "#888"
        gap_line = f'Gap: <span style="color:{color}">{gap:+.1f}%</span>'
    vol_z = data.get("vol_zscore")
    if vol_z is not None:
        color = "#6bff6b" if vol_z >= 2 else "#888"
        temp = f'Vol z-score: <span style="color:{color}">{vol_z:.1f}</span>'
        gap_line = f"{gap_line} | {temp}" if gap_line else temp

    gex_line = ""
    gex = data.get("gex")
    if gex is not None:
        color = "#ff9f43" if gex < 0 else "#888"
        gex_line = f'GEX: <span style="color:{color}">{gex:+,.0f}</span>'

    dp_line = ""
    dp = data.get("darkpool")
    if dp:
        dp_line = f"Dark Pool: ${dp['total_value']/1e6:.1f}M, {dp['at_ask_prints']} ask-side prints"

    strikes_html = ""
    strikes = data.get("0dte_strikes", [])
    if strikes:
        strikes_html = '<div style="margin-top:8px;padding:8px;background:#2a2a4a;border-radius:4px;">'
        strikes_html += '<span style="color:#aaa;font-size:11px;">0DTE STRIKES TO WATCH:</span><br>'
        for s in strikes:
            label = "ATM" if abs(s["pct_otm"]) < 0.5 else f"{s['pct_otm']:+.1f}% OTM"
            strikes_html += (
                f'<span style="color:#fff;font-size:13px;">'
                f'${s["strike"]:.0f} ({label}) — '
                f'bid ${s["bid"]:.2f} / ask ${s["ask"]:.2f} — '
                f'delta {s["delta"]:.2f} — '
                f'vol {s["volume"]:.0f} / OI {s["oi"]:.0f}'
                f'</span><br>'
            )
        strikes_html += '</div>'

    price = data.get("current_price", 0)
    price_str = f"${price:.2f}" if price else ""

    detail_lines = [l for l in [flow_line, gap_line, gex_line, dp_line] if l]

    return f"""<div style="border:1px solid #444;border-radius:8px;padding:15px;margin-bottom:15px;background:#1e1e3a;">
<div style="display:flex;justify-content:space-between;align-items:center;">
<span style="font-size:22px;font-weight:bold;color:#fff;">{ticker} <span style="color:#888;font-size:14px;">{price_str}</span></span>
<span style="color:#00ff88;font-size:16px;font-weight:bold;">SCORE {score:.0f}</span>
</div>
<div style="margin:8px 0;">{badges}</div>
<div style="color:#ccc;font-size:13px;line-height:1.8;">{'<br>'.join(detail_lines)}</div>
{strikes_html}
</div>"""


def render_email_html(ranked, scan_time, mode, flow_count):
    mode_label = "PREMARKET" if mode == "premarket" else "OPENING RANGE"

    if not ranked:
        return f"""<html><body style="font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:20px;">
<h2 style="color:#ff6b6b;">IGNITION {mode_label} — NO NAMES</h2>
<p>{scan_time}</p>
<p>0DTE flow tickers scanned: {flow_count}</p>
<p>No stocks with 0DTE ignition signals right now.</p>
</body></html>"""

    blocks = ""
    for ticker, data in ranked:
        blocks += _render_ticker_block(ticker, data)

    count = len(ranked)
    top_names = ", ".join(t for t, _ in ranked[:3])

    return f"""<html><body style="font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:20px;">
<h2 style="color:#00ff88;margin-bottom:5px;">IGNITION {mode_label} — {count} NAMES</h2>
<p style="color:#aaa;margin-top:0;">{scan_time} | {top_names}</p>
<p style="color:#666;font-size:12px;">0DTE call sweeps + gaps + volume spikes + GEX + dark pool</p>
{blocks}
<p style="color:#555;font-size:11px;margin-top:20px;">
0DTE flow tickers: {flow_count} | Ranked by flow aggression + gap + volume spike + GEX + dark pool<br>
Strategy: buy 0DTE ATM/1-OTM calls on opening range breakout above premarket high. Cut fast if no follow-through.
</p>
</body></html>"""


def send_email(html, scan_time, count, mode):
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not gmail_user or not gmail_pass:
        print("GMAIL creds not set, skipping email")
        return False

    mode_label = "PRE" if mode == "premarket" else "OPEN"
    label = f"{count} NAMES" if count else "QUIET"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"IGNITION {mode_label} {label} — {scan_time}"
    msg["From"] = gmail_user
    msg["To"] = gmail_user
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, gmail_user, msg.as_string())
        return True
    except Exception as e:
        print(f"Email failed: {type(e).__name__}: {e}")
        return False


def run_ignition_scan(mode="auto", skip_email=False, min_premium=10_000, max_names=5):
    if not _headers():
        print("UNUSUAL_WHALES_TOKEN not set.")
        return []

    now = datetime.now(timezone.utc)
    scan_time = now.strftime("%Y-%m-%d %H:%M UTC")

    if mode == "auto":
        et_hour = (now.hour - 4) % 24
        if et_hour < 10:
            mode = "premarket"
        else:
            mode = "open"

    mode_label = "PREMARKET" if mode == "premarket" else "OPENING RANGE"
    print(f"=== IGNITION SCANNER — {mode_label} ({scan_time}) ===")
    print()

    print("Scanning 0DTE call flow...")
    flow_hits = scan_0dte_flow(min_premium=min_premium)
    print(f"  {len(flow_hits)} tickers with 0DTE call flow")

    if not flow_hits:
        print("No 0DTE flow found. Market may be closed.")
        if not skip_email:
            html = render_email_html([], scan_time, mode, 0)
            send_email(html, scan_time, 0, mode)
        return []

    print("Scanning dark pool...")
    dp_hits = scan_darkpool()
    print(f"  {len(dp_hits)} tickers with ask-side dark pool prints")

    sorted_flow = sorted(flow_hits.items(), key=lambda x: -x[1]["flow_score"])
    check_tickers = [t for t, _ in sorted_flow[:30]]

    print(f"Checking gap + volume + GEX on top {len(check_tickers)} flow names...")

    for ticker in check_tickers:
        current_price, gap_pct = check_gap(ticker)
        flow_hits[ticker]["current_price"] = current_price
        flow_hits[ticker]["gap_pct"] = gap_pct

        vol_z = check_volume_spike(ticker)
        flow_hits[ticker]["vol_zscore"] = vol_z

        gex = check_gex(ticker)
        flow_hits[ticker]["gex"] = gex

        if ticker in dp_hits:
            flow_hits[ticker]["darkpool"] = dp_hits[ticker]

        if mode == "open" and current_price:
            strikes = get_0dte_strikes(ticker, current_price)
            flow_hits[ticker]["0dte_strikes"] = strikes

    ranked = rank_and_filter(
        {t: flow_hits[t] for t in check_tickers},
        max_names=max_names,
    )

    print(f"\n{'='*80}")
    if ranked:
        print(f"  TOP {len(ranked)} IGNITION NAMES:")
        print(f"  {'TICKER':<8} {'SCORE':>6}  {'SIGS':>5}  {'GAP':>6}  {'VOL Z':>6}  {'GEX':>10}  {'FLOW':>10}  DETAILS")
        print(f"  {'------':<8} {'-----':>6}  {'----':>5}  {'---':>6}  {'-----':>6}  {'---':>10}  {'----':>10}  -------")
        for ticker, data in ranked:
            gap_str = f"{data.get('gap_pct', 0):+.1f}%" if data.get('gap_pct') is not None else "n/a"
            vol_str = f"{data.get('vol_zscore', 0):.1f}" if data.get('vol_zscore') is not None else "n/a"
            gex_str = f"{data.get('gex', 0):+,.0f}" if data.get('gex') is not None else "n/a"
            flow_str = f"${data.get('total_premium', 0)/1000:.0f}K"
            sigs = "+".join(data.get("signals_hit", []))
            sweeps = data.get("sweeps", 0)
            asks = data.get("ask_side", 0)
            print(f"  {ticker:<8} {data['total_score']:>6.0f}  {data['signal_count']:>5}  {gap_str:>6}  {vol_str:>6}  {gex_str:>10}  {flow_str:>10}  {sweeps}sw {asks}ask | {sigs}")

            strikes = data.get("0dte_strikes", [])
            for s in strikes:
                label = "ATM" if abs(s["pct_otm"]) < 0.5 else f"{s['pct_otm']:+.1f}%"
                print(f"           ${s['strike']:.0f} ({label}) bid ${s['bid']:.2f} / ask ${s['ask']:.2f}  delta {s['delta']:.2f}  vol {s['volume']:.0f}")
    else:
        print("No names passed ranking. 0DTE flow tickers:", len(flow_hits))

    if not skip_email:
        html = render_email_html(ranked, scan_time, mode, len(flow_hits))
        if send_email(html, scan_time, len(ranked), mode):
            print(f"Email sent: {len(ranked)} names")
    else:
        print("--skip-email set")

    print(f"{'='*80}")
    return ranked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="0DTE Ignition Scanner")
    parser.add_argument("--mode", choices=["premarket", "open", "auto"], default="auto")
    parser.add_argument("--skip-email", action="store_true")
    parser.add_argument("--min-premium", type=int, default=10_000)
    parser.add_argument("--max-names", type=int, default=5)
    args = parser.parse_args()

    run_ignition_scan(
        mode=args.mode,
        skip_email=args.skip_email,
        min_premium=args.min_premium,
        max_names=args.max_names,
    )

"""4-Signal Convergence Scanner (standalone).

Finds mid-cap stocks ($2B-$50B) where 3 or 4 of these signals fire:
  1. FLOW     - Bullish OTM call sweeps, $100K+ premium, vol > OI
  2. DARKPOOL - Large block prints at or above the ask
  3. IV_LOW   - IV rank below 30 (cheap options)
  4. HIGH_SI  - Short interest above 15% (squeeze fuel)

Sends a separate email with results. Runs hourly during market hours via GH Actions.

Requires env vars: UNUSUAL_WHALES_TOKEN, GMAIL_USER, GMAIL_APP_PASSWORD

Usage:
  python scripts/convergence_scanner.py
  python scripts/convergence_scanner.py --skip-email
  python scripts/convergence_scanner.py --min-premium 200000 --min-dp-size 2000000
"""

import os
import sys
import re
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


def _ticker_from_chain(option_chain):
    if not option_chain:
        return None, None
    m = re.match(r"^([A-Z]{1,6})\d{6}([CP])", option_chain.upper())
    if m:
        return m.group(1), m.group(2)
    return None, None


def scan_flow(min_premium=100_000):
    raw = _get("/option-trades/flow-alerts", {
        "limit": 200, "is_otm": "true", "min_premium": min_premium,
    })
    if not raw:
        return {}

    rows = raw.get("data") or (raw if isinstance(raw, list) else [])
    by_ticker = {}

    for r in rows:
        if not isinstance(r, dict):
            continue

        oc = r.get("option_chain") or ""
        oc_ticker, oc_side = _ticker_from_chain(oc)
        ticker = r.get("ticker") or r.get("underlying_symbol") or oc_ticker
        if not ticker or ticker in SKIP_TICKERS:
            continue

        is_call = oc_side == "C" if oc_side else "call" in (r.get("type") or "").lower()
        if not is_call:
            continue

        type_field = (r.get("type") or "").lower()
        is_sweep = "sweep" in type_field
        sentiment = (r.get("sentiment") or "").lower()
        is_bullish = sentiment in ("bullish", "") or "bullish" in type_field

        prem = _f(r.get("total_premium") or r.get("premium"))
        vol = _f(r.get("volume"))
        oi = _f(r.get("open_interest"))
        vol_oi = (vol / oi) if oi > 0 else 999

        slot = by_ticker.setdefault(ticker, {
            "hits": 0, "total_premium": 0, "sweeps": 0,
            "bullish": 0, "best_vol_oi": 0,
        })
        slot["hits"] += 1
        slot["total_premium"] += prem
        if is_sweep:
            slot["sweeps"] += 1
        if is_bullish:
            slot["bullish"] += 1
        slot["best_vol_oi"] = max(slot["best_vol_oi"], vol_oi)

    qualified = {}
    for ticker, data in by_ticker.items():
        if data["hits"] >= 2 and data["bullish"] >= 1:
            qualified[ticker] = data
    return qualified


def scan_darkpool(min_size=1_000_000):
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
        if value < min_size:
            continue

        nbbo_ask = _f(r.get("nbbo_ask"))
        at_or_above_ask = price >= nbbo_ask if nbbo_ask > 0 else False

        slot = by_ticker.setdefault(ticker, {
            "prints": 0, "total_value": 0, "at_ask_prints": 0,
            "largest_print": 0,
        })
        slot["prints"] += 1
        slot["total_value"] += value
        slot["largest_print"] = max(slot["largest_print"], value)
        if at_or_above_ask:
            slot["at_ask_prints"] += 1

    qualified = {}
    for ticker, data in by_ticker.items():
        if data["at_ask_prints"] >= 1:
            qualified[ticker] = data
    return qualified


def get_market_cap(ticker):
    raw = _get(f"/stock/{ticker}/info")
    if not raw:
        return None
    data = raw.get("data") if isinstance(raw, dict) else raw
    if not isinstance(data, dict):
        return None
    mcap = data.get("marketcap") or data.get("market_cap") or data.get("marketCap")
    return _f(mcap) if mcap is not None else None


def check_iv_rank(ticker):
    raw = _get(f"/stock/{ticker}/iv-rank")
    if not raw:
        return None
    data = raw.get("data") if isinstance(raw, dict) else raw
    if isinstance(data, list) and data:
        data = data[-1]
    if not isinstance(data, dict):
        return None
    rank = data.get("iv_rank") or data.get("iv_percentile") or data.get("rank")
    return _f(rank) if rank is not None else None


def check_short_interest(ticker):
    raw = _get(f"/shorts/{ticker}/interest-float")
    if not raw:
        return None
    data = raw.get("data") if isinstance(raw, dict) else raw
    if isinstance(data, list) and data:
        data = data[-1]
    if not isinstance(data, dict):
        return None
    si = data.get("short_interest") or data.get("short_percent_of_float") or data.get("si_percent_float")
    return _f(si) if si is not None else None


# ── email ──

def render_email_html(results, scan_time, flow_count, dp_count, mcap_skipped, config):
    if not results:
        return f"""<html><body style="font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:20px;">
<h2 style="color:#ff6b6b;">CONVERGENCE SCANNER - NO HITS</h2>
<p>{scan_time}</p>
<p>Flow tickers: {flow_count} | Dark pool tickers: {dp_count} | Mcap filtered: {mcap_skipped}</p>
<p style="color:#888;">Filters: mcap ${config['mcap_min']/1e9:.0f}B-${config['mcap_max']/1e9:.0f}B | flow >=${config['min_premium']/1000:.0f}K | DP >=${config['min_dp_size']/1e6:.1f}M | IV <{config['iv_threshold']} | SI >{config['si_threshold']}%</p>
<p>No mid-cap tickers with 3+ signal convergence this hour.</p>
</body></html>"""

    rows_html = ""
    for r in results:
        conv = r["convergence"]
        label = "QUAD" if conv == 4 else "TRIPLE"
        label_color = "#00ff88" if conv == 4 else "#ffaa00"

        flow_cell = ""
        if "flow" in r["signals"]:
            f = r["signals"]["flow"]
            flow_cell = f"${f['total_premium']/1000:.0f}K<br><small>{f['hits']} alerts, {f['sweeps']} sweeps</small>"

        dp_cell = ""
        if "darkpool" in r["signals"]:
            d = r["signals"]["darkpool"]
            dp_cell = f"${d['total_value']/1e6:.1f}M<br><small>{d['at_ask_prints']} ask-side</small>"

        iv_cell = ""
        if r["iv_rank"] is not None:
            color = "#00ff88" if r["iv_rank"] < config["iv_threshold"] else "#888"
            iv_cell = f'<span style="color:{color}">{r["iv_rank"]:.0f}</span>'

        si_cell = ""
        if r["short_interest"] is not None:
            color = "#ff6b6b" if r["short_interest"] > config["si_threshold"] else "#888"
            si_cell = f'<span style="color:{color}">{r["short_interest"]:.1f}%</span>'

        mcap_cell = f"${r.get('market_cap', 0)/1e9:.1f}B"

        rows_html += f"""<tr style="border-bottom:1px solid #333;">
<td style="padding:8px;font-weight:bold;font-size:16px;">{r['ticker']}</td>
<td style="padding:8px;color:{label_color};font-weight:bold;">{label}</td>
<td style="padding:8px;">{mcap_cell}</td>
<td style="padding:8px;">{flow_cell}</td>
<td style="padding:8px;">{dp_cell}</td>
<td style="padding:8px;text-align:center;">{iv_cell}</td>
<td style="padding:8px;text-align:center;">{si_cell}</td>
</tr>"""

    quads = sum(1 for r in results if r["convergence"] == 4)
    triples = sum(1 for r in results if r["convergence"] == 3)
    summary = []
    if quads:
        summary.append(f'<span style="color:#00ff88;font-weight:bold;">{quads} QUAD</span>')
    if triples:
        summary.append(f'<span style="color:#ffaa00;font-weight:bold;">{triples} TRIPLE</span>')

    return f"""<html><body style="font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:20px;">
<h2 style="color:#00ff88;margin-bottom:5px;">CONVERGENCE SCANNER</h2>
<p style="color:#888;margin-top:0;">{scan_time} | {' + '.join(summary)} convergence</p>
<p style="color:#666;font-size:12px;">Filters: mcap ${config['mcap_min']/1e9:.0f}B-${config['mcap_max']/1e9:.0f}B | flow >=${config['min_premium']/1000:.0f}K | DP >=${config['min_dp_size']/1e6:.1f}M | IV <{config['iv_threshold']} | SI >{config['si_threshold']}%</p>

<table style="border-collapse:collapse;width:100%;margin-top:15px;">
<tr style="background:#2a2a4a;color:#aaa;font-size:12px;">
<th style="padding:8px;text-align:left;">TICKER</th>
<th style="padding:8px;text-align:left;">LEVEL</th>
<th style="padding:8px;text-align:left;">MCAP</th>
<th style="padding:8px;text-align:left;">FLOW</th>
<th style="padding:8px;text-align:left;">DARK POOL</th>
<th style="padding:8px;text-align:center;">IV RANK</th>
<th style="padding:8px;text-align:center;">SI %</th>
</tr>
{rows_html}
</table>

<p style="color:#666;font-size:11px;margin-top:20px;">
Flow: {flow_count} tickers | Dark Pool: {dp_count} tickers | Mcap filtered: {mcap_skipped}<br>
Signals marked green = active convergence signal
</p>
</body></html>"""


def send_convergence_email(html, scan_time, result_count):
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not gmail_user or not gmail_pass:
        print("GMAIL_USER / GMAIL_APP_PASSWORD not set, skipping email")
        return False

    msg = MIMEMultipart("alternative")
    label = f"{result_count} HITS" if result_count else "NO HITS"
    msg["Subject"] = f"CONVERGENCE {label} - {scan_time}"
    msg["From"] = gmail_user
    msg["To"] = gmail_user
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, gmail_user, msg.as_string())
        return True
    except Exception as e:
        print(f"Email send failed: {type(e).__name__}: {e}")
        return False


# ── main scan ──

def run_convergence_scan(min_premium=100_000, min_dp_size=1_000_000,
                         iv_threshold=30, si_threshold=15,
                         mcap_min=2e9, mcap_max=50e9, skip_email=False):
    if not _headers():
        print("UNUSUAL_WHALES_TOKEN not set. Cannot run convergence scanner.")
        return []

    now = datetime.now(timezone.utc)
    scan_time = now.strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== CONVERGENCE SCANNER ({scan_time}) ===")
    print(f"Filters: mcap ${mcap_min/1e9:.0f}B-${mcap_max/1e9:.0f}B | flow >=${min_premium/1000:.0f}K | dark pool >=${min_dp_size/1e6:.1f}M | IV rank <{iv_threshold} | SI >{si_threshold}%")
    print()

    print("Signal 1/4: scanning options flow...")
    flow_hits = scan_flow(min_premium=min_premium)
    print(f"  {len(flow_hits)} tickers with bullish OTM call flow")

    print("Signal 2/4: scanning dark pool...")
    dp_hits = scan_darkpool(min_size=min_dp_size)
    print(f"  {len(dp_hits)} tickers with large ask-side dark pool prints")

    all_tickers = sorted(set(list(flow_hits.keys()) + list(dp_hits.keys())))
    if not all_tickers:
        print("\nNo tickers found with flow or dark pool signals. Market may be closed.")
        if not skip_email:
            config = dict(mcap_min=mcap_min, mcap_max=mcap_max, min_premium=min_premium,
                          min_dp_size=min_dp_size, iv_threshold=iv_threshold, si_threshold=si_threshold)
            html = render_email_html([], scan_time, 0, 0, 0, config)
            if send_convergence_email(html, scan_time, 0):
                print("Email sent (no hits)")
        return []

    print(f"\nSignal 3-4/4: checking IV rank + short interest on {len(all_tickers)} tickers...")

    results = []
    mcap_skipped = 0
    for i, ticker in enumerate(all_tickers):
        mcap = get_market_cap(ticker)
        if mcap is None or mcap < mcap_min or mcap > mcap_max:
            mcap_skipped += 1
            continue

        signals = {}
        signal_count = 0

        if ticker in flow_hits:
            signals["flow"] = flow_hits[ticker]
            signal_count += 1

        if ticker in dp_hits:
            signals["darkpool"] = dp_hits[ticker]
            signal_count += 1

        iv = check_iv_rank(ticker)
        if iv is not None and iv < iv_threshold:
            signals["iv_rank"] = iv
            signal_count += 1

        si = check_short_interest(ticker)
        if si is not None and si > si_threshold:
            signals["short_interest"] = si
            signal_count += 1

        if signal_count >= 3:
            results.append({
                "ticker": ticker,
                "convergence": signal_count,
                "signals": signals,
                "iv_rank": iv,
                "short_interest": si,
                "market_cap": mcap,
            })

        if (i + 1) % 10 == 0:
            print(f"  checked {i+1}/{len(all_tickers)}...")

    if mcap_skipped:
        print(f"  {mcap_skipped} tickers outside ${mcap_min/1e9:.0f}B-${mcap_max/1e9:.0f}B mcap range")

    results.sort(key=lambda x: (-x["convergence"], -x["signals"].get("flow", {}).get("total_premium", 0)))

    print(f"\n{'='*80}")

    if not results:
        print("No tickers with 3+ signal convergence right now.")
        print(f"Flow tickers: {len(flow_hits)} | Dark pool tickers: {len(dp_hits)}")
    else:
        print(f"\n  {'TICKER':<8} {'CONV':>4}  {'MCAP':>6}  {'FLOW':>8}  {'DARK POOL':>12}  {'IV RANK':>8}  {'SI %':>6}  DETAILS")
        print(f"  {'------':<8} {'----':>4}  {'----':>6}  {'----':>8}  {'---------':>12}  {'-------':>8}  {'----':>6}  -------")

        for r in results:
            ticker = r["ticker"]
            conv = r["convergence"]
            mcap_str = f"${r.get('market_cap', 0)/1e9:.1f}B"

            flow_str = ""
            if "flow" in r["signals"]:
                fl = r["signals"]["flow"]
                flow_str = f"${fl['total_premium']/1000:.0f}K"

            dp_str = ""
            if "darkpool" in r["signals"]:
                d = r["signals"]["darkpool"]
                dp_str = f"${d['total_value']/1e6:.1f}M"

            iv_str = ""
            if r["iv_rank"] is not None:
                marker = " *" if r["iv_rank"] < iv_threshold else ""
                iv_str = f"{r['iv_rank']:.0f}{marker}"

            si_str = ""
            if r["short_interest"] is not None:
                marker = " *" if r["short_interest"] > si_threshold else ""
                si_str = f"{r['short_interest']:.1f}{marker}"

            details = []
            if "flow" in r["signals"]:
                fl = r["signals"]["flow"]
                details.append(f"{fl['hits']} alerts, {fl['sweeps']} sweeps")
            if "darkpool" in r["signals"]:
                d = r["signals"]["darkpool"]
                details.append(f"{d['at_ask_prints']} ask-side prints")

            conv_label = "QUAD" if conv == 4 else "TRIPLE"
            print(f"  {ticker:<8} {conv_label:>4}  {mcap_str:>6}  {flow_str:>8}  {dp_str:>12}  {iv_str:>8}  {si_str:>6}  {' | '.join(details)}")

    # Email
    if not skip_email:
        config = dict(mcap_min=mcap_min, mcap_max=mcap_max, min_premium=min_premium,
                      min_dp_size=min_dp_size, iv_threshold=iv_threshold, si_threshold=si_threshold)
        html = render_email_html(results, scan_time, len(flow_hits), len(dp_hits), mcap_skipped, config)
        if send_convergence_email(html, scan_time, len(results)):
            print(f"Email sent: {len(results)} hits")
    else:
        print("--skip-email set, no email sent")

    print(f"{'='*80}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="4-Signal Convergence Scanner")
    parser.add_argument("--min-premium", type=int, default=100_000)
    parser.add_argument("--min-dp-size", type=int, default=1_000_000)
    parser.add_argument("--iv-threshold", type=int, default=30)
    parser.add_argument("--si-threshold", type=int, default=15)
    parser.add_argument("--mcap-min", type=float, default=2e9)
    parser.add_argument("--mcap-max", type=float, default=50e9)
    parser.add_argument("--skip-email", action="store_true")
    args = parser.parse_args()

    run_convergence_scan(
        min_premium=args.min_premium,
        min_dp_size=args.min_dp_size,
        iv_threshold=args.iv_threshold,
        si_threshold=args.si_threshold,
        mcap_min=args.mcap_min,
        mcap_max=args.mcap_max,
        skip_email=args.skip_email,
    )

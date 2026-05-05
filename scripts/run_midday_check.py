import json
import os
import pathlib
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from jinja2 import Template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "results"


def load_alpaca():
    def get(n):
        if os.environ.get(n): return os.environ[n]
        r = subprocess.run(["powershell", "-Command", f'[Environment]::GetEnvironmentVariable("{n}","User")'],
                           capture_output=True, text=True)
        return (r.stdout or "").strip()
    for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD"):
        v = get(k)
        if v: os.environ[k] = v


def load_latest_scan():
    candidates = sorted(RESULTS_DIR.glob("scan_*.json"), reverse=True)
    if not candidates:
        return None, None
    path = candidates[0]
    with open(path) as f:
        return json.load(f), path.stem


def fetch_quotes(tickers):
    if not os.environ.get("ALPACA_API_KEY"):
        return {}
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
    sc = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    syms = list({t.replace(".US", "") for t in tickers if t.endswith(".US") or "." not in t})
    out = {}
    for i in range(0, len(syms), 100):
        batch = syms[i:i+100]
        try:
            trades = sc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=batch))
            quotes = sc.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=batch))
            for sym in batch:
                t = trades.get(sym) if isinstance(trades, dict) else None
                q = quotes.get(sym) if isinstance(quotes, dict) else None
                if t:
                    rec = {"price": float(t.price), "trade_time": str(t.timestamp)}
                    if q:
                        rec["bid"] = float(q.bid_price) if q.bid_price else None
                        rec["ask"] = float(q.ask_price) if q.ask_price else None
                    out[sym] = rec
        except Exception as e:
            print(f"  batch fetch error: {e}")
    return out


def categorize_intraday_move(pct):
    if pct >= 8:
        return "MISSED_BULLET", "stock already ran +8%+ today - move likely played out, skip"
    if pct >= 4:
        return "CHASE_RISK", "stock up +4-8% today - reduced edge, half size or wait for pullback"
    if pct >= 1:
        return "STILL_ACTIONABLE", "moderate move, entry zone still valid"
    if pct >= -2:
        return "FLAT", "no meaningful intraday move"
    if pct >= -5:
        return "POSSIBLE_DIP_BUY", "modest pullback to entry zone"
    return "BREAKING", "stock down 5%+ - thesis cracking, skip"


def build_payload(scan, quotes):
    tickets = scan.get("tickets", [])
    hunter_q = [t for t in tickets if t.get("hunter") and t["hunter"].get("qualified")]
    hunter_q.sort(key=lambda t: t["hunter"]["score"], reverse=True)
    top = hunter_q[:15]

    enriched = []
    for t in top:
        sym = t["ticker"].replace(".US", "")
        q = quotes.get(sym)
        if not q:
            continue
        scan_close = t.get("price")
        if not scan_close or scan_close <= 0:
            continue
        live = q["price"]
        pct = (live / scan_close - 1) * 100
        category, action = categorize_intraday_move(pct)
        enriched.append({
            "ticker": t["ticker"],
            "name": (t.get("name") or "")[:30],
            "tier": t.get("tier"),
            "hunter_score": t["hunter"]["score"],
            "scan_close": scan_close,
            "live": live,
            "live_bid": q.get("bid"),
            "live_ask": q.get("ask"),
            "intraday_move_pct": round(pct, 2),
            "category": category,
            "action": action,
            "stop_loss": t.get("stop_loss"),
            "phase1_target": t.get("phase1_target"),
            "options_trade": t.get("options_trade"),
            "lottery_score": (t.get("lottery_score") or {}).get("score"),
            "lottery_tier": (t.get("lottery_score") or {}).get("tier"),
        })
    enriched.sort(key=lambda x: x["hunter_score"], reverse=True)
    return enriched


TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; color:#222; }
.wrap { max-width:780px; margin:0 auto; background:#fff; padding:24px 28px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
h1 { font-size:20px; margin:0 0 6px; }
.meta { color:#666; font-size:12px; margin-bottom:18px; }
.intro { background:#fef3c7; border-left:4px solid #f59e0b; padding:10px 14px; border-radius:4px; margin:0 0 18px; font-size:12px; line-height:1.5; }
.pick { padding:10px 14px; margin-bottom:10px; background:#fafafa; border-radius:4px; border-left:4px solid #ccc; }
.pick.MISSED_BULLET { border-left-color:#7c2d12; background:#fdecec; }
.pick.CHASE_RISK { border-left-color:#e67e22; background:#fef3c7; }
.pick.STILL_ACTIONABLE { border-left-color:#1a9850; background:#f0fdf4; }
.pick.FLAT { border-left-color:#999; }
.pick.POSSIBLE_DIP_BUY { border-left-color:#4a90e2; background:#eef6ff; }
.pick.BREAKING { border-left-color:#c94545; background:#fdecec; opacity:0.7; }
.head { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px; }
.tk { font-weight:700; font-size:15px; }
.cat { font-size:10px; padding:2px 8px; border-radius:3px; font-weight:700; letter-spacing:0.5px; color:#fff; }
.cat.MISSED_BULLET { background:#7c2d12; }
.cat.CHASE_RISK { background:#e67e22; }
.cat.STILL_ACTIONABLE { background:#1a9850; }
.cat.FLAT { background:#999; }
.cat.POSSIBLE_DIP_BUY { background:#4a90e2; }
.cat.BREAKING { background:#c94545; }
.move { font-weight:700; font-size:14px; font-variant-numeric:tabular-nums; }
.up { color:#0d7b34; } .dn { color:#c94545; } .fl { color:#666; }
.row { font-size:11px; color:#444; margin:3px 0; }
.action { font-size:11px; color:#555; font-style:italic; margin-top:4px; }
.footer { margin-top:24px; font-size:10px; color:#999; text-align:center; }
</style></head>
<body>
<div class="wrap">
<h1>Mid-Session Update - {{ date }}</h1>
<div class="meta">{{ time_label }} - mid-US-session check on this morning's Hunter picks. Tells you whether each pick's entry window is still open or if the move already played out.</div>
<div class="intro">
<strong>Categories:</strong>
<br>STILL_ACTIONABLE = entry window open
<br>CHASE_RISK (+4-8% today) = reduced edge, half-size or wait
<br>MISSED_BULLET (+8%+) = move already happened, skip
<br>BREAKING (-5%+) = thesis cracking, skip
</div>
{% for p in picks %}
<div class="pick {{ p.category }}">
<div class="head">
<div>
<span class="tk">{{ p.ticker }}</span>
<span class="cat {{ p.category }}">{{ p.category|replace('_', ' ') }}</span>
<span style="font-size:11px; color:#666;">T{{ p.tier }} - Hunt {{ p.hunter_score }}{% if p.lottery_tier %} - Lottery {{ p.lottery_tier }}{% endif %}</span>
</div>
<div class="move {% if p.intraday_move_pct >= 1 %}up{% elif p.intraday_move_pct <= -1 %}dn{% else %}fl{% endif %}">
${{ "%.2f"|format(p.live) }} ({{ "%+.2f"|format(p.intraday_move_pct) }}%)
</div>
</div>
<div class="row"><strong>{{ p.name }}</strong></div>
<div class="row">Scan close ${{ "%.2f"|format(p.scan_close) }} -> Live ${{ "%.2f"|format(p.live) }}{% if p.live_bid and p.live_ask %} (bid ${{ "%.2f"|format(p.live_bid) }}/ask ${{ "%.2f"|format(p.live_ask) }}){% endif %}</div>
<div class="row">Stop ${{ "%.2f"|format(p.stop_loss) }} - Phase 1 ${{ "%.2f"|format(p.phase1_target) }}</div>
<div class="action">-> {{ p.action }}</div>
</div>
{% endfor %}
<div class="footer">swing-trading-scanner - mid-session update - flags missed bullets</div>
</div>
</body>
</html>"""


def main():
    load_alpaca()
    print(f"Mid-session check: starting at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
    scan, scan_id = load_latest_scan()
    if not scan:
        print("No scan file - exit")
        return
    print(f"Loaded {scan_id}")

    tickets = scan.get("tickets", [])
    hunter_q = [t for t in tickets if t.get("hunter") and t["hunter"].get("qualified")]
    if not hunter_q:
        print("No Hunter qualified picks - skipping")
        return

    print(f"Fetching live quotes for {len(hunter_q[:15])} picks")
    syms = [t["ticker"] for t in hunter_q[:15]]
    quotes = fetch_quotes(syms)
    print(f"Got {len(quotes)} quotes")

    picks = build_payload(scan, quotes)
    if not picks:
        print("No actionable enrichment - exit")
        return

    print(f"\n{len(picks)} picks categorized:")
    for p in picks:
        print(f"  {p['ticker']:10s} {p['intraday_move_pct']:+6.2f}%  {p['category']:18s}")

    if os.environ.get("SKIP_EMAIL"):
        out = RESULTS_DIR / f"midday_{scan.get('scan_date', scan_id)}.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(Template(TEMPLATE).render(
                date=scan.get("scan_date"),
                time_label=datetime.now(timezone.utc).strftime("%H:%M UTC"),
                picks=picks,
            ))
        print(f"SKIP_EMAIL - wrote {out}")
        return

    from src.email_report import send_email
    html = Template(TEMPLATE).render(
        date=scan.get("scan_date"),
        time_label=datetime.now(timezone.utc).strftime("%H:%M UTC"),
        picks=picks,
    )
    try:
        send_email(html, scan.get("scan_date"), subject=f"Mid-Session Update {scan.get('scan_date')}")
        print("Mid-session email sent")
    except Exception as e:
        print(f"Send failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

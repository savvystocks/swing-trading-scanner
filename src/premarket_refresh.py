import json
import os
import pathlib
from datetime import datetime
from jinja2 import Template

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "results"


def load_latest_scan():
    candidates = sorted(RESULTS_DIR.glob("scan_*.json"), reverse=True)
    if not candidates:
        return None, None
    path = candidates[0]
    with open(path) as f:
        return json.load(f), path.stem


def fetch_live_quotes(tickers, verbose=True):
    if not os.environ.get("ALPACA_API_KEY"):
        if verbose:
            print("  ALPACA_API_KEY missing")
        return {}
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
    except ImportError:
        return {}
    sc = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    symbols = list({t.replace(".US", "") for t in tickers})
    out = {}
    try:
        trades = sc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbols))
        quotes = sc.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbols))
    except Exception as e:
        if verbose:
            print(f"  Alpaca fetch failed: {type(e).__name__}: {str(e)[:150]}")
        return {}
    for sym in symbols:
        try:
            t = trades.get(sym) if isinstance(trades, dict) else None
            q = quotes.get(sym) if isinstance(quotes, dict) else None
            if t:
                out[sym] = {
                    "last_trade": float(t.price),
                    "last_trade_time": str(t.timestamp),
                }
                if q:
                    out[sym]["bid"] = float(q.bid_price)
                    out[sym]["ask"] = float(q.ask_price)
        except Exception:
            pass
    return out


def categorize_move(delta_pct):
    if delta_pct >= 5:
        return "STRONG_GAINER", "stock has gapped UP - chase risk, verify before buying"
    if delta_pct >= 2:
        return "MODEST_GAINER", "trend continuing into pre-market"
    if delta_pct >= -1:
        return "FLAT", "unchanged from yesterday's close"
    if delta_pct >= -3:
        return "WEAKENING", "trend cracking - reconsider"
    if delta_pct >= -5:
        return "DOWN", "stop-loss may already be near - verify"
    return "BROKEN", "trend broken - skip this name"


def build_refresh_payload(scan, verbose=True):
    tickets = scan.get("tickets", [])
    hunter_q = [t for t in tickets if t.get("hunter") and t["hunter"].get("qualified") and t.get("tier") and t["tier"] >= 3]
    hunter_q.sort(key=lambda t: t["hunter"]["score"], reverse=True)
    top = hunter_q[:10]
    if not top:
        return None

    us_top = [t for t in top if t.get("ticker", "").endswith(".US")]
    if not us_top:
        return None

    if verbose:
        print(f"  fetching live quotes for {len(us_top)} top Hunter picks")
    live = fetch_live_quotes([t["ticker"] for t in us_top], verbose=verbose)
    if not live:
        if verbose:
            print(f"  no live quotes - aborting refresh")
        return None

    enriched = []
    for t in us_top:
        sym = t["ticker"].replace(".US", "")
        l = live.get(sym)
        if not l:
            continue
        close = t.get("price")
        if not close:
            continue
        live_price = l["last_trade"]
        delta_pct = (live_price / close - 1) * 100
        delta_usd = live_price - close
        category, action = categorize_move(delta_pct)
        enriched.append({
            "ticker": t["ticker"],
            "name": (t.get("name") or "")[:30],
            "sector": t.get("sector") or "",
            "tier": t.get("tier"),
            "hunter_score": t["hunter"]["score"],
            "hunter_eta": t["hunter"].get("eta_label", ""),
            "hunter_reasons": t["hunter"].get("reasons", []),
            "scan_close": close,
            "live_price": live_price,
            "delta_pct": delta_pct,
            "delta_usd": delta_usd,
            "category": category,
            "action": action,
            "stop_loss": t.get("stop_loss"),
            "phase1_target": t.get("phase1_target"),
            "options_trade": t.get("options_trade"),
            "live_bid": l.get("bid"),
            "live_ask": l.get("ask"),
        })

    enriched.sort(key=lambda x: (-x["hunter_score"], -x["delta_pct"]))
    return enriched


PREMARKET_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; color:#222; }
.wrap { max-width:780px; margin:0 auto; background:#fff; padding:24px 28px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); }
h1 { font-size:20px; margin:0 0 6px; }
.meta { color:#666; font-size:12px; margin-bottom:18px; }
.intro { background:#eef6ff; border-left:4px solid #4a90e2; padding:10px 14px; border-radius:4px; margin:0 0 18px; font-size:12px; line-height:1.5; }
.pick { border-left:4px solid #ccc; padding:10px 14px; margin-bottom:10px; background:#fafafa; border-radius:4px; }
.pick.STRONG_GAINER { border-left-color:#0d7b34; background:#e7f5ec; }
.pick.MODEST_GAINER { border-left-color:#1a9850; }
.pick.FLAT { border-left-color:#999; }
.pick.WEAKENING { border-left-color:#e67e22; background:#fdf6ec; }
.pick.DOWN { border-left-color:#c94545; background:#fdecec; }
.pick.BROKEN { border-left-color:#a00; background:#fdecec; opacity:0.7; }
.head { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:6px; }
.tk { font-weight:700; font-size:15px; }
.cat { font-size:10px; padding:2px 8px; border-radius:3px; background:#eee; font-weight:700; letter-spacing:0.5px; }
.cat.STRONG_GAINER { background:#0d7b34; color:#fff; }
.cat.MODEST_GAINER { background:#1a9850; color:#fff; }
.cat.FLAT { background:#999; color:#fff; }
.cat.WEAKENING { background:#e67e22; color:#fff; }
.cat.DOWN { background:#c94545; color:#fff; }
.cat.BROKEN { background:#a00; color:#fff; }
.move { font-weight:700; font-size:14px; }
.up { color:#0d7b34; }
.dn { color:#c94545; }
.fl { color:#666; }
.row { font-size:11px; color:#444; margin:3px 0; }
.action { font-size:11px; color:#555; font-style:italic; margin-top:4px; }
.footer { margin-top:24px; font-size:10px; color:#999; text-align:center; }
</style></head>
<body>
<div class="wrap">
  <h1>Pre-Market Refresh - {{ date }}</h1>
  <div class="meta">{{ time_label }} - 30 min before US open. Top Hunter picks vs scan close. Verify live before executing.</div>
  <div class="intro">
    <strong>How to read this:</strong> green = stock holding or pushing higher overnight (entry still valid), orange/red = weakening or broken (verify or skip). Catalysts that fired in your morning swing scan may have already played out before US open. Use live bid/ask to size limit orders.
  </div>
  {% for p in picks %}
    <div class="pick {{ p.category }}">
      <div class="head">
        <div>
          <span class="tk">{{ p.ticker }}</span>
          <span class="cat {{ p.category }}">{{ p.category|replace('_',' ') }}</span>
          <span style="font-size:11px; color:#666;">T{{ p.tier }} - Hunter {{ p.hunter_score }}</span>
        </div>
        <div class="move {% if p.delta_pct >= 1 %}up{% elif p.delta_pct <= -1 %}dn{% else %}fl{% endif %}">
          ${{ "%.2f"|format(p.live_price) }} ({{ "%+.2f"|format(p.delta_pct) }}%)
        </div>
      </div>
      <div class="row"><strong>{{ p.name }}</strong> &middot; {{ p.sector }}</div>
      <div class="row">Scan close ${{ "%.2f"|format(p.scan_close) }} &rarr; Live ${{ "%.2f"|format(p.live_price) }}{% if p.live_bid and p.live_ask %} &middot; Bid/Ask ${{ "%.2f"|format(p.live_bid) }}/${{ "%.2f"|format(p.live_ask) }}{% endif %}</div>
      <div class="row">Stop ${{ "%.2f"|format(p.stop_loss) }} &middot; Phase 1 ${{ "%.2f"|format(p.phase1_target) }}</div>
      {% if p.hunter_reasons %}<div class="row" style="color:#8e44ad;">{{ p.hunter_reasons|join(' &middot; ') }}</div>{% endif %}
      <div class="action">&#8594; {{ p.action }}</div>
    </div>
  {% endfor %}
  <div class="footer">swing-trading-scanner &middot; pre-market refresh &middot; live data via Alpaca</div>
</div>
</body>
</html>"""


def render_premarket_email(picks, date_str):
    if not picks:
        return None
    tmpl = Template(PREMARKET_TEMPLATE)
    return tmpl.render(
        date=date_str,
        time_label=datetime.utcnow().strftime("%H:%M UTC"),
        picks=picks,
    )

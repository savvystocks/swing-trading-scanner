"""Parse Robinhood option fill emails and reconcile them into the truth file.

Robinhood quotes the fill as dollars PER CONTRACT (premium x 100). The rest of
the system stores entry_price as the per-share premium, so price_per_contract is
divided by 100 here. Verified against the real ETOR fill: $75.00/contract = 0.75
premium, 16 x $75 = $1,200 = the logged cost.
"""

import re
import html
from datetime import date, datetime


GBP_USD_RATE = 1.26


def _strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _parse_order_date(s):
    s = s.replace(",", "").strip()
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_expiry(raw, order_date):
    parts = raw.split("/")
    try:
        day = int(parts[0])
        month = int(parts[1])
    except (ValueError, IndexError):
        return None
    if len(parts) >= 3 and parts[2]:
        y = int(parts[2])
        year = 2000 + y if y < 100 else y
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    base_year = order_date.year if order_date else date.today().year
    for year in (base_year, base_year + 1):
        try:
            cand = date(year, month, day)
        except ValueError:
            return None
        if not order_date or cand >= order_date:
            return cand.isoformat()
    return date(base_year, month, day).isoformat()


def parse_fill_email(raw):
    text = _strip_html(raw or "")
    m = re.search(
        r"to\s+(buy|sell)(?:\s+to\s+(open|close))?\s+([\d,]+)\s+contracts?\s+of\s+"
        r"([A-Za-z][A-Za-z\.\-]*)\s+\$([\d,]+(?:\.\d+)?)\s+(Call|Put)\s+"
        r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
        text, re.IGNORECASE)
    if not m:
        return None
    pm = re.search(r"average price of\s+\$([\d,]+(?:\.\d+)?)\s+per\s+contract", text, re.IGNORECASE)
    if not pm:
        return None
    dm = re.search(
        r"\bon\s+(\d{1,2}\s+[A-Za-z]+,?\s+\d{4})(?:\s+at\s+(\d{1,2}:\d{2})\s*([A-Za-z]{2,4})?)?",
        text, re.IGNORECASE)

    order_date = _parse_order_date(dm.group(1)) if dm else None
    price_per_contract = float(pm.group(1).replace(",", ""))

    return {
        "action": m.group(1).upper(),
        "open_close": (m.group(2) or "").lower() or None,
        "contracts": int(m.group(3).replace(",", "")),
        "ticker": m.group(4).upper(),
        "strike": float(m.group(5).replace(",", "")),
        "side": "CALL" if m.group(6).lower() == "call" else "PUT",
        "expiration": _parse_expiry(m.group(7), order_date),
        "price_per_contract": price_per_contract,
        "premium": round(price_per_contract / 100.0, 4),
        "filled_date": order_date.isoformat() if order_date else None,
        "filled_time": dm.group(2) if dm else None,
        "tz": dm.group(3) if dm else None,
    }


def _eqf(a, b, tol=0.001):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _match(p, fill):
    return (p.get("status") == "OPEN"
            and p.get("ticker") == fill["ticker"]
            and p.get("side") == fill["side"]
            and _eqf(p.get("strike"), fill["strike"])
            and str(p.get("expiration", ""))[:10] == fill["expiration"])


def _has_fill(p, fill):
    mid = fill.get("message_id")
    return bool(mid) and any(f.get("message_id") == mid for f in (p.get("fills") or []))


def _attach_fill(p, fill):
    p.setdefault("fills", []).append({
        "message_id": fill.get("message_id"),
        "action": fill["action"],
        "contracts": fill["contracts"],
        "premium": fill["premium"],
        "price_per_contract": fill["price_per_contract"],
        "filled_date": fill["filled_date"],
        "filled_time": fill.get("filled_time"),
        "tz": fill.get("tz"),
    })


def apply_fill(positions, archive, fill):
    prem = fill["premium"]
    n = fill["contracts"]

    if fill["action"] == "BUY":
        for p in positions:
            if _match(p, fill):
                if _has_fill(p, fill):
                    return positions, archive, f"skip duplicate {fill['ticker']} buy"
                old_n = int(p.get("contracts") or 0)
                old_e = float(p.get("entry_price") or 0)
                if old_n == n and _eqf(old_e, prem, 0.005):
                    _attach_fill(p, fill)
                    p["broker"] = "Robinhood"
                    p["source"] = "robinhood_email"
                    return positions, archive, f"adopt existing {fill['ticker']} {n}x @ ${prem}"
                new_n = old_n + n
                new_e = round((old_e * old_n + prem * n) / new_n, 4)
                p["contracts"] = new_n
                p["entry_price"] = new_e
                p["cost_usd"] = round(new_e * 100 * new_n, 2)
                p["cost_gbp"] = round(p["cost_usd"] / GBP_USD_RATE, 2)
                p["source"] = "robinhood_email"
                _attach_fill(p, fill)
                return positions, archive, f"add {n}x {fill['ticker']} -> {new_n}x avg ${new_e}"
        cost = round(prem * 100 * n, 2)
        entry = {
            "ticker": fill["ticker"], "side": fill["side"], "strike": fill["strike"],
            "expiration": fill["expiration"], "entry_price": prem, "contracts": n,
            "cost_usd": cost, "cost_gbp": round(cost / GBP_USD_RATE, 2),
            "opened_at": fill["filled_date"], "broker": "Robinhood", "status": "OPEN",
            "source": "robinhood_email",
            "notes": f"Synced from Robinhood email {fill['filled_date']}",
        }
        _attach_fill(entry, fill)
        positions.append(entry)
        return positions, archive, f"open {n}x {fill['ticker']} {fill['side']} ${fill['strike']} @ ${prem}"

    for p in list(positions):
        if _match(p, fill):
            if _has_fill(p, fill):
                return positions, archive, f"skip duplicate {fill['ticker']} sell"
            open_n = int(p.get("contracts") or 0)
            entry = float(p.get("entry_price") or 0)
            sell_n = min(n, open_n)
            pnl_usd = (prem - entry) * 100 * sell_n
            pnl_gbp = round(pnl_usd / GBP_USD_RATE, 2)
            if n >= open_n:
                closed = dict(p)
                closed.update({
                    "status": "CLOSED", "exit_price": prem, "closed_at": fill["filled_date"],
                    "pnl_usd": round(pnl_usd, 2), "pnl_gbp": pnl_gbp,
                    "return_pct": round((prem - entry) / entry * 100, 1) if entry > 0 else 0,
                    "source": "robinhood_email",
                })
                _attach_fill(closed, fill)
                archive.append(closed)
                positions.remove(p)
                return positions, archive, f"close {fill['ticker']} {open_n}x @ ${prem} (PnL GBP {pnl_gbp:+.0f})"
            rem = open_n - n
            p["contracts"] = rem
            p["cost_usd"] = round(entry * 100 * rem, 2)
            p["cost_gbp"] = round(p["cost_usd"] / GBP_USD_RATE, 2)
            p.setdefault("trims", []).append({
                "at": fill["filled_date"], "trimmed_contracts": n,
                "trim_price": prem, "trim_pnl_gbp": pnl_gbp,
            })
            _attach_fill(p, fill)
            p["source"] = "robinhood_email"
            return positions, archive, f"trim {fill['ticker']} {n}x @ ${prem} -> {rem}x left (PnL GBP {pnl_gbp:+.0f})"

    return positions, archive, f"UNMATCHED sell {n}x {fill['ticker']} {fill['side']} ${fill['strike']} @ ${prem}"

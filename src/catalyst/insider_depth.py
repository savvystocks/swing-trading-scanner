from datetime import datetime, timedelta


CEO_TITLES = {"ceo", "chief executive officer", "president & ceo", "founder, ceo"}
CFO_TITLES = {"cfo", "chief financial officer"}
DIRECTOR_TITLES = {"director", "board member", "non-executive director"}


def _normalize_title(title):
    if not title:
        return ""
    return title.lower().strip()


def _is_buy(transaction):
    code = (transaction.get("transactionCode") or "").upper()
    type_str = (transaction.get("transactionType") or "").upper()
    if code in ("P", "A"):
        return True
    if "BUY" in type_str or "PURCHASE" in type_str:
        return True
    return False


def analyze_insider(client, eodhd_ticker, lookback_days=90):
    if not eodhd_ticker or not eodhd_ticker.endswith(".US"):
        return None
    try:
        transactions = client.insider_transactions(eodhd_ticker, limit=50)
    except Exception:
        return None
    if not transactions:
        return None

    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    cutoff_30 = datetime.utcnow().date() - timedelta(days=30)
    cutoff_14 = datetime.utcnow().date() - timedelta(days=14)

    buys_total = []
    buys_30d = []
    buys_14d = []
    sells_30d = []
    ceo_buys_90d = []
    cfo_buys_90d = []
    director_buys_90d = []
    big_purchase_flag = False
    unique_buyers_90d = set()

    for t in transactions:
        date_str = t.get("transactionDate") or t.get("date") or ""
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if d < cutoff:
            continue

        is_buy = _is_buy(t)
        owner = t.get("ownerCik") or t.get("ownerName") or ""
        title = _normalize_title(t.get("ownerTitle") or t.get("title") or "")

        try:
            shares = float(t.get("transactionShares") or 0)
        except Exception:
            shares = 0
        try:
            price = float(t.get("transactionPrice") or 0)
        except Exception:
            price = 0
        value = shares * price

        if is_buy:
            buys_total.append({"date": d, "value": value, "owner": owner, "title": title})
            unique_buyers_90d.add(owner)
            if d >= cutoff_30:
                buys_30d.append(value)
            if d >= cutoff_14:
                buys_14d.append(value)
            if any(c in title for c in CEO_TITLES):
                ceo_buys_90d.append({"date": d, "value": value})
            elif any(c in title for c in CFO_TITLES):
                cfo_buys_90d.append({"date": d, "value": value})
            elif any(c in title for c in DIRECTOR_TITLES):
                director_buys_90d.append({"date": d, "value": value})
            if value >= 1_000_000:
                big_purchase_flag = True
        else:
            if d >= cutoff_30:
                sells_30d.append(value)

    total_buy_value_90d = sum(b["value"] for b in buys_total)
    total_buy_value_30d = sum(buys_30d)
    total_buy_value_14d = sum(buys_14d)
    total_sell_value_30d = sum(sells_30d)
    net_30d = total_buy_value_30d - total_sell_value_30d

    today = datetime.utcnow().date()

    def _recency_weight(buy_date):
        days_ago = (today - buy_date).days
        if days_ago <= 14: return 1.0
        if days_ago <= 30: return 0.85
        if days_ago <= 60: return 0.60
        return 0.30

    def _weighted_value(buy_list, role_multiplier):
        total = 0.0
        for b in buy_list:
            total += b["value"] * role_multiplier * _recency_weight(b["date"])
        return total

    ceo_weighted = _weighted_value(ceo_buys_90d, 3.0)
    cfo_weighted = _weighted_value(cfo_buys_90d, 2.0)
    director_weighted = _weighted_value(director_buys_90d, 1.0)
    quality_score = ceo_weighted + cfo_weighted + director_weighted

    signals = []
    points = 0.0

    if ceo_buys_90d:
        ceo_raw = sum(b["value"] for b in ceo_buys_90d)
        ceo_recent = sum(b["value"] for b in ceo_buys_90d if (today - b["date"]).days <= 30)
        if ceo_recent >= 500_000:
            signals.append(f"CEO bought ${ceo_recent/1e3:.0f}K in last 30d (top weight)")
            points += 8
        elif ceo_raw >= 500_000:
            signals.append(f"CEO bought ${ceo_raw/1e3:.0f}K in 90d")
            points += 5
        elif ceo_raw >= 100_000:
            signals.append(f"CEO bought ${ceo_raw/1e3:.0f}K")
            points += 3
        elif ceo_raw > 0:
            signals.append(f"CEO bought ${ceo_raw/1e3:.0f}K (small)")
            points += 1

    if cfo_buys_90d:
        cfo_raw = sum(b["value"] for b in cfo_buys_90d)
        if cfo_raw >= 250_000:
            signals.append(f"CFO bought ${cfo_raw/1e3:.0f}K in 90d")
            points += 4
        elif cfo_raw > 0:
            signals.append(f"CFO bought ${cfo_raw/1e3:.0f}K")
            points += 2

    multi_role_buys = sum(1 for r in [ceo_buys_90d, cfo_buys_90d, director_buys_90d] if r)
    if multi_role_buys >= 3:
        signals.append("CEO + CFO + Director all buying (full C-suite cluster)")
        points += 5
    elif multi_role_buys == 2 and ceo_buys_90d:
        signals.append("CEO + 1 other officer buying")
        points += 2

    if big_purchase_flag:
        signals.append("$1M+ single-purchase in 90d")
        points += 4

    if len(unique_buyers_90d) >= 4:
        signals.append(f"{len(unique_buyers_90d)} unique buyers in 90d (broad cluster)")
        points += 4
    elif len(unique_buyers_90d) >= 3:
        signals.append(f"{len(unique_buyers_90d)} unique buyers in 90d")
        points += 3
    elif len(unique_buyers_90d) >= 2:
        signals.append(f"{len(unique_buyers_90d)} unique buyers in 90d")
        points += 2

    if total_buy_value_14d >= 500_000:
        signals.append(f"Heavy recent buying ${total_buy_value_14d/1e3:.0f}K in 14d")
        points += 4
    elif total_buy_value_14d >= 250_000:
        signals.append(f"Recent buying ${total_buy_value_14d/1e3:.0f}K in 14d")
        points += 2

    if total_sell_value_30d >= 1_000_000 and net_30d < -500_000:
        signals.append(f"Net selling: -${abs(net_30d)/1e6:.1f}M in 30d")
        points -= 4

    return {
        "points": round(min(points, 14), 2),
        "signals": signals,
        "ceo_buy_value_90d": int(sum(b["value"] for b in ceo_buys_90d)),
        "cfo_buy_value_90d": int(sum(b["value"] for b in cfo_buys_90d)),
        "director_buy_value_90d": int(sum(b["value"] for b in director_buys_90d)),
        "total_buy_value_90d": int(total_buy_value_90d),
        "total_sell_value_30d": int(total_sell_value_30d),
        "net_30d_value": int(net_30d),
        "unique_buyers_90d": len(unique_buyers_90d),
        "big_purchase_flag": big_purchase_flag,
        "quality_score": round(quality_score, 0),
        "ceo_recent_30d": sum(b["value"] for b in ceo_buys_90d if (today - b["date"]).days <= 30),
    }

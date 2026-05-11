import os


MACRO_TICKERS = {
    "yield_curve_short": "SHY.US",
    "yield_curve_long": "TLT.US",
    "credit_spread_hy": "HYG.US",
    "credit_spread_ig": "LQD.US",
    "dollar": "UUP.US",
    "gold": "GLD.US",
    "uranium": "URA.US",
    "lithium": "LIT.US",
    "oil": "USO.US",
    "copper": "CPER.US",
    "vix": "VIX.INDX",
    "vix_9d": "VIX9D.INDX",
    "vix_3m": "VIX3M.INDX",
    "semis_etf": "SOXX.US",
    "biotech_etf": "XBI.US",
    "regional_banks_etf": "KRE.US",
    "small_cap_etf": "IWM.US",
    "russell_growth_etf": "IWO.US",
    "qqq": "QQQ.US",
    "spy": "SPY.US",
}


def fetch_macro_snapshot(client):
    out = {}
    for label, ticker in MACRO_TICKERS.items():
        try:
            ohlcv = client.ohlcv(ticker)
            if not ohlcv or len(ohlcv) < 30:
                continue
            last = ohlcv[-1]
            d_5_ago = ohlcv[-6] if len(ohlcv) >= 6 else None
            d_30_ago = ohlcv[-31] if len(ohlcv) >= 31 else None
            try:
                price = float(last.get("close") or 0)
                p_5 = float(d_5_ago.get("close") or 0) if d_5_ago else None
                p_30 = float(d_30_ago.get("close") or 0) if d_30_ago else None
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            out[label] = {
                "ticker": ticker,
                "price": price,
                "roc_5d_pct": round((price - p_5) / p_5 * 100, 2) if p_5 else None,
                "roc_30d_pct": round((price - p_30) / p_30 * 100, 2) if p_30 else None,
            }
        except Exception:
            continue
    return out


def macro_regime_summary(snapshot):
    if not snapshot:
        return {"regime": "unknown", "summary": "no macro data"}

    flags = []

    yc = snapshot.get("yield_curve_long")
    if yc and yc.get("roc_30d_pct") is not None:
        if yc["roc_30d_pct"] > 3:
            flags.append("long bonds rallying (rates falling)")
        elif yc["roc_30d_pct"] < -3:
            flags.append("long bonds dumping (rates rising)")

    hyg = snapshot.get("credit_spread_hy")
    if hyg and hyg.get("roc_5d_pct") is not None:
        if hyg["roc_5d_pct"] < -1:
            flags.append("HY credit weakening (risk-off)")

    vix = snapshot.get("vix")
    vix_9d = snapshot.get("vix_9d")
    vix_3m = snapshot.get("vix_3m")
    vix_regime = "unknown"
    vix_term = None
    if vix:
        v = vix["price"]
        if v < 15:
            vix_regime = "low_vol"
        elif v <= 20:
            vix_regime = "normal"
        elif v <= 28:
            vix_regime = "elevated"
        else:
            vix_regime = "stressed"
        if vix_9d and vix_3m:
            try:
                v9 = vix_9d["price"]
                v3m = vix_3m["price"]
                if v9 > v * 1.05 and v > v3m:
                    vix_term = "BACKWARDATION (panic, mean-reversion buy signal)"
                    flags.append(vix_term)
                elif v3m > v * 1.10:
                    vix_term = "STEEP CONTANGO (calm, complacency risk)"
                    flags.append(vix_term)
            except Exception:
                pass

    dxy = snapshot.get("dollar")
    if dxy and dxy.get("roc_30d_pct") is not None:
        if dxy["roc_30d_pct"] < -3:
            flags.append(f"dollar weakening {dxy['roc_30d_pct']:.1f}%/30d (commodities/EM tailwind)")
        elif dxy["roc_30d_pct"] > 3:
            flags.append(f"dollar strengthening +{dxy['roc_30d_pct']:.1f}%/30d (commodities/EM headwind)")

    semis = snapshot.get("semis_etf")
    if semis and semis.get("roc_5d_pct") is not None and semis["roc_5d_pct"] >= 5:
        flags.append(f"semis +{semis['roc_5d_pct']:.1f}%/5d (sector ripping — chase momentum names)")
    biotech = snapshot.get("biotech_etf")
    if biotech and biotech.get("roc_5d_pct") is not None and biotech["roc_5d_pct"] >= 5:
        flags.append(f"biotech +{biotech['roc_5d_pct']:.1f}%/5d (XBI breakout — small caps in motion)")

    lithium = snapshot.get("lithium")
    if lithium and lithium.get("roc_30d_pct") is not None and lithium["roc_30d_pct"] > 8:
        flags.append(f"lithium ETF +{lithium['roc_30d_pct']:.0f}% in 30d (battery cycle hot)")

    uranium = snapshot.get("uranium")
    if uranium and uranium.get("roc_30d_pct") is not None and uranium["roc_30d_pct"] > 8:
        flags.append(f"uranium +{uranium['roc_30d_pct']:.0f}% in 30d (nuclear bid)")

    gold = snapshot.get("gold")
    if gold and gold.get("roc_30d_pct") is not None and gold["roc_30d_pct"] > 5:
        flags.append(f"gold +{gold['roc_30d_pct']:.0f}% (defensive bid / dollar weak)")

    return {
        "regime": vix_regime,
        "vix": vix["price"] if vix else None,
        "vix_9d": vix_9d["price"] if vix_9d else None,
        "vix_3m": vix_3m["price"] if vix_3m else None,
        "vix_term": vix_term,
        "flags": flags,
        "snapshot": snapshot,
    }


def index_rebalance_candidates(scored_results):
    candidates = {"sp500_promotion": [], "russell_top1000": []}
    for s in scored_results:
        mcap = s.get("market_cap") or 0
        ticker = s.get("ticker")
        if not ticker:
            continue
        if 10_000_000_000 <= mcap <= 25_000_000_000:
            candidates["sp500_promotion"].append({
                "ticker": ticker,
                "name": s.get("name"),
                "market_cap": mcap,
                "current_index": s.get("index"),
            })
        if 1_500_000_000 <= mcap <= 5_000_000_000:
            candidates["russell_top1000"].append({
                "ticker": ticker,
                "name": s.get("name"),
                "market_cap": mcap,
            })
    candidates["sp500_promotion"].sort(key=lambda x: x["market_cap"], reverse=True)
    candidates["russell_top1000"].sort(key=lambda x: x["market_cap"], reverse=True)
    return candidates

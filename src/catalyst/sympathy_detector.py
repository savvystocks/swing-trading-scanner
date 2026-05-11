from collections import defaultdict


def build_industry_index(scored_results):
    by_industry = defaultdict(list)
    for s in scored_results:
        industry = (s.get("industry") or "").strip().lower()
        if not industry:
            continue
        by_industry[industry].append(s)
    return by_industry


def detect_sympathy_moves(scored_results, min_peers_moved=2, peer_move_threshold=5.0, lookback_days=5):
    by_industry = build_industry_index(scored_results)
    out = {}
    for industry, peers in by_industry.items():
        if len(peers) < 3:
            continue
        movers = []
        for p in peers:
            ret_5d = p.get("ret_5d") or p.get("return_5d") or 0
            try:
                ret_5d = float(ret_5d)
            except (TypeError, ValueError):
                continue
            if ret_5d >= peer_move_threshold:
                movers.append({
                    "ticker": p.get("ticker"),
                    "ret_5d": ret_5d,
                    "mcap": p.get("market_cap") or 0,
                })
        if len(movers) < min_peers_moved:
            continue
        movers.sort(key=lambda x: x["ret_5d"], reverse=True)
        median_move = movers[len(movers) // 2]["ret_5d"]
        for p in peers:
            ticker = p.get("ticker")
            if not ticker:
                continue
            self_ret = p.get("ret_5d") or 0
            try:
                self_ret = float(self_ret)
            except (TypeError, ValueError):
                self_ret = 0
            if self_ret >= peer_move_threshold:
                continue
            laggard_gap = median_move - self_ret
            if laggard_gap < 3:
                continue
            top_peers = [m["ticker"] for m in movers[:3] if m["ticker"] != ticker]
            out[ticker] = {
                "key": "sector_sympathy",
                "industry": industry,
                "peers_moved": len(movers),
                "median_peer_move_5d": round(median_move, 1),
                "self_5d_move": round(self_ret, 1),
                "laggard_gap": round(laggard_gap, 1),
                "top_peer_movers": top_peers,
                "details": f"{len(movers)} peers in {industry[:30]} +{median_move:.1f}%/5d, this is laggard ({self_ret:+.1f}%)",
                "direction": "bull",
            }
    return out


def apply_sympathy_scoring(scored_results, sympathy_signals):
    for s in scored_results:
        ticker = s.get("ticker")
        if ticker not in sympathy_signals:
            continue
        sig = sympathy_signals[ticker]
        components = s.get("components") or {}
        score_delta = 0
        if sig["peers_moved"] >= 4 and sig["laggard_gap"] >= 7:
            score_delta = 5
        elif sig["peers_moved"] >= 3 and sig["laggard_gap"] >= 5:
            score_delta = 3
        elif sig["peers_moved"] >= 2:
            score_delta = 2
        if score_delta > 0:
            components["sympathy"] = {
                "points": score_delta,
                "label": f"sector sympathy: {sig['details']} (peers: {', '.join(sig['top_peer_movers'][:3])})",
            }
            s["components"] = components
            s["score"] = round((s.get("score") or 0) + score_delta, 2)
    return scored_results

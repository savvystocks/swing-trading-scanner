from collections import defaultdict


def peer_signals(scored_candidates):
    by_sector = defaultdict(list)
    for c in scored_candidates:
        sector = c.get("sector")
        if sector:
            by_sector[sector].append(c)
    return by_sector


def peer_confirmation_score(ticker, sector, sector_map, min_peers_with_signal=3, points_max=5.0):
    if not sector or sector not in sector_map:
        return {"points": 0.0, "label": "no sector match"}
    peers = sector_map[sector]
    peers_with_catalyst = [p for p in peers if p.get("ticker") != ticker and len(p.get("catalysts") or []) > 0]
    n = len(peers_with_catalyst)
    if n >= min_peers_with_signal:
        points = points_max
        label = f"{n} peers with catalysts (sector wave)"
    elif n >= 1:
        points = points_max * 0.5
        label = f"{n} peer(s) with catalyst"
    else:
        points = 0.0
        label = "no peers with catalysts"
    return {"points": round(points, 2), "label": label, "peer_count": n}

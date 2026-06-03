"""Sector concentration warning.

If multiple high-tier picks share a sector, flag the risk. Five semis at
40% MAX_CONVICTION each = 200% account exposure to one industry move.
"""


WARN_THRESHOLD = 3   # warn if 3+ ELITE+ picks in same sector
CRITICAL_THRESHOLD = 4


def check_concentration(picks):
    """Group ELITE+ picks by sector, return list of warnings."""
    if not picks:
        return []
    by_sector = {}
    for p in picks:
        c = p.get("_confluence") or {}
        tier = c.get("tier", "PASS")
        if tier not in ("ELITE", "MAX_CONVICTION", "GAMMA_BOMB"):
            continue
        sector = p.get("sector") or "Unknown"
        by_sector.setdefault(sector, []).append({
            "ticker": p.get("ticker"),
            "tier": tier,
            "side": c.get("side"),
            "size_pct": c.get("size_pct", 0),
        })

    warnings = []
    for sector, entries in by_sector.items():
        if len(entries) >= WARN_THRESHOLD:
            total_size = sum(e["size_pct"] for e in entries)
            level = "CRITICAL" if len(entries) >= CRITICAL_THRESHOLD else "WARNING"
            tickers = ", ".join(f"{e['ticker']}({e['tier']}/{e['size_pct']}%)" for e in entries)
            warnings.append({
                "level": level,
                "sector": sector,
                "count": len(entries),
                "total_size_pct": total_size,
                "tickers": tickers,
                "label": (f"{level}: {len(entries)} {sector} picks total {total_size}% account "
                         f"size = concentrated bet on one industry. Consider trimming or skipping "
                         f"redundant names. ({tickers})"),
            })
    return warnings

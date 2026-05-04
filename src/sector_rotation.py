from src.sectors import GICS_TO_ETF


def build_sector_state_map(sector_perf_list):
    state_map = {}
    for sp in sector_perf_list or []:
        etf = sp.get("etf")
        if not etf:
            continue
        state_map[etf] = {
            "stage": sp.get("stage"),
            "outlook": sp.get("outlook"),
            "pct_above_200d": sp.get("pct_above_200d"),
            "rs_vs_spy": sp.get("rs_vs_spy"),
            "rotation_maturity": sp.get("rotation_maturity"),
        }
    return state_map


def apply_sector_overlay_to_hunter(scored_results, sector_perf_list, verbose=True):
    sector_states = build_sector_state_map(sector_perf_list)
    if not sector_states:
        return scored_results

    boosted = 0
    penalized = 0
    disqualified = 0

    for r in scored_results:
        ticket = r.get("ticket") if isinstance(r, dict) and "ticket" in r else r
        if not ticket:
            continue
        sector = ticket.get("sector")
        etf_tuple = GICS_TO_ETF.get(sector)
        if not etf_tuple:
            continue
        etf = etf_tuple[0]
        state = sector_states.get(etf)
        if not state:
            continue

        h = ticket.get("hunter")
        if not h:
            continue

        score = h.get("score", 0)
        reasons = list(h.get("reasons", []))
        stage = state.get("stage")
        outlook = state.get("outlook")
        pct_200 = state.get("pct_above_200d")

        adjustment = 0
        if stage == 2 and outlook in ("LEADING", "STRONG"):
            adjustment = 8
            reasons.append(f"sector tailwind: {etf} Stage 2 {outlook} ({pct_200:+.1f}% vs 200d)")
            boosted += 1
        elif stage == 2:
            adjustment = 4
            reasons.append(f"sector neutral-bull: {etf} Stage 2 {outlook}")
        elif stage == 4:
            adjustment = -15
            reasons.append(f"SECTOR HEADWIND: {etf} Stage 4 ({pct_200:+.1f}% vs 200d)")
            penalized += 1
        elif stage == 3:
            adjustment = -5
            reasons.append(f"sector cooling: {etf} Stage 3 ({pct_200:+.1f}% vs 200d)")
            penalized += 1

        new_score = max(0, min(100, score + adjustment))
        h["score"] = new_score
        h["reasons"] = reasons
        h["sector_overlay"] = {
            "etf": etf,
            "stage": stage,
            "outlook": outlook,
            "pct_above_200d": pct_200,
            "adjustment": adjustment,
        }

        if new_score < 50 and h.get("qualified"):
            h["qualified"] = False
            h.setdefault("disqualified", []).append("sector_rotation_filter")
            disqualified += 1

    if verbose:
        print(f"  sector_rotation: boosted={boosted} penalized={penalized} disqualified={disqualified}")
    return scored_results

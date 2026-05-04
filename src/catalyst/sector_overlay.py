from src.sectors import GICS_TO_ETF


def build_state_map(sector_perf_list):
    state = {}
    for sp in sector_perf_list or []:
        etf = sp.get("etf")
        if not etf:
            continue
        state[etf] = {
            "stage": sp.get("stage"),
            "outlook": sp.get("outlook"),
            "pct_above_200d": sp.get("pct_above_200d"),
        }
    return state


def apply_catalyst_sector_overlay(final_scored, sector_perf_list, verbose=True):
    state = build_state_map(sector_perf_list)
    if not state:
        return final_scored

    boosted = 0
    penalized = 0

    for s in final_scored:
        sector = s.get("sector")
        etf_tuple = GICS_TO_ETF.get(sector)
        if not etf_tuple:
            continue
        etf = etf_tuple[0]
        st = state.get(etf)
        if not st:
            continue

        stage = st.get("stage")
        outlook = st.get("outlook")
        pct_200 = st.get("pct_above_200d")
        adjustment = 0
        label = ""

        if stage == 2 and outlook in ("LEADING", "STRONG"):
            adjustment = 5
            label = f"sector tailwind: {etf} Stage 2 {outlook} ({pct_200:+.1f}% vs 200d)"
            boosted += 1
        elif stage == 2:
            adjustment = 2
            label = f"sector neutral-bull: {etf} Stage 2 {outlook}"
        elif stage == 4:
            adjustment = -8
            label = f"sector headwind: {etf} Stage 4 ({pct_200:+.1f}% vs 200d) - catalyst likely fades"
            penalized += 1
        elif stage == 3:
            adjustment = -3
            label = f"sector cooling: {etf} Stage 3"
            penalized += 1

        if adjustment != 0:
            new_score = max(0, s["score"] + adjustment)
            s["score"] = round(new_score, 2)
            s.setdefault("components", {})["sector_overlay"] = {
                "points": adjustment,
                "label": label,
                "etf": etf,
                "stage": stage,
                "outlook": outlook,
                "pct_above_200d": pct_200,
            }

    if verbose:
        print(f"  catalyst sector overlay: boosted={boosted} penalized={penalized}")
    return final_scored

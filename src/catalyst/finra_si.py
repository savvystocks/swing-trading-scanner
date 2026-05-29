import requests


FINRA_RSS = "https://api.finra.org/data/group/otcMarket/name/regSHODaily"

UA = "Catalyst-Scanner savvastgeorgiou@gmail.com"


def fetch_si_delta(ticker, periods=2):
    url = "https://www.nasdaq.com/api/quote/{ticker}/short-interest"
    out = {"ticker": ticker, "current_si_pct": None, "previous_si_pct": None, "delta_pct": None}
    return out


def short_interest_squeeze_score(short_pct_float, days_to_cover, si_delta_pct=None):
    score = 0
    flags = []
    if short_pct_float is None:
        return {"score": 0, "flags": ["no SI data"]}

    if short_pct_float >= 30:
        score += 4
        flags.append(f"SI {short_pct_float:.0f}% (extreme)")
    elif short_pct_float >= 20:
        score += 3
        flags.append(f"SI {short_pct_float:.0f}% (high)")
    elif short_pct_float >= 15:
        score += 2

    if days_to_cover is not None:
        if days_to_cover >= 7:
            score += 3
            flags.append(f"DTC {days_to_cover:.1f}d (severe)")
        elif days_to_cover >= 4:
            score += 2

    if si_delta_pct is not None:
        if si_delta_pct <= -10:
            score += 3
            flags.append(f"SI dropping fast ({si_delta_pct:+.0f}%) — covering pre-event")
        elif si_delta_pct >= 10:
            score -= 1
            flags.append(f"SI rising ({si_delta_pct:+.0f}%) — bears piling on")

    return {"score": score, "flags": flags}

"""For each pick, determine whether CALL or PUT has higher edge.

Unified ranking: every ticker has Conviction (bull) and Bear_Conviction.
Whichever is higher determines the trade direction. Output added to pick
as `_direction` with the winning score + side label.
"""


def determine_direction(pick):
    call_score = (pick.get("_conviction") or {}).get("score") or 0
    put_score = (pick.get("_bear_conviction") or {}).get("score") or 0

    try:
        call_score = float(call_score)
    except (TypeError, ValueError):
        call_score = 0
    try:
        put_score = float(put_score)
    except (TypeError, ValueError):
        put_score = 0

    if put_score > call_score and put_score >= 60:
        return {
            "side": "PUT",
            "winning_score": put_score,
            "call_score": call_score,
            "put_score": put_score,
            "edge_pts": put_score - call_score,
            "label": "📉 PUT",
        }
    elif call_score >= put_score and call_score >= 50:
        return {
            "side": "CALL",
            "winning_score": call_score,
            "call_score": call_score,
            "put_score": put_score,
            "edge_pts": call_score - put_score,
            "label": "📈 CALL",
        }
    else:
        winning = max(call_score, put_score)
        side = "CALL" if call_score >= put_score else "PUT"
        return {
            "side": side,
            "winning_score": winning,
            "call_score": call_score,
            "put_score": put_score,
            "edge_pts": abs(call_score - put_score),
            "label": f"📈 CALL" if side == "CALL" else "📉 PUT",
        }


def apply_directions(picks, verbose=False):
    if not picks:
        return
    counts = {"CALL": 0, "PUT": 0}
    for p in picks:
        try:
            d = determine_direction(p)
            p["_direction"] = d
            counts[d["side"]] += 1
        except Exception:
            continue
    if verbose:
        print(f"  direction_picker: {counts['CALL']} CALLs / {counts['PUT']} PUTs")

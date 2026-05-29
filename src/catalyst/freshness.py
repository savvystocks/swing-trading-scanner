from datetime import datetime, timezone


def freshness_score(signals, points_max=5.0):
    fresh_hours = None
    for s in signals:
        details = s.get("details", "")
        if "filed " in details:
            try:
                date_part = details.split("filed ")[-1].strip()[:10]
                d = datetime.strptime(date_part, "%Y-%m-%d")
                d = d.replace(tzinfo=timezone.utc)
                hours_ago = (datetime.now(timezone.utc) - d).total_seconds() / 3600
                if fresh_hours is None or hours_ago < fresh_hours:
                    fresh_hours = hours_ago
            except Exception:
                pass
    if fresh_hours is None:
        return {"points": 0.0, "label": "no filing freshness data"}
    if fresh_hours < 6:
        points = points_max
        label = f"very fresh ({fresh_hours:.0f}h ago)"
    elif fresh_hours < 24:
        points = points_max * 0.7
        label = f"fresh ({fresh_hours:.0f}h ago)"
    elif fresh_hours < 48:
        points = points_max * 0.4
        label = f"recent ({fresh_hours:.0f}h ago)"
    elif fresh_hours < 96:
        points = points_max * 0.2
        label = f"older ({fresh_hours:.0f}h ago)"
    else:
        points = 0.0
        label = f"stale ({fresh_hours:.0f}h ago)"
    return {"points": round(points, 2), "label": label, "hours_ago": round(fresh_hours, 1)}

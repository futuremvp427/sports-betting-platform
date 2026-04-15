def detect_patterns(bets):
    patterns = {}

    for b in bets:
        key = (b.get("sport"), b.get("bet_type"))

        if key not in patterns:
            patterns[key] = {"wins": 0, "losses": 0}

        if b.get("result") == "win":
            patterns[key]["wins"] += 1
        elif b.get("result") == "loss":
            patterns[key]["losses"] += 1

    insights = {}

    for k, v in patterns.items():
        total = v["wins"] + v["losses"]
        win_rate = v["wins"] / total if total > 0 else 0

        insights[k] = {
            "win_rate": win_rate,
            "sample_size": total
        }

    return insights

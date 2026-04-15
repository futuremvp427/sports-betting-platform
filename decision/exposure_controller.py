def limit_exposure(bets, max_per_team=1):
    seen = set()
    filtered = []

    for b in bets:
        team = b.get("team")
        if team in seen:
            continue

        seen.add(team)
        filtered.append(b)

    return filtered

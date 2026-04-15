def track_performance(bets):
    total = len(bets)
    wins = sum(1 for b in bets if b.get("result") == "win")
    losses = sum(1 for b in bets if b.get("result") == "loss")

    win_rate = wins / total if total > 0 else 0

    return {
        "total_bets": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }

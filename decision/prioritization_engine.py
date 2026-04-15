def rank_bets(decisions):
    ranked = sorted(decisions, key=lambda x: x.get("probability", 0), reverse=True)
    return ranked


def filter_top_bets(ranked, limit=5):
    return ranked[:limit]

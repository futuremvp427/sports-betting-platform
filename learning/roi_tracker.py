def calculate_roi(settled_bets):
    total_risked = sum(b.get("stake", 0) for b in settled_bets)
    total_profit = sum(b.get("profit", 0) for b in settled_bets)

    roi = (total_profit / total_risked) if total_risked > 0 else 0

    return {
        "total_risked": total_risked,
        "total_profit": total_profit,
        "roi": roi
    }

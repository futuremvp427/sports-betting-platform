from decision.strategy import evaluate_bet

def run_decision_pipeline(predictions):
    results = []
    for p in predictions:
        decision = evaluate_bet(p.get("probability", 0), p.get("odds", 0))
        results.append({
            "game_id": p.get("game_id"),
            "team": p.get("team"),
            "decision": decision,
            "probability": p.get("probability"),
            "odds": p.get("odds")
        })
    return results

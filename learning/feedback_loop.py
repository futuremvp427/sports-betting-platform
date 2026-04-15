def update_model_memory(past_results):
    """
    Builds learning memory from past bets
    """

    adjustments = []

    for r in past_results:
        error = r.get("actual_result", 0) - r.get("predicted_probability", 0)

        adjustments.append({
            "game_id": r.get("game_id"),
            "error": error
        })

    return adjustments

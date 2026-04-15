def adjust_weights(current_weights, feedback):
    """
    Adjusts model weights based on error feedback
    """

    updated = current_weights.copy()

    for f in feedback:
        error = f.get("error", 0)

        # simple gradient-style adjustment
        updated["confidence_weight"] = max(0, updated.get("confidence_weight", 1) + error * 0.01)

    return updated

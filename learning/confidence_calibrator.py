def calibrate_confidence(predictions, historical_accuracy=0.55):
    calibrated = []

    for p in predictions:
        raw = p.get("probability", 0)

        # adjust confidence based on historical accuracy
        adjusted = raw * historical_accuracy

        calibrated.append({
            **p,
            "calibrated_probability": adjusted
        })

    return calibrated

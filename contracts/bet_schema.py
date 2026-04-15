REQUIRED_BET_FIELDS = {
    "sport": str,
    "event_id": (str, int),
    "team": str,
    "bet_type": str,
    "probability": (int, float),
    "odds": (int, float),
}

OPTIONAL_BET_FIELDS = {
    "stake": (int, float),
    "result": str,
    "profit": (int, float),
    "confidence": (int, float),
}


def validate_bet_record(record):
    errors = []

    for field, expected_type in REQUIRED_BET_FIELDS.items():
        if field not in record:
            errors.append(f"missing:{field}")
            continue
        if not isinstance(record[field], expected_type):
            errors.append(f"invalid_type:{field}")

    for field, expected_type in OPTIONAL_BET_FIELDS.items():
        if field in record and not isinstance(record[field], expected_type):
            errors.append(f"invalid_type:{field}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }

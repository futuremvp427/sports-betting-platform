WEIGHT_HISTORY = []


def save_weights(weights):
    WEIGHT_HISTORY.append(weights.copy())


def get_history():
    return WEIGHT_HISTORY

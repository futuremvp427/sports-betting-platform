def calculate_drawdown(bankroll_history):
    peak = bankroll_history[0] if bankroll_history else 0
    max_drawdown = 0

    for value in bankroll_history:
        if value > peak:
            peak = value

        drawdown = (peak - value)

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return {
        "max_drawdown": max_drawdown
    }

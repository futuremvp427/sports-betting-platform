from learning.performance_tracker import track_performance
from learning.roi_tracker import calculate_roi
from learning.drawdown_tracker import calculate_drawdown
from core.continuous_learning_engine import run_learning_cycle


def run_intelligence_cycle(bets, bankroll_history, weights):
    performance = track_performance(bets)
    roi_data = calculate_roi(bets)
    drawdown = calculate_drawdown(bankroll_history)

    learning = run_learning_cycle(bets, weights)

    return {
        "performance": performance,
        "roi": roi_data,
        "drawdown": drawdown,
        "learning": learning
    }

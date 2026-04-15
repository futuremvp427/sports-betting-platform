from core.system_engine import run_full_system


def run_simulation_cycles(predictions, cycles=50):
    history = []

    for i in range(cycles):
        result = run_full_system(predictions)
        history.append(result)

    return history

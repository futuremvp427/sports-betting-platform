import random


def simulate_outcome(probability):
    return "win" if random.random() < probability else "loss"


def run_simulation_cycles_v2(predictions, cycles=50):
    history = []

    for _ in range(cycles):
        cycle_results = []

        for p in predictions:
            prob = p.get("probability", 0.5)
            outcome = simulate_outcome(prob)

            simulated = {
                **p,
                "result": outcome
            }

            cycle_results.append(simulated)

        history.append(cycle_results)

    return history

from learning.feedback_loop import update_model_memory
from learning.adaptive_weights import adjust_weights


def run_learning_cycle(past_results, current_weights):
    """
    Full learning loop:
    results -> feedback -> weight adjustment
    """

    feedback = update_model_memory(past_results)
    new_weights = adjust_weights(current_weights, feedback)

    return {
        "feedback": feedback,
        "updated_weights": new_weights
    }

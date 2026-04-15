from decision.pipeline_engine_v2 import run_decision_pipeline


def run_full_system(predictions):
    """
    Master system orchestrator
    predictions -> decisions -> output
    """

    decisions = run_decision_pipeline(predictions)

    return {
        "total_predictions": len(predictions),
        "decisions": decisions
    }

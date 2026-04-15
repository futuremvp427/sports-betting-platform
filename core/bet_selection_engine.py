from decision.prioritization_engine import rank_bets, filter_top_bets
from decision.exposure_controller import limit_exposure


def select_bets(decisions):
    ranked = rank_bets(decisions)
    top = filter_top_bets(ranked)
    final = limit_exposure(top)

    return final

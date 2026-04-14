"""
Decision engine - converts predictions into actionable betting decisions.
Handles implied probability, expected value, edge scoring, bet sizing (Kelly),
and decision justification. Keeps predictive betting separate from arbitrage.
"""
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime

from config import settings
from config.logging_config import get_logger

logger = get_logger("decision")


class DecisionEngine:
    """
    Converts calibrated predictions into betting decisions.
    Calculates EV, edge, and recommended stakes using Kelly criterion.
    """

    def __init__(self, bankroll: float = None):
        self.bankroll = bankroll or settings.betting.initial_bankroll
        self.min_edge = settings.betting.min_edge
        self.kelly_fraction = settings.betting.kelly_fraction
        self.max_bet_fraction = settings.betting.max_bet_fraction

    @staticmethod
    def american_to_decimal(american_odds: float) -> float:
        """Convert American odds to decimal odds."""
        if american_odds > 0:
            return (american_odds / 100) + 1
        elif american_odds < 0:
            return (100 / abs(american_odds)) + 1
        return 1.0

    @staticmethod
    def decimal_to_implied_prob(decimal_odds: float) -> float:
        """Convert decimal odds to implied probability."""
        if decimal_odds <= 0:
            return 1.0
        return 1.0 / decimal_odds

    @staticmethod
    def american_to_implied_prob(american_odds: float) -> float:
        """Convert American odds to implied probability."""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        elif american_odds < 0:
            return abs(american_odds) / (abs(american_odds) + 100)
        return 1.0

    def calculate_ev(self, predicted_prob: float, decimal_odds: float) -> float:
        """
        Calculate expected value of a bet.
        EV = (prob * (odds - 1)) - ((1 - prob) * 1)
        Positive EV means profitable in the long run.
        """
        if decimal_odds <= 1:
            return -1.0
        ev = (predicted_prob * (decimal_odds - 1)) - ((1 - predicted_prob) * 1)
        return round(ev, 4)

    def calculate_edge(self, predicted_prob: float, implied_prob: float) -> float:
        """
        Calculate the edge (advantage) over the market.
        Edge = predicted_prob - implied_prob
        """
        return round(predicted_prob - implied_prob, 4)

    def kelly_stake(self, predicted_prob: float, decimal_odds: float) -> float:
        """
        Calculate optimal stake using fractional Kelly criterion.
        Kelly% = (bp - q) / b
        where b = decimal_odds - 1, p = win probability, q = 1 - p
        """
        b = decimal_odds - 1
        if b <= 0:
            return 0.0

        p = predicted_prob
        q = 1 - p
        kelly = (b * p - q) / b

        if kelly <= 0:
            return 0.0

        # Apply fraction and cap
        fractional_kelly = kelly * self.kelly_fraction
        max_stake = self.bankroll * self.max_bet_fraction
        recommended = min(fractional_kelly * self.bankroll, max_stake)

        return round(max(0, recommended), 2)

    def evaluate_bet(self, prediction: Dict[str, Any],
                     odds_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a single betting opportunity.
        Combines prediction with odds to produce a decision.
        """
        # Get the predicted probability for the recommended side
        home_prob = prediction.get("calibrated_home_prob",
                                    prediction.get("home_win_prob", 0.5))
        away_prob = prediction.get("calibrated_away_prob",
                                    prediction.get("away_win_prob", 0.5))

        home_odds = odds_data.get("home_odds")
        away_odds = odds_data.get("away_odds")

        decisions = []

        # Evaluate home side
        if home_odds is not None:
            home_decimal = self.american_to_decimal(home_odds)
            home_implied = self.american_to_implied_prob(home_odds)
            home_edge = self.calculate_edge(home_prob, home_implied)
            home_ev = self.calculate_ev(home_prob, home_decimal)
            home_stake = self.kelly_stake(home_prob, home_decimal)

            if home_edge >= self.min_edge and home_ev > 0:
                decisions.append({
                    "side": "home",
                    "team": prediction.get("home_team", "Unknown"),
                    "odds": home_odds,
                    "decimal_odds": round(home_decimal, 4),
                    "implied_prob": round(home_implied, 4),
                    "predicted_prob": round(home_prob, 4),
                    "edge": home_edge,
                    "expected_value": home_ev,
                    "recommended_stake": home_stake,
                    "kelly_fraction": round(home_stake / self.bankroll if self.bankroll > 0 else 0, 4),
                    "confidence": prediction.get("confidence", 0),
                    "sportsbook": odds_data.get("sportsbook", "unknown"),
                })

        # Evaluate away side
        if away_odds is not None:
            away_decimal = self.american_to_decimal(away_odds)
            away_implied = self.american_to_implied_prob(away_odds)
            away_edge = self.calculate_edge(away_prob, away_implied)
            away_ev = self.calculate_ev(away_prob, away_decimal)
            away_stake = self.kelly_stake(away_prob, away_decimal)

            if away_edge >= self.min_edge and away_ev > 0:
                decisions.append({
                    "side": "away",
                    "team": prediction.get("away_team", "Unknown"),
                    "odds": away_odds,
                    "decimal_odds": round(away_decimal, 4),
                    "implied_prob": round(away_implied, 4),
                    "predicted_prob": round(away_prob, 4),
                    "edge": away_edge,
                    "expected_value": away_ev,
                    "recommended_stake": away_stake,
                    "kelly_fraction": round(away_stake / self.bankroll if self.bankroll > 0 else 0, 4),
                    "confidence": prediction.get("confidence", 0),
                    "sportsbook": odds_data.get("sportsbook", "unknown"),
                })

        return decisions

    def evaluate_slate(self, predictions: List[Dict], odds_list: List[Dict]) -> List[Dict[str, Any]]:
        """
        Evaluate all games on a slate.
        Matches predictions with odds and produces bet recommendations.
        """
        all_decisions = []

        for prediction in predictions:
            home_team = prediction.get("home_team", "")
            away_team = prediction.get("away_team", "")

            # Find matching odds
            matching_odds = [
                o for o in odds_list
                if (o.get("home_team", "") == home_team or
                    o.get("home_team_name", "") == home_team)
            ]

            for odds_data in matching_odds:
                decisions = self.evaluate_bet(prediction, odds_data)
                for decision in decisions:
                    decision["home_team"] = home_team
                    decision["away_team"] = away_team
                    decision["decision_type"] = "value_bet"
                    decision["justification"] = self._generate_justification(decision)
                    all_decisions.append(decision)

        # Sort by edge descending
        all_decisions.sort(key=lambda x: x.get("edge", 0), reverse=True)

        # Filter low-confidence bets
        min_confidence = settings.model.min_confidence
        filtered = [d for d in all_decisions if d.get("confidence", 0) >= min_confidence - 0.5]

        logger.info(f"Evaluated slate: {len(filtered)} value bets from {len(predictions)} games")
        return filtered

    def _generate_justification(self, decision: Dict[str, Any]) -> str:
        """Generate a human-readable justification for a bet decision."""
        parts = []
        parts.append(f"Side: {decision.get('team')} ({decision.get('side')})")
        parts.append(f"Edge: {decision.get('edge', 0):.1%} over market")
        parts.append(f"Predicted: {decision.get('predicted_prob', 0):.1%} vs Implied: {decision.get('implied_prob', 0):.1%}")
        parts.append(f"EV: {decision.get('expected_value', 0):+.2%}")
        parts.append(f"Kelly stake: ${decision.get('recommended_stake', 0):.2f}")
        parts.append(f"Confidence: {decision.get('confidence', 0):.1%}")
        return " | ".join(parts)

    def update_bankroll(self, new_bankroll: float):
        """Update the bankroll for stake calculations."""
        self.bankroll = new_bankroll
        logger.info(f"Bankroll updated to ${self.bankroll:.2f}")

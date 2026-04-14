"""
Arbitrage scanner - detects arbitrage opportunities across sportsbooks.
Adapted from ArbitrageFinder patterns.
Completely separate from predictive betting logic.
"""
import itertools
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from config import settings
from config.logging_config import get_logger

logger = get_logger("arbitrage")


class ArbitrageScanner:
    """
    Scans odds across multiple sportsbooks to find arbitrage opportunities.
    An arbitrage exists when the combined implied probabilities across books < 1.
    """

    def __init__(self, min_profit_pct: float = None):
        self.min_profit_pct = min_profit_pct or settings.arbitrage.min_profit_pct

    @staticmethod
    def american_to_decimal(american_odds: float) -> float:
        """Convert American odds to decimal."""
        if american_odds > 0:
            return (american_odds / 100) + 1
        elif american_odds < 0:
            return (100 / abs(american_odds)) + 1
        return 1.0

    @staticmethod
    def implied_prob(decimal_odds: float) -> float:
        """Convert decimal odds to implied probability."""
        if decimal_odds <= 0:
            return 1.0
        return 1.0 / decimal_odds

    def find_arbitrage(self, odds_by_book: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find arbitrage opportunities from a list of odds snapshots.
        Groups odds by game and checks all book combinations.

        odds_by_book: list of dicts with keys:
            external_game_id, sportsbook, home_odds, away_odds,
            home_team (optional), away_team (optional)
        """
        # Group by game
        games = {}
        for odds in odds_by_book:
            game_id = odds.get("external_game_id") or odds.get("game_id")
            if game_id not in games:
                games[game_id] = {
                    "home_team": odds.get("home_team", odds.get("home_team_name", "Home")),
                    "away_team": odds.get("away_team", odds.get("away_team_name", "Away")),
                    "sport": odds.get("sport", "unknown"),
                    "books": [],
                }
            if odds.get("home_odds") is not None and odds.get("away_odds") is not None:
                games[game_id]["books"].append({
                    "sportsbook": odds.get("sportsbook", "unknown"),
                    "home_odds": float(odds["home_odds"]),
                    "away_odds": float(odds["away_odds"]),
                    "home_decimal": self.american_to_decimal(float(odds["home_odds"])),
                    "away_decimal": self.american_to_decimal(float(odds["away_odds"])),
                })

        opportunities = []

        for game_id, game_data in games.items():
            books = game_data["books"]
            if len(books) < 2:
                continue

            # Check all pairs of books
            for book_a, book_b in itertools.combinations(books, 2):
                # Check: home from book_a, away from book_b
                arb = self._check_two_way_arb(
                    game_id, game_data, book_a, book_b, "home_a_away_b"
                )
                if arb:
                    opportunities.append(arb)

                # Check: away from book_a, home from book_b
                arb = self._check_two_way_arb(
                    game_id, game_data, book_b, book_a, "home_b_away_a"
                )
                if arb:
                    opportunities.append(arb)

        # Sort by profit percentage
        opportunities.sort(key=lambda x: x["profit_pct"], reverse=True)
        logger.info(f"Found {len(opportunities)} arbitrage opportunities")
        return opportunities

    def _check_two_way_arb(self, game_id: str, game_data: Dict,
                            book_home: Dict, book_away: Dict,
                            direction: str) -> Optional[Dict[str, Any]]:
        """
        Check if there's an arbitrage between two books for a two-way market.
        book_home provides the home odds, book_away provides the away odds.
        """
        home_decimal = book_home["home_decimal"]
        away_decimal = book_away["away_decimal"]

        home_implied = self.implied_prob(home_decimal)
        away_implied = self.implied_prob(away_decimal)
        total_implied = home_implied + away_implied

        if total_implied < 1.0:
            profit_pct = ((1.0 / total_implied) - 1) * 100

            if profit_pct >= self.min_profit_pct:
                # Calculate optimal stakes for $1000 total
                total_stake = 1000.0
                stake_home = total_stake * (home_implied / total_implied)
                stake_away = total_stake * (away_implied / total_implied)

                # Guaranteed profit
                payout_home = stake_home * home_decimal
                payout_away = stake_away * away_decimal
                guaranteed_profit = min(payout_home, payout_away) - total_stake

                return {
                    "game_id": game_id,
                    "sport": game_data["sport"],
                    "home_team": game_data["home_team"],
                    "away_team": game_data["away_team"],
                    "book_a": book_home["sportsbook"],
                    "book_b": book_away["sportsbook"],
                    "side_a": "home",
                    "side_b": "away",
                    "odds_a": book_home["home_odds"],
                    "odds_b": book_away["away_odds"],
                    "decimal_a": round(home_decimal, 4),
                    "decimal_b": round(away_decimal, 4),
                    "implied_a": round(home_implied, 4),
                    "implied_b": round(away_implied, 4),
                    "total_implied": round(total_implied, 4),
                    "profit_pct": round(profit_pct, 2),
                    "stake_a": round(stake_home, 2),
                    "stake_b": round(stake_away, 2),
                    "total_stake": round(total_stake, 2),
                    "guaranteed_profit": round(guaranteed_profit, 2),
                    "detected_time": datetime.utcnow().isoformat(),
                    "status": "active",
                }

        return None

    def scan_live_odds(self, odds_provider, sport: str = "nba") -> List[Dict[str, Any]]:
        """
        Convenience method: fetch live odds and scan for arbitrage.
        """
        odds_data = odds_provider.get_odds(sport)
        return self.find_arbitrage(odds_data)

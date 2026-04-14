"""
Historical data loader - fetches and stores historical game results.
Uses ESPN API for historical scores and can generate synthetic data for backtesting.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from data.providers.espn import ESPNProvider
from data.normalization.normalizer import DataNormalizer
from storage.database import get_db
from config.logging_config import get_logger

logger = get_logger("data.historical")


class HistoricalDataLoader:
    """Loads and manages historical game data."""

    def __init__(self):
        self.espn = ESPNProvider()
        self.normalizer = DataNormalizer()
        self.db = get_db()

    def load_from_espn(self, sport: str, start_date: str, end_date: str) -> int:
        """
        Load historical game data from ESPN API and store in database.
        Returns number of games loaded.
        """
        logger.info(f"Loading historical {sport} data from {start_date} to {end_date}")
        events = self.espn.get_historical_scores(sport, start_date, end_date)
        count = 0

        for event in events:
            normalized = self.normalizer.normalize_game(event, source="espn")
            try:
                self.db.upsert_game(**normalized)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to store game {normalized.get('external_id')}: {e}")

        logger.info(f"Loaded {count} historical games for {sport}")
        return count

    def generate_synthetic_data(self, sport: str = "nba", num_games: int = 500,
                                 start_date: str = "2024-01-01") -> pd.DataFrame:
        """
        Generate synthetic historical data for backtesting when real data is unavailable.
        Creates realistic game results with scores, odds, and outcomes.
        """
        logger.info(f"Generating {num_games} synthetic games for {sport}")
        np.random.seed(42)

        teams = self._get_teams_for_sport(sport)
        start = datetime.strptime(start_date, "%Y-%m-%d")
        games = []

        for i in range(num_games):
            home_idx, away_idx = np.random.choice(len(teams), 2, replace=False)
            home_team = teams[home_idx]
            away_team = teams[away_idx]

            # Home advantage factor
            home_strength = np.random.normal(0.55, 0.15)
            home_strength = np.clip(home_strength, 0.3, 0.8)

            # Generate scores based on sport
            if sport == "nba":
                home_score = int(np.random.normal(110, 12))
                away_score = int(np.random.normal(108, 12))
                if np.random.random() < home_strength:
                    home_score = max(home_score, away_score + np.random.randint(1, 15))
                else:
                    away_score = max(away_score, home_score + np.random.randint(1, 15))
            elif sport == "nfl":
                home_score = int(np.random.normal(24, 10))
                away_score = int(np.random.normal(21, 10))
                home_score = max(0, home_score)
                away_score = max(0, away_score)
            elif sport == "mlb":
                home_score = int(np.random.exponential(4.5))
                away_score = int(np.random.exponential(4.2))
                home_score = max(0, home_score)
                away_score = max(0, away_score)
            else:
                home_score = int(np.random.normal(3, 1.5))
                away_score = int(np.random.normal(2.5, 1.5))
                home_score = max(0, home_score)
                away_score = max(0, away_score)

            # Ensure no ties for sports that don't allow them
            if home_score == away_score and sport in ("nba", "nfl"):
                home_score += 1

            winner = home_team if home_score > away_score else away_team
            game_date = start + timedelta(days=i // 5, hours=np.random.randint(17, 22))

            # Generate realistic odds
            if home_score > away_score:
                home_odds = -int(np.random.uniform(120, 300))
                away_odds = int(np.random.uniform(100, 250))
            else:
                home_odds = int(np.random.uniform(100, 250))
                away_odds = -int(np.random.uniform(120, 300))

            # Add some noise to odds
            home_odds += int(np.random.normal(0, 20))
            away_odds += int(np.random.normal(0, 20))

            games.append({
                "external_id": f"synthetic_{sport}_{i:04d}",
                "sport": sport,
                "league": sport.upper(),
                "home_team_name": home_team,
                "away_team_name": away_team,
                "scheduled_time": game_date.isoformat(),
                "status": "final",
                "home_score": home_score,
                "away_score": away_score,
                "winner": winner,
                "home_odds": home_odds,
                "away_odds": away_odds,
                "home_win_prob": home_strength,
            })

        df = pd.DataFrame(games)
        logger.info(f"Generated {len(df)} synthetic games")
        return df

    def store_synthetic_data(self, df: pd.DataFrame) -> int:
        """Store synthetic data in the database."""
        count = 0
        for _, row in df.iterrows():
            game_data = {
                "external_id": row["external_id"],
                "sport": row["sport"],
                "league": row["league"],
                "home_team_name": row["home_team_name"],
                "away_team_name": row["away_team_name"],
                "scheduled_time": row["scheduled_time"],
                "status": row["status"],
                "home_score": int(row["home_score"]),
                "away_score": int(row["away_score"]),
                "winner": row["winner"],
            }
            try:
                game_id = self.db.upsert_game(**game_data)

                # Also store odds
                self.db.insert_odds_snapshot(
                    game_id=game_id,
                    external_game_id=row["external_id"],
                    sport=row["sport"],
                    sportsbook="synthetic",
                    market_type="h2h",
                    home_odds=float(row["home_odds"]),
                    away_odds=float(row["away_odds"]),
                    source="synthetic",
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to store synthetic game: {e}")

        logger.info(f"Stored {count} synthetic games in database")
        return count

    def get_historical_dataframe(self, sport: str = None, limit: int = 1000) -> pd.DataFrame:
        """Get historical data as a pandas DataFrame for modeling."""
        games = self.db.get_games(sport=sport, status="final", limit=limit)
        if not games:
            return pd.DataFrame()
        return pd.DataFrame(games)

    @staticmethod
    def _get_teams_for_sport(sport: str) -> List[str]:
        """Get team names for a sport."""
        teams = {
            "nba": [
                "Los Angeles Lakers", "Boston Celtics", "Golden State Warriors",
                "Miami Heat", "Milwaukee Bucks", "Philadelphia 76ers",
                "Denver Nuggets", "Phoenix Suns", "Dallas Mavericks",
                "Brooklyn Nets", "Memphis Grizzlies", "Cleveland Cavaliers",
                "New York Knicks", "Sacramento Kings", "Minnesota Timberwolves",
                "Oklahoma City Thunder", "New Orleans Pelicans", "Atlanta Hawks",
                "Chicago Bulls", "Toronto Raptors",
            ],
            "nfl": [
                "Kansas City Chiefs", "San Francisco 49ers", "Philadelphia Eagles",
                "Dallas Cowboys", "Buffalo Bills", "Baltimore Ravens",
                "Miami Dolphins", "Detroit Lions", "Cincinnati Bengals",
                "Jacksonville Jaguars", "Cleveland Browns", "Green Bay Packers",
                "Seattle Seahawks", "Pittsburgh Steelers", "New England Patriots",
                "Los Angeles Rams",
            ],
            "mlb": [
                "New York Yankees", "Los Angeles Dodgers", "Houston Astros",
                "Atlanta Braves", "Philadelphia Phillies", "Texas Rangers",
                "Baltimore Orioles", "Tampa Bay Rays", "Minnesota Twins",
                "Milwaukee Brewers", "Arizona Diamondbacks", "Toronto Blue Jays",
            ],
            "nhl": [
                "Edmonton Oilers", "Florida Panthers", "Dallas Stars",
                "New York Rangers", "Vancouver Canucks", "Colorado Avalanche",
                "Boston Bruins", "Carolina Hurricanes", "Winnipeg Jets",
                "Nashville Predators",
            ],
        }
        return teams.get(sport, teams["nba"])

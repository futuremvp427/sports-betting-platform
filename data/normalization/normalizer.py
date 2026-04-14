"""
Data normalization layer.
Standardizes data from different providers into a unified internal format.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime

from config.logging_config import get_logger

logger = get_logger("data.normalizer")

# Team name normalization map (common variations)
TEAM_NAME_MAP = {
    # NBA
    "la lakers": "Los Angeles Lakers",
    "lakers": "Los Angeles Lakers",
    "la clippers": "Los Angeles Clippers",
    "clippers": "Los Angeles Clippers",
    "gs warriors": "Golden State Warriors",
    "warriors": "Golden State Warriors",
    "ny knicks": "New York Knicks",
    "knicks": "New York Knicks",
    "okc thunder": "Oklahoma City Thunder",
    "thunder": "Oklahoma City Thunder",
    "phx suns": "Phoenix Suns",
    "suns": "Phoenix Suns",
    # NFL
    "kc chiefs": "Kansas City Chiefs",
    "chiefs": "Kansas City Chiefs",
    "sf 49ers": "San Francisco 49ers",
    "49ers": "San Francisco 49ers",
    "ne patriots": "New England Patriots",
    "patriots": "New England Patriots",
    # MLB
    "ny yankees": "New York Yankees",
    "yankees": "New York Yankees",
    "la dodgers": "Los Angeles Dodgers",
    "dodgers": "Los Angeles Dodgers",
}


class DataNormalizer:
    """Normalizes data from various providers into standard internal format."""

    @staticmethod
    def normalize_team_name(name: str) -> str:
        """Normalize a team name to its canonical form."""
        if not name:
            return name
        lower = name.strip().lower()
        return TEAM_NAME_MAP.get(lower, name.strip())

    @staticmethod
    def normalize_american_odds(odds: float) -> Dict[str, float]:
        """
        Convert American odds to multiple formats.
        Returns dict with american, decimal, implied_probability.
        """
        if odds is None:
            return {"american": None, "decimal": None, "implied_probability": None}

        american = float(odds)
        if american > 0:
            decimal = (american / 100) + 1
            implied_prob = 100 / (american + 100)
        elif american < 0:
            decimal = (100 / abs(american)) + 1
            implied_prob = abs(american) / (abs(american) + 100)
        else:
            decimal = 1.0
            implied_prob = 1.0

        return {
            "american": american,
            "decimal": round(decimal, 4),
            "implied_probability": round(implied_prob, 4),
        }

    @staticmethod
    def normalize_decimal_odds(odds: float) -> Dict[str, float]:
        """Convert decimal odds to multiple formats."""
        if odds is None or odds <= 1:
            return {"american": None, "decimal": None, "implied_probability": None}

        decimal = float(odds)
        implied_prob = 1 / decimal

        if decimal >= 2.0:
            american = (decimal - 1) * 100
        else:
            american = -100 / (decimal - 1)

        return {
            "american": round(american, 1),
            "decimal": round(decimal, 4),
            "implied_probability": round(implied_prob, 4),
        }

    @staticmethod
    def normalize_game(raw_game: Dict[str, Any], source: str = "unknown") -> Dict[str, Any]:
        """Normalize a game record from any source."""
        return {
            "external_id": raw_game.get("external_id") or raw_game.get("id"),
            "sport": raw_game.get("sport", "unknown").lower(),
            "league": raw_game.get("league", raw_game.get("sport", "unknown")).upper(),
            "home_team_name": DataNormalizer.normalize_team_name(
                raw_game.get("home_team_name") or raw_game.get("home_team", "")
            ),
            "away_team_name": DataNormalizer.normalize_team_name(
                raw_game.get("away_team_name") or raw_game.get("away_team", "")
            ),
            "scheduled_time": raw_game.get("scheduled_time") or raw_game.get("commence_time"),
            "status": raw_game.get("status", "scheduled"),
            "home_score": raw_game.get("home_score"),
            "away_score": raw_game.get("away_score"),
            "winner": raw_game.get("winner"),
            "venue": raw_game.get("venue"),
            "season": raw_game.get("season"),
            "metadata": str({"source": source}),
        }

    @staticmethod
    def normalize_odds_snapshot(raw_odds: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an odds snapshot from any source."""
        normalized = {
            "external_game_id": raw_odds.get("external_game_id"),
            "sport": raw_odds.get("sport", "unknown").lower(),
            "sportsbook": raw_odds.get("sportsbook", "unknown"),
            "market_type": raw_odds.get("market_type", "h2h"),
            "snapshot_time": raw_odds.get("snapshot_time", datetime.utcnow().isoformat()),
            "source": raw_odds.get("source", "unknown"),
        }

        # Normalize H2H odds
        if raw_odds.get("home_odds") is not None:
            home_conv = DataNormalizer.normalize_american_odds(raw_odds["home_odds"])
            normalized["home_odds"] = home_conv["american"]
        if raw_odds.get("away_odds") is not None:
            away_conv = DataNormalizer.normalize_american_odds(raw_odds["away_odds"])
            normalized["away_odds"] = away_conv["american"]
        if raw_odds.get("draw_odds") is not None:
            draw_conv = DataNormalizer.normalize_american_odds(raw_odds["draw_odds"])
            normalized["draw_odds"] = draw_conv["american"]

        # Normalize spread odds
        for key in ("spread_home", "spread_away", "spread_home_odds", "spread_away_odds",
                     "total_over", "total_under", "total_over_odds", "total_under_odds"):
            if raw_odds.get(key) is not None:
                normalized[key] = raw_odds[key]

        return normalized

    @staticmethod
    def normalize_batch(items: List[Dict], item_type: str = "game",
                        source: str = "unknown") -> List[Dict]:
        """Normalize a batch of items."""
        if item_type == "game":
            return [DataNormalizer.normalize_game(item, source) for item in items]
        elif item_type == "odds":
            return [DataNormalizer.normalize_odds_snapshot(item) for item in items]
        else:
            logger.warning(f"Unknown item type: {item_type}")
            return items

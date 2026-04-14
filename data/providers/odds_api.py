"""
The Odds API provider - fetches live odds from multiple sportsbooks.
Adapted from the-odds-api/samples-python and skill patterns.
"""
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import BaseProvider
from config import settings
from config.logging_config import get_logger

logger = get_logger("data.odds_api")

# Sport key mapping for The Odds API
SPORT_KEY_MAP = {
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "mlb": "baseball_mlb",
    "nhl": "icehockey_nhl",
    "ncaab": "basketball_ncaab",
    "ncaaf": "americanfootball_ncaaf",
    "mls": "soccer_usa_mls",
    "epl": "soccer_epl",
    "soccer": "soccer_epl",
}


class OddsAPIProvider(BaseProvider):
    """Provider for The Odds API - real-time odds from multiple sportsbooks."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.odds_api.api_key
        self.base_url = settings.odds_api.base_url
        self._remaining_requests = None
        self._used_requests = None

    @property
    def provider_name(self) -> str:
        return "the_odds_api"

    def _make_request(self, endpoint: str, params: Dict = None) -> Any:
        """Make an authenticated request to The Odds API."""
        if not self.api_key:
            logger.warning("No Odds API key configured. Using demo mode.")
            return self._get_demo_data(endpoint)

        url = f"{self.base_url}/{endpoint}"
        default_params = {"apiKey": self.api_key}
        if params:
            default_params.update(params)

        try:
            response = requests.get(url, params=default_params, timeout=30)
            self._remaining_requests = response.headers.get("x-requests-remaining")
            self._used_requests = response.headers.get("x-requests-used")
            logger.info(f"Odds API: {self._remaining_requests} requests remaining")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Odds API request failed: {e}")
            return self._get_demo_data(endpoint)

    def get_sports(self) -> List[Dict[str, Any]]:
        """Get list of available sports."""
        data = self._make_request("sports")
        if isinstance(data, list):
            return [
                {
                    "key": s.get("key"),
                    "group": s.get("group"),
                    "title": s.get("title"),
                    "active": s.get("active", False),
                }
                for s in data
            ]
        return data

    def get_events(self, sport: str, **kwargs) -> List[Dict[str, Any]]:
        """Get upcoming events for a sport."""
        sport_key = SPORT_KEY_MAP.get(sport.lower(), sport)
        data = self._make_request(f"sports/{sport_key}/events")
        if isinstance(data, list):
            return [
                {
                    "external_id": e.get("id"),
                    "sport": sport,
                    "home_team": e.get("home_team"),
                    "away_team": e.get("away_team"),
                    "scheduled_time": e.get("commence_time"),
                    "source": self.provider_name,
                }
                for e in data
            ]
        return data if isinstance(data, list) else []

    def get_odds(self, sport: str, regions: str = None, markets: str = None,
                 odds_format: str = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get odds for all upcoming events in a sport.
        Returns normalized odds snapshots.
        """
        sport_key = SPORT_KEY_MAP.get(sport.lower(), sport)
        params = {
            "regions": regions or settings.odds_api.default_regions,
            "markets": markets or settings.odds_api.default_markets,
            "oddsFormat": odds_format or settings.odds_api.default_odds_format,
        }

        data = self._make_request(f"sports/{sport_key}/odds", params)
        if not isinstance(data, list):
            return []

        odds_list = []
        for event in data:
            event_id = event.get("id")
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            commence_time = event.get("commence_time")

            for bookmaker in event.get("bookmakers", []):
                book_name = bookmaker.get("key", bookmaker.get("title", "unknown"))
                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "h2h")
                    outcomes = {o["name"]: o.get("price") for o in market.get("outcomes", [])}
                    point_map = {o["name"]: o.get("point") for o in market.get("outcomes", [])}

                    odds_entry = {
                        "external_game_id": event_id,
                        "sport": sport,
                        "sportsbook": book_name,
                        "market_type": market_key,
                        "home_team": home_team,
                        "away_team": away_team,
                        "scheduled_time": commence_time,
                        "snapshot_time": datetime.utcnow().isoformat(),
                        "source": self.provider_name,
                    }

                    if market_key == "h2h":
                        odds_entry["home_odds"] = outcomes.get(home_team)
                        odds_entry["away_odds"] = outcomes.get(away_team)
                        odds_entry["draw_odds"] = outcomes.get("Draw")
                    elif market_key == "spreads":
                        odds_entry["spread_home"] = point_map.get(home_team)
                        odds_entry["spread_away"] = point_map.get(away_team)
                        odds_entry["spread_home_odds"] = outcomes.get(home_team)
                        odds_entry["spread_away_odds"] = outcomes.get(away_team)
                    elif market_key == "totals":
                        odds_entry["total_over"] = point_map.get("Over")
                        odds_entry["total_under"] = point_map.get("Under")
                        odds_entry["total_over_odds"] = outcomes.get("Over")
                        odds_entry["total_under_odds"] = outcomes.get("Under")

                    odds_list.append(odds_entry)

        logger.info(f"Fetched {len(odds_list)} odds entries for {sport}")
        return odds_list

    def get_odds_by_event(self, sport: str, event_id: str, **kwargs) -> List[Dict[str, Any]]:
        """Get odds for a specific event."""
        sport_key = SPORT_KEY_MAP.get(sport.lower(), sport)
        params = {
            "regions": kwargs.get("regions", settings.odds_api.default_regions),
            "markets": kwargs.get("markets", settings.odds_api.default_markets),
            "oddsFormat": kwargs.get("odds_format", settings.odds_api.default_odds_format),
        }
        data = self._make_request(f"sports/{sport_key}/events/{event_id}/odds", params)
        return data if isinstance(data, list) else []

    def _get_demo_data(self, endpoint: str) -> List[Dict[str, Any]]:
        """Return demo data when no API key is available.
        Features Caesars Sportsbook and PrizePicks as primary platforms."""
        logger.info("Returning demo data (no API key) — Caesars & PrizePicks featured")
        now = datetime.utcnow().isoformat()

        if "sports" in endpoint:
            return [
                {"key": "basketball_nba", "group": "Basketball", "title": "NBA", "active": True},
                {"key": "americanfootball_nfl", "group": "American Football", "title": "NFL", "active": True},
                {"key": "baseball_mlb", "group": "Baseball", "title": "MLB", "active": True},
                {"key": "icehockey_nhl", "group": "Ice Hockey", "title": "NHL", "active": True},
            ]

        if "odds" in endpoint:
            return [
                {
                    "id": "demo_event_001",
                    "sport_key": "basketball_nba",
                    "home_team": "Los Angeles Lakers",
                    "away_team": "Boston Celtics",
                    "commence_time": now,
                    "bookmakers": [
                        {
                            "key": "caesars",
                            "title": "Caesars Sportsbook",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Los Angeles Lakers", "price": -148},
                                        {"name": "Boston Celtics", "price": 128},
                                    ],
                                },
                                {
                                    "key": "spreads",
                                    "outcomes": [
                                        {"name": "Los Angeles Lakers", "price": -110, "point": -3.5},
                                        {"name": "Boston Celtics", "price": -110, "point": 3.5},
                                    ],
                                },
                                {
                                    "key": "totals",
                                    "outcomes": [
                                        {"name": "Over", "price": -108, "point": 224.5},
                                        {"name": "Under", "price": -112, "point": 224.5},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "prizepicks",
                            "title": "PrizePicks",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Los Angeles Lakers", "price": -152},
                                        {"name": "Boston Celtics", "price": 132},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "draftkings",
                            "title": "DraftKings",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Los Angeles Lakers", "price": -150},
                                        {"name": "Boston Celtics", "price": 130},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "fanduel",
                            "title": "FanDuel",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Los Angeles Lakers", "price": -145},
                                        {"name": "Boston Celtics", "price": 125},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "betmgm",
                            "title": "BetMGM",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Los Angeles Lakers", "price": -155},
                                        {"name": "Boston Celtics", "price": 135},
                                    ],
                                },
                            ],
                        },
                    ],
                },
                {
                    "id": "demo_event_002",
                    "sport_key": "basketball_nba",
                    "home_team": "Golden State Warriors",
                    "away_team": "Miami Heat",
                    "commence_time": now,
                    "bookmakers": [
                        {
                            "key": "caesars",
                            "title": "Caesars Sportsbook",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Golden State Warriors", "price": -195},
                                        {"name": "Miami Heat", "price": 168},
                                    ],
                                },
                                {
                                    "key": "spreads",
                                    "outcomes": [
                                        {"name": "Golden State Warriors", "price": -108, "point": -5.5},
                                        {"name": "Miami Heat", "price": -112, "point": 5.5},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "prizepicks",
                            "title": "PrizePicks",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Golden State Warriors", "price": -188},
                                        {"name": "Miami Heat", "price": 162},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "draftkings",
                            "title": "DraftKings",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Golden State Warriors", "price": -200},
                                        {"name": "Miami Heat", "price": 170},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "fanduel",
                            "title": "FanDuel",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Golden State Warriors", "price": -190},
                                        {"name": "Miami Heat", "price": 165},
                                    ],
                                },
                            ],
                        },
                    ],
                },
                {
                    "id": "demo_event_003",
                    "sport_key": "basketball_nba",
                    "home_team": "Denver Nuggets",
                    "away_team": "Phoenix Suns",
                    "commence_time": now,
                    "bookmakers": [
                        {
                            "key": "caesars",
                            "title": "Caesars Sportsbook",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Denver Nuggets", "price": -175},
                                        {"name": "Phoenix Suns", "price": 150},
                                    ],
                                },
                            ],
                        },
                        {
                            "key": "prizepicks",
                            "title": "PrizePicks",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Denver Nuggets", "price": -168},
                                        {"name": "Phoenix Suns", "price": 145},
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ]

        # Default events
        return [
            {
                "id": "demo_event_001",
                "home_team": "Los Angeles Lakers",
                "away_team": "Boston Celtics",
                "commence_time": now,
            },
            {
                "id": "demo_event_002",
                "home_team": "Golden State Warriors",
                "away_team": "Miami Heat",
                "commence_time": now,
            },
            {
                "id": "demo_event_003",
                "home_team": "Denver Nuggets",
                "away_team": "Phoenix Suns",
                "commence_time": now,
            },
        ]
